"""Model–program conformance (P5A-02): replay the committed run on each model and check the three layers stay apart —
the model's own verdict, the program regression, and whether the two correspond. The deviation is re-derived from the
recorded observation (deterministic), so the belief model DEVIATES and the revised model CORRESPONDS as real results."""

from __future__ import annotations

from pathlib import Path

import pytest
from formal_lab_contracts.research import (
    ConformanceItem,
    CounterexampleEvidence,
    ModelConclusion,
    ProgramRegression,
    ResearchCase,
)
from formal_lab_runtime.research import decide_correspondence, load_case, replay_conformance

ROOT = Path(__file__).resolve().parents[2]
CASE = ROOT / "research" / "cases" / "orders-p2-speed"

pytestmark = pytest.mark.skipif(not (CASE / "case.json").exists(), reason="the orders-p2-speed case is not built")

UNKNOWN_CONCLUSION = ModelConclusion(verdict="UNKNOWN", query="GOAL_REACHABILITY(all_completed)")
PASS_REGRESSION = ProgramRegression(status="PASS")


def _files_and_case():
    files = load_case(CASE)
    return files, ResearchCase.model_validate(files.document)


def test_belief_model_deviates_from_the_real_run():
    files, case = _files_and_case()
    res = replay_conformance(files, case, model_label="v1", property_id="all_completed", observation_id="obs-run",
                             model_conclusion=UNKNOWN_CONCLUSION, program_regression=PASS_REGRESSION)
    assert res.correspondence == "DEVIATES"
    assert res.counts.get("DIFFERENT", 0) >= 1 and res.counts.get("MATCH", 0) >= 1
    assert any(it.status == "DIFFERENT" for it in res.items)


def test_revised_model_corresponds_on_the_same_run():
    files, case = _files_and_case()
    res = replay_conformance(files, case, model_label="v2", property_id="all_completed", observation_id="obs-run",
                             model_conclusion=UNKNOWN_CONCLUSION, program_regression=PASS_REGRESSION)
    assert res.correspondence == "CORRESPONDS"
    assert res.counts.get("DIFFERENT", 0) == 0 and res.counts.get("MATCH", 0) >= 1


def test_three_layers_are_recorded_apart():
    files, case = _files_and_case()
    res = replay_conformance(files, case, model_label="v1", property_id="all_completed", observation_id="obs-run",
                             model_conclusion=UNKNOWN_CONCLUSION,
                             program_regression=ProgramRegression(status="PASS", summary="suite green"))
    # a model verdict, a program regression, and a correspondence that is none of the two
    assert res.model_conclusion.verdict == "UNKNOWN"
    assert res.program_regression.status == "PASS"
    assert res.correspondence == "DEVIATES"
    assert "equivalence" in res.scope  # the scope text denies that agreement is semantic equivalence


def test_no_observation_is_not_comparable():
    files, case = _files_and_case()
    res = replay_conformance(files, case, model_label="v1", property_id="all_completed", observation_id=None,
                             model_conclusion=UNKNOWN_CONCLUSION, program_regression=ProgramRegression(status="NOT_RUN"))
    assert res.correspondence == "NOT_COMPARABLE" and not res.program_observations


def test_correspondence_decision_branches():
    match = [ConformanceItem(element="remaining[o1]", status="MATCH", evidence="observed")]
    diff = [ConformanceItem(element="remaining[o1]", status="DIFFERENT", predicted=3, observed=4, evidence="observed")]
    assert decide_correspondence(diff, has_observation=True)[0] == "DEVIATES"
    assert decide_correspondence(match, has_observation=False)[0] == "NOT_COMPARABLE"
    # a model counterexample is UNCONFIRMED until the program shows it, SPURIOUS only with evidence of abstraction error
    witness = ModelConclusion(verdict="WITNESS", query="INVARIANT_VIOLATION(on_time)")
    assert decide_correspondence(match, has_observation=True, model_conclusion=witness)[0] == "UNCONFIRMED"
    spurious = CounterexampleEvidence(status="abstraction_error", artifact_id="obs-run", note="unmodelled retry")
    assert decide_correspondence(match, has_observation=True, counterexample=spurious)[0] == "SPURIOUS"
    reproduced = CounterexampleEvidence(status="reproduced", artifact_id="obs-run", note="seen on the run")
    assert decide_correspondence(match, has_observation=True, counterexample=reproduced)[0] == "CORRESPONDS"
    unsupported = ModelConclusion(verdict="UNSUPPORTED")
    assert decide_correspondence(match, has_observation=True, model_conclusion=unsupported)[0] == "UNSUPPORTED"
