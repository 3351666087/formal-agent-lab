"""Per-participant planner input (phase 3A, G4).

A participant's `ParticipantView` decides what its planner receives; everything a planner gets passes through one
`ParticipantInput`:

- the observation (turn start, round start, answers to observation requests): facts and unknown items of withheld
  locations are removed, so the participant's belief treats them as never observed (ASSUMED_INITIAL);
- observation requests: withheld locations are not served (the refusal is on the record);
- `last_outcome`: field differences on withheld locations are dropped from the effect comparison it carries;
- settings: `ParticipantServices.get_setting` reads the participant's own settings before the platform's.

The kernel keeps working on the full observation (precondition checks, predictions, effect comparison) — the view
restricts the planner, not the platform. Planner checkpoints only ever contain what the planner saw, so a restored
planner continues on the same input. Without a view nothing is filtered and the input is the phase-2 one.
"""

from __future__ import annotations

from typing import Any

from formal_lab_contracts import (
    ActionOutcome,
    ModelPackage,
    Observation,
    Participant,
    ParticipantView,
    digest_of,
)


def _family(path: str) -> str:
    return path.split("[", 1)[0]


def _hit(path: str, patterns: list[str]) -> bool:
    return any(path == p or _family(path) == p for p in patterns)


class ParticipantInput:
    """Filters what one participant's planner receives (see module docstring)."""

    def __init__(self, participant: Participant):
        self.participant = participant
        self.view: ParticipantView | None = participant.view

    @property
    def filtered(self) -> bool:
        return self.view is not None and bool(self.view.include or self.view.exclude)

    def allows(self, path: str) -> bool:
        if not self.filtered:
            return True
        assert self.view is not None
        if self.view.include and not _hit(path, self.view.include):
            return False
        return not _hit(path, self.view.exclude)

    def observation(self, obs: Observation) -> tuple[Observation, list[str]]:
        """The planner's observation and the withheld locations (sorted)."""
        if not self.filtered:
            return obs, []
        withheld = sorted({f.path for f in obs.facts if not self.allows(f.path)}
                          | {u.path for u in obs.unknowns if not self.allows(u.path)})
        if not withheld:
            return obs, []
        return obs.model_copy(update={
            "facts": [f for f in obs.facts if self.allows(f.path)],
            "unknowns": [u for u in obs.unknowns if self.allows(u.path)],
            "requested_paths": [p for p in obs.requested_paths if self.allows(p)],
        }), withheld

    def request(self, paths: list[str]) -> tuple[list[str], list[str]]:
        """(served, declined) locations of an observation request."""
        return [p for p in paths if self.allows(p)], [p for p in paths if not self.allows(p)]

    def outcome(self, data: dict[str, Any] | None) -> ActionOutcome | None:
        if data is None:
            return None
        outcome = ActionOutcome.model_validate(data)
        if not self.filtered or outcome.effect_comparison is None:
            return outcome
        cmp = outcome.effect_comparison
        kept = [d for d in cmp.diffs if self.allows(d.path)]
        if len(kept) == len(cmp.diffs):
            return outcome
        counts: dict[str, int] = {}
        for d in kept:
            counts[d.evidence] = counts.get(d.evidence, 0) + 1
        return outcome.model_copy(update={"effect_comparison": cmp.model_copy(update={
            "diffs": kept, "evidence_counts": counts})})

    def digest(self, obs: Observation) -> str:
        """Digest of what the planner receives (turn, request and evidence metadata excluded): equal inputs → equal
        digests, before and after a recovery."""
        return digest_of({"actor_id": obs.actor_id, "revision": obs.state_revision,
                          "facts": sorted(((f.path, f.value, f.observed_at_step) for f in obs.facts),
                                          key=lambda x: x[0]),
                          "unknowns": sorted((u.path, u.reason) for u in obs.unknowns)}).value


class ParticipantServices:
    """PluginServices for one participant's planner: the run's services, with the participant's own settings read
    first. `participant()` tells the planner who it plans for."""

    def __init__(self, base: Any, participant: Participant):
        self._base = base
        self._participant = participant

    def pinned_model(self) -> ModelPackage:
        return self._base.pinned_model()

    def get_model(self, ref) -> ModelPackage:
        return self._base.get_model(ref)

    def loaded_model(self) -> Any:
        return self._base.loaded_model()

    def get_setting(self, key: str) -> str | None:
        own = self._participant.view.settings if self._participant.view else {}
        return own[key] if key in own else self._base.get_setting(key)

    def participant(self) -> Participant:
        return self._participant

    @property
    def actor_id(self) -> str:
        return self._participant.actor_id
