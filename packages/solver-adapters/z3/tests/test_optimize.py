"""Cost optimisation, robustness and observation requests (P2-021 … P2-027), checked against the exhaustive
reference (formal_lab_model.objectives.optimal_by_search) and the reference interpreter."""

from __future__ import annotations

import random

import pytest
from formal_lab_contracts import CheckQuery, ModelIR, ModelSource, ObjectiveSpec
from formal_lab_model import Interpreter, build_package, check_model
from formal_lab_model.objectives import optimal_by_search, path_values, resolve_levels
from formal_lab_model.samples import lamp, queue_costs, random_model, shortcut
from formal_lab_solver_z3.verifier import Z3Verifier

V = Z3Verifier()
OPTIMAL_SEEN: dict[str, int] = {}


def pkg(ir: ModelIR):
    return build_package(ir, package_id=ir.name, version=1, source=ModelSource(format="fal-ir-json/v1"))


def optimize(ir: ModelIR, objective: dict, timeout_ms: int = 30_000, state=None):
    spec = ObjectiveSpec.model_validate(objective)
    query = CheckQuery(kind="OPTIMIZE_OBJECTIVE", objective=spec, bound={"max_steps": spec.horizon,
                                                                        "timeout_ms": timeout_ms},
                       initial_state="GIVEN_STATE" if state else "MODEL_INITIAL")
    return V.check(pkg(ir), query, state=state), spec


def reference(ir: ModelIR, spec: ObjectiveSpec, state=None):
    checked = check_model(ir)
    it = Interpreter(checked)
    return optimal_by_search(it, resolve_levels(spec, checked), state or it.initial_state(), spec.goal_property,
                             spec.horizon)


def test_shorter_but_more_expensive_plan_is_not_chosen():
    """The shortest plan (express, 1 step, fare 10) is not the cheapest (walk ×3, fare 3): the optimiser takes the
    longer, cheaper plan and proves no cheaper plan exists within the horizon; shortest-path search does not."""
    ir = shortcut()
    shortest = V.check(pkg(ir), CheckQuery(kind="GOAL_REACHABILITY", property_id="arrived",
                                           bound={"max_steps": 4, "timeout_ms": 20_000}))
    assert [s.action.action_type for s in shortest.witness.steps[1:]] == ["express"]
    res, spec = optimize(ir, {"objective_id": "cheap", "goal_property": "arrived", "horizon": 4,
                              "levels": [{"id": "fare", "model_objective": "fare"}]})
    assert res.verdict == "OPTIMAL" and res.semantics == "OPTIMAL_PATH"
    assert [s.action.action_type for s in res.witness.steps[1:]] == ["walk", "walk", "walk"]
    assert res.witness.replay == "CONFIRMED"
    level = res.optimization.levels[0]
    assert level.value == 3 and level.optimal and level.proven_lower == 3 and res.optimization.plan_length == 3
    ref = reference(ir, spec)
    assert ref["values"] == {"fare": 3} and ref["length"] == 3


def test_lexicographic_levels_and_maximize():
    ir = shortcut()
    res, _ = optimize(ir, {"objective_id": "few_rides", "goal_property": "arrived", "horizon": 4, "levels": [
        {"id": "rides", "model_objective": "rides_taken"}, {"id": "fare", "model_objective": "fare"}]})
    assert res.verdict == "OPTIMAL"
    assert {lv.level: lv.value for lv in res.optimization.levels} == {"rides": 0, "fare": 3}
    most, spec2 = optimize(ir, {"objective_id": "joyride", "goal_property": "arrived", "horizon": 4, "levels": [
        {"id": "rides", "model_objective": "rides_taken", "direction": "maximize"},
        {"id": "fare", "model_objective": "fare"}]})
    assert {lv.level: lv.value for lv in most.optimization.levels} == {"rides": 1, "fare": 10}
    assert reference(ir, spec2)["values"] == {"rides": 1, "fare": 10}


def test_state_rate_and_extremum_costs_match_reference():
    ir = queue_costs()
    res, spec = optimize(ir, {"objective_id": "wait", "goal_property": "all_served", "horizon": 3, "levels": [
        {"id": "waiting", "model_objective": "waiting"}, {"id": "latest", "model_objective": "latest_weight"}]})
    assert res.verdict == "OPTIMAL" and res.witness.replay == "CONFIRMED"
    order = [s.action.params["j"] for s in res.witness.steps[1:]]
    assert order == ["b", "c", "a"]  # heaviest first
    ref = reference(ir, spec)
    assert {lv.level: lv.value for lv in res.optimization.levels} == ref["values"] == {"waiting": 5, "latest": 5}


