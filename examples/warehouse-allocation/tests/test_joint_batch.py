"""JOINT_BATCH rounds and per-participant planner input on the warehouse example (phase 3A, G4)."""

from __future__ import annotations

import json
import time
from typing import Any

import pytest
from formal_lab_contracts import Budget, PlanningContext, TurnPolicy
from formal_lab_contracts.errors import Unsupported
from formal_lab_contracts.interfaces import PluginRegistration
from formal_lab_example_warehouse.model import demo_model
from formal_lab_example_warehouse.plugins import RULES, WarehouseRules, build_package
from formal_lab_example_warehouse.scenarios import JOINT, VIEWS, package, receiver_and_picker
from formal_lab_runtime import default_registry, make_manifest, resume_local, run_local

SPY = RULES.model_copy(update={
    "plugin_id": "test.warehouse.spy-rules",
    "config_schema": {"type": "object", "properties": {"role": {"type": "string"}, "sleep": {"type": "number"}},
                      "additionalProperties": False}})
SEEN: dict[str, list[dict[str, Any]]] = {}


class SpyRules(WarehouseRules):
    """The warehouse rules, recording what the planner receives (and optionally slow)."""

    def __init__(self, services: Any, config: dict[str, Any]):
        super().__init__(services.loaded_model(), {"role": config.get("role", "both")})
        self.sleep = float(config.get("sleep", 0))
        self.actor = services.actor_id
        self.style = services.get_setting("style")

    def propose(self, context: PlanningContext):
        SEEN.setdefault(self.actor, []).append({
            "paths": sorted({f.path for f in context.observation.facts} | {u.path for u in context.observation.unknowns}),
            "style": self.style, "last_diffs": [d.path for d in (context.last_outcome.effect_comparison.diffs
                                                                 if context.last_outcome is not None
                                                                 and context.last_outcome.effect_comparison else [])]})
        if self.sleep:
            time.sleep(self.sleep)
        return super().propose(context)


def registry():
    reg = default_registry()
    reg.register(PluginRegistration(SPY, lambda config, services: SpyRules(services, dict(config or {}))))
    return reg


def scenario(*, views=None, spy: dict[str, dict] | None = None, turns=None, **kw):
    pkg = package()
    sc = receiver_and_picker(pkg, turns=turns or JOINT, views=views, **kw)
    if spy:
        parts = [p.model_copy(update={"strategy": p.strategy.model_copy(update={
            "plugin": SPY.ref(), "config": {**p.strategy.config, **spy.get(p.actor_id, {})}})})
                 for p in sc.participants]
        sc = sc.model_copy(update={"participants": parts})
    return pkg, sc


def run(pkg, sc, reg, run_id="run_g4", **kw):
    m = make_manifest(run_id=run_id, project_id="wh", scenario=sc, package=pkg, registry=reg, seed=1)
    return m, run_local(m, pkg, reg, **kw)


def events(res, kind):
    return [e for e in res.events if str(e.event_type) == kind]


def signature(res):
    return [(s.step, s.actor_id, s.proposal.action.model_dump_json() if s.proposal else None,
             s.outcome.status.value if s.outcome else None, s.turn.env_step if s.turn else None) for s in res.steps]


def test_policy_needs_round_start_observations():
    with pytest.raises(ValueError, match="ROUND_START"):
        TurnPolicy(mode="JOINT_BATCH")
    with pytest.raises(ValueError, match="only used with JOINT_BATCH"):
        TurnPolicy(batch_timeout_s=2)


