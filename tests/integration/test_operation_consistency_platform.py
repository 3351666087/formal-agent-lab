"""Pre-execution decisions and operation consistency on the durable path (phase 3A, G2).

The order example's inventory gate (safety stock 2) runs through Temporal against the real service process, with the
worker SIGKILLed mid-run: the decisions are persisted on the operation records and as events, a denied operation is
never sent (the service has no row for it), every sent operation exists exactly once in the service, and the durable
path records the same decisions as the local runner.
"""

from __future__ import annotations

import time
import uuid

import httpx
import pytest
from formal_lab_example_orders.env import tenant_for
from formal_lab_example_orders.lifecycle import ServiceManager
from formal_lab_example_orders.scenarios import run as local_run
from formal_lab_example_orders.scenarios import scenario as order_scenario

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def mgr(tmp_path_factory):
    m = ServiceManager(tmp_path_factory.mktemp("it-gates"), project="it-gates", supervise=True).start()
    m.ready()
    try:
        yield m
    finally:
        m.close()


def test_gated_run_on_the_durable_path_with_a_killed_worker(stack, mgr):
    project = next(p for p in stack.get("/projects") if p["name"] == "订单服务示例")["id"]
    version_id = stack.get(f"/projects/{project}/scenarios")[0]["model_version_id"]
    manifest = order_scenario("normal", endpoint=mgr.endpoint, safety_stock=2)
    body = manifest.model_dump(mode="json", exclude={"scenario_id", "revision", "model", "contract_version"})
    body["name"] = f"{body['name']} [gate-{uuid.uuid4().hex[:6]}]"
    body["extensions"] = {"formal-lab.run-defaults": {"version": "1.0.0", "schema_id": "formal-lab.run-defaults/config@1",
                                                      "data": {"config": {"initial_check_horizon": 0}}}}
    sid = stack.post(f"/projects/{project}/scenarios", {**body, "model_version_id": version_id})["id"]
    assert stack.get(f"/scenarios/{sid}")["manifest"]["execution_gates"][0]["config"] == {"min_stock_after": 2}
    run = stack.post(f"/projects/{project}/runs", {"scenario_id": sid, "seed": 1})
    deadline = time.time() + 120
    while stack.get(f"/runs/{run['id']}").get("last_step", 0) < 4 and time.time() < deadline:
        time.sleep(0.2)
    stack.kill_worker()
    time.sleep(1)
    stack.start_worker()
    done = stack.wait_status(run["id"], {"SUCCEEDED", "FAILED", "BUDGET_EXHAUSTED"}, timeout=400)
    assert done["status"] == "SUCCEEDED", done.get("status_reason")

    ops = stack.get(f"/runs/{run['id']}/operations")
    decisions = [d for o in ops for d in o["decisions"]]
    denied = {d["operation_id"] for d in decisions if d["verdict"] == "DENY"}
    assert denied and all(d["values_source"] in ("FRESH", "NONE") for d in decisions)
    assert all(o["request_digest"] for o in ops)
    service = httpx.get(f"{mgr.endpoint}/t/{tenant_for(run['id'])}/admin/export", timeout=10).json()["operations"]
    service_ids = [r["operation_id"] for r in service]
    assert len(service_ids) == len(set(service_ids))  # nothing twice, even with the killed worker
    assert not denied & set(service_ids)  # denied operations were never sent
    sent = {o["operation_id"] for o in ops if any(t.get("effect") == "SEND" for t in o["transitions"])}
    assert sent == set(service_ids)
    events = stack.events(run["id"])
    assert sum(1 for e in events if e["event_type"] == "EXECUTION_DECIDED") >= len(decisions)

    local = local_run("normal", backend="service", seed=1, endpoint=mgr.endpoint, tenant="it-gates-local",
                      run_id="run_it_gates_local", safety_stock=2)
    local_denied = [(e.payload["decision"]["step"], e.payload["decision"]["reason"]) for e in local.events
                    if str(e.event_type) == "EXECUTION_DECIDED" and e.payload["decision"]["verdict"] == "DENY"]
    durable_denied = sorted((d["step"], d["reason"]) for d in decisions if d["verdict"] == "DENY")
    assert durable_denied == sorted(local_denied)  # same decisions on both paths
