"""Ordered, de-duplicated run events and the run status state machine."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from formal_lab_contracts import RunStatus, TraceEvent, utcnow
from formal_lab_contracts.errors import Conflict
from formal_lab_runtime.engine import EventDraft, event_id_for
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import Run, RunEvent

ALLOWED: dict[RunStatus, set[RunStatus]] = {
    RunStatus.CREATED: {RunStatus.QUEUED, RunStatus.CANCELLED, RunStatus.FAILED},
    RunStatus.QUEUED: {RunStatus.RUNNING, RunStatus.CANCELLING, RunStatus.FAILED},
    RunStatus.RUNNING: {RunStatus.PAUSING, RunStatus.CANCELLING, RunStatus.SUCCEEDED, RunStatus.FAILED,
                        RunStatus.BUDGET_EXHAUSTED},
    RunStatus.PAUSING: {RunStatus.PAUSED, RunStatus.RUNNING, RunStatus.CANCELLING, RunStatus.SUCCEEDED,
                        RunStatus.FAILED, RunStatus.BUDGET_EXHAUSTED},
    RunStatus.PAUSED: {RunStatus.RUNNING, RunStatus.CANCELLING},
    RunStatus.CANCELLING: {RunStatus.CANCELLED, RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.BUDGET_EXHAUSTED},
    RunStatus.CANCELLED: set(),
    RunStatus.SUCCEEDED: set(),
    RunStatus.FAILED: set(),
    RunStatus.BUDGET_EXHAUSTED: set(),
}


def transition(run: Run, new: RunStatus, reason: str | None = None) -> None:
    current = RunStatus(run.status)
    if new == current:
        return
    if new not in ALLOWED[current]:
        raise Conflict(f"run {run.id}: cannot go from {current} to {new}", details={"status": current.value})
    run.status = new.value
    if reason is not None:
        run.status_reason = reason
    manifest = dict(run.manifest)
    manifest["status"] = new.value
    manifest["status_reason"] = run.status_reason
    run.manifest = manifest


def lock_run(s: Session, run_id: str) -> Run:
    run = s.get(Run, run_id, with_for_update=True, populate_existing=True)
    if run is None:
        from formal_lab_contracts.errors import NotFound

        raise NotFound(f"run {run_id} not found")
    return run


def append_events(s: Session, run: Run, drafts: Iterable[EventDraft]) -> list[RunEvent]:
    """Append events with gap-free per-run sequence numbers. The caller must hold the run row lock.
    Drafts whose idempotency key already exists are skipped (retries never duplicate events)."""
    drafts = list(drafts)
    if not drafts:
        return []
    keys = [d.key for d in drafts]
    existing = set(s.scalars(select(RunEvent.idempotency_key).where(RunEvent.run_id == run.id,
                                                                     RunEvent.idempotency_key.in_(keys))))
    added = []
    now = utcnow()
    for d in drafts:
        if d.key in existing:
            continue
        existing.add(d.key)
        run.event_seq += 1
        row = RunEvent(run_id=run.id, seq=run.event_seq, event_id=d.event_id, event_type=d.event_type.value,
                       logical_step=d.step, wall_time=now, actor_id=d.actor_id,
                       causal_parents=[event_id_for(k) for k in d.parents], payload_schema=d.payload_schema,
                       payload=d.payload, idempotency_key=d.key,
                       turn=d.turn.model_dump(mode="json") if d.turn else None,
                       stage=d.stage.value if d.stage else None)
        s.add(row)
        added.append(row)
    s.flush()
    return added


def to_trace_event(row: RunEvent, *, upgrade: bool = False) -> TraceEvent:
    """TraceEvent of a stored row; `upgrade` rewrites embedded v1 objects of phase-1 rows to v2 (exports)."""
    from formal_lab_contracts import compat

    payload = compat.upgrade_event_payload(row.event_type, row.payload) if upgrade else row.payload
    return TraceEvent(event_id=row.event_id, run_id=row.run_id, seq=row.seq, event_type=row.event_type,
                      causal_parents=row.causal_parents, logical_step=row.logical_step, wall_time=row.wall_time,
                      actor_id=row.actor_id, payload_schema=row.payload_schema, payload=payload,
                      idempotency_key=row.idempotency_key, turn=row.turn, stage=row.stage)


def list_events(s: Session, run_id: str, *, after_seq: int = 0, limit: int = 500,
                event_types: list[str] | None = None, step: int | None = None) -> list[RunEvent]:
    q = select(RunEvent).where(RunEvent.run_id == run_id, RunEvent.seq > after_seq)
    if event_types:
        q = q.where(RunEvent.event_type.in_(event_types))
    if step is not None:
        q = q.where(RunEvent.logical_step == step)
    return list(s.scalars(q.order_by(RunEvent.seq).limit(limit)))


def draft(key: str, event_type: str, step: int | None, payload: dict[str, Any], parents: list[str] | None = None,
          actor_id: str | None = None) -> EventDraft:
    from formal_lab_contracts import EventType

    return EventDraft(key, EventType(event_type), step, payload, parents or [], actor_id)
