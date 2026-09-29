"""Model releases and regression cases (P2-072 … P2-076): an effect difference becomes a minimal regression case;
the original model version is rejected by it, a revised version that explains the observation is released; rule
sets are type-checked with the model; releases state their checks, bounds, assumptions and log."""

from __future__ import annotations

import pytest
from formal_lab_contracts import ModelSource, RegressionCase, RuleSet
from formal_lab_env.ir_world import truth_model_ir
from formal_lab_example_scheduling.scenarios import STRATEGIES, model_package, scenario
from formal_lab_model import build_package
from formal_lab_model.rules import ruleset_digest
from formal_lab_runtime import default_registry, make_manifest, run_local
from formal_lab_runtime.release import check_release, replay_regression_case


@pytest.fixture(scope="module")
def reg():
    return default_registry()


@pytest.fixture(scope="module")
def mismatch(reg):
    pkg = model_package()
    sc = scenario("expectation-mismatch", pkg, seed=1, strategy=STRATEGIES["rule"])
    m = make_manifest(run_id="run_rel", project_id="p", scenario=sc, package=pkg, registry=reg, seed=1,
                      config={"initial_check_horizon": 0})
    res = run_local(m, pkg, reg)
    cases = [RegressionCase.model_validate(e.payload["case"]) for e in res.events
             if str(e.event_type) == "REGRESSION_CASE_CREATED"]
    suggestions = [e.payload for e in res.events if str(e.event_type) == "MODEL_REVISION_SUGGESTED"]
    return pkg, res, cases, suggestions


def revised(pkg):
    """The fix a modeller makes after reading the suggestion: m2 is degraded (constant `degraded[m2]`)."""
    ir = truth_model_ir(pkg, {"degraded[m2]": True})
    return build_package(ir, package_id=pkg.package_id, version=2,
                         source=ModelSource(format="fal-ir-json/v1", text=ir.model_dump_json(), origin="revision"))


def test_an_effect_difference_becomes_a_minimal_regression_case(mismatch):
    """P2-075 / P2-076: the difference yields a revision suggestion (action, differing fields, constants its effects
    read) and a regression case with model, scenario, seed, input state, action, expected and observed values."""
    pkg, _, cases, suggestions = mismatch
    assert cases and suggestions
    s = suggestions[0]
    assert s["different_fields"] and "degraded" in s["constants_read"] and s["action"]["action_type"] == "advance"
    c = cases[0]
    assert c.source == "EFFECT_DIFFERENCE" and c.minimized and len(c.actions) == 1
    assert c.model == pkg.ref() and c.seed == 1 and c.scenario is not None and c.initial_state
    assert c.compared_paths and all(c.expected[p] != c.observed[p] for p in c.compared_paths)
    assert c.origin["run_id"] == "run_rel"


def test_old_version_is_rejected_the_revised_one_released(reg, mismatch):
    """P2-072 / P2-073: the release runs type checks, bounded queries and every regression case; the original
    version still predicts the old values (REJECTED), the revision explains them (RELEASED)."""
    pkg, _, cases, _ = mismatch
    old, log_old = check_release(pkg, reg, cases=cases, horizon=4)
    assert old.status == "REJECTED" and all(r.status == "FAIL" for r in old.regression)
    assert any("regression case" in r for r in old.reasons) and any("[verdict] REJECTED" in line for line in log_old)
    new_pkg = revised(pkg)
    assert replay_regression_case(cases[0], new_pkg, reg).status == "PASS"
    new, _ = check_release(new_pkg, reg, cases=cases, horizon=4)
    assert new.status == "RELEASED" and not new.reasons, new.reasons
    kinds = {c.kind for c in new.checks}
    assert {"TYPE_CHECK", "GOAL_REACHABILITY", "INVARIANT_VIOLATION"} <= {str(k) for k in kinds}
    assert new.bounds and new.assumptions and new.scope == "MODEL_INTERNAL" and new.compiled
    assert new.model == new_pkg.ref() and new.release_id != old.release_id and new.stages
    again, _ = check_release(new_pkg, reg, cases=cases, horizon=4)
    assert again.release_id == new.release_id and again.digest == new.digest  # the record is reproducible


