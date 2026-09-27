"""formal-lab-contracts/v2 — run-kernel vocabulary shared by the core objects.

Turns (who acts when), termination, cost objectives, belief assumptions, execution stages, operation states and
the typed results of the new query kinds. These types depend only on `common` and `ir`, so every other contract
module can use them.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from .common import ContractModel, Digest, Identifier, Name, StateScalar
from .ir import CostTerm

# =========================================================================== turns


class TurnMode(StrEnum):
    ROUND_ROBIN = "ROUND_ROBIN"  # participants in declaration order, one action per logical step
    FIXED_TABLE = "FIXED_TABLE"  # the scenario's `table` of actor ids, repeated


class ObservationTiming(StrEnum):
    TURN_START = "TURN_START"  # the acting participant observes the world right before its own turn
    ROUND_START = "ROUND_START"  # every participant observes once at the start of the round (may act on stale state)


class ConflictPolicy(StrEnum):
    REVALIDATE = "REVALIDATE"  # a proposal based on an older world revision applies if its precondition still holds
    REJECT_STALE = "REJECT_STALE"  # … is rejected when a location it depends on changed since that revision


class TurnPolicy(ContractModel):
    """Explicit interleaving semantics: exactly one participant acts per logical (global) step."""

    mode: TurnMode = TurnMode.ROUND_ROBIN
    table: list[Identifier] = Field(default_factory=list, description="FIXED_TABLE: actor ids in turn order")
    observation_timing: ObservationTiming = ObservationTiming.TURN_START
    conflict_policy: ConflictPolicy = ConflictPolicy.REVALIDATE

    @model_validator(mode="after")
    def _table(self) -> TurnPolicy:
        if self.mode is TurnMode.FIXED_TABLE and not self.table:
            raise ValueError("FIXED_TABLE needs a non-empty `table`")
        if self.mode is TurnMode.ROUND_ROBIN and self.table:
            raise ValueError("`table` is only used with FIXED_TABLE")
        return self


class TurnRef(ContractModel):
    """Position of one action in the interleaving: global step g, round r, and the actor's own step count."""

    global_step: int = Field(ge=0)
    round: int = Field(ge=0)
    actor_id: Identifier
    actor_step: int = Field(ge=0)


# =========================================================================== termination


class NoActionPolicy(StrEnum):
    FAIL = "FAIL"  # the run fails (v1 NO_APPLICABLE_ACTION stop condition)
    SKIP_ACTOR = "SKIP_ACTOR"  # the actor passes its turn (recorded), others continue
    END = "END"  # the run ends with reason NO_APPLICABLE_ACTION (status SUCCEEDED only if a goal holds)


class ActorGoalMode(StrEnum):
    IGNORE = "IGNORE"  # per-actor goals are reported but do not end the run
    ALL = "ALL"  # the run succeeds when every participant with a goal has reached it
    ANY = "ANY"  # the run succeeds when the first participant reaches its goal


class TerminationReason(StrEnum):
    JOINT_GOAL_REACHED = "JOINT_GOAL_REACHED"
    ACTOR_GOAL_REACHED = "ACTOR_GOAL_REACHED"
    ALL_ACTOR_GOALS_REACHED = "ALL_ACTOR_GOALS_REACHED"
    INVARIANT_VIOLATED = "INVARIANT_VIOLATED"
    NO_APPLICABLE_ACTION = "NO_APPLICABLE_ACTION"
    NO_PROGRESS = "NO_PROGRESS"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    ACTOR_BUDGETS_EXHAUSTED = "ACTOR_BUDGETS_EXHAUSTED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    OPERATION_UNRESOLVED = "OPERATION_UNRESOLVED"


class TerminationPolicy(ContractModel):
    """When a run ends. Budget exhaustion always ends it; the rest is configured here (v1 stop conditions map to
    `joint_goal`, `invariants` and `on_no_action=FAIL`)."""

    joint_goal: Name | None = Field(default=None, description="property whose truth ends the run successfully")
    actor_goals: ActorGoalMode = ActorGoalMode.IGNORE
    invariants: list[Name] = Field(default_factory=list, description="a violation ends the run as FAILED")
    on_no_action: NoActionPolicy = NoActionPolicy.FAIL
    no_progress_limit: int | None = Field(
        default=None, ge=1,
        description="end with NO_PROGRESS after this many consecutive turns without a state change")


