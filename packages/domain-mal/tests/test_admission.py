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


@pytest.fixture(scope="module")
def package_def():
    graph = json.loads((FIX / "net_app_data.graph.json").read_text())
    native = json.loads((FIX / "net_app_data.native.json").read_text())["reachable_case"]
    return package_from_graph(graph, native["entry"], native["goal"], package_id="mal-net-app-data-rb", version=1,
                              reachable=native["compromised"], language={"name": "coreLang", "version": "1.0.0"},
                              include_defense=True)


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


def _receipt_and_binding(signer, params, *, revision=5, property_id="secret-confidentiality", verdict="WITNESS",
                         reach_forbidden="secret:read"):
    basis = target_check_basis(property_id=property_id, verdict=verdict, scope="MODEL_INTERNAL", backend="z3",
                               bound={"max_steps": 60},
                               target_digest=TargetSecurity(property_id=property_id,
                                                            reach_forbidden=reach_forbidden).target_digest())
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


def test_k01_same_name_different_target_cannot_reuse_credential(issuer):
    """K01: two targets share a property_id label but break on different steps. A receipt issued for one cannot
    authorise the other (its check basis is bound to the concrete target, not the label); the correct target admits."""
    signer, verifier = issuer
    params = {"n": "secret__read"}
    tgt_a = TargetSecurity(property_id="confidentiality", reach_forbidden="secret:read")
    tgt_b = TargetSecurity(property_id="confidentiality", reach_forbidden="net:eavesdrop")  # same name, other target
    assert tgt_a.target_digest() != tgt_b.target_digest()
    r, b = _receipt_and_binding(signer, params, property_id="confidentiality", reach_forbidden="secret:read")
    # reused under scenario B: the label matches but the concrete target does not → denied
    deny = admit(r, b, verifier=verifier, rules=mal_ruleset(), role_allowed_actions=["compromise"],
                 context=_ctx(params, tgt=tgt_b))
    assert not deny.allowed and deny.by_kind("target_security")[0].holds is False
    # the correct target still admits
    ok = admit(r, b, verifier=verifier, rules=mal_ruleset(), role_allowed_actions=["compromise"],
               context=_ctx(params, tgt=tgt_a))
    assert ok.allowed and ok.by_kind("target_security")[0].holds is True


def test_k01_a_receipt_without_a_target_digest_is_not_enough(issuer):
    """A legacy receipt whose basis carries no target digest cannot satisfy the condition (a name match alone is
    not the real query)."""
    signer, verifier = issuer
    params = {"n": "secret__read"}
    basis = target_check_basis(property_id="secret-confidentiality", verdict="WITNESS", scope="MODEL_INTERNAL",
                               backend="z3", bound={"max_steps": 60})  # no target_digest
    r = issue_receipt(run_id="r", step=6, actor_id="red", operation_id="op", action_params=params, state_revision=5,
                      check_basis=basis, guarantee_scope="bounded reachability", signer=signer,
                      service_identity="mal-sim")
    b = RequestBinding(run_id="r", step=6, actor_id="red", operation_id="op", action_type="compromise",
                       action_params_digest=digest_params(params), current_revision=5, service_identity="mal-sim")
    d = admit(r, b, verifier=verifier, rules=mal_ruleset(), role_allowed_actions=["compromise"], context=_ctx(params))
    assert not d.allowed and d.by_kind("target_security")[0].holds is False


