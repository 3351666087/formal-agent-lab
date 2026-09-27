"""Run lifecycle on the API side: creation (pinned manifest), control requests, queries."""

from __future__ import annotations

from typing import Any

from formal_lab_contracts import (
    CONTRACT_VERSION,
    TERMINAL_RUN_STATUSES,
    Budget,
    Participant,
    PluginRef,
    ReleaseRef,
    RunStatus,
    ScenarioManifest,
    compat,
    utcnow,
)
from formal_lab_contracts.errors import Conflict, InvalidInput
from formal_lab_runtime import make_manifest
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import MetricRow, ModelVersion, Project, Run, RunEvent, Scenario, StrategyConfig
from .common import get_or_404, new_id, registry
from .events import append_events, draft, list_events, lock_run, transition
from .modeling import package_of


def evaluators_for(package_id: str, extra: list[dict[str, Any]] | None = None) -> list[PluginRef]:
    """Evaluators whose descriptors declare they apply to this model package (or to all models)."""
    from formal_lab_contracts import PluginInterface
    from formal_lab_contracts.capabilities import EVAL_APPLIES_TO

    refs: list[PluginRef] = []
    for entry in registry().entries(PluginInterface.EVALUATOR):
        for cap in entry.descriptor.capabilities:
            if cap.id == EVAL_APPLIES_TO and (cap.params.get("all") or package_id in cap.params.get("package_ids", [])):
                refs.append(entry.descriptor.ref())
    refs.sort(key=lambda r: (r.plugin_id != "formal-lab.eval.generic", r.plugin_id))
    for e in extra or []:
        ref = PluginRef.model_validate(e)
        if ref not in refs:
            refs.append(ref)
    return refs


def _package_for(s: Session, scenario: ScenarioManifest):
    row = s.scalar(select(ModelVersion).where(ModelVersion.digest == scenario.model.digest.value,
                                              ModelVersion.version == scenario.model.version))
    if row is None:
        raise InvalidInput(f"model {scenario.model.package_id}@{scenario.model.version} is not stored on this server")
    return package_of(row)


def create_run(s: Session, project_id: str, body: dict[str, Any], *, client_request_id: str | None = None,
               source_run: Run | None = None, matrix_id: str | None = None) -> tuple[Run, bool]:
    """Create a run with a fully pinned RunManifest. Returns (run, created); a repeated client_request_id
    returns the existing run (duplicate submission is idempotent)."""
    get_or_404(s, Project, project_id, "project")
    if client_request_id:
        existing = s.scalar(select(Run).where(Run.project_id == project_id, Run.client_request_id == client_request_id))
        if existing is not None:
            return existing, False
    run_id = new_id("run")
    release = None
    if source_run is not None:  # re-run: same pinned scenario snapshot / participants / seed / budget
        src = compat.upgrade_run_manifest(source_run.manifest)
        scenario, participants, seed, budget = src.scenario, src.participants, src.seed, src.budget
        release = src.release
        evaluators = [PluginRef(plugin_id=p.plugin_id, version=p.version) for p in src.plugins
                      if p.role.startswith("evaluator")]
        scenario_id, strategy_id, config = source_run.scenario_id, source_run.strategy_config_id, {
            k: v for k, v in src.config.items() if k != "budget_dimensions"}
    else:
        sc_row = get_or_404(s, Scenario, body.get("scenario_id"), "scenario")
        if sc_row.project_id != project_id:
            raise InvalidInput("scenario belongs to another project")
        scenario = compat.upgrade_scenario(sc_row.manifest)
        participants = list(scenario.participants)
        strategy_id = body.get("strategy_config_id")
        per_actor = dict(body.get("participant_strategies") or {})
        unknown = set(per_actor) - {p.actor_id for p in participants}
        if unknown:
            raise InvalidInput(f"participant_strategies names unknown participants {sorted(unknown)}")

        def with_strategy(p: Participant, sid: str) -> Participant:
            st = get_or_404(s, StrategyConfig, sid, "strategy")
            return p.model_copy(update={"strategy": {"plugin": {"plugin_id": st.plugin_id,
                                                                "version": st.plugin_version},
                                                     "config": st.config}})

        participants = [with_strategy(p, per_actor.get(p.actor_id) or strategy_id)
                        if (per_actor.get(p.actor_id) or strategy_id) else p for p in participants]
        participants = [Participant.model_validate(p.model_dump(mode="json")) for p in participants]
        seed = int(body["seed"]) if body.get("seed") is not None else scenario.seed
        budget = Budget.model_validate({**scenario.budget.model_dump(exclude_none=True), **(body.get("budget") or {})})
        evaluators = evaluators_for(scenario.model.package_id, body.get("evaluators"))
        scenario_id, config = sc_row.id, dict(body.get("config") or {})
    package = _package_for(s, scenario)
    if body.get("release_id"):
        from ..db import ReleaseRow

        rel = get_or_404(s, ReleaseRow, body["release_id"], "release")
        if rel.status != "RELEASED":
            raise InvalidInput(f"release {rel.release_id} was rejected; it cannot be run")
        release = ReleaseRef(release_id=rel.release_id, digest={"value": rel.digest})
    manifest = make_manifest(run_id=run_id, project_id=project_id, scenario=scenario, package=package,
                             registry=registry(), participants=participants, evaluators=evaluators, config=config,
                             source_run_id=source_run.id if source_run else None, matrix_id=matrix_id, seed=seed,
                             budget=budget, release=release)
    run = Run(id=run_id, project_id=project_id, scenario_id=scenario_id, strategy_config_id=strategy_id,
              matrix_id=matrix_id, source_run_id=source_run.id if source_run else None,
              client_request_id=client_request_id, status=RunStatus.CREATED.value,
              manifest=manifest.model_dump(mode="json"), usage={}, workflow_id=f"run-{run_id}",
              contract_version=CONTRACT_VERSION)
    s.add(run)
    s.flush()
    append_events(s, run, [draft(f"{run_id}:run:created", "RUN_CREATED", None,
                                 {"manifest": manifest.model_dump(mode="json"),
                                  "source_run_id": run.source_run_id, "matrix_id": matrix_id})])
    return run, True


