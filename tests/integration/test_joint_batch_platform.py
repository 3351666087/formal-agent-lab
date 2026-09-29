"""JOINT_BATCH on the durable path (Temporal + PostgreSQL, phase 3A G4): the open batch lives in the persisted carry
state, so a worker killed in the middle of a round continues it — one environment step per round, every member's
outcome on its own proposal step, the same trajectory and the same planner inputs as the local runner. A run
cancelled mid-round cancels the open batch: nothing of it was sent."""

from __future__ import annotations

import time

import pytest

pytestmark = pytest.mark.integration


def project(stack, name: str) -> dict:
    return next(p for p in stack.get("/projects") if p["name"] == name)


def scenario(stack, project_id: str, name: str) -> dict:
    return next(s for s in stack.get(f"/projects/{project_id}/scenarios") if s["name"] == name)


def of(events, kind):
    return [e for e in events if e["event_type"] == kind]


def pause_inside_a_round(stack, run_id: str, at_least: int) -> dict:
    """Pause at a step boundary inside a round (odd global step: the receiver proposed, the picker not yet)."""
    stack.wait_step(run_id, at_least)
    for _ in range(4):
        stack.post(f"/runs/{run_id}/pause")
        paused = stack.wait_status(run_id, {"PAUSED"}, timeout=120)
        if paused["last_step"] % 2 == 1:
            return paused
        stack.post(f"/runs/{run_id}/resume")
        stack.wait_step(run_id, paused["last_step"] + 1)
    raise AssertionError("could not pause inside a round")


def local_reference():
    from formal_lab_example_warehouse.scenarios import JOINT, VIEWS, package, receiver_and_picker
    from formal_lab_runtime import default_registry, make_manifest, run_local

    reg, pkg = default_registry(), package()
    m = make_manifest(run_id="run_g4_ref", project_id="wh", scenario=receiver_and_picker(pkg, turns=JOINT, views=VIEWS),
                      package=pkg, registry=reg, seed=0)
    return run_local(m, pkg, reg)


def test_worker_killed_mid_round_continues_the_batch(stack):
    wh = project(stack, "仓储分配示例")
    sc = scenario(stack, wh["id"], "仓储：收货员 + 拣货员同步批次")
    run = stack.post(f"/projects/{wh['id']}/runs", {"scenario_id": sc["id"], "seed": 0})
    paused = pause_inside_a_round(stack, run["id"], 3)
    carry_batch = [e for e in stack.events(run["id"]) if e["event_type"] == "BATCH_OPENED"][-1]["payload"]["batch"]
    mid_round = paused["last_step"] % 2 == 1
    stack.post(f"/runs/{run['id']}/resume")
    stack.kill_worker()
    time.sleep(3)
    stack.start_worker()
    done = stack.wait_status(run["id"], {"SUCCEEDED", "FAILED", "BUDGET_EXHAUSTED"}, timeout=300)
    assert done["status"] == "SUCCEEDED", done.get("status_reason")
    assert mid_round and carry_batch["status"] == "OPEN"
    events = stack.events(run["id"])
    keys = [e["idempotency_key"] for e in events]
    assert len(keys) == len(set(keys)), "no duplicated events after recovery"
    submitted = [e["payload"]["batch"] for e in of(events, "BATCH_SUBMITTED")]
    assert len(submitted) == len(of(events, "BATCH_OPENED")) == done["last_step"] // 2
    assert all(b["env_step"] == b["round"] and len(b["members"]) == 2 for b in submitted)
    outcomes = of(events, "ACTION_OUTCOME")
    assert sorted(e["logical_step"] for e in outcomes) == list(range(1, done["last_step"] + 1))
    ref = local_reference()
    durable = [(e["logical_step"], e["actor_id"], e["payload"]["outcome"]["action"],
                e["payload"]["outcome"]["status"]) for e in sorted(outcomes, key=lambda e: e["logical_step"])]
    local = [(s.step, s.actor_id, s.proposal.action.model_dump(mode="json"), s.outcome.status.value)
             for s in ref.steps]
    assert durable == local, "the durable run is the local runner's trajectory"
    digests = [(e["logical_step"], e["payload"].get("planner_input_digest")) for e in of(events, "ACTION_PROPOSED")]
    ref_digests = [(e.logical_step, e.payload.get("planner_input_digest"))
                   for e in ref.events if str(e.event_type) == "ACTION_PROPOSED"]
    assert digests == ref_digests and all(d for _, d in digests), "each planner received the same input"
    step = stack.get(f"/runs/{run['id']}/steps/1")
    assert step["events"] and any(ev["event_type"] == "BATCH_OPENED" for ev in step["events"])


def test_cancel_mid_round_cancels_the_open_batch(stack):
    wh = project(stack, "仓储分配示例")
    sc = scenario(stack, wh["id"], "仓储：收货员 + 拣货员同步批次")
    run = stack.post(f"/projects/{wh['id']}/runs", {"scenario_id": sc["id"], "seed": 0})
    paused = pause_inside_a_round(stack, run["id"], 1)
    stack.post(f"/runs/{run['id']}/cancel")
    cancelled = stack.wait_status(run["id"], {"CANCELLED"}, timeout=120)
    events = stack.events(run["id"])
    opened, done = of(events, "BATCH_OPENED"), of(events, "BATCH_SUBMITTED")
    assert paused["last_step"] % 2 == 1
    batch = of(events, "BATCH_CANCELLED")[0]["payload"]["batch"]
    assert batch["status"] == "CANCELLED" and len(opened) == len(done) + 1
    assert {x["status"] for x in batch["members"]} == {"CANCELLED"} and batch["operation_id"] is None
    assert cancelled["termination_reason"] == "CANCELLED"


def test_a_view_must_name_locations_of_the_model(stack):
    wh = project(stack, "仓储分配示例")
    sc = scenario(stack, wh["id"], "仓储：收货员 + 拣货员同步批次")
    body = {k: v for k, v in sc["manifest"].items() if k not in ("scenario_id", "revision", "model",
                                                                 "contract_version")}
    body["participants"][0]["view"] = {"include": ["dock", "docks"]}
    bad = stack.client.post(f"/projects/{wh['id']}/scenarios", json={**body, "name": "bad view",
                                                                      "model_version_id": sc["model_version_id"]})
    assert bad.status_code == 422
    errors = bad.json()["error"]["field_errors"]
    assert [e["path"] for e in errors] == ["/participants/0/view/include"] and "'docks'" in errors[0]["message"]
