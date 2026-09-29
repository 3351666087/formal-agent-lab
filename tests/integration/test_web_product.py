"""Phase-2 product path in the browser (P2-090 … P2-099) against the real stack.

- the full acceptance: a new project → model (pasted JSON) → strategy configurations from schema forms → a
  two-participant scenario with turns and joint termination → a run in the console (participants, plans,
  operations, recovery) → a v2 cost comparison → the evidence navigator → the exported bundle replayed offline in an
  empty directory;
- UI states (empty, waiting, failure, reconnect, narrow) as real screenshots, and measurements of the first-screen
  bundle and of a large trajectory in the console (docs/execution/evidence/phase2/web/).
"""

from __future__ import annotations

import gzip
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from pathlib import Path as _P

import pytest
from formal_lab_example_scheduling.model import build_model

ROOT = _P(__file__).resolve().parents[2]
SHOTS = ROOT / "docs" / "execution" / "evidence" / "phase2" / "ui"
DESKTOP = {"width": 1440, "height": 900}
PHONE = {"width": 375, "height": 812}


def shot(page, name: str) -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS / f"{name}.jpg"), type="jpeg", quality=72, full_page=True)


def no_overflow(page) -> None:
    widths = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
    assert widths[0] <= widths[1] + 1, f"horizontal page overflow {widths} on {page.url}"

pytestmark = [pytest.mark.integration, pytest.mark.ui]
EVIDENCE = ROOT / "docs" / "execution" / "evidence" / "phase2" / "web"


def field(scope, label: str):
    return scope.locator(f"label.field:has(> span:text-is('{label}'))").locator("input, select, textarea").first