def test_rules_are_type_checked_with_the_model(reg):
    """P2-070 / P2-071 / P2-072: a rule set is released only when every rule's condition type-checks against the
    model; a wrong location or a non-boolean condition rejects the release with the rule named."""
    pkg = model_package()
    good = {"rule_id": "pause_on_difference", "trigger": {"events": ["EFFECT_COMPARED"]},
            "condition": {"op": "gt", "args": [{"op": "ref", "name": "ev_different_count"},
                                               {"op": "const", "value": 0}]},
            "priority": 10, "outcome": "PAUSE", "message": "effects differ from the model: pause and review"}
    bad = {"rule_id": "broken", "trigger": {"events": ["ACTION_OUTCOME"]},
           "condition": {"op": "var", "name": "no_such_location", "index": []}, "priority": 1,
           "outcome": "REPLAN", "message": "x"}
    for rules, status in (([good], "RELEASED"), ([good, bad], "REJECTED")):
        rs = RuleSet(ruleset_id="scheduling-rules", version=1, name="rules", model=pkg.ref(), rules=rules)
        rs = RuleSet.model_validate({**rs.model_dump(mode="json"), "digest": {"value": ruleset_digest(rs)}})
        record, _ = check_release(pkg, reg, ruleset=rs, horizon=3)
        assert record.status == status, record.reasons
        assert record.ruleset is not None and record.ruleset.digest == rs.digest
        rule_checks = {c.subject: c for c in record.checks if str(c.kind) == "RULE_CHECK"}
        assert rule_checks["pause_on_difference"].passed
        if status == "REJECTED":
            assert not rule_checks["broken"].passed and "broken" in rule_checks["broken"].subject


# ------------------------------------------------------------------ phase 3A, G3: capability report and required checks

def test_capability_report_for_the_ir_model_and_its_release_fields(reg):
    """IR model: every feature is SUPPORTED by a declared provider; query checks say what they establish
    (`property_holds`, `claim`) separately from the release process; sizes come from the declared stats()."""
    from formal_lab_runtime.release import capability_report

    pkg = model_package()
    report = capability_report(pkg, reg)
    assert {f.feature: f.status.value for f in report.features} == {
        "release.type_check": "SUPPORTED", "run.candidates": "SUPPORTED", "run.predict": "SUPPORTED",
        "release.regression_replay": "SUPPORTED", "rules": "SUPPORTED", "release.objectives": "SUPPORTED",
        "release.stats": "SUPPORTED", "query.goal_reachability": "SUPPORTED",
        "query.invariant_violation": "SUPPORTED", "query.action_precondition": "SUPPORTED",
        "query.optimize_objective": "SUPPORTED", "query.robust_sequence": "SUPPORTED"}
    rec, log = check_release(pkg, reg, horizon=4)
    assert rec.status == "RELEASED" and rec.process_completed is True and rec.config.required_checks == ["TYPE_CHECK"]
    queries = [c for c in rec.checks if str(c.kind) in ("GOAL_REACHABILITY", "INVARIANT_VIOLATION")]
    assert queries and all(c.executed and c.backend is not None and c.claim for c in queries)
    assert rec.compiled[0].stats["ground_actions"] > 0 and "action_types" in rec.compiled[0].stats
    assert "[process] completed" in log


