"""Z3 engine checks: verdicts, witness replay and differential comparison with the interpreter."""

from __future__ import annotations

import itertools

import pytest
from formal_lab_contracts import CheckQuery, ModelIR, ModelSource
from formal_lab_model import Interpreter, bfs, build_package, check_model
from formal_lab_model.samples import lamp, random_model, two_jobs
from formal_lab_solver_z3.verifier import Z3Verifier


def pkg(ir: ModelIR, version: int = 1):
    return build_package(ir, package_id=ir.name, version=version, source=ModelSource(format="fal-ir-json/v1"))


def q(kind: str, prop: str | None = None, k: int = 5, timeout_ms: int = 20_000, **kw):
    return CheckQuery(kind=kind, property_id=prop, bound={"max_steps": k, "timeout_ms": timeout_ms}, **kw)


V = Z3Verifier()


def test_goal_reachable_with_confirmed_shortest_witness():
    res = V.check(pkg(two_jobs()), q("GOAL_REACHABILITY", "all_done", 8))
    assert res.verdict == "WITNESS" and res.semantics == "EXISTS_PATH"
    assert len(res.witness.steps) - 1 == 5  # same shortest length as BFS
    assert res.witness.replay == "CONFIRMED"
    assert res.witness.steps[-1].state["status[b]"] == "done"


def test_goal_not_reachable_within_bound_is_bounded_conclusion():
    res = V.check(pkg(two_jobs()), q("GOAL_REACHABILITY", "all_done", 4))
    assert res.verdict == "NO_WITNESS_WITHIN_BOUND"
    assert res.bound.max_steps == 4 and "bounded" in res.explanation
    assert res.scope == "MODEL_INTERNAL"


def test_invariant_counterexample_and_holding_invariant():
    viol = V.check(pkg(two_jobs()), q("INVARIANT_VIOLATION", "done_by_2", 6))
    assert viol.verdict == "WITNESS" and viol.semantics == "ALL_PATHS"
    assert viol.witness.replay == "CONFIRMED"
    held = V.check(pkg(two_jobs()), q("INVARIANT_VIOLATION", "b_after_a", 7))
    assert held.verdict == "NO_WITNESS_WITHIN_BOUND"
    lamp_inv = V.check(pkg(lamp()), q("INVARIANT_VIOLATION", "few_toggles", 5))
    assert lamp_inv.verdict == "WITNESS" and len(lamp_inv.witness.steps) - 1 == 3
    guard = V.check(pkg(lamp()), q("INVARIANT_VIOLATION", "never_four", 8))
    assert guard.verdict == "NO_WITNESS_WITHIN_BOUND"  # the domain guard forbids toggles=4


def test_timeout_yields_unknown_with_reason():
    res = V.check(pkg(two_jobs()), q("GOAL_REACHABILITY", "all_done", 400, timeout_ms=1))
    assert res.verdict == "UNKNOWN"
    assert res.stats.reason_unknown == "timeout" and res.stats.steps_explored < 400


def test_unsupported_profile_feature():
    data = lamp().model_dump(mode="json")
    data["features"] = ["probabilistic_effects"]
    ir = ModelIR.model_validate(data)
    from datetime import UTC, datetime

    from formal_lab_contracts import ModelPackage
    from formal_lab_model import ir_digest

    package = ModelPackage(package_id="p", version=1, frontend={"plugin_id": "x", "version": "1.0.0"},
                           semantic_profile=ir.semantic_profile, digest=ir_digest(ir),
                           payload={"kind": "fal-ir", "ir": ir},
                           source={"format": "fal-ir-json/v1"}, created_at=datetime.now(UTC))
    res = V.check(package, q("GOAL_REACHABILITY", "lit", 3))
    assert res.verdict == "UNSUPPORTED" and res.unsupported.extension_point


def test_precondition_with_unknowns_matches_interpreter():
    package = pkg(two_jobs())
    it = Interpreter(check_model(two_jobs()))
    s = it.initial_state()
    act = {"action_type": "start", "params": {"j": "a", "m": "m1"}}
    cases = [
        ({}, [], "APPLICABLE"),
        ({}, ["status[a]"], "UNKNOWN"),
        ({"status[a]": "done"}, [], "INAPPLICABLE"),
        ({"status[a]": "done"}, ["on[b,m2]"], "INAPPLICABLE"),
        ({}, ["on[b,m2]", "left[b]"], "APPLICABLE"),
    ]
    for override, unknown, expected in cases:
        state = {**s, **override}
        res = V.check(package, q("ACTION_PRECONDITION", k=0, action=act), state=state, unknown_paths=unknown)
        known = {p: val for p, val in state.items() if p not in unknown}
        ref, _ = it.applicability_with_unknowns(it.ground("start", {"j": "a", "m": "m1"}), known, unknown)
        assert res.verdict == expected == ref, (override, unknown)


