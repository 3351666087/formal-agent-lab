"""Phase 4B (B2) without CybORG: the cage4_v1 driver, the metrics evaluator and the trajectory comparison are pure
platform code and are checked on recorded / constructed data (the toolchain-backed checks are in
test_platform_cage.py, marked `cage`)."""

from __future__ import annotations

import json

import pytest
from formal_lab_contracts import EpisodeRecord, Fact, GroundAction, Observation
from formal_lab_env_cage import metrics, model, trajectory

DESCRIBE = {"scenario": "Scenario4", "subnets": ["admin_network_subnet"],
            "hosts": ["admin_network_subnet_router", "admin_network_subnet_user_host_0",
                      "admin_network_subnet_server_host_0"],
            "blue_actions": ["Sleep", "Monitor", "Analyse", "Remove", "Restore", "DeployDecoy"],
            "limits": {"user_hosts": [3, 10], "server_hosts": [1, 6]}}


@pytest.fixture
def loaded():
    return model.Cage4Driver().load(model.package(DESCRIBE))


def _obs(allowed: list[str], alerts: dict[str, str] | None = None, busy: bool = False) -> Observation:
    alerts = alerts or {}
    facts = [Fact(path=f"allowed[{h}]", value=h in allowed, observed_at_step=3) for h in DESCRIBE["hosts"]]
    facts += [Fact(path=f"alert_kind[{h}]", value=alerts.get(h, "none"), observed_at_step=3) for h in DESCRIBE["hosts"]]
    facts += [Fact(path=f"alert[{h}]", value=h in alerts, observed_at_step=3) for h in DESCRIBE["hosts"]]
    facts += [Fact(path="busy", value=busy, observed_at_step=3), Fact(path="done", value=False, observed_at_step=3)]
    return Observation(run_id="r", actor_id="blue_agent_0", step=3, state_revision=3, facts=facts)


def test_driver_validates_its_payload():
    driver = model.Cage4Driver()
    assert driver.validate(model.package(DESCRIBE)) == []
    bad = model.package(DESCRIBE).model_copy(update={"payload": {"kind": "namespaced", "namespace": "x",
                                                                  "schema_id": "y", "data": {}}})
    assert driver.validate(bad)


def test_candidates_are_the_agents_own_action_space(loaded):
    belief = loaded.belief(_obs(["admin_network_subnet_user_host_0"]))
    cands = loaded.candidates(belief)
    hosted = {(c.action.action_type, c.action.params.get("host")) for c in cands if c.action.params}
    assert hosted == {(a, "admin_network_subnet_user_host_0") for a in model.HOSTED}  # only the allowed host
    assert {"sleep", "monitor"} <= {c.action.action_type for c in cands}
    busy = loaded.candidates(loaded.belief(_obs(["admin_network_subnet_user_host_0"], busy=True)))
    assert all("in progress" in c.reason for c in busy)


def test_predict_is_applicability_only(loaded):
    state = loaded.belief(_obs(["admin_network_subnet_user_host_0"])).state
    ok = loaded.predict(state, GroundAction(action_type="restore", params={"host": "admin_network_subnet_user_host_0"}))
    assert ok.applicable and ok.next_state is None  # native effects are not predicted → INSUFFICIENT_INFORMATION
    out = loaded.predict(state, GroundAction(action_type="restore", params={"host": "admin_network_subnet_router"}))
    assert not out.applicable and "action space" in out.reason
    assert not loaded.predict(state, GroundAction(action_type="shell")).applicable


def test_react_policy_reads_only_its_own_alerts():
    from formal_lab_contracts import PlanningContext
    from formal_lab_env_cage.strategies import BlueReact

    def ctx(obs):
        return PlanningContext.model_construct(run_id="r", step_id="r:s4", step=4, actor_id="blue_agent_0",
                                               observation=obs, candidates=[])

    h = "admin_network_subnet_user_host_0"
    assert BlueReact().propose(ctx(_obs([h], {h: "file"}))).action.action_type == "restore"
    assert BlueReact().propose(ctx(_obs([h], {h: "connection"}))).action.action_type == "analyse"
    assert BlueReact().propose(ctx(_obs([h], {}))).action.action_type == "monitor"
    assert BlueReact().propose(ctx(_obs([h], {h: "file"}, busy=True))).action.action_type == "sleep"
    # an alert on a host outside the agent's action space is not acted on
    assert BlueReact().propose(ctx(_obs([h], {"admin_network_subnet_router": "file"}))).action.action_type == "monitor"