def mark_queued(s: Session, run_id: str) -> Run:
    run = lock_run(s, run_id)
    if run.status == RunStatus.CREATED.value:
        transition(run, RunStatus.QUEUED)
        append_events(s, run, [draft(f"{run_id}:run:queued", "RUN_QUEUED", None, {"workflow_id": run.workflow_id},
                                     [f"{run_id}:run:created"])])
    return run


def request_pause(s: Session, run_id: str) -> Run:
    run = lock_run(s, run_id)
    if run.status in (RunStatus.PAUSING.value, RunStatus.PAUSED.value):
        return run
    if run.status not in (RunStatus.RUNNING.value, RunStatus.QUEUED.value):
        raise Conflict(f"cannot pause a run in status {run.status}")
    if run.status == RunStatus.QUEUED.value:
        raise Conflict("run has not started yet; pause takes effect at logical-step boundaries of a running run")
    n = int(run.usage.get("pause_requests", 0)) + 1
    run.usage = {**run.usage, "pause_requests": n}
    transition(run, RunStatus.PAUSING, "pause requested; takes effect at the next logical-step boundary")
    append_events(s, run, [draft(f"{run_id}:run:pausing:{n}", "RUN_PAUSING", run.last_step,
                                 {"requested_at": utcnow().isoformat(), "boundary": "next logical step"})])
    return run


def request_resume(s: Session, run_id: str) -> Run:
    run = lock_run(s, run_id)
    if run.status == RunStatus.PAUSING.value:  # never reached the boundary: just continue
        n = int(run.usage.get("pause_requests", 0))
        transition(run, RunStatus.RUNNING, "resumed before the pause took effect")
        append_events(s, run, [draft(f"{run_id}:run:resumed-early:{n}", "RUN_RESUMED", run.last_step,
                                     {"paused_seconds": 0})])
    elif run.status != RunStatus.PAUSED.value:
        raise Conflict(f"cannot resume a run in status {run.status}")
    return run


def request_cancel(s: Session, run_id: str) -> tuple[Run, bool]:
    """Returns (run, needs_orchestrator_cancel)."""
    run = lock_run(s, run_id)
    status = RunStatus(run.status)
    if status in TERMINAL_RUN_STATUSES or status == RunStatus.CANCELLING:
        return run, False
    if status == RunStatus.CREATED:
        transition(run, RunStatus.CANCELLED, "cancelled before start")
        run.finished_at = utcnow()
        append_events(s, run, [draft(f"{run_id}:run:cancelled", "RUN_CANCELLED", None,
                                     {"status": "CANCELLED", "reason": "cancelled before start"})])
        return run, False
    transition(run, RunStatus.CANCELLING, "cancellation requested")
    append_events(s, run, [draft(f"{run_id}:run:cancelling", "RUN_CANCELLING", run.last_step,
                                 {"requested_at": utcnow().isoformat()})])
    return run, True


