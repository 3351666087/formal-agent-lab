"""Run-kernel behaviour: phase-1 parity, resume equivalence in a fresh process, planner cache boundaries and plan
revisions (P2-011 / P2-028 / P2-041 / P2-042 / P2-046)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from formal_lab_contracts.bundle import read_bundle
from formal_lab_example_scheduling.scenarios import STRATEGIES, model_package, scenario
from formal_lab_runtime import default_registry, make_manifest, resume_local, run_local
from formal_lab_runtime.local_runner import LocalRunState

ROOT = Path(__file__).resolve().parents[3]
PHASE1 = ROOT / "tests" / "compat" / "fixtures" / "phase1"


@pytest.fixture(scope="module")
def reg():
    return default_registry()


@pytest.fixture(scope="module")
def pkg():
    return model_package()


def manifest(reg, pkg, key: str, strategy: str, seed: int, run_id: str = "run_k"):
    sc = scenario(key, pkg, seed=seed, strategy=STRATEGIES[strategy])
    return make_manifest(run_id=run_id, project_id="p", scenario=sc, package=pkg, registry=reg, seed=seed)


def actions(events) -> list[tuple]:
    out = []
    for e in events:
        if str(e.event_type) == "ACTION_OUTCOME":
            o = e.payload["outcome"]
            out.append((e.logical_step, o["action"]["action_type"], tuple(sorted(o["action"]["params"].items())),
                        o["status"]))
    return out


def test_single_participant_run_reproduces_the_phase1_trajectory(reg, pkg):
    """Same model, scenario, seed and rule strategy: every action and outcome equals the phase-1 bundle."""
    old = read_bundle(PHASE1 / "normal.replay.zip")
    assert old.info["upgraded_from"] == "formal-lab/replay-bundle@1"
    res = run_local(manifest(reg, pkg, "normal", "rule", 1), pkg, reg)
    assert res.status == "SUCCEEDED" and res.usage.steps == old.manifest.budget_usage.steps
    assert actions(res.events) == actions(old.events)
    assert {m.metric_id: m.value for m in res.metrics if m.metric_id != "wall_seconds"} == \
        {m.metric_id: m.value for m in old.metrics if m.metric_id != "wall_seconds"}


RESUME = """
import json, sys
from formal_lab_example_scheduling.scenarios import model_package
from formal_lab_runtime import resume_local
state = json.load(open(sys.argv[1]))
res = resume_local(state, model_package())
out = [(e.logical_step, e.payload["outcome"]["action"], e.payload["outcome"]["status"]) for e in res.events
       if str(e.event_type) == "ACTION_OUTCOME"]
print(json.dumps({"status": res.status.value, "steps": res.usage.steps, "actions": out,
                  "carry_turn": res.carry["turn"], "metrics": {m.metric_id: m.value for m in res.metrics
                                                               if m.metric_id != "wall_seconds"}}))
