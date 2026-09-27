"""Turn an Observation into the actor's belief state (what a model-based strategy can plan with)."""

from __future__ import annotations

from dataclasses import dataclass

from formal_lab_contracts import (
    AssumptionItem,
    AssumptionSet,
    AssumptionSetRef,
    BeliefState,
    Observation,
    PlanBasis,
    Provenance,
    StateScalar,
    digest_of,
)

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


def belief_state(observation: Observation, model: CheckedModel) -> BeliefState:
    """v2 belief with explicit provenance per location (P2-025).

    KNOWN: observed fresh at this step. STALE: a last-known value (older fact, or the last-known value of an
    unknown item). UNKNOWN: reported unknown without any value — the model's initial value is used as a
    placeholder and the location is free in every completion-based check. ASSUMED_INITIAL: never mentioned by the
    observation — the model's initial value is assumed. Completion-based checks treat exactly the observation's
    unknown items as free (the phase-1 semantics); everything that is not KNOWN is listed in the assumption set.
    """
    old = belief_from_observation(observation, model)
    fresh = {f.path for f in observation.facts if f.observed_at_step >= observation.step and f.path in old.state}
    provenance: dict[str, Provenance] = {}
    as_of: dict[str, int] = {}
    facts = {f.path: f for f in observation.facts}
    unknown_items = {u.path: u for u in observation.unknowns}
    for path in old.state:
        if path in fresh:
            provenance[path] = Provenance.KNOWN
        elif path in unknown_items and unknown_items[path].last_known is None:
            provenance[path] = Provenance.UNKNOWN
        elif path in old.stale_paths:
            provenance[path] = Provenance.STALE
            known = facts.get(path) or (unknown_items[path].last_known if path in unknown_items else None)
            if known is not None:
                as_of[path] = known.observed_at_step
        else:
            provenance[path] = Provenance.ASSUMED_INITIAL
    items = [AssumptionItem(path=p, provenance=v, value=None if v is Provenance.UNKNOWN else old.state[p],
                            as_of_step=as_of.get(p),
                            reason=(unknown_items[p].reason if p in unknown_items else
                                    "never observed: model initial value" if v is Provenance.ASSUMED_INITIAL else
                                    "older observation"))
             for p, v in sorted(provenance.items()) if v is not Provenance.KNOWN]
    counts: dict[str, int] = {}
    for v in provenance.values():
        counts[v.value] = counts.get(v.value, 0) + 1
    digest = digest_of([[i.path, i.provenance.value, i.value, i.as_of_step] for i in items])
    return BeliefState(actor_id=observation.actor_id, step=observation.step, world_revision=observation.state_revision,
                       state=old.state, provenance=provenance, as_of_step=as_of, free_paths=old.unknown_paths,
                       assumptions=AssumptionSet(items=items, digest=digest, counts=counts))


def free_paths(belief: BeliefState, observation: Observation) -> list[str]:
    """Locations that completion-based checks range over: the observation's unknown items (phase-1 semantics)."""
    return sorted({u.path for u in observation.unknowns if u.path in belief.state})


def plan_basis(belief: BeliefState) -> PlanBasis:
    return PlanBasis.FULLY_OBSERVED if all(v is Provenance.KNOWN for v in belief.provenance.values()) \
        else PlanBasis.ASSUMPTION_BASED


def assumption_ref(belief: BeliefState, basis: PlanBasis | None = None) -> AssumptionSetRef:
    a = belief.assumptions
    return AssumptionSetRef(digest=a.digest, count=len(a.items), basis=basis or plan_basis(belief),
                            counts={k: v for k, v in a.counts.items() if k != "KNOWN"})