# ------------------------------------------------------------------------ queries


def run_dict(run: Run, s: Session, *, full: bool = False) -> dict[str, Any]:
    m = run.manifest
    participants = m.get("participants", [])
    strategy = participants[0]["strategy"]["plugin"] if participants else None
    carry = run.carry or {}
    out: dict[str, Any] = {
        "id": run.id, "project_id": run.project_id, "scenario_id": run.scenario_id, "status": run.status,
        "status_reason": run.status_reason, "source_run_id": run.source_run_id, "matrix_id": run.matrix_id,
        "strategy": strategy, "strategy_config_id": run.strategy_config_id, "seed": m.get("seed"),
        "scenario_name": m.get("scenario", {}).get("name"), "model": m.get("model"), "budget": m.get("budget"),
        "usage": run.usage, "event_seq": run.event_seq, "last_step": run.last_step, "imported": run.imported,
        "created_at": run.created_at, "started_at": run.started_at, "finished_at": run.finished_at,
        "error": run.error,
        "participants": [{"actor_id": p["actor_id"], "role": p.get("role"), "strategy": p["strategy"]["plugin"],
                          "goal": p.get("goal")} for p in participants],
        "termination_reason": run.termination_reason, "turn": carry.get("turn"),
        "actor_usage": (run.usage or {}).get("actors", {}), "stored_contract_version": run.contract_version,
    }
    metrics = s.scalars(select(MetricRow).where(MetricRow.run_id == run.id)).all()
    out["metrics"] = {mr.metric_id: {"value": mr.value, "status": mr.status, "unit": mr.result.get("unit")}
                      for mr in metrics}
    if full:
        out["manifest"] = compat.upgrade_run_manifest(m).model_dump(mode="json")
        out["carry"] = carry
        out["final_state"] = run.final_state
        out["lineage"] = {"source_run_id": run.source_run_id,
                          "reruns": [r.id for r in s.scalars(select(Run).where(Run.source_run_id == run.id))]}
    return out


def list_runs(s: Session, project_id: str, *, status: str | None = None, scenario_id: str | None = None,
              matrix_id: str | None = None, limit: int = 200) -> list[Run]:
    q = select(Run).where(Run.project_id == project_id)
    if status:
        q = q.where(Run.status == status)
    if scenario_id:
        q = q.where(Run.scenario_id == scenario_id)
    if matrix_id:
        q = q.where(Run.matrix_id == matrix_id)
    return list(s.scalars(q.order_by(Run.created_at.desc()).limit(limit)))


STEP_EVENT_TYPES = ("OBSERVATION", "CANDIDATES", "ACTION_PROPOSED", "CHECK_COMPLETED", "ACTION_OUTCOME",
                    "EFFECT_COMPARED")


def step_detail(s: Session, run_id: str, step: int) -> dict[str, Any]:
    get_or_404(s, Run, run_id, "run")
    rows = list_events(s, run_id, step=step, limit=100)
    out: dict[str, Any] = {"run_id": run_id, "step": step, "events": []}
    for row in rows:
        out["events"].append({"seq": row.seq, "event_id": row.event_id, "event_type": row.event_type})
        p = row.payload
        match row.event_type:
            case "OBSERVATION":
                out["observation"] = p.get("observation")
                out["belief"] = p.get("belief")
            case "CANDIDATES":
                out["candidates"] = p.get("candidates")
            case "ACTION_PROPOSED":
                out["proposal"] = p.get("proposal")
                out["model_call_artifacts"] = p.get("model_call_artifacts", [])
            case "CHECK_COMPLETED":
                out.setdefault("checks", []).append(p)
            case "ACTION_OUTCOME":
                out["outcome"] = p.get("outcome")
            case "EFFECT_COMPARED":
                out["comparison"] = p.get("comparison")
                out["observation_after"] = p.get("observation_after")
    return out


def run_events_count(s: Session, run_id: str) -> int:
    from sqlalchemy import func

    return s.scalar(select(func.count()).select_from(RunEvent).where(RunEvent.run_id == run_id)) or 0
