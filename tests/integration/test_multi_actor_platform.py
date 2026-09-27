"""Several participants on the durable path (Temporal + PostgreSQL): pause/resume, SIGKILLed worker and cancel keep
the turn order, per-participant counters and plan progress (P2-031 / P2-036 / P2-037), and the second semantic
profile runs through the platform exactly like the IR (P2-012)."""

from __future__ import annotations

import time

import pytest

pytestmark = pytest.mark.integration


def project(stack, name: str) -> dict:
    return next(p for p in stack.get("/projects") if p["name"] == name)


def scenario(stack, project_id: str, name: str) -> dict:
    return next(s for s in stack.get(f"/projects/{project_id}/scenarios") if s["name"] == name)


def turns(stack, run_id: str) -> list[dict]:
    return [e["turn"] for e in stack.events(run_id) if e["event_type"] == "TURN_STARTED"]


def assert_turn_order(stack, run_id: str, cycle: list[str]) -> list[dict]:
    events = stack.events(run_id)
    assert [e["seq"] for e in events] == list(range(1, len(events) + 1))
    keys = [e["idempotency_key"] for e in events]
    assert len(keys) == len(set(keys)), "no duplicated events after recovery"
    ts = turns(stack, run_id)
    assert [t["global_step"] for t in ts] == list(range(1, len(ts) + 1)), "every global step exactly once"
    assert [t["actor_id"] for t in ts] == [cycle[i % len(cycle)] for i in range(len(ts))], "round-robin order"
    for actor in cycle:
        mine = [t["actor_step"] for t in ts if t["actor_id"] == actor]
        assert mine == list(range(1, len(mine) + 1)), f"{actor}'s own step counter is contiguous"
    outcomes = [e for e in events if e["event_type"] == "ACTION_OUTCOME"]
    assert len({(e["logical_step"]) for e in outcomes}) == len(outcomes), "one outcome per global step"
    return ts


def test_two_dispatchers_pause_resume_and_worker_crash(stack):
    demo = project(stack, "生产调度示例")
    sc = scenario(stack, demo["id"], "两名调度员（轮流）")
    run = stack.post(f"/projects/{demo['id']}/runs", {"scenario_id": sc["id"], "seed": 1})
    stack.wait_step(run["id"], 3)
    stack.post(f"/runs/{run['id']}/pause")
    paused = stack.wait_status(run["id"], {"PAUSED"}, timeout=120)
    at_pause = paused["turn"]
    time.sleep(2)
    still = stack.get(f"/runs/{run['id']}")
    assert still["last_step"] == paused["last_step"] and still["turn"] == at_pause  # nothing moves while paused
    stack.post(f"/runs/{run['id']}/resume")
    stack.wait_step(run["id"], paused["last_step"] + 3)
    stack.kill_worker()
    time.sleep(3)
    stack.start_worker()
    done = stack.wait_status(run["id"], {"SUCCEEDED", "FAILED", "BUDGET_EXHAUSTED"}, timeout=300)
    assert done["status"] == "SUCCEEDED" and done["termination_reason"] == "JOINT_GOAL_REACHED"
    ts = assert_turn_order(stack, run["id"], ["dispatcher_a", "dispatcher_b"])
    actors = done["actor_usage"]
    assert actors["dispatcher_a"]["steps"] + actors["dispatcher_b"]["steps"] == done["last_step"] == len(ts)
    assert done["usage"]["steps"] == done["last_step"]
    # the paused event records the turn cursor at the boundary
    paused_events = [e for e in stack.events(run["id"]) if e["event_type"] == "RUN_PAUSED"]
    assert paused_events and paused_events[0]["payload"]["turn"]["global_step"] == paused["last_step"]
    # the symbolic dispatcher's plan versions only grow (checkpoint restored after the crash, not reset)
    plans = [e["payload"]["plan"]["version"] for e in stack.events(run["id"])
             if e["event_type"] == "PLAN_UPDATED" and e["actor_id"] == "dispatcher_b"]
    assert plans == sorted(plans) and plans[0] == 1
    step = stack.get(f"/runs/{run['id']}/steps/2")
    assert step["events"] and any(ev["event_type"] == "TURN_STARTED" for ev in step["events"])


def test_multi_actor_cancel_and_second_profile_through_the_platform(stack):
    wh = project(stack, "仓储分配示例")
    sc = scenario(stack, wh["id"], "仓储：收货员 + 拣货员轮流作业")
    run = stack.post(f"/projects/{wh['id']}/runs", {"scenario_id": sc["id"], "seed": 0})
    done = stack.wait_status(run["id"], {"SUCCEEDED", "FAILED", "BUDGET_EXHAUSTED"}, timeout=180)
    assert done["status"] == "SUCCEEDED", done.get("status_reason")
    assert_turn_order(stack, run["id"], ["receiver", "picker"])
    assert done["metrics"]["orders_completed"]["value"] == 3.0  # the warehouse scorer applied by package id
    manifest = done["manifest"]
    roles = {p["role"]: p for p in manifest["plugins"]}
    assert roles["driver"]["plugin_id"] == "formal-lab.example.warehouse.driver"
    assert roles["environment"]["plugin_id"] == "formal-lab.env.driver-world"
    checks = [e for e in stack.events(run["id"]) if e["event_type"] == "CHECK_COMPLETED"]
    assert checks and all(e["payload"]["result"]["verdict"] == "UNSUPPORTED" for e in checks)  # IR verifier
    verifier = next(n for n in manifest["negotiation"] if n["role"] == "verifier")
    assert verifier["verdict"] == "UNSUPPORTED" and verifier["reasons"]
    # cancel a running two-participant run: it ends at a step boundary as CANCELLED with its reason
    demo = project(stack, "生产调度示例")
    two = scenario(stack, demo["id"], "两名调度员（轮流）")
    run2 = stack.post(f"/projects/{demo['id']}/runs", {"scenario_id": two["id"], "seed": 3})
    stack.wait_step(run2["id"], 2)
    stack.post(f"/runs/{run2['id']}/cancel")
    cancelled = stack.wait_status(run2["id"], {"CANCELLED"}, timeout=120)
    assert cancelled["termination_reason"] == "CANCELLED"
    assert_turn_order(stack, run2["id"], ["dispatcher_a", "dispatcher_b"])
