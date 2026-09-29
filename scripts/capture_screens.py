#!/usr/bin/env python3
"""Web product flows and baseline screenshots (phase 3A, G5).

Against a running platform with the seeded examples (`scripts/dev.sh up`, web dev server on :5173 or the built bundle),
this drives the two G5 flows in the browser and captures the screenshots that the README and docs/design-system.md
use as their baseline:

1. Warehouse joint batch: scenario page → “运行实验” → run console until 成功 → the batch panel → export (download) →
   the downloaded bundle is read offline (formal_lab_contracts.bundle.read_bundle).
2. Order recovery (“订单：延迟响应（业务服务）”): same path; the evidence page shows the reconciled operations.
3. The six areas + landing, light and dark, one narrow (390 px) view; keyboard (skip link) and reduced-motion checks.

Output: docs/assets/screens/*.png and docs/execution/evidence/phase3/g5-web.json.

    scripts/in-vm.sh 'uv run --frozen python scripts/capture_screens.py --web http://127.0.0.1:5173'
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

import httpx
from formal_lab_contracts.bundle import read_bundle
from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "docs" / "assets" / "screens"
OUT = ROOT / "docs" / "execution" / "evidence" / "phase3" / "g5-web.json"
VIEW = {"width": 1440, "height": 900}


def api(base: str, path: str, **kw):
    r = httpx.request(kw.pop("method", "GET"), f"{base}/api/v1{path}", trust_env=False, timeout=60, **kw)
    r.raise_for_status()
    return r.json()


def by_name(items, name, key="name"):
    return next(x for x in items if x[key] == name)


ERROR_SCREENS: list[str] = []


def shot(page: Page, name: str, *, full: bool = False) -> str:
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.wait_for_timeout(600)
    body = page.inner_text("body")
    if "Unexpected Application Error" in body or page.locator("[data-testid=route-error]").count():
        ERROR_SCREENS.append(name)  # an error screen is never a baseline
    path = SHOTS / f"{name}.png"
    page.screenshot(path=str(path), full_page=full)
    return str(path.relative_to(ROOT))


def run_from_scenario(page: Page, web: str, base: str, pid: str, sid: str, timeout: float = 300) -> str:
    """Start the scenario from its page (the Web entry), wait until the run is terminal, show its console."""
    page.goto(f"{web}/p/{pid}/scenarios/{sid}", wait_until="networkidle")
    page.get_by_role("button", name="运行实验").click()
    page.wait_for_url("**/runs/run_*", timeout=30_000)
    run_id = page.url.rstrip("/").split("/")[-1]
    deadline = time.time() + timeout
    while api(base, f"/runs/{run_id}")["status"] not in ("SUCCEEDED", "FAILED", "CANCELLED", "BUDGET_EXHAUSTED"):
        if time.time() > deadline:
            raise SystemExit(f"run {run_id} did not finish")
        time.sleep(1)
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(1500)
    return run_id


def download_and_read(page: Page, name: str) -> dict:
    with page.expect_download() as dl:
        page.get_by_role("link", name="导出").first.click()
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / f"{name}.replay.zip"
        dl.value.save_as(str(target))
        b = read_bundle(target.read_bytes())
        return {"bytes": target.stat().st_size, "events": len(b.events), "operations": len(b.operations),
                "rounds": len(b.batches()), "status": b.manifest.status.value,
                "reconciled": sum(1 for o in b.operations if o.state.value == "RECONCILED")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--web", default="http://127.0.0.1:5173")
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    args = ap.parse_args()
    web, base = args.web.rstrip("/"), args.api.rstrip("/")
    t0 = time.time()
    projects = api(base, "/projects")
    wh, od, sch = (by_name(projects, n)["id"] for n in ("仓储分配示例", "订单服务示例", "生产调度示例"))
    wh_sc = by_name(api(base, f"/projects/{wh}/scenarios"), "仓储：收货员 + 拣货员同步批次")["id"]
    od_sc = by_name(api(base, f"/projects/{od}/scenarios"), "订单：延迟响应（业务服务）")["id"]
    out: dict = {"web": web, "screens": {}}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport=VIEW, device_scale_factor=1.5, color_scheme="light", accept_downloads=True)
        page = ctx.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        # ---- flow 1: warehouse joint batch through the Web
        batch_run = run_from_scenario(page, web, base, wh, wh_sc)
        page.get_by_test_id("batch-panel").wait_for()
        rounds = page.get_by_test_id("batch-panel").locator(".batch-row").count()
        out["warehouse_batch"] = {"run_id": batch_run, "rounds_shown": rounds, "export": download_and_read(page, "wh")}
        out["screens"]["run_batch"] = shot(page, "run-batch")
        page.get_by_test_id("batch-panel").scroll_into_view_if_needed()
        page.locator("table[aria-label='步骤列表'] tbody tr").nth(6).click()
        page.get_by_test_id("planner-input").wait_for()
        out["screens"]["run_batch_step"] = shot(page, "run-batch-step", full=True)

        # ---- flow 2: order recovery through the Web
        order_run = run_from_scenario(page, web, base, od, od_sc)
        abnormal = page.get_by_test_id("operations-panel").locator("tbody tr").count()
        out["order_recovery"] = {"run_id": order_run, "abnormal_operations_shown": abnormal,
                                 "export": download_and_read(page, "orders")}
        out["screens"]["run_orders"] = shot(page, "run-orders")
        page.goto(f"{web}/p/{od}/evidence/{order_run}", wait_until="networkidle")
        page.wait_for_timeout(800)
        for _ in range(4):  # step 4: the first answer lost past the timeout and settled by query
            page.keyboard.press("ArrowRight")
        out["evidence_session_snapshot"] = page.get_by_test_id("session-snapshot").count() > 0
        out["screens"]["evidence"] = shot(page, "evidence-orders")

        # ---- the areas (light)
        mx = api(base, f"/projects/{sch}/matrices")
        if not mx:  # a small matrix so the benchmark area shows a real comparison (and a reused copy)
            strategies = {s["name"]: s["id"] for s in api(base, f"/projects/{sch}/strategies")}
            scen = by_name(api(base, f"/projects/{sch}/scenarios"), "状态延迟")["id"]
            spec = {"version": 2, "name": "EDD vs 任务计划（状态延迟）", "scenarios": [scen],
                    "participants": [{"*": strategies["EDD 规则"]}, {"*": strategies["任务计划（规则生成）"]}],
                    "seeds": [1, 2, 3], "max_parallel": 2}
            first = api(base, f"/projects/{sch}/matrices", method="POST", json=spec)["matrix"]["id"]
            deadline = time.time() + 600
            while time.time() < deadline and not all(c["status"] in ("DONE", "FAILED") for c in
                                                     api(base, f"/matrices/{first}/cells")):
                time.sleep(2)
            api(base, f"/projects/{sch}/matrices", method="POST", json={**spec, "name": "同一配置（复用）"})
            mx = api(base, f"/projects/{sch}/matrices")
        matrix = next(m for m in mx if m["name"].startswith("EDD"))
        pages = {
            "landing": f"{web}/",
            "models": f"{web}/p/{od}/models",
            "scenarios": f"{web}/p/{wh}/scenarios/{wh_sc}",
            "strategies": f"{web}/p/{wh}/strategies",
            "runs": f"{web}/p/{wh}/runs",
            "benchmarks": f"{web}/p/{sch}/benchmarks/{matrix['id']}",
        }
        for name, url in pages.items():
            page.goto(url, wait_until="networkidle")
            if name == "models":
                page.get_by_role("link").filter(has_text="订单处理模型").first.click()
                page.get_by_role("tab", name="结构图").wait_for()
            out["screens"][name] = shot(page, name)
        reused = [m for m in mx if m["name"] == "同一配置（复用）"]
        if reused:
            page.goto(f"{web}/p/{sch}/benchmarks/{reused[0]['id']}", wait_until="networkidle")
            page.get_by_text("单元队列").click()
            out["benchmarks_reused_badges"] = page.get_by_test_id("reused-cell").count()
            out["screens"]["benchmarks_reused"] = shot(page, "benchmarks-reused", full=True)

        # ---- dark, narrow
        dark = browser.new_context(viewport=VIEW, device_scale_factor=1.5, color_scheme="dark")
        dp = dark.new_page()
        dp.goto(f"{web}/p/{wh}/runs/{batch_run}", wait_until="networkidle")
        out["screens"]["run_batch_dark"] = shot(dp, "run-batch-dark")
        dp.goto(f"{web}/", wait_until="networkidle")
        out["screens"]["landing_dark"] = shot(dp, "landing-dark")
        narrow = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, color_scheme="light")
        np_ = narrow.new_page()
        np_.goto(f"{web}/p/{wh}/runs/{batch_run}", wait_until="networkidle")
        out["screens"]["run_narrow"] = shot(np_, "run-narrow")
        out["narrow_no_horizontal_scroll"] = np_.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")

        # ---- keyboard and reduced motion
        kb = browser.new_context(viewport=VIEW).new_page()
        kb.goto(f"{web}/p/{wh}/runs/{batch_run}", wait_until="networkidle")
        kb.keyboard.press("Tab")
        out["skip_link_first"] = kb.evaluate("document.activeElement?.className") == "skip-link"
        kb.keyboard.press("Enter")
        out["skip_link_moves_focus"] = kb.evaluate("document.activeElement?.id") == "main"
        rm = browser.new_context(viewport=VIEW, reduced_motion="reduce").new_page()
        rm.goto(f"{web}/", wait_until="networkidle")
        out["reduced_motion_durations"] = rm.evaluate(
            "getComputedStyle(document.documentElement).getPropertyValue('--dur-base').trim()")
        out["page_errors"] = errors
        out["error_screens"] = ERROR_SCREENS
        browser.close()

    w, o = out["warehouse_batch"], out["order_recovery"]
    checks = {
        "web: warehouse batch run, rounds shown, export read offline": w["rounds_shown"] > 0
                                                                        and w["export"]["rounds"] == w["rounds_shown"]
                                                                        and w["export"]["status"] == "SUCCEEDED",
        "web: order recovery run, reconciled operations exported": o["export"]["reconciled"] > 0
                                                                   and o["abnormal_operations_shown"] > 0,
        "web: reused matrix cells marked": out.get("benchmarks_reused_badges", 0) > 0,
        "web: narrow view has no horizontal page scroll": out["narrow_no_horizontal_scroll"],
        "web: skip link first and moves focus to main": out["skip_link_first"] and out["skip_link_moves_focus"],
        "web: reduced motion zeroes durations": out["reduced_motion_durations"] == "0ms",
        "web: no page errors": not out["page_errors"],
        "web: no error screens captured": not out["error_screens"],
    }
    doc = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "duration_s": round(time.time() - t0, 1),
           "checks": checks, "ok": all(checks.values()), **out}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(checks, indent=1, ensure_ascii=False))
    return 0 if doc["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