def test_k03_gate_conditions_carry_the_three_states_with_detail(issuer):
    """K03 (data): real admission decisions produce ConditionChecks with holds True and False, each with a detail,
    and the contract permits holds=None (the 'unknown' state the UI must keep distinct from false)."""
    from formal_lab_contracts import ConditionCheck

    signer, verifier = issuer
    allow = admit(*_receipt_and_binding(signer, {"n": "secret__read"}), verifier=verifier, rules=mal_ruleset(),
                  role_allowed_actions=["compromise"], context=_ctx({"n": "secret__read"}))
    ts = allow.by_kind("target_security")[0]
    assert ts.holds is True and ts.detail  # true, with an explanation
    lab = LabPolicy(allowed_assets=["app"], max_attack_steps=40)  # net out of bounds → false
    deny = admit(*_receipt_and_binding(signer, {"n": "net__eavesdrop"}), verifier=verifier, rules=mal_ruleset(),
                 role_allowed_actions=["compromise"], context=_ctx({"n": "net__eavesdrop"}, lab=lab))
    lp = deny.by_kind("lab_policy")[0]
    assert lp.holds is False and lp.detail  # false, with an explanation
    # the 'unknown' state is a valid gate record (ConditionCheck.holds is bool | None); the UI renders it as 未知
    assert ConditionCheck(name="x", holds=None, detail="the gate could not determine it").holds is None


def test_k02_attack_budget_unit(tmp_path):
    """K02 budget semantics: one admit = one unit; a retry of an admitted op is not re-charged; a reload (pause/
    resume) keeps the spent count; limit None is unbounded."""
    from formal_lab_domain_mal.gate import AttackBudget

    p = tmp_path / "attack-budget.json"
    b = AttackBudget(p, "run1", 1)
    assert b.check_and_consume("op1") == (True, 1, 1)   # consumes the one unit
    assert b.check_and_consume("op2") == (False, 1, 1)  # exhausted
    assert b.check_and_consume("op1") == (True, 1, 1)   # retry of an admitted op: allowed, not re-charged
    assert AttackBudget(p, "run1", 1).check_and_consume("op3") == (False, 1, 1)  # resume: quota not regained
    unbounded = AttackBudget(tmp_path / "u.json", "r", None)
    assert all(unbounded.check_and_consume(f"op{i}")[0] for i in range(5))


def test_k02_budget_of_one_admits_one_governed_action(tmp_path, package):
    """With max_attack_steps=1 only one compromise is admitted across the run (budget 40 reaches the goal; 1 cannot),
    and the durable ledger records exactly one consumed unit."""
    tgt = TargetSecurity(property_id="secret-confidentiality", reach_forbidden="secret:read")
    out = gated_red_team(package, workdir=tmp_path, target_security=tgt,
                         lab_policy=LabPolicy(allowed_assets=["app", "secret", "net"], max_attack_steps=1))
    wr = out["with_receipts"]
    assert wr["goal_reached"] is False  # one admitted compromise cannot reach the multi-step goal
    ledger = json.loads((tmp_path / "attack-budget-run_mal_d2_admit.json").read_text())
    assert ledger["limit"] == 1 and len(ledger["admitted"]) == 1  # exactly one governed action consumed the budget


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
    # a governed non-compromise action type gets no receipt
    strict = _issuer(package, governed_action_types=["compromise", "harden"])
    assert strict.decide(_req("harden", goal_id, revision=0, values={})).verdict == "DENY"


def test_actions_outside_the_admission_scope_pass_explicitly(package):
    """Phase 4B (B3): the defender's `harden` is not an admission-governed step — it passes with a recorded reason
    and a GOVERNED_ACTION=false condition (it used to be denied, so blue could never act in a gated red/blue run)."""
    from formal_lab_domain_mal.frontend import attack_graph_of
    from formal_lab_domain_mal.gate import MalBrokerGate

    goal_id = attack_graph_of(package)["lowering"]["goal_id"]
    res = _issuer(package).decide(_req("harden", goal_id, revision=None, values={}))
    assert res.verdict == "ALLOW" and "outside this gate's admission scope" in res.reason
    assert [(c.name, c.holds) for c in res.conditions] == [("GOVERNED_ACTION", False)]
    gate = MalBrokerGate(store=None, verifier=None, id_to_full={}, lab_policy=None, target_security=None,
                         role_allowed_actions=["compromise"])
    assert gate.decide(_req("harden", goal_id, revision=0, values={})).verdict == "ALLOW"