def test_minimal_protocol_only_driver_gets_an_accurate_report_and_explicit_rejections(reg):
    """A driver that implements only the public protocol (no IR, no stats) is released on what it supports; each
    missing capability is UNSUPPORTED with its reason, and a release that requires it is not passed."""
    from fal_example_external_plugin.counter_driver import package
    from formal_lab_contracts import GroundAction, ReleaseConfig
    from formal_lab_runtime.release import capability_report

    pkg = package()
    report = capability_report(pkg, reg)
    status = {f.feature: f.status.value for f in report.features}
    assert status["release.type_check"] == status["release.regression_replay"] == "SUPPORTED"
    assert status["rules"] == status["release.stats"] == status["query.goal_reachability"] == "UNSUPPORTED"
    assert "counter_v1" in next(f.reason for f in report.features if f.feature == "query.goal_reachability")

    rec, _ = check_release(pkg, reg)  # default config: only the type check is required
    assert rec.status == "RELEASED" and rec.process_completed is True
    unsupported = [c for c in rec.checks if c.verdict == "UNSUPPORTED"]
    assert {c.subject for c in unsupported} == {"reached", "bounded"} and not any(c.executed for c in unsupported)
    assert "ground_actions" not in rec.compiled[0].stats and rec.compiled[0].stats["state_locations"] == 1

    rec, _ = check_release(pkg, reg, config=ReleaseConfig(required_checks=["TYPE_CHECK", "GOAL_REACHABILITY"]))
    assert rec.status == "REJECTED" and rec.process_completed is False
    assert "GOAL_REACHABILITY" in rec.reasons[0] and "no installed verifier" in rec.reasons[0]

    rules = RuleSet(ruleset_id="guard", version=1, name="guard", model=pkg.ref(), rules=[{
        "rule_id": "pause", "trigger": {"events": ["ACTION_OUTCOME"]}, "condition": {"op": "const", "value": True},
        "priority": 1, "outcome": "PAUSE", "message": "x"}])
    rec, _ = check_release(pkg, reg, ruleset=rules)
    assert rec.status == "REJECTED" and rec.process_completed is False
    assert any(c.kind == "RULE_CHECK" and c.verdict == "UNSUPPORTED" for c in rec.checks)

    case = RegressionCase(case_id="reg_counter", source="EFFECT_DIFFERENCE", model=pkg.ref(), seed=0,
                          initial_state={"count": 1}, actions=[GroundAction(action_type="inc")],
                          expected={"count": 2}, observed={"count": 2}, compared_paths=["count"], minimized=True,
                          created_at="2026-09-29T00:00:00Z")
    rec, _ = check_release(pkg, reg, cases=[case])
    assert rec.status == "RELEASED" and rec.regression[0].status == "PASS"


def test_process_completed_and_property_holds_are_separate(reg):
    """Requiring a property to hold: every required check runs conclusively (the process completes), and the release
    is still not passed when the property does not hold within the bound. queue-costs needs 3 steps to serve every
    job: within 2 the goal is conclusively unreachable (NO_WITNESS_WITHIN_BOUND, not a missing result)."""
    from formal_lab_contracts import ReleaseConfig
    from formal_lab_model.samples import queue_costs

    ir = queue_costs()
    pkg = build_package(ir, package_id="queue-costs", version=1,
                        source=ModelSource(format="fal-ir-json/v1", text=ir.model_dump_json(), origin="test"))
    need = ["TYPE_CHECK", "GOAL_REACHABILITY"]
    rec, _ = check_release(pkg, reg, config=ReleaseConfig(required_checks=need, required_holds=["all_served"],
                                                          horizon=2))
    check = next(c for c in rec.checks if c.subject == "all_served")
    assert check.executed and check.verdict == "NO_WITNESS_WITHIN_BOUND" and check.property_holds is False
    assert "not reachable within 2 steps" in check.claim
    assert rec.process_completed is True and rec.status == "REJECTED"
    assert any("all_served" in r and "does not hold" in r for r in rec.reasons)
    rec, _ = check_release(pkg, reg, config=ReleaseConfig(required_checks=need, required_holds=["all_served"],
                                                          horizon=3))
    assert next(c for c in rec.checks if c.subject == "all_served").property_holds is True
    assert rec.process_completed is True and rec.status == "RELEASED"
