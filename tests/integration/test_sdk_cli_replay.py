"""SDK / CLI / replay / matrix / Inspect import against the real stack (P1-100…P1-107, P1-124…P1-126)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from formal_lab_contracts.bundle import read_bundle
from formal_lab_sdk import Client

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]


def fal(stack, *args: str, cwd: Path | None = None, env: dict | None = None, check: bool = True):
    res = subprocess.run([sys.executable, "-m", "formal_lab_sdk.cli", *args], cwd=cwd or ROOT, text=True,
                         capture_output=True, env={**os.environ, "FAL_API_URL": stack.base, **(env or {})}, timeout=900)
    if check:
        assert res.returncode == 0, res.stdout + res.stderr
    return res


@pytest.fixture(scope="module")
def sdk(stack) -> Client:
    return Client(stack.base)


def test_sdk_builds_project_from_scratch_and_reads_results(stack, sdk):
    from formal_lab_example_scheduling.model import build_model
    from formal_lab_example_scheduling.scenarios import BUDGET, SCENARIO_CONFIGS, STOP

    project = sdk.create_project(f"sdk-{uuid.uuid4().hex[:6]}", "created through the Python SDK")
    model = sdk.create_model(project["id"], "neutral-scheduling", build_model().model_dump(mode="json"))
    scenario = sdk.create_scenario(project["id"], {
        "name": "sdk normal", "model_version_id": model["version"]["id"],
        "environment": {"plugin": {"plugin_id": "formal-lab.env.ir-world", "version": "1.0.0"},
                        "config": SCENARIO_CONFIGS["normal"]["env"]},
        "participants": [{"actor_id": "dispatcher", "strategy": {
            "plugin": {"plugin_id": "formal-lab.planner.z3-bounded", "version": "1.0.0"}, "config": {"horizon": 18}}}],
        "objectives": [{"property_id": "all_done"}], "budget": BUDGET, "seed": 4, "stop_conditions": STOP})
    run = sdk.start_run(project["id"], scenario["id"])
    seen = [ev.seq for ev in sdk.follow(run["id"])]
    done = sdk.wait(run["id"])
    assert done["status"] == "SUCCEEDED" and seen == list(range(1, done["event_seq"] + 1))
    manifest = sdk.manifest(run["id"])
    assert manifest.model.package_id == "neutral-scheduling" and manifest.seed == 4
    step = sdk.step(run["id"], 1)
    assert step["proposal"]["source"]["kind"] == "SYMBOLIC" and step["checks"][0]["result"]["verdict"] == "APPLICABLE"
    check = sdk.check(model["version"]["id"], {"kind": "INVARIANT_VIOLATION", "property_id": "on_time",
                                               "bound": {"max_steps": 12, "timeout_ms": 30000}})
    assert check.verdict == "WITNESS" and check.witness.replay == "CONFIRMED"


def test_external_plugin_registered_through_public_interfaces(stack, sdk, demo):
    plugin_ids = {p["descriptor"]["plugin_id"] for p in sdk.plugins("PLANNER")}
    assert "org.example.preference-planner" in plugin_ids
    st = sdk.create_strategy(demo["project"], f"external-{uuid.uuid4().hex[:6]}", "org.example.preference-planner",
                             {"preference": ["assign", "resume", "advance"]})
    run = sdk.start_run(demo["project"], demo["scenarios"]["正常调度"]["id"], st["id"], seed=1)
    done = sdk.wait(run["id"])
    assert done["status"] == "SUCCEEDED"
    assert {sdk.step(run["id"], n)["proposal"]["source"]["kind"] for n in (1, 2)} == {"EXTERNAL"}


def test_cli_export_offline_replay_import_and_rerun(stack, sdk, demo, tmp_path):
    res = fal(stack, "run", "start", "--project", "生产调度示例", "--scenario", "预期与模拟结果不一致",
              "--strategy", "EDD 规则", "--seed", "2", "--wait")
    run_id = res.stdout.split()[1]
    bundle_path = tmp_path / "out" / "bundle.zip"
    bundle_path.parent.mkdir()
    fal(stack, "export", run_id, "-o", str(bundle_path))
    empty = tmp_path / "empty-workdir"
    empty.mkdir()
    shutil.copy(bundle_path, empty / "bundle.zip")
    offline = {"FAL_API_URL": "http://127.0.0.1:9/api/v1"}  # unreachable: proves no server is needed
    verify = fal(stack, "replay", "verify", "bundle.zip", cwd=empty, env=offline)
    assert verify.stdout.startswith("OK formal-lab/replay-bundle@1")
    view = fal(stack, "replay", "view", "bundle.zip", cwd=empty, env=offline)
    assert "step   1" in view.stdout and "effect=DIFFERENT" in view.stdout
    step = json.loads(fal(stack, "replay", "step", "bundle.zip", "3", cwd=empty, env=offline).stdout)
    assert {"observation", "candidates", "proposal", "check", "outcome", "comparison"} <= set(step)
    bundle = read_bundle((empty / "bundle.zip").read_bytes())
    assert "contracts/v1/DIGEST.json" in bundle.info["files"] and bundle.artifacts  # contracts + snapshots inside
    assert len(bundle.events) == sdk.run(run_id)["event_seq"]

    project = sdk.create_project(f"import-{uuid.uuid4().hex[:6]}")
    # a run id is unique per server: importing a bundle of a run that still exists is a CONFLICT
    # (the fresh-database import path is covered by test_import_into_fresh_database_keeps_events_and_allows_rerun)
    conflict = fal(stack, "import", str(empty / "bundle.zip"), "--project", project["name"], check=False)
    assert conflict.returncode == 2 and "CONFLICT" in conflict.stderr
    rerun = sdk.rerun(run_id)
    again = sdk.wait(rerun["id"])
    assert again["status"] == "SUCCEEDED" and again["source_run_id"] == run_id
    original = sdk.run(run_id)
    assert original["status"] == "SUCCEEDED" and rerun["id"] in original["lineage"]["reruns"]


def test_import_into_fresh_database_keeps_events_and_allows_rerun(stack, sdk, tmp_path):
    """Export a run, delete it from the server, import the bundle, then re-run the imported run."""
    from formal_lab_api.db import Run, session_scope

    demo_project = sdk.find_project("生产调度示例")["id"]
    scenario = next(s for s in sdk.scenarios(demo_project) if s["name"] == "资源不足")
    run = sdk.start_run(demo_project, scenario["id"], seed=5)
    sdk.wait(run["id"])
    data = sdk.export_run(run["id"])
    events_before = [e.model_dump() for e in sdk.events(run["id"])]
    with session_scope() as s:
        s.delete(s.get(Run, run["id"]))
    target = sdk.create_project(f"imported-{uuid.uuid4().hex[:6]}")
    imported = sdk.import_bundle(target["id"], data)
    assert imported["imported"] and imported["status"] == "SUCCEEDED"
    assert [e.model_dump() for e in sdk.events(run["id"])] == events_before
    rerun = sdk.rerun(run["id"])
    done = sdk.wait(rerun["id"])
    assert done["status"] == "SUCCEEDED" and done["source_run_id"] == run["id"]
    assert done["metrics"]["delay_cost"]["value"] == imported["metrics"]["delay_cost"]["value"]


def test_cli_matrix_compares_two_non_stub_strategies(stack, tmp_path):
    out = tmp_path / "report.json"
    fal(stack, "matrix", "run", "--project", "生产调度示例", "--scenario", "正常调度", "--scenario", "资源不足",
        "--scenario", "预期与模拟结果不一致", "--strategy", "EDD 规则", "--strategy", "Z3 有界规划",
        "--seeds", "1,2,3", "--report", str(out))
    report = json.loads(out.read_text())
    assert len(report["cells"]) == 18 and all(c["status"] == "SUCCEEDED" for c in report["cells"])
    assert len(report["aggregates"]) == 6
    agg = report["aggregates"][0]["metrics"]
    assert agg["delay_cost"]["result"]["sample_size"] == 3 and agg["delay_cost"]["result"]["ci"]["n"] == 3
    assert agg["model_calls"]["result"]["status"] == "MISSING"  # not applicable for rule/z3: never 0
    cost = next(c for c in report["comparisons"] if c["metric_id"] == "delay_cost")
    assert cost["n_pairs"] == 9 and "test" in cost
    kinds = {k for a in report["aggregates"] for k in a["source_kinds"]}
    assert kinds == {"RULE", "SYMBOLIC"}


def test_inspect_evaluation_is_imported_and_reported(stack, sdk, tmp_path):
    env = {**os.environ, "FAL_API_URL": stack.base}
    subprocess.run([sys.executable, "-m", "inspect_ai._cli.main", "eval",  # Inspect wants a cwd-relative path
                    "examples/neutral-scheduling/src/formal_lab_example_scheduling/inspect_task.py",
                    "-T", "strategy=rule", "-T", "scenarios=normal,state-delay", "-T", "seeds=7,8",
                    "-T", f"bundle_dir={tmp_path / 'bundles'}", "--model", "mockllm/model",
                    "--log-dir", str(tmp_path / "logs"), "--display", "none"], check=True, env=env, cwd=ROOT,
                   capture_output=True, timeout=900)
    [log] = list((tmp_path / "logs").glob("*.eval"))
    res = subprocess.run([sys.executable, "-m", "formal_lab_eval.inspect_import", str(log), "--project", "生产调度示例",
                          "--api", stack.base], check=True, capture_output=True, text=True, env=env, cwd=ROOT)
    info = json.loads(res.stdout)
    assert len(info["runs"]) == 4 and info["samples_with_scores"] == 4
    report = sdk.matrix_report(info["matrix_id"])
    assert report["matrix"]["spec"]["source"] == "inspect" and len(report["cells"]) == 4
    assert report["matrix"]["spec"]["artifacts"][0]["format_version"] == "inspect_ai/eval-log"
