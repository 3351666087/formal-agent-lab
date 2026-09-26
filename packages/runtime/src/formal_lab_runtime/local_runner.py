"""In-process runner: executes a whole episode with the shared step engine (no database, no Temporal).

Used by the standalone example, tests, the Inspect adapter and offline tooling. The durable platform
path (Temporal workflow + activities) calls the very same engine functions step by step.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from formal_lab_contracts import (
    BudgetUsage,
    EventType,
    MetricResult,
    ModelPackage,
    RunManifest,
    RunStatus,
    StepRecord,
    TraceEvent,
    utcnow,
)

from .engine import EventDraft, event_id_for, event_key, execute_step, failure_status, finish_run, open_components, start_run
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

    def metric(self, metric_id: str) -> MetricResult | None:
        return next((m for m in self.metrics if m.metric_id == metric_id), None)


def to_trace_events(run_id: str, drafts: list[EventDraft], start_seq: int) -> list[TraceEvent]:
    out = []
    for i, d in enumerate(drafts):
        out.append(TraceEvent(event_id=d.event_id, run_id=run_id, seq=start_seq + i, event_type=d.event_type,
                              causal_parents=[event_id_for(k) for k in d.parents], logical_step=d.step,
                              wall_time=utcnow(), actor_id=d.actor_id, payload_schema=d.payload_schema,
                              payload=d.payload, idempotency_key=d.key))
    return out


def run_local(manifest: RunManifest, package: ModelPackage, registry: PluginRegistry | None = None) -> LocalRunResult:
    registry = registry or default_registry()
    rc = open_components(manifest, package, registry)
    run_id = manifest.run_id
    drafts: list[EventDraft] = [
        EventDraft(event_key(run_id, None, "created"), EventType.RUN_CREATED, None,
                   {"manifest": manifest.model_dump(mode="json")}),
        EventDraft(event_key(run_id, None, "queued"), EventType.RUN_QUEUED, None, {"runner": "local"},
                   [event_key(run_id, None, "created")]),
    ]
    usage = BudgetUsage()
    t_start = time.perf_counter()
    start = start_run(rc)
    drafts += start.events
    snapshot = start.snapshot
    steps: list[StepRecord] = []
    calls: list[dict[str, Any]] = []
    status, reason = RunStatus.FAILED, "not finished"
    step = 1
    parent = event_key(run_id, 0, "snapshot")
    while True:
        usage.wall_seconds = time.perf_counter() - t_start
        try:
            ex = execute_step(rc, snapshot, step, usage)
        except Exception as exc:  # non-retryable in-process: fail the run and keep evidence
            status, reason = failure_status(exc)
            break
        drafts += ex.events
        calls += ex.model_calls
        if ex.snapshot is not None:
            snapshot = ex.snapshot
        if ex.observation is not None:
            usage.steps += 1
            usage.model_calls += ex.usage_delta.model_calls
            usage.input_tokens += ex.usage_delta.input_tokens
            usage.output_tokens += ex.usage_delta.output_tokens
            checks = [ex.precheck] if ex.precheck else []
            steps.append(StepRecord(step=step, observation=ex.observation, proposal=ex.proposal, outcome=ex.outcome,
                                    checks=checks))
            parent = event_key(run_id, step, "comparison") if ex.outcome else event_key(run_id, step, "candidates")
        if ex.terminal is not None:
            status, reason = ex.terminal, ex.terminal_reason
            break
        step += 1
    usage.wall_seconds = time.perf_counter() - t_start
    fin = finish_run(rc, status=status, reason=reason, final_snapshot=snapshot, usage=usage, steps=steps,
                     last_step=steps[-1].step if steps else 0, parent_key=parent)
    drafts += fin.events
    events = to_trace_events(run_id, drafts, 1)
    final_manifest = manifest.model_copy(update={"status": status, "status_reason": reason, "budget_usage": usage})
    return LocalRunResult(final_manifest, status, reason, events, fin.metrics, usage, fin.final_state, steps, calls)


def new_run_id() -> str:
    return f"run_{uuid.uuid4().hex[:20]}"
