"""Matrix v2 on the durable path (P2-080 … P2-085): full cell configurations with stable ids, a queue that survives a
killed worker and a lost queue workflow, reruns of failed cells, incremental merge with reuse of completed cells,
and the v2 report (splits, per-dimension comparisons, probes/evaluators with sources) as JSON, CSV and Markdown."""

from __future__ import annotations

import asyncio
import json
import time
import uuid

import pytest

pytestmark = pytest.mark.integration


def wait_cells(stack, matrix_id: str, pred, timeout: float = 600) -> list[dict]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        cells = stack.get(f"/matrices/{matrix_id}/cells")
        if pred(cells):
            return cells
        time.sleep(1)
    raise AssertionError(f"matrix {matrix_id} cells did not reach the condition: "
                         f"{[(c['cell_id'], c['status']) for c in stack.get(f'/matrices/{matrix_id}/cells')]}")


def finished(cells: list[dict]) -> bool:
    return all(c["status"] in ("DONE", "FAILED", "CANCELLED") for c in cells)


def terminate(workflow_id: str) -> None:
    from formal_lab_api.settings import get_settings
    from temporalio.client import Client

    async def go():
        s = get_settings()
        client = await Client.connect(s.temporal_address, namespace=s.temporal_namespace)
        await client.get_workflow_handle(workflow_id).terminate("test: the queue driver is lost")

    asyncio.run(go())


def test_matrix_v2_queue_recovery_merge_and_report(stack, demo):
    pid = demo["project"]
    # a copy of the scenario per session: completed cells of the same configuration are reused across matrices of a
    # project (by design, checked below with merge), so on a database kept from an earlier session a matrix of the
    # original scenario would start fully reused
    delay = stack.post(f"/scenarios/{demo['scenarios']['状态延迟']['id']}/copy",
                       {"name": f"状态延迟（矩阵 v2 测试 {uuid.uuid4().hex[:6]}）"})["id"]
    strategies = {s["name"]: s["id"] for s in stack.get(f"/projects/{pid}/strategies")}
    edd, task = strategies["EDD 规则"], strategies["任务计划（规则生成）"]
    spec = {"version": 2, "name": "delay ablation", "scenarios": [delay],
            "participants": [{"*": edd}, {"*": task}],
            "ablations": [{}, {"label": "no-observation-delay", "env": {"observation": {"delay_steps": None}}}],
            "seeds": {"dev": [1], "acceptance": [2, 3]}, "max_parallel": 2}
    res = stack.post(f"/projects/{pid}/matrices", spec)
    mid = res["matrix"]["id"]
    assert res["cells"] == {"queued": 12, "reused": 0, "skipped": 0, "rerun_conservative": 0}
    cells = stack.get(f"/matrices/{mid}/cells")
    assert len({c["cell_id"] for c in cells}) == 12 and {c["split"] for c in cells} == {"dev", "acceptance"}
    # at most max_parallel cells run at once; kill the worker mid-matrix
    wait_cells(stack, mid, lambda cs: sum(c["status"] == "DONE" for c in cs) >= 2)
    assert sum(c["status"] == "RUNNING" for c in stack.get(f"/matrices/{mid}/cells")) <= 2
    stack.kill_worker()
    time.sleep(2)
    stack.start_worker()
    # lose the queue driver itself: the database keeps the queue, /resume continues it
    wait_cells(stack, mid, lambda cs: sum(c["status"] == "DONE" for c in cs) >= 4)
    terminate(f"matrix-{mid}")
    time.sleep(3)
    before = stack.get(f"/matrices/{mid}/cells")
    assert any(c["status"] == "QUEUED" for c in before)
    stack.post(f"/matrices/{mid}/resume")
    # a running cell is cancelled → FAILED → rerun-failed queues it again
    running = wait_cells(stack, mid, lambda cs: any(c["status"] == "RUNNING" for c in cs))
    victim = next(c for c in running if c["status"] == "RUNNING")
    stack.post(f"/runs/{victim['run_id']}/cancel")
    cells = wait_cells(stack, mid, finished)
    assert next(c for c in cells if c["cell_id"] == victim["cell_id"])["status"] == "FAILED"
    assert stack.post(f"/matrices/{mid}/rerun-failed")["requeued"] >= 1
    cells = wait_cells(stack, mid, lambda cs: finished(cs) and all(c["status"] == "DONE" for c in cs))
    rerun = next(c for c in cells if c["cell_id"] == victim["cell_id"])
    assert rerun["attempts"] == 2 and rerun["run_id"] != victim["run_id"]
    # incremental merge: one more acceptance seed → 4 new cells; merging it again adds nothing
    merged = stack.post(f"/matrices/{mid}/cells", {"seeds": {"dev": [1], "acceptance": [2, 3, 4]}})
    assert merged["cells"] == {"queued": 4, "reused": 0, "skipped": 12, "rerun_conservative": 0}
    again = stack.post(f"/matrices/{mid}/cells", {"seeds": {"dev": [1], "acceptance": [2, 3, 4]}})
    assert again["cells"]["queued"] == 0 and again["cells"]["skipped"] == 16
    wait_cells(stack, mid, lambda cs: len(cs) == 16 and all(c["status"] == "DONE" for c in cs))
    # a new matrix sharing configurations reuses the completed cells (same cell ids, same runs)
    other = stack.post(f"/projects/{pid}/matrices", {**spec, "name": "reuse", "participants": [{"*": edd}],
                                                     "seeds": {"dev": [1], "acceptance": [2]}})
    assert other["cells"] == {"queued": 0, "reused": 4, "skipped": 0, "rerun_conservative": 0}
    ids = {c["cell_id"]: c["run_id"] for c in stack.get(f"/matrices/{mid}/cells")}
    assert all(ids[c["cell_id"]] == c["run_id"] for c in stack.get(f"/matrices/{other['matrix']['id']}/cells"))
    # the report: splits, one-dimension comparisons (method vs mechanism), sources, denominators, conclusions
    rep = stack.get(f"/matrices/{mid}/report")
    assert rep["complete"] and set(rep["splits"]) == {"dev", "acceptance"}
    acc = rep["splits"]["acceptance"]
    assert acc["outcomes"]["denominator_cells"] == 12 and acc["outcomes"]["run_failed"] == 0
    kinds = {c["kind"] for c in acc["comparisons"]}
    assert {"method", "mechanism"} <= kinds
    method = next(c for c in acc["comparisons"] if c["kind"] == "method" and c["metric_id"] == "steps_used")
    assert method["n_pairs"] == 6 and method["paired_on"].startswith("all other dimensions")
    assert rep["metric_sources"]["delay_cost"].startswith("evaluator")
    assert rep["conclusions"] and rep["conclusions"][0].startswith("[acceptance]")
    csv_text = stack.client.get(f"/matrices/{mid}/report", params={"format": "csv"}).text
    assert csv_text.startswith("section,split") and "comparison,acceptance" in csv_text
    md = stack.client.get(f"/matrices/{mid}/report", params={"format": "md"}).text
    assert "## Conclusions" in md and "### Paired comparisons" in md


