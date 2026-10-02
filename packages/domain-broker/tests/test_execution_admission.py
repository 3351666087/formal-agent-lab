"""Admission against the kernel's ExecutionContext (phase 4A, A2): one canonical binding for issuing and verifying,
every mismatch its own reason, the revision checked against the environment's current one."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from formal_lab_contracts import (
    ExecutionContext,
    GateRequest,
    PluginRef,
    TurnRef,
    execution_binding,
    params_digest,
    utcnow,
)
from formal_lab_domain_broker import (
    CheckBasis,
    HmacSigner,
    HmacVerifier,
    KeyStore,
    ReceiptIssuerGate,
    ReceiptStore,
    Rule,
    RuleSet,
    RuleStatus,
    admit_execution,
    bindings_from_context,
    issue_for_context,
)
from formal_lab_domain_broker.broker import BrokerGate

BASIS = CheckBasis(query_kind="ACTION_PRECONDITION", property_id=None, verdict="HOLDS", scope="MODEL_INTERNAL",
                   backend="formal-lab.verifier.z3-bmc@1.1.0")


@pytest.fixture
def keys():
    ks = KeyStore({"issuer-1": b"signing-secret-kept-apart-from-env-credentials"})
    return HmacSigner(ks, "issuer-1"), HmacVerifier(ks)


def rules() -> RuleSet:
    return RuleSet(ruleset_id="t", version=1, status=RuleStatus.DRAFT, rules=[
        Rule(rule_id="r.receipt", on="side_effect_action", when=["receipt_present", "receipt_authorizes_action"],
             then="REQUIRE_RECEIPT", kind="action_precondition", status=RuleStatus.REVIEWED, source="receipt"),
    ]).released()


def context(**over) -> ExecutionContext:
    base = dict(run_id="run1", step=6, turn=TurnRef(global_step=6, round=3, actor_id="red", actor_step=3),
                actor_id="red", operation_id="run1:s6:red:apply", phase="FIRST_SEND", action_type="reserve",
                action_params_digest=params_digest({"o": "o1"}), request_digest="d" * 64,
                environment=PluginRef(plugin_id="formal-lab.example.orders.service", version="1.0.0"),
                session_id="t-1", service_identity="http://127.0.0.1:8765", proposal_revision=5, current_revision=7,
                revision_source="FRESH", revision_note="read", versions={"model": "m@1", "view": "v1"},
                read_at=utcnow())
    base.update(over)
    return ExecutionContext(**base)


def test_receipt_at_5_does_not_admit_a_send_at_7(keys):
    signer, verifier = keys
    receipt = issue_for_context(context(current_revision=5), check_basis=BASIS, guarantee_scope="s", signer=signer)
    d = admit_execution(receipt, context(current_revision=7), verifier=verifier, rules=rules())
    assert not d.allowed
    stale = next(r for r in d.reasons if r.kind == "state_revision")
    assert stale.holds is False and "checked at revision 5" in stale.detail and "at 7" in stale.detail


def test_receipt_issued_for_the_same_context_admits(keys):
    signer, verifier = keys
    ctx = context()
    receipt = issue_for_context(ctx, check_basis=BASIS, guarantee_scope="s", signer=signer)
    assert receipt.bindings.binding == execution_binding(ctx)
    assert admit_execution(receipt, ctx, verifier=verifier, rules=rules()).allowed


@pytest.mark.parametrize("field,value", [
    ("session_id", "t-2"),
    ("environment", PluginRef(plugin_id="formal-lab.example.orders.service", version="2.0.0")),
    ("turn", TurnRef(global_step=6, round=4, actor_id="red", actor_step=3)),
    ("versions", {"model": "m@2", "view": "v1"}),
    ("operation_id", "run1:s6:red:apply:other"),
    ("action_params_digest", params_digest({"o": "o2"})),
    ("actor_id", "blue"),
    ("service_identity", "http://127.0.0.1:9999"),
    ("run_id", "run2"),
])
def test_every_binding_mismatch_is_an_explicit_reason(keys, field, value):
    signer, verifier = keys
    receipt = issue_for_context(context(), check_basis=BASIS, guarantee_scope="s", signer=signer)
    d = admit_execution(receipt, context(**{field: value}), verifier=verifier, rules=rules())
    assert not d.allowed
    failed = [r.detail for r in d.reasons if r.kind == "binding" and r.holds is False]
    assert any(r.startswith(f"{field}:") and "MISMATCH" in r for r in failed), failed


def test_unknown_current_revision_never_admits(keys):
    signer, verifier = keys
    receipt = issue_for_context(context(), check_basis=BASIS, guarantee_scope="s", signer=signer)
    d = admit_execution(receipt, context(current_revision=None, revision_source="UNKNOWN", revision_note="down"),
                        verifier=verifier, rules=rules())
    assert not d.allowed and any("current revision unknown" in r.detail for r in d.reasons)


def test_missing_required_binding_denies(keys):
    signer, verifier = keys
    receipt = issue_for_context(context(), check_basis=BASIS, guarantee_scope="s", signer=signer)
    d = admit_execution(receipt, context(session_id=None), verifier=verifier, rules=rules())
    assert not d.allowed and any("required binding session_id is missing" in r.detail for r in d.reasons)


def test_receipt_without_execution_binding_or_tampered_denies(keys):
    from dataclasses import replace

    signer, verifier = keys
    ctx = context()
    receipt = issue_for_context(ctx, check_basis=BASIS, guarantee_scope="s", signer=signer)
    legacy = replace(receipt, bindings=replace(receipt.bindings, binding=None, binding_digest=None))
    assert not admit_execution(legacy, ctx, verifier=verifier, rules=rules()).allowed
    forged = replace(receipt, bindings=replace(bindings_from_context(context(current_revision=9))))
    d = admit_execution(forged, context(current_revision=9), verifier=verifier, rules=rules())
    assert not d.allowed and any(r.kind == "provenance" and r.holds is False for r in d.reasons)


def test_expired_receipt_denies(keys):
    signer, verifier = keys
    past = datetime.now(UTC) - timedelta(hours=2)
    receipt = issue_for_context(context(), check_basis=BASIS, guarantee_scope="s", signer=signer, ttl_seconds=60,
                                now=past)
    assert not admit_execution(receipt, context(), verifier=verifier, rules=rules()).allowed


def test_issuer_refuses_without_a_current_revision(keys):
    signer, _ = keys
    with pytest.raises(ValueError):
        issue_for_context(context(current_revision=None), check_basis=BASIS, guarantee_scope="s", signer=signer)


def _request(ctx: ExecutionContext) -> GateRequest:
    action = {"action_type": ctx.action_type, "params": {"o": "o1"}}
    return GateRequest(run_id=ctx.run_id, step=ctx.step, actor_id=ctx.actor_id, operation_id=ctx.operation_id,
                       phase=ctx.phase, action=action, proposal_id="p", based_on_revision=ctx.proposal_revision,
                       values={}, values_source="NONE", request_digest=ctx.request_digest, config={},
                       execution=ctx)


def test_issuer_then_broker_gate_admit_only_the_issued_basis(keys):
    signer, verifier = keys
    store = ReceiptStore()
    issuer = ReceiptIssuerGate(store=store, signer=signer, basis=lambda _r: BASIS, guarantee_scope="s")
    broker = BrokerGate(store=store, verifier=verifier, rules=rules())
    ctx = context(current_revision=5)
    assert issuer.decide(_request(ctx)).verdict == "ALLOW"
    assert broker.decide(_request(ctx)).verdict == "ALLOW"
    moved = broker.decide(_request(context(current_revision=7)))  # same request digest, state moved
    assert moved.verdict == "DENY" and "the state changed since the check" in moved.reason
    unknown = issuer.decide(_request(context(current_revision=None, revision_source="UNKNOWN")))
    assert unknown.verdict == "DENY"
    nothing = ReceiptIssuerGate(store=store, signer=signer, basis=lambda _r: None, guarantee_scope="s")
    assert nothing.decide(_request(ctx)).verdict == "DENY"


def test_broker_gate_without_execution_context_keeps_the_phase3_path(keys):
    _, verifier = keys
    broker = BrokerGate(store=ReceiptStore(), verifier=verifier, rules=rules())
    req = _request(context()).model_copy(update={"execution": None})
    assert broker.decide(req).verdict == "DENY"  # no receipt → denied, as before