def test_no_plan_within_horizon_is_a_bounded_conclusion():
    res, _ = optimize(shortcut(), {"objective_id": "x", "goal_property": "arrived", "horizon": 1,
                                   "levels": [{"id": "rides", "model_objective": "rides_taken",
                                               "direction": "maximize"}]}, state={"pos": 1, "rides": 0})
    assert res.verdict == "NO_PLAN_WITHIN_HORIZON" and res.witness is None


def _with_costs(ir: ModelIR, seed: int) -> tuple[ModelIR, list[str]]:
    """Random action costs, two objectives and goal targets that are false initially (conjunctions of
    location = value atoms), so optimal plans of various lengths and unreachable goals both occur."""
    rng = random.Random(seed)
    it = Interpreter(check_model(ir))
    init = it.initial_state()
    data = ir.model_dump(mode="json")
    for a in data["actions"]:
        a["cost"] = rng.randint(0, 4)
    atoms = []
    for path in sorted(init):
        name, _, rest = path.partition("[")
        index = [{"op": "const", "value": m} for m in rest.rstrip("]").split(",")] if rest else []
        for value in it.model.param_domain(it.model.families[name].ty):
            if init[path] != value:
                atoms.append({"op": "eq", "args": [{"op": "var", "name": name, "index": index},
                                                     {"op": "const", "value": value}]})
    goals = []
    for i in range(4):
        picked = rng.sample(atoms, rng.choice([1, 1, 2]))
        expr = picked[0] if len(picked) == 1 else {"op": "and", "args": picked}
        data["properties"].append({"id": f"g{i}", "kind": "goal", "expr": expr})
        goals.append(f"g{i}")
    data["objectives"] = [
        {"id": "effort", "terms": [{"kind": "action_cost"}]},
        {"id": "pressure", "terms": [{"kind": "state_rate", "expr": {"op": "var", "name": "x", "index": []}},
                                     {"kind": "terminal", "weight": 2,
                                      "expr": {"op": "var", "name": "y", "index": []}}]},
    ]
    return ModelIR.model_validate(data), goals


@pytest.mark.parametrize("seed", range(0, 60, 3))
def test_differential_optimum_against_exhaustive_reference(seed):
    ir, goals = _with_costs(random_model(seed), seed)
    for goal in goals:
        for levels in ([{"id": "effort", "model_objective": "effort"}],
                       [{"id": "pressure", "model_objective": "pressure"},
                        {"id": "effort", "model_objective": "effort"}]):
            res, spec = optimize(ir, {"objective_id": "o", "goal_property": goal, "horizon": 4, "levels": levels})
            ref = reference(ir, spec)
            key = f"{seed}:{goal}:{len(levels)}"
            if ref is None:
                assert res.verdict == "NO_PLAN_WITHIN_HORIZON", (key, res.explanation)
                OPTIMAL_SEEN[key] = -1
                continue
            assert res.verdict == "OPTIMAL", (key, res.explanation)
            assert {lv.level: lv.value for lv in res.optimization.levels} == ref["values"], key
            assert res.optimization.plan_length == ref["length"], key
            assert res.witness.replay == "CONFIRMED", res.witness.replay_note
            OPTIMAL_SEEN[key] = ref["length"]


def test_differential_optimum_suite_is_discriminating():
    if len(OPTIMAL_SEEN) < 150:
        pytest.skip("run together with test_differential_optimum_against_exhaustive_reference")
    lengths = list(OPTIMAL_SEEN.values())
    assert sum(n >= 2 for n in lengths) >= 20, sorted(lengths)
    assert sum(n >= 3 for n in lengths) >= 5, sorted(lengths)
    assert sum(n == -1 for n in lengths) >= 10, sorted(lengths)


def test_timeout_gives_feasible_with_proven_interval_or_unknown():
    from formal_lab_example_scheduling.model import build_model

    ir = build_model(with_objectives=True)
    res, _ = optimize(ir, {"objective_id": "delay", "goal_property": "all_done", "horizon": 18,
                           "levels": [{"id": "delay", "model_objective": "delay_cost"}]}, timeout_ms=1500)
    assert res.verdict in ("FEASIBLE", "OPTIMAL", "UNKNOWN")
    if res.verdict == "FEASIBLE":
        lv = res.optimization.levels[0]
        assert not lv.optimal and lv.value is not None and res.witness.replay == "CONFIRMED"
        assert lv.proven_lower is None or lv.proven_lower <= lv.value
    if res.verdict == "UNKNOWN":
        assert res.witness is None


