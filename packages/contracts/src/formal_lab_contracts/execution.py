"""formal-lab-contracts/v2 — execution records: turn state, belief, task plans, planner checkpoints, operations,
environment sessions, probes, stage records, step / episode records and query bundles."""

from __future__ import annotations

import hashlib as _hashlib
import json as _json
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import Field, model_validator

from .common import ContractModel, Digest, EvidenceRef, Identifier, PluginRef, StateScalar
from .errors import ErrorInfo
from .ir import Expr
from .kernel import (
    OPERATION_TRANSITIONS,
    AssumptionSet,
    ExecutionPhase,
    ExecutionStage,
    GateVerdict,
    OperationEffect,
    OperationState,
    Provenance,
    StageStatus,
    TerminationReason,
    TurnRef,
)
from .objects import (
    ActionOutcome,
    ActionProposal,
    BoundedCheckResult,
    BudgetUsage,
    CheckQuery,
    GroundAction,
    ModelPackage,
    ModelRef,
    Observation,
    ProposalSourceKind,
    RetrySemantics,
    RunStatus,
    ScenarioManifest,
)

# =========================================================================== turns


class TurnState(ContractModel):
    """Persistent cursor of the TurnScheduler (P2-031): restored exactly after pause, crash or continue-as-new."""

    global_step: int = Field(ge=0, description="last completed global step (0 before the first turn)")
    round: int = Field(ge=0)
    position: int = Field(ge=0, description="index into the turn cycle of the next turn")
    actor_steps: dict[str, int] = Field(default_factory=dict)
    skipped: dict[str, int] = Field(default_factory=dict, description="turns passed per actor (no action)")
    retired: list[str] = Field(default_factory=list, description="actors out of budget / finished; never scheduled")
    goals_reached: list[str] = Field(default_factory=list, description="actors whose own goal holds")
    no_progress: int = Field(default=0, ge=0, description="consecutive turns without a state change")


# =========================================================================== belief


class BeliefState(ContractModel):
    """What one participant may plan with: every location has a value, each with its provenance (P2-025)."""

    actor_id: str
    step: int = Field(ge=0)
    world_revision: int = Field(ge=0)
    state: dict[str, StateScalar]
    provenance: dict[str, Provenance]
    as_of_step: dict[str, int] = Field(default_factory=dict, description="STALE locations: step of the value")
    free_paths: list[str] = Field(default_factory=list,
                                  description="locations completion-based checks range over (the observation's "
                                  "unknown items); other non-KNOWN locations are assumed at their value")
    assumptions: AssumptionSet

    def paths(self, provenance: Provenance) -> list[str]:
        return sorted(p for p, v in self.provenance.items() if v is provenance)


# =========================================================================== joint batches (phase 3A, G4)


class BatchMemberStatus(StrEnum):
    PROPOSED = "PROPOSED"  # proposed on the round-start observation; submitted with the batch
    PASSED = "PASSED"  # had its turn but no applicable action (SKIP_ACTOR)
    ABSENT = "ABSENT"  # retired (own budget) before it could propose in this round
    TIMED_OUT = "TIMED_OUT"  # had not proposed within the round's batch_timeout_s; its proposal is not submitted
    CANCELLED = "CANCELLED"  # the run was cancelled before the batch was submitted


class BatchMember(ContractModel):
    actor_id: Identifier
    status: BatchMemberStatus
    proposal_id: str | None = None
    global_step: int | None = Field(default=None, ge=0, description="global step of its proposal")
    actor_step: int | None = Field(default=None, ge=0)
    reason: str | None = None


class BatchRecord(ContractModel):
    """One round of a JOINT_BATCH run: who proposed at which global step, and the single environment step the batch
    was applied at. Kept in the run's carry state while open, so a restart continues the round."""

    batch_id: str
    run_id: str
    round: int = Field(ge=1)
    status: Literal["OPEN", "SUBMITTED", "CANCELLED"]
    expected: list[Identifier] = Field(description="every participant, in turn order; each ends with one member "
                                                  "status")
    members: list[BatchMember] = Field(default_factory=list)
    opened_at_step: int = Field(ge=1)
    opened_at: datetime
    submitted_at_step: int | None = None
    env_step: int | None = Field(default=None, ge=0, description="environment step count after the batch")
    operation_id: str | None = None
    semantics: str | None = Field(default=None, description="the environment's declared batch semantics")
    joint_prediction: bool = Field(default=False, description="the driver declares the same joint semantics, so "
                                                              "effects are compared against a joint prediction")
    note: str | None = None


