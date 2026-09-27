"""The Web product path through the public client only (P2-097): formal_lab_sdk.Client and `fal`, no internal
imports — new project, model, strategy configurations, a two-participant scenario, a run with its operations,
a rule set and a release, a v2 cost comparison with its CSV / Markdown report, export and offline replay."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid

import pytest
from formal_lab_example_scheduling.model import build_model
from formal_lab_sdk import Client

pytestmark = pytest.mark.integration


def test_public_client_covers_the_product_path(stack, tmp_path):
    c = Client(stack.base)
    project = c.create_project(f"SDK 纵向 {uuid.uuid4().hex[:6]}", group="sdk")
    pid = project["id"]
    model = c.create_model(pid, "line-scheduling", build_model(with_objectives=True).model_dump(mode="json"),
                           name="产线调度")
    version_id = model["version"]["id"]
    edd = c.create_strategy(pid, "EDD", "formal-lab.example.scheduling.edd-dispatch", {}, "1.0.0")
    z3 = c.create_strategy(pid, "Z3", "formal-lab.planner.z3-bounded", {"horizon": 18}, "1.1.0")
    scenario = c.create_scenario(pid, {
        "name": "两名调度员", "model_version_id": version_id,
        "environment": {"plugin": {"plugin_id": "formal-lab.env.ir-world", "version": "1.1.0"}, "config": {}},
        "participants": [{"actor_id": "a", "role": "dispatcher", "strategy": {
                              "plugin": {"plugin_id": "formal-lab.example.scheduling.edd-dispatch", "version": "1.0.0"},
                              "config": {}}},
                         {"actor_id": "b", "role": "dispatcher", "strategy": {
                              "plugin": {"plugin_id": "formal-lab.planner.z3-bounded", "version": "1.1.0"},
                              "config": {"horizon": 18}}}],
        "turns": {"mode": "ROUND_ROBIN", "observation_timing": "ROUND_START", "conflict_policy": "REVALIDATE"},
        "termination": {"joint_goal": "all_done", "on_no_action": "SKIP_ACTOR", "no_progress_limit": 12},
        "budget": {"max_steps": 60}, "seed": 1})
    run = c.start_run(pid, scenario["id"], seed=1)
    done = c.wait(run["id"], timeout=300)
    assert done["status"] == "SUCCEEDED" and done["termination_reason"] == "JOINT_GOAL_REACHED"
    assert set(done["actor_usage"]) == {"a", "b"}
    ops = c.operations(run["id"])
    assert ops and all(o["state"] in ("COMPLETED", "RECONCILED") for o in ops)
    # rules and a release of the model version
    rs = c.save_ruleset(pid, version_id, "reviews", [{
        "rule_id": "pause_on_difference", "trigger": {"events": ["EFFECT_COMPARED"]},
        "condition": {"op": "gt", "args": [{"op": "ref", "name": "ev_different_count"}, {"op": "const", "value": 0}]},
        "priority": 10, "outcome": "PAUSE", "message": "pause on an effect difference"}])
    release = c.release(version_id, ruleset=("reviews", rs["version"]), regression="model", horizon=4)
    assert release["status"] == "RELEASED", release["record"]["reasons"]
    assert release["record"]["ruleset"]["ruleset_id"] == "reviews"
    assert c.releases(pid)[-1]["release_id"] == release["release_id"]
    # v2 cost comparison: both participants EDD vs both Z3, dev / acceptance seeds
    mx = c.create_matrix_v2(pid, {"name": "cost", "scenarios": [scenario["id"]],
                                  "participants": [{"*": edd["id"]}, {"*": z3["id"]}],
                                  "seeds": {"dev": [1], "acceptance": [2, 3]}, "max_parallel": 2})
    cells = c.wait_matrix(mx["matrix"]["id"], timeout=900)
    assert len(cells) == 6 and all(x["status"] == "DONE" for x in cells)
    rep = c.matrix_report(mx["matrix"]["id"])
    acc = rep["splits"]["acceptance"]
    assert acc["outcomes"]["denominator_cells"] == 4 and any(x["kind"] == "method" for x in acc["comparisons"])
    assert c.matrix_report(mx["matrix"]["id"], "csv").startswith("section,split")
    assert "## Conclusions" in c.matrix_report(mx["matrix"]["id"], "md")
    # export → offline replay in an empty directory with `fal`
    bundle = tmp_path / "run.replay.zip"
    bundle.write_bytes(c.export_run(run["id"]))
    env = {k: v for k, v in os.environ.items() if not k.startswith("FAL_API")}
    res = subprocess.run([sys.executable, "-m", "formal_lab_sdk.cli", "replay", "turns", bundle.name, "--actor", "b"],
                         cwd=tmp_path, env=env, text=True, capture_output=True, timeout=120)
    assert res.returncode == 0 and res.stdout.strip() and all(" b " in f" {line} " for line in res.stdout.splitlines())
