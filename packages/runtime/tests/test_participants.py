"""Per-participant planner input (phase 3A, G4): view filter, requests, last outcome, settings."""

from __future__ import annotations

from formal_lab_contracts import (
    ActionOutcome,
    EffectComparison,
    FieldDiff,
    Observation,
    Participant,
    UnknownItem,
)
from formal_lab_model.belief import belief_state_from
from formal_lab_runtime.participants import ParticipantInput, ParticipantServices

INITIAL = {"clock": 0, "dock[a]": 5, "stock[z1]": 0, "serves[s1]": "none"}


def participant(view=None) -> Participant:
    return Participant.model_validate({"actor_id": "p", "strategy": {"plugin": {"plugin_id": "x.y", "version": "1.0.0"},
                                                                     "config": {}}, "view": view})


def observation() -> Observation:
    return Observation.model_validate({
        "run_id": "r", "actor_id": "p", "step": 3, "state_revision": 3,
        "facts": [{"path": "clock", "value": 3, "observed_at_step": 3},
                  {"path": "dock[a]", "value": 1, "observed_at_step": 3},
                  {"path": "serves[s1]", "value": "z1", "observed_at_step": 3}],
        "unknowns": [UnknownItem(path="stock[z1]", reason="OBSERVATION_DELAY",
                                 last_known={"path": "stock[z1]", "value": 2, "observed_at_step": 1}).model_dump()]})


def test_without_a_view_nothing_changes():
    inp = ParticipantInput(participant())
    obs = observation()
    assert inp.observation(obs) == (obs, []) and inp.request(["dock[a]"]) == (["dock[a]"], [])


def test_withheld_locations_are_never_observed_for_the_planner():
    inp = ParticipantInput(participant({"include": ["clock", "stock"], "exclude": []}))
    pobs, withheld = inp.observation(observation())
    assert withheld == ["dock[a]", "serves[s1]"]
    belief = belief_state_from(pobs, INITIAL)
    assert belief.state["dock[a]"] == 5 and belief.provenance["dock[a]"].value == "ASSUMED_INITIAL"
    assert belief.state["stock[z1]"] == 2 and belief.provenance["stock[z1]"].value == "STALE"  # kept (in the view)
    assert inp.request(["dock[a]", "stock[z1]"]) == (["stock[z1]"], ["dock[a]"])
    excl = ParticipantInput(participant({"exclude": ["serves"]}))
    assert excl.observation(observation())[1] == ["serves[s1]"]
    assert inp.digest(pobs) == ParticipantInput(participant({"include": ["clock", "stock"]})).digest(pobs)


def test_last_outcome_loses_differences_on_withheld_locations():
    inp = ParticipantInput(participant({"exclude": ["dock"]}))
    diffs = [FieldDiff(path="dock[a]", expected=1, observed=0, status="DIFFERENT", evidence="observed"),
             FieldDiff(path="clock", expected=4, observed=4, status="MATCH", evidence="observed")]
    outcome = ActionOutcome(operation_id="o", run_id="r", step_id="s", action={"action_type": "tick"},
                            status="APPLIED", effect_applied=True, revision_before=3, revision_after=4,
                            effect_comparison=EffectComparison(verdict="DIFFERENT", expected_by="m", diffs=diffs,
                                                               evidence_counts={"observed": 2}))
    seen = inp.outcome(outcome.model_dump(mode="json"))
    assert [d.path for d in seen.effect_comparison.diffs] == ["clock"]
    assert seen.effect_comparison.evidence_counts == {"observed": 1}
    assert inp.outcome(None) is None


def test_participant_settings_come_first():
    class Base:
        def get_setting(self, key):
            return {"style": "platform", "region": "eu"}.get(key)

    services = ParticipantServices(Base(), participant({"settings": {"style": "careful"}}))
    assert services.get_setting("style") == "careful" and services.get_setting("region") == "eu"
    assert services.actor_id == "p" and services.participant().view.settings == {"style": "careful"}