# =========================================================================== task plans / checkpoints


class TaskStatus(StrEnum):
    PENDING = "PENDING"
    READY = "READY"  # dependencies done
    IN_PROGRESS = "IN_PROGRESS"  # its action was proposed; waiting for the completion criterion
    DONE = "DONE"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class TaskNode(ContractModel):
    node_id: str = Field(min_length=1)
    label: str | None = None
    action: GroundAction | None = Field(default=None, description="action that executes the task (if any)")
    depends_on: list[str] = Field(default_factory=list)
    done_when: Expr | None = Field(default=None, description="completion criterion over the belief state (IR)")
    status: TaskStatus = TaskStatus.PENDING
    attempts: int = 0
    completed_at_step: int | None = None
    note: str | None = None


class PlanTrigger(StrEnum):
    INITIAL = "INITIAL"
    NEW_OBSERVATION = "NEW_OBSERVATION"  # the belief contradicts what the plan expected
    RESOURCE_CHANGE = "RESOURCE_CHANGE"  # a resource the plan relies on changed (e.g. another actor took it)
    BUDGET = "BUDGET"  # remaining budget cannot cover the plan
    EFFECT_DIFFERENCE = "EFFECT_DIFFERENCE"  # observed effects differ from predictions
    ACTION_REJECTED = "ACTION_REJECTED"
    RULE = "RULE"  # a REPLAN rule fired
    RESTORED = "RESTORED"  # restored from a checkpoint (no change)


class PlanRevision(ContractModel):
    trigger: PlanTrigger
    detail: str
    at_step: int = Field(ge=0)


class PlanGenerator(ContractModel):
    kind: ProposalSourceKind = Field(description="RULE / SYMBOLIC / LLM / LLM_STUB / EXTERNAL")
    strategy: PluginRef
    model: str | None = None
    method: str | None = None


