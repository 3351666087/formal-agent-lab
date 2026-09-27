"""FROZEN formal-lab-contracts/v1 — do not edit (contracts/v1 must stay byte-identical).

The frozen objects of formal-lab-contracts/v1 and their supporting types."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import Field, model_validator

from .common import (
    ArtifactRef,
    ContractModel,
    ContractVersion,
    Digest,
    EvidenceRef,
    ExtensibleModel,
    Identifier,
    Name,
    PluginId,
    PluginRef,
    SemVer,
    StateScalar,
)
from .errors import ErrorInfo
from .ir import Effect, Expr, ModelIR

# =========================================================================== PluginDescriptor


class PluginInterface(StrEnum):
    MODEL_FRONTEND = "MODEL_FRONTEND"
    PLANNER = "PLANNER"
    VERIFIER = "VERIFIER"
    ENVIRONMENT = "ENVIRONMENT"
    EVALUATOR = "EVALUATOR"
    ARTIFACT_STORE = "ARTIFACT_STORE"


INTERFACE_VERSION = "1"


class Capability(ContractModel):
    id: str = Field(min_length=1, description="e.g. query.goal_reachability, profile.deterministic_finite_v1")
    version: str = "1"
    params: dict[str, Any] = Field(default_factory=dict)


class PluginUi(ContractModel):
    """Display metadata; the Web UI renders plugins exclusively from this and the schemas."""

    label: str
    description: str | None = None
    category: str | None = None
    state_labels: dict[str, str] = Field(default_factory=dict, description="state variable → label")
    action_labels: dict[str, str] = Field(default_factory=dict, description="action type → label")
    action_display: dict[str, str] = Field(
        default_factory=dict, description="action type → template, e.g. '分配 {op} → {machine}'"
    )
    metric_labels: dict[str, str] = Field(default_factory=dict)
    entity_labels: dict[str, str] = Field(default_factory=dict)
    value_labels: dict[str, str] = Field(default_factory=dict, description="enum symbol → label")


class PluginDescriptor(ExtensibleModel):
    contract_version: ContractVersion = "formal-lab-contracts/v1"
    plugin_id: PluginId
    version: SemVer
    interface: PluginInterface
    interface_version: str = INTERFACE_VERSION
    capabilities: list[Capability] = Field(default_factory=list)
    semantic_profiles: list[str] = Field(default_factory=list)
    config_schema: dict[str, Any] = Field(default_factory=lambda: {"type": "object", "properties": {}})
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    entrypoint: str = Field(description="python import path 'module:attr' of the factory")
    ui: PluginUi
    license: str | None = None
    source: str | None = Field(default=None, description="package name / URL providing the plugin")

    def ref(self) -> PluginRef:
        return PluginRef(plugin_id=self.plugin_id, version=self.version)

    def has_capability(self, capability_id: str) -> bool:
        return any(c.id == capability_id for c in self.capabilities)


# =========================================================================== ModelPackage


class ModelRef(ContractModel):
    package_id: Identifier
    version: int = Field(ge=1)
    digest: Digest


class ModelSource(ContractModel):
    format: str = Field(description="source format, e.g. fal-ir-json/v1")
    text: str | None = None
    artifact: ArtifactRef | None = None
    origin: str | None = Field(default=None, description="where the source came from (path, editor, import)")
    author: str | None = None
    parent_version: int | None = Field(default=None, ge=1, description="version this one was edited from")


class CompiledArtifact(ContractModel):
    backend: str
    backend_version: str
    digest: Digest
    artifact: ArtifactRef | None = None
    stats: dict[str, Any] = Field(default_factory=dict)


class ModelPackage(ExtensibleModel):
    contract_version: ContractVersion = "formal-lab-contracts/v1"
    package_id: Identifier
    version: int = Field(ge=1)
    frontend: PluginRef = Field(description="plugin category that produced the IR")
    semantic_profile: str
    digest: Digest = Field(description="sha256 of the canonical IR")
    ir: ModelIR
    source: ModelSource
    compiled: list[CompiledArtifact] = Field(default_factory=list)
    created_at: datetime

    def ref(self) -> ModelRef:
        return ModelRef(package_id=self.package_id, version=self.version, digest=self.digest)


# =========================================================================== ScenarioManifest


class Budget(ContractModel):
    max_steps: int | None = Field(default=None, ge=1)
    max_wall_seconds: float | None = Field(default=None, gt=0)
    max_model_calls: int | None = Field(default=None, ge=0)
    max_tokens: int | None = Field(default=None, ge=0)


class BudgetUsage(ContractModel):
    steps: int = 0
    wall_seconds: float = 0.0
    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class StrategySpec(ContractModel):
    plugin: PluginRef
    config: dict[str, Any] = Field(default_factory=dict)


class Participant(ContractModel):
    actor_id: Identifier
    role: str = "operator"
    strategy: StrategySpec


class EnvironmentSpec(ContractModel):
    plugin: PluginRef
    config: dict[str, Any] = Field(default_factory=dict)


class Objective(ContractModel):
    property_id: Name | None = None
    metric_id: str | None = None
    description: str | None = None


class StopConditionKind(StrEnum):
    GOAL_REACHED = "GOAL_REACHED"
    INVARIANT_VIOLATED = "INVARIANT_VIOLATED"
    NO_APPLICABLE_ACTION = "NO_APPLICABLE_ACTION"


class StopCondition(ContractModel):
    kind: StopConditionKind
    property_id: Name | None = None


class ScenarioManifest(ExtensibleModel):
    contract_version: ContractVersion = "formal-lab-contracts/v1"
    scenario_id: Identifier
    revision: int = Field(default=1, ge=1)
    name: str
    description: str | None = None
    model: ModelRef
    environment: EnvironmentSpec
    participants: list[Participant] = Field(min_length=1)
    objectives: list[Objective] = Field(default_factory=list)
    budget: Budget
    seed: int = 0
    stop_conditions: list[StopCondition] = Field(default_factory=list)


# =========================================================================== Observation


class Fact(ContractModel):
    path: str = Field(description="state location path, e.g. op_status[o1_cut]")
    value: StateScalar
    observed_at_step: int = Field(ge=0)
    source: Literal["DIRECT", "DELAYED"] = "DIRECT"


class UnknownItem(ContractModel):
    path: str
    reason: Literal["OBSERVATION_DELAY", "NOT_OBSERVABLE", "NOT_YET_OBSERVED"]
    last_known: Fact | None = None


class Observation(ContractModel):
    run_id: str
    actor_id: str
    step: int = Field(ge=0, description="logical step at which the observation is taken")
    state_revision: int = Field(ge=0)
    facts: list[Fact]
    unknowns: list[UnknownItem] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    semantics: str = Field(
        default="Facts are what the actor observed (possibly stale, see observed_at_step); unknowns are "
        "locations whose current value the actor cannot know at this step. The environment truth state is a "
        "separate object that agents never receive.",
    )


# =========================================================================== ActionSpec / Proposal / Outcome


class RetrySemantics(StrEnum):
    IDEMPOTENT = "IDEMPOTENT"
    RECONCILE_THEN_RETRY = "RECONCILE_THEN_RETRY"
    NOT_RETRYABLE = "NOT_RETRYABLE"


class ActionSpec(ContractModel):
    action_type: Name
    label: str | None = None
    description: str | None = None
    params_schema: dict[str, Any] = Field(description="JSON Schema of the parameter object")
    preconditions: list[str] = Field(default_factory=list, description="human-readable preconditions")
    precondition_expr: Expr | None = None
    expected_effects: list[str] = Field(default_factory=list, description="human-readable expected effects")
    effects: list[Effect] = Field(default_factory=list)
    cost: float = Field(default=1.0, ge=0)
    timeout_seconds: float = Field(default=30.0, gt=0)
    retry: RetrySemantics = RetrySemantics.RECONCILE_THEN_RETRY


class GroundAction(ContractModel):
    action_type: Name
    params: dict[str, StateScalar] = Field(default_factory=dict)


class ProposalSourceKind(StrEnum):
    RULE = "RULE"
    SYMBOLIC = "SYMBOLIC"
    LLM = "LLM"
    LLM_STUB = "LLM_STUB"
    HUMAN = "HUMAN"
    EXTERNAL = "EXTERNAL"


class ModelUsage(ContractModel):
    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


class ProposalSource(ContractModel):
    kind: ProposalSourceKind
    strategy: PluginRef
    model: str | None = Field(default=None, description="model identifier for LLM / LLM_STUB sources")
    model_call_ids: list[str] = Field(default_factory=list)


class ActionProposal(ContractModel):
    proposal_id: str
    run_id: str
    step_id: str
    step: int = Field(ge=0)
    actor_id: str
    action: GroundAction
    based_on_revision: int = Field(ge=0, description="observation state_revision the proposal relied on")
    source: ProposalSource
    rationale: str | None = None
    candidates_considered: int | None = None
    usage: ModelUsage = Field(default_factory=ModelUsage)


class OutcomeStatus(StrEnum):
    APPLIED = "APPLIED"
    REJECTED = "REJECTED"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_NON_RETRYABLE = "FAILED_NON_RETRYABLE"
    TIMED_OUT = "TIMED_OUT"
    UNKNOWN = "UNKNOWN"
    CANCELLED = "CANCELLED"


class ComparisonVerdict(StrEnum):
    MATCH = "MATCH"
    DIFFERENT = "DIFFERENT"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"


class FieldDiff(ContractModel):
    path: str
    expected: StateScalar | None
    observed: StateScalar | None
    status: Literal["MATCH", "DIFFERENT", "UNKNOWN"]


class EffectComparison(ContractModel):
    verdict: ComparisonVerdict
    expected_by: str = Field(description="what produced the expectation, e.g. model:<package>@<version>")
    diffs: list[FieldDiff] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)


class ActionOutcome(ContractModel):
    operation_id: str
    run_id: str
    step_id: str
    proposal_id: str | None = None
    action: GroundAction
    status: OutcomeStatus
    effect_applied: bool | None = Field(description="null when it is unknown whether the effect took place")
    revision_before: int = Field(ge=0)
    revision_after: int | None = Field(default=None, ge=0)
    result: dict[str, Any] = Field(default_factory=dict)
    error: ErrorInfo | None = None
    effect_comparison: EffectComparison | None = None
    evidence: list[EvidenceRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def _consistent(self) -> ActionOutcome:
        if self.status is OutcomeStatus.APPLIED and self.effect_applied is not True:
            raise ValueError("APPLIED outcome must have effect_applied=true")
        if self.status is OutcomeStatus.UNKNOWN and self.effect_applied is not None:
            raise ValueError("UNKNOWN outcome must have effect_applied=null")
        return self


# =========================================================================== BoundedCheckResult


class QueryKind(StrEnum):
    GOAL_REACHABILITY = "GOAL_REACHABILITY"
    INVARIANT_VIOLATION = "INVARIANT_VIOLATION"
    ACTION_PRECONDITION = "ACTION_PRECONDITION"


class QuerySemantics(StrEnum):
    EXISTS_PATH = "EXISTS_PATH"  # is there a path (≤ bound) reaching the goal?
    ALL_PATHS = "ALL_PATHS"  # do all paths (≤ bound) satisfy the invariant? (searched as a violating path)
    SINGLE_STEP = "SINGLE_STEP"  # is the action applicable in the given (possibly partial) state?


QUERY_SEMANTICS = {
    QueryKind.GOAL_REACHABILITY: QuerySemantics.EXISTS_PATH,
    QueryKind.INVARIANT_VIOLATION: QuerySemantics.ALL_PATHS,
    QueryKind.ACTION_PRECONDITION: QuerySemantics.SINGLE_STEP,
}


class SearchVerdict(StrEnum):
    WITNESS = "WITNESS"
    NO_WITNESS_WITHIN_BOUND = "NO_WITNESS_WITHIN_BOUND"
    UNKNOWN = "UNKNOWN"
    UNSUPPORTED = "UNSUPPORTED"


class PreconditionVerdict(StrEnum):
    APPLICABLE = "APPLICABLE"
    INAPPLICABLE = "INAPPLICABLE"
    UNKNOWN = "UNKNOWN"
    UNSUPPORTED = "UNSUPPORTED"


class CheckBound(ContractModel):
    max_steps: int = Field(ge=0, description="maximum path length explored (0 for single-step queries)")
    timeout_ms: int | None = Field(default=None, ge=1)


class CheckQuery(ContractModel):
    kind: QueryKind
    property_id: Name | None = Field(default=None, description="goal / invariant property to query")
    action: GroundAction | None = Field(default=None, description="action for ACTION_PRECONDITION")
    bound: CheckBound
    initial_state: Literal["MODEL_INITIAL", "GIVEN_STATE"] = "MODEL_INITIAL"

    @model_validator(mode="after")
    def _shape(self) -> CheckQuery:
        if self.kind is QueryKind.ACTION_PRECONDITION:
            if self.action is None:
                raise ValueError("ACTION_PRECONDITION requires `action`")
        elif self.property_id is None:
            raise ValueError(f"{self.kind} requires `property_id`")
        return self


class WitnessStep(ContractModel):
    step: int
    action: GroundAction | None = Field(description="action leading into this state (null for step 0)")
    state: dict[str, StateScalar]


class Witness(ContractModel):
    steps: list[WitnessStep]
    replay: Literal["CONFIRMED", "REFUTED", "NOT_REPLAYED"] = "NOT_REPLAYED"
    replay_note: str | None = None


class BackendInfo(ContractModel):
    name: str
    version: str


class SolverStats(ContractModel):
    solver_status: str = Field(description="raw backend status, e.g. sat / unsat / unknown / not-run")
    steps_explored: int = 0
    elapsed_ms: float = 0.0
    timeout_ms: int | None = None
    reason_unknown: str | None = None


class UnsupportedInfo(ContractModel):
    feature: str
    reason: str
    extension_point: str | None = Field(default=None, description="interface through which support can be added")


class BoundedCheckResult(ExtensibleModel):
    contract_version: ContractVersion = "formal-lab-contracts/v1"
    check_id: str
    query: CheckQuery
    semantics: QuerySemantics
    verdict: SearchVerdict | PreconditionVerdict
    bound: CheckBound
    scope: Literal["MODEL_INTERNAL"] = Field(
        default="MODEL_INTERNAL", description="conclusion holds for the model, not for the real system"
    )
    assumptions: list[str] = Field(default_factory=list)
    model_digest: Digest
    state_digest: Digest | None = None
    action_digest: Digest | None = None
    witness: Witness | None = None
    variable_mapping: dict[str, str] = Field(default_factory=dict, description="solver symbol → state path")
    backend: BackendInfo
    stats: SolverStats
    unsupported: UnsupportedInfo | None = None
    explanation: str | None = None

    @model_validator(mode="after")
    def _verdict_matches_kind(self) -> BoundedCheckResult:
        search = self.query.kind in (QueryKind.GOAL_REACHABILITY, QueryKind.INVARIANT_VIOLATION)
        allowed = SearchVerdict if search else PreconditionVerdict
        try:
            self.verdict = allowed(str(self.verdict))
        except ValueError as exc:
            raise ValueError(f"verdict {self.verdict} not valid for {self.query.kind}") from exc
        if self.semantics is not QUERY_SEMANTICS[self.query.kind]:
            raise ValueError(f"semantics {self.semantics} does not match {self.query.kind}")
        if self.verdict == SearchVerdict.WITNESS and self.witness is None:
            raise ValueError("WITNESS verdict requires a witness")
        if str(self.verdict) == "UNSUPPORTED" and self.unsupported is None:
            raise ValueError("UNSUPPORTED verdict requires `unsupported` details")
        return self


# =========================================================================== TraceEvent


class EventType(StrEnum):
    RUN_CREATED = "RUN_CREATED"
    RUN_QUEUED = "RUN_QUEUED"
    RUN_STARTED = "RUN_STARTED"
    OBSERVATION = "OBSERVATION"
    CANDIDATES = "CANDIDATES"
    ACTION_PROPOSED = "ACTION_PROPOSED"
    CHECK_COMPLETED = "CHECK_COMPLETED"
    ACTION_OUTCOME = "ACTION_OUTCOME"
    EFFECT_COMPARED = "EFFECT_COMPARED"
    STATE_SNAPSHOT = "STATE_SNAPSHOT"
    RUN_PAUSING = "RUN_PAUSING"
    RUN_PAUSED = "RUN_PAUSED"
    RUN_RESUMED = "RUN_RESUMED"
    RUN_CANCELLING = "RUN_CANCELLING"
    RUN_CANCELLED = "RUN_CANCELLED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    RUN_SUCCEEDED = "RUN_SUCCEEDED"
    RUN_FAILED = "RUN_FAILED"
    METRICS_COMPUTED = "METRICS_COMPUTED"
    LOG = "LOG"


class TraceEvent(ContractModel):
    event_id: str
    run_id: str
    seq: int = Field(ge=1, description="monotonic per-run sequence number, gap-free")
    event_type: EventType
    causal_parents: list[str] = Field(default_factory=list, description="event ids this event was caused by")
    logical_step: int | None = Field(default=None, ge=0)
    wall_time: datetime
    actor_id: str | None = None
    payload_schema: str = Field(description="schema id of payload, e.g. formal-lab/events/ACTION_PROPOSED@1")
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None


# =========================================================================== Metrics


class MetricDirection(StrEnum):
    HIGHER_IS_BETTER = "HIGHER_IS_BETTER"
    LOWER_IS_BETTER = "LOWER_IS_BETTER"
    NONE = "NONE"


class Aggregation(StrEnum):
    MEAN = "MEAN"
    SUM = "SUM"
    MEDIAN = "MEDIAN"
    MIN = "MIN"
    MAX = "MAX"
    RATE = "RATE"


class MetricDefinition(ContractModel):
    metric_id: str = Field(pattern=r"^[a-z0-9_.-]+$")
    version: str = "1"
    label: str
    unit: str
    direction: MetricDirection
    aggregation: Aggregation
    value_type: Literal["float", "int", "bool"] = "float"
    description: str | None = None


class MetricStatus(StrEnum):
    OK = "OK"
    MISSING = "MISSING"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    ERROR = "ERROR"


class ConfidenceInterval(ContractModel):
    low: float
    high: float
    level: float = Field(gt=0, lt=1)
    method: str
    n: int = Field(ge=1)


class MetricResult(ContractModel):
    metric_id: str
    metric_version: str
    subject: str = Field(description="run id, or matrix-cell key for aggregates")
    value: float | None
    status: MetricStatus
    missing_reason: str | None = None
    unit: str | None = None
    sample_size: int | None = Field(default=None, ge=0, description="number of runs aggregated (aggregates only)")
    missing_count: int | None = Field(default=None, ge=0)
    aggregation: Aggregation | None = None
    ci: ConfidenceInterval | None = None
    evidence: list[EvidenceRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def _value_status(self) -> MetricResult:
        if self.status is MetricStatus.OK and self.value is None:
            raise ValueError("OK metric requires a value")
        if self.status is not MetricStatus.OK and self.value is not None:
            raise ValueError(f"{self.status} metric must not carry a value")
        return self


# =========================================================================== RunManifest


class RunStatus(StrEnum):
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PAUSING = "PAUSING"
    PAUSED = "PAUSED"
    CANCELLING = "CANCELLING"
    CANCELLED = "CANCELLED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"


TERMINAL_RUN_STATUSES = frozenset(
    {RunStatus.CANCELLED, RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.BUDGET_EXHAUSTED}
)


class PluginPin(ContractModel):
    role: str = Field(description="environment / strategy:<actor> / verifier / evaluator / model_frontend")
    plugin_id: PluginId
    version: SemVer
    interface: PluginInterface
    interface_version: str
    descriptor_digest: Digest


class PlatformInfo(ContractModel):
    version: str
    source_revision: str | None = None


class RunManifest(ExtensibleModel):
    contract_version: ContractVersion = "formal-lab-contracts/v1"
    run_id: str
    project_id: str
    created_at: datetime
    scenario: ScenarioManifest = Field(description="scenario snapshot as it was when the run was created")
    scenario_digest: Digest
    model: ModelRef
    plugins: list[PluginPin]
    participants: list[Participant] = Field(description="effective per-actor strategy (after overrides)")
    config: dict[str, Any] = Field(default_factory=dict)
    budget: Budget
    seed: int
    status: RunStatus
    status_reason: str | None = None
    source_run_id: str | None = Field(default=None, description="run this one re-runs (lineage)")
    matrix_id: str | None = None
    platform: PlatformInfo
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    budget_usage: BudgetUsage = Field(default_factory=BudgetUsage)


# =========================================================================== runtime exchange types


class CandidateAction(ContractModel):
    action: GroundAction
    label: str | None = None
    belief_applicability: PreconditionVerdict = Field(
        description="applicability judged on the actor's observation (unknown facts stay UNKNOWN)"
    )


class PlanningContext(ContractModel):
    run_id: str
    step: int
    step_id: str
    actor_id: str
    observation: Observation
    action_specs: list[ActionSpec]
    candidates: list[CandidateAction]
    model: ModelRef
    budget: Budget
    usage: BudgetUsage
    seed: int


class EnvironmentSnapshot(ContractModel):
    environment: PluginRef
    step: int = Field(ge=0)
    state_revision: int = Field(ge=0)
    digest: Digest
    data: dict[str, Any]


class StepRecord(ContractModel):
    step: int
    observation: Observation
    proposal: ActionProposal | None
    outcome: ActionOutcome | None
    checks: list[BoundedCheckResult] = Field(default_factory=list)


class EpisodeRecord(ContractModel):
    """Input to Evaluator.score: everything needed to compute metrics deterministically."""

    run_id: str
    scenario: ScenarioManifest
    status: RunStatus
    steps: list[StepRecord]
    final_truth_state: dict[str, StateScalar]
    final_step: int
    usage: BudgetUsage
    environment_summary: dict[str, Any] = Field(default_factory=dict)

