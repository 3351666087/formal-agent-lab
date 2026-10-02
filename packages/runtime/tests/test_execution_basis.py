"""Authoritative execution basis (phase 4A, A2): identity from the kernel's turn, the current revision from the
environment, conditional writes refused at the side-effect boundary — against a scripted versioned service that
counts every write, so "nothing was written" is read from the service, not inferred."""

from __future__ import annotations

from types import SimpleNamespace

from formal_lab_contracts import (
    ActionOutcome,
    ActionProposal,
    ExecutionPhase,
    GateResult,
    OperationState,
    OutcomeStatus,
    PluginRef,
    execution_binding,
    execution_binding_digest,
)
from formal_lab_contracts import capabilities as caps
from formal_lab_contracts.errors import ResultUnknown
from formal_lab_runtime.coordination import Coordinator, InMemoryLedger
from formal_lab_runtime.engine import KERNEL_BASIS, _send_hook

LIVE = {caps.ENV_PERSISTENT_SESSION, caps.ENV_QUERY_OPERATION, caps.ENV_IDEMPOTENT_STEP, caps.ENV_CURRENT_REVISION,
        caps.ENV_CONDITIONAL_STEP}


class VersionedService:
    """Applies an operation once per id; with `expected_revision` the write is conditional (EXACT)."""

    def __init__(self, revision: int = 0):
        self.revision = revision
        self.writes: list[str] = []  # operation ids that changed the state
        self.refused: list[tuple[str, int, int]] = []  # (operation id, expected, actual)
        self.answers: dict[str, ActionOutcome] = {}
        self.down = False
        self.lose_next = False
        self.drop_next = 0  # the next n sends die before the service commits (another writer lands meanwhile)

    def current_revision(self) -> int:
        if self.down:
            raise ConnectionError("service unreachable")
        return self.revision

    def other_writer(self, n: int = 1) -> None:
        self.revision += n

    def step(self, proposal: ActionProposal, *, operation_id: str, expected_revision: int | None = None):
        if operation_id in self.answers:
            return self.answers[operation_id]
        if self.drop_next:
            self.drop_next -= 1
            self.other_writer(2)
            raise ResultUnknown("connection reset before the service committed")
        before = self.revision
        if expected_revision is not None and expected_revision != self.revision:
            self.refused.append((operation_id, expected_revision, self.revision))
            out = ActionOutcome(operation_id=operation_id, run_id=proposal.run_id, step_id=proposal.step_id,
                                action=proposal.action, status=OutcomeStatus.REJECTED, effect_applied=False,
                                revision_before=before, revision_after=before,
                                result={"reason": f"STALE_REVISION: verified at {expected_revision}, at {before}"})
        else:
            self.revision += 1
            self.writes.append(operation_id)
            out = ActionOutcome(operation_id=operation_id, run_id=proposal.run_id, step_id=proposal.step_id,
                                action=proposal.action, status=OutcomeStatus.APPLIED, effect_applied=True,
                                revision_before=before, revision_after=self.revision)
        self.answers[operation_id] = out
        if self.lose_next:
            self.lose_next = False
            raise ResultUnknown("answer lost after commit")
        return out

    def query_operation(self, operation_id: str):
        return self.answers.get(operation_id)


class RecordingGate:
    """An execution gate that admits only when the receipt revision equals the kernel's current one."""

    def __init__(self, receipt_revision: int | None = None, during=None):
        self.receipt_revision = receipt_revision
        self.during = during
        self.requests = []

    def paths(self, action):
        return []

    def decide(self, request):
        self.requests.append(request)
        if self.during is not None:
            self.during()
        ex = request.execution
        if self.receipt_revision is not None and ex.current_revision != self.receipt_revision:
            return GateResult(verdict="DENY", reason=f"receipt checked at {self.receipt_revision}, "
                                                     f"current {ex.current_revision}")
        return GateResult(verdict="ALLOW", reason="ok")