def test_recoveries_are_computed_from_enter_and_leave_events():
    timeline = [{"world_step": 1, "red_foothold_hosts": ["a"]},
                {"world_step": 2, "red_foothold_hosts": ["a", "b"]},
                {"world_step": 5, "red_foothold_hosts": ["b"]},  # a left after 4 steps
                {"world_step": 6, "red_foothold_hosts": ["b", "c"]}]
    done, open_ = metrics.recoveries(timeline)
    assert done == [4] and open_ == {"b", "c"}


def _episode(timeline, *, busy=0, unavailable=None):
    from formal_lab_contracts import ScenarioManifest

    sc = ScenarioManifest.model_construct(participants=[object()] * 5)
    steps = []
    for _ in range(busy):
        steps.append(type("S", (), {"outcome": type("O", (), {"status": "REJECTED",
                                                              "result": {"reason": "AGENT_BUSY: x"}})()})())
    return EpisodeRecord.model_construct(
        run_id="r", scenario=sc, steps=steps,
        final_truth_state={"referee_timeline": json.dumps(timeline)} if timeline is not None else {},
        environment_summary={"unavailable": unavailable} if unavailable else {})


def test_metrics_keep_native_score_and_platform_metrics_apart():
    timeline = [{"world_step": 1, "rewards": {"Blue": -1.0}, "green": {"work:TRUE": 3, "access:FALSE": 1},
                 "red_foothold_hosts": ["h1"]},
                {"world_step": 2, "rewards": {"Blue": -2.0}, "green": {"work:TRUE": 2}, "red_foothold_hosts": []}]
    got = {m.metric_id: m for m in metrics.Cage4Metrics().score(_episode(timeline, busy=2))}
    assert got["native_blue_reward"].value == -3.0
    assert got["green_success_rate"].value == pytest.approx(5 / 6)
    assert got["green_failed_actions"].value == 1 and got["red_foothold_host_steps"].value == 1
    assert got["recovery_time"].value == 1 and got["unrecovered_hosts"].value == 0
    assert got["blue_actions_not_started"].value == 2 and got["blue_agent_count"].value == 5
    labels = {d.metric_id: d.label for d in metrics.DEFINITIONS}
    assert "不是业务存活" in labels["blue_agent_count"] and "原生" in labels["native_blue_reward"]


def test_metrics_say_why_when_the_referee_timeline_is_missing():
    got = {m.metric_id: m for m in metrics.Cage4Metrics().score(_episode(None, unavailable="worker gone"))}
    assert got["native_blue_reward"].status == "MISSING" and "worker gone" in got["native_blue_reward"].missing_reason
    assert got["blue_agent_count"].status == "OK"


def _rec(step, *, blue="[Sleep]", reward=0.0, digest="d"):
    return {"world_step": step, "phase": 0, "done": False, "rewards": {"Blue": reward}, "red": {"red_agent_0": "[x]"},
            "green": {}, "red_footholds": 0, "red_foothold_hosts": [], "digest": f"{digest}{step}",
            "blue": {"blue_agent_0": {"executed": blue, "success": "TRUE", "submitted": {"name": "Sleep"}}}}


def test_trajectory_comparison_finds_the_first_difference():
    a = [_rec(1), _rec(2), _rec(3)]
    assert trajectory.compare(a, [_rec(1), _rec(2), _rec(3)])["equal"]
    b = [_rec(1), _rec(2, blue="[Monitor]"), _rec(3, digest="x")]
    c = trajectory.compare(a, b)
    assert not c["equal"] and c["first_difference"]["world_step"] == 2
    assert c["first_difference"]["field"] == "blue.blue_agent_0.executed" and c["equal_world_steps"] == 1
    short = trajectory.compare(a, a[:2])
    assert not short["equal"] and short["first_difference"]["field"] == "presence"
    assert trajectory.platform_actions(a) == [{"blue_agent_0": {"name": "Sleep"}}] * 3
