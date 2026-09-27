from __future__ import annotations

import json

import pytest
from formal_lab_contracts import ModelIR, ModelSource, Observation
from formal_lab_contracts.errors import InvalidInput, Unsupported
from formal_lab_model import (
    GroundAction,
    Interpreter,
    action_specs,
    bfs,
    canonical_ir,
    check_model,
    compare_effects,
    diff_models,
    ir_digest,
)
from formal_lab_model.frontend import IRJsonFrontend
from formal_lab_model.samples import ap, assign, c, lamp, random_model, two_jobs, v


def interp(ir: ModelIR) -> Interpreter:
    checked = check_model(ir)
    assert checked.issues == [], checked.issues
    return Interpreter(checked)


# ----------------------------------------------------------------------------- checker


def test_sample_models_are_well_formed():
    for ir in (lamp(), two_jobs(), *(random_model(s) for s in range(40))):
        assert check_model(ir).issues == []


def _with(ir: ModelIR, patch) -> ModelIR:
    data = ir.model_dump(mode="json")
    patch(data)
    return ModelIR.model_validate(data)


@pytest.mark.parametrize(
    ("patch", "code"),
    [
        (lambda d: d["properties"][0].__setitem__("expr", v("nope")), "UNKNOWN_VARIABLE"),
        (lambda d: d["properties"][0].__setitem__("expr", ap("add", v("toggles"), c(1))), "TYPE_MISMATCH"),
        (lambda d: d["properties"][0].__setitem__("expr", ap("and", v("on"), v("toggles"))), "TYPE_MISMATCH"),
        (lambda d: d["actions"][0]["effects"].append(assign("on", c(3))), "TYPE_MISMATCH"),
        (lambda d: d["state"].append(dict(d["state"][0])), "DUPLICATE_NAME"),
        (lambda d: d["state"][1]["initial"].__setitem__("default", 9), "BAD_VALUE"),
        (lambda d: d["actions"][0].__setitem__("precondition", {"op": "ref", "name": "ghost"}), "UNBOUND"),
        (lambda d: d.__setitem__("semantic_profile", "probabilistic_v1"), "UNSUPPORTED_PROFILE"),
        (lambda d: d.__setitem__("features", ["probabilistic_effects"]), "UNSUPPORTED_FEATURE"),
    ],
)
def test_checker_reports_issues(patch, code):
    issues = check_model(_with(lamp(), patch)).issues
    assert code in {i.code for i in issues}, issues


def test_checker_table_and_symbol_rules():
    def patch(d):
        d["constants"][0]["value"] = {"cells": [{"index": ["a"], "value": 2}]}  # b missing, no default

    assert "INCOMPLETE_TABLE" in {i.code for i in check_model(_with(two_jobs(), patch)).issues}

    def assign_const(d):
        d["actions"][1]["effects"].append(assign("duration", c(1), c("a")))

    assert "ASSIGN_TO_CONSTANT" in {i.code for i in check_model(_with(two_jobs(), assign_const)).issues}

    def ambiguous(d):
        d["enums"].append({"name": "other", "values": ["done", "x"]})
        d["properties"].append({"id": "amb", "kind": "goal", "expr": ap("eq", c("done"), c("done"))})

    assert "AMBIGUOUS_SYMBOL" in {i.code for i in check_model(_with(two_jobs(), ambiguous)).issues}


# ----------------------------------------------------------------------------- interpreter


def test_lamp_semantics_and_domain_guard():
    it = interp(lamp())
    s = it.initial_state()
    toggle = GroundAction("toggle", ())
    for expected in (1, 2, 3):
        s = it.apply(toggle, s)
        assert s["toggles"] == expected
    assert s["on"] is True
    res = it.step(toggle, s)  # toggles would become 4 > max 3
    assert not res.applicable and res.reason.startswith("DOMAIN_GUARD")
    assert it.apply(GroundAction("reset", ()), s) == {"on": False, "toggles": 0}


def test_later_write_wins():
    ir = _with(lamp(), lambda d: d["actions"][0]["effects"].append(assign("on", c(False))))
    it = interp(ir)
    s = it.apply(GroundAction("toggle", ()), it.initial_state())
    assert s["on"] is False and s["toggles"] == 1


