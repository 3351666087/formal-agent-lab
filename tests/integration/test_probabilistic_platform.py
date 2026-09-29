"""Optional PRISM-games track through the platform (P2-X04): the typed game payload in, the typed probabilistic
record out, kept apart from the deterministic Z3 checks — over the API and in the model workbench."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from formal_lab_solver_prism import EXAMPLE, Unavailable, locate

pytestmark = pytest.mark.integration
SHOTS = Path(__file__).resolve().parents[2] / os.environ.get("FAL_EVIDENCE_DIR", "docs/execution/evidence/phase3") / "prism-games"  # phase 2 sets FAL_EVIDENCE_DIR


def _installed() -> bool:
    try:
        locate()
        return True
    except Unavailable:
        return False


needs_prism = pytest.mark.skipif(not _installed(), reason="PRISM-games not installed (optional extension track)")


def _version_id(stack, demo) -> str:
    model = stack.get(f"/projects/{demo['project']}/models")[0]
    return stack.get(f"/models/{model['id']}/versions/{model['latest_version']}")["id"]


def test_extension_reports_its_backend_assumptions_and_distribution(stack):
    info = stack.get("/extensions/prism-games")
    assert info["game_schema"] == "org.formal-lab.prism-games/allocation-game@1"
    assert info["pinned"]["license"] == "GPL-2.0" and "not shipped" in info["distribution"]
    assert info["available"] is _installed()
    if not info["available"]:
        assert "not installed" in info["reason"]


def test_request_without_a_game_is_rejected_at_the_field(stack, demo):
    vid = _version_id(stack, demo)
    r = stack.client.post(f"/model-versions/{vid}/probabilistic-checks", json={})
    assert r.status_code == 422 and "org.formal-lab.prism-games" in r.json()["error"]["message"]
    bad = EXAMPLE.model_dump(mode="json") | {"rounds": 99}
    r = stack.client.post(f"/model-versions/{vid}/probabilistic-checks", json={"game": bad})
    assert r.status_code == 422 and "rounds" in r.json()["error"]["message"]


@needs_prism
def test_probabilistic_check_is_verified_stored_and_listed_apart_from_z3(stack, demo):
    vid = _version_id(stack, demo)
    z3_before = len(stack.get(f"/model-versions/{vid}/checks"))
    res = stack.post(f"/model-versions/{vid}/probabilistic-checks", {"game": EXAMPLE.model_dump(mode="json")})
    rec = res["record"]
    assert rec["schema_id"] == "org.formal-lab.prism-games/result@1" and rec["kind"] == "PROBABILISTIC"
    assert rec["verified"] and rec["size"]["states"] == rec["reference_states"] == 91
    robust, coop = rec["properties"]
    assert robust["agrees"] and coop["agrees"] and 0 < robust["value"] < coop["value"] < 1
    assert abs(rec["strategy_value"] - robust["value"]) <= 1e-6
    listed = stack.get(f"/model-versions/{vid}/probabilistic-checks")
    assert listed[0]["check_id"] == res["check_id"]
    assert len(stack.get(f"/model-versions/{vid}/checks")) == z3_before  # never mixed into the Z3 list


@needs_prism
@pytest.mark.ui
def test_model_workbench_shows_probabilistic_conclusions_separately(page, web, stack, demo):
    page.goto(f"{web}/p/{demo['project']}/models")
    page.get_by_text("类型检查通过").wait_for(timeout=20000)
    page.get_by_role("tab", name="概率扩展").click()
    panel = page.get_by_test_id("probabilistic-panel")
    panel.get_by_text("prism-games 3.2.4（").wait_for(timeout=20000)  # the backend field, not a result's line
    results = panel.get_by_test_id("prob-result")
    page.wait_for_function("document.querySelector('[data-testid=prob-result]') || "
                           "document.body.innerText.includes('还没有概率查询')", timeout=20000)  # list loaded
    before = results.count()
    panel.get_by_role("button", name="运行概率查询").click()
    panel.get_by_role("button", name="运行概率查询").wait_for(timeout=60000)  # "求解中…" while it runs
    page.wait_for_function(f"document.querySelectorAll('[data-testid=prob-result]').length > {before}", timeout=20000)
    assert "模型内核对通过" in results.first.inner_text()
    assert "确定性结论" in panel.inner_text()
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS / "workbench-probabilistic.jpg"), type="jpeg", quality=72, full_page=True)