class TaskPlan(ContractModel):
    """A structured, versioned plan with a cursor (P2-040). Every revision is a new version with its reason."""

    plan_id: Identifier
    actor_id: str
    version: int = Field(ge=1)
    generator: PlanGenerator
    created_at_step: int = Field(ge=0)
    nodes: list[TaskNode] = Field(default_factory=list)
    cursor: str | None = Field(default=None, description="node currently being executed")
    status: Literal["ACTIVE", "COMPLETED", "INVALIDATED", "ABANDONED"] = "ACTIVE"
    revision: PlanRevision | None = Field(default=None, description="why this version replaced the previous one")
    parent_version: int | None = None
    objective_value: float | None = None
    assumptions_digest: str | None = None

    @model_validator(mode="after")
    def _graph(self) -> TaskPlan:
        ids = [n.node_id for n in self.nodes]
        if len(set(ids)) != len(ids):
            raise ValueError("task node ids must be unique")
        known = set(ids)
        for n in self.nodes:
            missing = [d for d in n.depends_on if d not in known]
            if missing:
                raise ValueError(f"node {n.node_id} depends on unknown nodes {missing}")
        if self.cursor is not None and self.cursor not in known:
            raise ValueError(f"cursor {self.cursor!r} is not a node")
        return self

    def node(self, node_id: str) -> TaskNode:
        return next(n for n in self.nodes if n.node_id == node_id)

    def ready(self) -> list[TaskNode]:
        done = {n.node_id for n in self.nodes if n.status in (TaskStatus.DONE, TaskStatus.SKIPPED)}
        return [n for n in self.nodes if n.status in (TaskStatus.PENDING, TaskStatus.READY)
                and all(d in done for d in n.depends_on)]

    def progress(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for n in self.nodes:
            key = str(getattr(n.status, "value", n.status))
            out[key] = out.get(key, 0) + 1
        return out


class PlannerCheckpoint(ContractModel):
    """Recoverable planner state (P2-041): persisted with the step's proposal and restored in a fresh process."""

    actor_id: str
    planner: PluginRef
    step: int = Field(ge=0, description="global step after which the checkpoint was taken")
    plan: TaskPlan | None = None
    progress: dict[str, Any] = Field(default_factory=dict, description="structured task progress / memory")
    summary: str | None = Field(default=None, description="short natural-language summary (model-assisted)")
    rng_state: list[Any] | None = Field(default=None, description="random.getstate() as JSON")
    cache_refs: list[str] = Field(default_factory=list, description="keys of reusable solver/plan cache entries")
    remaining_budget: BudgetUsage | None = None
    digest: Digest | None = None


# =========================================================================== operations / sessions / probes


class OperationTransition(ContractModel):
    state: OperationState
    at: datetime
    reason: str
    attempt: int = Field(default=1, ge=1)
    effect: OperationEffect | None = Field(default=None, description="what this transition did to the backend "
                                           "(phase 3A); absent in records written before it")


class ConditionCheck(ContractModel):
    """One business / resource condition evaluated by an execution gate."""

    name: str = Field(min_length=1)
    holds: bool | None = Field(description="None: the gate could not determine it")
    observed: Any = None
    required: Any = None
    paths: list[str] = Field(default_factory=list, description="state locations the condition read")
    detail: str | None = None


def params_digest(params: dict[str, Any]) -> str:
    """sha256 of an action's parameters in canonical JSON — the one definition every binding uses."""
    body = _json.dumps(params, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return _hashlib.sha256(body.encode()).hexdigest()


class ExecutionContext(ContractModel):
    """The authoritative basis of one send, built by the kernel right before it (phase 4A, A2) — never by a strategy.

    Identity comes from the kernel's turn (not the proposal's `actor_id` claim), the environment / session / service
    identity from the run's environment, and `current_revision` from the environment's own authoritative read at the
    side-effect boundary. `proposal_revision` is kept separately: the revision the plan was made on is not the
    revision the write happens on. When the current revision cannot be read it is None with `revision_source`
    UNKNOWN, and a gate that needs it must deny. Receipts bind to `execution_binding(context)` — the same canonical
    form is used to issue and to verify."""

    run_id: str
    step: int = Field(ge=0)
    turn: TurnRef | None = None
    actor_id: Identifier = Field(description="the actor of the kernel's turn (authoritative identity)")
    operation_id: str
    phase: ExecutionPhase
    action_type: str
    action_params_digest: str = Field(description="params_digest(action.params)")
    request_digest: str
    environment: PluginRef
    session_id: str | None = None
    service_identity: str | None = None
    proposal_revision: int | None = Field(default=None, description="the revision the proposal was planned on")
    current_revision: int | None = Field(default=None, description="the environment's revision at the send")
    revision_source: Literal["FRESH", "SERIALIZED", "UNKNOWN"] = Field(
        description="FRESH: read from the environment right before the send (env.current_revision); SERIALIZED: a "
                    "pure-data environment whose state lives in this serialized step; UNKNOWN: could not be read")
    revision_note: str | None = None
    versions: dict[str, str] = Field(default_factory=dict, description="model, driver/adapter, rules, participant "
                                                                       "view, environment and gate versions")
    read_at: datetime


BINDING_FIELDS = ("run_id", "step", "turn", "actor_id", "operation_id", "action_type", "action_params_digest",
                  "environment", "session_id", "service_identity", "current_revision", "versions")


def execution_binding(context: ExecutionContext) -> dict[str, Any]:
    """The canonical binding of a send: what a verification receipt must match field for field."""
    data = context.model_dump(mode="json")
    turn = data.get("turn") or {}
    return {
        "run_id": data["run_id"], "step": data["step"],
        "turn": {k: turn.get(k) for k in ("global_step", "round", "actor_id", "actor_step")} if turn else None,
        "actor_id": data["actor_id"], "operation_id": data["operation_id"], "action_type": data["action_type"],
        "action_params_digest": data["action_params_digest"],
        "environment": f"{data['environment']['plugin_id']}@{data['environment']['version']}",
        "session_id": data["session_id"], "service_identity": data["service_identity"],
        "current_revision": data["current_revision"], "versions": dict(sorted(data["versions"].items())),
    }


def execution_binding_digest(context: ExecutionContext) -> str:
    body = _json.dumps(execution_binding(context), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return _hashlib.sha256(body.encode()).hexdigest()


class GateRequest(ContractModel):
    """What an execution gate sees for one send (phase 3A, G2). `values` are the locations the gate asked for, read
    by the kernel right before the send: fresh from the environment when it answers observation requests
    (env.observe_on_request), else from the actor's current observation. `execution` (phase 4A) is the
    authoritative basis of the send — gates read the current revision there instead of borrowing a location."""

    run_id: str
    step: int = Field(ge=0)
    actor_id: str | None = None
    operation_id: str
    phase: ExecutionPhase
    action: GroundAction
    proposal_id: str | None = None
    based_on_revision: int | None = None
    values: dict[str, StateScalar] = Field(default_factory=dict)
    values_source: Literal["FRESH", "OBSERVATION", "NONE"] = "NONE"
    values_revision: int | None = None
    request_digest: str
    config: dict[str, Any] = Field(default_factory=dict, description="the gate's scenario configuration")
    execution: ExecutionContext | None = Field(default=None, description="authoritative basis of the send (phase 4A)")


class GateResult(ContractModel):
    """A gate's answer: ALLOW or DENY with the reason and the conditions it evaluated."""

    verdict: GateVerdict
    reason: str = Field(min_length=1)
    conditions: list[ConditionCheck] = Field(default_factory=list)


class ExecutionDecision(ContractModel):
    """Typed record of one pre-execution decision (phase 3A, G2): kept on the operation record and as an event, so
    decision, operation record and the backend's side effect can be traced to each other."""

    decision_id: str
    run_id: str
    step: int = Field(ge=0)
    actor_id: str | None = None
    operation_id: str
    gate: PluginRef
    phase: ExecutionPhase
    verdict: GateVerdict
    reason: str = Field(min_length=1)
    conditions: list[ConditionCheck] = Field(default_factory=list)
    values_source: Literal["FRESH", "OBSERVATION", "NONE"] = "NONE"
    checked_at_revision: int | None = None
    request_digest: str
    at: datetime
    execution: ExecutionContext | None = Field(default=None, description="the basis the decision was made on "
                                                                         "(phase 4A); absent in older records")


class ReconciliationResult(ContractModel):
    method: Literal["QUERY_OPERATION", "STATE_COMPARISON", "SNAPSHOT_REPLAY", "MANUAL"]
    found: bool = Field(description="the environment knows the operation (it took effect or was rejected)")
    outcome: ActionOutcome | None = None
    note: str


class ReviewMark(ContractModel):
    status: Literal["NEEDS_REVIEW", "CONFIRMED_APPLIED", "CONFIRMED_NOT_APPLIED", "TERMINATED"]
    by: str
    at: datetime
    note: str | None = None


class OperationRecord(ContractModel):
    """Coordination record of one environment operation (P2-051). Intent is recorded before dispatch; every state
    change is kept with its reason."""

    operation_id: str
    run_id: str
    step: int = Field(ge=0)
    actor_id: str | None = None
    kind: Literal["apply", "reset", "probe", "batch"] = "apply"
    state: OperationState
    transitions: list[OperationTransition] = Field(default_factory=list)
    proposal_id: str | None = None
    action: GroundAction | None = None
    based_on_revision: int | None = None
    outcome: ActionOutcome | None = None
    reconciliation: ReconciliationResult | None = None
    review: ReviewMark | None = None
    attempts: int = Field(default=0, ge=0)
    request_digest: str | None = Field(default=None, description="sha256 of the canonical request (actor, kind, "
                                       "action); the same id with another request is a conflict (phase 3A)")
    decisions: list[ExecutionDecision] = Field(default_factory=list, description="pre-execution decisions (phase 3A)")
    batch_id: str | None = Field(default=None, description="JOINT_BATCH: the batch this operation submitted")
    batch_outcomes: list[ActionOutcome] = Field(default_factory=list, description="JOINT_BATCH: one outcome per "
                                                "submitted proposal, in submission order")

    @model_validator(mode="after")
    def _transitions_valid(self) -> OperationRecord:
        prev: OperationState | None = None
        for t in self.transitions:
            if prev is not None and t.state not in OPERATION_TRANSITIONS[prev] and t.state != prev:
                raise ValueError(f"illegal operation transition {prev} → {t.state}")
            prev = t.state
        if prev is not None and prev != self.state:
            raise ValueError("`state` must equal the last transition")
        return self


class RecoveryMode(StrEnum):
    RESEED = "RESEED"  # re-create from scenario + seed (pure-data)
    SNAPSHOT = "SNAPSHOT"  # restore a FULL_STATE snapshot
    SERVICE_RESET = "SERVICE_RESET"  # ask the service to reset to a seeded state
    STATE_IMPORT = "STATE_IMPORT"  # load an exported business state


class SessionStatus(StrEnum):
    CREATED = "CREATED"
    STARTING = "STARTING"
    READY = "READY"
    RESETTING = "RESETTING"
    CLOSED = "CLOSED"
    FAILED = "FAILED"


class EnvironmentSession(ContractModel):
    """A running environment instance and its lifecycle (P2-050 / P2-062)."""

    session_id: Identifier
    environment: PluginRef
    backend: Literal["PURE_DATA", "SERVICE"]
    status: SessionStatus
    capabilities: list[str] = Field(default_factory=list)
    recovery_modes: list[RecoveryMode] = Field(default_factory=list)
    endpoint: str | None = Field(default=None, description="base URL of a service backend (loopback / service name)")
    project_label: str = Field(description="ownership label on every resource this session creates")
    owner: dict[str, str] = Field(default_factory=dict, description="project_id / run_id / profile")
    revision: int = Field(default=0, ge=0)
    created_at: datetime
    updated_at: datetime
    health: dict[str, Any] = Field(default_factory=dict)
    note: str | None = None


class ProbeWindow(ContractModel):
    kind: Literal["LOGICAL_STEPS", "WALL_SECONDS"]
    size: float = Field(gt=0)
    start: float
    end: float


class ProbeResult(ContractModel):
    """An independent business observation (P2-064): taken from the service itself, not from the agent's view."""

    probe_id: str
    probe: PluginRef
    source: str = Field(description="where the value was read, e.g. GET /metrics of the order service")
    metric: str
    value: float | None
    unit: str
    status: Literal["OK", "MISSING", "ERROR"] = "OK"
    missing_reason: str | None = None
    window: ProbeWindow
    logical_step: int | None = None
    wall_time: datetime
    evidence: list[EvidenceRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def _value(self) -> ProbeResult:
        if self.status == "OK" and self.value is None:
            raise ValueError("OK probe result needs a value")
        if self.status != "OK" and self.value is not None:
            raise ValueError("MISSING / ERROR probe results carry no value")
        return self


# =========================================================================== stages / steps / episodes


class StageRecord(ContractModel):
    """Typed record of one execution stage (P2-016): inputs/outputs by digest, retry semantics, error, evidence."""

    stage: ExecutionStage
    status: StageStatus
    retry: RetrySemantics
    input_digest: str | None = None
    output_digest: str | None = None
    elapsed_ms: float = 0.0
    error: ErrorInfo | None = None
    evidence: list[EvidenceRef] = Field(default_factory=list)
    note: str | None = None


class StepRecord(ContractModel):
    step: int
    observation: Observation
    proposal: ActionProposal | None
    outcome: ActionOutcome | None
    checks: list[BoundedCheckResult] = Field(default_factory=list)
    actor_id: str | None = Field(default=None, description="acting participant (v2)")
    turn: TurnRef | None = None
    stages: list[StageRecord] = Field(default_factory=list)
    operation: OperationRecord | None = None
    probes: list[ProbeResult] = Field(default_factory=list)


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
    actor_usage: dict[str, BudgetUsage] = Field(default_factory=dict)
    termination_reason: TerminationReason | None = None
    probes: list[ProbeResult] = Field(default_factory=list)
    backend: Literal["PURE_DATA", "SERVICE"] = "PURE_DATA"


# =========================================================================== query bundles


class QueryBundle(ContractModel):
    """Replayable package of one check (P2-029): everything needed to re-ask and to explain the answer."""

    format: Literal["formal-lab/query-bundle@1"] = "formal-lab/query-bundle@1"
    bundle_id: str
    created_at: datetime
    model: ModelRef
    driver: PluginRef | None = None
    verifier: PluginRef
    query: CheckQuery
    state: dict[str, StateScalar] | None = None
    unknown_paths: list[str] = Field(default_factory=list)
    assumptions: AssumptionSet | None = None
    result: BoundedCheckResult
    explanation: list[str] = Field(default_factory=list, description="the shared, rendered explanation")
    replay: dict[str, Any] = Field(default_factory=dict, description="independent re-check of the witness")
    package: ModelPackage | None = Field(default=None, description="embedded model package (exports), so the bundle "
                                                                   "can be replayed offline")