def test_two_jobs_quantifiers_forall_effects_and_dependencies():
    it = interp(two_jobs())
    s = it.initial_state()
    applicable = {ga.key for ga in it.applicable_actions(s)}
    assert "start(j=a,m=m1)" in applicable and "start(j=b,m=m1)" not in applicable  # b needs a
    s = it.apply(GroundAction("start", (("j", "a"), ("m", "m1"))), s)
    assert s["status[a]"] == "running" and s["on[a,m1]"] and s["left[a]"] == 2
    assert "start(j=b,m=m2)" not in {ga.key for ga in it.applicable_actions(s)}  # tool busy + dependency
    s = it.apply(GroundAction("tick", ()), s)
    assert s["left[a]"] == 1 and s["status[a]"] == "running"
    s = it.apply(GroundAction("tick", ()), s)
    assert s["status[a]"] == "done" and not s["on[a,m1]"] and s["clock"] == 2
    assert it.holds("b_after_a", s)


def test_bfs_shortest_witness_and_bounds():
    it = interp(two_jobs())
    goal = bfs(it, it.initial_state(), lambda s: it.holds("all_done", s), max_depth=10)
    assert goal.found and len(goal.path) - 1 == 5  # start a, tick, tick, start b, tick
    none = bfs(it, it.initial_state(), lambda s: it.holds("all_done", s), max_depth=4)
    assert not none.found and not none.truncated
    viol = bfs(it, it.initial_state(), lambda s: not it.holds("done_by_2", s), max_depth=6)
    assert viol.found and viol.path[-1][1]["clock"] >= 4  # ticking without starting a


def test_partial_state_applicability():
    it = interp(two_jobs())
    s = it.initial_state()
    start_a = GroundAction("start", (("j", "a"), ("m", "m1")))
    known = {k: val for k, val in s.items() if k != "status[a]"}
    verdict, n = it.applicability_with_unknowns(start_a, known, ["status[a]"])
    assert verdict == "UNKNOWN" and n >= 2  # waiting → applicable, running/done → not
    known2 = {k: val for k, val in s.items() if k != "on[b,m2]"}
    assert it.applicability_with_unknowns(start_a, known2, ["on[b,m2]"])[0] == "APPLICABLE"
    known3 = {**s, "status[a]": "done"}
    del known3["on[b,m2]"]
    assert it.applicability_with_unknowns(start_a, known3, ["on[b,m2]"])[0] == "INAPPLICABLE"


# ----------------------------------------------------------------------------- frontend / digest


def test_frontend_compiles_and_digest_is_canonical():
    fe = IRJsonFrontend()
    data = lamp().model_dump(mode="json")
    text_a = json.dumps(data)
    text_b = json.dumps(dict(reversed(list(data.items()))), indent=4)  # different key order / whitespace
    pa = fe.compile(ModelSource(format="fal-ir-json/v1", text=text_a), package_id="lamp", version=1)
    pb = fe.compile(ModelSource(format="fal-ir-json/v1", text=text_b), package_id="lamp", version=2)
    assert pa.digest == pb.digest == ir_digest(lamp())
    changed = _with(lamp(), lambda d: d["state"][1]["type"].__setitem__("max", 4))
    assert ir_digest(changed) != pa.digest
    assert canonical_ir(lamp())["actions"][0]["cost"] == 1  # defaults are explicit in the normal form


def test_frontend_errors():
    fe = IRJsonFrontend()
    with pytest.raises(InvalidInput) as bad_json:
        fe.compile(ModelSource(format="fal-ir-json/v1", text="{not json"), package_id="x", version=1)
    assert "JSON" in bad_json.value.message
    with pytest.raises(InvalidInput) as schema:
        fe.compile(ModelSource(format="fal-ir-json/v1", text='{"name":"x"}'), package_id="x", version=1)
    assert schema.value.field_errors
    typed = _with(lamp(), lambda d: d["properties"][0].__setitem__("expr", v("toggles")))
    with pytest.raises(InvalidInput) as typing:
        fe.compile(ModelSource(format="fal-ir-json/v1", text=typed.model_dump_json()), package_id="x", version=1)
    assert any("TYPE_MISMATCH" in fe_.message for fe_ in typing.value.field_errors)
    prob = _with(lamp(), lambda d: d.__setitem__("features", ["probabilistic_effects"]))
    with pytest.raises(Unsupported):
        fe.compile(ModelSource(format="fal-ir-json/v1", text=prob.model_dump_json()), package_id="x", version=1)
    with pytest.raises(Unsupported):
        fe.compile(ModelSource(format="pddl", text="(define)"), package_id="x", version=1)


