"""The local order service on the durable path (Temporal + PostgreSQL) — P2-053 … P2-058.

A real service process (lifecycle manager, supervised) is the environment; the worker reaches it over loopback.
Checked: the durable path and the local runner produce the same steps, stages and outcomes (shared kernel);
lost answers are settled by lookup; a SIGKILLed worker resumes from the persisted proposal and the ledger; a cancel
while operations are held ends at a step boundary with every business operation accounted for; operators can list
abnormal operations, record reviews, and end a run with an explanation.
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
FINAL = {"COMPLETED", "RECONCILED", "FAILED"}


class Orders:
    def __init__(self, stack, mgr: ServiceManager):
        self.stack, self.mgr = stack, mgr
        project = next(p for p in stack.get("/projects") if p["name"] == "订单服务示例")
        self.project = project["id"]
        seeded = stack.get(f"/projects/{self.project}/scenarios")
        self.version_id = seeded[0]["model_version_id"]
        self.strategies = {s["name"]: s["id"] for s in stack.get(f"/projects/{self.project}/strategies")}

    def scenario(self, case: str, **env_extra) -> str:
        manifest = order_scenario(case, endpoint=self.mgr.endpoint, env_extra=env_extra or None)
        body = manifest.model_dump(mode="json", exclude={"scenario_id", "revision", "model", "contract_version"})
        body["name"] = f"{body['name']} [it-{uuid.uuid4().hex[:6]}]"
        body["extensions"] = {"formal-lab.run-defaults": {"version": "1.0.0",
                                                          "schema_id": "formal-lab.run-defaults/config@1",
                                                          "data": {"config": {"initial_check_horizon": 0}}}}
        return self.stack.post(f"/projects/{self.project}/scenarios", {**body, "model_version_id": self.version_id})["id"]

    def start(self, scenario_id: str, seed: int = 1) -> dict:
        return self.stack.post(f"/projects/{self.project}/runs", {"scenario_id": scenario_id, "seed": seed})

    def service_ops(self, run_id: str) -> list[dict]:
        r = httpx.get(f"{self.mgr.endpoint}/t/{tenant_for(run_id)}/admin/export", timeout=10)
        r.raise_for_status()
        return r.json()["operations"]


@pytest.fixture(scope="module")
def orders(stack, tmp_path_factory):
    mgr = ServiceManager(tmp_path_factory.mktemp("it-orders"), project="it-orders", supervise=True).start()
    mgr.ready()
    try:
        yield Orders(stack, mgr)
    finally:
        mgr.close()


def outcomes(events: list[dict]) -> list[tuple]:
    return [(e["logical_step"], e["payload"]["outcome"]["action"]["action_type"],
             tuple(sorted(e["payload"]["outcome"]["action"]["params"].items())), e["payload"]["outcome"]["status"])
            for e in events if e["event_type"] == "ACTION_OUTCOME"]


def test_durable_path_and_local_runner_share_the_kernel(stack, orders):
    """P2-057: the same case, seed and strategy through Temporal and through the local runner against the same
    service: identical actions, outcomes, stage sequence per step, operation states and metrics."""
    sid = orders.scenario("delayed")
    run = orders.start(sid)
    done = stack.wait_status(run["id"], {"SUCCEEDED", "FAILED", "BUDGET_EXHAUSTED"}, timeout=300)
    assert done["status"] == "SUCCEEDED", done.get("status_reason")
    local = local_run("delayed", backend="service", seed=1, endpoint=orders.mgr.endpoint, tenant="it-local-delayed",
                      run_id="run_it_local_delayed")
    events = stack.events(run["id"])
    local_rows = [(e.logical_step, e.payload["outcome"]["action"]["action_type"],
                   tuple(sorted(e.payload["outcome"]["action"]["params"].items())), e.payload["outcome"]["status"])
                  for e in local.events if str(e.event_type) == "ACTION_OUTCOME"]
    assert outcomes(events) == local_rows
    def per_step(rows):  # (event type, execution stage) in order, per step — the kernel's shape of a step
        out: dict[int, list] = {}
        for step, kind, stage in rows:
            if step:
                out.setdefault(step, []).append((kind, stage))
        return out

    platform_shape = per_step([(e["logical_step"], e["event_type"], e.get("stage")) for e in events])
    local_shape = per_step([(e.logical_step, str(e.event_type), str(e.stage) if e.stage else None)
                            for e in local.events])
    assert platform_shape == local_shape
    ops = stack.get(f"/runs/{run['id']}/operations")
    assert [o["state"] for o in ops] == [o.state.value for o in local.operations]
    assert "RECONCILED" in {o["state"] for o in ops}
    assert {k: v["value"] for k, v in done["metrics"].items() if k in ("orders_completed", "late_orders")} == \
        {m.metric_id: m.value for m in local.metrics if m.metric_id in ("orders_completed", "late_orders")}


def test_lost_answers_and_a_killed_worker(stack, orders):
    """P2-053 / P2-054 / P2-055: every answer is held past the client timeout; the worker is SIGKILLed mid-run and
    restarted. The step resumes from the persisted proposal (no second proposal), the ledger's DISPATCHED /
    OUTCOME_UNKNOWN operations are settled by lookup, and the service holds exactly one operation per step."""
    sid = orders.scenario("normal", conditions={"hold_after_commit_ms": 1200, "hold_every": 1}, timeout_s=0.4)
    run = orders.start(sid)
    stack.wait_step(run["id"], 3, timeout=120)
    time.sleep(0.6)  # inside an apply: the answer is being held
    stack.kill_worker()
    time.sleep(1)
    stack.start_worker()
    done = stack.wait_status(run["id"], {"SUCCEEDED", "FAILED", "BUDGET_EXHAUSTED"}, timeout=400)
    assert done["status"] == "SUCCEEDED", done.get("status_reason")
    events = stack.events(run["id"])
    proposals = [e["logical_step"] for e in events if e["event_type"] == "ACTION_PROPOSED"]
    assert proposals == sorted(set(proposals)), "one proposal per step, also across the crash"
    ops = stack.get(f"/runs/{run['id']}/operations")
    assert all(o["state"] in FINAL for o in ops) and len(ops) == done["last_step"]
    assert sum(1 for o in ops if o["state"] == "RECONCILED") >= done["last_step"] - 2
    service = orders.service_ops(run["id"])
    assert sorted(o["operation_id"] for o in service) == sorted(o["operation_id"] for o in ops)
    kinds = {e["event_type"] for e in events}
    assert {"OPERATION_STATE", "OPERATION_RECONCILED"} <= kinds
    recovery = [e for e in events if e["event_type"] == "RECOVERY"]
    assert recovery, "the restart is on the record"
    abnormal = stack.get(f"/runs/{run['id']}/operations", params={"abnormal": "true"})
    assert abnormal and all(any(t["state"] == "OUTCOME_UNKNOWN" for t in o["transitions"]) for o in abnormal)
    # P2-058: an operator confirms one of them; a second review needs an explicit supersede
    op_id = abnormal[0]["operation_id"]
    reviewed = stack.post(f"/operations/{op_id}/review",
                          {"status": "CONFIRMED_APPLIED", "note": "service operations table shows it once",
                           "by": "it-operator"})
    assert reviewed["review"]["status"] == "CONFIRMED_APPLIED" and not reviewed["needs_review"]
    stack.post(f"/operations/{op_id}/review", {"status": "CONFIRMED_NOT_APPLIED", "note": "x"}, expect=409)
    review_events = [e for e in stack.events(run["id"]) if e["event_type"] == "OPERATION_REVIEW"]
    assert review_events and review_events[-1]["payload"]["review"]["by"] == "it-operator"
    assert stack.get(f"/operations/{op_id}")["review"]["note"] == "service operations table shows it once"


def test_cancel_while_operations_are_held_is_an_explained_termination(stack, orders):
    """P2-054 / P2-058: cancelling while the service holds answers ends the run at a step boundary; every business
    operation the service performed is in the ledger in a final state; the operator's reason is on the run."""
    sid = orders.scenario("normal", conditions={"hold_after_commit_ms": 1500, "hold_every": 1}, timeout_s=0.4)
    run = orders.start(sid)
    stack.wait_step(run["id"], 2, timeout=120)
    stack.post(f"/runs/{run['id']}/cancel", {"reason": "service answers too slowly for this experiment",
                                            "operations": []})
    done = stack.wait_status(run["id"], {"CANCELLED"}, timeout=120)
    assert "terminated by operator: service answers too slowly" in (done["status_reason"] or "")
    cancelling = [e for e in stack.events(run["id"]) if e["event_type"] == "RUN_CANCELLING"]
    assert cancelling and cancelling[0]["payload"]["reason"].startswith("terminated by operator")
    time.sleep(2)  # nothing moves after the end
    ops = stack.get(f"/runs/{run['id']}/operations")
    assert ops and all(o["state"] in FINAL for o in ops)
    service = orders.service_ops(run["id"])
    assert {o["operation_id"] for o in service} <= {o["operation_id"] for o in ops}
    assert len(service) <= done["last_step"] + 1


def test_operator_reason_survives_a_generic_workflow_cancellation(stack, orders):
    """The cancellation can reach the workflow mid-activity, and then it finalizes with a generic reason: the
    operator's explained termination recorded at CANCELLING must still be the run's reason (race seen in CI)."""
    from formal_lab_api.services.execution import finalize_run

    sid = orders.scenario("normal", conditions={"hold_after_commit_ms": 1500, "hold_every": 1}, timeout_s=0.4)
    run = orders.start(sid)
    stack.wait_step(run["id"], 1, timeout=120)
    stack.post(f"/runs/{run['id']}/cancel", {"reason": "operator reason kept", "operations": []})
    finalize_run(run["id"], "CANCELLED", "cancelled by user", None)  # what the workflow's CancelledError path does
    done = stack.wait_status(run["id"], {"CANCELLED"}, timeout=120)
    assert done["status_reason"] == "terminated by operator: operator reason kept"
    terminal = [e for e in stack.events(run["id"]) if e["event_type"] == "RUN_CANCELLED"]
    assert terminal and terminal[-1]["payload"]["reason"] == "terminated by operator: operator reason kept"
