"""Operation identity, pre-execution decisions and unknown outcomes in the coordinator (phase 3A, G2) — against a
scripted live environment, so every send and every lookup is counted."""

from __future__ import annotations

from formal_lab_contracts import (
    ActionOutcome,
    ActionProposal,
    ExecutionDecision,
    ExecutionPhase,
    GateVerdict,
    OperationState,
    OutcomeStatus,
    utcnow,
)
from formal_lab_contracts import capabilities as caps
from formal_lab_contracts.errors import ResultUnknown
from formal_lab_runtime.coordination import Coordinator, InMemoryLedger, SendDecision, request_digest

LIVE = {caps.ENV_PERSISTENT_SESSION, caps.ENV_QUERY_OPERATION}


class Service:
    """A live backend that deduplicates by id; `lose` drops the answer of the next n sends after committing."""

    def __init__(self, lose: int = 0, lose_before_commit: bool = False):
        self.applied: dict[str, ActionProposal] = {}
        self.sends: list[str] = []
        self.queries: list[str] = []
        self.lose = lose
        self.before_commit = lose_before_commit

    def _outcome(self, p: ActionProposal, op: str) -> ActionOutcome:
        return ActionOutcome(operation_id=op, run_id=p.run_id, step_id=p.step_id, proposal_id=p.proposal_id,
                             action=p.action, status=OutcomeStatus.APPLIED, effect_applied=True, revision_before=0,
                             revision_after=1, result={"written_paths": ["x"]})

    def step(self, proposal: ActionProposal, *, operation_id: str) -> ActionOutcome:
        self.sends.append(operation_id)
        if self.lose and self.before_commit:
            self.lose -= 1
            raise ResultUnknown("connection reset before the service committed")
        self.applied.setdefault(operation_id, proposal)
        if self.lose:
            self.lose -= 1
            raise ResultUnknown("answer lost after commit")
        return self._outcome(proposal, operation_id)

    def query_operation(self, operation_id: str) -> ActionOutcome | None:
        self.queries.append(operation_id)
        p = self.applied.get(operation_id)
        return None if p is None else self._outcome(p, operation_id)


def proposal(action: str = "reserve", o: str = "o1", actor: str = "handler") -> ActionProposal:
    return ActionProposal(proposal_id="r:s1:proposal", run_id="r", step_id="r:s1", step=1, actor_id=actor,
                          action={"action_type": action, "params": {"o": o}}, based_on_revision=0,
                          source={"kind": "RULE", "strategy": {"plugin_id": "x", "version": "1.0.0"}})


def gate(verdicts: list[bool]):
    """A hook answering the given verdicts in order and recording the phases it was asked about."""
    phases: list[ExecutionPhase] = []

    def hook(phase, record, prop):
        phases.append(phase)
        allowed = verdicts[len(phases) - 1]
        d = ExecutionDecision(decision_id=f"{record.operation_id}:g0:{phase.value}:{record.attempts}", run_id="r", step=1,
                              actor_id=prop.actor_id, operation_id=record.operation_id,
                              gate={"plugin_id": "test.gate", "version": "1.0.0"}, phase=phase,
                              verdict=GateVerdict.ALLOW if allowed else GateVerdict.DENY,
                              reason="ok" if allowed else "condition fails", request_digest=record.request_digest,
                              at=utcnow())
        return SendDecision(allowed, d.reason, [d])

    return hook, phases


def test_same_id_same_request_reuses_the_result_without_sending():
    svc, ledger = Service(), InMemoryLedger()
    first = Coordinator(svc, LIVE, ledger).execute(proposal(), "op1", run_id="r", step=1)
    again = Coordinator(svc, LIVE, ledger).execute(proposal(), "op1", run_id="r", step=1)  # redelivered step
    assert first.outcome.status == OutcomeStatus.APPLIED and again.reused and again.outcome == first.outcome
    assert svc.sends == ["op1"] and len(svc.applied) == 1
    effects = [t.effect.value for t in again.record.transitions]
    assert effects == ["NONE", "SEND", "NONE", "REUSE"]  # PREPARED, DISPATCHED, COMPLETED, reused


