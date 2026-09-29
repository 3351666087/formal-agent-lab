"""Operator view of environment operations (P2-058): query abnormal operations, mark a manual review, and end a run
with an explanation. Every review is appended to the run's event log (OPERATION_REVIEW), so all recovery and review
actions are traceable next to the automatic ones (OPERATION_STATE / OPERATION_RECONCILED / RECOVERY)."""

from __future__ import annotations

from typing import Any

from formal_lab_contracts import OperationRecord, ReviewMark, utcnow
from formal_lab_contracts.errors import Conflict, InvalidInput, NotFound
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import OperationRecordRow
from .events import append_events, draft
from .runs import lock_run

ABNORMAL = {"OUTCOME_UNKNOWN", "DISPATCHED", "FAILED", "RECONCILED"}
REVIEW_STATUSES = {"CONFIRMED_APPLIED", "CONFIRMED_NOT_APPLIED", "TERMINATED"}


def operation_dict(row: OperationRecordRow) -> dict[str, Any]:
    rec = row.record
    return {"operation_id": row.operation_id, "run_id": row.run_id, "step": row.step, "actor_id": row.actor_id,
            "state": row.state, "needs_review": row.needs_review, "attempts": rec.get("attempts"),
            "action": rec.get("action"), "review": rec.get("review"), "reconciliation": rec.get("reconciliation"),
            "transitions": rec.get("transitions", []), "outcome": rec.get("outcome"), "updated_at": row.updated_at,
            "request_digest": rec.get("request_digest"), "decisions": rec.get("decisions", []),
            "kind": rec.get("kind", "apply"), "batch_id": rec.get("batch_id"),
            "batch_outcomes": rec.get("batch_outcomes", [])}


def list_operations(s: Session, run_id: str, *, state: str | None = None, needs_review: bool | None = None,
                    abnormal: bool = False) -> list[dict[str, Any]]:
    q = select(OperationRecordRow).where(OperationRecordRow.run_id == run_id)
    if state:
        q = q.where(OperationRecordRow.state == state)
    if needs_review is not None:
        q = q.where(OperationRecordRow.needs_review == needs_review)
    rows = list(s.scalars(q.order_by(OperationRecordRow.step, OperationRecordRow.operation_id)))
    if abnormal:
        rows = [r for r in rows if r.needs_review or r.state in ABNORMAL
                or any(t.get("state") == "OUTCOME_UNKNOWN" for t in r.record.get("transitions", []))]
    return [operation_dict(r) for r in rows]


def get_operation(s: Session, operation_id: str) -> dict[str, Any]:
    row = s.get(OperationRecordRow, operation_id)
    if row is None:
        raise NotFound(f"operation {operation_id} not found")
    return operation_dict(row)


def review_operation(s: Session, operation_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """Record an operator's review of one operation. The mark never changes what the environment did; it states
    what a person confirmed (applied / not applied) or that the run is to be ended because of it."""
    status = body.get("status")
    if status not in REVIEW_STATUSES:
        raise InvalidInput(f"review status must be one of {sorted(REVIEW_STATUSES)}")
    note = str(body.get("note") or "").strip()
    if not note:
        raise InvalidInput("a review needs a note explaining what was checked")
    row = s.get(OperationRecordRow, operation_id, with_for_update=True)
    if row is None:
        raise NotFound(f"operation {operation_id} not found")
    run = lock_run(s, row.run_id)
    rec = OperationRecord.model_validate(row.record)
    if rec.review is not None and rec.review.status != "NEEDS_REVIEW" and not body.get("supersede"):
        raise Conflict(f"operation {operation_id} was already reviewed ({rec.review.status}); pass supersede=true "
                       "to replace the review")
    mark = ReviewMark(status=status, by=str(body.get("by") or "operator"), at=utcnow(), note=note)
    previous = rec.review.model_dump(mode="json") if rec.review is not None else None
    rec = rec.model_copy(update={"review": mark})
    row.record, row.needs_review = rec.model_dump(mode="json"), False
    # the review history is the run's event log: one OPERATION_REVIEW per review, with the mark it replaced
    append_events(s, run, [draft(f"{run.id}:op-review:{operation_id}:{mark.at.isoformat()}", "OPERATION_REVIEW",
                                 row.step, {"operation_id": operation_id, "review": mark.model_dump(mode="json"),
                                            "state": row.state, "previous": previous}, actor_id=row.actor_id)])
    return operation_dict(row)
