"""Capability identifiers, the capability matrix vocabulary and negotiation."""

from __future__ import annotations

from pydantic import Field

from .common import ContractModel
from .objects import PluginDescriptor

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


def _version_tuple(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in v.split(".") if p.isdigit())


def negotiate(descriptor: PluginDescriptor, requirements: list[CapabilityRequirement]) -> CapabilityNegotiation:
    offered = {c.id: c.version for c in descriptor.capabilities}
    granted, missing_required, missing_optional = [], [], []
    for req in requirements:
        have = offered.get(req.id)
        if have is not None and _version_tuple(have) >= _version_tuple(req.min_version):
            granted.append(req.id)
        elif req.optional:
            missing_optional.append(req.id)
        else:
            missing_required.append(req.id)
    return CapabilityNegotiation(
        plugin_id=descriptor.plugin_id,
        plugin_version=descriptor.version,
        compatible=not missing_required,
        granted=granted,
        missing_required=missing_required,
        missing_optional=missing_optional,
    )
