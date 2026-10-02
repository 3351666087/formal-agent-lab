"""Phase 4A (A4) on the durable path (Temporal + PostgreSQL, API and worker subprocesses).

1. Joint rounds on the subprocess environment: the receiver may only put away, so it is idle in most rounds while the
   picker keeps the world moving; paused inside a round and the worker SIGKILLed — every submitted batch is exactly
   one world step of the child process's own log, recorded as WORLD_STEPPED apart from the members and the batch.
2. Matrix reuse: an identical matrix reuses the deterministic cell and re-runs the model cell (its model version is
   not pinned); a changed budget is new execution for both; every decision carries its reason, and the report counts
   reuse, new runs and sampling apart.
"""

from __future__ import annotations

import json
import time
import uuid
from collections import Counter
from pathlib import Path

import pytest
from formal_lab_strategies.protocol_server import MODEL, ProtocolTestServer

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]


def of(events, kind):
    return [e for e in events if e["event_type"] == kind]


def pause_inside_a_round(stack, run_id: str) -> dict:
    """Pause right after a submission step so that the next (proposal) step is the one in flight."""
    for at_least in range(2, 40, 2):
        deadline = time.time() + 120
        while True:
            run = stack.get(f"/runs/{run_id}")
            assert run["status"] not in ("SUCCEEDED", "FAILED", "CANCELLED", "BUDGET_EXHAUSTED"), run["status"]
            if run["status"] == "RUNNING" and run["last_step"] >= at_least and run["last_step"] % 2 == 0:
                break
            assert time.time() < deadline
            time.sleep(0.01)
        stack.post(f"/runs/{run_id}/pause")
        paused = stack.wait_status(run_id, {"PAUSED"}, timeout=120)
        if paused["last_step"] % 2 == 1:
            return paused
        stack.post(f"/runs/{run_id}/resume")
    raise AssertionError("could not pause inside a round")


def test_joint_rounds_on_the_subprocess_environment_match_its_world_steps(stack):
    wh = next(p for p in stack.get("/projects") if p["name"] == "仓储分配示例")
    base = next(s for s in stack.get(f"/projects/{wh['id']}/scenarios") if s["name"] == "仓储：收货员 + 拣货员同步批次")
    log = ROOT / "var" / "it-world" / f"{uuid.uuid4().hex[:8]}.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    m = base["manifest"]
    participants = json.loads(json.dumps(m["participants"]))
    participants[0]["scope"] = {"action_types": ["putaway"]}  # the receiver cannot wait by ticking
    body = {"name": f"子进程环境同步批次 {uuid.uuid4().hex[:6]}", "model_version_id": base["model_version_id"],
            "environment": {"plugin": {"plugin_id": "formal-lab.example.subprocess-world", "version": "1.0.0"},
                            "config": {"world": m["environment"]["config"], "world_log": str(log)}},
            "participants": participants, "objectives": m.get("objectives", []), "budget": m["budget"],
            "seed": 0, "turns": m["turns"], "termination": m["termination"]}
    sc = stack.post(f"/projects/{wh['id']}/scenarios", body, expect=201)
    run = stack.post(f"/projects/{wh['id']}/runs", {"scenario_id": sc["id"], "seed": 0})
    rid = run["id"]
    pause_inside_a_round(stack, rid)
    stack.post(f"/runs/{rid}/resume")
    stack.kill_worker()
    time.sleep(3)
    stack.start_worker()
    done = stack.wait_status(rid, {"SUCCEEDED", "FAILED", "BUDGET_EXHAUSTED"}, timeout=600)
    assert done["status"] == "SUCCEEDED", done.get("status_reason")

    events = stack.events(rid)
    keys = [e["idempotency_key"] for e in events]
    assert len(keys) == len(set(keys)), "no duplicated events after recovery"
    submitted = [e["payload"]["batch"] for e in of(events, "BATCH_SUBMITTED")]
    worlds = [e["payload"] for e in of(events, "WORLD_STEPPED")]
    lines = [json.loads(x) for x in log.read_text().splitlines()]
    unique = list(dict.fromkeys((x["world_step"], x["operation_id"]) for x in lines))
    # every submitted batch is one world step of the child's own log, round by round (a re-execution after the kill
    # repeats a logged (world_step, operation) pair: counted, never a new world step)
    assert [(b["world_step"], b["operation_id"]) for b in submitted] == unique
    assert [w["world_step"] for w in worlds] == [b["world_step"] for b in submitted] == list(range(1, len(submitted) + 1))
    assert all(w["source"] == "environment report" for w in worlds)
    status = Counter((mm["actor_id"], mm["status"]) for b in submitted for mm in b["members"])
    skipped = Counter((e["actor_id"], e["payload"]["retired"]) for e in of(events, "TURN_SKIPPED"))
    assert status[("receiver", "PASSED")] > 0 and status[("receiver", "PROPOSED")] > 0
    assert status[("picker", "PROPOSED")] == len(submitted)
    assert skipped[("receiver", False)] == status[("receiver", "PASSED")] and not skipped[("receiver", True)]
    turn = done.get("turn") or {}
    assert (turn.get("skipped") or {}).get("receiver") == status[("receiver", "PASSED")]


