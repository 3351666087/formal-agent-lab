"""Phase 4A (A5): the ordinary business scenario through every product entry, and the batch panel on narrow screens.

1. Product flow on the order-handling model (pure backend): CLI `fal model push` imports the model, the SDK configures
   the scenario and strategy, CLI `fal run start --wait` runs it, the API and the Web explain a step, the Web and the
   CLI export the run, and the exported bundle is replayed offline (`fal replay …`) with the API process stopped.
2. The JOINT_BATCH panel at 390 px, tablet and desktop, light and dark: member cells keep a usable width, the
   participant, the action and the status stay readable (or reachable through the full-text title), the scrolling
   round list is keyboard-reachable, and reduced motion removes transitions.

Evidence: $A5_EVIDENCE_DIR or $FAL_EVIDENCE_DIR (default docs/execution/evidence/phase4) a5-product-flow.json, a5-narrow.json, screens/.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path

import httpx
import pytest
from formal_lab_contracts.bundle import read_bundle
from formal_lab_sdk import Client

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / (os.environ.get("A5_EVIDENCE_DIR") or os.environ.get("FAL_EVIDENCE_DIR", "docs/execution/evidence/phase4"))
SCREENS = EVIDENCE / "screens"
VIEWPORTS = {"phone-390": {"width": 390, "height": 844}, "tablet-768": {"width": 768, "height": 1024},
             "desktop-1440": {"width": 1440, "height": 900}}


def fal(stack, *args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    res = subprocess.run([sys.executable, "-m", "formal_lab_sdk.cli", *args], cwd=cwd or ROOT, text=True,
                         capture_output=True, env={**os.environ, "FAL_API_URL": stack.base}, timeout=900)
    if check:
        assert res.returncode == 0, res.stdout + res.stderr
    return res


def test_ordinary_business_flow_through_every_entry(stack, web, browser, tmp_path):
    from formal_lab_example_orders.model import model_package
    from formal_lab_example_orders.scenarios import RULES, scenario

    record: dict = {"entries": {}}
    name = f"A5 订单流程 {uuid.uuid4().hex[:6]}"
    sdk = Client(stack.base)
    project = sdk.create_project(name, "A5 product flow: import → configure → run → explain → export → replay")
    # CLI: import the model
    ir_path = tmp_path / "orders.ir.json"
    ir_path.write_text(json.dumps(model_package().ir.model_dump(mode="json"), ensure_ascii=False))
    pushed = fal(stack, "model", "push", str(ir_path), "--project", project["id"], "--package-id", "orders-a5")
    model = next(m for m in sdk.models(project["id"]) if m["package_id"] == "orders-a5")
    record["entries"]["cli_model_push"] = {"stdout": pushed.stdout.strip()[:200], "model_id": model["id"]}
    # SDK: configure the scenario and the strategy
    pure = scenario("normal", backend="pure", seed=0).model_dump(mode="json")
    version_id = sdk.model_version(model["id"], model["latest_version"])["id"]
    body = {"name": "订单：正常处理（纯数据）", "model_version_id": version_id, "environment": pure["environment"],
            "participants": pure["participants"], "objectives": pure["objectives"], "budget": pure["budget"],
            "seed": 0, "termination": pure["termination"]}
    sc = sdk.create_scenario(project["id"], body)
    st = sdk.create_strategy(project["id"], "订单规则", RULES["plugin"]["plugin_id"], {})
    record["entries"]["sdk_configure"] = {"scenario_id": sc["id"], "strategy_id": st["id"]}
    # CLI: run and wait
    started = fal(stack, "run", "start", "--project", project["id"], "--scenario", sc["id"], "--strategy", st["id"],
                  "--wait", check=False)
    run_id = started.stdout.split()[1]
    run = sdk.run(run_id)
    assert run["status"] == "SUCCEEDED", started.stdout + started.stderr
    record["entries"]["cli_run_start"] = {"run_id": run_id, "status": run["status"], "steps": run["last_step"],
                                          "exit": started.returncode}
    # API + CLI: explain a step
    step = httpx.get(f"{stack.base}/runs/{run_id}/steps/1", timeout=30).json()
    cli_step = json.loads(fal(stack, "run", "step", run_id, "1").stdout)
    assert step["proposal"]["action"] == cli_step["proposal"]["action"]
    record["entries"]["api_explain_step1"] = {"action": step["proposal"]["action"],
                                             "rationale": step["proposal"].get("rationale"),
                                             "check": (step.get("checks") or [{}])[0].get("result", {}).get("verdict"),
                                             "comparison": (step.get("outcome") or {}).get("effect_comparison", {})
                                             .get("verdict")}
    # Web: the run console, a step's explanation, export (download)
    ctx = browser.new_context(viewport=VIEWPORTS["desktop-1440"], locale="zh-CN", accept_downloads=True)
    page = ctx.new_page()
    page.goto(f"{web}/p/{project['id']}/runs/{run_id}")
    page.get_by_text("成功").first.wait_for(timeout=60000)
    row = page.locator("table[aria-label='步骤列表'] tbody tr").filter(
        has=page.locator("td.num", has_text=re.compile(r"^1$")))
    row.first.click()
    page.wait_for_timeout(800)
    detail = page.locator("main").inner_text()
    assert step["proposal"].get("rationale", "")[:20] in detail
    SCREENS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SCREENS / "a5-flow-step-explanation.png"))
    with page.expect_download() as dl:
        page.get_by_role("link", name="导出").first.click()
    web_bundle = tmp_path / "web.replay.zip"
    dl.value.save_as(str(web_bundle))
    ctx.close()
    record["entries"]["web_explain_export"] = {"bundle_bytes": web_bundle.stat().st_size,
                                               "screenshot": "screens/a5-flow-step-explanation.png"}
    # CLI: export
    cli_bundle = tmp_path / "cli.replay.zip"
    fal(stack, "export", run_id, "-o", str(cli_bundle))
    a, b = read_bundle(web_bundle.read_bytes()), read_bundle(cli_bundle.read_bytes())
    assert len(a.events) == len(b.events) == run["event_seq"] and a.manifest.run_id == b.manifest.run_id == run_id
    # offline: the API is stopped, the exported bundle still replays in an empty directory
    stack.stop()
    try:
        with pytest.raises(httpx.HTTPError):
            httpx.get(f"{stack.base}/health", timeout=2).raise_for_status()
        empty = tmp_path / "offline"
        empty.mkdir()
        verify = fal(stack, "replay", "verify", str(cli_bundle), cwd=empty)
        view = fal(stack, "replay", "view", str(web_bundle), cwd=empty)
        step1 = json.loads(fal(stack, "replay", "step", str(cli_bundle), "1", cwd=empty).stdout)
        offline_action = step1["proposal"].get("proposal", step1["proposal"])["action"]  # event payload shape
        assert verify.stdout.startswith("OK") and offline_action == step["proposal"]["action"]
        record["entries"]["offline_replay_api_stopped"] = {"api_reachable": False,
                                                           "verify": verify.stdout.strip()[:200],
                                                           "view_lines": len(view.stdout.splitlines()),
                                                           "step1_action": offline_action}
    finally:
        stack.start_api()
        stack.start_worker()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "a5-product-flow.json").write_text(json.dumps({"deliverable": "phase4A-A5 product flow",
                                                               "scenario": "订单：正常处理（纯数据）", **record},
                                                              indent=2, ensure_ascii=False) + "\n")


MEASURE = """() => {
  const panel = document.querySelector('[data-testid=batch-panel]');
  if (!panel) return null;
  const grid = panel.querySelector('.batch-grid');
  const cells = [...panel.querySelectorAll('.batch-cell')].slice(0, 6).map((c) => {
    const r = c.getBoundingClientRect();
    const parts = [...c.querySelectorAll('.badge, .chip, [data-part], .ellipsis')];
    const clipped = parts.filter((k) => {
      const kr = k.getBoundingClientRect();
      const cut = k.scrollWidth > k.clientWidth + 1 || kr.right > r.right + 1 || kr.width < 8;
      return cut && !(k.classList.contains('ellipsis') && k.getAttribute('title'));
    }).map((k) => k.textContent.trim().slice(0, 40));
    const action = c.querySelector('.ellipsis');
    return {width: Math.round(r.width), height: Math.round(r.height), clipped,
            action_title: action ? action.getAttribute('title') : null, text: c.innerText.replace(/\\s+/g, ' ').slice(0, 90)};
  });
  const style = getComputedStyle(cells.length ? panel.querySelector('.batch-cell') : panel);
  return {cells, page_overflow: document.scrollingElement.scrollWidth > window.innerWidth + 1,
          grid_tabindex: grid ? grid.getAttribute('tabindex') : null, grid_scrollable: grid ? grid.scrollHeight > grid.clientHeight : false,
          cell_color: style.color, cell_background: style.backgroundColor};
}"""


def _luminance(rgb: str) -> float:
    vals = [int(x) for x in rgb[rgb.index("(") + 1:rgb.index(")")].split(",")[:3]]
    lin = [(v / 255) / 12.92 if v / 255 <= 0.03928 else (((v / 255) + 0.055) / 1.055) ** 2.4 for v in vals]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def test_batch_panel_on_narrow_tablet_and_desktop(stack, web, browser):
    wh = next(p for p in stack.get("/projects") if p["name"] == "仓储分配示例")
    sc = next(s for s in stack.get(f"/projects/{wh['id']}/scenarios") if s["name"] == "仓储：收货员 + 拣货员同步批次")
    run = stack.post(f"/projects/{wh['id']}/runs", {"scenario_id": sc["id"], "seed": 0})
    stack.wait_status(run["id"], {"SUCCEEDED", "FAILED", "BUDGET_EXHAUSTED"}, timeout=300)
    out: dict = {"run_id": run["id"], "views": {}}
    SCREENS.mkdir(parents=True, exist_ok=True)
    for vname, viewport in VIEWPORTS.items():
        for scheme in ("light", "dark"):
            ctx = browser.new_context(viewport=viewport, locale="zh-CN", color_scheme=scheme)
            page = ctx.new_page()
            page.goto(f"{web}/p/{wh['id']}/runs/{run['id']}")
            panel = page.get_by_test_id("batch-panel")
            panel.wait_for(timeout=60000)
            page.locator("[data-testid=batch-panel] .batch-cell").first.wait_for(timeout=60000)
            panel.scroll_into_view_if_needed()
            page.wait_for_timeout(400)
            m = page.evaluate(MEASURE)
            m["contrast"] = round((max(_luminance(m["cell_color"]), _luminance(m["cell_background"])) + 0.05)
                                  / (min(_luminance(m["cell_color"]), _luminance(m["cell_background"])) + 0.05), 2)
            shot = SCREENS / f"a5-batch-{vname}-{scheme}.png"
            panel.screenshot(path=str(shot))
            m["screenshot"] = str(shot.relative_to(EVIDENCE))
            if scheme == "light":  # keyboard: the round list is a focusable scroll region
                grid = page.locator("[data-testid=batch-panel] .batch-grid")
                before = grid.evaluate("el => el.scrollTop")
                grid.focus()
                page.keyboard.press("PageDown")
                page.wait_for_timeout(300)
                m["keyboard"] = {"focused": grid.evaluate("el => el === document.activeElement"),
                                 "scrolled": grid.evaluate("el => el.scrollTop") > before or not m["grid_scrollable"]}
            out["views"][f"{vname}-{scheme}"] = m
            ctx.close()
    ctx = browser.new_context(viewport=VIEWPORTS["phone-390"], locale="zh-CN", reduced_motion="reduce")
    page = ctx.new_page()
    page.goto(f"{web}/p/{wh['id']}/runs/{run['id']}")
    page.get_by_test_id("batch-panel").wait_for(timeout=60000)
    out["reduced_motion"] = page.evaluate("""() => {
      const el = document.querySelector('.btn, button');
      const s = getComputedStyle(el);
      return {matches: matchMedia('(prefers-reduced-motion: reduce)').matches, transition: s.transitionDuration,
              animation: s.animationDuration};
    }""")
    ctx.close()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "a5-narrow.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    for key, m in out["views"].items():
        assert not m["page_overflow"], key
        assert all(c["width"] >= 150 for c in m["cells"]), (key, [c["width"] for c in m["cells"]])
        assert all(not c["clipped"] for c in m["cells"]), (key, [c["clipped"] for c in m["cells"]])
        assert all(c["action_title"] for c in m["cells"]), key
        assert m["contrast"] >= 4.5, (key, m["contrast"])
        if "keyboard" in m:
            assert m["grid_tabindex"] == "0" and m["keyboard"]["focused"] and m["keyboard"]["scrolled"], key
    rm = out["reduced_motion"]
    assert rm["matches"] and rm["transition"] in ("0s", "0ms") and rm["animation"] in ("0s", "0ms")