def test_gated_red_blue_lets_blue_defend_and_denies_stale_red_steps(package_def, tmp_path):
    """A gated red/blue episode: blue's hardens are applied; red, whose role view withholds `hardened`, keeps trying a
    step blue has hardened — the issuer checks it at send time and denies it (no receipt, nothing sent)."""
    import os
    import uuid

    from formal_lab_domain_mal.run import red_blue_scenario
    from formal_lab_runtime import default_registry, make_manifest, run_local

    ks = tmp_path / "k.json"
    ks.write_text(json.dumps({"issuer-1": os.urandom(24).hex()}))
    rc = str(tmp_path / "r.json")
    tgt = {"property_id": "secret-confidentiality", "reach_forbidden": "secret:read"}
    gates = [{"plugin": {"plugin_id": "formal-lab.domain.mal.receipt-issuer", "version": "1.0.0"},
              "config": {"keystore_path": str(ks), "receipts_path": rc, "target_security": tgt}},
             {"plugin": {"plugin_id": "formal-lab.domain.mal.broker-gate", "version": "1.0.0"},
              "config": {"keystore_path": str(ks), "receipts_path": rc, "target_security": tgt,
                         "lab_policy": {"allowed_assets": ["app", "secret", "net"], "max_attack_steps": 40}}}]
    scn = red_blue_scenario(package_def, strategy="rule", horizon=30, seed=0, execution_gates=gates)
    body = scn.model_dump(mode="json")
    body["participants"][0]["view"] = {"exclude": ["hardened"], "label": "attacker view"}
    scn = scn.model_validate(body)
    reg = default_registry()
    res = run_local(make_manifest(run_id=f"t_{uuid.uuid4().hex[:6]}", project_id="t", scenario=scn,
                                  package=package_def, registry=reg), package_def, reg)
    applied = {(st.proposal.actor_id, str(st.outcome.status)) for st in res.steps if st.outcome and st.proposal}
    assert ("blue", "APPLIED") in applied and ("red", "REJECTED") in applied
    denials = [d for st in res.steps for d in (st.operation.decisions if st.operation else [])
               if str(d.verdict) == "DENY"]
    assert denials and all("ACTION_PRECONDITION_FAILED" in d.reason for d in denials)


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


def test_exported_bundle_keeps_every_gate_decision_of_a_step(package, tmp_path):
    """Phase 4B (B3): offline replay explains a step with all its pre-send decisions (issuer and Broker), not only the
    last one recorded."""
    import uuid

    from formal_lab_contracts.bundle import read_bundle
    from formal_lab_domain_mal.run import red_team_scenario
    from formal_lab_runtime import default_registry, make_manifest, run_local
    from formal_lab_runtime.bundles import bundle_from_local

    ks = tmp_path / "k.json"
    ks.write_text(json.dumps({"issuer-1": "11" * 24}))
    rc = str(tmp_path / "r.json")
    tgt = {"property_id": "secret-confidentiality", "reach_forbidden": "secret:read"}
    gates = [{"plugin": {"plugin_id": "formal-lab.domain.mal.receipt-issuer", "version": "1.0.0"},
              "config": {"keystore_path": str(ks), "receipts_path": rc, "target_security": tgt}},
             {"plugin": {"plugin_id": "formal-lab.domain.mal.broker-gate", "version": "1.0.0"},
              "config": {"keystore_path": str(ks), "receipts_path": rc, "target_security": tgt,
                         "lab_policy": {"allowed_assets": ["app", "secret", "net"], "max_attack_steps": 40}}}]
    reg = default_registry()
    scn = red_team_scenario(package, execution_gates=gates)
    res = run_local(make_manifest(run_id=f"t_{uuid.uuid4().hex[:6]}", project_id="t", scenario=scn, package=package,
                                  registry=reg), package, reg)
    step = read_bundle(bundle_from_local(res, package)).step(1)
    assert [d["decision"]["gate"]["plugin_id"] for d in step["decisions"]] == [
        "formal-lab.domain.mal.receipt-issuer", "formal-lab.domain.mal.broker-gate"]
