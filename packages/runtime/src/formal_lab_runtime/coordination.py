"""Operation coordination (P2-051 … P2-058, phase 3A G2), shared by the local runner and the durable (Temporal) path.

Every environment operation goes through the state machine

    PREPARED → DISPATCHED → COMPLETED | FAILED | OUTCOME_UNKNOWN → (RECONCILED | DISPATCHED again | FAILED)

The intent is recorded (PREPARED, DISPATCHED) *before* the environment is called and the result after it, in an
`OperationLedger`. Rules:

- **Identity.** An operation id is bound to its canonical request (actor, kind, action: `request_digest`). The same id
  with the same request reuses the recorded result — nothing is sent again (effect REUSE). The same id with another
  request is a conflict: nothing is sent and the step cannot proceed (review).
- **Pre-execution decision.** Right before every send — first send, re-send, pure-data re-execution — the scenario's
  execution gates decide (`ExecutionDecision`, kept on the record). DENY → nothing is sent; the operation is FAILED
  (definitely not applied) and the action REJECTED with the gate's reason. Reusing or querying a result is not a send
  and consults no gate.
- **Unknown outcomes.** A lost answer is settled by asking the environment (env.query_operation, effect QUERY). Found →
  RECONCILED with the environment's outcome, never sent again. Not found → re-sent with the same id **only if the
  environment declares env.idempotent_step** (it deduplicates by id); otherwise, and when the lookup itself fails, the
  operation is marked NEEDS_REVIEW and the run ends with OPERATION_UNRESOLVED (explainable, never a guess).
- env.pure_replayable (pure-data simulator): the step engine restores the pre-step snapshot, so re-executing is exact;
  the recorded outcome and gate verdict must match.

Every transition carries its `effect`: SEND (may take effect), QUERY (asked about history), REUSE (recorded result
used), NONE (bookkeeping) — so the record says which attempts could have produced a side effect.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from formal_lab_contracts import (
    OPERATION_TRANSITIONS,
    ActionOutcome,
    ActionProposal,
    ExecutionDecision,
    ExecutionPhase,
    OperationEffect,
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


def request_digest(proposal: ActionProposal, kind: str = "apply") -> str:
    """sha256 of the canonical request an operation id stands for."""
    body = {"kind": kind, "actor_id": proposal.actor_id, "action": proposal.action.model_dump(mode="json")}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def batch_request_digest(proposals: list[ActionProposal]) -> str:
    """sha256 of a JOINT_BATCH submission: the member requests in submission order."""
    body = [{"actor_id": p.actor_id, "action": p.action.model_dump(mode="json")} for p in proposals]
    return hashlib.sha256(json.dumps({"kind": "batch", "members": body}, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def transition(record: OperationRecord, state: OperationState, reason: str, *,
               effect: OperationEffect = OperationEffect.NONE, **update: Any) -> OperationRecord:
    if state != record.state and state not in OPERATION_TRANSITIONS[record.state]:
        raise NonRetryableFailure(f"operation {record.operation_id}: illegal transition {record.state} → {state}")
    attempt = record.attempts + (1 if state == OperationState.DISPATCHED else 0)
    return record.model_copy(update={
        "state": state,
        "attempts": attempt,
        "transitions": [*record.transitions,
                        OperationTransition(state=state, at=utcnow(), reason=reason, attempt=max(1, attempt),
                                            effect=effect)],
        **update,
    })


@dataclass
class SendDecision:
    """What the pre-execution hook answers for one send."""

    allowed: bool
    reason: str
    decisions: list[ExecutionDecision] = field(default_factory=list)


GateHook = Callable[[ExecutionPhase, OperationRecord, ActionProposal], SendDecision]


@dataclass
class CoordinationResult:
    outcome: ActionOutcome | None
    record: OperationRecord
    transitions: list[tuple[OperationState, str]]  # new transitions made in this attempt (for events)
    unresolved: bool = False  # the outcome could not be settled: review needed, run must end
    decisions: list[ExecutionDecision] = field(default_factory=list)  # decisions made in this attempt
    denied: bool = False  # a gate denied the send: nothing was sent
    reused: bool = False  # the recorded result was used: nothing was sent
    conflict: str | None = None  # the id was reused with another request: nothing was sent
    outcomes: list[ActionOutcome] = field(default_factory=list)  # JOINT_BATCH: one per submitted proposal


class Coordinator:
    """Executes one operation against an environment with the rules above."""

    MAX_DISPATCHES = 3

    def __init__(self, env: Any, capabilities: set[str], ledger: OperationLedger,
                 on_transition: Callable[[OperationRecord], None] | None = None, gate: GateHook | None = None):
        self.env = env
        self.caps = capabilities
        self.ledger = ledger
        self.on_transition = on_transition
        self.gate = gate

    @property
    def pure(self) -> bool:
        return caps.ENV_PURE_REPLAYABLE in self.caps or caps.ENV_SNAPSHOT_RESTORE in self.caps

    @property
    def queryable(self) -> bool:
        return caps.ENV_QUERY_OPERATION in self.caps and hasattr(self.env, "query_operation")

    @property
    def resend_safe(self) -> bool:
        """Re-sending an id the environment has no record of is safe only if it deduplicates by id."""
        return caps.ENV_IDEMPOTENT_STEP in self.caps

    def _save(self, record: OperationRecord, log: list, state: OperationState, reason: str, *,
              effect: OperationEffect = OperationEffect.NONE, **update) -> OperationRecord:
        record = transition(record, state, reason, effect=effect, **update)
        self.ledger.put(record)
        log.append((state, reason))
        if self.on_transition is not None:
            self.on_transition(record)
        return record

    def execute(self, proposal: ActionProposal, operation_id: str, *, run_id: str, step: int) -> CoordinationResult:
        log: list[tuple[OperationState, str]] = []
        digest = request_digest(proposal)
        record = self.ledger.get(operation_id)
        if record is None:
            record = OperationRecord(operation_id=operation_id, run_id=run_id, step=step, actor_id=proposal.actor_id,
                                     state=OperationState.PREPARED, proposal_id=proposal.proposal_id,
                                     action=proposal.action, based_on_revision=proposal.based_on_revision,
                                     request_digest=digest,
                                     transitions=[OperationTransition(state=OperationState.PREPARED, at=utcnow(),
                                                                      reason="intent recorded before dispatch",
                                                                      effect=OperationEffect.NONE)])
            self.ledger.put(record)
            log.append((OperationState.PREPARED, "intent recorded before dispatch"))
            return self._dispatch(record, proposal, log, ExecutionPhase.FIRST_SEND)
        if record.request_digest is not None and record.request_digest != digest:
            was = record.action.action_type if record.action else "?"
            why = (f"operation id {operation_id} was recorded for another request ({was} by {record.actor_id}, "
                   f"digest {record.request_digest[:12]}) and is now asked for {proposal.action.action_type} by "
                   f"{proposal.actor_id} (digest {digest[:12]}): nothing is sent")
            log.append((record.state, f"conflict: {why}"))
            return CoordinationResult(None, record, log, unresolved=True, conflict=why)
        if record.state in (OperationState.COMPLETED, OperationState.RECONCILED, OperationState.FAILED):
            if not self.pure:  # a live service already answered (or the send was denied): never send it again
                record = self._save(record, log, record.state, "recorded result reused; nothing sent",
                                    effect=OperationEffect.REUSE)
                return CoordinationResult(record.outcome, record, log, reused=True)
            return self._reexecute(record, proposal, log)
        if record.state in (OperationState.DISPATCHED, OperationState.OUTCOME_UNKNOWN) and not self.pure:
            settled = self._reconcile(record, proposal, log, "retry after an interrupted attempt")
            if settled is not None:
                return settled
            record = self.ledger.get(operation_id) or record
            return self._dispatch(record, proposal, log, ExecutionPhase.RESEND)
        phase = (ExecutionPhase.FIRST_SEND if record.attempts == 0 else
                 ExecutionPhase.REEXECUTE if self.pure else ExecutionPhase.RESEND)
        return self._dispatch(record, proposal, log, phase)

    def execute_batch(self, proposals: list[ActionProposal], operation_id: str, *, run_id: str, step: int,
                      batch_id: str) -> CoordinationResult:
        """One JOINT_BATCH submission (phase 3A, G4): `env.step_batch` applies every proposal in one environment step.
        Same identity rules as `execute`; a lost answer is re-sent with the same id only when the environment
        deduplicates by id (env.idempotent_step), a pure-data environment re-executes and must answer the same."""
        log: list[tuple[OperationState, str]] = []
        digest = batch_request_digest(proposals)
        record = self.ledger.get(operation_id)
        if record is None:
            record = OperationRecord(operation_id=operation_id, run_id=run_id, step=step, kind="batch",
                                     state=OperationState.PREPARED, batch_id=batch_id, request_digest=digest,
                                     based_on_revision=min((p.based_on_revision for p in proposals), default=None),
                                     transitions=[OperationTransition(state=OperationState.PREPARED, at=utcnow(),
                                                                      reason=f"batch intent recorded: "
                                                                             f"{len(proposals)} proposal(s)",
                                                                      effect=OperationEffect.NONE)])
            self.ledger.put(record)
            log.append((OperationState.PREPARED, "batch intent recorded before dispatch"))
        elif record.request_digest != digest:
            why = (f"operation id {operation_id} was recorded for another batch (digest {record.request_digest}) "
                   f"and is now asked for digest {digest[:12]}: nothing is sent")
            log.append((record.state, f"conflict: {why}"))
            return CoordinationResult(None, record, log, unresolved=True, conflict=why)
        elif record.state is OperationState.FAILED:  # the environment refused the batch: never sent again
            return CoordinationResult(None, record, log, reused=True, outcomes=list(record.batch_outcomes))
        elif record.state in (OperationState.COMPLETED, OperationState.RECONCILED):
            if not self.pure:
                record = self._save(record, log, record.state, "recorded batch result reused; nothing sent",
                                    effect=OperationEffect.REUSE)
                return CoordinationResult(None, record, log, reused=True, outcomes=list(record.batch_outcomes))
            outcomes = self.env.step_batch(proposals, operation_id=operation_id)
            if [_essence(o) for o in outcomes] != [_essence(o) for o in record.batch_outcomes]:
                raise NonRetryableFailure(f"pure-data replay of batch {operation_id} differs from the recorded "
                                          "outcomes")
            return CoordinationResult(None, record, log, outcomes=outcomes)
        elif record.state in (OperationState.DISPATCHED, OperationState.OUTCOME_UNKNOWN) and not self.pure \
                and not self.resend_safe:
            return self._unresolved(record, log, "batch interrupted after dispatch; the environment does not declare "
                                                 "env.idempotent_step: re-sending could apply it twice")
        while True:
            if record.attempts >= self.MAX_DISPATCHES and not self.pure:
                return self._unresolved(record, log, f"batch outcome still unknown after {record.attempts} "
                                                     "dispatch(es)")
            record = self._save(record, log, OperationState.DISPATCHED,
                                "batch sent to the environment" if record.attempts == 0 else
                                "batch re-sent with the same id", effect=OperationEffect.SEND)
            try:
                outcomes = self.env.step_batch(proposals, operation_id=operation_id)
            except (ResultUnknown, Timeout) as exc:
                record = self._save(record, log, OperationState.OUTCOME_UNKNOWN, f"{exc.code.value}: {exc.message}")
                if self.pure:
                    raise
                if not self.resend_safe:
                    return self._unresolved(record, log, "batch answer lost; the environment does not declare "
                                                         "env.idempotent_step: re-sending could apply it twice")
                continue
            except FormalLabError as exc:
                if exc.retryable:
                    raise
                record = self._save(record, log, OperationState.FAILED, f"{exc.code.value}: {exc.message}")
                failed = [ActionOutcome(operation_id=f"{operation_id}:{p.actor_id}", run_id=p.run_id,
                                        step_id=p.step_id, proposal_id=p.proposal_id, action=p.action,
                                        status=OutcomeStatus.FAILED_NON_RETRYABLE, effect_applied=False,
                                        revision_before=p.based_on_revision, error=exc.to_info(), turn=p.turn,
                                        operation_state=OperationState.FAILED) for p in proposals]
                record = record.model_copy(update={"batch_outcomes": failed})
                self.ledger.put(record)
                return CoordinationResult(None, record, log, outcomes=failed)
            if len(outcomes) != len(proposals):
                raise NonRetryableFailure(f"step_batch answered {len(outcomes)} outcome(s) for {len(proposals)} "
                                          "proposal(s)")
            outcomes = [o.model_copy(update={"operation_state": OperationState.COMPLETED}) for o in outcomes]
            applied = sum(o.status is OutcomeStatus.APPLIED for o in outcomes)
            record = self._save(record, log, OperationState.COMPLETED,
                                f"environment applied the batch: {applied}/{len(outcomes)} APPLIED",
                                batch_outcomes=outcomes)
            return CoordinationResult(None, record, log, outcomes=outcomes)

    # ------------------------------------------------------------------ sends
    def _decide(self, phase: ExecutionPhase, record: OperationRecord, proposal: ActionProposal,
                log: list, made: list[ExecutionDecision]) -> tuple[OperationRecord, SendDecision | None]:
        if self.gate is None:
            return record, None
        verdict = self.gate(phase, record, proposal)
        made.extend(verdict.decisions)
        if verdict.decisions:
            record = record.model_copy(update={"decisions": [*record.decisions, *verdict.decisions]})
            self.ledger.put(record)
        return record, verdict

    def _denied(self, record: OperationRecord, proposal: ActionProposal, log: list, verdict: SendDecision,
                made: list[ExecutionDecision]) -> CoordinationResult:
        record = self._save(record, log, OperationState.FAILED, f"denied before sending: {verdict.reason}")
        outcome = ActionOutcome(
            operation_id=record.operation_id, run_id=proposal.run_id, step_id=proposal.step_id,
            proposal_id=proposal.proposal_id, action=proposal.action, status=OutcomeStatus.REJECTED,
            effect_applied=False, revision_before=proposal.based_on_revision,
            revision_after=proposal.based_on_revision, turn=proposal.turn, operation_state=OperationState.FAILED,
            result={"reason": f"EXECUTION_GATE: {verdict.reason}", "not_sent": True,
                    "decisions": [d.decision_id for d in made]})
        record = record.model_copy(update={"outcome": outcome})
        self.ledger.put(record)
        return CoordinationResult(outcome, record, log, decisions=made, denied=True)

    def _dispatch(self, record: OperationRecord, proposal: ActionProposal, log: list,
                  phase: ExecutionPhase) -> CoordinationResult:
        made: list[ExecutionDecision] = []
        while True:
            if record.attempts >= self.MAX_DISPATCHES and not self.pure:
                return self._unresolved(record, log, f"outcome still unknown after {record.attempts} dispatch(es)",
                                        made)
            record, verdict = self._decide(phase, record, proposal, log, made)
            if verdict is not None and not verdict.allowed:
                return self._denied(record, proposal, log, verdict, made)
            record = self._save(record, log, OperationState.DISPATCHED,
                                "sent to the environment" if record.attempts == 0 else "re-sent with the same id",
                                effect=OperationEffect.SEND)
            t0 = time.perf_counter()
            try:
                outcome = self.env.step(proposal, operation_id=record.operation_id)
            except (ResultUnknown, Timeout) as exc:
                record = self._save(record, log, OperationState.OUTCOME_UNKNOWN,
                                    f"{exc.code.value}: {exc.message} (after {time.perf_counter() - t0:.2f}s)")
                if self.pure:  # cannot happen for a pure simulator; treat as a failure of the environment
                    raise
                settled = self._reconcile(record, proposal, log, "response lost", made)
                if settled is not None:
                    return settled
                record = self.ledger.get(record.operation_id) or record
                phase = ExecutionPhase.RESEND
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
                return CoordinationResult(failed, record, log, decisions=made)
            outcome = outcome.model_copy(update={"operation_state": OperationState.COMPLETED})
            record = self._save(record, log, OperationState.COMPLETED,
                                f"environment answered {outcome.status.value}", outcome=outcome)
            return CoordinationResult(outcome, record, log, decisions=made)

    def _reexecute(self, record: OperationRecord, proposal: ActionProposal, log: list) -> CoordinationResult:
        """Pure-data environment: the restored snapshot has not seen the operation — re-apply it and require the
        same gate verdict and the same result as recorded."""
        made: list[ExecutionDecision] = []
        if self.gate is not None:
            verdict = self.gate(ExecutionPhase.REEXECUTE, record, proposal)
            made = verdict.decisions
            recorded = [d for d in record.decisions if d.phase != ExecutionPhase.REEXECUTE]
            was_denied = bool(recorded) and recorded[-1].verdict.value == "DENY"
            if verdict.allowed == was_denied:
                raise NonRetryableFailure(f"pure-data re-execution of {record.operation_id}: the gate now answers "
                                          f"{'ALLOW' if verdict.allowed else 'DENY'}, it answered the opposite")
            if not verdict.allowed:
                return CoordinationResult(record.outcome, record, log, decisions=made, denied=True)
        outcome = self.env.step(proposal, operation_id=record.operation_id)
        if record.outcome is not None and _essence(outcome) != _essence(record.outcome):
            raise NonRetryableFailure(f"pure-data replay of {record.operation_id} differs from the recorded outcome")
        return CoordinationResult(outcome, record, log, decisions=made)

    # ------------------------------------------------------------------ unknown outcomes
    def _reconcile(self, record: OperationRecord, proposal: ActionProposal, log: list, why: str,
                   made: list[ExecutionDecision] | None = None) -> CoordinationResult | None:
        """None = the environment has no record of the operation and it may be re-sent (idempotent environment)."""
        made = made if made is not None else []
        if not self.queryable:
            return self._unresolved(record, log, f"{why}; the environment cannot be queried for operation "
                                                 f"{record.operation_id}", made)
        try:
            found = self.env.query_operation(record.operation_id)
        except (ResultUnknown, Timeout) as exc:  # the service cannot even be asked: never guess, ask a person
            if record.state == OperationState.DISPATCHED:
                record = self._save(record, log, OperationState.OUTCOME_UNKNOWN, f"{why}; outcome not recorded")
            return self._unresolved(record, log, f"{why}; looking up operation {record.operation_id} failed: "
                                                 f"{exc.message}", made)
        if found is None:
            if record.state == OperationState.DISPATCHED:  # interrupted before any answer: mark it explicitly
                record = self._save(record, log, OperationState.OUTCOME_UNKNOWN, f"{why}; state after dispatch "
                                    "not recorded")
            if not self.resend_safe:
                return self._unresolved(record, log, f"{why}; the environment has no record of operation "
                                                     f"{record.operation_id}, but it does not declare "
                                                     "env.idempotent_step: re-sending could apply it twice", made)
            note = "the environment has no record of the operation: it never took effect; re-sending the same id"
            record = self._save(record.model_copy(update={"reconciliation": ReconciliationResult(
                method="QUERY_OPERATION", found=False, note=note)}), log, record.state,
                f"queried: {note}", effect=OperationEffect.QUERY)
            return None
        if record.state == OperationState.DISPATCHED:
            record = self._save(record, log, OperationState.OUTCOME_UNKNOWN, f"{why}; outcome not recorded")
        outcome = found.model_copy(update={"operation_state": OperationState.RECONCILED})
        record = self._save(record, log, OperationState.RECONCILED,
                            f"query_operation: the environment reports {found.status.value} "
                            f"(effect applied: {found.effect_applied})", effect=OperationEffect.QUERY,
                            outcome=outcome,
                            reconciliation=ReconciliationResult(method="QUERY_OPERATION", found=True, outcome=outcome,
                                                                note="settled by the environment's operation record; "
                                                                     "not sent again"))
        return CoordinationResult(outcome, record, log, decisions=made)

    def _unresolved(self, record: OperationRecord, log: list, why: str,
                    made: list[ExecutionDecision] | None = None) -> CoordinationResult:
        from formal_lab_contracts import ReviewMark

        if record.state == OperationState.DISPATCHED:
            record = self._save(record, log, OperationState.OUTCOME_UNKNOWN, why)
        record = record.model_copy(update={"review": ReviewMark(status="NEEDS_REVIEW", by="coordinator",
                                                                at=utcnow(), note=why)})
        self.ledger.put(record)
        log.append((record.state, f"needs review: {why}"))
        return CoordinationResult(None, record, log, unresolved=True, decisions=made or [])


def _essence(outcome: ActionOutcome) -> tuple:
    return (outcome.status, outcome.effect_applied, outcome.revision_before, outcome.revision_after,
            sorted(outcome.result.get("written_paths", [])))