def test_reuse_key_covers_views_gates_and_extensions(stack):
    """Phase 3A: a completed cell is reused (and marked) only for the same full configuration — model, plugins with
    descriptor digests, rules, participant views, scenario, seed, budget and declared extension configs."""
    wh = next(p for p in stack.get("/projects") if p["name"] == "仓储分配示例")
    base = next(s for s in stack.get(f"/projects/{wh['id']}/scenarios") if s["name"] == "仓储：收货员 + 拣货员同步批次")
    sid = stack.post(f"/scenarios/{base['id']}/copy", {"name": f"同步批次（复用键 {uuid.uuid4().hex[:6]}）"})["id"]
    strategies = {s["name"]: s["id"] for s in stack.get(f"/projects/{wh['id']}/strategies")}
    spec = {"version": 2, "name": "reuse key", "scenarios": [sid], "seeds": [0],
            "participants": [{"receiver": strategies["仓储规则（收货）"], "picker": strategies["仓储规则（拣货）"]}]}
    first = stack.post(f"/projects/{wh['id']}/matrices", spec)
    assert first["cells"] == {"queued": 1, "reused": 0, "skipped": 0, "rerun_conservative": 0}
    done = wait_cells(stack, first["matrix"]["id"], finished, timeout=300)
    assert done[0]["status"] == "DONE" and done[0]["reused_from"] is None
    parts = done[0]["key_parts"]
    assert {"plugins", "views", "scenario_digest", "extensions", "model", "seed", "budget", "rules"} <= set(parts)

    again = stack.post(f"/projects/{wh['id']}/matrices", {**spec, "name": "same configuration"})
    assert again["cells"] == {"queued": 0, "reused": 1, "skipped": 0, "rerun_conservative": 0}
    reused = stack.get(f"/matrices/{again['matrix']['id']}/cells")[0]
    assert reused["cell_id"] == done[0]["cell_id"] and reused["run_id"] == done[0]["run_id"]
    assert reused["reused_from"] == {"matrix_id": first["matrix"]["id"], "cell_id": done[0]["cell_id"],
                                     "run_id": done[0]["run_id"]}

    manifest = stack.get(f"/scenarios/{sid}")["manifest"]
    body = {k: v for k, v in manifest.items() if k not in ("scenario_id", "revision", "model", "contract_version")}
    model_version = stack.get(f"/scenarios/{sid}")["model_version_id"]

    def changed(edit, name):
        b = json.loads(json.dumps(body))
        edit(b)
        r = stack.client.put(f"/scenarios/{sid}", json={**b, "model_version_id": model_version})
        assert r.status_code == 200, r.text
        res = stack.post(f"/projects/{wh['id']}/matrices", {**spec, "name": name})
        cell = stack.get(f"/matrices/{res['matrix']['id']}/cells")[0]
        return res["cells"], cell

    counts, view_cell = changed(lambda b: b["participants"][1]["view"].update(exclude=["dock", "done_at"]), "view")
    assert counts == {"queued": 1, "reused": 0, "skipped": 0, "rerun_conservative": 0} and view_cell["cell_id"] != done[0]["cell_id"]
    assert view_cell["key_parts"]["views"] != parts["views"] and view_cell["key_parts"]["plugins"] == parts["plugins"]
    counts, gate_cell = changed(lambda b: b.update(execution_gates=[{
        "plugin": {"plugin_id": "formal-lab.example.warehouse.capacity-gate", "version": "1.0.0"},
        "config": {"max_fill": 0.9}}]), "gate")
    assert counts["queued"] == 1 and gate_cell["key_parts"]["plugins"] != view_cell["key_parts"]["plugins"]
    counts, ext_cell = changed(lambda b: b["extensions"].update({"org.example.note": {
        "version": "1.0.0", "schema_id": "org.example.note/v1", "data": {"note": "changed"}}}), "extension")
    assert counts["queued"] == 1 and ext_cell["key_parts"]["extensions"] != gate_cell["key_parts"]["extensions"]