def test_same_id_with_another_request_is_a_conflict_and_nothing_is_sent():
    svc, ledger = Service(), InMemoryLedger()
    Coordinator(svc, LIVE, ledger).execute(proposal(o="o1"), "op1", run_id="r", step=1)
    res = Coordinator(svc, LIVE, ledger).execute(proposal(o="o2"), "op1", run_id="r", step=1)
    assert res.unresolved and res.conflict and "reserve" in res.conflict and res.outcome is None
    assert svc.sends == ["op1"] and ledger.get("op1").request_digest == request_digest(proposal(o="o1"))


def test_lost_answer_is_settled_by_query_and_never_applied_twice():
    svc, ledger = Service(lose=1), InMemoryLedger()
    res = Coordinator(svc, LIVE, ledger).execute(proposal(), "op1", run_id="r", step=1)
    assert res.outcome.operation_state == OperationState.RECONCILED and svc.sends == ["op1"] and svc.queries == ["op1"]
    assert [t.effect.value for t in res.record.transitions if t.effect.value != "NONE"] == ["SEND", "QUERY"]


def test_not_found_is_resent_only_when_the_environment_deduplicates_by_id():
    # lost before commit: the service never saw it
    svc = Service(lose=1, lose_before_commit=True)
    res = Coordinator(svc, LIVE | {caps.ENV_IDEMPOTENT_STEP}, InMemoryLedger()).execute(proposal(), "op1",
                                                                                       run_id="r", step=1)
    assert res.outcome.status == OutcomeStatus.APPLIED and svc.sends == ["op1", "op1"] and len(svc.applied) == 1
    svc = Service(lose=1, lose_before_commit=True)  # same situation, backend without env.idempotent_step
    res = Coordinator(svc, LIVE, InMemoryLedger()).execute(proposal(), "op1", run_id="r", step=1)
    assert res.unresolved and res.record.review.status == "NEEDS_REVIEW" and "idempotent_step" in res.record.review.note
    assert svc.sends == ["op1"] and not svc.applied


def test_gate_is_asked_before_first_send_and_resend_but_not_on_reuse():
    svc, ledger = Service(lose=1, lose_before_commit=True), InMemoryLedger()
    hook, phases = gate([True, True])
    res = Coordinator(svc, LIVE | {caps.ENV_IDEMPOTENT_STEP}, ledger, gate=hook).execute(proposal(), "op1",
                                                                                       run_id="r", step=1)
    assert phases == [ExecutionPhase.FIRST_SEND, ExecutionPhase.RESEND] and len(res.record.decisions) == 2
    again = Coordinator(svc, LIVE | {caps.ENV_IDEMPOTENT_STEP}, ledger, gate=hook).execute(proposal(), "op1",
                                                                                         run_id="r", step=1)
    assert again.reused and phases == [ExecutionPhase.FIRST_SEND, ExecutionPhase.RESEND]  # no third question


def test_denied_send_changes_nothing_and_is_recorded():
    svc, ledger = Service(), InMemoryLedger()
    hook, _ = gate([False])
    res = Coordinator(svc, LIVE, ledger, gate=hook).execute(proposal(), "op1", run_id="r", step=1)
    assert res.denied and svc.sends == [] and res.outcome.status == OutcomeStatus.REJECTED
    assert res.outcome.effect_applied is False and res.outcome.result["reason"].startswith("EXECUTION_GATE")
    rec = ledger.get("op1")
    assert rec.state == OperationState.FAILED and rec.decisions[0].verdict == GateVerdict.DENY
    assert all(t.effect.value == "NONE" for t in rec.transitions)  # nothing was sent at any point