def test_robust_sequence_over_unknown_completions():
    ir = lamp()
    seq = [{"action_type": "toggle", "params": {}}, {"action_type": "toggle", "params": {}}]
    query = CheckQuery(kind="ROBUST_SEQUENCE", sequence=seq, bound={"max_steps": 2, "timeout_ms": 10_000},
                       initial_state="GIVEN_STATE")
    free = V.check(pkg(ir), query, state={"on": False, "toggles": 0}, unknown_paths=["toggles"])
    assert free.verdict == "NOT_ROBUST" and free.robustness.counterexample["toggles"] >= 2
    assert free.robustness.failing_index in (0, 1)
    it = Interpreter(check_model(ir))
    start = {"on": False, **free.robustness.counterexample}
    _, failed = it.replay(start, [it.ground("toggle", {})] * 2)
    assert failed == free.robustness.failing_index  # the counterexample really breaks the sequence
    known = V.check(pkg(ir), query, state={"on": False, "toggles": 0})
    assert known.verdict == "ROBUST"
    lit = V.check(pkg(ir), query.model_copy(update={"property_id": "lit"}), state={"on": False, "toggles": 0})
    assert lit.verdict == "NOT_ROBUST" and lit.robustness.goal_fails  # two toggles leave the lamp off


def test_unknown_precondition_carries_completions_and_observation_request():
    ir = lamp()
    res = V.check(pkg(ir), CheckQuery(kind="ACTION_PRECONDITION", action={"action_type": "reset", "params": {}},
                                      bound={"max_steps": 0}, initial_state="GIVEN_STATE"),
                  state={"on": True, "toggles": 0}, unknown_paths=["toggles", "on"])
    assert res.verdict == "UNKNOWN"
    req = res.observation_request
    assert req is not None and req.paths == ["toggles"]  # `on` is not read by reset's precondition
    assert req.applicable_completion["toggles"] > 0 and req.inapplicable_completion["toggles"] == 0
    it = Interpreter(check_model(ir))
    assert path_values  # (imported for the reference API)
    assert it.step(it.ground("reset", {}), {"on": True, "toggles": req.applicable_completion["toggles"]}).applicable


def test_non_ir_package_is_unsupported():
    from formal_lab_contracts import ModelPackage, digest_of

    data = {"zones": []}
    package = ModelPackage(package_id="w", version=1, frontend={"plugin_id": "x", "version": "1.0.0"},
                           semantic_profile="warehouse_alloc_v1",
                           digest=digest_of({"namespace": "org.x.w", "schema_id": "w@1", "data": data}),
                           payload={"kind": "namespaced", "namespace": "org.x.w", "schema_id": "w@1", "data": data},
                           source={"format": "w"}, created_at="2026-09-27T00:00:00Z")
    res = V.check(package, CheckQuery(kind="GOAL_REACHABILITY", property_id="g", bound={"max_steps": 3}))
    assert res.verdict == "UNSUPPORTED" and "neutral IR" in res.unsupported.reason


def test_extremum_quantifiers_agree_with_the_interpreter():
    """max_over / min_over (with `where` and `default`) mean the same in the interpreter and the Z3 encoding:
    reachability of every possible extremum value equals exhaustive BFS."""
    from formal_lab_model import bfs

    base = queue_costs().model_dump(mode="json")
    served = {"op": "var", "name": "served", "index": [{"op": "ref", "name": "x"}]}
    weight = {"op": "var", "name": "weight", "index": [{"op": "ref", "name": "x"}]}
    for op, default in (("max_over", -1), ("min_over", 99)):
        ext = {"op": op, "var": "x", "domain": "jobs", "where": served, "body": weight,
               "default": {"op": "const", "value": default}}
        data = dict(base)
        data["properties"] = [{"id": f"is_{i}", "kind": "goal",
                               "expr": {"op": "eq", "args": [ext, {"op": "const", "value": v}]}}
                              for i, v in enumerate((default, 1, 3, 5))]
        ir = ModelIR.model_validate(data)
        it = Interpreter(check_model(ir))
        for prop in [p["id"] for p in data["properties"]]:
            ref = bfs(it, it.initial_state(), lambda s, p=prop, it=it: it.holds(p, s), max_depth=3)
            res = V.check(pkg(ir), CheckQuery(kind="GOAL_REACHABILITY", property_id=prop,
                                              bound={"max_steps": 3, "timeout_ms": 10_000}))
            assert (res.verdict == "WITNESS") == ref.found, (op, prop)
            if ref.found:
                assert len(res.witness.steps) == len(ref.path) and res.witness.replay == "CONFIRMED"
