"""Several participants (P2-030 … P2-038): turn orders and cursors, per-participant views, goals, budgets and
usage, deterministic conflict arbitration, termination reasons, and resume in a fresh process."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest
from formal_lab_contracts import PluginRef, TurnPolicy, TurnRef
from formal_lab_example_scheduling.scenarios import model_package, two_dispatchers
from formal_lab_example_warehouse.scenarios import package as wh_package
from formal_lab_example_warehouse.scenarios import receiver_and_picker
from formal_lab_runtime import CycleScheduler, default_registry, make_manifest, run_local
from formal_lab_runtime.local_runner import LocalRunState

WH_EVALUATORS = [PluginRef(plugin_id="formal-lab.eval.generic", version="1.0.0"),
                 PluginRef(plugin_id="formal-lab.example.warehouse.scorer", version="1.0.0")]


@pytest.fixture(scope="module")
def reg():
    return default_registry()


def run(reg, scenario, package, run_id="run_m", **kw):
    m = make_manifest(run_id=run_id, project_id="p", scenario=scenario, package=package, registry=reg,
                      evaluators=kw.pop("evaluators", None), seed=scenario.seed)
    return run_local(m, package, reg, **kw)


def outcomes(res):
    return [(e.logical_step, e.actor_id, e.turn.round if e.turn else None, e.payload["outcome"]["action"],
             e.payload["outcome"]["status"], e.payload["outcome"].get("conflict"))
            for e in res.events if str(e.event_type) == "ACTION_OUTCOME"]


def test_round_robin_and_fixed_table_cursor():
    rr = CycleScheduler(TurnPolicy(), ["a", "b"])
    state, seen = rr.initial_state(), []
    for _ in range(5):
        turn = rr.next_turn(state)
        seen.append((turn.global_step, turn.round, turn.actor_id, turn.actor_step))
        state = rr.advance(state, turn, acted=True, progressed=True)
    assert seen == [(1, 1, "a", 1), (2, 1, "b", 1), (3, 2, "a", 2), (4, 2, "b", 2), (5, 3, "a", 3)]
    table = CycleScheduler(TurnPolicy(mode="FIXED_TABLE", table=["a", "a", "b"]), ["a", "b"])
    state, seen = table.initial_state(), []
    for _ in range(6):
        turn = table.next_turn(state)
        seen.append((turn.actor_id, turn.round))
        state = table.advance(state, turn, acted=True, progressed=True)
    assert seen == [("a", 1), ("a", 1), ("b", 1), ("a", 2), ("a", 2), ("b", 2)]
    # a retired actor's slots are passed over without consuming a global step; the cursor survives JSON
    state = table.retire(state, "a")
    turn = table.next_turn(type(state).model_validate_json(state.model_dump_json()))
    assert turn.actor_id == "b" and turn.global_step == 7
    assert table.next_turn(table.retire(state, "b")) is None
    assert TurnRef.model_validate(turn.model_dump()).round == 3


def test_two_dispatchers_take_turns_with_own_usage(reg):
    pkg = model_package()
    res = run(reg, two_dispatchers(pkg, seed=1), pkg)
    rows = outcomes(res)
    assert res.status == "SUCCEEDED" and str(res.termination_reason) == "JOINT_GOAL_REACHED"
    assert [r[1] for r in rows[:4]] == ["dispatcher_a", "dispatcher_b", "dispatcher_a", "dispatcher_b"]
    assert [r[2] for r in rows[:4]] == [1, 1, 2, 2]
    usage = res.actor_usage
    assert usage["dispatcher_a"]["steps"] + usage["dispatcher_b"]["steps"] == res.usage.steps
    turns = [e.turn for e in res.events if str(e.event_type) == "TURN_STARTED"]
    assert all(t.actor_step == sum(1 for u in turns[:i + 1] if u.actor_id == t.actor_id)
               for i, t in enumerate(turns))
    # event keys, proposal and operation ids carry the actor (P2-034)
    props = [e for e in res.events if str(e.event_type) == "ACTION_PROPOSED"]
    assert all(f":{e.actor_id}:proposal" in e.payload["proposal"]["proposal_id"] for e in props)
    assert all(f":{e.actor_id}:" in (e.idempotency_key or "") for e in props)


@pytest.mark.parametrize("config", ["rule+rule", "rule+symbolic",
                                    pytest.param("model+symbolic", marks=pytest.mark.llm)])
def test_delivered_two_participant_configurations(reg, config):
    """P2-039: rule+rule and rule+symbolic always run; model+symbolic runs when a model endpoint is configured
    (otherwise NOT_RUN with that reason — never a stub in its place)."""
    from formal_lab_example_scheduling.scenarios import TWO_DISPATCHER_CONFIGS
    from formal_lab_runtime.settings import llm_configured

    pair = TWO_DISPATCHER_CONFIGS[config]
    if "llm" in pair and not llm_configured():
        pytest.skip("FAL_LLM_API_KEY not configured (NOT_RUN)")
    pkg = model_package()
    res = run(reg, two_dispatchers(pkg, seed=2, strategies=pair), pkg, f"run_cfg_{config.replace('+', '_')}")
    assert res.status == "SUCCEEDED" and str(res.termination_reason) == "JOINT_GOAL_REACHED"
    kinds = {e.actor_id: e.payload["proposal"]["source"]["kind"] for e in res.events
             if str(e.event_type) == "ACTION_PROPOSED"}
    expect = {"rule": "RULE", "z3": "SYMBOLIC", "llm": "LLM"}
    assert kinds == {"dispatcher_a": expect[pair[0]], "dispatcher_b": expect[pair[1]]}
    assert set(res.actor_usage) == {"dispatcher_a", "dispatcher_b"}
    if "llm" in pair:
        assert res.actor_usage["dispatcher_a"]["model_calls"] > 0 and res.actor_usage["dispatcher_b"]["model_calls"] == 0


@pytest.mark.parametrize("policy", ["REVALIDATE", "REJECT_STALE"])
def test_two_dispatchers_wanting_the_same_machine_is_arbitrated_deterministically(reg, policy):
    """Round-start observations: dispatcher B proposes on the state before A's action and asks for the machine and
    operation A just took. The environment rejects B's action with ConflictInfo (which locations changed since B's
    revision, by whom); the outcome is identical on every run."""
    pkg = model_package()
    sc = two_dispatchers(pkg, seed=1, timing="ROUND_START", conflict_policy=policy)
    first, second = run(reg, sc, pkg, "run_c1"), run(reg, sc, pkg, "run_c2")
    a1, b1 = outcomes(first)[0], outcomes(first)[1]
    assert a1[1] == "dispatcher_a" and a1[4] == "APPLIED"
    assert b1[1] == "dispatcher_b" and b1[4] == "REJECTED" and b1[3] == a1[3]  # the very same assignment
    conflict = b1[5]
    assert conflict["policy"] == policy and conflict["based_on_revision"] == 0 and conflict["current_revision"] == 1
    assert conflict["changed_paths"] and "dispatcher_a" in conflict["reason"]
    assert [(o[1], o[3], o[4]) for o in outcomes(first)] == [(o[1], o[3], o[4]) for o in outcomes(second)]
    assert first.status == "SUCCEEDED"
    turn_start = run(reg, two_dispatchers(pkg, seed=1, timing="TURN_START", conflict_policy=policy), pkg, "run_c3")
    assert not any(o[5] for o in outcomes(turn_start))  # fresh observations: no stale proposals


def test_per_participant_views_goals_scopes_and_budgets(reg):
    pkg = wh_package()
    sc = receiver_and_picker(pkg, env={"observation": {"per_actor": {"picker": {"delay_steps": {"dock": 2}}}}})
    res = run(reg, sc, pkg, evaluators=WH_EVALUATORS)
    assert res.status == "SUCCEEDED"
    obs = [e for e in res.events if str(e.event_type) == "OBSERVATION" and e.logical_step]
    by_actor = {}
    for e in obs:
        by_actor.setdefault(e.actor_id, e.payload["observation"])
    assert not any(u["path"].startswith("dock[") for u in by_actor["receiver"]["unknowns"])
    assert any(u["path"].startswith("dock[") for u in by_actor["picker"]["unknowns"])  # own delayed view
    acts = {(o[1], o[3]["action_type"]) for o in outcomes(res)}
    assert {a for who, a in acts if who == "receiver"} <= {"putaway", "tick"}  # scopes respected
    assert {a for who, a in acts if who == "picker"} <= {"assign", "release", "pick", "tick"}
    cands = [e for e in res.events if str(e.event_type) == "CANDIDATES" and e.actor_id == "receiver"]
    assert all(c["action"]["action_type"] in ("putaway", "tick") for c in cands[0].payload["candidates"])
    assert res.carry["turn"]["goals_reached"] == ["receiver"]  # the receiver's own goal (docks clear)
    assert res.actor_usage["receiver"]["steps"] <= 30  # participant budget


def _variant(scenario, **changes):
    """A scenario with changed fields, re-validated (so enums and nested objects are real contract values)."""
    from formal_lab_contracts import ScenarioManifest

    data = scenario.model_dump(mode="json")
    for key, value in changes.items():
        data[key] = value
    return ScenarioManifest.model_validate(data)


def test_termination_reasons(reg):
    pkg = wh_package()
    base = receiver_and_picker(pkg)
    term = base.termination.model_dump(mode="json")
    res = run(reg, _variant(base, termination={**term, "joint_goal": None, "actor_goals": "ANY"}), pkg, "run_any")
    assert str(res.termination_reason) == "ACTOR_GOAL_REACHED" and res.status == "SUCCEEDED"
    parts = [p.model_dump(mode="json") for p in base.participants]
    tight = _variant(base, participants=[{**p, "budget": {"max_steps": 2}} for p in parts])
    res = run(reg, tight, pkg, "run_budget")
    assert str(res.termination_reason) == "ACTOR_BUDGETS_EXHAUSTED" and res.status == "BUDGET_EXHAUSTED"
    assert sum(1 for e in res.events if str(e.event_type) == "TURN_SKIPPED" and e.payload["retired"]) == 2
    stuck = _variant(base, participants=[{**parts[0], "scope": {"action_types": ["tick"], "params": {}}},
                                         {**parts[1], "scope": {"action_types": ["release"], "params": {}}}],
                     termination={**term, "no_progress_limit": 3})
    res = run(reg, stuck, pkg, "run_stuck")
    assert str(res.termination_reason) in ("NO_PROGRESS", "BUDGET_EXHAUSTED") and res.status != "SUCCEEDED"
    skipped = [e for e in res.events if str(e.event_type) == "TURN_SKIPPED" and not e.payload["retired"]]
    assert skipped and skipped[0].actor_id == "picker"  # nothing to release: the picker passes (SKIP_ACTOR)
    fail = _variant(stuck, termination={**stuck.termination.model_dump(mode="json"), "on_no_action": "FAIL"})
    res = run(reg, fail, pkg, "run_fail")
    assert str(res.termination_reason) == "NO_APPLICABLE_ACTION" and res.status == "FAILED"


RESUME = """
import json, sys
from formal_lab_example_scheduling.scenarios import model_package
from formal_lab_runtime import resume_local
res = resume_local(json.load(open(sys.argv[1])), model_package())
print(json.dumps({"status": res.status.value, "turn": res.carry["turn"], "usage": res.actor_usage,
                  "rows": [(e.logical_step, e.actor_id, e.payload["outcome"]["action"], e.payload["outcome"]["status"])
                           for e in res.events if str(e.event_type) == "ACTION_OUTCOME"]}))
"""


def test_multi_actor_resume_in_a_fresh_process(reg, tmp_path):
    """Turn cursor, round-start observations, per-actor usage and conflict history survive a process boundary."""
    pkg = model_package()
    sc = two_dispatchers(pkg, seed=2, timing="ROUND_START", conflict_policy="REJECT_STALE", strategies=("rule", "z3"))
    full = run(reg, sc, pkg, "run_mr")
    part = run(reg, sc, pkg, "run_mr", stop_after=7)
    assert isinstance(part, LocalRunState) and part.carry.round_observations
    path = tmp_path / "state.json"
    path.write_text(json.dumps(part.to_json()))
    out = subprocess.run([sys.executable, "-c", RESUME, str(path)], capture_output=True, text=True, check=True,
                         cwd=tmp_path).stdout.strip().splitlines()[-1]
    resumed = json.loads(out)
    expect = [(o[0], o[1], o[3], o[4]) for o in outcomes(full)]
    assert [tuple(r) for r in resumed["rows"]] == json.loads(json.dumps(expect), object_hook=None) or \
        resumed["rows"] == json.loads(json.dumps(expect))
    assert resumed["turn"] == full.carry["turn"] and resumed["usage"] == full.actor_usage