def rc_for(env, env_caps=LIVE, gates=()):
    pkg = SimpleNamespace(package_id="m", version="1.0.0", digest=SimpleNamespace(value="a" * 64))
    scenario = SimpleNamespace(environment=SimpleNamespace(plugin=PluginRef(plugin_id="test.env", version="1.0.0")))
    manifest = SimpleNamespace(run_id="r", scenario=scenario, rules=None)
    refs = [(PluginRef(plugin_id=f"test.gate{i}", version="1.0.0"), g, {}) for i, g in enumerate(gates)]
    return SimpleNamespace(env=env, env_caps=set(env_caps), run_id="r", manifest=manifest, package=pkg,
                           driver_ref=None, participants={}, gates=refs)


def proposal(*, actor: str = "handler", run: str = "r", step: int = 1, rev: int = 5,
             params: dict | None = None) -> ActionProposal:
    return ActionProposal(proposal_id=f"{run}:s{step}:proposal", run_id=run, step_id=f"{run}:s{step}", step=step,
                          actor_id=actor, action={"action_type": "reserve", "params": params or {"o": "o1"}},
                          based_on_revision=rev, source={"kind": "RULE", "strategy": {"plugin_id": "x",
                                                                                       "version": "1.0.0"}})


def coordinator(svc, gates=(), ledger=None, env_caps=LIVE, actor="handler"):
    rc = rc_for(svc, env_caps, gates)
    return Coordinator(svc, set(env_caps), ledger or InMemoryLedger(), gate=_send_hook(rc, 1, actor)), rc


def test_basis_carries_proposal_and_current_revision_apart():
    svc = VersionedService(revision=7)
    gate = RecordingGate()
    coord, _ = coordinator(svc, [gate])
    result = coord.execute(proposal(rev=5), "op1", run_id="r", step=1)
    ex = gate.requests[0].execution
    assert (ex.proposal_revision, ex.current_revision, ex.revision_source) == (5, 7, "FRESH")
    assert ex.actor_id == "handler" and ex.operation_id == "op1" and ex.phase == ExecutionPhase.FIRST_SEND
    assert result.outcome.status is OutcomeStatus.APPLIED and svc.writes == ["op1"]


def test_receipt_at_5_with_service_at_7_writes_nothing():
    svc = VersionedService(revision=7)
    coord, _ = coordinator(svc, [RecordingGate(receipt_revision=5)])
    result = coord.execute(proposal(rev=5), "op1", run_id="r", step=1)
    assert result.denied and result.record.state is OperationState.FAILED
    assert svc.writes == [] and svc.revision == 7 and "op1" not in svc.answers  # never reached the service


def test_state_change_after_the_check_is_refused_by_the_conditional_write():
    svc = VersionedService(revision=5)
    gate = RecordingGate(receipt_revision=5, during=lambda: svc.other_writer(1))  # a writer lands after the check
    coord, _ = coordinator(svc, [gate])
    result = coord.execute(proposal(rev=5), "op1", run_id="r", step=1)
    assert result.outcome.status is OutcomeStatus.REJECTED and not result.outcome.effect_applied
    assert svc.writes == [] and svc.refused == [("op1", 5, 6)]


def test_legal_send_at_the_same_revision_applies_once():
    svc = VersionedService(revision=5)
    coord, _ = coordinator(svc, [RecordingGate(receipt_revision=5)])
    result = coord.execute(proposal(rev=5), "op1", run_id="r", step=1)
    assert result.outcome.status is OutcomeStatus.APPLIED and svc.writes == ["op1"] and svc.revision == 6


def test_unknown_current_revision_blocks_a_conditional_write():
    svc = VersionedService(revision=5)
    svc.down = True
    gate = RecordingGate()
    coord, _ = coordinator(svc, [gate])
    result = coord.execute(proposal(rev=5), "op1", run_id="r", step=1)
    assert result.denied and svc.writes == [] and gate.requests == []  # gates are not even asked
    d = result.record.decisions[-1]
    assert d.gate == KERNEL_BASIS and d.reason.startswith("BASIS_UNKNOWN")
    assert d.execution.current_revision is None and d.execution.revision_source == "UNKNOWN"


def test_a_proposal_claiming_another_identity_is_refused():
    for bad in (proposal(actor="intruder"), proposal(run="other"), proposal(step=2)):
        svc = VersionedService(revision=5)
        coord, _ = coordinator(svc, [RecordingGate()])
        result = coord.execute(bad, "op1", run_id="r", step=1)
        assert result.denied and svc.writes == [], bad
        assert result.record.decisions[-1].reason.startswith("IDENTITY_MISMATCH")