def test_one_environment_step_per_round_and_joint_comparison():
    reg = registry()
    pkg, sc = scenario()
    _, res = run(pkg, sc, reg)
    assert res.status.value == "SUCCEEDED"
    submitted = [e.payload["batch"] for e in events(res, "BATCH_SUBMITTED")]
    assert len(submitted) == len(events(res, "BATCH_OPENED")) == len(res.steps) // 2
    for b in submitted:  # two members, two global steps, one environment step (= the round)
        assert [x["status"] for x in b["members"]] == ["PROPOSED", "PROPOSED"]
        assert b["env_step"] == b["round"] and b["submitted_at_step"] == 2 * b["round"]
        assert b["semantics"] == "START_STATE_DISJOINT_WRITES" and b["joint_prediction"] is True
    for s in res.steps:  # every member's outcome sits on its own proposal step
        assert s.outcome is not None and s.turn.batch_id == f"run_g4:b{s.turn.round}"
        assert s.turn.env_step == s.turn.round and s.outcome.revision_before == s.proposal.based_on_revision
    verdicts = {e.payload["comparison"]["verdict"] for e in events(res, "EFFECT_COMPARED")}
    assert verdicts == {"MATCH"}  # the joint prediction foresees write conflicts inside a batch
    conflicts = [s for s in res.steps if s.outcome.conflict is not None]
    assert conflicts and all("batch write conflict" in s.outcome.conflict.reason for s in conflicts)
    assert all(s.actor_id == "picker" for s in conflicts)  # the later member of the round loses the location


def test_restart_mid_round_continues_the_batch():
    reg = registry()
    pkg, sc = scenario(views=VIEWS, spy={"receiver": {}, "picker": {}})
    SEEN.clear()
    m, full = run(pkg, sc, reg)
    uninterrupted = json.loads(json.dumps(SEEN))
    SEEN.clear()
    part = run_local(m, pkg, reg, stop_after=5)  # receiver proposed in round 3; picker not yet
    state = json.loads(json.dumps(part.to_json()))
    batch = state["carry"]["batch"]["record"]
    assert batch["status"] == "OPEN" and [x["actor_id"] for x in batch["members"]] == ["receiver"]
    assert state["snapshot"]["step"] == 2  # nothing of round 3 reached the environment
    resumed = resume_local(state, pkg, registry())  # fresh plugins, state from JSON only
    assert signature(resumed) == signature(full)
    assert json.loads(json.dumps(SEEN)) == uninterrupted  # the same input for every planner, before and after
    digest = lambda r: [e.payload.get("planner_input_digest") for e in events(r, "ACTION_PROPOSED")]  # noqa: E731
    assert digest(resumed) == digest(full) and all(digest(full))


def test_each_participant_receives_its_own_fields():
    reg = registry()
    views = {"receiver": {**VIEWS["receiver"], "settings": {"style": "careful"}}, "picker": VIEWS["picker"]}
    pkg, sc = scenario(views=views, spy={"receiver": {}, "picker": {}})
    SEEN.clear()
    _, res = run(pkg, sc, reg)
    assert res.status.value == "SUCCEEDED"
    families = {a: {p.split("[", 1)[0] for call in calls for p in call["paths"]} for a, calls in SEEN.items()}
    assert families["receiver"] == {"clock", "dock", "stock"}
    assert "dock" not in families["picker"] and {"serves", "picked", "stock"} <= families["picker"]
    assert {c["style"] for c in SEEN["receiver"]} == {"careful"} and {c["style"] for c in SEEN["picker"]} == {None}
    for a, calls in SEEN.items():  # effect comparisons handed back through last_outcome are filtered too
        assert all(p.split("[", 1)[0] in families[a] for c in calls for p in c["last_diffs"])
    withheld = {e.actor_id: set(e.payload["planner_input"]["withheld"]) for e in events(res, "OBSERVATION")
                if "planner_input" in e.payload}
    assert all(p.startswith("dock[") for p in withheld["picker"])
    assert not any(p.startswith(("dock[", "stock[", "clock")) for p in withheld["receiver"])