class ActionScope(ContractModel):
    """Which ground actions a participant may choose (candidates outside the scope are not offered to it)."""

    action_types: list[Name] = Field(default_factory=list, description="empty = every action type")
    params: dict[Name, list[StateScalar]] = Field(default_factory=dict,
                                                 description="parameter → allowed values (unlisted = any)")


# =========================================================================== objectives


class ObjectiveLevel(ContractModel):
    """One lexicographic level: minimise (or maximise) the sum of its terms over the path."""

    id: Name
    label: str | None = None
    unit: str = "cost"
    direction: Literal["minimize", "maximize"] = "minimize"
    terms: list[CostTerm] = Field(default_factory=list)
    model_objective: Name | None = Field(default=None, description="use the terms of ModelIR.objectives[id]")

    @model_validator(mode="after")
    def _source(self) -> ObjectiveLevel:
        if bool(self.terms) == bool(self.model_objective):
            raise ValueError("give either inline `terms` or a `model_objective` reference")
        return self


class ObjectiveSpec(ContractModel):
    """What a cost-aware planner optimises (P2-020).

    A candidate plan is a path s_0 → … → s_k (k ≤ horizon) that ends in the first state where `goal_property`
    holds. Its value on each level is the sum of the level's terms over that path (see `CostTerm`); levels are
    compared lexicographically in list order. Costs stop accumulating once the goal holds.
    """

    objective_id: Name
    levels: list[ObjectiveLevel] = Field(min_length=1)
    goal_property: Name
    horizon: int = Field(ge=1, le=200)
    accumulation: Literal["until_goal"] = "until_goal"
    description: str | None = None


class OptimizationStatus(StrEnum):
    OPTIMAL = "OPTIMAL"  # best value proven for every level within the horizon
    FEASIBLE = "FEASIBLE"  # a plan was found; optimality not proven (timeout) — see `bounds`
    NO_PLAN_WITHIN_HORIZON = "NO_PLAN_WITHIN_HORIZON"
    UNKNOWN = "UNKNOWN"
    UNSUPPORTED = "UNSUPPORTED"


class ObjectiveBound(ContractModel):
    level: Name
    value: int | None = Field(description="objective value of the returned plan")
    proven_lower: int | None = Field(default=None, description="no plan within the horizon is cheaper than this")
    proven_upper: int | None = Field(default=None, description="a plan at most this expensive exists")
    optimal: bool = False


class OptimizationResult(ContractModel):
    objective_id: Name
    status: OptimizationStatus
    horizon: int
    plan_length: int | None = None
    levels: list[ObjectiveBound] = Field(default_factory=list)
    solver_calls: int = 0
    method: str = Field(default="incremental bound tightening (binary search per lexicographic level)")
    scope: Literal["MODEL_INTERNAL_WITHIN_HORIZON"] = "MODEL_INTERNAL_WITHIN_HORIZON"


# =========================================================================== assumptions / observation requests


class Provenance(StrEnum):
    KNOWN = "KNOWN"  # observed fresh at this step
    STALE = "STALE"  # last known value, observed at an earlier step
    UNKNOWN = "UNKNOWN"  # no value observed; completions range over the declared domain
    ASSUMED_INITIAL = "ASSUMED_INITIAL"  # never observed: the model's initial value is assumed


class AssumptionItem(ContractModel):
    path: str
    provenance: Provenance
    value: StateScalar | None = Field(description="value the plan assumed (null for free UNKNOWN locations)")
    as_of_step: int | None = Field(default=None, ge=0)
    reason: str | None = None


class AssumptionSet(ContractModel):
    """Everything a belief-based conclusion assumed beyond fresh observations (P2-025)."""

    items: list[AssumptionItem] = Field(default_factory=list)
    digest: Digest
    counts: dict[str, int] = Field(default_factory=dict, description="provenance → number of locations")

    @property
    def empty(self) -> bool:
        return not self.items


class PlanBasis(StrEnum):
    FULLY_OBSERVED = "FULLY_OBSERVED"  # every location the plan relied on was observed fresh
    ASSUMPTION_BASED = "ASSUMPTION_BASED"  # used last-known / initial values (see the assumption set)
    ROBUST = "ROBUST"  # checked to hold for every allowed completion of the unknowns


class ObservationRequest(ContractModel):
    """Extra observations that would settle an UNKNOWN verdict (P2-027)."""

    paths: list[str] = Field(min_length=1)
    reason: str
    for_action: str | None = Field(default=None, description="ground action key the request is about")
    applicable_completion: dict[str, StateScalar] | None = None
    inapplicable_completion: dict[str, StateScalar] | None = None


