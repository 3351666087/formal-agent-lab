"""Operation coordination (P2-051 … P2-058), shared by the local runner and the durable (Temporal) path.

Every environment operation goes through the state machine

    PREPARED → DISPATCHED → COMPLETED | FAILED | OUTCOME_UNKNOWN → (RECONCILED | DISPATCHED again)

The intent is recorded (PREPARED, DISPATCHED) *before* the environment is called and the result after it, in an
`OperationLedger`. What a retry after a crash does depends on the environment's declared capabilities:

- env.pure_replayable (pure-data simulator): the step engine restores the pre-step snapshot, so the environment
  never saw the operation — re-executing is exact (and the recorded outcome, if any, must match).
- env.query_operation (+ env.idempotent_step): the live service is asked what happened to the operation id.
  Found → RECONCILED with the service's outcome (never applied twice). Not found → dispatched again with the same
  id (the service deduplicates by id, so even a lost "not found" race cannot double-apply).
- neither: an operation left DISPATCHED / OUTCOME_UNKNOWN cannot be settled automatically; it is marked
  NEEDS_REVIEW and the run ends with OPERATION_UNRESOLVED (explainable termination, P2-058).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from formal_lab_contracts import (
    OPERATION_TRANSITIONS,
    ActionOutcome,
    ActionProposal,
    OperationRecord,
    OperationState,
    OperationTransition,
    OutcomeStatus,
    ReconciliationResult,
    utcnow,
)
from formal_lab_contracts import capabilities as caps
from formal_lab_contracts.errors import FormalLabError, NonRetryableFailure, ResultUnknown, Timeout


class OperationLedger(Protocol):
    """Durable record of operations. `get` / `put` must be atomic per record; the platform backs it with the
    database (each transition committed before the next action), the local runner with memory."""

    def get(self, operation_id: str) -> OperationRecord | None: ...

    def put(self, record: OperationRecord) -> None: ...


@dataclass
class InMemoryLedger:
    records: dict[str, OperationRecord] = field(default_factory=dict)

    def get(self, operation_id: str) -> OperationRecord | None:
        return self.records.get(operation_id)

    def put(self, record: OperationRecord) -> None:
        self.records[record.operation_id] = record

    def all(self) -> list[OperationRecord]:
        return list(self.records.values())


def transition(record: OperationRecord, state: OperationState, reason: str, **update: Any) -> OperationRecord:
    if state != record.state and state not in OPERATION_TRANSITIONS[record.state]:
        raise NonRetryableFailure(f"operation {record.operation_id}: illegal transition {record.state} → {state}")
    attempt = record.attempts + (1 if state is OperationState.DISPATCHED else 0)
    return record.model_copy(update={
        "state": state,
        "attempts": attempt,
        "transitions": [*record.transitions,
                        OperationTransition(state=state, at=utcnow(), reason=reason, attempt=max(1, attempt))],
        **update,
    })


@dataclass
class CoordinationResult:
    outcome: ActionOutcome | None
    record: OperationRecord
    transitions: list[tuple[OperationState, str]]  # new transitions made in this attempt (for events)
    unresolved: bool = False  # the outcome could not be settled: review needed, run must end


class Coordinator:
    """Executes one operation against an environment with the capability-dependent recovery rules above."""

    MAX_DISPATCHES = 3

    def __init__(self, env: Any, capabilities: set[str], ledger: OperationLedger,
                 on_transition: Callable[[OperationRecord], None] | None = None):
        self.env = env
        self.caps = capabilities
        self.ledger = ledger
        self.on_transition = on_transition

    @property
    def pure(self) -> bool:
        return caps.ENV_PURE_REPLAYABLE in self.caps or caps.ENV_SNAPSHOT_RESTORE in self.caps

    @property
    def queryable(self) -> bool:
        return caps.ENV_QUERY_OPERATION in self.caps and hasattr(self.env, "query_operation")

    def _save(self, record: OperationRecord, log: list, state: OperationState, reason: str, **update) -> OperationRecord:
        record = transition(record, state, reason, **update)
        self.ledger.put(record)
        log.append((state, reason))
        if self.on_transition is not None:
            self.on_transition(record)
        return record

    def execute(self, proposal: ActionProposal, operation_id: str, *, run_id: str, step: int) -> CoordinationResult:
        log: list[tuple[OperationState, str]] = []
        record = self.ledger.get(operation_id)
        if record is None:
            record = OperationRecord(operation_id=operation_id, run_id=run_id, step=step, actor_id=proposal.actor_id,
                                     state=OperationState.PREPARED, proposal_id=proposal.proposal_id,
                                     action=proposal.action, based_on_revision=proposal.based_on_revision,
                                     transitions=[OperationTransition(state=OperationState.PREPARED, at=utcnow(),
                                                                      reason="intent recorded before dispatch")])
            self.ledger.put(record)
            log.append((OperationState.PREPARED, "intent recorded before dispatch"))
        elif record.state in (OperationState.COMPLETED, OperationState.RECONCILED, OperationState.FAILED):
            if not self.pure:  # a live service already answered: never send it again
                return CoordinationResult(record.outcome, record, log)
            # pure-data: the restored snapshot has not seen it — re-execute and require the same result
            outcome = self.env.step(proposal, operation_id=operation_id)
            if record.outcome is not None and _essence(outcome) != _essence(record.outcome):
                raise NonRetryableFailure(f"pure-data replay of {operation_id} differs from the recorded outcome")
            return CoordinationResult(outcome, record, log)
        elif record.state in (OperationState.DISPATCHED, OperationState.OUTCOME_UNKNOWN) and not self.pure:
            settled = self._reconcile(record, proposal, log, "retry after an interrupted attempt")
            if settled is not None:
                return settled
            record = self.ledger.get(operation_id) or record
        return self._dispatch(record, proposal, log)

    def _dispatch(self, record: OperationRecord, proposal: ActionProposal, log: list) -> CoordinationResult:
        while True:
            if record.attempts >= self.MAX_DISPATCHES and not self.pure:
                return self._unresolved(record, log, f"outcome still unknown after {record.attempts} dispatch(es)")
            record = self._save(record, log, OperationState.DISPATCHED,
                                 "sent to the environment" if record.attempts == 0 else "re-sent with the same id")
            t0 = time.perf_counter()
            try:
                outcome = self.env.step(proposal, operation_id=record.operation_id)
            except (ResultUnknown, Timeout) as exc:
                record = self._save(record, log, OperationState.OUTCOME_UNKNOWN,
                                    f"{exc.code.value}: {exc.message} (after {time.perf_counter() - t0:.2f}s)")
                if self.pure:  # cannot happen for a pure simulator; treat as a failure of the environment
                    raise
                settled = self._reconcile(record, proposal, log, "response lost")
                if settled is not None:
                    return settled
                record = self.ledger.get(record.operation_id) or record
                continue
            except FormalLabError as exc:
                if exc.retryable:
                    raise  # transport-level retry of the whole step (the operation was not accepted)
                record = self._save(record, log, OperationState.FAILED, f"{exc.code.value}: {exc.message}")
                failed = ActionOutcome(operation_id=record.operation_id, run_id=proposal.run_id,
                                       step_id=proposal.step_id, proposal_id=proposal.proposal_id,
                                       action=proposal.action, status=OutcomeStatus.FAILED_NON_RETRYABLE,
                                       effect_applied=False, revision_before=proposal.based_on_revision,
                                       error=exc.to_info(), turn=proposal.turn,
                                       operation_state=OperationState.FAILED)
                record = record.model_copy(update={"outcome": failed})
                self.ledger.put(record)
                return CoordinationResult(failed, record, log)
            outcome = outcome.model_copy(update={"operation_state": OperationState.COMPLETED})
            record = self._save(record, log, OperationState.COMPLETED,
                                f"environment answered {outcome.status.value}", outcome=outcome)
            return CoordinationResult(outcome, record, log)

    def _reconcile(self, record: OperationRecord, proposal: ActionProposal, log: list,
                   why: str) -> CoordinationResult | None:
        if not self.queryable:
            return self._unresolved(record, log, f"{why}; the environment cannot be queried for operation "
                                                 f"{record.operation_id}")
        found = self.env.query_operation(record.operation_id)
        if found is None:
            if record.state is OperationState.DISPATCHED:  # interrupted before any answer: mark it explicitly
                record = self._save(record, log, OperationState.OUTCOME_UNKNOWN, f"{why}; state after dispatch "
                                    "not recorded")
            note = "the environment has no record of the operation: it never took effect; re-sending the same id"
            self.ledger.put(record.model_copy(update={"reconciliation": ReconciliationResult(
                method="QUERY_OPERATION", found=False, note=note)}))
            log.append((record.state, note))
            return None
        if record.state is OperationState.DISPATCHED:
            record = self._save(record, log, OperationState.OUTCOME_UNKNOWN, f"{why}; outcome not recorded")
        outcome = found.model_copy(update={"operation_state": OperationState.RECONCILED})
        record = self._save(record, log, OperationState.RECONCILED,
                            f"query_operation: the environment reports {found.status.value} "
                            f"(effect applied: {found.effect_applied})", outcome=outcome,
                            reconciliation=ReconciliationResult(method="QUERY_OPERATION", found=True, outcome=outcome,
                                                                note="settled by the environment's operation record; "
                                                                     "not sent again"))
        return CoordinationResult(outcome, record, log)

    def _unresolved(self, record: OperationRecord, log: list, why: str) -> CoordinationResult:
        from formal_lab_contracts import ReviewMark

        if record.state is OperationState.DISPATCHED:
            record = self._save(record, log, OperationState.OUTCOME_UNKNOWN, why)
        record = record.model_copy(update={"review": ReviewMark(status="NEEDS_REVIEW", by="coordinator",
                                                                at=utcnow(), note=why)})
        self.ledger.put(record)
        log.append((record.state, f"needs review: {why}"))
        return CoordinationResult(None, record, log, unresolved=True)


def _essence(outcome: ActionOutcome) -> tuple:
    return (outcome.status, outcome.effect_applied, outcome.revision_before, outcome.revision_after,
            sorted(outcome.result.get("written_paths", [])))
