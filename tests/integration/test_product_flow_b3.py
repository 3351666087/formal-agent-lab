"""Phase 4B (B3): the MAL security domain through every product entry, on the real stack.

One domain (a coreLang attack graph, net-app-data) carried through the Web, the HTTP API, the CLI and the SDK, each
with its own recorded calls / operations:

1. Web — the model workbench imports the attack graph from its source through the MAL model-frontend form (the
   attack-graph extension is kept); the scenario form shows the configured execution gates and keeps them on save.
2. CLI — `fal model push --frontend …` imports the defence-enabled variant (red/blue); `fal run start --wait` runs the
   per-action gated red-team scenario; `fal run step` explains a step; `fal export` + `fal replay …` read it offline.
3. SDK — configures the gated red-team and red/blue scenarios and the strategies, runs the model-revision check
   (an incomplete-capture belief v1 vs the full native capture v2 disagree about the target), and a strategy matrix.
4. API — explains a step with its Broker decisions, runs the red/blue game, issues the participants' read tokens and
   downloads each role's own view.

Checked from the real configuration: role views (red's planner withholds `hardened`; each participant's download is its
own projection, without credentials or the other side's configuration), action explanations, Broker decisions (every
compromise ALLOWed only after the per-send issuer check; red's stale attempt on a step blue hardened is DENIED with no
side effect; blue's harden passes as outside the admission scope), and the model-deviation displays (effect comparison
per step; the belief-vs-truth revision at model level). The run console, step detail, evidence replay and benchmark
pages are visited and screenshotted.

Evidence: $B3_EVIDENCE_DIR or $FAL_EVIDENCE_DIR (default docs/execution/evidence/phase4) b3-product-flow.json, screens/.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx
import pytest
from formal_lab_contracts import ModelSource
from formal_lab_contracts.bundle import read_bundle
from formal_lab_sdk import Client

pytestmark = [pytest.mark.integration, pytest.mark.ui, pytest.mark.timeout(1800)]  # a browser flow (see test_web_ui)
ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / (os.environ.get("B3_EVIDENCE_DIR") or os.environ.get("FAL_EVIDENCE_DIR", "docs/execution/evidence/phase4"))
SCREENS = EVIDENCE / "screens"
DESKTOP = {"width": 1440, "height": 900}
PKG = ROOT / "packages" / "domain-mal"
FORMAT = "mal-attack-graph/v1"
MAL_FE = {"plugin_id": "formal-lab.domain.mal.frontend", "version": "1.0.0"}
ISSUER = "formal-lab.domain.mal.receipt-issuer"
BROKER = "formal-lab.domain.mal.broker-gate"
TGT = {"property_id": "secret-confidentiality", "reach_forbidden": "secret:read"}
LAB = {"allowed_assets": ["app", "secret", "net"], "max_attack_steps": 40}
CHECK = {"kind": "GOAL_REACHABILITY", "property_id": "target_reached", "bound": {"max_steps": 60, "timeout_ms": 30000}}
FINISHED = {"SUCCEEDED", "FAILED", "BUDGET_EXHAUSTED", "CANCELLED"}


def fal(stack, *args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    res = subprocess.run([sys.executable, "-m", "formal_lab_sdk.cli", *args], cwd=cwd or ROOT, text=True,
                         capture_output=True, env={**os.environ, "FAL_API_URL": stack.base}, timeout=900)
    if check:
        assert res.returncode == 0, res.stdout + res.stderr
    return res


def _fixture() -> tuple[dict, dict, dict]:
    graph = json.loads((PKG / "tests/fixtures/net_app_data.graph.json").read_text())
    native = json.loads((PKG / "tests/fixtures/net_app_data.native.json").read_text())["reachable_case"]
    model = json.loads((PKG / "src/formal_lab_domain_mal/models/net_app_data.json").read_text())
    return graph, native, model


def envelope(**extra) -> dict:
    """A mal-attack-graph/v1 source envelope (the format the MAL frontend declares) for the committed capture."""
    graph, native, model = _fixture()
    return {"language": {"name": "coreLang", "version": "1.0.0"}, "model": model, "graph": graph,
            "entry_points": native["entry"], "goal": native["goal"], "reachable": native["compromised"], **extra}


def local_package(env: dict, package_id: str):
    from formal_lab_domain_mal.frontend import MalFrontend

    return MalFrontend().compile(ModelSource(format=FORMAT, text=json.dumps(env)), package_id=package_id, version=1)


def gate_specs(work: Path) -> list[dict]:
    """The per-action admission pair: the issuer checks each compromise at send time and signs a receipt; the Broker
    admits only against it. The signing key is generated for this test and never leaves its directory."""
    ks = work / "keys.json"
    ks.write_text(json.dumps({"issuer-1": os.urandom(24).hex()}))
    ks.chmod(0o600)
    rc = str(work / "receipts.json")
    return [{"plugin": {"plugin_id": ISSUER, "version": "1.0.0"},
             "config": {"keystore_path": str(ks), "key_id": "issuer-1", "receipts_path": rc, "target_security": TGT}},
            {"plugin": {"plugin_id": BROKER, "version": "1.0.0"},
             "config": {"keystore_path": str(ks), "receipts_path": rc, "service_identity": "mal-sim",
                        "target_security": TGT, "lab_policy": LAB, "role_allowed_actions": ["compromise"]}}]


def scenario_body(manifest, version_id: str, name: str) -> dict:
    m = manifest.model_dump(mode="json")
    body = {k: m[k] for k in ("environment", "participants", "objectives", "budget", "seed", "stop_conditions",
                              "execution_gates") if k in m}
    for k in ("turns", "termination"):
        if m.get(k):
            body[k] = m[k]
    if body.get("termination"):
        body["stop_conditions"] = []
    return {"name": name, "description": m.get("description") or "", "model_version_id": version_id, **body}


def step_row(page, n: int):
    return page.locator("table[aria-label='步骤列表'] tbody tr").filter(
        has=page.locator("td.num", has_text=re.compile(rf"^{n}$"))).first


def test_mal_domain_flow_through_every_entry(stack, web, browser, tmp_path):
    from formal_lab_domain_mal.run import red_blue_scenario, red_team_scenario

    record: dict = {"entries": {}, "checks": {}}
    sdk = Client(stack.base)
    project = sdk.create_project(f"B3 MAL 攻击图 {uuid.uuid4().hex[:6]}",
                                 "B3: MAL attack graph — import → configure → run → explain → export → replay")
    pid = project["id"]
    SCREENS.mkdir(parents=True, exist_ok=True)
    ctx = browser.new_context(viewport=DESKTOP, locale="zh-CN", accept_downloads=True)
    page = ctx.new_page()

    # 1. Web: import the attack graph from its source through the MAL model-frontend form
    page.goto(f"{web}/p/{pid}/models")
    page.get_by_role("button", name="新建模型").first.click()
    page.get_by_label("package_id").fill("mal-net-app-data")
    page.get_by_label("名称", exact=True).fill("MAL net-app-data 攻击图")
    page.get_by_label("模型来源").select_option("source")
    fe_select = page.get_by_label("模型前端")
    fe_select.locator("option", has_text="MAL 攻击图").first.wait_for(state="attached", timeout=30000)
    fe_select.select_option(f"{MAL_FE['plugin_id']}@{MAL_FE['version']}")
    assert page.get_by_label("源格式").input_value() == FORMAT
    page.get_by_label("源内容", exact=True).fill(json.dumps(envelope(), ensure_ascii=False))
    page.get_by_role("button", name="编译并创建 v1").click()
    page.get_by_test_id("model-source").wait_for(timeout=60000)
    source_text = page.get_by_test_id("model-source").inner_text()
    ext_text = page.get_by_test_id("model-extensions").inner_text()
    assert MAL_FE["plugin_id"] in source_text and FORMAT in source_text and "org.mal-lang.attack-graph" in ext_text
    page.screenshot(path=str(SCREENS / "b3-model-import.png"))
    model_a = next(m for m in sdk.models(pid) if m["package_id"] == "mal-net-app-data")
    va = sdk.model_version(model_a["id"], 1)
    assert va["package"]["frontend"]["plugin_id"] == MAL_FE["plugin_id"]
    assert "org.mal-lang.attack-graph" in va["package"]["extensions"]
    record["entries"]["web_model_import"] = {"model_id": model_a["id"], "version_id": va["id"],
                                             "source": source_text.strip()[:200], "extensions": ext_text.strip(),
                                             "screenshot": "screens/b3-model-import.png"}

    # 2. CLI: import the defence-enabled variant (red / blue) from a source file
    src = tmp_path / "net_app_data.defence.mal.json"
    src.write_text(json.dumps(envelope(include_defense=True), ensure_ascii=False))
    pushed = fal(stack, "model", "push", str(src), "--project", pid, "--package-id", "mal-net-app-data-rb",
                 "--frontend", MAL_FE["plugin_id"], "--source-format", FORMAT)
    model_b = next(m for m in sdk.models(pid) if m["package_id"] == "mal-net-app-data-rb")
    vb = sdk.model_version(model_b["id"], 1)
    assert any(a["name"] == "harden" for a in vb["package"]["payload"]["ir"]["actions"])
    record["entries"]["cli_model_push"] = {"model_id": model_b["id"], "stdout": pushed.stdout.strip()[:200],
                                           "actions": [a["name"] for a in vb["package"]["payload"]["ir"]["actions"]]}

    # 3. SDK: model revision — an incomplete capture (belief) and the full native capture disagree about the target
    graph, native, _ = _fixture()
    goal = native["goal"]
    goal_parents = next(n for n in graph["nodes"] if n["full_name"] == goal)["parents"]
    belief = [s for s in native["compromised"] if s != goal and s not in goal_parents]
    mc = sdk.create_model(pid, "mal-belief", name="MAL 信念模型（不完整捕获 → 完整捕获）",
                          source={"format": FORMAT, "text": json.dumps(envelope(reachable=belief))}, frontend=MAL_FE)
    v1 = sdk.model_version(mc["id"], 1)
    c1 = sdk.check(v1["id"], CHECK)
    sdk.add_model_version(mc["id"], note="完整原生捕获（修订）", source={"format": FORMAT, "text": json.dumps(envelope())},
                          frontend=MAL_FE)
    v2 = sdk.model_version(mc["id"], 2)
    c2 = sdk.check(v2["id"], CHECK)
    assert c1.verdict != "WITNESS" and c2.verdict == "WITNESS" and c2.witness.replay == "CONFIRMED"
    record["checks"]["model_revision"] = {"belief_v1": str(c1.verdict), "truth_v2": str(c2.verdict),
                                          "v2_witness_steps": len(c2.witness.steps) if c2.witness else None,
                                          "deviation": "model error on a comparable state (belief misses the target)"}

    # 4. SDK: configure — per-action gated red team; gated red / blue with the attacker's role view
    work = tmp_path / "broker"
    work.mkdir()
    gates = gate_specs(work)
    red = red_team_scenario(local_package(envelope(), "mal-net-app-data"), execution_gates=gates, strategy="symbolic")
    red_body = scenario_body(red, va["id"], "MAL 红队：逐动作准入（Z3 有界规划）")
    red_body["participants"][0]["label"] = "红队"
    sc_red = sdk.create_scenario(pid, red_body)
    rb = red_blue_scenario(local_package(envelope(include_defense=True), "mal-net-app-data-rb"), strategy="rule",
                           horizon=40, execution_gates=gates)
    rb_body = scenario_body(rb, vb["id"], "MAL 红蓝对抗：逐动作准入 + 攻击方视图")
    rb_body["participants"][0].update(label="红队", view={"exclude": ["hardened"], "label": "攻击方视图（看不到加固）"})
    rb_body["participants"][1]["label"] = "蓝队"
    sc_rb = sdk.create_scenario(pid, rb_body)
    st_z3 = sdk.create_strategy(pid, "红队 Z3 有界规划", "formal-lab.planner.z3-bounded",
                                red.participants[0].strategy.config)
    st_rule = sdk.create_strategy(pid, "红队规则（贪心）", "formal-lab.domain.mal.red-rule", {})
    record["entries"]["sdk_configure"] = {"scenarios": [sc_red["id"], sc_rb["id"]],
                                          "strategies": [st_z3["id"], st_rule["id"]],
                                          "gates": [g["plugin"]["plugin_id"] for g in gates]}

    # 5. Web: the scenario form shows the configured gates and keeps them on save
    page.goto(f"{web}/p/{pid}/scenarios/{sc_red['id']}")
    card = page.get_by_test_id("gates-editor")
    card.locator("select").first.wait_for(timeout=60000)
    page.wait_for_timeout(500)
    shown = card.locator("select").evaluate_all("els => els.map((e) => e.value)")
    assert shown == [f"{ISSUER}@1.0.0", f"{BROKER}@1.0.0"], shown
    card.screenshot(path=str(SCREENS / "b3-scenario-gates.png"))
    page.get_by_role("button", name="保存（新修订）").click()
    page.get_by_text("已保存（修订 r2）").wait_for(timeout=30000)
    saved = stack.get(f"/scenarios/{sc_red['id']}")
    assert saved["revision"] == 2 and [g["plugin"]["plugin_id"] for g in saved["manifest"]["execution_gates"]] \
        == [ISSUER, BROKER]
    record["entries"]["web_scenario_form"] = {"gates_shown": shown, "revision_after_save": saved["revision"],
                                              "gates_kept": True, "screenshot": "screens/b3-scenario-gates.png"}

    # 6. CLI: run the gated red-team scenario
    started = fal(stack, "run", "start", "--project", pid, "--scenario", sc_red["id"], "--wait", check=False)
    run_id = started.stdout.split()[1]
    run = sdk.run(run_id)
    assert run["status"] == "SUCCEEDED", started.stdout + started.stderr
    record["entries"]["cli_run_start"] = {"run_id": run_id, "status": run["status"], "steps": run["last_step"]}

    # 7. API + CLI: explain a step — the decision, the per-send Broker decisions, the effect comparison
    step = httpx.get(f"{stack.base}/runs/{run_id}/steps/1", timeout=30).json()
    cli_step = json.loads(fal(stack, "run", "step", run_id, "1").stdout)
    decisions = step["decisions"]
    assert [d["gate"]["plugin_id"] for d in decisions] == [ISSUER, BROKER]
    assert all(d["verdict"] == "ALLOW" for d in decisions) and decisions[0]["checked_at_revision"] is not None
    assert [d["verdict"] for d in cli_step["decisions"]] == ["ALLOW", "ALLOW"]
    assert step["proposal"]["action"]["action_type"] == "compromise" and step["comparison"]["verdict"] == "MATCH"
    record["entries"]["api_cli_explain_step1"] = {
        "action": step["proposal"]["action"], "source": step["proposal"]["source"]["kind"],
        "decisions": [{"gate": d["gate"]["plugin_id"], "verdict": d["verdict"], "revision": d["checked_at_revision"],
                       "reason": d["reason"][:160]} for d in decisions],
        "comparison": step["comparison"]["verdict"], "expected_by": step["comparison"]["expected_by"]}

    # 8. API: the red / blue game
    rb_run = stack.post(f"/projects/{pid}/runs", {"scenario_id": sc_rb["id"], "seed": 0})
    rb_done = stack.wait_status(rb_run["id"], FINISHED, timeout=900)
    events = stack.events(rb_run["id"])
    outcomes = [(e["actor_id"], e["payload"]["outcome"]["status"]) for e in events if e["event_type"] == "ACTION_OUTCOME"]
    denials = [e["payload"]["decision"] for e in events if e["event_type"] == "EXECUTION_DECIDED"
               and e["payload"]["decision"]["verdict"] == "DENY"]
    passes = [e["payload"]["decision"] for e in events if e["event_type"] == "EXECUTION_DECIDED"
              and e["actor_id"] == "blue"]
    assert ("blue", "APPLIED") in outcomes and ("red", "REJECTED") in outcomes
    assert denials and all(d["gate"]["plugin_id"] == ISSUER and "ACTION_PRECONDITION_FAILED" in d["reason"]
                           for d in denials)
    assert passes and all("outside this gate's admission scope" in d["reason"] for d in passes)
    denied_step = denials[0]["step"]
    deny = httpx.get(f"{stack.base}/runs/{rb_run['id']}/steps/{denied_step}", timeout=30).json()
    assert deny["outcome"]["status"] == "REJECTED" and deny["decisions"][0]["verdict"] == "DENY"
    assert len(deny["decisions"]) == 1  # the Broker is never asked: no receipt exists, nothing is sent
    red_turns = [e["payload"] for e in events if e["event_type"] == "OBSERVATION" and e["actor_id"] == "red"
                 and e["logical_step"]]  # step 0 is the initial observation, before anyone plans
    withheld = red_turns[0]["planner_input"]["withheld"]
    assert withheld and all(w.startswith("hardened") for w in withheld)
    assert all(o["planner_input"]["withheld"] == withheld for o in red_turns)
    record["entries"]["api_red_blue"] = {
        "run_id": rb_run["id"], "status": rb_done["status"], "steps": rb_done["last_step"],
        "outcomes": {f"{a}:{s}": outcomes.count((a, s)) for a, s in sorted(set(outcomes))},
        "denied_step": denied_step, "deny_reason": denials[0]["reason"][:200],
        "blue_pass_reason": passes[0]["reason"][:160], "red_withheld_locations": len(withheld)}

    # 9. Web: run console, step explanation with the Broker decisions; the denied red step under red's perspective
    page.goto(f"{web}/p/{pid}/runs/{run_id}")
    page.get_by_text(re.compile(r"已结束 · \d+ 事件")).wait_for(timeout=60000)
    step_row(page, 1).click()
    page.get_by_test_id("execution-decisions").wait_for(timeout=30000)
    detail = page.locator("main").inner_text()
    assert BROKER in detail and ISSUER in detail and "攻陷步骤" in detail
    page.screenshot(path=str(SCREENS / "b3-step-broker-decisions.png"))
    with page.expect_download() as dl:
        page.get_by_role("link", name="导出").first.click()
    web_bundle = tmp_path / "web.replay.zip"
    dl.value.save_as(str(web_bundle))
    page.goto(f"{web}/p/{pid}/runs/{rb_run['id']}")
    page.get_by_text(re.compile(r"已结束 · \d+ 事件")).wait_for(timeout=60000)
    page.get_by_label("参与者视角").select_option("red")
    step_row(page, denied_step).click()
    page.get_by_test_id("planner-input").wait_for(timeout=30000)
    rb_detail = page.locator("main").inner_text()
    assert "DENY" in rb_detail and "ACTION_PRECONDITION_FAILED" in rb_detail and "攻击方视图" in rb_detail
    page.screenshot(path=str(SCREENS / "b3-red-denied-step.png"))
    record["entries"]["web_console"] = {"bundle_bytes": web_bundle.stat().st_size, "screenshots": [
        "screens/b3-step-broker-decisions.png", "screens/b3-red-denied-step.png"]}

    # 10. role views: each participant downloads only its own projection
    full_text = httpx.get(f"{stack.base}/runs/{rb_run['id']}/export", timeout=60).content
    views = {}
    for actor, other in (("red", "blue"), ("blue", "red")):
        tok = stack.post(f"/runs/{rb_run['id']}/participants/{actor}/access", expect=201)["token"]
        dlr = stack.client.get("/participant/export", headers={"Authorization": f"Bearer {tok}"}, timeout=60)
        assert dlr.status_code == 200
        mine = read_bundle(dlr.content)
        text = json.dumps([e.model_dump(mode="json") for e in mine.events], ensure_ascii=False) \
            + json.dumps(mine.manifest.model_dump(mode="json"), ensure_ascii=False)
        leaks = [s for s in (str(work), "keys.json", "receipts.json") if s in text]
        theirs = next(p for p in mine.manifest.participants if p.actor_id == other)
        assert {e.actor_id for e in mine.events} <= {None, actor} and not leaks and theirs.strategy.config == {}
        views[actor] = {"events": len(mine.events), "credential_paths": leaks, "other_config_removed": True}
    assert len(read_bundle(full_text).events) > max(v["events"] for v in views.values())
    record["checks"]["role_views"] = views

    # 11. Web: evidence replay of the red / blue run
    page.goto(f"{web}/p/{pid}/evidence/{rb_run['id']}")
    position = page.get_by_text(re.compile(r"^步 \d+ / \d+$"))
    position.wait_for(timeout=60000)
    page.locator("main h2").first.click()  # focus the page (arrow keys step the replay outside form fields)
    for _ in range(rb_done["last_step"] + 1):
        if position.inner_text().startswith(f"步 {denied_step} /"):
            break
        page.keyboard.press("ArrowRight")
    assert position.inner_text().startswith(f"步 {denied_step} /")
    replay_text = page.locator("main").inner_text()
    assert "DENY" in replay_text and "ACTION_PRECONDITION_FAILED" in replay_text
    page.screenshot(path=str(SCREENS / "b3-evidence-replay.png"))
    page.get_by_role("tab", name="关联定位").click()
    page.get_by_test_id("navigator").wait_for(timeout=30000)
    record["entries"]["web_evidence"] = {"run_id": rb_run["id"], "replayed_step": denied_step,
                                         "screenshot": "screens/b3-evidence-replay.png"}

    # 12. SDK + Web: a strategy matrix on the gated red-team scenario (Z3 vs rule), shown on the benchmark page
    mx = sdk.create_matrix_v2(pid, {"version": 2, "name": "MAL 红队策略对比（逐动作准入）", "scenarios": [sc_red["id"]],
                                    "seeds": [0], "participants": [{"red": st_z3["id"]}, {"red": st_rule["id"]}],
                                    "max_parallel": 1})
    mid = mx["matrix"]["id"]
    deadline = time.time() + 900
    while time.time() < deadline:
        cells = sdk.matrix_cells(mid)
        if cells and all(c["status"] in ("DONE", "FAILED", "SKIPPED") for c in cells):
            break
        time.sleep(1)
    assert len(cells) == 2 and all(c["status"] == "DONE" for c in cells), cells
    report = sdk.matrix_report(mid)
    page.goto(f"{web}/p/{pid}/benchmarks/{mid}")
    page.get_by_role("heading", name="MAL 红队策略对比（逐动作准入）").wait_for(timeout=60000)
    page.wait_for_timeout(800)
    page.screenshot(path=str(SCREENS / "b3-benchmark.png"))
    record["entries"]["sdk_web_matrix"] = {"matrix_id": mid, "cells": [c["status"] for c in cells],
                                           "complete": report.get("complete"), "screenshot": "screens/b3-benchmark.png"}
    ctx.close()

    # 13. CLI: export, then offline — the API is stopped and the bundle still verifies and explains its steps
    cli_bundle = tmp_path / "cli.replay.zip"
    fal(stack, "export", run_id, "-o", str(cli_bundle))
    a, b = read_bundle(web_bundle.read_bytes()), read_bundle(cli_bundle.read_bytes())
    assert len(a.events) == len(b.events) == run["event_seq"] and a.manifest.run_id == b.manifest.run_id == run_id
    stack.stop()
    try:
        with pytest.raises(httpx.HTTPError):
            httpx.get(f"{stack.base}/health", timeout=2).raise_for_status()
        empty = tmp_path / "offline"
        empty.mkdir()
        verify = fal(stack, "replay", "verify", str(cli_bundle), cwd=empty)
        view = fal(stack, "replay", "view", str(web_bundle), cwd=empty)
        step1 = json.loads(fal(stack, "replay", "step", str(cli_bundle), "1", cwd=empty).stdout)
        offline_action = step1["proposal"].get("proposal", step1["proposal"])["action"]
        offline_gates = [d.get("decision", d)["gate"]["plugin_id"] for d in step1.get("decisions", [])]
        assert verify.stdout.startswith("OK") and offline_action == step["proposal"]["action"]
        assert offline_gates == [ISSUER, BROKER]
        record["entries"]["offline_replay_api_stopped"] = {"api_reachable": False, "verify": verify.stdout.strip()[:200],
                                                           "view_lines": len(view.stdout.splitlines()),
                                                           "step1_action": offline_action, "step1_gates": offline_gates}
    finally:
        stack.start_api()
        stack.start_worker()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "b3-product-flow.json").write_text(json.dumps(
        {"deliverable": "phase4B-B3 domain product flow", "domain": "MAL coreLang attack graph (net-app-data)",
         "project_id": pid, **record}, indent=2, ensure_ascii=False) + "\n")