def _cells_done(stack, mid: str, timeout: float = 900) -> list[dict]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        cells = stack.get(f"/matrices/{mid}/cells")
        if all(c["status"] in ("DONE", "FAILED", "CANCELLED") for c in cells):
            return cells
        time.sleep(1)
    raise AssertionError(f"matrix {mid} did not finish")


def test_matrix_reuse_identical_changed_and_conservative(stack, demo):
    pid = demo["project"]
    server = ProtocolTestServer().start()
    try:
        sid = stack.post(f"/scenarios/{demo['scenarios']['正常调度']['id']}/copy",
                         {"name": f"A4 复用验证 {uuid.uuid4().hex[:6]}"})["id"]  # no seeded name inside it
        sc = stack.get(f"/scenarios/{sid}")
        body = {k: v for k, v in sc["manifest"].items()
                if k not in ("scenario_id", "revision", "model", "contract_version")}
        body["participants"][0]["view"] = {"settings": {"FAL_LLM_BASE_URL": server.base_url,
                                                        "FAL_LLM_API_KEY": "protocol-test-only",
                                                        "FAL_LLM_MODEL": MODEL}}
        r = stack.client.put(f"/scenarios/{sid}", json={**body, "model_version_id": sc["model_version_id"]})
        assert r.status_code == 200, r.text
        edd = demo["strategies"]["formal-lab.example.scheduling.edd-dispatch"]["id"]
        llm = demo["strategies"]["formal-lab.planner.llm"]["id"]
        spec = {"version": 2, "name": "reuse A", "scenarios": [sid], "participants": [{"*": edd}, {"*": llm}],
                "seeds": [1], "budgets": [{"max_steps": 40}]}
        first = stack.post(f"/projects/{pid}/matrices", spec)
        assert first["cells"] == {"queued": 2, "reused": 0, "skipped": 0, "rerun_conservative": 0}
        a = {c["labels"]["participants"]: c for c in _cells_done(stack, first["matrix"]["id"])}
        requests_after_a = len(server.requests)
        assert requests_after_a > 0

        same = stack.post(f"/projects/{pid}/matrices", {**spec, "name": "reuse B (identical)"})
        assert same["cells"] == {"queued": 1, "reused": 1, "skipped": 0, "rerun_conservative": 1}
        b = {c["labels"]["participants"]: c for c in _cells_done(stack, same["matrix"]["id"])}
        rule_b, llm_b = next(v for k, v in b.items() if "EDD" in k), next(v for k, v in b.items() if "LLM" in k)
        rule_a, llm_a = next(v for k, v in a.items() if "EDD" in k), next(v for k, v in a.items() if "LLM" in k)
        assert rule_b["reuse"]["decision"] == "REUSED" and rule_b["run_id"] == rule_a["run_id"]
        assert "same full configuration" in rule_b["reuse"]["reason"]
        assert llm_b["reuse"]["decision"] == "RERUN" and llm_b["run_id"] != llm_a["run_id"]
        assert "not pinned" in llm_b["reuse"]["reason"] and len(server.requests) > requests_after_a
        assert llm_b["config_digest"] == llm_a["config_digest"]  # the same configuration, sampled again

        changed = stack.post(f"/projects/{pid}/matrices", {**spec, "name": "reuse C (budget)",
                                                           "budgets": [{"max_steps": 35}]})
        assert changed["cells"] == {"queued": 2, "reused": 0, "skipped": 0, "rerun_conservative": 0}
        c = _cells_done(stack, changed["matrix"]["id"])
        assert {x["reuse"]["decision"] for x in c} == {"NEW", "RERUN"}
        assert all(x["key_parts"]["budget"] != rule_a["key_parts"]["budget"] for x in c)

        report = stack.get(f"/matrices/{same['matrix']['id']}/report")
        o = report["splits"]["acceptance"]["outcomes"]
        assert [r["cell_id"] for r in o["reused"]] == [rule_b["cell_id"]] and o["new_runs"] == 1
        assert o["sampling"] == {"DETERMINISTIC": 1, "RESAMPLED": 1}
        assert o["success"]["denominator"] == 2 and "planned cell" in o["success"]["definition"]
        assert {"split", "providers", "runtime"} <= set(rule_b["key_parts"])
    finally:
        server.stop()