class RobustnessVerdict(StrEnum):
    ROBUST = "ROBUST"  # every completion of the unknowns lets the whole sequence apply (and reach the goal)
    NOT_ROBUST = "NOT_ROBUST"  # a counterexample completion exists
    UNKNOWN = "UNKNOWN"
    UNSUPPORTED = "UNSUPPORTED"


class RobustnessResult(ContractModel):
    """Open-loop robustness of a fixed action sequence over all completions (P2-026). This is not policy
    synthesis: the sequence cannot branch on later observations."""

    verdict: RobustnessVerdict
    sequence: list[str] = Field(description="ground action keys, in order")
    require_goal: Name | None = None
    counterexample: dict[str, StateScalar] | None = Field(default=None,
                                                          description="completion of the unknowns that breaks it")
    failing_index: int | None = Field(default=None, description="first action that is inapplicable (0-based)")
    goal_fails: bool = False
    unknown_paths: list[str] = Field(default_factory=list)


# =========================================================================== execution stages / operations


class ExecutionStage(StrEnum):
    TURN = "TURN"  # choose the acting participant (TurnScheduler)
    OBSERVE = "OBSERVE"  # observation → belief with provenance
    PROPOSE = "PROPOSE"  # candidates + strategy proposal (may call a model)
    CHECK = "CHECK"  # precondition / rules on the belief
    EXECUTE = "EXECUTE"  # dispatch the operation to the environment
    RECONCILE = "RECONCILE"  # settle an operation whose outcome is unknown
    PROBE = "PROBE"  # independent business observations
    COMPARE = "COMPARE"  # predicted vs observed effects
    TERMINATE = "TERMINATE"  # termination policy


class StageStatus(StrEnum):
    OK = "OK"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class OperationState(StrEnum):
    PREPARED = "PREPARED"  # intent recorded before anything is sent
    DISPATCHED = "DISPATCHED"  # sent to the environment; no answer yet
    COMPLETED = "COMPLETED"  # answer received (applied or rejected)
    FAILED = "FAILED"  # definitely not applied (error before or at the environment)
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"  # sent, answer lost: it may or may not have taken effect
    RECONCILED = "RECONCILED"  # an unknown outcome settled by querying the environment


OPERATION_TRANSITIONS: dict[OperationState, frozenset[OperationState]] = {
    OperationState.PREPARED: frozenset({OperationState.DISPATCHED, OperationState.FAILED}),
    OperationState.DISPATCHED: frozenset({OperationState.COMPLETED, OperationState.FAILED,
                                          OperationState.OUTCOME_UNKNOWN}),
    OperationState.OUTCOME_UNKNOWN: frozenset({OperationState.RECONCILED, OperationState.DISPATCHED,
                                               OperationState.FAILED}),
    OperationState.COMPLETED: frozenset(),
    OperationState.FAILED: frozenset(),
    OperationState.RECONCILED: frozenset(),
}


# =========================================================================== references


class ReleaseRef(ContractModel):
    release_id: Identifier
    digest: Digest


class RuleSetRef(ContractModel):
    ruleset_id: Identifier
    version: int = Field(ge=1)
    digest: Digest


class PlanRef(ContractModel):
    plan_id: Identifier
    version: int = Field(ge=1)
    node_id: str | None = None


class AssumptionSetRef(ContractModel):
    digest: Digest
    count: int = Field(ge=0)
    basis: PlanBasis = PlanBasis.FULLY_OBSERVED
    counts: dict[str, int] = Field(default_factory=dict)


class RuleOutcome(StrEnum):
    CONTINUE = "CONTINUE"
    OBSERVE_MORE = "OBSERVE_MORE"
    REPLAN = "REPLAN"
    PAUSE = "PAUSE"



# =========================================================================== capability negotiation


class CapabilityRequirement(ContractModel):
    id: str
    min_version: str = "1"
    optional: bool = False


class CapabilityNegotiation(ContractModel):
    plugin_id: str
    plugin_version: str
    compatible: bool
    granted: list[str] = Field(default_factory=list)
    missing_required: list[str] = Field(default_factory=list)
    missing_optional: list[str] = Field(default_factory=list)
    role: str | None = Field(default=None, description="role of the plugin in the run (v2)")
    verdict: Literal["SUPPORTED", "PARTIAL", "UNSUPPORTED"] | None = Field(
        default=None, description="SUPPORTED: all granted; PARTIAL: optional ones missing; UNSUPPORTED (v2)")
    reasons: list[str] = Field(default_factory=list, description="human-readable explanation (v2)")
