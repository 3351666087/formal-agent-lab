"""D4 unit tests for the security-domain layer on the order service: the released rule set, the Broker-gated
privileged action (a denial never touches the service), and the service/model property comparison. Pure — no running
service (the full lifecycle is exercised by scripts/d4_service_lab_evidence.py)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from formal_lab_domain_broker import HmacSigner, HmacVerifier, KeyStore, VerificationReceipt, digest_params
from formal_lab_domain_broker.receipt import CheckBasis, ReceiptBindings, sign_receipt
from formal_lab_example_orders.domain_lab import (
    check_property_vs_model,
    gated_condition_change,
    orders_admission_ruleset,
)


def _keys():
    ks = KeyStore({"ops-key": b"orders-signing-secret"})
    return HmacSigner(ks, "ops-key"), HmacVerifier(ks)


def _receipt(signer, conditions, *, revision=0):
    now = datetime.now(UTC)
    r = VerificationReceipt(
        receipt_id="c", bindings=ReceiptBindings(
            run_id="redlab", step=0, actor_id="operator", operation_id="cfg", action_type="set_conditions",
            action_params_digest=digest_params({"conditions": conditions}), state_revision=revision,
            service_identity="order-service"),
        check_basis=CheckBasis(query_kind="ACTION_PRECONDITION", property_id="privileged-config", verdict="HOLDS",
                               scope="MODEL_INTERNAL", backend="z3"),
        guarantee_scope="operator-authorised change", issued_at=now.isoformat(),
        expires_at=(now + timedelta(seconds=300)).isoformat(), issuer="ops-key")
    return sign_receipt(r, signer)


def test_ruleset_released():
    rs = orders_admission_ruleset()
    assert rs.status == "RELEASED"
    assert {r.kind for r in rs.rules} == {"action_precondition", "role_rule"}


def test_denied_privileged_action_never_calls_service():
    _, verifier = _keys()
    # a bad endpoint: if the code tried to POST, it would raise — a DENY must not reach it
    out = gated_condition_change("http://127.0.0.1:1", "redlab", {"slow_stations": ["p2"]}, receipt=None,
                                 verifier=verifier, ruleset=orders_admission_ruleset(), current_revision=0,
                                 role_allowed_actions=["set_conditions"])
    assert out["admitted"] is False and out["applied"] is False and out["verdict"] == "DENY"


def test_wrong_role_denied():
    signer, verifier = _keys()
    conds = {"slow_stations": ["p2"]}
    out = gated_condition_change("http://127.0.0.1:1", "redlab", conds, receipt=_receipt(signer, conds),
                                 verifier=verifier, ruleset=orders_admission_ruleset(), current_revision=0,
                                 role_allowed_actions=["reserve"])  # operator role action not permitted
    assert out["applied"] is False and out["verdict"] == "DENY"


def test_property_comparison():
    assert check_property_vs_model(service_denied_without_receipt=True, model_blocks_unauthorized=True,
                                   comparable=True)["result"] == "CONSISTENT"
    assert check_property_vs_model(service_denied_without_receipt=False, model_blocks_unauthorized=True,
                                   comparable=True)["result"] == "MODEL_DEVIATION"
    assert check_property_vs_model(service_denied_without_receipt=True, model_blocks_unauthorized=True,
                                   comparable=False)["result"] == "UNDECIDABLE"
