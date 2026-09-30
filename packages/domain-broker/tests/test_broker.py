"""D2 unit tests for the admission broker: receipts, bindings, freshness, expiry, rules and role boundaries.

Pure — no MAL toolchain, no platform run. Every DENY path here is a "zero side effect" case: the Broker refuses before
anything is sent."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from formal_lab_contracts import ParticipantView
from formal_lab_domain_broker import (
    CheckBasis,
    HmacSigner,
    HmacVerifier,
    KeyStore,
    ReceiptBindings,
    ReceiptStore,
    RequestBinding,
    Rule,
    RuleSet,
    RuleStatus,
    VerificationReceipt,
    admit,
    condition,
    digest_params,
    evaluate,
    red_blue_boundaries,
    sign_receipt,
    signature_ok,
)
from formal_lab_domain_broker.roles import RoleBoundary


@pytest.fixture
def keys():
    ks = KeyStore({"issuer-1": b"a-signing-secret-kept-apart-from-env-creds"})
    return ks, HmacSigner(ks, "issuer-1"), HmacVerifier(ks)


def _rules() -> RuleSet:
    return RuleSet(ruleset_id="t", version=1, status=RuleStatus.DRAFT, rules=[
        Rule(rule_id="r.receipt", on="side_effect_action", when=["receipt_present", "receipt_authorizes_action"],
             then="REQUIRE_RECEIPT", kind="action_precondition", status=RuleStatus.REVIEWED, source="need a receipt"),
        Rule(rule_id="r.role", on="side_effect_action", when=["role_permits_action"], then="ADMIT", kind="role_rule",
             status=RuleStatus.REVIEWED, source="role may act"),
    ]).released()


def _receipt(signer, *, revision=5, params=None, expires_in=300) -> VerificationReceipt:
    params = params or {"n": "x"}
    now = datetime.now(UTC)
    r = VerificationReceipt(
        receipt_id="rc1",
        bindings=ReceiptBindings(run_id="run1", step=6, actor_id="red", operation_id="op6", action_type="compromise",
                                 action_params_digest=digest_params(params), state_revision=revision,
                                 service_identity="svc"),
        check_basis=CheckBasis(query_kind="GOAL_REACHABILITY", property_id="p", verdict="WITNESS",
                               scope="MODEL_INTERNAL", backend="z3"),
        guarantee_scope="bounded reachability", issued_at=now.isoformat(),
        expires_at=(now + timedelta(seconds=expires_in)).isoformat(), issuer="issuer-1")
    return sign_receipt(r, signer)


def _binding(*, revision=5, params=None) -> RequestBinding:
    params = params or {"n": "x"}
    return RequestBinding(run_id="run1", step=6, actor_id="red", operation_id="op6", action_type="compromise",
                          action_params_digest=digest_params(params), current_revision=revision, service_identity="svc")


def test_sign_and_verify_roundtrip(keys):
    _, signer, verifier = keys
    r = _receipt(signer)
    assert signature_ok(r, verifier)
    assert r.issuer == "issuer-1"


def test_happy_admit(keys):
    _, signer, verifier = keys
    d = admit(_receipt(signer), _binding(), verifier=verifier, rules=_rules(), role_allowed_actions=["compromise"])
    assert d.allowed
    assert d.by_kind("provenance")[0].holds
    assert d.by_kind("role_rule")[0].holds


def test_missing_receipt_denies(keys):
    _, _, verifier = keys
    d = admit(None, _binding(), verifier=verifier, rules=_rules(), role_allowed_actions=["compromise"])
    assert not d.allowed and d.verdict == "DENY"


def test_tampered_signature_denies(keys):
    _, signer, verifier = keys
    bad = replace(_receipt(signer), signature="00" * 32)
    d = admit(bad, _binding(), verifier=verifier, rules=_rules(), role_allowed_actions=["compromise"])
    assert not d.allowed and d.by_kind("provenance")[0].holds is False


def test_binding_mismatch_denies(keys):
    _, signer, verifier = keys
    d = admit(_receipt(signer), replace(_binding(), actor_id="blue"), verifier=verifier, rules=_rules(),
              role_allowed_actions=["compromise"])
    assert not d.allowed
    assert any(r.kind == "binding" and r.holds is False for r in d.reasons)


def test_stale_revision_denies(keys):
    _, signer, verifier = keys
    d = admit(_receipt(signer, revision=5), _binding(revision=7), verifier=verifier, rules=_rules(),
              role_allowed_actions=["compromise"])
    assert not d.allowed and d.by_kind("state_revision")[0].holds is False


def test_expired_receipt_denies(keys):
    _, signer, verifier = keys
    r = _receipt(signer, expires_in=-1)
    d = admit(r, _binding(), verifier=verifier, rules=_rules(), role_allowed_actions=["compromise"])
    assert not d.allowed and d.by_kind("expiry")[0].holds is False


def test_wrong_role_denies(keys):
    _, signer, verifier = keys
    d = admit(_receipt(signer), _binding(), verifier=verifier, rules=_rules(), role_allowed_actions=["observe"])
    assert not d.allowed and d.by_kind("role_rule")[0].holds is False


def test_unknown_condition_denies_and_is_not_silently_true(keys):
    _, signer, verifier = keys
    # role_allowed_actions=None makes role_permits_action undeterminable → the rule does not fire → DENY
    d = admit(_receipt(signer), _binding(), verifier=verifier, rules=_rules(), role_allowed_actions=None)
    assert not d.allowed
    assert d.by_kind("role_rule")[0].holds is None


def test_wrong_key_fails_verification():
    ks_issuer = KeyStore({"issuer-1": b"secret-A"})
    ks_broker = KeyStore({"issuer-1": b"secret-B"})  # broker has a different secret under the same id
    signer = HmacSigner(ks_issuer, "issuer-1")
    d = admit(_receipt(signer), _binding(), verifier=HmacVerifier(ks_broker), rules=_rules(),
              role_allowed_actions=["compromise"])
    assert not d.allowed and d.by_kind("provenance")[0].holds is False


def test_ruleset_must_be_reviewed_before_release():
    rs = RuleSet(ruleset_id="x", version=1, rules=[
        Rule(rule_id="d", on="e", when=[], then="ADMIT", status=RuleStatus.DRAFT)])
    with pytest.raises(ValueError, match="DRAFT"):
        rs.released()


def test_evaluate_refuses_unreleased_ruleset():
    rs = RuleSet(ruleset_id="x", version=1, rules=[])
    with pytest.raises(ValueError, match="not RELEASED"):
        evaluate(rs, "side_effect_action", {})


def test_receipt_store_roundtrip(tmp_path, keys):
    _, signer, _ = keys
    store = ReceiptStore(tmp_path / "r.json")
    store.put("digest-1", _receipt(signer))
    reloaded = ReceiptStore(tmp_path / "r.json")  # a separate reader (e.g. the gate process)
    got = reloaded.get("digest-1")
    assert got is not None and got.bindings.actor_id == "red"
    assert reloaded.get("absent") is None


def test_provenance_survives_expiry_for_history(keys):
    """Credential/receipt expiry does not block verifying provenance of a historical record (D2)."""
    _, signer, verifier = keys
    r = _receipt(signer, expires_in=-100)
    assert signature_ok(r, verifier)  # still authentic, even though admit() would refuse a fresh send
    assert r.is_expired()


# ------------------------------------------------------------------ role boundaries


def test_red_blue_leak_guard():
    b = red_blue_boundaries()
    attacker = b["attacker"]
    # a payload that legitimately carries compromise state but also, by mistake, ground truth + a signing key
    payload = {"compromised": {"app:read": True}, "ground_truth": {"secret:read": True}, "signing_key": "deadbeef"}
    leaks = attacker.leaks(payload)
    assert "ground_truth" in leaks and "signing_key" in leaks
    clean = {"compromised": {"app:read": True}}
    assert attacker.leaks(clean) == []


def test_view_redaction_withholds_secret_paths():
    rb = RoleBoundary(role="attacker", view=ParticipantView(include=["compromised"], exclude=["defense"]),
                      secret_paths=["ground_truth"], credential_fields=["signing_key"])
    state = {"compromised[app:read]": True, "defense[eavesdrop]": False, "ground_truth[secret:read]": True}
    red = rb.redact_state(state)
    assert "compromised[app:read]" in red
    assert "defense[eavesdrop]" not in red and "ground_truth[secret:read]" not in red


def test_custom_condition_registration():
    @condition("always_true_probe")
    def _p(ctx):
        return True

    from formal_lab_domain_broker.rules import evaluate_condition
    assert evaluate_condition("always_true_probe", {}) is True
    assert evaluate_condition("no_such_condition", {}) is None
