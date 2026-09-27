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
