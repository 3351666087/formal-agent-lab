"""In-process runner: executes an episode with the shared step engine (no database, no Temporal).

Used by the standalone examples, tests, the Inspect adapter and offline tooling. The durable platform path
(Temporal workflow + activities) calls the very same engine functions step by step, with a database-backed
operation ledger instead of the in-memory one (P2-057).

A local run can stop after any step (`stop_after`) and hand back a JSON-serialisable `LocalRunState`; a fresh
process continues it with `resume_local` exactly as if it had never stopped — environment snapshot, turn cursor,
planner checkpoints, per-actor usage, rule flags and the operation ledger travel in the state (P2-046).
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from formal_lab_contracts import (
    BudgetUsage,
    EnvironmentSnapshot,
    EventType,
    MetricResult,
    ModelPackage,
    OperationRecord,
    ProbeResult,
    RunManifest,
    RunStatus,
    StepRecord,
    TerminationReason,
    TraceEvent,
    utcnow,
)

from .coordination import InMemoryLedger
from .engine import (
    CarryState,
    EventDraft,
    add_usage,
    event_id_for,
    event_key,
    execute_step,
    failure_status,
    finish_run,
    open_components,
    start_run,
)
from .registry import PluginRegistry, default_registry


@dataclass
class LocalRunResult:
    manifest: RunManifest
    status: RunStatus
    reason: str | None
    events: list[TraceEvent]
    metrics: list[MetricResult]
    usage: BudgetUsage
    final_state: dict[str, Any]
    steps: list[StepRecord] = field(default_factory=list)
    model_calls: list[dict[str, Any]] = field(default_factory=list)
    termination_reason: TerminationReason | None = None
    actor_usage: dict[str, Any] = field(default_factory=dict)
    operations: list[OperationRecord] = field(default_factory=list)
    probes: list[ProbeResult] = field(default_factory=list)
    carry: dict[str, Any] = field(default_factory=dict)

    def metric(self, metric_id: str) -> MetricResult | None:
        return next((m for m in self.metrics if m.metric_id == metric_id), None)


@dataclass
class LocalRunState:
    """Everything needed to continue a local run in another process (JSON via to_json / from_json)."""

    manifest: RunManifest
    next_step: int
    snapshot: EnvironmentSnapshot
    carry: CarryState
    usage: BudgetUsage
    drafts: list[EventDraft]
    steps: list[StepRecord]
    model_calls: list[dict[str, Any]]
    operations: list[OperationRecord]
    probes: list[ProbeResult]
    wall_before: float
    paused: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {"manifest": self.manifest.model_dump(mode="json"), "next_step": self.next_step,
                "snapshot": self.snapshot.model_dump(mode="json"), "carry": self.carry.to_json(),
                "usage": self.usage.model_dump(), "drafts": [d.to_json() for d in self.drafts],
                "steps": [s.model_dump(mode="json") for s in self.steps], "model_calls": self.model_calls,
                "operations": [o.model_dump(mode="json") for o in self.operations],
                "probes": [p.model_dump(mode="json") for p in self.probes], "wall_before": self.wall_before,
                "paused": self.paused}

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> LocalRunState:
        return cls(manifest=RunManifest.model_validate(data["manifest"]), next_step=data["next_step"],
                   snapshot=EnvironmentSnapshot.model_validate(data["snapshot"]),
                   carry=CarryState.from_json(data["carry"]), usage=BudgetUsage.model_validate(data["usage"]),
                   drafts=[EventDraft.from_json(d) for d in data["drafts"]],
                   steps=[StepRecord.model_validate(s) for s in data["steps"]], model_calls=data["model_calls"],
                   operations=[OperationRecord.model_validate(o) for o in data["operations"]],
                   probes=[ProbeResult.model_validate(p) for p in data["probes"]],
                   wall_before=data["wall_before"], paused=data.get("paused"))


def to_trace_events(run_id: str, drafts: list[EventDraft], start_seq: int) -> list[TraceEvent]:
    out = []
    for i, d in enumerate(drafts):
        out.append(TraceEvent(event_id=d.event_id, run_id=run_id, seq=start_seq + i, event_type=d.event_type,
                              causal_parents=[event_id_for(k) for k in d.parents], logical_step=d.step,
                              wall_time=utcnow(), actor_id=d.actor_id, payload_schema=d.payload_schema,
                              payload=d.payload, idempotency_key=d.key, turn=d.turn, stage=d.stage))
    return out


def run_local(manifest: RunManifest, package: ModelPackage, registry: PluginRegistry | None = None, *,
              stop_after: int | None = None, rulesets: dict[str, Any] | None = None,
              honour_pause: bool = False) -> LocalRunResult | LocalRunState:
    """Run a whole episode in-process. With `stop_after=k` the run stops after global step k and returns the
    resumable `LocalRunState` instead of a result. With `honour_pause`, a PAUSE rule also stops it there."""
    registry = registry or default_registry()
    rc = open_components(manifest, package, registry, rulesets=rulesets)
    run_id = manifest.run_id
    drafts: list[EventDraft] = [
        EventDraft(event_key(run_id, None, "created"), EventType.RUN_CREATED, None,
                   {"manifest": manifest.model_dump(mode="json")}),
        EventDraft(event_key(run_id, None, "queued"), EventType.RUN_QUEUED, None, {"runner": "local"},
                   [event_key(run_id, None, "created")]),
    ]
    start = start_run(rc)
    drafts += start.events
    state = LocalRunState(manifest=manifest, next_step=1, snapshot=start.snapshot, carry=start.carry,
                          usage=BudgetUsage(), drafts=drafts, steps=[], model_calls=[], operations=[], probes=[],
                          wall_before=0.0)
    return _continue(rc, state, package, stop_after=stop_after, honour_pause=honour_pause)


def resume_local(state: LocalRunState | dict[str, Any], package: ModelPackage, registry: PluginRegistry | None = None,
                 *, stop_after: int | None = None, rulesets: dict[str, Any] | None = None,
                 honour_pause: bool = False) -> LocalRunResult | LocalRunState:
    """Continue a stopped local run (possibly in a new process: the plugins are created afresh and restored from
    the carried checkpoints)."""
    if isinstance(state, dict):
        state = LocalRunState.from_json(state)
    registry = registry or default_registry()
    rc = open_components(state.manifest, package, registry, rulesets=rulesets)
    state.drafts.append(EventDraft(event_key(state.manifest.run_id, None, f"resumed-{state.next_step}"),
                                   EventType.RECOVERY, state.next_step - 1,
                                   {"kind": "local-resume", "next_step": state.next_step,
                                    "note": "fresh process: plugins recreated, state restored from the carried "
                                            "snapshot, turn cursor and planner checkpoints"},
                                   [state.carry.last_event_key] if state.carry.last_event_key else []))
    state.paused = None
    return _continue(rc, state, package, stop_after=stop_after, honour_pause=honour_pause)


def _continue(rc, state: LocalRunState, package: ModelPackage, *, stop_after: int | None,
              honour_pause: bool) -> LocalRunResult | LocalRunState:
    run_id = state.manifest.run_id
    ledger = InMemoryLedger({o.operation_id: o for o in state.operations})
    status, reason, term = RunStatus.FAILED, "not finished", None
    t_start = time.perf_counter()
    step = state.next_step
    while True:
        usage = state.usage.model_copy(update={"wall_seconds": state.wall_before + time.perf_counter() - t_start})
        try:
            ex = execute_step(rc, state.snapshot, step, usage, state.carry, ledger)
        except Exception as exc:  # non-retryable in-process: fail the run and keep evidence
            status, reason = failure_status(exc)
            term = TerminationReason.FAILED
            break
        state.drafts += ex.events
        state.model_calls += ex.model_calls
        state.probes += ex.probes
        if ex.carry is not None:
            state.carry = ex.carry
        if ex.snapshot is not None:
            state.snapshot = ex.snapshot
        if ex.observation is not None:
            state.usage = add_usage(state.usage, ex.usage_delta, steps=1)
            checks = [ex.precheck] if ex.precheck else []
            state.steps.append(StepRecord(step=step, observation=ex.observation, proposal=ex.proposal,
                                          outcome=ex.outcome, checks=checks, actor_id=ex.turn.actor_id if ex.turn
                                          else None, turn=ex.turn, stages=ex.stages, operation=ex.operation,
                                          probes=ex.probes))
        if ex.terminal is not None:
            status, reason, term = ex.terminal, ex.terminal_reason, ex.termination_reason
            break
        step += 1
        state.next_step = step
        state.operations = ledger.all()
        if ex.pause_requested and honour_pause:
            state.paused = ex.pause_requested
            state.wall_before += time.perf_counter() - t_start
            return state
        if stop_after is not None and step > stop_after:
            state.wall_before += time.perf_counter() - t_start
            return state
    state.usage = state.usage.model_copy(update={"wall_seconds": state.wall_before + time.perf_counter() - t_start})
    parent = state.carry.last_event_key or event_key(run_id, 0, "snapshot")
    fin = finish_run(rc, status=status, reason=reason, final_snapshot=state.snapshot, usage=state.usage,
                     steps=state.steps, last_step=state.steps[-1].step if state.steps else 0, parent_key=parent,
                     termination_reason=term, actor_usage=state.carry.actor_usage, probes=state.probes)
    state.drafts += fin.events
    events = to_trace_events(run_id, state.drafts, 1)
    final_manifest = state.manifest.model_copy(update={
        "status": status, "status_reason": reason, "budget_usage": state.usage, "termination_reason": term,
        "actor_usage": {k: BudgetUsage.model_validate(v) for k, v in state.carry.actor_usage.items()}})
    return LocalRunResult(final_manifest, status, reason, events, fin.metrics, state.usage, fin.final_state,
                          state.steps, state.model_calls, term, state.carry.actor_usage, ledger.all(), state.probes,
                          state.carry.to_json())


def new_run_id() -> str:
    return f"run_{uuid.uuid4().hex[:20]}"
