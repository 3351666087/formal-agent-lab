"""formal-lab-contracts/v1 capability vocabulary (frozen copy)."""

from __future__ import annotations

from pydantic import Field

from .common import ContractModel

# Semantic profiles
PROFILE_DETERMINISTIC_FINITE_V1 = "profile.deterministic_finite_v1"

# Verifier queries
QUERY_GOAL_REACHABILITY = "query.goal_reachability"
QUERY_INVARIANT_VIOLATION = "query.invariant_violation"
QUERY_ACTION_PRECONDITION = "query.action_precondition"
QUERY_PARTIAL_STATE = "query.partial_state"  # precondition checks over observations with unknowns

# Planner / environment features
PLAN_BOUNDED_SEARCH = "plan.bounded_search"
PLAN_LLM = "plan.llm"
PLAN_RULE = "plan.rule"
ENV_SNAPSHOT_RESTORE = "env.snapshot_restore"
ENV_OBSERVATION_DELAY = "env.observation_delay"
ENV_TRUTH_OVERRIDES = "env.truth_overrides"
ENV_SEEDED_VARIATION = "env.seeded_variation"
EVAL_DETERMINISTIC = "eval.deterministic"
EVAL_APPLIES_TO = "eval.applies_to"  # params: {"package_ids": [...]} or {"all": true}

# Semantic features that are outside deterministic_finite_v1 (engines must answer UNSUPPORTED)
FEATURE_PROBABILISTIC_EFFECTS = "probabilistic_effects"
FEATURE_CONCURRENT_ACTIONS = "concurrent_actions"
FEATURE_DENSE_TIME = "dense_time"
FEATURE_UNBOUNDED_INTEGERS = "unbounded_integers"
FEATURE_PARTIAL_OBSERVATION_IN_MODEL = "partial_observation_in_model"

UNSUPPORTED_FEATURES_V1 = (
    FEATURE_PROBABILISTIC_EFFECTS,
    FEATURE_CONCURRENT_ACTIONS,
    FEATURE_DENSE_TIME,
    FEATURE_UNBOUNDED_INTEGERS,
    FEATURE_PARTIAL_OBSERVATION_IN_MODEL,
)


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
