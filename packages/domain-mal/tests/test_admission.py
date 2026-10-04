"""D2 tests for the MAL admission binding: the released rule set, receipt issuance, the LabPolicy / TargetSecurity
conditions, and the full gated platform run (admit → goal reached; deny → zero side effects). Offline: uses the
committed fixture, ir-world and Z3 — no MAL toolchain needed."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from formal_lab_domain_broker import HmacSigner, HmacVerifier, KeyStore, RequestBinding, admit, digest_params
from formal_lab_domain_mal.admission import issue_receipt, mal_ruleset, target_check_basis
from formal_lab_domain_mal.config import LabPolicy, TargetSecurity
from formal_lab_domain_mal.demo import gated_red_team
from formal_lab_domain_mal.frontend import package_from_graph

FIX = Path(__file__).parent / "fixtures"
PKG = Path(__file__).parents[1]


@pytest.fixture(scope="module")
def package():
    graph = json.loads((FIX / "net_app_data.graph.json").read_text())
    native = json.loads((FIX / "net_app_data.native.json").read_text())["reachable_case"]
    model = json.loads((PKG / "src/formal_lab_domain_mal/models/net_app_data.json").read_text())
    return package_from_graph(graph, native["entry"], native["goal"], package_id="mal-net-app-data", version=1,
                             reachable=native["compromised"], model=model, language={"name": "coreLang",
                                                                                     "version": "1.0.0"})


@pytest.fixture
def issuer():
    ks = KeyStore({"issuer-1": b"mal-signing-secret"})
    return HmacSigner(ks, "issuer-1"), HmacVerifier(ks)


def test_ruleset_released_with_four_kinds():
    rs = mal_ruleset()
    assert rs.status == "RELEASED"
    kinds = {r.kind for r in rs.rules}
    assert kinds == {"lab_policy", "action_precondition", "role_rule", "target_security"}
    assert rs.digest()  # frozen content digest
    # every rule kept the natural-language source it was reviewed from
    assert all(r.source for r in rs.rules)


def _ctx(params, *, lab=None, tgt=None):
    return {"lab_policy": lab or LabPolicy(allowed_assets=["app", "secret", "net"], max_attack_steps=40),
            "target_security": tgt or TargetSecurity(property_id="secret-confidentiality", reach_forbidden="secret:read"),
            "action_params": params, "id_to_full": {"secret__read": "secret:read", "net__eavesdrop": "net:eavesdrop"}}


def _receipt_and_binding(signer, params, *, revision=5, property_id="secret-confidentiality", verdict="WITNESS"):
    basis = target_check_basis(property_id=property_id, verdict=verdict, scope="MODEL_INTERNAL", backend="z3",
                               bound={"max_steps": 60})
    r = issue_receipt(run_id="r", step=6, actor_id="red", operation_id="op", action_params=params,
                      state_revision=revision, check_basis=basis, guarantee_scope="bounded reachability", signer=signer,
                      service_identity="mal-sim")
    b = RequestBinding(run_id="r", step=6, actor_id="red", operation_id="op", action_type="compromise",
                       action_params_digest=digest_params(params), current_revision=revision, service_identity="mal-sim")
    return r, b


def test_mal_admit_happy(issuer):
    signer, verifier = issuer
    params = {"n": "secret__read"}
    r, b = _receipt_and_binding(signer, params)
    d = admit(r, b, verifier=verifier, rules=mal_ruleset(), role_allowed_actions=["compromise"], context=_ctx(params))
    assert d.allowed
    for kind in ("lab_policy", "action_precondition", "role_rule", "target_security"):
        assert d.by_kind(kind)[0].holds is True


def test_lab_policy_out_of_scope_denies(issuer):
    signer, verifier = issuer
    params = {"n": "net__eavesdrop"}
    r, b = _receipt_and_binding(signer, params)
    lab = LabPolicy(allowed_assets=["app"], max_attack_steps=40)  # net not allowed
    d = admit(r, b, verifier=verifier, rules=mal_ruleset(), role_allowed_actions=["compromise"],
              context=_ctx(params, lab=lab))
    assert not d.allowed and d.by_kind("lab_policy")[0].holds is False


def test_target_security_mismatch_denies(issuer):
    signer, verifier = issuer
    params = {"n": "secret__read"}
    # receipt attests a different property → target_security condition fails
    r, b = _receipt_and_binding(signer, params, property_id="some-other-property")
    d = admit(r, b, verifier=verifier, rules=mal_ruleset(), role_allowed_actions=["compromise"], context=_ctx(params))
    assert not d.allowed and d.by_kind("target_security")[0].holds is False


def test_gated_run_admits_with_receipts_and_denies_without(tmp_path, package):
    tgt = TargetSecurity(property_id="secret-confidentiality", reach_forbidden="secret:read")
    lab = LabPolicy(allowed_assets=["app", "secret", "net"], max_attack_steps=40)
    out = gated_red_team(package, workdir=tmp_path, target_security=tgt, lab_policy=lab)
    # with receipts: every send admitted, the attack reaches the goal
    wr = out["with_receipts"]
    assert wr["status"] == "SUCCEEDED" and wr["goal_reached"] is True
    assert wr["gate_verdicts"] and all(v == "ALLOW" for v in wr["gate_verdicts"])
    # without receipts: every send denied, the goal is never compromised — zero side effects
    wo = out["without_receipts"]
    assert wo["goal_reached"] is False
    assert wo["denied_operations"] > 0
    assert "ALLOW" not in wo["gate_verdicts"]


def _issuer(package, **kw):
    from formal_lab_domain_mal.frontend import attack_graph_of
    from formal_lab_domain_mal.gate import MalReceiptIssuer
    from formal_lab_model.driver import IRFiniteDriver

    inv = {v: k for k, v in attack_graph_of(package)["lowering"]["id_map"].items()}
    return MalReceiptIssuer(loaded=IRFiniteDriver().load(package), package=package, signer=None, store=None,
                            target=TargetSecurity(property_id="secret-confidentiality", reach_forbidden="secret:read"),
                            bound={"max_steps": 60, "timeout_ms": 30000}, id_to_full=inv, **kw)


def _req(action_type, n, *, revision, values):
    from types import SimpleNamespace

    from formal_lab_contracts import GroundAction

    return SimpleNamespace(action=GroundAction(action_type=action_type, params={"n": n}),
                           execution=SimpleNamespace(current_revision=revision, revision_note="test"),
                           values=values, request_digest="d")


def test_issuer_denies_when_the_action_precondition_fails_now(package):
    from formal_lab_domain_mal.frontend import attack_graph_of

    issuer = _issuer(package)
    goal_id = attack_graph_of(package)["lowering"]["goal_id"]
    # the goal step with nothing compromised yet: its precondition does not hold → DENY, no receipt (no signer used)
    res = issuer.decide(_req("compromise", goal_id, revision=0, values={}))
    assert res.verdict == "DENY" and "ACTION_PRECONDITION_FAILED" in res.reason


def test_issuer_denies_without_a_current_revision_or_for_a_non_compromise_action(package):
    from formal_lab_domain_mal.frontend import attack_graph_of

    issuer = _issuer(package)
    goal_id = attack_graph_of(package)["lowering"]["goal_id"]
    assert issuer.decide(_req("compromise", goal_id, revision=None, values={})).verdict == "DENY"
    assert issuer.decide(_req("harden", goal_id, revision=0, values={})).verdict == "DENY"


def test_per_action_loop_issues_a_receipt_per_revision_and_reaches_goal(package, tmp_path):
    from formal_lab_domain_mal.demo import per_action_gated_red_team

    out = per_action_gated_red_team(package, workdir=tmp_path, strategy="symbolic",
                                    target_security=TargetSecurity(property_id="secret-confidentiality",
                                                                   reach_forbidden="secret:read"),
                                    lab_policy=LabPolicy(allowed_assets=["app", "secret", "net"], max_attack_steps=40))
    assert out["run"]["goal_reached"] and out["run"]["status"] == "SUCCEEDED"
    assert out["every_send_checked_at_its_revision"]
    revs = [d["checked_at_revision"] for d in out["issuer_decisions"]]
    assert revs == sorted(revs) and len(revs) >= 3  # one issuer check per send, at increasing revisions
