"""Activity-side run execution (called by Temporal activities in the worker).

Consistency model (one global step = one participant's turn)
- Every step has two ledger rows: `<run>:s<n>:propose` and `<run>:s<n>:apply` (table `operations`).
- propose: TURN / OBSERVE / PROPOSE are computed (possibly a model call) and committed before the environment is
  touched. A retry finds the COMPLETED record and reuses it: a model is never called twice for the same step and
  tokens are counted once.
- apply: the environment operation runs through the kernel's Coordinator with a database-backed ledger (table
  `operation_records`): PREPARED / DISPATCHED are committed *before* the environment is called, the answer after.
  Pure-data environments are restored from the stored pre-step snapshot and re-executed exactly; live services are
  asked for the operation id instead of being sent the operation again (P2-053 / P2-054). The new snapshot, all
  events of the step, usage (global and per participant), the carry state (turn cursor, planner checkpoints, rule
  flags) and the COMPLETED apply record are then committed in one transaction.
- Worker restarts and lost caches are safe: components are rebuilt from the pinned manifest, planners are restored
  from the carried checkpoints, and the turn cursor comes from the database (P2-037 / P2-055).
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any

from formal_lab_contracts import (
    TERMINAL_RUN_STATUSES,
    BudgetUsage,
    EnvironmentSnapshot,
    MetricResult,
    OperationRecord,
    RunManifest,
    RunStatus,
    StepRecord,
    TerminationReason,
    compat,
    digest_of,
    utcnow,
)
from formal_lab_contracts.errors import Conflict, NonRetryableFailure
from formal_lab_runtime.engine import (
    CarryState,
    PlanPhase,
    RunComponents,
    add_usage,
    apply_step,
    event_key,
    finish_run,
    open_components,
    plan_step,
    start_run,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import (
    MetricRow,
    ModelVersion,
    Operation,
    OperationRecordRow,
    RegressionCaseRow,
    RuleSetRow,
    Run,
    RunEvent,
    Snapshot,
    session_scope,
)
from .common import get_json_artifact, put_json_artifact, registry
from .events import append_events, draft, lock_run, transition
from .modeling import package_of

log = logging.getLogger(__name__)
_CACHE: dict[str, tuple[str, RunComponents]] = {}
_CACHE_LOCK = threading.Lock()


# ------------------------------------------------------------------------ helpers


def manifest_of(run: Run) -> RunManifest:
    return compat.upgrade_run_manifest(run.manifest)


def _rulesets(s: Session, manifest: RunManifest) -> dict[str, Any]:
    if manifest.rules is None:
        return {}
    from formal_lab_contracts import RuleSet

    row = s.scalar(select(RuleSetRow).where(RuleSetRow.digest == manifest.rules.digest.value))
    if row is None:
        raise NonRetryableFailure(f"rule set {manifest.rules.ruleset_id}@{manifest.rules.version} not stored")
    return {row.digest: RuleSet.model_validate(row.body)}


def _components(s: Session, run: Run) -> RunComponents:
    manifest = manifest_of(run)
    key = digest_of(manifest.model_copy(update={"status": RunStatus.CREATED, "status_reason": None,
                                                "budget_usage": BudgetUsage(), "actor_usage": {},
                                                "termination_reason": None})).value
    with _CACHE_LOCK:
        hit = _CACHE.get(run.id)
        if hit and hit[0] == key:
            return hit[1]
    row = s.scalar(select(ModelVersion).where(ModelVersion.digest == manifest.model.digest.value,
                                              ModelVersion.version == manifest.model.version))
    if row is None:
        raise NonRetryableFailure(f"pinned model {manifest.model.package_id}@{manifest.model.version} missing")
    rc = open_components(manifest, package_of(row), registry(), rulesets=_rulesets(s, manifest))
    with _CACHE_LOCK:
        _CACHE[run.id] = (key, rc)
        if len(_CACHE) > 64:
            _CACHE.pop(next(iter(_CACHE)))
    return rc


def forget_components(run_id: str) -> None:
    """Drop the cached plugin instances of a run (tests: simulate a worker that lost its process cache)."""
    with _CACHE_LOCK:
        _CACHE.pop(run_id, None)


def _usage(run: Run, now: datetime | None = None) -> BudgetUsage:
    u = run.usage or {}
    usage = BudgetUsage.model_validate({k: v for k, v in u.items() if k in BudgetUsage.model_fields})
    if run.started_at is not None:
        now = now or utcnow()
        paused = run.paused_seconds + ((now - run.paused_at).total_seconds() if run.paused_at else 0.0)
        usage.wall_seconds = max(0.0, (now - run.started_at).total_seconds() - paused)
    return usage


def _save_usage(run: Run, usage: BudgetUsage, actor_usage: dict[str, Any] | None = None) -> None:
    extra = {k: v for k, v in (run.usage or {}).items() if k not in BudgetUsage.model_fields}
    if actor_usage is not None:
        extra["actors"] = actor_usage
    run.usage = {**extra, **usage.model_dump(), "tokens": usage.tokens}
    manifest = dict(run.manifest)
    manifest["budget_usage"] = usage.model_dump()
    if actor_usage is not None and run.contract_version != "formal-lab-contracts/v1":
        manifest["actor_usage"] = actor_usage
    run.manifest = manifest


def _carry(run: Run, rc: RunComponents) -> CarryState:
    if run.carry:
        return CarryState.from_json(run.carry)
    return CarryState(turn=rc.scheduler.initial_state())


def _store_snapshot(s: Session, run_id: str, step: int, snap: EnvironmentSnapshot) -> None:
    if s.get(Snapshot, (run_id, step)) is not None:
        return
    ref = put_json_artifact(s, run_id=run_id, kind="snapshot", name=f"{run_id}-step-{step}.json",
                            obj=snap.model_dump(mode="json"), format_version="formal-lab/env-snapshot@1")
    s.add(Snapshot(run_id=run_id, step=step, state_revision=snap.state_revision, digest=snap.digest.value,
                   artifact=ref.model_dump(mode="json")))


def load_snapshot(s: Session, run_id: str, step: int) -> EnvironmentSnapshot:
    row = s.get(Snapshot, (run_id, step))
    if row is None:
        raise NonRetryableFailure(f"no snapshot for {run_id} step {step}")
    return EnvironmentSnapshot.model_validate(get_json_artifact(row.artifact))


def latest_snapshot_step(s: Session, run_id: str) -> int | None:
    from sqlalchemy import func

    return s.scalar(select(func.max(Snapshot.step)).where(Snapshot.run_id == run_id))


def _op(s: Session, op_id: str) -> Operation | None:
    return s.get(Operation, op_id)


def _stop_result(run: Run) -> dict[str, Any] | None:
    status = RunStatus(run.status)
    if status in TERMINAL_RUN_STATUSES:
        return {"terminal": True, "status": status.value, "reason": run.status_reason, "finalized": True}
    if status == RunStatus.CANCELLING:
        return {"terminal": True, "status": RunStatus.CANCELLED.value, "reason": "cancellation requested",
                "finalized": False}
    return None


class DbLedger:
    """OperationLedger on `operation_records`: each put is its own committed transaction, so the intent is durable
    before the environment is called."""

    def get(self, operation_id: str) -> OperationRecord | None:
        with session_scope() as s:
            row = s.get(OperationRecordRow, operation_id)
            return OperationRecord.model_validate(row.record) if row is not None else None

    def put(self, record: OperationRecord) -> None:
        with session_scope() as s:
            row = s.get(OperationRecordRow, record.operation_id, with_for_update=True)
            data = record.model_dump(mode="json")
            review = record.review is not None and record.review.status == "NEEDS_REVIEW"
            if row is None:
                s.add(OperationRecordRow(operation_id=record.operation_id, run_id=record.run_id, step=record.step,
                                         actor_id=record.actor_id, state=record.state.value, needs_review=review,
                                         record=data))
            else:
                row.state, row.record, row.needs_review = record.state.value, data, review


# ------------------------------------------------------------------------ activities


def prepare_run(run_id: str) -> dict[str, Any]:
    """QUEUED → RUNNING: reset the environment, store snapshot 0, the initial carry state and start events."""
    with session_scope() as s:
        run = lock_run(s, run_id)
        stop = _stop_result(run)
        if stop:
            return stop
        last = latest_snapshot_step(s, run_id)
        if last is not None:  # already prepared (activity retry / workflow continue-as-new)
            return {"terminal": False, "next_step": run.last_step + 1}
        rc = _components(s, run)
        start = start_run(rc)
        _store_snapshot(s, run_id, 0, start.snapshot)
        if run.status == RunStatus.QUEUED.value:
            transition(run, RunStatus.RUNNING)
        run.started_at = run.started_at or utcnow()
        run.carry = start.carry.to_json()
        append_events(s, run, start.events)
        s.add(Operation(operation_id=f"{run_id}:run:start", run_id=run_id, step=0, kind="start", status="COMPLETED",
                        result={"snapshot_digest": start.snapshot.digest.value}))
        return {"terminal": False, "next_step": 1}


def run_step(run_id: str, step: int) -> dict[str, Any]:
    propose_id, apply_id = f"{run_id}:s{step}:propose", f"{run_id}:s{step}:apply"
    # ---- phase 0: read state, reconcile ledger rows
    with session_scope() as s:
        run = s.get(Run, run_id)
        if run is None:
            raise NonRetryableFailure(f"run {run_id} not found")
        stop = _stop_result(run)
        if stop:
            return stop
        done = _op(s, apply_id)
        if done is not None and done.status == "COMPLETED":
            return dict(done.result or {})
        rc = _components(s, run)
        snapshot = load_snapshot(s, run_id, step - 1)
        usage = _usage(run)
        carry = _carry(run, rc)
        recorded = _op(s, propose_id)
        plan = PlanPhase.from_json(recorded.result) if recorded and recorded.status == "COMPLETED" else None
        recovered = recorded is not None and plan is not None

    # ---- phase 1: plan (may call a model); persist before touching the environment
    if plan is None:
        plan = plan_step(rc, snapshot, step, usage, carry)
        with session_scope() as s:
            refs = [put_json_artifact(s, run_id=run_id, kind="model_call", name=f"{c['call_id']}.json", obj=c,
                                      format_version="formal-lab/model-call@1").model_dump(mode="json")
                    for c in plan.model_calls]
            for ev in plan.events:
                if ev.event_type.value == "ACTION_PROPOSED":
                    ev.payload["model_call_artifacts"] = refs
            existing = _op(s, propose_id)
            if existing is None:
                s.add(Operation(operation_id=propose_id, run_id=run_id, step=step, kind="propose",
                                status="COMPLETED", result=plan.to_json()))
            elif existing.status == "COMPLETED":  # a concurrent attempt won; use its plan
                plan = PlanPhase.from_json(existing.result)
            else:
                existing.status, existing.result, existing.attempts = "COMPLETED", plan.to_json(), existing.attempts + 1

    # ---- phase 2: apply through the coordinator (pure envs: deterministic w.r.t. snapshot) and commit atomically
    ex = apply_step(rc, snapshot, plan, carry, DbLedger())
    with session_scope() as s:
        run = lock_run(s, run_id)
        done = _op(s, apply_id)
        if done is not None and done.status == "COMPLETED":
            return dict(done.result or {})
        if RunStatus(run.status) in TERMINAL_RUN_STATUSES:  # finalised meanwhile: never append after the end
            return _stop_result(run) or {"terminal": True, "status": run.status, "finalized": True}
        if ex.snapshot is not None and ex.observation is not None:
            _store_snapshot(s, run_id, step, ex.snapshot)
        events = list(ex.events)
        if recovered:
            events.insert(0, draft(f"{run_id}:s{step}:recovery", "RECOVERY", step,
                                   {"kind": "resumed-from-ledger", "step": step,
                                    "note": "the step's proposal was already committed by an earlier attempt; "
                                            "reused (no second model call), planner restored from the checkpoint"},
                                   [carry.last_event_key] if carry.last_event_key else []))
        append_events(s, run, events)
        usage = _usage(run)
        if ex.observation is not None:
            usage = add_usage(usage, ex.usage_delta, steps=1)
            run.last_step = step
        new_carry = ex.carry or carry
        run.carry = new_carry.to_json()
        _save_usage(run, usage, new_carry.actor_usage)
        if ex.termination_reason is not None:
            run.termination_reason = ex.termination_reason.value
        if ex.regression_case is not None and s.get(RegressionCaseRow, ex.regression_case.case_id) is None:
            s.add(RegressionCaseRow(case_id=ex.regression_case.case_id, project_id=run.project_id,
                                    model_digest=ex.regression_case.model.digest.value,
                                    source=ex.regression_case.source, origin_run_id=run_id,
                                    case=ex.regression_case.model_dump(mode="json")))
        pause = None
        if ex.pause_requested and ex.terminal is None and run.status == RunStatus.RUNNING.value:
            n = int(run.usage.get("pause_requests", 0)) + 1
            run.usage = {**run.usage, "pause_requests": n}
            transition(run, RunStatus.PAUSING, f"paused by rule: {ex.pause_requested}")
            append_events(s, run, [draft(f"{run_id}:run:pausing:{n}", "RUN_PAUSING", step,
                                         {"requested_at": utcnow().isoformat(), "by": "rule",
                                          "reason": ex.pause_requested, "boundary": "after this step"},
                                         [new_carry.last_event_key] if new_carry.last_event_key else [])])
            pause = ex.pause_requested
        result = {"terminal": ex.terminal is not None, "status": ex.terminal.value if ex.terminal else None,
                  "reason": ex.terminal_reason, "next_step": step + 1, "finalized": False,
                  "termination_reason": ex.termination_reason.value if ex.termination_reason else None,
                  "outcome": ex.outcome.status.value if ex.outcome else None,
                  "actor_id": ex.turn.actor_id if ex.turn else None, "pause_requested": pause}
        s.add(Operation(operation_id=apply_id, run_id=run_id, step=step, kind="apply", status="COMPLETED",
                        result=result))
        return result


def mark_paused(run_id: str) -> dict[str, Any]:
    with session_scope() as s:
        run = lock_run(s, run_id)
        if run.status != RunStatus.PAUSING.value:
            return {"status": run.status}
        n = int(run.usage.get("pause_requests", 0))
        transition(run, RunStatus.PAUSED, f"paused at logical-step boundary after step {run.last_step}")
        run.paused_at = utcnow()
        append_events(s, run, [draft(f"{run_id}:run:paused:{n}", "RUN_PAUSED", run.last_step,
                                     {"after_step": run.last_step,
                                      "turn": (run.carry or {}).get("turn")}, [f"{run_id}:run:pausing:{n}"])])
        return {"status": run.status}


def mark_resumed(run_id: str) -> dict[str, Any]:
    with session_scope() as s:
        run = lock_run(s, run_id)
        if run.status not in (RunStatus.PAUSED.value, RunStatus.PAUSING.value):
            return {"status": run.status}
        n = int(run.usage.get("pause_requests", 0))
        paused_for = (utcnow() - run.paused_at).total_seconds() if run.paused_at else 0.0
        run.paused_seconds += paused_for
        run.paused_at = None
        transition(run, RunStatus.RUNNING, "resumed")
        append_events(s, run, [draft(f"{run_id}:run:resumed:{n}", "RUN_RESUMED", run.last_step,
                                     {"paused_seconds": round(paused_for, 3),
                                      "turn": (run.carry or {}).get("turn")}, [f"{run_id}:run:paused:{n}"])])
        return {"status": run.status}


def step_records(s: Session, run_id: str) -> list[StepRecord]:
    """StepRecords from the stored events (v1 rows are upgraded on the way)."""
    from formal_lab_contracts import (
        ActionOutcome,
        ActionProposal,
        BoundedCheckResult,
        Observation,
        ProbeResult,
        TurnRef,
    )

    by_step: dict[int, dict[str, Any]] = {}
    for row in s.scalars(select(RunEvent).where(RunEvent.run_id == run_id, RunEvent.logical_step.is_not(None),
                                                RunEvent.logical_step > 0).order_by(RunEvent.seq)):
        slot = by_step.setdefault(row.logical_step, {"checks": [], "probes": []})
        p = compat.upgrade_event_payload(row.event_type, row.payload)
        if row.turn and "turn" not in slot:
            slot["turn"] = TurnRef.model_validate(row.turn)
        if row.event_type == "OBSERVATION":
            slot["observation"] = Observation.model_validate(p["observation"])
            slot.setdefault("actor_id", row.actor_id)
        elif row.event_type == "OBSERVATION_REQUESTED":
            slot["observation"] = Observation.model_validate(p["observation"])
        elif row.event_type == "ACTION_PROPOSED":
            slot["proposal"] = ActionProposal.model_validate(p["proposal"])
        elif row.event_type == "ACTION_OUTCOME":
            slot["outcome"] = ActionOutcome.model_validate(p["outcome"])
            if p.get("operation"):
                slot["operation"] = OperationRecord.model_validate(p["operation"])
        elif row.event_type == "CHECK_COMPLETED":
            slot["checks"].append(compat.upgrade_check_result(p["result"]))
        elif row.event_type == "PROBE_SAMPLED":
            slot["probes"] += [ProbeResult.model_validate(x) for x in p.get("results", [])]
    _ = BoundedCheckResult
    return [StepRecord(step=k, observation=v["observation"], proposal=v.get("proposal"), outcome=v.get("outcome"),
                       checks=v["checks"], actor_id=v.get("actor_id"), turn=v.get("turn"),
                       operation=v.get("operation"), probes=v["probes"])
            for k, v in sorted(by_step.items()) if "observation" in v]


def finalize_run(run_id: str, status: str, reason: str | None = None, error: dict[str, Any] | None = None) -> dict:
    """Terminal transition + metrics from the last snapshot (idempotent)."""
    with session_scope() as s:
        run = lock_run(s, run_id)
        current = RunStatus(run.status)
        if current in TERMINAL_RUN_STATUSES:
            return {"terminal": True, "status": current.value, "reason": run.status_reason, "finalized": True}
        target = RunStatus(status)
        if current == RunStatus.CANCELLING and target not in TERMINAL_RUN_STATUSES:
            target = RunStatus.CANCELLED
        term = TerminationReason(run.termination_reason) if run.termination_reason else None
        if target == RunStatus.CANCELLED:
            term = TerminationReason.CANCELLED
        elif target == RunStatus.FAILED and term is None:
            term = TerminationReason.FAILED
        elif target == RunStatus.BUDGET_EXHAUSTED and term is None:
            term = TerminationReason.BUDGET_EXHAUSTED
        run.termination_reason = term.value if term else None
        last = latest_snapshot_step(s, run_id)
        snapshot = load_snapshot(s, run_id, last) if last is not None else None
        usage = _usage(run)
        steps = step_records(s, run_id)
        metrics: list[MetricResult] = []
        carry = run.carry or {}
        try:
            rc = _components(s, run)
            parent = carry.get("last_event_key") or (event_key(run_id, run.last_step, "comparison") if run.last_step
                                                     else event_key(run_id, 0, "snapshot"))
            fin = finish_run(rc, status=target, reason=reason, final_snapshot=snapshot, usage=usage, steps=steps,
                             last_step=run.last_step, parent_key=parent, termination_reason=term,
                             actor_usage=carry.get("actor_usage", {}),
                             probes=[p for st in steps for p in st.probes])
            metrics = fin.metrics
            append_events(s, run, fin.events)
            run.final_state = {"truth_state": fin.final_state, "properties": fin.properties}
        except Exception as exc:  # scoring must not hide the terminal status; keep evidence of the failure
            log.exception("finalize scoring failed for %s", run_id)
            append_events(s, run, [draft(f"{run_id}:run:terminal", {
                RunStatus.SUCCEEDED: "RUN_SUCCEEDED", RunStatus.FAILED: "RUN_FAILED",
                RunStatus.CANCELLED: "RUN_CANCELLED", RunStatus.BUDGET_EXHAUSTED: "BUDGET_EXHAUSTED"}[target],
                run.last_step, {"status": target.value, "reason": reason, "scoring_error": repr(exc),
                                "termination_reason": term.value if term else None})])
        for mres in metrics:
            row = s.get(MetricRow, (run_id, mres.metric_id))
            data = mres.model_dump(mode="json")
            if row is None:
                s.add(MetricRow(run_id=run_id, metric_id=mres.metric_id, result=data, value=mres.value,
                                status=mres.status.value))
            else:
                row.result, row.value, row.status = data, mres.value, mres.status.value
        try:
            transition(run, target, reason)
        except Conflict:
            run.status, run.status_reason = target.value, reason
        if run.contract_version != "formal-lab-contracts/v1":
            manifest = dict(run.manifest)
            manifest["termination_reason"] = run.termination_reason
            run.manifest = manifest
        run.error = error
        run.finished_at = utcnow()
        _save_usage(run, usage, carry.get("actor_usage"))
        return {"terminal": True, "status": target.value, "reason": reason, "finalized": True,
                "termination_reason": run.termination_reason}