"""


@pytest.mark.parametrize(("key", "strategy", "seed", "stop"), [("state-delay", "z3", 2, 7),
                                                              ("state-delay", "rule", 3, 11),
                                                              ("expectation-mismatch", "z3", 1, 5)])
def test_resume_in_a_fresh_process_equals_the_uninterrupted_run(reg, pkg, tmp_path, key, strategy, seed, stop):
    full = run_local(manifest(reg, pkg, key, strategy, seed), pkg, reg)
    part = run_local(manifest(reg, pkg, key, strategy, seed), pkg, reg, stop_after=stop)
    assert isinstance(part, LocalRunState) and part.next_step == stop + 1
    path = tmp_path / "state.json"
    path.write_text(json.dumps(part.to_json()))
    proc = subprocess.run([sys.executable, "-c", RESUME, str(path)], capture_output=True, text=True, check=True,
                          cwd=tmp_path)
    resumed = json.loads(proc.stdout.strip().splitlines()[-1])
    expect = [(e.logical_step, e.payload["outcome"]["action"], e.payload["outcome"]["status"]) for e in full.events
              if str(e.event_type) == "ACTION_OUTCOME"]
    assert resumed["actions"] == json.loads(json.dumps(expect))
    assert resumed["status"] == full.status.value and resumed["steps"] == full.usage.steps
    assert resumed["carry_turn"] == full.carry["turn"]
    assert resumed["metrics"] == {m.metric_id: m.value for m in full.metrics if m.metric_id != "wall_seconds"}


def test_resume_in_process_emits_recovery_event(reg, pkg):
    part = run_local(manifest(reg, pkg, "normal", "z3", 1), pkg, reg, stop_after=3)
    res = resume_local(part, pkg, reg)
    kinds = [str(e.event_type) for e in res.events]
    assert "RECOVERY" in kinds and res.status == "SUCCEEDED"
    seqs = [e.seq for e in res.events]
    assert seqs == list(range(1, len(seqs) + 1))


def test_planner_cache_key_covers_query_boundaries():
    from formal_lab_solver_z3.planner import CacheEntry, PlanCache, cache_key

    base = {"model": "m", "driver": "d", "mode": "shortest", "goal": "g", "objective": None, "horizon": 16,
            "state": "s", "assumptions": "a"}
    variants = [dict(base, horizon=12), dict(base, assumptions="b"), dict(base, mode="cost"),
                dict(base, objective={"x": 1}), dict(base, state="t"), dict(base, driver="other")]
    keys = {cache_key(**base)} | {cache_key(**v) for v in variants}
    assert len(keys) == 1 + len(variants)
    cache = PlanCache(capacity=2)
    cache.put("k1", CacheEntry(kind="plan"))
    cache.put("k2", CacheEntry(kind="none"))
    assert cache.get("k1").kind == "plan"  # k1 becomes most recent
    cache.put("k3", CacheEntry(kind="plan"))
    assert cache.get("k2") is None and cache.stats()["evictions"] == 1
    assert cache.get("k3").kind == "plan" and cache.get("k1").kind == "plan"


def test_plan_revisions_record_their_trigger(reg, pkg):
    """In the mismatch scenario the world deviates from the model: the Z3 plan is revised and every revision says
    why; plans made from last-known values are labelled assumption-based."""
    res = run_local(manifest(reg, pkg, "expectation-mismatch", "z3", 1), pkg, reg)
    plans = [e.payload["plan"] for e in res.events if str(e.event_type) == "PLAN_UPDATED"]
    assert plans[0]["version"] == 1 and plans[0]["revision"]["trigger"] == "INITIAL"
    triggers = {p["revision"]["trigger"] for p in plans[1:]}
    assert triggers and triggers <= {"EFFECT_DIFFERENCE", "NEW_OBSERVATION", "ACTION_REJECTED", "BUDGET"}
    assert all(p["version"] == i + 1 for i, p in enumerate(plans))
    delay = run_local(manifest(reg, pkg, "state-delay", "z3", 2, "run_d"), pkg, reg)
    bases = {e.payload["proposal"]["assumptions"]["basis"] for e in delay.events
             if str(e.event_type) == "ACTION_PROPOSED"}
    assert "ASSUMPTION_BASED" in bases


def test_cost_mode_planner_uses_the_objective(reg, pkg):
    """The cost-mode Z3 planner optimises the scenario objective (model v2 declares delay_cost / effort)."""
    from formal_lab_contracts import ModelSource
    from formal_lab_example_scheduling.model import build_model
    from formal_lab_model import build_package

    ir = build_model(with_objectives=True)
    pkg2 = build_package(ir, package_id="neutral-scheduling", version=2, source=ModelSource(format="fal-ir-json/v1"))
    sc = scenario("resource-shortage", pkg2, seed=1, strategy={
        "plugin": {"plugin_id": "formal-lab.planner.z3-bounded", "version": "1.1.0"},
        "config": {"mode": "cost", "horizon": 18, "timeout_ms": 60000}})
    from formal_lab_contracts import ObjectiveSpec

    sc = sc.model_copy(update={"objective": ObjectiveSpec.model_validate({
        "objective_id": "delay_then_effort", "goal_property": "all_done", "horizon": 18,
        "levels": [{"id": "delay", "model_objective": "delay_cost"}, {"id": "effort", "model_objective": "effort"}]})})
    m = make_manifest(run_id="run_cost", project_id="p", scenario=sc, package=pkg2, registry=reg, seed=1)
    res = run_local(m, pkg2, reg)
    assert res.status == "SUCCEEDED"
    plans = [e.payload["plan"] for e in res.events if str(e.event_type) == "PLAN_UPDATED"]
    assert plans and plans[0]["generator"]["method"] == "OPTIMIZE_OBJECTIVE"
    assert plans[0]["objective_value"] is not None


def test_observation_requests_settle_unknown_actions(reg, pkg):
    """State-delay with a planner that asks for observations when its next action is UNKNOWN: the environment
    answers on request (OBSERVE_MORE), the request is recorded, and fewer actions are rejected than without it."""
    def run(request: bool):
        strategy = {"plugin": {"plugin_id": "formal-lab.planner.z3-bounded", "version": "1.1.0"},
                    "config": {"horizon": 18, "request_observations": request,
                               "fallback_order": ["assign", "resume", "advance"]}}
        sc = scenario("state-delay", pkg, seed=2, strategy=strategy)
        m = make_manifest(run_id=f"run_req_{request}", project_id="p", scenario=sc, package=pkg, registry=reg, seed=2)
        return run_local(m, pkg, reg)

    plain, asking = run(False), run(True)
    requests = [e for e in asking.events if str(e.event_type) == "OBSERVATION_REQUESTED"]
    assert requests and all(e.payload["paths"] for e in requests)
    assert asking.status == "SUCCEEDED"
    rejected = lambda r: sum(1 for e in r.events if str(e.event_type) == "ACTION_OUTCOME"  # noqa: E731
                             and e.payload["outcome"]["status"] == "REJECTED")
    assert rejected(asking) < rejected(plain)


def test_query_bundle_records_inputs_and_replays(reg):
    from formal_lab_contracts import CheckQuery, ModelSource
    from formal_lab_model import build_package
    from formal_lab_model.samples import shortcut
    from formal_lab_runtime.query import replay_query, run_query

    package = build_package(shortcut(), package_id="shortcut", version=1, source=ModelSource(format="fal-ir-json/v1"))
    query = CheckQuery(kind="OPTIMIZE_OBJECTIVE", bound={"max_steps": 4, "timeout_ms": 20000},
                       objective={"objective_id": "cheap", "goal_property": "arrived", "horizon": 4,
                                  "levels": [{"id": "fare", "model_objective": "fare"}]})
    bundle = run_query(reg, package, query)
    assert bundle.result.verdict == "OPTIMAL" and bundle.replay["witness"] == "CONFIRMED"
    assert bundle.verifier.version == "1.1.0" and bundle.driver.plugin_id == "formal-lab.driver.ir-finite"
    assert any(line.startswith("objective level fare: value 3, optimal (proven)") for line in bundle.explanation)
    again = replay_query(reg, package, bundle)
    assert again["same"] and again["values_after"] == {"fare": 3}
