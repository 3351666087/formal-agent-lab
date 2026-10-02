"""One projection rule for everything that reaches a participant (phase 4A, A2): payload keys, path items, path
lists, free text; last_outcome (result, conflict, error); settings that are credentials."""

from __future__ import annotations

from formal_lab_contracts import ActionOutcome, Participant, ParticipantView
from formal_lab_runtime.participants import (
    WITHHELD,
    ParticipantInput,
    ParticipantServices,
    Projection,
    secret_setting,
)

VIEW = ParticipantView(include=[], exclude=["stock"])
FAMILIES = {"stock", "status", "clock"}


def test_payload_projection_removes_every_form_of_a_withheld_location():
    p = Projection(VIEW, FAMILIES)
    payload = {"stock[a]": 4, "status[o1]": "reserved",
               "facts": [{"path": "stock[a]", "value": 4}, {"path": "clock", "value": 1}],
               "written_paths": ["stock[a]", "status[o1]"],
               "reason": "PRECONDITION_FALSE: stock[a] = 1 is below 2; status[o1] is submitted",
               "nested": {"diffs": [{"path": "stock[b]", "expected": 3}], "note": "stock unchanged"}}
    out = p.value(payload)
    assert "stock[a]" not in out and out["status[o1]"] == "reserved"
    assert out["facts"] == [{"path": "clock", "value": 1}] and out["written_paths"] == ["status[o1]"]
    assert out["reason"] == f"PRECONDITION_FALSE: {WITHHELD} is below 2; status[o1] is submitted"
    assert out["nested"]["diffs"] == [] and out["nested"]["note"] == f"{WITHHELD} unchanged"
    assert "stock[" not in str(out)
    assert payload["stock[a]"] == 4  # the operator's payload is untouched


def test_without_a_view_the_payload_is_unchanged():
    payload = {"stock[a]": 4, "reason": "stock[a] = 1"}
    assert Projection(None, FAMILIES).value(payload) is payload


def test_last_outcome_result_conflict_and_error_are_projected():
    inp = ParticipantInput(Participant.model_validate(
        {"actor_id": "p", "strategy": {"plugin": {"plugin_id": "x", "version": "1.0.0"}, "config": {}},
         "view": VIEW.model_dump()}), FAMILIES)
    outcome = ActionOutcome.model_validate({
        "operation_id": "o", "run_id": "r", "step_id": "s", "action": {"action_type": "reserve", "params": {"o": "o3"}},
        "status": "REJECTED", "effect_applied": False, "revision_before": 3, "revision_after": 3,
        "result": {"reason": "STALE_REVISION: stock[a] changed", "written": {"stock[a]": 1, "status[o3]": "x"}},
        "conflict": {"policy": "REVALIDATE", "based_on_revision": 1, "current_revision": 3,
                     "changed_paths": ["stock[a]", "status[o1]"], "reason": "stock[a] was written by other"},
        "error": {"code": "CONFLICT", "message": "stock[a] = 1 below qty", "retryable": False}})
    seen = inp.outcome(outcome.model_dump(mode="json"))
    text = seen.model_dump_json()
    assert "stock[" not in text
    assert seen.conflict.changed_paths == ["status[o1]"] and seen.result["written"] == {"status[o3]": "x"}


def test_credentials_are_never_settings_of_a_participant():
    class Base:
        def get_setting(self, key):
            return {"ORDERS_WRITE_TOKEN_FILE": "/secret/path", "FAL_LLM_MODEL": "m"}.get(key)

    part = Participant.model_validate(
        {"actor_id": "p", "strategy": {"plugin": {"plugin_id": "x", "version": "1.0.0"}, "config": {}}})
    services = ParticipantServices(Base(), part)
    for key in ("ORDERS_WRITE_TOKEN_FILE", "orders_write_token", "BROKER_SIGNING_KEY", "FAL_PARTICIPANT_TOKEN_KEY",
                "DB_PASSWORD", "X_KEYSTORE_PATH"):
        assert secret_setting(key) and services.get_setting(key) is None
    assert services.get_setting("FAL_LLM_MODEL") == "m"
    assert services.refused_settings[0] == "ORDERS_WRITE_TOKEN_FILE"
