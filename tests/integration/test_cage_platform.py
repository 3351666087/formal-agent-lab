"""Phase 4B (B2): CAGE Challenge 4 on the durable platform path (Temporal + PostgreSQL, API and worker processes).

1. Discovery and a real platform run: the CAGE model is created through the API from CybORG's own `describe`, the
   environment / driver / blue planners / evaluator are found in the plugin catalog; a react run is paused inside a
   round, the worker SIGKILLed and restarted — the run completes, and its committed world steps equal the native
   direct path driven with the same blue actions (state + RNG digests included). Blue's participant download holds
   none of the referee data (red footholds, green results).
2. The platform matrix: the same two scenario variants (dev: FiniteStateRedAgent, holdout: DiscoveryFSRed, fixed
   before any tuning) x three blue methods (A: official baseline SleepAgent mapping, B: constant Monitor, C:
   platform react rule) x three shared seeds; the paired report (reference = the official baseline) is written as
   evidence with its metric definitions; one cell re-run gives the same metrics.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.cage]
ROOT = Path(__file__).resolve().parents[2]
EV = ROOT / os.environ.get("FAL_EVIDENCE_DIR", "docs/execution/evidence/phase4")
STEPS = 30  # the recovery / trajectory run; the official CAGE 4 evaluation runs 500 world steps
MATRIX_STEPS = 100  # the comparison: long enough for mission phases and multi-tick restores to play out
SEEDS = [1, 2, 3]


@pytest.fixture(scope="module")
def cage(stack):
    from formal_lab_env_cage import bridge, model, scenarios

    why = bridge.available()
    if why:
        pytest.skip(why)
    describe = bridge.describe()
    pkg = model.package(describe)
    project = stack.post("/projects", {"name": f"CAGE 4 平台接入 {uuid.uuid4().hex[:6]}"})
    pid = project["id"]
    payload = {"semantic_profile": model.PROFILE, "namespace": model.NAMESPACE, "schema_id": model.SCHEMA_ID,
               "data": pkg.payload.data, "source_format": "cage4-describe/v1"}
    created = stack.post(f"/projects/{pid}/models", {"package_id": model.PACKAGE_ID, "name": "CAGE 4 蓝方接口",
                                                      "payload": payload})
    mv = created["version"]["id"]
    names = {"sleep": "A 官方基线 · SleepAgent 映射", "monitor": "B 恒定监控 · Monitor",
             "react": "C 平台规则 · 告警响应"}
    strategies = {k: stack.post(f"/projects/{pid}/strategies", {"plugin_id": scenarios.POLICIES[k],
                                                                 "name": names[k], "config": {}})["id"]
                  for k in names}

    def scenario(variant: str, policy: str, world_log: str | None = None, steps: int = STEPS) -> str:
        sc = scenarios.scenario(pkg, policy=policy, variant=variant, steps=steps, seed=SEEDS[0], world_log=world_log)
        body = {k: v for k, v in sc.model_dump(mode="json").items()
                if k not in ("scenario_id", "revision", "model", "contract_version")}
        body["name"] = f"CAGE 4 · {variant} · {uuid.uuid4().hex[:4]}"
        return stack.post(f"/projects/{pid}/scenarios", {**body, "model_version_id": mv}, expect=201)["id"]

    return {"pid": pid, "mv": mv, "pkg": pkg, "strategies": strategies, "scenario": scenario, "describe": describe}


def _pause_inside_a_round(stack, rid: str) -> dict:
    for at_least in range(7, 60, 5):
        deadline = time.time() + 300
        while True:
            run = stack.get(f"/runs/{rid}")
            assert run["status"] not in ("SUCCEEDED", "FAILED", "CANCELLED", "BUDGET_EXHAUSTED"), run["status"]
            if run["status"] == "RUNNING" and run["last_step"] >= at_least:
                break
            assert time.time() < deadline
            time.sleep(0.05)
        stack.post(f"/runs/{rid}/pause")
        paused = stack.wait_status(rid, {"PAUSED"}, timeout=300)
        if paused["last_step"] % 5 != 0:  # members of a round proposed, the batch not yet submitted
            return paused
        stack.post(f"/runs/{rid}/resume")
    raise AssertionError("could not pause inside a round")


@pytest.mark.timeout(1800)
def test_cage_run_survives_a_worker_kill_and_matches_the_native_path(stack, cage):
    from formal_lab_env_cage import bridge, scenarios, trajectory

    catalog = {p["descriptor"]["plugin_id"] for p in stack.get("/plugins")}
    assert {"formal-lab.env.cage4", "formal-lab.driver.cage4", "formal-lab.cage4.blue-react",
            "formal-lab.cage4.metrics"} <= catalog
    log = ROOT / "var" / "it-cage" / f"{uuid.uuid4().hex[:8]}.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    sid = cage["scenario"]("dev", "react", world_log=str(log))
    rid = stack.post(f"/projects/{cage['pid']}/runs", {"scenario_id": sid, "seed": 2})["id"]
    paused = _pause_inside_a_round(stack, rid)
    stack.post(f"/runs/{rid}/resume")
    stack.kill_worker()
    time.sleep(3)
    stack.start_worker()
    done = stack.wait_status(rid, {"SUCCEEDED", "FAILED", "BUDGET_EXHAUSTED"}, timeout=1200)
    assert done["status"] == "SUCCEEDED", done.get("status_reason")

    platform = list({json.loads(x)["world_step"]: json.loads(x) for x in log.read_text().splitlines()}.values())
    native = bridge.native(seed=2, steps=STEPS, controlled=scenarios.BLUE,
                           actions=trajectory.platform_actions(platform))["steps"]
    cmp = trajectory.compare(native, platform)
    assert cmp["equal"], cmp["first_difference"]

    events = stack.events(rid)
    submitted = [e["payload"]["batch"] for e in events if e["event_type"] == "BATCH_SUBMITTED"]
    assert [b["world_step"] for b in submitted] == list(range(1, len(platform) + 1))
    assert all(b["automatic"] for b in submitted)  # native red / green acted inside every world step
    metrics = {m["metric_id"]: m for e in events if e["event_type"] == "METRICS_COMPUTED"
               for m in e["payload"]["metrics"]}
    assert metrics["native_blue_reward"]["status"] == "OK" and metrics["blue_agent_count"]["value"] == 5

    grant = stack.post(f"/runs/{rid}/participants/blue_agent_0/access", expect=201)
    bundle = stack.client.get("/participant/export", headers={"Authorization": f"Bearer {grant['token']}"})
    assert bundle.status_code == 200, bundle.text
    text = bundle.text
    assert "referee_timeline" not in text and "red_foothold" not in text and "green_totals" not in text
    (EV / "b2-platform-run.json").write_text(json.dumps({
        "run_id": rid, "paused_at_global_step": paused["last_step"], "worker_killed_and_restarted": True,
        "status": done["status"], "world_steps": len(platform), "native_vs_platform": {
            k: cmp[k] for k in ("equal", "world_steps", "equal_world_steps", "first_difference", "termination",
                                "reward_totals", "compared_fields")},
        "batches": len(submitted), "metrics": {k: {"status": v["status"], "value": v["value"]} for k, v in
                                               metrics.items()},
        "participant_download_has_referee_data": False}, indent=2, ensure_ascii=False) + "\n")


def _cells_done(stack, mid: str, timeout: float = 3600) -> list[dict]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        cells = stack.get(f"/matrices/{mid}/cells")
        if all(c["status"] in ("DONE", "FAILED", "CANCELLED") for c in cells):
            return cells
        time.sleep(2)
    raise AssertionError(f"matrix {mid} did not finish")


@pytest.mark.timeout(5400)
def test_cage_paired_matrix_on_the_platform(stack, cage):
    st = cage["strategies"]
    dev, holdout = cage["scenario"]("dev", "sleep", steps=MATRIX_STEPS), cage["scenario"]("holdout", "sleep",
                                                                                             steps=MATRIX_STEPS)
    spec = {"version": 2, "name": "CAGE 4 蓝方方法配对比较", "scenarios": [dev, holdout],
            "participants": [{"*": st["sleep"]}, {"*": st["monitor"]}, {"*": st["react"]}],
            "seeds": SEEDS, "budgets": [{"max_steps": MATRIX_STEPS * 5 + 10}]}
    made = stack.post(f"/projects/{cage['pid']}/matrices", spec)
    mid = made["matrix"]["id"]
    assert made["cells"]["queued"] == 2 * 3 * len(SEEDS)
    cells = _cells_done(stack, mid)
    report = stack.get(f"/matrices/{mid}/report")
    md = stack.client.get(f"/matrices/{mid}/report", params={"format": "md"}).text
    csv = stack.client.get(f"/matrices/{mid}/report", params={"format": "csv"}).text
    section = report["splits"]["acceptance"]
    outcomes = section["outcomes"]
    assert outcomes["success"]["denominator"] == len(cells)
    comparisons = [c for c in section.get("comparisons", []) if c.get("dimension") == "participants"]
    # reference = the official baseline (every blue agent on A), compared with B and C on the same scenario / seed
    assert comparisons and all(c["a"].startswith("*=A ") for c in comparisons)
    assert {c["b"][:4] for c in comparisons} == {"*=B ", "*=C "}

    # re-run one cell with the same seed: a deterministic environment and rule policies give the same metrics
    from formal_lab_env_cage import scenarios

    one = next(c for c in cells if c["status"] == "DONE" and c["labels"]["participants"].startswith("*=C "))
    run = stack.get(f"/runs/{one['run_id']}")
    again = stack.post(f"/projects/{cage['pid']}/runs", {
        "scenario_id": run["scenario_id"], "seed": one["seed"], "budget": {"max_steps": MATRIX_STEPS * 5 + 10},
        "participant_strategies": {a: st["react"] for a in scenarios.BLUE}})
    rerun = stack.wait_status(again["id"], {"SUCCEEDED", "FAILED"}, timeout=2400)

    def metrics(rid: str) -> dict:
        evs = stack.events(rid)
        return {m["metric_id"]: m["value"] for e in evs if e["event_type"] == "METRICS_COMPUTED"
                for m in e["payload"]["metrics"]}

    EV.mkdir(parents=True, exist_ok=True)
    (EV / "b2-paired-report.md").write_text(md)
    (EV / "b2-paired-report.csv").write_text(csv)
    (EV / "b2-matrix.json").write_text(json.dumps({
        "matrix_id": mid, "spec": spec, "steps_per_episode": MATRIX_STEPS, "seeds": SEEDS,
        "variants": {"dev": "FiniteStateRedAgent (official Scenario4 red)",
                     "holdout": "DiscoveryFSRed (official variant; fixed before tuning, never used to adjust a policy)"},
        "methods": {"A": "official baseline: SleepAgent mapped (blue-sleep)",
                    "B": "constant Monitor (blue-monitor; CybORG's MonitorAgent class cannot run in Scenario4)",
                    "C": "platform rule (blue-react): own alerts only"},
        "not_applicable": {"cc4BlueRandomAgent": "draws from CybORG's RNG: a platform copy would not be the same agent",
                           "RL agents": "need torch / ray (optional track, not installed)",
                           "MAL / LLM strategies": "no cage4_v1 implementation — not compared under the same name"},
        "cells": [{k: c.get(k) for k in ("cell_id", "status", "seed", "labels", "run_id")} for c in cells],
        "report": report, "rerun": {"cell": one["cell_id"], "first": metrics(one["run_id"]),
                                    "again": metrics(again["id"]), "status": rerun["status"]},
        "sample_note": "3 shared seeds x 2 scenario variants: an engineering sample; it supports no claim of "
                       "convergence or significant advantage; a different seed is a different generated network of "
                       "the same scenario, not another topology family"},
        indent=2, ensure_ascii=False, default=str) + "\n")
    assert rerun["status"] == "SUCCEEDED"
    first, second = metrics(one["run_id"]), metrics(again["id"])
    timing = {"wall_seconds"}  # elapsed time is not a property of the episode
    assert {k: v for k, v in first.items() if k not in timing} == {k: v for k, v in second.items() if k not in timing}