def test_resend_after_a_lost_send_is_checked_against_the_fresh_basis():
    svc = VersionedService(revision=5)
    svc.drop_next = 1  # the first send never commits; another writer moves the state to 7 meanwhile
    gate = RecordingGate(receipt_revision=5)  # the receipt issued for the first send
    coord, _ = coordinator(svc, [gate])
    result = coord.execute(proposal(rev=5), "op1", run_id="r", step=1)
    phases = [(r.execution.phase, r.execution.current_revision) for r in gate.requests]
    assert phases == [(ExecutionPhase.FIRST_SEND, 5), (ExecutionPhase.RESEND, 7)]
    assert result.denied and svc.writes == [] and svc.revision == 7


def test_resend_with_a_fresh_check_applies_once():
    svc = VersionedService(revision=5)
    svc.drop_next = 1
    gate = RecordingGate()  # re-checked (e.g. a receipt re-issued) at the resend's own basis
    coord, _ = coordinator(svc, [gate])
    result = coord.execute(proposal(rev=5), "op1", run_id="r", step=1)
    assert result.outcome.status is OutcomeStatus.APPLIED and svc.writes == ["op1"]
    assert result.outcome.revision_before == 7  # written at the basis it was re-checked on


def test_lost_answer_is_reconciled_not_rewritten():
    svc = VersionedService(revision=5)
    svc.lose_next = True
    coord, _ = coordinator(svc, [RecordingGate(receipt_revision=5)])
    result = coord.execute(proposal(rev=5), "op1", run_id="r", step=1)
    assert result.record.state is OperationState.RECONCILED and svc.writes == ["op1"]


def test_two_workers_sharing_the_ledger_send_once():
    svc = VersionedService(revision=5)
    ledger = InMemoryLedger()
    g1, g2 = RecordingGate(), RecordingGate()
    a, _ = coordinator(svc, [g1], ledger)
    b, _ = coordinator(svc, [g2], ledger)
    a.execute(proposal(rev=5), "op1", run_id="r", step=1)
    again = b.execute(proposal(rev=5), "op1", run_id="r", step=1)
    assert again.reused and svc.writes == ["op1"] and g2.requests == []


def test_same_id_other_request_is_a_conflict():
    svc = VersionedService(revision=5)
    ledger = InMemoryLedger()
    coord, _ = coordinator(svc, [RecordingGate()], ledger)
    coord.execute(proposal(rev=5), "op1", run_id="r", step=1)
    clash = coord.execute(proposal(rev=5, params={"o": "o2"}), "op1", run_id="r", step=1)
    assert clash.unresolved and clash.conflict and svc.writes == ["op1"]


def test_binding_is_one_canonical_definition():
    svc = VersionedService(revision=7)
    gate = RecordingGate()
    coord, _ = coordinator(svc, [gate])
    coord.execute(proposal(rev=5), "op1", run_id="r", step=1)
    ex = gate.requests[0].execution
    b = execution_binding(ex)
    assert b["current_revision"] == 7 and b["environment"] == "test.env@1.0.0" and b["operation_id"] == "op1"
    assert execution_binding_digest(ex) == execution_binding_digest(ex.model_copy())
    assert execution_binding_digest(ex) != execution_binding_digest(ex.model_copy(update={"session_id": "other"}))
    # the strategy's own claims (proposal id, rationale) are not part of the binding
    assert "proposal_id" not in b and "rationale" not in b


def test_without_conditional_writes_an_unknown_revision_does_not_block_but_is_marked():
    svc = VersionedService(revision=5)
    gate = RecordingGate()
    caps_ = {caps.ENV_PERSISTENT_SESSION, caps.ENV_QUERY_OPERATION}
    coord, _ = coordinator(svc, [gate], env_caps=caps_)
    result = coord.execute(proposal(rev=5), "op1", run_id="r", step=1)
    ex = gate.requests[0].execution
    assert ex.current_revision is None and ex.revision_source == "UNKNOWN"
    assert result.outcome.status is OutcomeStatus.APPLIED  # a gate that needs the revision must deny on its own
