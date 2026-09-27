"""Find a difference → locate it in the model → edit a new version → re-check → compare in a new experiment
(P2-072 … P2-077), through the API and `fal`, on the durable path."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from formal_lab_contracts import ModelPackage
from formal_lab_env.ir_world import truth_model_ir

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]


def fal(stack, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    res = subprocess.run([sys.executable, "-m", "formal_lab_sdk.cli", *args], cwd=ROOT, text=True, capture_output=True,
                         env={**os.environ, "FAL_API_URL": stack.base}, timeout=600)
    if check:
        assert res.returncode == 0, res.stdout + res.stderr
    return res


def differences(stack, run_id: str) -> int:
    return sum(1 for e in stack.events(run_id) if e["event_type"] == "EFFECT_COMPARED"
               and e["payload"]["comparison"]["verdict"] == "DIFFERENT")


def test_difference_to_released_revision_to_new_experiment(stack, demo):
    pid = demo["project"]
    mismatch = demo["scenarios"]["预期与模拟结果不一致"]
    rule = demo["strategies"]["formal-lab.example.scheduling.edd-dispatch"]["id"]
    # 1. the difference: a run on the original model version
    old_run = stack.post(f"/projects/{pid}/runs", {"scenario_id": mismatch["id"], "strategy_config_id": rule,
                                                   "seed": 1, "config": {"initial_check_horizon": 0}})
    old = stack.wait_status(old_run["id"], {"SUCCEEDED", "FAILED", "BUDGET_EXHAUSTED"}, timeout=300)
    assert old["status"] == "SUCCEEDED" and differences(stack, old["id"]) > 0
    out = fal(stack, "run", "suggestions", old["id"]).stdout
    assert "advance" in out and "degraded" in out and "case reg_" in out
    suggestions = stack.get(f"/runs/{old['id']}/revision-suggestions")
    case_ids = [s["regression_case_id"] for s in suggestions]
    assert case_ids and all(case_ids)
    listed = fal(stack, "regression", "list", "--project", pid, "--package-id", "neutral-scheduling").stdout
    assert case_ids[0] in listed
    # 2. locate + edit: the suggestion names the constant the action's effects read; the modeller sets it
    v1_id = mismatch["model_version_id"]
    v1 = next(v for m in stack.get(f"/projects/{pid}/models") for v in [stack.get(f"/models/{m['id']}/versions/1")]
              if v["id"] == v1_id)
    pkg = ModelPackage.model_validate(v1["package"])
    fixed = json.loads(truth_model_ir(pkg, {"degraded[m2]": True}).model_dump_json())
    v2 = stack.post(f"/models/{v1['model_id']}/versions", {"ir": fixed, "note": "m2 is degraded (from run "
                                                                               f"{old['id']})", "parent_version": 1})
    assert v2["version"] > 1 and v2["digest"] != v1["digest"]
    # 3. re-check: the old version is rejected by its own regression cases, the new one is released
    rejected = fal(stack, "release", "check", v1_id, "--regression", ",".join(case_ids), "--horizon", "4", check=False)
    assert rejected.returncode == 1 and "REJECTED" in rejected.stdout and "FAIL" in rejected.stdout
    released = fal(stack, "release", "check", v2["id"], "--regression", ",".join(case_ids), "--horizon", "4")
    assert "RELEASED" in released.stdout
    release_id = released.stdout.split()[0]
    record = stack.get(f"/releases/{release_id}")["record"]
    assert record["log"] and record["bounds"] and all(r["status"] == "PASS" for r in record["regression"])
    assert fal(stack, "regression", "replay", case_ids[0], "--model-version", v2["id"]).returncode == 0
    assert fal(stack, "regression", "replay", case_ids[0], "--model-version", v1_id, check=False).returncode == 1
    # 4. new experiment on the released version; the old run keeps explaining the original version
    body = {k: v for k, v in mismatch["manifest"].items()
            if k not in ("scenario_id", "revision", "model", "contract_version", "extensions")}
    new_sc = stack.post(f"/projects/{pid}/scenarios", {**body, "name": "预期与模拟：修订后的模型",
                                                       "model_version_id": v2["id"]})
    stack.post(f"/projects/{pid}/runs", {"scenario_id": mismatch["id"], "strategy_config_id": rule, "seed": 1,
                                         "release_id": release_id}, expect=422)  # release of another version
    new_run = stack.post(f"/projects/{pid}/runs", {"scenario_id": new_sc["id"], "strategy_config_id": rule, "seed": 1,
                                                   "release_id": release_id, "config": {"initial_check_horizon": 0}})
    new = stack.wait_status(new_run["id"], {"SUCCEEDED", "FAILED", "BUDGET_EXHAUSTED"}, timeout=300)
    assert new["status"] == "SUCCEEDED" and differences(stack, new["id"]) == 0
    assert new["manifest"]["release"]["release_id"] == release_id
    assert new["manifest"]["model"]["version"] == v2["version"]
    again = stack.get(f"/runs/{old['id']}")
    assert again["manifest"]["model"]["version"] == 1 and differences(stack, old["id"]) > 0


def test_a_rule_pauses_the_affected_plan_on_an_effect_difference(stack, demo):
    """P2-070 / P2-075: a released rule set (EFFECT_COMPARED, ev_different_count > 0 → PAUSE) pauses the run at the
    first difference; the decision and its priority explanation are on the record; the run resumes."""
    pid = demo["project"]
    mismatch = demo["scenarios"]["预期与模拟结果不一致"]
    rules = [{"rule_id": "pause_on_difference", "trigger": {"events": ["EFFECT_COMPARED"]},
              "condition": {"op": "gt", "args": [{"op": "ref", "name": "ev_different_count"},
                                                 {"op": "const", "value": 0}]},
              "priority": 10, "outcome": "PAUSE", "message": "effects differ from the model: review before going on"}]
    bad = stack.client.post(f"/projects/{pid}/rulesets", json={
        "model_version_id": mismatch["model_version_id"], "ruleset_id": "broken",
        "rules": [{**rules[0], "rule_id": "b", "condition": {"op": "var", "name": "nowhere", "index": []}}]})
    assert bad.status_code == 422 and bad.json()["error"]["field_errors"]
    saved = stack.post(f"/projects/{pid}/rulesets", {"model_version_id": mismatch["model_version_id"],
                                                     "ruleset_id": "difference-review", "rules": rules})
    body = {k: v for k, v in mismatch["manifest"].items()
            if k not in ("scenario_id", "revision", "model", "contract_version", "extensions")}
    sc = stack.post(f"/projects/{pid}/scenarios", {**body, "name": f"差异即暂停 v{saved['version']}",
                                                   "model_version_id": mismatch["model_version_id"],
                                                   "rules": {"ruleset_id": "difference-review",
                                                             "version": saved["version"]}})
    run = stack.post(f"/projects/{pid}/runs", {"scenario_id": sc["id"], "seed": 1,
                                               "config": {"initial_check_horizon": 0}})
    paused = stack.wait_status(run["id"], {"PAUSED", "SUCCEEDED", "FAILED"}, timeout=300)
    assert paused["status"] == "PAUSED" and "pause_on_difference" in (paused["status_reason"] or "")
    decisions = [e for e in stack.events(run["id"]) if e["event_type"] == "RULE_EVALUATED"]
    assert decisions and decisions[-1]["payload"]["decision"]["outcome"] == "PAUSE"
    assert decisions[-1]["payload"]["decision"]["priority_explanation"]
    stack.post(f"/runs/{run['id']}/resume")
    stack.wait_status(run["id"], {"PAUSED", "SUCCEEDED"}, timeout=300)
