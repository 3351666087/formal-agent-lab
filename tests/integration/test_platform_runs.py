"""P1-123 and related: persistence, ordering, SSE resume, duplicate submission, pause/resume, cancel,
worker crash recovery, rerun lineage, budgets and model versioning — against the real stack."""

from __future__ import annotations

import time
import uuid
from collections import Counter

import httpx
import pytest

pytestmark = pytest.mark.integration

RULE = "formal-lab.example.scheduling.edd-dispatch"
Z3 = "formal-lab.planner.z3-bounded"


def start(stack, demo, scenario="正常调度", strategy=RULE, seed=1, **extra) -> dict:
    body = {"scenario_id": demo["scenarios"][scenario]["id"], "strategy_config_id": demo["strategies"][strategy]["id"],
            "seed": seed, **extra}
    return stack.post(f"/projects/{demo['project']}/runs", body)


def assert_consistent(stack, run_id: str) -> list[dict]:
    events = stack.events(run_id)
    assert [e["seq"] for e in events] == list(range(1, len(events) + 1)), "sequence must be gap-free"
    keys = [e["idempotency_key"] for e in events]
    assert len(keys) == len(set(keys)), "no duplicated events"
    ids = {e["event_id"] for e in events}
    assert all(p in ids for e in events for p in e["causal_parents"]), "causal parents must exist"
    per_step = Counter(e["logical_step"] for e in events if e["event_type"] == "ACTION_OUTCOME")
    assert all(n == 1 for n in per_step.values()), f"exactly one outcome per step: {per_step}"
    return events


def test_run_is_persisted_with_pinned_manifest(stack, demo):
    run = start(stack, demo)
    done = stack.wait_status(run["id"], {"SUCCEEDED", "FAILED", "BUDGET_EXHAUSTED"})
    assert done["status"] == "SUCCEEDED"
    events = assert_consistent(stack, run["id"])
    types = [e["event_type"] for e in events]
    assert types[:3] == ["RUN_CREATED", "RUN_QUEUED", "RUN_STARTED"] and types[-1] == "RUN_SUCCEEDED"
    manifest = done["manifest"]
    roles = {p["role"]: p for p in manifest["plugins"]}
    assert roles["strategy:dispatcher"]["plugin_id"] == RULE and len(roles["environment"]["descriptor_digest"]["value"]) == 64
    assert manifest["model"]["version"] == 1 and manifest["scenario_digest"]["value"]
    assert done["metrics"]["goal_reached"]["value"] == 1.0
    step3 = stack.get(f"/runs/{run['id']}/steps/3")
    assert {"observation", "candidates", "proposal", "checks", "outcome", "comparison"} <= set(step3)


def test_duplicate_submission_returns_same_run(stack, demo):
    key = f"dup-{uuid.uuid4().hex[:8]}"
    body = {"scenario_id": demo["scenarios"]["正常调度"]["id"], "strategy_config_id": demo["strategies"][RULE]["id"]}
    r1 = stack.client.post(f"/projects/{demo['project']}/runs", json=body, headers={"Idempotency-Key": key})
    r2 = stack.client.post(f"/projects/{demo['project']}/runs", json=body, headers={"Idempotency-Key": key})
    assert r1.status_code == 201 and r2.status_code == 200 and r1.json()["id"] == r2.json()["id"]
    stack.wait_status(r1.json()["id"], {"SUCCEEDED"})
    types = Counter(e["event_type"] for e in stack.events(r1.json()["id"]))
    assert types["RUN_QUEUED"] == 1 and types["RUN_STARTED"] == 1


def _sse(stack, run_id: str, last_event_id: int | None = None, max_events: int | None = None) -> list[int]:
    headers = {"Last-Event-ID": str(last_event_id)} if last_event_id is not None else {}
    seqs: list[int] = []
    with httpx.stream("GET", f"{stack.base}/runs/{run_id}/events/stream", headers=headers, timeout=120) as resp:
        for line in resp.iter_lines():
            if line.startswith("id: "):
                seqs.append(int(line[4:]))
                if max_events and len(seqs) >= max_events:
                    break
    return seqs