def test_product_acceptance_new_project_to_two_participant_cost_comparison(page, web, stack, tmp_path):
    name = f"验收项目 {uuid.uuid4().hex[:6]}"
    page.goto(web)
    page.get_by_role("button", name="新建项目").first.click()
    dialog = page.get_by_role("dialog")
    field(dialog, "名称").fill(name)
    dialog.get_by_role("button", name="创建").click()
    page.wait_for_url(re.compile(r"/p/prj_[^/]+/models"))
    pid = page.url.split("/p/")[1].split("/")[0]
    shot(page, "p2-01-new-project")
    # model: paste the scheduling model (with its cost objectives) as JSON
    page.get_by_role("button", name="新建模型").first.click()
    dialog = page.get_by_role("dialog")
    field(dialog, "package_id").fill("line-scheduling")
    field(dialog, "名称").fill("产线调度")
    dialog.locator("textarea").fill(build_model(with_objectives=True).model_dump_json(indent=1))
    dialog.get_by_role("button", name="创建 v1").click()
    page.get_by_role("tab", name="目标与发布").click()
    page.get_by_text("delay_cost").first.wait_for()
    page.get_by_role("button", name=re.compile("发布检查 v1")).click()
    page.get_by_test_id("release-record").wait_for(timeout=120000)
    shot(page, "p2-02-model-release")
    # strategy configurations from their schema forms
    page.goto(f"{web}/p/{pid}/strategies")
    for label, plugin in (("EDD", "formal-lab.example.scheduling.edd-dispatch@1.0.0"),
                          ("Z3", "formal-lab.planner.z3-bounded@1.1.0")):
        page.get_by_role("button", name="新建策略配置").click()
        dialog = page.get_by_role("dialog")
        field(dialog, "名称").fill(label)
        field(dialog, "策略插件").select_option(plugin)
        if label == "Z3":  # a plugin without configuration items has no example to fill in
            dialog.get_by_role("button", name="填入示例").click()
        dialog.get_by_role("button", name="保存").click()
        dialog.wait_for(state="detached")
    # a two-participant scenario: turns + joint termination
    page.goto(f"{web}/p/{pid}/scenarios/new")
    field(page, "名称").first.fill("两名调度员：成本对比")
    editor = page.get_by_test_id("participants-editor")
    editor.get_by_role("button", name="＋ 参与者").click()
    groups = editor.get_by_role("group", name=re.compile(r"^参与者 "))  # not the nested 参与者视图 groups
    field(groups.nth(0), "参与者 ID").fill("dispatcher_a")
    field(groups.nth(1), "参与者 ID").fill("dispatcher_b")
    field(groups.nth(0), "策略插件").select_option("formal-lab.example.scheduling.edd-dispatch@1.0.0")
    field(groups.nth(1), "策略插件").select_option("formal-lab.planner.z3-bounded@1.1.0")
    page.get_by_role("button", name="启用 v2 联合终止条件").click()
    field(page.get_by_test_id("turns-editor"), "观测时点").select_option("ROUND_START")
    shot(page, "p2-03-scenario-two-participants")
    page.get_by_role("button", name="创建场景").click()
    page.wait_for_url(re.compile(r"/scenarios/scn_"))
    page.get_by_role("button", name="运行实验").click()
    page.wait_for_url(re.compile(r"/runs/run_"))
    run_id = page.url.rsplit("/", 1)[1]
    panel = page.get_by_test_id("participants-panel")
    panel.get_by_text("dispatcher_b").wait_for()
    run = stack.wait_status(run_id, {"SUCCEEDED", "FAILED", "BUDGET_EXHAUSTED"}, timeout=300)
    assert run["status"] == "SUCCEEDED" and run["termination_reason"] == "JOINT_GOAL_REACHED"
    page.reload()
    page.get_by_test_id("operations-panel").wait_for()
    page.get_by_test_id("recovery-log").wait_for()
    shot(page, "p2-04-run-console-kernel")
    # cost comparison (v2 matrix: both participants EDD vs both Z3; dev / acceptance seeds fixed in advance)
    page.goto(f"{web}/p/{pid}/benchmarks")
    page.get_by_role("button", name="新建矩阵").click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_label("两名调度员：成本对比").check()
    dialog.get_by_label("EDD", exact=True).check()
    dialog.get_by_label("Z3", exact=True).check()
    field(dialog, "验收种子（acceptance）").fill("2,3")
    dialog.get_by_text("将创建 6 个实验").wait_for()
    dialog.get_by_role("button", name="创建并运行").click()
    page.get_by_test_id("matrix-v2").wait_for()
    page.get_by_text("全部完成").wait_for(timeout=600000)
    page.get_by_test_id("outcome-distribution").get_by_text("分母 4 个单元").wait_for()
    page.get_by_label("划分").select_option("acceptance")
    with page.expect_download() as dl:
        page.get_by_role("button", name="当前视图 JSON").click()
    view = json.loads(Path(dl.value.path()).read_text())
    assert view["split"] == "acceptance" and view["outcomes"]["denominator_cells"] == 4
    assert any(c["kind"] == "method" for c in view["comparisons"])
    shot(page, "p2-05-benchmark-cost-comparison")
    # evidence navigator of the two-participant run
    page.goto(f"{web}/p/{pid}/evidence/{run_id}")
    page.get_by_role("tab", name="关联定位").click()
    page.get_by_test_id("navigator").get_by_text("line-scheduling@v1").wait_for()
    shot(page, "p2-06-evidence-navigator")
    # offline replay of the exported bundle in an empty directory, no server
    empty = tmp_path / "offline"
    empty.mkdir()
    bundle = empty / f"{run_id}.replay.zip"
    bundle.write_bytes(stack.client.get(f"/runs/{run_id}/export").content)
    env = {k: v for k, v in os.environ.items() if not k.startswith("FAL_API")}
    out = []
    for args in (("replay", "verify", bundle.name), ("replay", "turns", bundle.name), ("replay", "model", bundle.name)):
        res = subprocess.run([sys.executable, "-m", "formal_lab_sdk.cli", *args], cwd=empty, env=env, text=True,
                             capture_output=True, timeout=120)
        assert res.returncode == 0, res.stderr
        out.append(res.stdout)
    assert out[0].startswith("OK formal-lab/replay-bundle@2") and "participants=2" in out[0]
    assert "dispatcher_a" in out[1] and "dispatcher_b" in out[1]
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "product-acceptance.log").write_text(
        f"project {name} ({pid}); run {run_id}: {run['status']} {run['termination_reason']}, {run['last_step']} steps\n"
        f"matrix view (acceptance): {json.dumps(view['outcomes'], ensure_ascii=False)}\n\n$ fal replay verify\n{out[0]}\n"
        f"$ fal replay turns (first 6)\n" + "\n".join(out[1].splitlines()[:6]) + f"\n\n$ fal replay model\n{out[2]}")


