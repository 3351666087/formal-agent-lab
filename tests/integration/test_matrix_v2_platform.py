"""Matrix v2 on the durable path (P2-080 … P2-085): full cell configurations with stable ids, a queue that survives a
killed worker and a lost queue workflow, reruns of failed cells, incremental merge with reuse of completed cells,
and the v2 report (splits, per-dimension comparisons, probes/evaluators with sources) as JSON, CSV and Markdown."""

from __future__ import annotations

import asyncio
import time

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
    delay = demo["scenarios"]["状态延迟"]["id"]
    strategies = {s["name"]: s["id"] for s in stack.get(f"/projects/{pid}/strategies")}
    edd, task = strategies["EDD 规则"], strategies["任务计划（规则生成）"]
    spec = {"version": 2, "name": "delay ablation", "scenarios": [delay],
            "participants": [{"*": edd}, {"*": task}],
            "ablations": [{}, {"label": "no-observation-delay", "env": {"observation": {"delay_steps": None}}}],
            "seeds": {"dev": [1], "acceptance": [2, 3]}, "max_parallel": 2}
    res = stack.post(f"/projects/{pid}/matrices", spec)
    mid = res["matrix"]["id"]
    assert res["cells"] == {"queued": 12, "reused": 0, "skipped": 0}
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
    assert merged["cells"] == {"queued": 4, "reused": 0, "skipped": 12}
    again = stack.post(f"/matrices/{mid}/cells", {"seeds": {"dev": [1], "acceptance": [2, 3, 4]}})
    assert again["cells"]["queued"] == 0 and again["cells"]["skipped"] == 16
    wait_cells(stack, mid, lambda cs: len(cs) == 16 and all(c["status"] == "DONE" for c in cs))
    # a new matrix sharing configurations reuses the completed cells (same cell ids, same runs)
    other = stack.post(f"/projects/{pid}/matrices", {**spec, "name": "reuse", "participants": [{"*": edd}],
                                                     "seeds": {"dev": [1], "acceptance": [2]}})
    assert other["cells"] == {"queued": 0, "reused": 4, "skipped": 0}
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