def test_sse_live_stream_and_reconnect(stack, demo):
    run = start(stack, demo, scenario="状态延迟")
    first = _sse(stack, run["id"], max_events=25)  # disconnect mid-run
    rest = _sse(stack, run["id"], last_event_id=first[-1])  # resume with Last-Event-ID
    done = stack.get(f"/runs/{run['id']}")
    assert done["status"] == "SUCCEEDED"
    assert first + rest == list(range(1, done["event_seq"] + 1)), "reconnect continues exactly after the last id"


def test_pause_takes_effect_at_step_boundary_and_resume(stack, demo):
    run = start(stack, demo, scenario="状态延迟")
    stack.wait_step(run["id"], 2)
    paused = stack.post(f"/runs/{run['id']}/pause")
    assert paused["status"] in ("PAUSING", "PAUSED")
    now = stack.wait_status(run["id"], {"PAUSED"}, timeout=60)
    seq = now["event_seq"]
    time.sleep(2.0)
    still = stack.get(f"/runs/{run['id']}")
    assert still["status"] == "PAUSED" and still["event_seq"] == seq, "no progress while paused"
    stack.post(f"/runs/{run['id']}/resume")
    done = stack.wait_status(run["id"], {"SUCCEEDED", "FAILED", "BUDGET_EXHAUSTED"})
    assert done["status"] == "SUCCEEDED"
    events = assert_consistent(stack, run["id"])
    paused_ev = next(e for e in events if e["event_type"] == "RUN_PAUSED")
    before = [e for e in events if e["seq"] < paused_ev["seq"] and e["event_type"] == "EFFECT_COMPARED"]
    assert before and before[-1]["logical_step"] == paused_ev["logical_step"], "paused after a completed step"
    assert any(e["event_type"] == "RUN_RESUMED" for e in events)


def test_cancel_keeps_evidence(stack, demo):
    run = start(stack, demo, scenario="状态延迟")
    stack.wait_step(run["id"], 3)
    res = stack.post(f"/runs/{run['id']}/cancel")
    assert res["status"] in ("CANCELLING", "CANCELLED")
    done = stack.wait_status(run["id"], {"CANCELLED"}, timeout=60)
    events = assert_consistent(stack, run["id"])
    assert events[-1]["event_type"] == "RUN_CANCELLED"
    assert any(e["event_type"] == "RUN_CANCELLING" for e in events)
    assert done["metrics"]["steps_used"]["value"] == done["last_step"]  # partial metrics preserved
    assert done["final_state"]["truth_state"], "final truth snapshot kept"
    assert stack.post(f"/runs/{run['id']}/cancel")["status"] == "CANCELLED"  # idempotent


def test_worker_crash_is_recovered_without_duplicates(stack, demo):
    run = start(stack, demo, scenario="状态延迟")
    stack.wait_step(run["id"], 4)
    stack.kill_worker()  # SIGKILL: no graceful shutdown, activity possibly mid-flight
    frozen = stack.get(f"/runs/{run['id']}")
    time.sleep(3)
    assert stack.get(f"/runs/{run['id']}")["last_step"] <= frozen["last_step"] + 1
    stack.start_worker()
    done = stack.wait_status(run["id"], {"SUCCEEDED", "FAILED", "BUDGET_EXHAUSTED"}, timeout=240)
    assert done["status"] == "SUCCEEDED"
    assert_consistent(stack, run["id"])
    diag = stack.get(f"/runs/{run['id']}/diagnostics")
    assert diag["workflow"]["found"] and diag["workflow"]["status"] == "COMPLETED"


