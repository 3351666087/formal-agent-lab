"""Turn an Observation into the actor's belief state (what a model-based strategy can plan with)."""

from __future__ import annotations

from dataclasses import dataclass

from formal_lab_contracts import Observation, StateScalar

from .checker import CheckedModel


@dataclass
class Belief:
    state: dict[str, StateScalar]  # every state location has a value
    unknown_paths: list[str]  # locations whose current value the actor does not know
    assumed_paths: list[str]  # locations never observed: value taken from the model's initial state
    stale_paths: list[str]  # locations whose value is the last known (older than this step)


def belief_from_observation(observation: Observation, model: CheckedModel) -> Belief:
    state = model.initial_state()
    seen: set[str] = set()
    stale: list[str] = []
    for fact in observation.facts:
        if fact.path in state:
            state[fact.path] = fact.value
            seen.add(fact.path)
            if fact.observed_at_step < observation.step:
                stale.append(fact.path)
    for item in observation.unknowns:
        if item.last_known is not None and item.path in state and item.path not in seen:
            state[item.path] = item.last_known.value
            seen.add(item.path)
            stale.append(item.path)
    unknown = sorted({u.path for u in observation.unknowns if u.path in state})
    assumed = sorted(p for p in state if p not in seen)
    return Belief(state=state, unknown_paths=unknown, assumed_paths=assumed, stale_paths=sorted(set(stale)))
