"""Import validation of a research case (P5A-01): every check runs against the real committed case, mutated in a
temp copy, so each assertion is an actual validator result — not a hand-written boolean.

Scenarios: a valid ordinary case, property mismatch, version mismatch, a missing observation, stale evidence, the
data-separation rule (a reference answer must not be a task input), and offline read (a zip, no repository)."""

from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

import pytest
from formal_lab_runtime.research import compute_case_digest, load_case, sha256_bytes, validate_case

ROOT = Path(__file__).resolve().parents[2]
CASE = ROOT / "research" / "cases" / "orders-p2-speed"

pytestmark = pytest.mark.skipif(not (CASE / "case.json").exists(), reason="the orders-p2-speed case is not built")


def clone(tmp: Path) -> Path:
    d = tmp / "case"
    shutil.copytree(CASE, d)
    return d


def reseal(d: Path) -> None:
    """Recompute every artifact sha and the case digest from the files on disk, so a single edit is the only problem."""
    doc = json.loads((d / "case.json").read_text())
    for a in doc["artifacts"]:
        a["sha256"] = sha256_bytes((d / a["path"]).read_bytes())
    doc["case_digest"] = compute_case_digest(doc)
    (d / "case.json").write_text(json.dumps(doc, ensure_ascii=False))


def codes(d: Path, *, repo: Path | None = ROOT) -> set[str]:
    report, _ = validate_case(load_case(d), repo=repo)
    return {p.code for p in report.problems}


def edit_conf(d: Path, label: str, change) -> None:
    f = d / "conformance" / f"{label}-all_completed.result.json"
    doc = json.loads(f.read_text())
    change(doc)
    f.write_text(json.dumps(doc, ensure_ascii=False))


def test_valid_ordinary_case(tmp_path):
    report, case = validate_case(load_case(clone(tmp_path)), repo=ROOT)
    assert report.ok, report.as_dict()
    assert case is not None and case.identity.case_id == "orders-p2-speed"
    assert report.checked["conformance"] == 2 and report.checked["model"] == 2


def test_tampered_case_without_updated_digest_is_rejected(tmp_path):
    d = clone(tmp_path)
    doc = json.loads((d / "case.json").read_text())
    doc["identity"]["purpose"] = "something else"  # content changed, digest not updated
    (d / "case.json").write_text(json.dumps(doc, ensure_ascii=False))
    assert "CASE_DIGEST_MISMATCH" in codes(d)


def test_property_digest_mismatch(tmp_path):
    d = clone(tmp_path)
    doc = json.loads((d / "case.json").read_text())
    doc["models"][0]["properties"][0]["digest"] = "0" * 64
    (d / "case.json").write_text(json.dumps(doc, ensure_ascii=False))
    reseal(d)  # digest/shas consistent again, so the declared property digest is the only wrong thing
    assert "PROPERTY_DIGEST_MISMATCH" in codes(d)


def test_model_version_mismatch(tmp_path):
    d = clone(tmp_path)
    doc = json.loads((d / "case.json").read_text())
    doc["models"][0]["model_ref"]["version"] = 99
    (d / "case.json").write_text(json.dumps(doc, ensure_ascii=False))
    reseal(d)
    assert "MODEL_REF_MISMATCH" in codes(d)


def test_software_revision_unknown(tmp_path):
    d = clone(tmp_path)
    doc = json.loads((d / "case.json").read_text())
    doc["software"]["revision"] = "0" * 40
    (d / "case.json").write_text(json.dumps(doc, ensure_ascii=False))
    reseal(d)
    assert "REVISION_UNKNOWN" in codes(d)  # a name cannot stand in for a real tree at a real revision


def test_missing_observation(tmp_path):
    d = clone(tmp_path)
    edit_conf(d, "v1", lambda doc: doc.update(program_observations=[]))  # decisive correspondence, nothing to compare
    reseal(d)
    assert "MISSING_OBSERVATION" in codes(d)


def test_stale_conformance(tmp_path):
    d = clone(tmp_path)
    edit_conf(d, "v1", lambda doc: doc["program_observations"][0].update(sha256="0" * 64))
    reseal(d)
    assert "STALE_CONFORMANCE" in codes(d)  # result computed from an observation the case no longer holds


def test_reference_answer_may_not_be_a_task_input(tmp_path):
    d = clone(tmp_path)
    doc = json.loads((d / "case.json").read_text())
    doc["validation"]["task_input_ids"].append("reference")
    (d / "case.json").write_text(json.dumps(doc, ensure_ascii=False))
    reseal(d)
    assert "REFERENCE_IN_TASK_INPUT" in codes(d)


def test_offline_read_from_zip_without_repository(tmp_path):
    d = clone(tmp_path)
    buf = tmp_path / "case.zip"
    with zipfile.ZipFile(buf, "w") as zf:
        for p in sorted(d.rglob("*")):
            if p.is_file():
                zf.write(p, p.relative_to(d.parent).as_posix())
    report, case = validate_case(load_case(buf.read_bytes()), repo=None)
    assert report.ok, report.as_dict()  # self-contained: digests check with no server and no checkout
    assert any(w.code == "SOFTWARE_NOT_VERIFIED_HERE" for w in report.warnings)
    assert case is not None