def test_rerun_creates_new_run_with_lineage(stack, demo):
    run = start(stack, demo, strategy=Z3, seed=2)
    src = stack.wait_status(run["id"], {"SUCCEEDED"})
    rerun = stack.post(f"/runs/{run['id']}/rerun")
    assert rerun["id"] != run["id"] and rerun["source_run_id"] == run["id"]
    again = stack.wait_status(rerun["id"], {"SUCCEEDED"})
    assert again["manifest"]["seed"] == src["manifest"]["seed"] == 2
    assert again["manifest"]["model"] == src["manifest"]["model"]
    assert again["metrics"]["makespan"]["value"] == src["metrics"]["makespan"]["value"]
    assert rerun["id"] in stack.get(f"/runs/{run['id']}")["lineage"]["reruns"]


def test_budget_override_exhausts(stack, demo):
    run = start(stack, demo, budget={"max_steps": 3})
    done = stack.wait_status(run["id"], {"BUDGET_EXHAUSTED", "SUCCEEDED", "FAILED"})
    assert done["status"] == "BUDGET_EXHAUSTED" and done["last_step"] == 3
    assert done["metrics"]["makespan"]["status"] == "MISSING"


def test_model_versions_are_immutable_and_runs_keep_their_version(stack, demo):
    project = demo["project"]
    models = stack.get(f"/projects/{project}/models")
    model = next(m for m in models if m["package_id"] == "neutral-scheduling")
    v1 = stack.get(f"/models/{model['id']}/versions/1")
    ir = v1["package"]["ir"]
    ir["constants"] = [c if c["name"] != "due" else {**c, "value": {"cells": [
        {"index": ["o1"], "value": 7}, {"index": ["o2"], "value": 7}, {"index": ["o3"], "value": 8}]}}
        for c in ir["constants"]]
    v2 = stack.post(f"/models/{model['id']}/versions", {"ir": ir, "note": "relax o1 due date"})
    assert v2["version"] >= 2 and v2["digest"] != v1["digest"]
    same = stack.post(f"/models/{model['id']}/versions", {"ir": ir})
    assert same["version"] == v2["version"], "unchanged content does not create a version"
    diff = stack.get(f"/models/{model['id']}/diff", params={"from": 1, "to": v2["version"]})
    assert [(d["section"], d["name"]) for d in diff] == [("constants", "due")]
    run = start(stack, demo)  # scenario still pinned to version 1
    assert stack.get(f"/runs/{run['id']}")["manifest"]["model"]["digest"]["value"] == v1["digest"]
    stack.wait_status(run["id"], {"SUCCEEDED"})


def test_error_semantics(stack, demo):
    r = stack.client.get("/runs/run_doesnotexist")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"
    bad = stack.client.post(f"/projects/{demo['project']}/scenarios", json={
        "name": "bad", "model_version_id": demo["scenarios"]["正常调度"]["model_version_id"],
        "environment": {"plugin": {"plugin_id": "formal-lab.env.ir-world", "version": "1.0.0"},
                        "config": {"telepathy": True}},
        "participants": [{"actor_id": "d", "strategy": {"plugin": {"plugin_id": RULE, "version": "1.0.0"}}}]})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "INVALID_INPUT"
    wrong_version = stack.client.post(f"/projects/{demo['project']}/strategies",
                                      json={"plugin_id": RULE, "plugin_version": "9.9.9"})
    assert wrong_version.status_code == 404 and wrong_version.json()["error"]["code"] == "NOT_FOUND"
    v = stack.post("/models/validate", {"ir": {"name": "p", "features": ["probabilistic_effects"],
                                               "state": [{"name": "x", "type": {"kind": "bool"},
                                                          "initial": {"default": False}}],
                                               "actions": [{"name": "a"}]}})
    assert not v["valid"] and v["issues"][0]["code"] == "UNSUPPORTED_FEATURE"
    finished = stack.get(f"/projects/{demo['project']}/runs", params={"status": "SUCCEEDED"})[0]
    conflict = stack.client.post(f"/runs/{finished['id']}/pause")
    assert conflict.status_code == 409 and conflict.json()["error"]["code"] == "CONFLICT"