def test_missing_timed_out_and_cancelled_members():
    reg = registry()
    # ABSENT: the receiver's own budget ends after two proposals; later batches list it as absent
    pkg, sc = scenario()
    parts = [p.model_copy(update={"budget": Budget(max_steps=2)}) if p.actor_id == "receiver" else p
             for p in sc.participants]
    _, res = run(pkg, sc.model_copy(update={"participants": parts}), reg, run_id="run_g4_absent")
    later = [e.payload["batch"] for e in events(res, "BATCH_SUBMITTED")][2:]
    assert later and all({x["actor_id"]: x["status"] for x in b["members"]}["receiver"] == "ABSENT" for b in later)
    assert all(b["env_step"] == b["round"] for b in later)

    # TIMED_OUT: the picker's planner needs 0.4 s, the batch allows 0.2 s — its proposal is never sent
    pkg, sc = scenario(spy={"picker": {"sleep": 0.4}}, turns={**JOINT, "batch_timeout_s": 0.2})
    sc = sc.model_copy(update={"budget": sc.budget.model_copy(update={"max_steps": 4})})
    _, res = run(pkg, sc, reg, run_id="run_g4_timeout")
    first = events(res, "BATCH_SUBMITTED")[0].payload["batch"]
    assert [(x["actor_id"], x["status"]) for x in first["members"]] == [("receiver", "PROPOSED"),
                                                                        ("picker", "TIMED_OUT")]
    assert first["operation_id"] and first["env_step"] == 1
    picker = next(s for s in res.steps if s.actor_id == "picker")
    assert picker.proposal is not None and picker.outcome is None  # proposed, too late, not submitted

    # CANCELLED: the run's step budget ends mid-round — the open batch is cancelled, nothing of it was sent
    pkg, sc = scenario()
    sc = sc.model_copy(update={"budget": sc.budget.model_copy(update={"max_steps": 5})})
    _, res = run(pkg, sc, reg, run_id="run_g4_cancel")
    assert res.status.value == "BUDGET_EXHAUSTED"
    cancelled = events(res, "BATCH_CANCELLED")[0].payload["batch"]
    assert cancelled["round"] == 3 and cancelled["status"] == "CANCELLED"
    assert [x["status"] for x in cancelled["members"]] == ["CANCELLED", "CANCELLED"]
    assert res.final_state and len(events(res, "BATCH_SUBMITTED")) == 2


def test_gate_denies_one_member_of_a_batch():
    reg = registry()
    pkg = build_package(demo_model(zones=[{"id": "z1", "capacity": 4}, {"id": "z2", "capacity": 8}]),
                        package_id="warehouse-gate")
    sc = receiver_and_picker(pkg, seed=1, turns=JOINT, max_fill=0.5)
    _, res = run(pkg, sc, reg, run_id="run_g4_gate")
    assert res.status.value == "SUCCEEDED", res.reason
    denied = [s for s in res.steps if s.outcome and s.outcome.result.get("not_sent")]
    assert denied and all(s.outcome.result["reason"].startswith("EXECUTION_GATE") for s in denied)
    decided = events(res, "EXECUTION_DECIDED")
    assert decided and all(e.payload["batch_id"] for e in decided)
    submitted = {e.payload["batch"]["batch_id"]: e.payload["operation"] for e in events(res, "BATCH_SUBMITTED")}
    for s in denied:  # a denied member is not part of what reached the environment; the world did not change for it
        op = submitted[s.turn.batch_id]
        assert s.outcome.operation_id not in {o["operation_id"] for o in (op["batch_outcomes"] if op else [])}
        assert s.outcome.effect_applied is False


def test_joint_batch_needs_a_batch_environment():
    from formal_lab_example_orders.model import model_package
    from formal_lab_example_orders.scenarios import scenario as order_scenario

    pkg = model_package()
    sc = order_scenario("normal", endpoint="http://127.0.0.1:1", tenant="t", two_actors=True, timing="ROUND_START")
    sc = sc.model_copy(update={"turns": TurnPolicy.model_validate({**sc.turns.model_dump(), "mode": "JOINT_BATCH"})})
    with pytest.raises(Unsupported, match=r"env\.batch_step"):
        make_manifest(run_id="run_g4_neg", project_id="orders", scenario=sc, package=pkg, registry=default_registry(),
                      seed=1)