def _with_targets(ir: ModelIR, seed: int, n: int = 6) -> tuple[ModelIR, list[str]]:
    """Add goal properties (conjunctions of location = value atoms) that are false initially."""
    import random

    it = Interpreter(check_model(ir))
    init = it.initial_state()
    rng = random.Random(seed)
    atoms = []
    for path in sorted(init):
        name, _, rest = path.partition("[")
        index = [{"op": "const", "value": m} for m in rest.rstrip("]").split(",")] if rest else []
        fam = it.model.families[name]
        for value in it.model.param_domain(fam.ty):
            atoms.append(({"op": "eq", "args": [{"op": "var", "name": name, "index": index},
                                                  {"op": "const", "value": value}]}, init[path] == value))
    props, ids = [], []
    for i in range(200):
        picked = rng.sample(atoms, rng.choice([1, 2, 2, 3]))
        if all(holds for _, holds in picked):
            continue
        expr = picked[0][0] if len(picked) == 1 else {"op": "and", "args": [a for a, _ in picked]}
        props.append({"id": f"t{i}", "kind": "goal", "expr": expr})
        ids.append(f"t{i}")
        if len(ids) == n:
            break
    data = ir.model_dump(mode="json")
    data["properties"] += props
    return ModelIR.model_validate(data), ids


DEPTHS: dict[str, int] = {}


@pytest.mark.parametrize("seed", range(60))
def test_differential_random_models(seed):
    """Interpreter BFS and Z3 BMC agree on verdict and shortest witness length (k ≤ 5) for the model's own
    properties and for synthesized targets that are false in the initial state."""
    ir, targets = _with_targets(random_model(seed), seed)
    package = pkg(ir)
    it = Interpreter(check_model(ir))
    queries = [("GOAL_REACHABILITY", "goal"), ("INVARIANT_VIOLATION", "inv")] + [
        ("GOAL_REACHABILITY", t) for t in targets]
    for kind, prop in queries:
        target = (lambda s, p=prop: it.holds(p, s)) if kind == "GOAL_REACHABILITY" else (
            lambda s, p=prop: not it.holds(p, s))
        ref = bfs(it, it.initial_state(), target, max_depth=5)
        res = V.check(package, q(kind, prop, 5))
        assert not ref.truncated
        if ref.found:
            assert res.verdict == "WITNESS", (seed, kind, prop)
            assert len(res.witness.steps) == len(ref.path), (seed, kind, prop)
            assert res.witness.replay == "CONFIRMED", res.witness.replay_note
            DEPTHS[f"{seed}:{prop}"] = len(ref.path) - 1
        else:
            assert res.verdict == "NO_WITNESS_WITHIN_BOUND", (seed, kind, prop)
            DEPTHS[f"{seed}:{prop}"] = -1


def test_differential_suite_is_discriminating():
    """Guard against a vacuous differential test: it must exercise deep witnesses and bounded negatives."""
    if len(DEPTHS) < 300:
        pytest.skip("run together with test_differential_random_models")
    values = list(DEPTHS.values())
    assert sum(d >= 2 for d in values) >= 40, sorted(values)
    assert sum(d >= 3 for d in values) >= 10, sorted(values)
    assert sum(d == -1 for d in values) >= 40, sorted(values)


@pytest.mark.parametrize("seed", range(0, 60, 3))
def test_differential_single_step_on_reachable_states(seed):
    """For every reachable state (depth ≤ 2) and ground action, Z3 applicability equals the interpreter's."""
    from formal_lab_model import reachable_states

    ir = random_model(seed)
    package = pkg(ir)
    it = Interpreter(check_model(ir))
    for state, ga in itertools.product(reachable_states(it, it.initial_state(), 2)[:6], it.model.ground_actions):
        expected = "APPLICABLE" if it.step(ga, state).applicable else "INAPPLICABLE"
        res = V.check(package, q("ACTION_PRECONDITION", k=0,
                                 action={"action_type": ga.action, "params": dict(ga.params)}), state=state)
        assert res.verdict == expected, (seed, ga.key, state)


def test_concurrent_checks_do_not_share_z3_contexts():
    """Regression: Z3 contexts are not thread-safe; parallel activities / Inspect samples must not crash."""
    from concurrent.futures import ThreadPoolExecutor

    package = pkg(two_jobs())
    queries = [q("GOAL_REACHABILITY", "all_done", 8), q("INVARIANT_VIOLATION", "done_by_2", 6),
               q("GOAL_REACHABILITY", "all_done", 4)] * 6
    with ThreadPoolExecutor(max_workers=6) as pool:
        verdicts = list(pool.map(lambda query: str(V.check(package, query).verdict), queries))
    assert verdicts == ["WITNESS", "WITNESS", "NO_WITNESS_WITHIN_BOUND"] * 6
