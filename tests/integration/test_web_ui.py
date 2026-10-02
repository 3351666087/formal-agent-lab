"""Browser tests of the six Web areas against the real stack (Playwright + Chromium, P1-090…P1-096, P1-124).

The built web app is served by `vite preview` and proxies /api to the test API. Screenshots are written to
docs/execution/evidence/phase2/ui/ (phase-1 shots in evidence/ui/ are history and are not overwritten) and every page is checked for horizontal overflow at desktop and phone widths.
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.integration, pytest.mark.ui]
ROOT = Path(__file__).resolve().parents[2]
# FAL_EVIDENCE_DIR: the round this run belongs to (phase 3 by default; scripts/phase2_check.py sets phase 2)
SHOTS = ROOT / os.environ.get("FAL_EVIDENCE_DIR", "docs/execution/evidence/phase3") / "ui"
DESKTOP = {"width": 1440, "height": 900}
PHONE = {"width": 375, "height": 812}


def shot(page, name: str) -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS / f"{name}.jpg"), type="jpeg", quality=72, full_page=True)


def no_overflow(page) -> None:
    widths = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
    assert widths[0] <= widths[1] + 1, f"horizontal page overflow {widths} on {page.url}"


def project_id(stack) -> str:
    return next(p["id"] for p in stack.get("/projects") if p["name"] == "生产调度示例")


def test_projects_and_empty_error_states(page, web, stack):
    page.goto(web)
    page.get_by_role("heading", name="项目", exact=True).wait_for()
    page.get_by_role("heading", name="生产调度示例").wait_for()
    shot(page, "01-projects")
    # empty state: a fresh project has no models
    empty = stack.post("/projects", {"name": f"ui-empty-{int(time.time())}"})
    page.goto(f"{web}/p/{empty['id']}/models")
    page.get_by_text("项目中还没有模型").wait_for()
    # error state: unknown run
    page.goto(f"{web}/p/{empty['id']}/runs/run_does_not_exist")
    page.get_by_role("alert").get_by_text("NOT_FOUND").wait_for()
    shot(page, "02-error-state")
    stack.client.delete(f"/projects/{empty['id']}")


def test_model_workbench_edit_check_and_persist(page, web, stack):
    pid = project_id(stack)
    page.goto(f"{web}/p/{pid}/models")
    page.get_by_text("类型检查通过").wait_for(timeout=20000)
    page.locator("svg[aria-label='模型结构图']").wait_for()
    shot(page, "03-model-graph")
    # keyboard: move between tabs with arrow keys
    page.get_by_role("tab", name="结构图").focus()
    page.keyboard.press("ArrowRight")
    assert page.get_by_role("tab", name="表单编辑").get_attribute("aria-selected") == "true"
    # form edit → unsaved → reload restores the local draft → save as new version → reload shows it
    marker = f"UI edit {int(time.time())}"
    desc = page.locator("label.field:has(> span:text-is('说明')) input").first
    desc.fill(marker)
    page.get_by_text("有未保存修改").wait_for()
    page.reload()
    page.get_by_text("已恢复刷新前未保存的草稿").wait_for(timeout=20000)
    page.get_by_role("button", name="保存为新版本").click()
    page.get_by_text(re.compile(r"已保存为 v\d+")).wait_for(timeout=20000)
    page.reload()
    page.get_by_role("tab", name="表单编辑").click()
    assert page.locator("label.field:has(> span:text-is('说明')) input").first.input_value() == marker
    shot(page, "04-model-form")
    # bounded check with a witness replayed by the interpreter
    page.get_by_role("tab", name="编译与检查").click()
    page.locator("label.field:has(> span:text-is('步数上界 k')) input").fill("16")
    page.get_by_role("button", name="编译并检查").click()
    page.get_by_text("解释器重放：CONFIRMED").wait_for(timeout=60000)
    shot(page, "05-model-check")
    page.get_by_role("tab", name="版本差异").click()
    page.get_by_role("tab", name="能力矩阵").click()
    page.get_by_text("probabilistic_effects").wait_for()


def test_scenario_edit_persists_and_starts_run(page, web, stack):
    pid = project_id(stack)
    page.goto(f"{web}/p/{pid}/scenarios")
    page.get_by_role("link", name=re.compile("正常调度")).first.click()
    seed_input = page.locator("label.field:has(> span:text-is('种子')) input").first
    seed_input.wait_for()
    before = page.locator(".card-head .badge", has_text="修订").first.inner_text()
    seed_input.fill("5")
    page.get_by_role("button", name="保存（新修订）").click()
    page.get_by_text(re.compile(r"已保存（修订 r\d+）")).wait_for()
    page.reload()
    assert page.locator("label.field:has(> span:text-is('种子')) input").first.input_value() == "5"
    assert page.locator(".card-head .badge", has_text="修订").first.inner_text() != before
    shot(page, "06-scenario")
    page.get_by_role("button", name="运行实验").click()
    page.wait_for_url(re.compile(r"/runs/run_"))
    page.get_by_text(re.compile(r"已结束 · \d+ 事件")).wait_for(timeout=120000)  # the run ended (stream end state)
    expect(page.get_by_role("button", name="暂停")).to_be_disabled(timeout=15000)  # disabled once finished
    shot(page, "07-run-console")


def test_run_console_live_sse_resume_after_reload(page, web, stack):
    pid = project_id(stack)
    page.goto(f"{web}/p/{pid}/runs")
    delay = next(s for s in stack.get(f"/projects/{pid}/scenarios") if s["name"] == "状态延迟")
    page.locator("label.field:has(> span:text-is('场景')) select").select_option(label=f"状态延迟 (r{delay['revision']})")
    page.get_by_role("button", name="启动").click()
    page.wait_for_url(re.compile(r"/runs/(run_\w+)"))
    run_id = page.url.rsplit("/", 1)[1]
    page.get_by_text("实时").first.wait_for(timeout=30000)
    page.wait_for_function("document.querySelectorAll('table[aria-label=步骤列表] tbody tr').length >= 4", timeout=60000)
    page.reload()  # disconnect mid-run: the page reloads history and resumes the stream after the last seq
    # the stream's own end state ("已结束 · N 事件"), not any "成功" on the page: the resources line reads
    # "模型成功/尝试 …" from the first second, which made this wait return mid-run
    page.get_by_text(re.compile(r"已结束 · \d+ 事件")).wait_for(timeout=180000)
    final = stack.get(f"/runs/{run_id}")
    assert final["status"] == "SUCCEEDED", final["status"]
    page.get_by_text(f"已结束 · {final['event_seq']} 事件").wait_for(timeout=15000)
    page.locator("table[aria-label='步骤列表'] tbody tr").nth(3).click()
    page.get_by_role("heading", name="决策").wait_for()
    page.get_by_role("heading", name="前提检查（信念状态）").wait_for()
    page.get_by_text("未知").first.wait_for()
    page.keyboard.press("ArrowRight")
    page.get_by_role("tab", name="状态图表").click()
    page.locator("table[aria-label='状态随步骤变化']").wait_for()
    shot(page, "08-run-state-chart")
    page.get_by_role("tab", name="事件").click()
    page.locator("table[aria-label='事件'] tbody tr").first.click()
    shot(page, "09-run-events")


def test_strategies_evidence_and_benchmarks(page, web, stack):
    pid = project_id(stack)
    page.goto(f"{web}/p/{pid}/strategies")
    page.get_by_text("Z3 bounded planner").first.wait_for()
    page.get_by_label("兼容性检查场景").select_option(label="正常调度")
    page.get_by_text("兼容", exact=True).first.wait_for()
    shot(page, "10-strategies")
    run = next(r for r in stack.get(f"/projects/{pid}/runs", params={"status": "SUCCEEDED"}) if not r["imported"])
    page.goto(f"{web}/p/{pid}/evidence/{run['id']}")
    page.get_by_text("真值快照（证据）").wait_for()
    page.keyboard.press("ArrowRight")
    page.keyboard.press("ArrowRight")
    page.get_by_text(re.compile(r"步 2 / \d+")).wait_for()
    shot(page, "11-evidence-replay")
    page.get_by_role("tab", name="因果时间线").click()
    page.locator("svg[aria-label='因果时间线'] g[role=button]").nth(5).click()
    page.get_by_text("event_id").wait_for()
    page.get_by_role("tab", name="差异报告").click()
    page.get_by_role("tab", name="产物").click()
    page.locator("tbody tr.selectable").first.click()
    page.get_by_role("link", name="下载").wait_for()
    shot(page, "12-evidence-artifacts")
    # benchmarks: create a small matrix through the UI and read its report
    page.goto(f"{web}/p/{pid}/benchmarks")
    page.get_by_role("button", name="新建矩阵").click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_label(re.compile("单元队列（v2）")).uncheck()  # the phase-1 matrix (one run per cell, no queue)
    dialog.get_by_label("正常调度", exact=True).check()
    dialog.get_by_label("资源不足", exact=True).check()
    dialog.get_by_label("EDD 规则", exact=True).check()
    dialog.get_by_label("Z3 有界规划", exact=True).check()
    dialog.locator("label.field:has(> span:text-is('种子（逗号分隔）')) input").fill("1,2")
    dialog.get_by_text("将创建 8 个实验").wait_for()
    dialog.get_by_role("button", name="创建并运行").click()
    page.get_by_text("全部完成").wait_for(timeout=240000)
    page.get_by_role("heading", name=re.compile("配对比较")).wait_for()
    page.locator("svg[aria-label='指标柱状图']").wait_for()
    shot(page, "13-benchmarks")


@pytest.mark.parametrize("area", ["", "models", "scenarios", "strategies", "runs", "evidence", "benchmarks"])
def test_responsive_no_overflow(browser, web, stack, area):
    pid = project_id(stack)
    for name, viewport in (("desktop", DESKTOP), ("phone", PHONE)):
        ctx = browser.new_context(viewport=viewport, locale="zh-CN")
        page = ctx.new_page()
        page.goto(f"{web}/p/{pid}/{area}" if area else web)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(600)
        no_overflow(page)
        if name == "phone":
            shot(page, f"20-phone-{area or 'projects'}")
            page.get_by_role("button", name="打开导航").click()
            page.wait_for_timeout(300)
            box = page.locator("aside.sidebar").bounding_box()
            assert box is not None and box["x"] >= -1, "navigation drawer opens on phones"
            no_overflow(page)
        ctx.close()
