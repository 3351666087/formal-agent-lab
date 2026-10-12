"""Phase 6B: the isolation-judgment scorer (program-grounded, real results), the frozen rubric, the answer-leak
guard, and that the two business framings of a synthetic base encode the same verified-equal problem."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from formal_lab_contracts.errors import InvalidInput
from formal_lab_eval.research import load_study, plan_units
from formal_lab_eval.research_scorers import load_rubric, rubric_digest, scorer_for

ROOT = Path(__file__).resolve().parents[3]
STUDY = ROOT / "research" / "studies" / "p6b-eval"
pytestmark = pytest.mark.skipif(not (STUDY / "study.json").exists(), reason="p6b-eval not built")


def _ref(name: str) -> dict:
    return json.loads((STUDY / "reference" / name).read_text())


def test_isolation_scorer_is_grounded_in_the_recorded_run():
    s = scorer_for("orders.isolation-judgment", "1")
    defect, fix = _ref("isolation-defect.json"), _ref("isolation-fix.json")
    # the correct answer for each variant (from the recorded run, not hand-written)
    good_defect = s.score(defect["answer"], defect, repo_root=ROOT, truncated=False)
    assert good_defect.behavior == "CORRECT" and good_defect.program_correspondence == "CORRESPONDS"
    assert good_defect.signals["violation_identified"] is True
    good_fix = s.score(fix["answer"], fix, repo_root=ROOT, truncated=False)
    assert good_fix.behavior == "CORRECT" and good_fix.program_correspondence == "CORRESPONDS"
    # wrong verdicts deviate from the independently recorded run
    wrong = s.score({"isolation_holds": True, "violations": []}, defect, repo_root=ROOT, truncated=False)
    assert wrong.behavior == "INCORRECT" and wrong.program_correspondence == "DEVIATES"
    missed = s.score({"isolation_holds": False, "violations": []}, defect, repo_root=ROOT, truncated=False)
    assert missed.behavior == "CORRECT" and missed.signals["violation_identified"] is False  # right verdict, no cite
    assert set(good_defect.dependencies) == {"observation", "conformance"}


def test_isolation_scorer_rejects_tampered_evidence(tmp_path):
    s = scorer_for("orders.isolation-judgment", "1")
    ref = _ref("isolation-defect.json")
    ref["observation"]["sha256"] = "0" * 64
    with pytest.raises(InvalidInput, match="changed"):
        s.score(ref["answer"], ref, repo_root=ROOT, truncated=False)


def test_rubric_is_frozen_by_version_and_digest(tmp_path):
    rub = load_rubric(ROOT, "fal-research-rubric", "1")
    assert rub["digest"] == rubric_digest(rub) and len(rub["dimensions"]) == 6
    assert {d["id"] for d in rub["dimensions"]} == {"formal_correctness", "program_correspondence", "assumption_scope",
                                                    "observable_safety", "refusal_appropriateness", "usefulness_cost"}
    bad = ROOT / "research" / "rubric" / "fal-research-rubric-1.json"
    d = tmp_path / "research" / "rubric"
    d.mkdir(parents=True)
    doc = json.loads(bad.read_text())
    doc["dimensions"][0]["basis"] = "edited without a new version"
    (d / "fal-research-rubric-1.json").write_text(json.dumps(doc))
    with pytest.raises(InvalidInput, match="digest mismatch"):
        load_rubric(tmp_path, "fal-research-rubric", "1")


def test_answer_leak_guard_rejects_a_reference_answer_in_an_input(tmp_path):
    d = tmp_path / "s"
    shutil.copytree(STUDY, d)
    ans = _ref("isolation-defect.json")["answer"]
    (d / "inputs" / "isolation-defect.md").write_text(
        (d / "inputs" / "isolation-defect.md").read_text() + "\n" + json.dumps(ans))
    with pytest.raises(InvalidInput, match="ANSWER_LEAK"):
        load_study(d)


def test_two_business_framings_encode_the_same_verified_problem():
    study = load_study(STUDY)
    by_ref: dict[str, list[str]] = {}
    for t in study.tasks:
        if str(t.track) == "synthetic_representation":
            by_ref.setdefault(t.reference, []).append(t.representation_id)
    # each base problem has exactly two framings sharing one reference (same sample, digest and shortest answer)
    assert sorted(by_ref["reference/counter.json"]) == ["garage", "library"]
    assert sorted(by_ref["reference/route.json"]) == ["approval", "courier"]
    counter = _ref("counter.json")
    assert counter["sample"] == "lamp" and counter["shortest_length"] == 3 and counter["model_digest"]


def test_frozen_batch_is_24_static_units():
    units, not_run = plan_units(load_study(STUDY))
    assert len(units) == 24 and not not_run
    assert {u.mode for u in units} == {"STATIC_UNASSISTED"}  # the frozen batch is unassisted
