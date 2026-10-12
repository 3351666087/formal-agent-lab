"""Phase 6A research studies: validation of a study definition, the answer axis, the two built-in scorers (real
replay / reference-interpreter results, not hand-written booleans), the output cap and the reuse keys."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from formal_lab_contracts.errors import InvalidInput
from formal_lab_contracts.research import ProviderConfig, StudyTask
from formal_lab_eval.research import cap_params, load_study, plan_units, scoring_key
from formal_lab_eval.research_scorers import parse_answer, registered, scorer_for

ROOT = Path(__file__).resolve().parents[3]
STUDY = ROOT / "research" / "studies" / "p6a-protocol"
pytestmark = pytest.mark.skipif(not (STUDY / "study.json").exists(), reason="p6a studies not built")
DIAG = {"type": "object", "properties": {"constant": {"type": "string"}, "station": {"type": "string"},
                                         "value": {"type": "boolean"}},
        "required": ["constant", "station", "value"], "additionalProperties": False}


def test_study_plans_units_and_lists_unimplemented_modes():
    units, not_run = plan_units(load_study(STUDY))
    assert len(units) == 24 and len(not_run) == 4
    assert all(n["mode"] == "ASSISTED" for n in not_run)


def test_a_reference_copied_into_the_task_input_is_rejected(tmp_path):
    d = tmp_path / "s"
    shutil.copytree(STUDY, d)
    shutil.copy(d / "reference" / "orders-deviation.json", d / "inputs" / "leak.json")
    doc = json.loads((d / "study.json").read_text())
    doc["tasks"][0]["inputs"].append("inputs/leak.json")
    (d / "study.json").write_text(json.dumps(doc))
    with pytest.raises(InvalidInput, match="REFERENCE_IN_TASK_INPUT"):
        load_study(d)


def test_unknown_scorer_and_missing_file_are_rejected(tmp_path):
    d = tmp_path / "s"
    shutil.copytree(STUDY, d)
    doc = json.loads((d / "study.json").read_text())
    doc["tasks"][1]["scorer_id"] = "nobody.scorer"
    doc["tasks"][2]["inputs"] = ["inputs/missing.md"]
    (d / "study.json").write_text(json.dumps(doc))
    with pytest.raises(InvalidInput) as exc:
        load_study(d)
    assert "nobody.scorer" in str(exc.value) and "missing.md" in str(exc.value)


@pytest.mark.parametrize("text,expected", [
    ('{"constant": "slow", "station": "p2", "value": true}', "VALID"),
    ('```json\n{"constant": "slow", "station": "p2", "value": true}\n```', "VALID"),
    ("I think p2 is slow.", "INVALID_JSON"),
    ('{"constant": "slow", "station": "p2"}', "SCHEMA_VIOLATION"),
    ('{"constant": "slow", "station": "p2", "value": "yes"}', "TYPE_ERROR"),
    ("   ", "EMPTY"),
])
def test_answer_axis(text, expected):
    assert parse_answer("json", DIAG, "ANSWERED", text)[0] == expected


def test_no_answer_is_parsed_from_a_refusal_or_a_failed_call():
    assert parse_answer("json", DIAG, "CONTENT_REFUSAL", "{}")[0] == "NO_ANSWER"
    assert parse_answer("json", DIAG, "PROVIDER_ERROR", None)[0] == "NO_ANSWER"


def _reference(name: str) -> dict:
    return json.loads((STUDY / "reference" / name).read_text())


def test_deviation_scorer_replays_the_recorded_program_run():
    s = scorer_for("orders.deviation-diagnosis", "1")
    ref = _reference("orders-deviation.json")
    good = s.score({"constant": "slow", "station": "p2", "value": True}, ref, repo_root=ROOT, truncated=False)
    assert good.behavior == "CORRECT" and good.program_correspondence == "CORRESPONDS"
    wrong = s.score({"constant": "slow", "station": "p1", "value": True}, ref, repo_root=ROOT, truncated=False)
    assert wrong.behavior == "INCORRECT" and wrong.program_correspondence == "DEVIATES"
    bogus = s.score({"constant": "speed", "station": "p2", "value": True}, ref, repo_root=ROOT, truncated=False)
    assert bogus.model_internal == "INCORRECT" and bogus.program_correspondence == "NOT_EVALUATED"
    assert set(good.dependencies) == {"belief_model", "observation"}


@pytest.mark.parametrize("plan,label", [
    (["toggle", "toggle", "toggle"], "CORRECT"),
    (["toggle", "reset", "toggle", "toggle", "toggle"], "PARTIAL"),
    (["toggle", "toggle"], "INCORRECT"),
    (["reset"], "INCORRECT"),
    (["teleport"], "INCORRECT"),
])
def test_shortest_plan_scorer_uses_the_reference_interpreter(plan, label):
    s = scorer_for("synthetic.shortest-plan", "1")
    out = s.score({"reachable": True, "plan": plan}, _reference("lamp.json"), repo_root=ROOT, truncated=False)
    assert out.behavior == label and out.program_correspondence == "NOT_APPLICABLE"


def test_claiming_unreachable_is_wrong_when_a_plan_exists():
    s = scorer_for("synthetic.shortest-plan", "1")
    out = s.score({"reachable": False, "plan": []}, _reference("shortcut.json"), repo_root=ROOT, truncated=False)
    assert out.behavior == "INCORRECT"


def test_output_cap_is_enforced_and_recorded():
    base = dict(provider_config_id="x", provider="openai", api="openai.chat.completions", api_version="v1",
                route="COMPATIBLE_RELAY", base_url_setting="FAL_X", model="m")
    assert cap_params(ProviderConfig(**base, params={"max_completion_tokens": 9000}), 6000) == \
        {"max_completion_tokens": 6000}
    assert cap_params(ProviderConfig(**base, params={"max_tokens": 100}), 6000) == {"max_tokens": 100}
    anth = ProviderConfig(**{**base, "provider": "anthropic", "api": "anthropic.messages"}, params={})
    assert cap_params(anth, 512) == {"max_tokens": 512}


def test_scoring_key_moves_with_the_response_the_reference_and_the_scorer():
    t = StudyTask.model_validate(json.loads((STUDY / "study.json").read_text())["tasks"][0])
    k = scoring_key("a" * 64, t, "b" * 64, ("r", "1"))
    assert k != scoring_key("c" * 64, t, "b" * 64, ("r", "1"))
    assert k != scoring_key("a" * 64, t, "d" * 64, ("r", "1"))
    assert k != scoring_key("a" * 64, t.model_copy(update={"scorer_version": "2"}), "b" * 64, ("r", "1"))
    assert {"orders.deviation-diagnosis@1", "synthetic.shortest-plan@1"} <= set(registered())