def test_action_specs_and_diff():
    specs = {s.action_type: s for s in action_specs(check_model(two_jobs()))}
    start = specs["start"]
    assert start.params_schema["properties"]["j"]["enum"] == ["a", "b"]
    assert any("status[j]" in line for line in start.expected_effects)
    changed = _with(two_jobs(), lambda d: d["constants"][0]["value"]["cells"][0].__setitem__("value", 3))
    changes = diff_models(two_jobs(), changed)
    assert [(ch.section, ch.name, ch.kind) for ch in changes] == [("constants", "duration", "changed")]


def test_effect_comparison():
    obs = Observation(run_id="r", actor_id="a", step=3, state_revision=3,
                      facts=[{"path": "x", "value": 2, "observed_at_step": 3},
                             {"path": "y", "value": 1, "observed_at_step": 1, "source": "DELAYED"}])
    pre = {"x": 1, "y": 0}
    match = compare_effects(expected_post={"x": 2, "y": 0}, pre_state=pre, observation=obs, written_paths=["x"],
                            expected_by="model:t@1")
    assert match.verdict == "MATCH"
    differ = compare_effects(expected_post={"x": 3, "y": 0}, pre_state=pre, observation=obs, written_paths=["x"],
                             expected_by="model:t@1")
    assert differ.verdict == "DIFFERENT" and differ.diffs[0].observed == 2
    unknown = compare_effects(expected_post={"x": 2, "y": 1}, pre_state=pre, observation=obs, written_paths=["x", "y"],
                              expected_by="model:t@1")
    assert unknown.verdict == "INSUFFICIENT_INFORMATION"
    assert {d.path: d.status for d in unknown.diffs} == {"x": "MATCH", "y": "UNKNOWN"}


def test_effect_evidence_levels_and_freshness():
    """P2-074: every compared field says what backs it — observed fresh, verified within a stated scope, or
    unknown (stale / missing); `expected` is always the model's prediction; stale fields never count as a match."""
    from formal_lab_contracts import Fact, Observation, UnknownItem
    from formal_lab_model.compare import compare_effects

    obs = Observation(run_id="r", actor_id="a", step=5, state_revision=3,
                      facts=[Fact(path="x", value=2, observed_at_step=5), Fact(path="y", value=1, observed_at_step=3,
                                                                                source="DELAYED")],
                      unknowns=[UnknownItem(path="z", reason="NOT_OBSERVABLE")])
    cmp = compare_effects(expected_post={"x": 2, "y": 2, "z": 7, "w": 4}, pre_state={"x": 1, "y": 1, "z": 0, "w": 0},
                          observation=obs, written_paths=["x", "y", "z", "w"], expected_by="model:m@1",
                          verified={"w": 5})
    by = {d.path: d for d in cmp.diffs}
    assert (by["x"].status, by["x"].evidence, by["x"].freshness) == ("MATCH", "observed", "FRESH")
    assert (by["y"].status, by["y"].evidence, by["y"].freshness, by["y"].observed) == ("UNKNOWN", "unknown", "STALE",
                                                                                        None)
    assert (by["z"].status, by["z"].freshness) == ("UNKNOWN", "MISSING")
    assert (by["w"].status, by["w"].evidence) == ("DIFFERENT", "verified-within-scope")
    assert cmp.verdict == "DIFFERENT" and cmp.evidence_counts == {"observed": 1, "unknown": 2,
                                                                  "verified-within-scope": 1}
    fresh_only = compare_effects(expected_post={"x": 2, "y": 2}, pre_state={"x": 1, "y": 1}, observation=obs,
                                 written_paths=["x", "y"], expected_by="model:m@1")
    assert fresh_only.verdict == "INSUFFICIENT_INFORMATION"  # a stale field is never a match
    assert compare_effects(expected_post=None, pre_state={}, observation=obs, written_paths=[],
                           expected_by="m").verdict == "INSUFFICIENT_INFORMATION"
