"""Research cases through the platform API (phase 5A): import validates, provenance is readable, a model version and
the imported run both trace back to the case, export round-trips, and a tampered case is rejected on import."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CASE = ROOT / "research" / "cases" / "orders-p2-speed"

pytestmark = pytest.mark.integration


def _zip_case(mutate=None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(CASE.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(CASE).as_posix()
            data = p.read_bytes()
            if rel == "case.json" and mutate is not None:
                data = mutate(data)
            zf.writestr(f"{CASE.name}/{rel}", data)
    return buf.getvalue()


def _fresh_project(stack, name: str) -> str:
    """The integration database outlives a session: drop leftovers of this test (projects cascade to their runs,
    so the case's recorded observation run can be imported again)."""
    for prj in stack.get("/projects"):
        if prj["name"] == name:
            stack.client.delete(f"/projects/{prj['id']}")
    return stack.post("/projects", json={"name": name})["id"]


@pytest.mark.skipif(not (CASE / "case.json").exists(), reason="the orders-p2-speed case is not built")
def test_research_case_import_provenance_and_export(stack):
    pid = _fresh_project(stack, "research-it")

    detail = stack.post(f"/projects/{pid}/research/cases", content=_zip_case(),
                        headers={"content-type": "application/zip"}, expect=201)
    assert detail["case_id"] == "orders-p2-speed" and detail["track"] == "implementation_conformance"
    assert len(detail["software"]["trees"]) == 1 and len(detail["software"]["revision"]) == 40
    assert len(detail["models"]) == 2
    verdicts = {c["label"]: c["correspondence"] for c in detail["conformance"]}
    assert verdicts == {"conf-v1": "DEVIATES", "conf-v2": "CORRESPONDS"}
    assert detail["observation_run_id"]  # the recorded run was imported

    # provenance list
    cases = stack.get(f"/projects/{pid}/research/cases")
    assert any(c["id"] == detail["id"] for c in cases)

    # a model version traces back to the case it is verified in
    mv_id = next(c["model_version_id"] for c in detail["conformance"] if c["model_version_id"])
    linked = stack.get(f"/model-versions/{mv_id}/research")
    assert any(c["case_id"] == "orders-p2-speed" for c in linked)

    # the imported run traces back to the conformance verdicts
    run_research = stack.get(f"/runs/{detail['observation_run_id']}/research")
    assert run_research and run_research[0]["conformance"]

    # export round-trips: the downloaded zip validates offline against the protocol
    r = stack.client.get(f"/research/cases/{detail['id']}/export")
    r.raise_for_status()
    from formal_lab_runtime.research import load_case, validate_case

    report, case = validate_case(load_case(r.content), repo=None)
    assert report.ok, report.as_dict()
    assert case.identity.case_id == "orders-p2-speed"


@pytest.mark.skipif(not (CASE / "case.json").exists(), reason="the orders-p2-speed case is not built")
def test_import_rejects_a_tampered_case(stack):
    pid = _fresh_project(stack, "research-it-bad")

    def tamper(data: bytes) -> bytes:
        return data.replace(b'"timing-model-deviation"', b'"tampered-family"')  # digest no longer matches

    r = stack.client.post(f"/projects/{pid}/research/cases", content=_zip_case(mutate=tamper),
                          headers={"content-type": "application/zip"})
    assert r.status_code in (400, 422), (r.status_code, r.text)
    assert "CASE_DIGEST_MISMATCH" in r.text


STUDY = ROOT / "research" / "studies" / "p6a-protocol"
STUDY_RESULTS = ROOT / "research" / "results" / "p6a-protocol"


def _zip_study(tamper: bool = False) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("study.json", (STUDY / "study.json").read_bytes())
        for p in sorted(STUDY_RESULTS.rglob("*")):
            if not p.is_file():
                continue
            data = p.read_bytes()
            if tamper and p.parent.name == "responses" and p.name.startswith("orders-deviation.ptest-openai.S.r1"):
                data = data.replace(b"p1", b"p9")  # an answer edited after it was recorded
            zf.writestr(f"results/{p.relative_to(STUDY_RESULTS).as_posix()}", data)
    return buf.getvalue()


@pytest.mark.skipif(not (STUDY_RESULTS / "ledger.jsonl").exists(), reason="p6a-protocol results not produced")
def test_research_study_import_shows_units_and_raw_answers(stack):
    pid = _fresh_project(stack, "study-it")
    d = stack.post(f"/projects/{pid}/research/studies", content=_zip_study(),
                   headers={"content-type": "application/zip"}, expect=201)
    assert d["units"] == 24 and d["tracks"] == ["implementation_conformance", "synthetic_representation"]
    by = {u["unit_id"]: u for u in d["unit_summaries"]}
    refused = "orders-deviation.ptest-anthropic.S.r0"
    assert by[refused]["outcome"] == "CONTENT_REFUSAL" and by[refused]["behavior"] == "REFUSED"
    unit = stack.get(f"/research/studies/{d['id']}/units/{refused}")
    assert unit["response"]["raw"]["refusal"] and unit["evaluation"]["behavior_label"] == "REFUSED"
    again = stack.post(f"/projects/{pid}/research/studies", content=_zip_study(),
                       headers={"content-type": "application/zip"}, expect=201)
    assert [s["id"] for s in stack.get(f"/projects/{pid}/research/studies")] == [again["id"]]  # replaced
    r = stack.client.post(f"/projects/{pid}/research/studies", content=_zip_study(tamper=True),
                          headers={"content-type": "application/zip"})
    assert r.status_code in (400, 422) and "changed after it was recorded" in r.text
