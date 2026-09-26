"""Activity-side run execution (called by Temporal activities in the worker).

Consistency model
- Every step has two operation records: `<run>:s<n>:propose` and `<run>:s<n>:apply`.
- propose: observation, candidates and the strategy proposal (possibly a model call) are computed and the
  result is committed before the environment is touched. A retry finds the COMPLETED record and reuses it,
  so a model is never called twice for the same step and tokens are counted once.
- apply: the environment transition is pure with respect to the stored snapshot. The new snapshot, all events
  of the step, usage counters and the COMPLETED apply record are committed in one transaction, so an apply
  whose outcome is unknown (worker died) is reconciled by reading the record: absent ⇒ nothing was applied
  ⇒ safe to re-execute; present ⇒ return the recorded result.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any

from formal_lab_contracts import (
    ActionOutcome,
    ActionProposal,
    BoundedCheckResult,
    BudgetUsage,
    EnvironmentSnapshot,
    MetricResult,
    Observation,
    RunManifest,
    RunStatus,
    StepRecord,
    TERMINAL_RUN_STATUSES,
    digest_of,
    utcnow,
)
from formal_lab_contracts.errors import Conflict, NonRetryableFailure
from formal_lab_runtime.engine import (
    PlanPhase,
    RunComponents,
    apply_step,
    event_key,
    finish_run,
    open_components,
    plan_step,
    start_run,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import MetricRow, ModelVersion, Operation, Run, RunEvent, Snapshot, session_scope
from .common import get_json_artifact, put_json_artifact, registry
from .events import append_events, draft, lock_run, transition
from .modeling import package_of

log = logging.getLogger(__name__)
_CACHE: dict[str, tuple[str, RunComponents]] = {}
_CACHE_LOCK = threading.Lock()


# ------------------------------------------------------------------------ helpers


def _components(s: Session, run: Run) -> RunComponents:
    manifest = RunManifest.model_validate(run.manifest)
    key = digest_of(manifest.model_copy(update={"status": RunStatus.CREATED, "status_reason": None,
                                                "budget_usage": BudgetUsage()})).value
    with _CACHE_LOCK:
        hit = _CACHE.get(run.id)
        if hit and hit[0] == key:
            return hit[1]
    row = s.scalar(select(ModelVersion).where(ModelVersion.digest == manifest.model.digest.value,
                                              ModelVersion.version == manifest.model.version))
    if row is None:
        raise NonRetryableFailure(f"pinned model {manifest.model.package_id}@{manifest.model.version} missing")
    rc = open_components(manifest, package_of(row), registry())
    with _CACHE_LOCK:
        _CACHE[run.id] = (key, rc)
        if len(_CACHE) > 64:
            _CACHE.pop(next(iter(_CACHE)))
    return rc


def _usage(run: Run, now: datetime | None = None) -> BudgetUsage:
    u = run.usage or {}
    usage = BudgetUsage(steps=u.get("steps", 0), model_calls=u.get("model_calls", 0),
                        input_tokens=u.get("input_tokens", 0), output_tokens=u.get("output_tokens", 0))
    if run.started_at is not None:
        now = now or utcnow()
        paused = run.paused_seconds + ((now - run.paused_at).total_seconds() if run.paused_at else 0.0)
        usage.wall_seconds = max(0.0, (now - run.started_at).total_seconds() - paused)
    return usage


def _save_usage(run: Run, usage: BudgetUsage) -> None:
    extra = {k: v for k, v in (run.usage or {}).items() if k not in BudgetUsage.model_fields}
    run.usage = {**extra, **usage.model_dump(), "tokens": usage.tokens}
    manifest = dict(run.manifest)
    manifest["budget_usage"] = usage.model_dump()
    run.manifest = manifest


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


# ------------------------------------------------------------------------ activities


def prepare_run(run_id: str) -> dict[str, Any]:
    """QUEUED → RUNNING: reset the environment, store snapshot 0 and start events (idempotent)."""
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
        append_events(s, run, start.events)
        s.add(Operation(operation_id=f"{run_id}:run:start", run_id=run_id, step=0, kind="start", status="COMPLETED",
                        result={"snapshot_digest": start.snapshot.digest.value}))
        return {"terminal": False, "next_step": 1}


def run_step(run_id: str, step: int) -> dict[str, Any]:
    propose_id, apply_id = f"{run_id}:s{step}:propose", f"{run_id}:s{step}:apply"
    # ---- phase 0: read state, reconcile operation records
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
        recorded = _op(s, propose_id)
        plan = PlanPhase.from_json(recorded.result) if recorded and recorded.status == "COMPLETED" else None

    # ---- phase 1: plan (may call a model); persist before touching the environment
    if plan is None:
        plan = plan_step(rc, snapshot, step, usage)
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

    # ---- phase 2: apply (pure w.r.t. snapshot) and commit atomically
    ex = apply_step(rc, snapshot, plan)
    with session_scope() as s:
        run = lock_run(s, run_id)
        done = _op(s, apply_id)
        if done is not None and done.status == "COMPLETED":
            return dict(done.result or {})
        if RunStatus(run.status) in TERMINAL_RUN_STATUSES:  # finalised meanwhile: never append after the end
            return _stop_result(run) or {"terminal": True, "status": run.status, "finalized": True}
        if ex.snapshot is not None and ex.observation is not None:
            _store_snapshot(s, run_id, step, ex.snapshot)
        append_events(s, run, ex.events)
        usage = _usage(run)
        if ex.observation is not None:
            usage.steps += 1
            usage.model_calls += ex.usage_delta.model_calls
            usage.input_tokens += ex.usage_delta.input_tokens
            usage.output_tokens += ex.usage_delta.output_tokens
            run.last_step = step
        _save_usage(run, usage)
        result = {"terminal": ex.terminal is not None, "status": ex.terminal.value if ex.terminal else None,
                  "reason": ex.terminal_reason, "next_step": step + 1, "finalized": False,
                  "outcome": ex.outcome.status.value if ex.outcome else None}
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
                                     {"after_step": run.last_step}, [f"{run_id}:run:pausing:{n}"])])
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
                                     {"paused_seconds": round(paused_for, 3)}, [f"{run_id}:run:paused:{n}"])])
        return {"status": run.status}


def _step_records(s: Session, run_id: str) -> list[StepRecord]:
    by_step: dict[int, dict[str, Any]] = {}
    for row in s.scalars(select(RunEvent).where(RunEvent.run_id == run_id, RunEvent.logical_step.is_not(None),
                                                RunEvent.logical_step > 0).order_by(RunEvent.seq)):
        slot = by_step.setdefault(row.logical_step, {"checks": []})
        p = row.payload
        if row.event_type == "OBSERVATION":
            slot["observation"] = Observation.model_validate(p["observation"])
        elif row.event_type == "ACTION_PROPOSED":
            slot["proposal"] = ActionProposal.model_validate(p["proposal"])
        elif row.event_type == "ACTION_OUTCOME":
            slot["outcome"] = ActionOutcome.model_validate(p["outcome"])
        elif row.event_type == "CHECK_COMPLETED":
            slot["checks"].append(BoundedCheckResult.model_validate(p["result"]))
    return [StepRecord(step=k, observation=v["observation"], proposal=v.get("proposal"), outcome=v.get("outcome"),
                       checks=v["checks"]) for k, v in sorted(by_step.items()) if "observation" in v]


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
        last = latest_snapshot_step(s, run_id)
        snapshot = load_snapshot(s, run_id, last) if last is not None else None
        usage = _usage(run)
        steps = _step_records(s, run_id)
        metrics: list[MetricResult] = []
        try:
            rc = _components(s, run)
            parent = (event_key(run_id, run.last_step, "comparison") if run.last_step
                      else event_key(run_id, 0, "snapshot"))
            fin = finish_run(rc, status=target, reason=reason, final_snapshot=snapshot, usage=usage, steps=steps,
                             last_step=run.last_step, parent_key=parent)
            metrics = fin.metrics
            append_events(s, run, fin.events)
            run.final_state = {"truth_state": fin.final_state, "properties": fin.properties}
        except Exception as exc:  # scoring must not hide the terminal status; keep evidence of the failure
            log.exception("finalize scoring failed for %s", run_id)
            append_events(s, run, [draft(f"{run_id}:run:terminal", {
                RunStatus.SUCCEEDED: "RUN_SUCCEEDED", RunStatus.FAILED: "RUN_FAILED",
                RunStatus.CANCELLED: "RUN_CANCELLED", RunStatus.BUDGET_EXHAUSTED: "BUDGET_EXHAUSTED"}[target],
                run.last_step, {"status": target.value, "reason": reason, "scoring_error": repr(exc)})])
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
        run.error = error
        run.finished_at = utcnow()
        _save_usage(run, usage)
        return {"terminal": True, "status": target.value, "reason": reason, "finalized": True}