def test_ui_states_and_measurements(browser, web, stack):
    """P2-096: empty / waiting / failure / reconnect / narrow screenshots, first-screen bundle and large-trajectory
    interaction measurements."""
    empty_pid = stack.post("/projects", {"name": f"空项目 {uuid.uuid4().hex[:6]}"})["id"]
    demo = next(p["id"] for p in stack.get("/projects") if p["name"] == "生产调度示例")
    ctx = browser.new_context(viewport=DESKTOP, locale="zh-CN")
    pg = ctx.new_page()
    pg.goto(f"{web}/p/{empty_pid}/models")
    pg.get_by_text("项目中还没有模型").wait_for()
    shot(pg, "p2-10-state-empty")
    # a large trajectory: the labelled model stand-in stalls on state-delay, so a 400-step budget yields thousands
    # of events (every step recorded: observation, candidates, proposal, checks, outcome, comparison, …)
    scen = {x["name"]: x["id"] for x in stack.get(f"/projects/{demo}/scenarios")}
    stub = next(x["id"] for x in stack.get(f"/projects/{demo}/strategies") if x["name"] == "LLM 替身（stub）")
    big_run = stack.post(f"/projects/{demo}/runs", {"scenario_id": scen["状态延迟"], "strategy_config_id": stub, "seed": 5,
                                                    "budget": {"max_steps": 400, "max_model_calls": 1000},
                                                    "config": {"initial_check_horizon": 0}})
    big = stack.wait_status(big_run["id"], {"SUCCEEDED", "FAILED", "BUDGET_EXHAUSTED"}, timeout=1200)
    assert big["event_seq"] > 2000, big["event_seq"]
    # waiting: the event history is slow to arrive
    pg.route(re.compile(r".*/runs/.*/events\?.*"), lambda route: (time.sleep(2.5), route.continue_()))
    pg.goto(f"{web}/p/{demo}/runs/{big['id']}")
    pg.get_by_text("连接中").first.wait_for()
    shot(pg, "p2-11-state-waiting")
    pg.unroute(re.compile(r".*/runs/.*/events\?.*"))
    # failure: the API answers with an error
    pg.route(re.compile(r".*/api/v1/projects/[^/]+/models$"), lambda route: route.fulfill(
        status=503, content_type="application/json",
        body=json.dumps({"error": {"code": "RETRYABLE_FAILURE", "message": "database unavailable (test)",
                                   "retryable": True, "details": {}, "field_errors": []}})))
    pg.goto(f"{web}/p/{demo}/models")
    pg.get_by_text("database unavailable (test)").wait_for()
    shot(pg, "p2-12-state-failure")
    pg.unroute(re.compile(r".*/api/v1/projects/[^/]+/models$"))
    # reconnect: the live stream keeps dropping
    pg.route(re.compile(r".*/events/stream.*"), lambda route: route.abort())
    live = stack.post(f"/projects/{demo}/runs", {"scenario_id": next(
        s["id"] for s in stack.get(f"/projects/{demo}/scenarios") if s["name"] == "正常调度"), "seed": 9})
    pg.goto(f"{web}/p/{demo}/runs/{live['id']}")
    pg.get_by_text(re.compile("重连中|连接错误")).first.wait_for(timeout=20000)
    shot(pg, "p2-13-state-reconnect")
    pg.unroute(re.compile(r".*/events/stream.*"))
    # large trajectory: time to all events, to the (windowed) event table, and to scroll to the end
    t0 = time.perf_counter()
    pg.goto(f"{web}/p/{demo}/runs/{big['id']}")
    pg.get_by_text(re.compile(rf"{big['event_seq']} 事件")).wait_for(timeout=60000)
    loaded_s = time.perf_counter() - t0
    t1 = time.perf_counter()
    pg.get_by_role("tab", name="事件").click()
    table = pg.get_by_test_id("virtual-table")
    table.wait_for()
    table_s = time.perf_counter() - t1
    rendered = int(table.get_attribute("data-rendered") or 0)
    t2 = time.perf_counter()
    table.evaluate("el => el.scrollTo(0, el.scrollHeight)")
    pg.locator(f"tr[aria-rowindex='{big['event_seq'] + 1}']").wait_for(timeout=10000)
    scroll_s = time.perf_counter() - t2
    assert rendered < big["event_seq"] or big["event_seq"] < 60, "the table renders a window, not every row"
    ctx.close()
    # narrow screens
    phone = browser.new_context(viewport=PHONE, locale="zh-CN")
    pp = phone.new_page()
    for path, name in ((f"p/{demo}/runs/{big['id']}", "p2-14-narrow-run-console"),
                       (f"p/{demo}/scenarios", "p2-15-narrow-scenarios")):
        pp.goto(f"{web}/{path}")
        pp.wait_for_load_state("networkidle")
        pp.wait_for_timeout(500)
        no_overflow(pp)
        shot(pp, name)
    phone.close()
    assets = sorted((ROOT / "web" / "dist" / "assets").glob("*.js"))
    entry = next(a for a in assets if a.name.startswith("index-"))
    first = [entry, *[a for a in assets if a.name.startswith("Projects-")]]
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "measurements.json").write_text(json.dumps({
        "bundle": {"before_split": {"js_bytes": 476680, "gzip_bytes": 141330, "note": "single chunk (phase-1 build)"},
                   "first_screen_after_split": {"files": [a.name for a in first],
                                                "js_bytes": sum(a.stat().st_size for a in first),
                                                "gzip_bytes": sum(len(gzip.compress(a.read_bytes(), 9)) for a in first)},
                   "all_chunks": {a.name: a.stat().st_size for a in assets}},
        "large_trajectory": {"run_id": big["id"], "events": big["event_seq"], "steps": big["last_step"],
                             "seconds_until_all_events_shown": round(loaded_s, 3),
                             "seconds_to_open_event_table": round(table_s, 3),
                             "seconds_to_scroll_to_last_event": round(scroll_s, 3),
                             "rows_in_dom": rendered},
    }, indent=2) + "\n")
