"""Capability identifiers, the capability matrix vocabulary and negotiation."""

from __future__ import annotations

from .kernel import CapabilityNegotiation, CapabilityRequirement
from .objects import PluginDescriptor

# Semantic profiles
PROFILE_DETERMINISTIC_FINITE_V1 = "profile.deterministic_finite_v1"

# Model frontends: the source formats a MODEL_FRONTEND compiles, params {"formats": [...]} (phase 4B, B3)
FRONTEND_SOURCE_FORMAT = "frontend.source_format"

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

# v2 — semantic profiles and drivers
PROFILE_PREFIX = "profile."
DRIVER_CANDIDATES = "driver.candidates"  # ground actions + applicability on a belief (incl. unknowns)
DRIVER_PREDICT = "driver.predict"  # predicted post-state / written locations of an action
DRIVER_PROPERTIES = "driver.properties"  # goal / invariant truth values on a state
DRIVER_BELIEF = "driver.belief"  # observation → belief with provenance
DRIVER_DISPLAY = "driver.display"  # structure for the UI (graph, labels)
DRIVER_IR = "driver.ir"  # exposes the neutral IR (Z3 queries, rules and cost objectives apply)

# v2 — environment capabilities negotiated at run start (P2-050)
ENV_PURE_REPLAYABLE = "env.pure_replayable"  # restore(snapshot) + re-apply is safe (pure-data simulator)
ENV_PERSISTENT_SESSION = "env.persistent_session"  # state lives in an external service; never rolled back
ENV_SNAPSHOT = "env.snapshot"  # can describe its state at a step (FULL_STATE or SESSION_MARKER)
ENV_RESTORE = "env.restore"  # can restore a FULL_STATE snapshot
ENV_QUERY_OPERATION = "env.query_operation"  # can answer "what happened to operation <id>?"
ENV_IDEMPOTENT_STEP = "env.idempotent_step"  # the same operation id never takes effect twice
ENV_OBSERVE_ON_REQUEST = "env.observe_on_request"  # fresh values for requested locations (OBSERVE_MORE)
ENV_MULTI_ACTOR = "env.multi_actor"  # per-actor observations, revision-based conflict arbitration
ENV_RESET = "env.reset_session"  # environment-side reset to a seeded state
ENV_STATE_IMPORT = "env.state_import"  # load an exported state

# v2 — verifier / planner features
QUERY_OPTIMIZE_OBJECTIVE = "query.optimize_objective"
QUERY_ROBUST_SEQUENCE = "query.robust_sequence"
PLAN_COST_OPTIMAL = "plan.cost_optimal"
PLAN_TASK_PLAN = "plan.task_plan"  # keeps a TaskPlan with checkpoint/restore
PLAN_CHECKPOINT = "plan.checkpoint"
PLAN_OBSERVATION_REQUESTS = "plan.observation_requests"
PROBE_METRICS = "probe.metrics"

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


def _version_tuple(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in v.split(".") if p.isdigit())


def negotiate(descriptor: PluginDescriptor, requirements: list[CapabilityRequirement], *,
              role: str | None = None, why: dict[str, str] | None = None) -> CapabilityNegotiation:
    """Match required capabilities against a descriptor. `why` maps a capability id to the reason it is needed,
    so the result explains itself before a run starts (P2-015)."""
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
    why = why or {}
    reasons = [f"{descriptor.plugin_id} lacks {c}" + (f" (needed for {why[c]})" if c in why else "")
               for c in missing_required]
    reasons += [f"optional {c} not offered" + (f" ({why[c]} unavailable)" if c in why else "")
                for c in missing_optional]
    verdict = "UNSUPPORTED" if missing_required else ("PARTIAL" if missing_optional else "SUPPORTED")
    return CapabilityNegotiation(
        plugin_id=descriptor.plugin_id,
        plugin_version=descriptor.version,
        compatible=not missing_required,
        granted=granted,
        missing_required=missing_required,
        missing_optional=missing_optional,
        role=role,
        verdict=verdict,
        reasons=reasons,
    )

# phase 3A
GATE_PRE_EXECUTION = "gate.pre_execution"  # an EXECUTION_GATE plugin: ALLOW / DENY before each send
GATE_FRESH_VALUES = "gate.fresh_values"  # the gate asks for locations to be read right before the send
DRIVER_STATS = "driver.stats"  # the loaded model offers stats() (sizes for release records); optional
ENV_BATCH_STEP = "env.batch_step"  # step_batch(proposals, operation_id): one environment step for a JOINT_BATCH round
DRIVER_JOINT_PREDICT = "driver.joint_predict"  # the model gives simultaneous actions a meaning (params.semantics)
BATCH_START_STATE_DISJOINT_WRITES = "START_STATE_DISJOINT_WRITES"  # every action on the batch's start state;
# disjoint writes merge, an action writing a location an earlier member already wrote is rejected (conflict)

# phase 4A (A2) — execution basis at the side-effect boundary
ENV_CURRENT_REVISION = "env.current_revision"  # current_revision(): the authoritative state revision, read fresh
ENV_CONDITIONAL_STEP = "env.conditional_step"  # step(..., expected_revision=r): applied only if what the operation
# depends on is unchanged since r — checked atomically where the side effect happens (transaction / conditional update)
ENV_WORLD_STEP_REPORT = "env.world_step_report"  # world_step_report(): the world step just taken and the actions of the
#   environment's own automatic participants in it (phase 4A)
