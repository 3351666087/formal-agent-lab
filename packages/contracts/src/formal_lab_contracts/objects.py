"""The core objects of formal-lab-contracts/v2 and their supporting types.

v2 keeps every v1 object name, field name and meaning; it adds optional fields (multi-participant turns, cost
objectives, assumptions, operation states, …), a typed model payload (`ModelPackage.payload`, replacing the
mandatory `ir`) and extends a few enums. v1 JSON is upgraded by `formal_lab_contracts.compat`.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

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
    Namespace,
    PluginId,
    PluginRef,
    SemVer,
    StateScalar,
)
from .errors import ErrorInfo
from .ir import Effect, Expr, ModelIR
from .kernel import (
    ActionScope,
    AssumptionSet,
    AssumptionSetRef,
    CapabilityNegotiation,
    ConflictPolicy,
    ExecutionStage,
    ObjectiveSpec,
    ObservationRequest,
    ObservationTiming,
    OperationState,
    OptimizationResult,
    OptimizationStatus,
    PlanRef,
    ReleaseRef,
    RobustnessResult,
    RobustnessVerdict,
    RuleSetRef,
    TerminationPolicy,
    TerminationReason,
    TurnPolicy,
    TurnRef,
)

# =========================================================================== PluginDescriptor


class PluginInterface(StrEnum):
    MODEL_FRONTEND = "MODEL_FRONTEND"
    PLANNER = "PLANNER"
    VERIFIER = "VERIFIER"
    ENVIRONMENT = "ENVIRONMENT"
    EVALUATOR = "EVALUATOR"
    ARTIFACT_STORE = "ARTIFACT_STORE"
    SEMANTIC_DRIVER = "SEMANTIC_DRIVER"  # v2: validates/loads a model payload, candidates, predictions, properties
    PROBE = "PROBE"  # v2: independent business observations of an environment session
    EXECUTION_GATE = "EXECUTION_GATE"  # v2 (phase 3A): decides right before each send whether it may go ahead


INTERFACE_VERSION = "2"
# interface versions the registry accepts: v1 plugins keep working for the interfaces that existed in v1
SUPPORTED_INTERFACE_VERSIONS = ("1", "2")
V2_ONLY_INTERFACES = frozenset({PluginInterface.SEMANTIC_DRIVER, PluginInterface.PROBE,
                                PluginInterface.EXECUTION_GATE})


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
    condition_labels: dict[str, str] = Field(default_factory=dict, description="execution-gate condition name → label "
                                             "(phase 3A)")


class PluginDescriptor(ExtensibleModel):
    contract_version: Literal["formal-lab-contracts/v1", "formal-lab-contracts/v2"] = "formal-lab-contracts/v2"
    plugin_id: PluginId
    version: SemVer
    interface: PluginInterface
    interface_version: str = INTERFACE_VERSION
    capabilities: list[Capability] = Field(default_factory=list)
    requires: list[Capability] = Field(
        default_factory=list,
        description="capabilities this plugin needs from its collaborators; params.of names the role "
        "(driver / environment / verifier), e.g. {id: env.persistent_session, params: {of: environment}}")
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


class IRPayload(ContractModel):
    """Model in the neutral finite-state IR (profile deterministic_finite_v1)."""

    kind: Literal["fal-ir"] = "fal-ir"
    ir: ModelIR


class NamespacedPayload(ContractModel):
    """Model in a profile-specific format owned by a semantic-driver plugin. `schema_id` names the JSON Schema
    (published in the driver's descriptor `input_schema`) that validates `data`."""

    kind: Literal["namespaced"] = "namespaced"
    namespace: Namespace
    schema_id: str = Field(min_length=1)
    data: dict[str, Any]


ModelPayload = Annotated[IRPayload | NamespacedPayload, Field(discriminator="kind")]


class ModelPackage(ExtensibleModel):
    contract_version: ContractVersion = "formal-lab-contracts/v2"
    package_id: Identifier
    version: int = Field(ge=1)
    frontend: PluginRef = Field(description="plugin that produced the payload")
    semantic_profile: str
    digest: Digest = Field(description="sha256 of the canonical payload (IR: of the canonical IR, as in v1)")
    payload: ModelPayload
    source: ModelSource
    compiled: list[CompiledArtifact] = Field(default_factory=list)
    created_at: datetime

    def ref(self) -> ModelRef:
        return ModelRef(package_id=self.package_id, version=self.version, digest=self.digest)

    @property
    def is_ir(self) -> bool:
        return self.payload.kind == "fal-ir"

    @property
    def ir(self) -> ModelIR:
        """The IR of an IR-payload package (v1 compatibility accessor)."""
        if isinstance(self.payload, IRPayload):
            return self.payload.ir
        from .errors import Unsupported

        raise Unsupported(f"model {self.package_id}@{self.version} ({self.semantic_profile}) has a "
                          f"{self.payload.kind} payload, not the neutral IR")


# =========================================================================== ScenarioManifest


class Budget(ContractModel):
    max_steps: int | None = Field(default=None, ge=1)
    max_wall_seconds: float | None = Field(default=None, gt=0)
    max_model_calls: int | None = Field(default=None, ge=0)
    max_tokens: int | None = Field(default=None, ge=0)


class BudgetUsage(ContractModel):
    """Usage counters. `model_calls` counts calls that returned a usable response; `model_attempts` every request
    sent (incl. failures and lost responses); tokens are only what the provider reported — calls without usage data
    are counted in `unreported_calls`, calls whose response was lost in `unconfirmed_calls`."""

    steps: int = 0
    wall_seconds: float = 0.0
    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    model_attempts: int = 0
    unreported_calls: int = 0
    unconfirmed_calls: int = 0
    observation_requests: int = 0

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
    label: str | None = None
    goal: Name | None = Field(default=None, description="the participant's own goal property (v2)")
    budget: Budget | None = Field(default=None, description="per-participant budget, counted separately (v2)")
    scope: ActionScope | None = Field(default=None, description="ground actions this participant may choose (v2)")


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
    contract_version: ContractVersion = "formal-lab-contracts/v2"
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
    stop_conditions: list[StopCondition] = Field(
        default_factory=list, description="v1 stop conditions; used only when `termination` is not given")
    turns: TurnPolicy = Field(default_factory=TurnPolicy, description="interleaving of participants (v2)")
    termination: TerminationPolicy | None = Field(default=None, description="v2 termination; overrides stop_conditions")
    objective: ObjectiveSpec | None = Field(default=None, description="cost objective for planners and reports (v2)")
    driver: PluginRef | None = Field(default=None, description="semantic driver; default: the one for the profile")
    rules: RuleSetRef | None = Field(default=None, description="event–condition–handler rules to apply (v2)")
    release: ReleaseRef | None = Field(default=None, description="checked model release the scenario runs on (v2)")
    execution_gates: list[StrategySpec] = Field(
        default_factory=list, description="pre-execution decision plugins (EXECUTION_GATE) consulted in order before "
                                          "every send of an operation (phase 3A); none = phase-2 behaviour")

    @model_validator(mode="after")
    def _participants(self) -> ScenarioManifest:
        ids = [p.actor_id for p in self.participants]
        if len(set(ids)) != len(ids):
            raise ValueError("participant actor ids must be unique")
        unknown = [a for a in self.turns.table if a not in ids]
        if unknown:
            raise ValueError(f"turn table names unknown participants {unknown}")
        if self.termination is not None and self.stop_conditions:
            raise ValueError("give either v1 `stop_conditions` or v2 `termination`, not both")
        return self

    def effective_termination(self) -> TerminationPolicy:
        """v2 termination policy; derived from v1 stop conditions when not given (same behaviour as phase 1)."""
        if self.termination is not None:
            return self.termination
        from .kernel import NoActionPolicy

        goal = next((sc.property_id for sc in self.stop_conditions if sc.kind == StopConditionKind.GOAL_REACHED
                     and sc.property_id), None)
        return TerminationPolicy(
            joint_goal=goal,
            invariants=[sc.property_id for sc in self.stop_conditions
                        if sc.kind == StopConditionKind.INVARIANT_VIOLATED and sc.property_id],
            on_no_action=NoActionPolicy.FAIL if any(sc.kind == StopConditionKind.NO_APPLICABLE_ACTION
                                                    for sc in self.stop_conditions) else NoActionPolicy.END,
        )


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
    state_revision: int = Field(ge=0, description="world revision the observation reflects")
    facts: list[Fact]
    unknowns: list[UnknownItem] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    turn: TurnRef | None = Field(default=None, description="turn the observation was taken for (v2)")
    timing: ObservationTiming = ObservationTiming.TURN_START
    requested_paths: list[str] = Field(default_factory=list,
                                       description="locations observed fresh on request (OBSERVE_MORE, v2)")
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
    """Model usage of one proposal: `model_calls` usable responses, `attempts` requests sent; tokens as reported."""

    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    attempts: int = 0
    unreported_calls: int = 0
    unconfirmed_calls: int = 0


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
    turn: TurnRef | None = None
    plan: PlanRef | None = Field(default=None, description="task-plan node this proposal executes (v2)")
    assumptions: AssumptionSetRef | None = Field(default=None, description="what the proposal assumed (v2)")
    observation_request: ObservationRequest | None = Field(
        default=None, description="ask for fresh observations first; `action` is the fallback if none are possible")


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


EvidenceStatus = Literal["observed", "verified-within-scope", "predicted", "unknown"]


class FieldDiff(ContractModel):
    path: str
    expected: StateScalar | None = Field(description="predicted by the model")
    observed: StateScalar | None
    status: Literal["MATCH", "DIFFERENT", "UNKNOWN"]
    evidence: EvidenceStatus = Field(
        default="observed",
        description="basis of `observed`: fresh observation, verified within a stated scope (probe / operation "
        "query), or unknown (not comparable); `predicted` marks a value only the model supplies (v2)")
    observed_at_step: int | None = Field(default=None, ge=0)
    freshness: Literal["FRESH", "STALE", "MISSING"] = "FRESH"


class EffectComparison(ContractModel):
    verdict: ComparisonVerdict
    expected_by: str = Field(description="what produced the expectation, e.g. model:<package>@<version>")
    diffs: list[FieldDiff] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    evidence_counts: dict[str, int] = Field(default_factory=dict, description="evidence status → fields (v2)")


class ConflictInfo(ContractModel):
    """Why a proposal based on an older world revision was rejected (shared-resource arbitration)."""

    policy: ConflictPolicy
    based_on_revision: int = Field(ge=0)
    current_revision: int = Field(ge=0)
    changed_paths: list[str] = Field(default_factory=list, description="locations written since based_on_revision")
    reason: str


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
    turn: TurnRef | None = None
    operation_state: OperationState | None = Field(default=None, description="coordination state (v2)")
    conflict: ConflictInfo | None = None

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
    OPTIMIZE_OBJECTIVE = "OPTIMIZE_OBJECTIVE"  # v2: cheapest path to the goal within a horizon
    ROBUST_SEQUENCE = "ROBUST_SEQUENCE"  # v2: does a fixed action sequence work for every completion?


class QuerySemantics(StrEnum):
    EXISTS_PATH = "EXISTS_PATH"  # is there a path (≤ bound) reaching the goal?
    ALL_PATHS = "ALL_PATHS"  # do all paths (≤ bound) satisfy the invariant? (searched as a violating path)
    SINGLE_STEP = "SINGLE_STEP"  # is the action applicable in the given (possibly partial) state?
    OPTIMAL_PATH = "OPTIMAL_PATH"  # which goal path (≤ horizon) minimises the objective lexicographically?
    ALL_COMPLETIONS = "ALL_COMPLETIONS"  # does the sequence work for every completion of the unknown locations?


QUERY_SEMANTICS = {
    QueryKind.GOAL_REACHABILITY: QuerySemantics.EXISTS_PATH,
    QueryKind.INVARIANT_VIOLATION: QuerySemantics.ALL_PATHS,
    QueryKind.ACTION_PRECONDITION: QuerySemantics.SINGLE_STEP,
    QueryKind.OPTIMIZE_OBJECTIVE: QuerySemantics.OPTIMAL_PATH,
    QueryKind.ROBUST_SEQUENCE: QuerySemantics.ALL_COMPLETIONS,
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
    objective: ObjectiveSpec | None = Field(default=None, description="OPTIMIZE_OBJECTIVE: what to minimise (v2)")
    sequence: list[GroundAction] = Field(default_factory=list, description="ROBUST_SEQUENCE: actions in order (v2)")

    @model_validator(mode="after")
    def _shape(self) -> CheckQuery:
        if self.kind is QueryKind.ACTION_PRECONDITION:
            if self.action is None:
                raise ValueError("ACTION_PRECONDITION requires `action`")
        elif self.kind is QueryKind.OPTIMIZE_OBJECTIVE:
            if self.objective is None:
                raise ValueError("OPTIMIZE_OBJECTIVE requires `objective`")
        elif self.kind is QueryKind.ROBUST_SEQUENCE:
            if not self.sequence:
                raise ValueError("ROBUST_SEQUENCE requires a non-empty `sequence`")
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
    contract_version: ContractVersion = "formal-lab-contracts/v2"
    check_id: str
    query: CheckQuery
    semantics: QuerySemantics
    verdict: SearchVerdict | PreconditionVerdict | OptimizationStatus | RobustnessVerdict
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
    assumption_set: AssumptionSet | None = Field(default=None, description="assumptions behind the answer (v2)")
    optimization: OptimizationResult | None = None
    robustness: RobustnessResult | None = None
    observation_request: ObservationRequest | None = Field(
        default=None, description="UNKNOWN precondition: which observations would settle it (v2)")
    query_bundle: ArtifactRef | None = Field(default=None, description="replayable query package (v2)")

    @model_validator(mode="after")
    def _verdict_matches_kind(self) -> BoundedCheckResult:
        allowed = VERDICTS_BY_KIND[self.query.kind]
        try:
            self.verdict = allowed(str(self.verdict))
        except ValueError as exc:
            raise ValueError(f"verdict {self.verdict} not valid for {self.query.kind}") from exc
        if self.semantics is not QUERY_SEMANTICS[self.query.kind]:
            raise ValueError(f"semantics {self.semantics} does not match {self.query.kind}")
        if self.verdict == SearchVerdict.WITNESS and self.witness is None:
            raise ValueError("WITNESS verdict requires a witness")
        if self.verdict in (OptimizationStatus.OPTIMAL, OptimizationStatus.FEASIBLE) and (
                self.witness is None or self.optimization is None):
            raise ValueError(f"{self.verdict} requires a witness and optimization details")
        if self.verdict == RobustnessVerdict.NOT_ROBUST and (self.robustness is None
                                                             or self.robustness.counterexample is None):
            raise ValueError("NOT_ROBUST requires a counterexample completion")
        if str(self.verdict) == "UNSUPPORTED" and self.unsupported is None:
            raise ValueError("UNSUPPORTED verdict requires `unsupported` details")
        return self


VERDICTS_BY_KIND: dict[QueryKind, type[StrEnum]] = {
    QueryKind.GOAL_REACHABILITY: SearchVerdict,
    QueryKind.INVARIANT_VIOLATION: SearchVerdict,
    QueryKind.ACTION_PRECONDITION: PreconditionVerdict,
    QueryKind.OPTIMIZE_OBJECTIVE: OptimizationStatus,
    QueryKind.ROBUST_SEQUENCE: RobustnessVerdict,
}


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
    # v2
    TURN_STARTED = "TURN_STARTED"
    TURN_SKIPPED = "TURN_SKIPPED"
    OBSERVATION_REQUESTED = "OBSERVATION_REQUESTED"
    PLAN_UPDATED = "PLAN_UPDATED"
    PLANNER_CHECKPOINT = "PLANNER_CHECKPOINT"
    OPERATION_STATE = "OPERATION_STATE"
    OPERATION_RECONCILED = "OPERATION_RECONCILED"
    OPERATION_REVIEW = "OPERATION_REVIEW"
    PROBE_SAMPLED = "PROBE_SAMPLED"
    RULE_EVALUATED = "RULE_EVALUATED"
    SESSION_STATE = "SESSION_STATE"
    RECOVERY = "RECOVERY"
    MODEL_REVISION_SUGGESTED = "MODEL_REVISION_SUGGESTED"
    REGRESSION_CASE_CREATED = "REGRESSION_CASE_CREATED"
    EXECUTION_DECIDED = "EXECUTION_DECIDED"  # phase 3A: a pre-execution gate allowed or denied a send


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
    turn: TurnRef | None = Field(default=None, description="turn the event belongs to (v2)")
    stage: ExecutionStage | None = Field(default=None, description="execution stage that emitted it (v2)")


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
    contract_version: ContractVersion = "formal-lab-contracts/v2"
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
    turns: TurnPolicy = Field(default_factory=TurnPolicy, description="effective interleaving (v2)")
    termination: TerminationPolicy | None = Field(default=None, description="effective termination policy (v2)")
    objective: ObjectiveSpec | None = None
    rules: RuleSetRef | None = None
    release: ReleaseRef | None = None
    negotiation: list[CapabilityNegotiation] = Field(
        default_factory=list, description="capability negotiation performed before the run was created (v2)")
    actor_usage: dict[str, BudgetUsage] = Field(default_factory=dict, description="per-participant usage (v2)")
    termination_reason: TerminationReason | None = None

    def participant(self, actor_id: str) -> Participant:
        for p in self.participants:
            if p.actor_id == actor_id:
                return p
        raise KeyError(actor_id)


# =========================================================================== runtime exchange types


class CandidateAction(ContractModel):
    action: GroundAction
    label: str | None = None
    belief_applicability: PreconditionVerdict = Field(
        description="applicability judged on the actor's observation (unknown facts stay UNKNOWN)"
    )
    reason: str | None = Field(default=None, description="why it is INAPPLICABLE / UNKNOWN (v2)")
    observation_request: ObservationRequest | None = Field(default=None,
                                                           description="UNKNOWN: what would settle it (v2)")


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
    turn: TurnRef | None = Field(default=None, description="global/actor step of this decision (v2)")
    goal: Name | None = Field(default=None, description="the actor's goal (participant goal, else joint goal)")
    objective: ObjectiveSpec | None = None
    actor_budget: Budget | None = None
    actor_usage: BudgetUsage | None = None
    participants: list[str] = Field(default_factory=list, description="all actor ids in turn order (v2)")
    observation_request_allowed: bool = Field(
        default=False, description="the environment can answer an ObservationRequest this turn (v2)")
    assumptions: AssumptionSet | None = Field(default=None, description="provenance of the belief (v2)")
    last_outcome: ActionOutcome | None = Field(
        default=None, description="the actor's previous outcome incl. its effect comparison (plan revision, v2)")
    replan_requested: str | None = Field(default=None, description="reason a REPLAN rule fired for this actor (v2)")


class EnvironmentSnapshot(ContractModel):
    """Environment state at a step. FULL_STATE snapshots of pure-data environments can be restored; persistent
    service sessions produce SESSION_MARKER snapshots (revision + session reference only), which are never restored
    — recovery reconciles against the live session instead (v2)."""

    environment: PluginRef
    step: int = Field(ge=0)
    state_revision: int = Field(ge=0)
    digest: Digest
    data: dict[str, Any]
    kind: Literal["FULL_STATE", "SESSION_MARKER"] = "FULL_STATE"
    session_id: str | None = None

