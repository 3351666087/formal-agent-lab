"""Model decisions on the durable path (phase 4A, A3): a planner whose endpoint is the loopback protocol test service
(not a model), paused, resumed and its worker SIGKILLed — committed calls are never repeated, every committed call id
maps to exactly one request the service answered, and the source is the answering endpoint's, not the config's."""

from __future__ import annotations

import time

import pytest
from formal_lab_strategies.protocol_server import MODEL, ProtocolTestServer

pytestmark = pytest.mark.integration


def _scenario_body(demo: dict, url: str) -> dict:
    base = demo["scenarios"]["正常调度"]
    m = base["manifest"]
    actor = m["participants"][0]["actor_id"]
    return {"name": f"A3 protocol-test planner {int(time.time())}", "model_version_id": base["model_version_id"],
            "environment": m["environment"], "objectives": m.get("objectives", []), "budget": m["budget"],
            "seed": m.get("seed", 0), "stop_conditions": m.get("stop_conditions", []),
            "termination": m.get("termination"), "objective": m.get("objective"),
            "participants": [{"actor_id": actor, "strategy": {
                "plugin": {"plugin_id": "formal-lab.planner.llm", "version": "1.1.0"},
                "config": {"client": "openai_compatible", "on_model_failure": "fallback", "max_attempts": 2,
                           "timeout_s": 10}},
                # the participant's own settings (read first): this run's endpoint is the protocol test service
                "view": {"settings": {"FAL_LLM_BASE_URL": url, "FAL_LLM_API_KEY": "protocol-test-only",
                                      "FAL_LLM_MODEL": MODEL}}}]}


def _proposals(stack, run_id: str) -> list[dict]:
    return [e["payload"]["proposal"] for e in stack.events(run_id) if e["event_type"] == "ACTION_PROPOSED"]


def test_pause_resume_and_worker_kill_never_repeat_committed_calls(stack, demo):
    server = ProtocolTestServer(host="127.0.0.1").start()
    try:
        sc = stack.post(f"/projects/{demo['project']}/scenarios", _scenario_body(demo, server.base_url), expect=201)
        run = stack.post(f"/projects/{demo['project']}/runs", {"scenario_id": sc["id"], "seed": 1})
        rid = run["id"]
        stack.wait_step(rid, 3)
        stack.post(f"/runs/{rid}/pause")
        paused = stack.wait_status(rid, {"PAUSED"}, timeout=120)
        before = len(server.requests)
        time.sleep(2)
        assert len(server.requests) == before, "no request while paused"
        stack.post(f"/runs/{rid}/resume")
        stack.wait_step(rid, paused["last_step"] + 3)
        stack.kill_worker()
        time.sleep(2)
        stack.start_worker()
        done = stack.wait_status(rid, {"SUCCEEDED", "FAILED", "BUDGET_EXHAUSTED"}, timeout=300)
    finally:
        server.stop()

    props = _proposals(stack, rid)
    committed = [cid for p in props for cid in p["source"]["model_call_ids"]]
    answered = [f"ptest_{i:05d}" for i in range(1, len(server.requests) + 1)]  # ids the service gave, in order
    assert done["status"] == "SUCCEEDED" and props
    assert len(committed) == len(set(committed)), "a committed call is never repeated or double-counted"
    assert set(committed) <= set(answered), "every committed call id is an answer the service actually sent"
    lost = len(answered) - len(committed)
    # a request in flight when the worker was killed is answered but never committed (at most one per kill)
    assert 0 <= lost <= 1, (lost, len(answered), len(committed))
    kinds = {(p["source"]["kind"], p["source"].get("decided_by")) for p in props}
    assert kinds == {("LLM_PROTOCOL_TEST", "MODEL_RESPONSE")}, kinds
    assert done["usage"]["model_calls"] == len(committed)
