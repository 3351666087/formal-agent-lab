"""Step engine shared by every entry point (Temporal activities, local runner, SDK, Inspect adapter).

One global logical step = one participant's turn, executed as typed stages (P2-016):

    TURN → OBSERVE → PROPOSE  |  CHECK → EXECUTE → (RECONCILE) → PROBE → COMPARE → TERMINATE
    ───────── plan_step ─────── ───────────────────────── apply_step ──────────────────────────

`plan_step` decides (possibly calling a model) and is persisted before the environment is touched; `apply_step`
executes the operation through the `Coordinator` and evaluates effects, rules and termination. The engine is
persistence-agnostic: it receives the state after the previous step — environment snapshot, usage and the
`CarryState` (turn cursor, planner checkpoints, per-actor usage, rule flags, round observations) — and returns
everything to persist. Identifiers derive from (run, global step, actor), so a retried step reproduces the same
ids and idempotency keys (P2-034).

Model semantics come only from the semantic driver chosen for the pinned model (P2-010): the engine never builds
an interpreter itself.

JOINT_BATCH (phase 3A, G4): every member of a round still takes one global step for TURN → OBSERVE → PROPOSE →
CHECK, on the round-start observation; its proposal is kept in the open `BatchRecord` of the carry state (so a
restart continues the round). The step of the round's last member submits the batch through `env.step_batch` —
one environment step — and records every member's outcome and comparison at the member's own proposal step.

What a planner receives passes through its participant's `ParticipantInput` (view filter, settings); the kernel
checks, predicts and compares on the full observation.
"""

from __future__ import annotations

import contextlib
import copy
import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from formal_lab_contracts import (
    ActionOutcome,
    ActionProposal,
    BatchMember,
    BatchMemberStatus,
    BatchRecord,
    BeliefState,
    BoundedCheckResult,
    Budget,
    BudgetUsage,
    CandidateAction,
    CheckQuery,
    EffectComparison,
    EnvironmentSnapshot,
    EventType,
    ExecutionDecision,
    ExecutionPhase,
    ExecutionStage,
    GateRequest,
    GateVerdict,
    ModelPackage,
    ModelUsage,
    NoActionPolicy,
    Observation,
    ObservationTiming,
    OperationRecord,
    Participant,
    PlannerCheckpoint,
    PlanningContext,
    PluginInterface,
    PluginRef,
    PreconditionVerdict,
    RegressionCase,
    RetrySemantics,
    RuleDecision,
    RuleOutcome,
    RunManifest,
    RunStatus,
    StageRecord,
    StageStatus,
    TerminationPolicy,
    TerminationReason,
    TurnMode,
    TurnRef,
    TurnState,
    digest_of,
    utcnow,
)
from formal_lab_contracts import capabilities as caps
from formal_lab_contracts.errors import FormalLabError, NonRetryableFailure

from .coordination import Coordinator, GateHook, InMemoryLedger, OperationLedger, SendDecision, request_digest
from .execution_context import build_context, identity_problem
from .participants import ParticipantInput, ParticipantServices
from .registry import PluginRegistry
from .settings import get_setting
from .turns import CycleScheduler, scheduler_for

DEFAULT_VERIFIER = PluginRef(plugin_id="formal-lab.verifier.z3-bmc", version="1.0.0")


# ---------------------------------------------------------------------------- ids / events


def step_id(run_id: str, step: int) -> str:
    return f"{run_id}:s{step}"


def turn_id(run_id: str, step: int, actor_id: str) -> str:
    return f"{run_id}:s{step}:{actor_id}"


def event_key(run_id: str, step: int | None, kind: str, actor_id: str | None = None) -> str:
    if step is None:
        return f"{run_id}:run:{kind}"
    return f"{run_id}:s{step}:{actor_id}:{kind}" if actor_id else f"{run_id}:s{step}:{kind}"


def event_id_for(key: str) -> str:
    return "evt_" + hashlib.sha256(key.encode()).hexdigest()[:24]


@dataclass
class EventDraft:
    key: str
    event_type: EventType
    step: int | None
    payload: dict[str, Any]
    parents: list[str] = field(default_factory=list)  # idempotency keys of parent events
    actor_id: str | None = None
    turn: TurnRef | None = None
    stage: ExecutionStage | None = None

    @property
    def event_id(self) -> str:
        return event_id_for(self.key)

    @property
    def payload_schema(self) -> str:
        return f"formal-lab/events/{self.event_type.value}@2"

    def to_json(self) -> dict[str, Any]:
        return {"key": self.key, "event_type": self.event_type.value, "step": self.step, "payload": self.payload,
                "parents": self.parents, "actor_id": self.actor_id,
                "turn": self.turn.model_dump(mode="json") if self.turn else None,
                "stage": self.stage.value if self.stage else None}

    @classmethod
    def from_json(cls, e: dict[str, Any]) -> EventDraft:
        return cls(e["key"], EventType(e["event_type"]), e["step"], e["payload"], e["parents"], e.get("actor_id"),
                   TurnRef.model_validate(e["turn"]) if e.get("turn") else None,
                   ExecutionStage(e["stage"]) if e.get("stage") else None)


# ---------------------------------------------------------------------------- services / components


class RuntimeServices:
    """PluginServices implementation handed to plugin factories."""

    def __init__(self, package: ModelPackage, packages: dict[str, ModelPackage] | None = None,
                 loaded: Any = None):
        self._package = package
        self._packages = packages or {}
        self._loaded = loaded

    def pinned_model(self) -> ModelPackage:
        return self._package

    def get_model(self, ref) -> ModelPackage:
        if ref.package_id == self._package.package_id and ref.version == self._package.version:
            return self._package
        key = f"{ref.package_id}@{ref.version}"
        if key not in self._packages:
            raise NonRetryableFailure(f"model {key} not available to plugins")
        return self._packages[key]

    def get_setting(self, key: str) -> str | None:
        return get_setting(key)

    def loaded_model(self) -> Any:
        if self._loaded is None:
            raise NonRetryableFailure("no semantic driver loaded for this model")
        return self._loaded


@dataclass
class CarryState:
    """What one step hands to the next besides the environment snapshot (persisted with every step)."""

    turn: TurnState
    checkpoints: dict[str, dict[str, Any]] = field(default_factory=dict)  # actor → PlannerCheckpoint JSON
    last_outcomes: dict[str, dict[str, Any]] = field(default_factory=dict)  # actor → ActionOutcome JSON
    actor_usage: dict[str, dict[str, Any]] = field(default_factory=dict)  # actor → BudgetUsage JSON
    flags: dict[str, dict[str, Any]] = field(default_factory=dict)  # actor → {replan, observe_paths, rejected}
    round_observations: dict[str, dict[str, Any]] = field(default_factory=dict)  # actor → Observation JSON
    last_event_key: str | None = None
    # JOINT_BATCH: the open batch {record: BatchRecord, proposals / turns / observations: actor → JSON}
    batch: dict[str, Any] | None = None

    def to_json(self) -> dict[str, Any]:
        out = {"turn": self.turn.model_dump(mode="json"), "checkpoints": self.checkpoints,
               "last_outcomes": self.last_outcomes, "actor_usage": self.actor_usage, "flags": self.flags,
               "round_observations": self.round_observations, "last_event_key": self.last_event_key}
        if self.batch is not None:  # sequential runs keep the phase-2 carry shape
            out["batch"] = self.batch
        return out

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> CarryState:
        return cls(turn=TurnState.model_validate(data["turn"]), checkpoints=data.get("checkpoints", {}),
                   last_outcomes=data.get("last_outcomes", {}), actor_usage=data.get("actor_usage", {}),
                   flags=data.get("flags", {}), round_observations=data.get("round_observations", {}),
                   last_event_key=data.get("last_event_key"), batch=data.get("batch"))

    def copy(self) -> CarryState:
        return CarryState.from_json(copy.deepcopy(self.to_json()))

    def usage_of(self, actor: str) -> BudgetUsage:
        return BudgetUsage.model_validate(self.actor_usage.get(actor, {}))


def state_families(loaded: Any) -> set[str]:
    """State location families of the loaded model (for projecting participant payloads); empty if unknown."""
    try:
        return {str(k).split("[", 1)[0] for k in loaded.initial_state()}
    except Exception:
        return set()


@dataclass
class RunComponents:
    manifest: RunManifest
    package: ModelPackage
    env: Any
    planners: dict[str, Any]
    verifier: Any
    evaluators: list[Any]
    registry: PluginRegistry
    loaded: Any = None
    driver_ref: PluginRef | None = None
    env_caps: set[str] = field(default_factory=set)
    probes: list[Any] = field(default_factory=list)
    rules: Any = None  # formal_lab_model.rules.RuleEvaluator (IR drivers only)
    scheduler: CycleScheduler | None = None
    termination: TerminationPolicy | None = None
    gates: list[tuple[PluginRef, Any, dict[str, Any]]] = field(default_factory=list)  # (pinned ref, gate, config)
    env_batch_semantics: str | None = None  # env.batch_step params.semantics
    driver_joint_semantics: str | None = None  # driver.joint_predict params.semantics

    def __post_init__(self) -> None:
        self.participants: dict[str, Participant] = {p.actor_id: p for p in self.manifest.participants}
        families = state_families(self.loaded)
        self.inputs: dict[str, ParticipantInput] = {a: ParticipantInput(p, families)
                                                    for a, p in self.participants.items()}
        if self.scheduler is None:
            self.scheduler = scheduler_for(self.manifest.turns, list(self.participants))
        if self.termination is None:
            self.termination = self.manifest.termination or self.manifest.scenario.effective_termination()
        self.specs = self.loaded.action_specs()
        self._kinds = self.loaded.property_kinds()

    @property
    def run_id(self) -> str:
        return self.manifest.run_id

    @property
    def actor_id(self) -> str:  # phase-1 compatibility: the first participant
        return self.manifest.participants[0].actor_id

    @property
    def pure(self) -> bool:
        return caps.ENV_PURE_REPLAYABLE in self.env_caps or caps.ENV_SNAPSHOT_RESTORE in self.env_caps

    @property
    def is_ir(self) -> bool:
        return hasattr(self.loaded, "checked")

    @property
    def joint(self) -> bool:
        return str(self.manifest.turns.mode) == TurnMode.JOINT_BATCH.value

    @property
    def joint_prediction(self) -> bool:
        """Effects of a batch are compared against a joint prediction only when the driver gives simultaneous
        actions the same meaning the environment applies them with."""
        return self.env_batch_semantics is not None and self.env_batch_semantics == self.driver_joint_semantics


def plugin_ref_for(manifest: RunManifest, role: str) -> PluginRef | None:
    for pin in manifest.plugins:
        if pin.role == role:
            return PluginRef(plugin_id=pin.plugin_id, version=pin.version)
    return None


def driver_ref_for(manifest: RunManifest, package: ModelPackage, registry: PluginRegistry) -> PluginRef:
    pinned = plugin_ref_for(manifest, "driver") or manifest.scenario.driver
    if pinned is not None:
        return pinned
    return registry.driver_for(package.semantic_profile).descriptor.ref()


def open_components(manifest: RunManifest, package: ModelPackage, registry: PluginRegistry, *,
                    rulesets: dict[str, Any] | None = None) -> RunComponents:
    if package.digest != manifest.model.digest:
        raise NonRetryableFailure("model package digest differs from the run manifest (version drift)")
    driver_ref = driver_ref_for(manifest, package, registry)
    driver = registry.create(driver_ref, {}, RuntimeServices(package), expect=PluginInterface.SEMANTIC_DRIVER)
    driver_entry = registry.resolve(driver_ref)
    loaded = driver.load(package)
    services = RuntimeServices(package, loaded=loaded)
    scenario = manifest.scenario
    # the worker re-validates every configuration against the pinned plugin's schema — the same check the API runs
    # when a scenario is saved (P2-017): a plugin upgraded since then cannot silently accept a stale config
    registry.validate_config(scenario.environment.plugin, scenario.environment.config, path="/environment/config")
    for p in manifest.participants:
        registry.validate_config(p.strategy.plugin, p.strategy.config, path=f"/participants/{p.actor_id}/config")
    env_entry = registry.resolve(scenario.environment.plugin)
    env = registry.create(scenario.environment.plugin, scenario.environment.config, services,
                          expect=PluginInterface.ENVIRONMENT)
    env_caps = {c.id for c in env_entry.descriptor.capabilities}
    planners = {  # phase 3A: each planner gets its participant's services (own settings first)
        p.actor_id: registry.create(p.strategy.plugin, p.strategy.config, ParticipantServices(services, p),
                                    expect=PluginInterface.PLANNER)
        for p in manifest.participants
    }
    verifier_ref = plugin_ref_for(manifest, "verifier") or DEFAULT_VERIFIER
    verifier = registry.create(verifier_ref, manifest.config.get("verifier_config", {}), services,
                               expect=PluginInterface.VERIFIER)
    evaluators = [
        registry.create(PluginRef(plugin_id=pin.plugin_id, version=pin.version), {}, services,
                        expect=PluginInterface.EVALUATOR)
        for pin in manifest.plugins if pin.role.startswith("evaluator")
    ]
    probes = [
        registry.create(PluginRef(plugin_id=pin.plugin_id, version=pin.version),
                        manifest.config.get("probe_config", {}).get(pin.plugin_id, {}), services,
                        expect=PluginInterface.PROBE)
        for pin in manifest.plugins if pin.role.startswith("probe")
    ]
    gates = []
    for i, spec in enumerate(scenario.execution_gates):  # phase 3A: pinned versions, config re-validated
        pinned = plugin_ref_for(manifest, f"gate:{i}") or spec.plugin
        registry.validate_config(pinned, spec.config, path=f"/execution_gates/{i}/config")
        gates.append((pinned, registry.create(pinned, spec.config, services, expect=PluginInterface.EXECUTION_GATE),
                      dict(spec.config)))
    rules = None
    if manifest.rules is not None and manifest.config.get("rules_enabled", True):
        ruleset = (rulesets or {}).get(manifest.rules.digest.value)
        if ruleset is None:
            raise NonRetryableFailure(f"rule set {manifest.rules.ruleset_id}@{manifest.rules.version} is not "
                                      "available to this runner")
        if not driver_entry.descriptor.has_capability(caps.DRIVER_IR):  # negotiation refuses this before a run
            raise NonRetryableFailure(f"rules need {caps.DRIVER_IR}; {driver_ref.plugin_id} does not declare it")
        from formal_lab_model.rules import RuleEvaluator

        rules = RuleEvaluator(ruleset, loaded.checked, loaded.interp)
    semantics = {c.id: c.params.get("semantics") for c in [*env_entry.descriptor.capabilities,
                                                           *driver_entry.descriptor.capabilities]
                 if c.id in (caps.ENV_BATCH_STEP, caps.DRIVER_JOINT_PREDICT)}
    if str(manifest.turns.mode) == TurnMode.JOINT_BATCH.value and not (caps.ENV_BATCH_STEP in env_caps
                                                             and hasattr(env, "step_batch")):
        raise NonRetryableFailure(f"JOINT_BATCH needs {caps.ENV_BATCH_STEP}; {scenario.environment.plugin.plugin_id} "
                                  "does not declare it")
    return RunComponents(manifest, package, env, planners, verifier, evaluators, registry, loaded=loaded,
                         driver_ref=driver_ref, env_caps=env_caps, probes=probes, rules=rules, gates=gates,
                         env_batch_semantics=semantics.get(caps.ENV_BATCH_STEP),
                         driver_joint_semantics=semantics.get(caps.DRIVER_JOINT_PREDICT))


# ---------------------------------------------------------------------------- helpers


def _digest(obj: Any) -> str:
    return digest_of(obj).value


def _stage(stage: ExecutionStage, status: StageStatus, retry: RetrySemantics, t0: float, *, inp: Any = None,
           out: Any = None, note: str | None = None, error: FormalLabError | None = None) -> StageRecord:
    return StageRecord(stage=stage, status=status, retry=retry,
                       input_digest=_digest(inp) if inp is not None else None,
                       output_digest=_digest(out) if out is not None else None,
                       elapsed_ms=round((time.perf_counter() - t0) * 1000, 3), note=note,
                       error=error.to_info() if error is not None else None)


def goal_of(rc: RunComponents, actor_id: str | None = None) -> str | None:
    if actor_id is not None:
        goal = rc.participants[actor_id].goal
        if goal:
            return goal
    if rc.termination.joint_goal:
        return rc.termination.joint_goal
    for obj in rc.manifest.scenario.objectives:
        if obj.property_id:
            return obj.property_id
    return None


def budget_exhausted(budget: Budget, usage: BudgetUsage, dims: list[str]) -> str | None:
    if budget.max_steps is not None and usage.steps >= budget.max_steps:
        return f"step budget exhausted ({usage.steps}/{budget.max_steps})"
    if budget.max_wall_seconds is not None and usage.wall_seconds >= budget.max_wall_seconds:
        return f"wall-clock budget exhausted ({usage.wall_seconds:.1f}s/{budget.max_wall_seconds}s)"
    if "model_calls" in dims and budget.max_model_calls is not None and usage.model_calls >= budget.max_model_calls:
        return f"model-call budget exhausted ({usage.model_calls}/{budget.max_model_calls})"
    if "tokens" in dims and budget.max_tokens is not None and usage.tokens >= budget.max_tokens:
        return f"token budget exhausted ({usage.tokens}/{budget.max_tokens})"
    return None


def add_usage(usage: BudgetUsage, delta: ModelUsage, *, steps: int = 0) -> BudgetUsage:
    return usage.model_copy(update={
        "steps": usage.steps + steps,
        "model_calls": usage.model_calls + delta.model_calls,
        "model_attempts": usage.model_attempts + (delta.attempts or delta.model_calls),
        "input_tokens": usage.input_tokens + delta.input_tokens,
        "output_tokens": usage.output_tokens + delta.output_tokens,
        "unreported_calls": usage.unreported_calls + delta.unreported_calls,
        "unconfirmed_calls": usage.unconfirmed_calls + delta.unconfirmed_calls,
    })


STATUS_FOR = {
    TerminationReason.JOINT_GOAL_REACHED: RunStatus.SUCCEEDED,
    TerminationReason.ACTOR_GOAL_REACHED: RunStatus.SUCCEEDED,
    TerminationReason.ALL_ACTOR_GOALS_REACHED: RunStatus.SUCCEEDED,
    TerminationReason.INVARIANT_VIOLATED: RunStatus.FAILED,
    TerminationReason.NO_APPLICABLE_ACTION: RunStatus.FAILED,
    TerminationReason.NO_PROGRESS: RunStatus.FAILED,
    TerminationReason.BUDGET_EXHAUSTED: RunStatus.BUDGET_EXHAUSTED,
    TerminationReason.ACTOR_BUDGETS_EXHAUSTED: RunStatus.BUDGET_EXHAUSTED,
    TerminationReason.CANCELLED: RunStatus.CANCELLED,
    TerminationReason.FAILED: RunStatus.FAILED,
    TerminationReason.OPERATION_UNRESOLVED: RunStatus.FAILED,
}


def partial_checker(rc: RunComponents):
    """Applicability over all completions of the free locations, decided by the run's verifier."""

    def check(action, state, free):
        res = rc.verifier.check(
            rc.package,
            CheckQuery(kind="ACTION_PRECONDITION", action=action, initial_state="GIVEN_STATE",
                       bound={"max_steps": 0, "timeout_ms": 5000}),
            state=state, unknown_paths=free,
        )
        verdict = PreconditionVerdict(str(res.verdict)) if str(res.verdict) in PreconditionVerdict.__members__ \
            else PreconditionVerdict.UNKNOWN
        return verdict, res.observation_request

    return check


# ---------------------------------------------------------------------------- start


@dataclass
class StartResult:
    observation: Observation
    snapshot: EnvironmentSnapshot
    initial_check: BoundedCheckResult | None
    events: list[EventDraft]
    carry: CarryState


def start_run(rc: RunComponents) -> StartResult:
    m = rc.manifest
    first = m.participants[0].actor_id
    obs = rc.env.reset(m.scenario, rc.package, run_id=m.run_id, seed=m.seed)
    events = [
        EventDraft(event_key(m.run_id, None, "started"), EventType.RUN_STARTED, 0,
                   {"manifest_digest": _digest(m.model_dump(mode="json")), "seed": m.seed,
                    "budget": m.budget.model_dump(exclude_none=True),
                    "budget_dimensions": m.config.get("budget_dimensions", []),
                    "participants": [p.actor_id for p in m.participants],
                    "turns": m.turns.model_dump(mode="json"),
                    "termination": rc.termination.model_dump(mode="json"),
                    "driver": rc.driver_ref.model_dump() if rc.driver_ref else None,
                    "environment_capabilities": sorted(rc.env_caps)},
                   [event_key(m.run_id, None, "queued")]),
    ]
    if hasattr(rc.env, "session") and caps.ENV_PERSISTENT_SESSION in rc.env_caps:
        session = rc.env.session()
        events.append(EventDraft(event_key(m.run_id, 0, "session"), EventType.SESSION_STATE, 0,
                                 {"session": session.model_dump(mode="json")}, [event_key(m.run_id, None, "started")],
                                 stage=ExecutionStage.OBSERVE))
    events.append(EventDraft(event_key(m.run_id, 0, "observation"), EventType.OBSERVATION, 0,
                             {"observation": obs.model_dump(mode="json")}, [event_key(m.run_id, None, "started")],
                             first, stage=ExecutionStage.OBSERVE))
    check = None
    horizon = int(m.config.get("initial_check_horizon", 16))
    goal = goal_of(rc)
    if goal and horizon > 0 and rc.is_ir:
        belief = rc.loaded.belief(obs)
        check = rc.verifier.check(
            rc.package,
            CheckQuery(kind="GOAL_REACHABILITY", property_id=goal, initial_state="GIVEN_STATE",
                       bound={"max_steps": horizon, "timeout_ms": int(m.config.get("check_timeout_ms", 20000))}),
            state=belief.state,
        )
        events.append(EventDraft(event_key(m.run_id, 0, "initial-check"), EventType.CHECK_COMPLETED, 0,
                                 {"purpose": "initial goal reachability from the first participant's belief",
                                  "result": check.model_dump(mode="json")},
                                 [event_key(m.run_id, 0, "observation")], stage=ExecutionStage.CHECK))
    snap = rc.env.snapshot()
    events.append(EventDraft(event_key(m.run_id, 0, "snapshot"), EventType.STATE_SNAPSHOT, 0,
                             {"snapshot_digest": snap.digest.value, "state_revision": snap.state_revision,
                              "kind": snap.kind},
                             [event_key(m.run_id, 0, "observation")]))
    carry = CarryState(turn=CycleScheduler.initial_state(), last_event_key=event_key(m.run_id, 0, "snapshot"))
    for actor, planner in rc.planners.items():
        cp = planner.checkpoint() if hasattr(planner, "checkpoint") else None
        if cp is not None:
            carry.checkpoints[actor] = cp.model_dump(mode="json")
    return StartResult(obs, snap, check, events, carry)


# ---------------------------------------------------------------------------- plan


@dataclass
class PlanPhase:
    """Everything decided before touching the environment. Persisted as the step's `propose` operation so a
    retried activity reuses it (no second model call, no double-counted tokens)."""

    step: int
    turn: TurnRef | None = None
    observation: Observation | None = None
    candidates: list[CandidateAction] = field(default_factory=list)
    proposal: ActionProposal | None = None
    usage_delta: ModelUsage = field(default_factory=ModelUsage)
    model_calls: list[dict[str, Any]] = field(default_factory=list)
    events: list[EventDraft] = field(default_factory=list)
    terminal: RunStatus | None = None
    terminal_reason: str | None = None
    termination_reason: TerminationReason | None = None
    skipped: str | None = None  # the actor passed its turn (reason)
    retired: list[str] = field(default_factory=list)  # actors retired before this turn (budget)
    round_observations: dict[str, dict[str, Any]] = field(default_factory=dict)
    checkpoint: dict[str, Any] | None = None
    stages: list[StageRecord] = field(default_factory=list)
    observation_requests: int = 0
    last_request: dict[str, Any] | None = None  # {paths digest, revision} of the request served this turn
    elapsed_s: float = 0.0
    batch_open: dict[str, Any] | None = None  # JOINT_BATCH: the BatchRecord this step opened
    proposed_at: str | None = None  # JOINT_BATCH: wall time the proposal was ready (batch deadline)
    input_digest: str | None = None  # digest of the observation the planner finally received

    def to_json(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "turn": self.turn.model_dump(mode="json") if self.turn else None,
            "observation": self.observation.model_dump(mode="json") if self.observation else None,
            "candidates": [c.model_dump(mode="json") for c in self.candidates],
            "proposal": self.proposal.model_dump(mode="json") if self.proposal else None,
            "usage_delta": self.usage_delta.model_dump(),
            "model_calls": self.model_calls,
            "events": [e.to_json() for e in self.events],
            "terminal": self.terminal.value if self.terminal else None,
            "terminal_reason": self.terminal_reason,
            "termination_reason": self.termination_reason.value if self.termination_reason else None,
            "skipped": self.skipped,
            "retired": self.retired,
            "round_observations": self.round_observations,
            "checkpoint": self.checkpoint,
            "stages": [s.model_dump(mode="json") for s in self.stages],
            "observation_requests": self.observation_requests,
            "last_request": self.last_request,
            "elapsed_s": self.elapsed_s,
            **({"batch_open": self.batch_open} if self.batch_open is not None else {}),
            **({"proposed_at": self.proposed_at} if self.proposed_at is not None else {}),
            **({"input_digest": self.input_digest} if self.input_digest is not None else {}),
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> PlanPhase:
        return cls(
            step=data["step"],
            turn=TurnRef.model_validate(data["turn"]) if data.get("turn") else None,
            observation=Observation.model_validate(data["observation"]) if data["observation"] else None,
            candidates=[CandidateAction.model_validate(c) for c in data["candidates"]],
            proposal=ActionProposal.model_validate(data["proposal"]) if data["proposal"] else None,
            usage_delta=ModelUsage.model_validate(data["usage_delta"]),
            model_calls=data["model_calls"],
            events=[EventDraft.from_json(e) for e in data["events"]],
            terminal=RunStatus(data["terminal"]) if data["terminal"] else None,
            terminal_reason=data["terminal_reason"],
            termination_reason=TerminationReason(data["termination_reason"]) if data.get("termination_reason")
            else None,
            skipped=data.get("skipped"),
            retired=data.get("retired", []),
            round_observations=data.get("round_observations", {}),
            checkpoint=data.get("checkpoint"),
            stages=[StageRecord.model_validate(s) for s in data.get("stages", [])],
            observation_requests=data.get("observation_requests", 0),
            last_request=data.get("last_request"),
            elapsed_s=data.get("elapsed_s", 0.0),
            batch_open=data.get("batch_open"),
            proposed_at=data.get("proposed_at"),
            input_digest=data.get("input_digest"),
        )


def _terminal(plan: PlanPhase, reason: TerminationReason, text: str, status: RunStatus | None = None) -> PlanPhase:
    plan.terminal, plan.terminal_reason, plan.termination_reason = status or STATUS_FOR[reason], text, reason
    return plan


def _restore(rc: RunComponents, snapshot: EnvironmentSnapshot) -> None:
    """Pure-data environments restart from the stored pre-step snapshot; a live session is never rolled back."""
    if snapshot.kind == "FULL_STATE":
        rc.env.restore(snapshot)
    elif hasattr(rc.env, "attach"):
        rc.env.attach(snapshot)


def _belief_summary(belief: BeliefState) -> dict[str, Any]:
    counts = dict(belief.assumptions.counts)
    return {"unknown_paths": belief.free_paths,
            "stale_paths": [p for p, v in belief.provenance.items() if v.value == "STALE"],
            "provenance_counts": counts, "assumptions_digest": belief.assumptions.digest.value,
            "world_revision": belief.world_revision}


def _rule_context(obs: Observation | None, belief: BeliefState | None, *, verdict: str = "NONE",
                  outcome: str = "NONE", different: int = 0, step: int = 0, rejected: int = 0) -> dict[str, Any]:
    stale = sum(1 for v in (belief.provenance.values() if belief else []) if v.value == "STALE")
    return {"ev_verdict": verdict, "ev_outcome": outcome, "ev_unknown_count": len(obs.unknowns) if obs else 0,
            "ev_stale_count": stale, "ev_different_count": different, "ev_step": step,
            "ev_rejected_streak": rejected}


def _apply_rules(rc: RunComponents, event_type: str, belief: BeliefState, ctx: dict[str, Any]) -> RuleDecision | None:
    if rc.manifest.rules is None or not rc.manifest.config.get("rules_enabled", True):
        return None
    if rc.rules is None:  # non-IR driver: rules cannot be evaluated here
        return None
    return rc.rules.decide(event_type, belief.state, belief.free_paths, ctx)


def plan_step(rc: RunComponents, snapshot: EnvironmentSnapshot, step: int, usage: BudgetUsage,
              carry: CarryState) -> PlanPhase:
    """TURN, OBSERVE and PROPOSE for global step `step` (the state after step-1 is `snapshot` + `carry`)."""
    t_all = time.perf_counter()
    m = rc.manifest
    run_id = m.run_id
    plan = PlanPhase(step=step)
    dims = list(m.config.get("budget_dimensions", ["steps", "wall_seconds"]))
    reason = budget_exhausted(m.budget, usage, dims)
    if reason:
        return _terminal(plan, TerminationReason.BUDGET_EXHAUSTED, reason)

    # ---- TURN: retire actors whose own budget is spent, then ask the scheduler
    t0 = time.perf_counter()
    state = carry.turn
    parent = carry.last_event_key or event_key(run_id, 0, "snapshot")
    while True:
        turn = rc.scheduler.next_turn(state)
        if turn is None:
            return _terminal(plan, TerminationReason.ACTOR_BUDGETS_EXHAUSTED,
                             "every participant is retired (own budget exhausted)")
        p = rc.participants[turn.actor_id]
        spent = budget_exhausted(p.budget, carry.usage_of(turn.actor_id), dims) if p.budget else None
        if not spent:
            break
        state = rc.scheduler.retire(state, turn.actor_id)
        plan.retired.append(turn.actor_id)
        plan.events.append(EventDraft(event_key(run_id, step, f"retired-{turn.actor_id}"), EventType.TURN_SKIPPED,
                                      step, {"actor_id": turn.actor_id, "reason": f"participant budget: {spent}",
                                             "retired": True}, [parent], turn.actor_id, turn, ExecutionStage.TURN))
    if rc.joint:
        turn = turn.model_copy(update={"batch_id": f"{run_id}:b{turn.round}"})
    plan.turn = turn
    actor = turn.actor_id
    tkey = lambda kind: event_key(run_id, step, kind, actor)  # noqa: E731
    open_batch = (carry.batch or {}).get("record")
    if rc.joint and open_batch is not None and open_batch["status"] == "OPEN" and open_batch["round"] != turn.round:
        raise NonRetryableFailure(f"batch {open_batch['batch_id']} of round {open_batch['round']} was never "
                                  f"submitted, and step {step} is in round {turn.round}")
    if rc.joint and rc.scheduler.round_starts(state, turn):
        record = BatchRecord(batch_id=turn.batch_id, run_id=run_id, round=turn.round, status="OPEN",
                             expected=list(rc.scheduler.participants), opened_at_step=step, opened_at=utcnow(),
                             semantics=rc.env_batch_semantics, joint_prediction=rc.joint_prediction)
        plan.batch_open = record.model_dump(mode="json")
        plan.events.append(EventDraft(tkey("batch-opened"), EventType.BATCH_OPENED, step,
                                      {"batch": plan.batch_open}, [parent], actor, turn, ExecutionStage.TURN))
        parent = tkey("batch-opened")
    plan.events.append(EventDraft(tkey("turn"), EventType.TURN_STARTED, step,
                                  {"turn": turn.model_dump(mode="json"), "cycle": rc.scheduler.cycle,
                                   "active": rc.scheduler.active(state), "retired": state.retired,
                                   "timing": m.turns.observation_timing.value},
                                  [parent], actor, turn, ExecutionStage.TURN))
    plan.stages.append(_stage(ExecutionStage.TURN, StageStatus.OK, RetrySemantics.IDEMPOTENT, t0,
                              inp=state.model_dump(mode="json"), out=turn.model_dump(mode="json")))

    # ---- OBSERVE (turn start, or the actor's round-start observation)
    t0 = time.perf_counter()
    _restore(rc, snapshot)
    if m.turns.observation_timing.value == "ROUND_START":
        if rc.scheduler.round_starts(state, turn) or actor not in carry.round_observations:
            plan.round_observations = {a: rc.env.observe(a).model_copy(update={
                "timing": ObservationTiming.ROUND_START}).model_dump(mode="json") for a in rc.scheduler.active(state)}
        source = plan.round_observations or carry.round_observations
        obs = Observation.model_validate(source[actor]).model_copy(update={"turn": turn})
    else:
        obs = rc.env.observe(actor).model_copy(update={"turn": turn})
    flags = carry.flags.get(actor, {})
    requested = list(flags.get("observe_paths", []))
    plan.observation = obs
    belief = rc.loaded.belief(obs)
    inp = rc.inputs[actor]
    payload: dict[str, Any] = {"observation": obs.model_dump(mode="json"), "belief": _belief_summary(belief)}
    if inp.filtered:
        pobs, withheld = inp.observation(obs)
        payload["planner_input"] = {"withheld": withheld, "digest": inp.digest(pobs),
                                    "view": inp.view.model_dump(mode="json") if inp.view else None}
    plan.events.append(EventDraft(tkey("observation"), EventType.OBSERVATION, step, payload,
                                  [tkey("turn")], actor, turn, ExecutionStage.OBSERVE))
    decision = _apply_rules(rc, "OBSERVATION", belief, _rule_context(obs, belief, step=step,
                                                                    rejected=flags.get("rejected", 0)))
    if decision is not None:
        plan.events.append(EventDraft(tkey("rules-observation"), EventType.RULE_EVALUATED, step,
                                      {"decision": decision.model_dump(mode="json")}, [tkey("observation")], actor,
                                      turn, ExecutionStage.CHECK))
        if decision.outcome is RuleOutcome.OBSERVE_MORE and decision.winner:
            winner = next(r for r in rc.rules.ruleset.rules if r.rule_id == decision.winner)
            requested += [p for p in winner.observe_paths if p not in requested]
    can_request = caps.ENV_OBSERVE_ON_REQUEST in rc.env_caps and hasattr(rc.env, "observe_paths")
    if requested and can_request:
        obs, belief = _observe_more(rc, plan, step, turn, requested, "rule / carried request", tkey("observation"))
    plan.stages.append(_stage(ExecutionStage.OBSERVE, StageStatus.OK, RetrySemantics.IDEMPOTENT, t0,
                              inp=snapshot.digest.value, out=obs.model_dump(mode="json"),
                              note=f"{len(obs.facts)} facts, {len(obs.unknowns)} unknown; "
                                   f"assumptions {belief.assumptions.counts}"))

    # ---- candidates (on what the planner receives: withheld locations count as never observed)
    t0 = time.perf_counter()
    participant = rc.participants[actor]
    pobs, _ = inp.observation(obs)
    pbelief = rc.loaded.belief(pobs) if pobs is not obs else belief
    plan.candidates = rc.loaded.candidates(pbelief, scope=participant.scope, partial_checker=partial_checker(rc))
    counts = {v.value: sum(c.belief_applicability == v for c in plan.candidates) for v in PreconditionVerdict}
    plan.events.append(EventDraft(tkey("candidates"), EventType.CANDIDATES, step,
                                  {"candidates": [c.model_dump(mode="json") for c in plan.candidates],
                                   "counts": counts, "scope": participant.scope.model_dump(mode="json")
                                   if participant.scope else None},
                                  [tkey("observation")], actor, turn, ExecutionStage.PROPOSE))
    viable = [c for c in plan.candidates if c.belief_applicability in (PreconditionVerdict.APPLICABLE,
                                                                       PreconditionVerdict.UNKNOWN)]
    if not viable:
        policy = rc.termination.on_no_action
        text = f"no applicable action for {actor} on its belief"
        if policy is NoActionPolicy.SKIP_ACTOR:
            plan.skipped = text
        elif policy is NoActionPolicy.FAIL:
            _terminal(plan, TerminationReason.NO_APPLICABLE_ACTION, text)
        else:
            goal = rc.termination.joint_goal
            holds = bool(goal) and rc.loaded.properties(belief.state).get(goal, False)  # kernel: full belief
            _terminal(plan, TerminationReason.NO_APPLICABLE_ACTION, text,
                      RunStatus.SUCCEEDED if holds else RunStatus.FAILED)
        plan.elapsed_s = time.perf_counter() - t_all
        return plan

    # ---- PROPOSE (planner state restored from the carried checkpoint first: resume = uninterrupted)
    planner = rc.planners[actor]
    cp_json = carry.checkpoints.get(actor)
    if cp_json is not None and hasattr(planner, "restore"):
        planner.restore(PlannerCheckpoint.model_validate(cp_json))
    previous_plan = (cp_json or {}).get("plan") or {}
    proposal = _propose(rc, plan, step, turn, pobs, pbelief, usage, carry)
    if proposal.observation_request is not None and can_request and plan.observation_requests == 0:
        request = proposal.observation_request
        served, declined = inp.request(request.paths)
        seen = {"paths": _digest(sorted(request.paths)), "revision": obs.state_revision, "step": step}
        previous = carry.flags.get(actor, {}).get("last_request")
        first = plan.usage_delta
        if declined and not served:  # phase 3A: locations outside the participant's view are never served
            plan.events.append(EventDraft(
                event_key(rc.run_id, step, "observe-more-withheld", actor), EventType.OBSERVATION_REQUESTED, step,
                {"paths": request.paths, "reason": f"strategy: {request.reason}", "served": False,
                 "declined": f"outside the participant's view: {declined}"},
                [tkey("candidates")], actor, turn, ExecutionStage.OBSERVE))
        elif previous and previous["paths"] == seen["paths"] and previous["revision"] == obs.state_revision:
            # P2-047: the same locations were already re-observed and nothing has changed since — answering again
            # would repeat the same facts; the strategy decides without it and the refusal is on the record
            plan.events.append(EventDraft(
                event_key(rc.run_id, step, "observe-more-repeated", actor), EventType.OBSERVATION_REQUESTED, step,
                {"paths": request.paths, "reason": f"strategy: {request.reason}", "served": False,
                 "declined": f"repeated request: the same locations were re-observed at step {previous['step']} "
                             f"and the world revision is unchanged ({obs.state_revision})"},
                [tkey("candidates")], actor, turn, ExecutionStage.OBSERVE))
        else:
            why = f"strategy: {request.reason}" + (f" (withheld by the view: {declined})" if declined else "")
            obs, belief = _observe_more(rc, plan, step, turn, served, why, tkey("candidates"))
            plan.last_request = seen
            pobs, _ = inp.observation(obs)
            pbelief = rc.loaded.belief(pobs) if pobs is not obs else belief
            plan.candidates = rc.loaded.candidates(pbelief, scope=participant.scope,
                                                   partial_checker=partial_checker(rc))
        proposal = _propose(rc, plan, step, turn, pobs, pbelief, usage, carry, allow_request=False)
        plan.usage_delta = _sum_usage(first, plan.usage_delta)
    plan.proposal = proposal
    plan.observation = obs
    proposed: dict[str, Any] = {"proposal": proposal.model_dump(mode="json"),
                                "model_call_ids": proposal.source.model_call_ids}
    if inp.filtered:
        plan.input_digest = inp.digest(pobs)
        proposed["planner_input_digest"] = plan.input_digest
    if rc.joint:
        plan.proposed_at = utcnow().isoformat()
    plan.events.append(EventDraft(tkey("proposal"), EventType.ACTION_PROPOSED, step, proposed,
                                  [tkey("candidates")], actor, turn, ExecutionStage.PROPOSE))
    cp = planner.checkpoint() if hasattr(planner, "checkpoint") else None
    if cp is not None:
        plan.checkpoint = cp.model_dump(mode="json")
        plan.events.append(EventDraft(tkey("checkpoint"), EventType.PLANNER_CHECKPOINT, step,
                                      {"actor_id": actor, "digest": _digest(plan.checkpoint),
                                       "plan_version": (cp.plan.version if cp.plan else None),
                                       "progress": cp.plan.progress() if cp.plan else cp.progress},
                                      [tkey("proposal")], actor, turn, ExecutionStage.PROPOSE))
        if cp.plan is not None and (cp.plan.plan_id, cp.plan.version) != (previous_plan.get("plan_id"),
                                                                          previous_plan.get("version")):
            plan.events.append(EventDraft(tkey("plan"), EventType.PLAN_UPDATED, step,
                                          {"plan": cp.plan.model_dump(mode="json"),
                                           "previous_version": previous_plan.get("version")},
                                          [tkey("proposal")], actor, turn, ExecutionStage.PROPOSE))
    plan.stages.append(_stage(ExecutionStage.PROPOSE, StageStatus.OK, RetrySemantics.RECONCILE_THEN_RETRY, t0,
                              inp=[c.model_dump(mode="json") for c in plan.candidates],
                              out=proposal.model_dump(mode="json"),
                              note=f"{proposal.source.kind.value}: {proposal.action.action_type}"))
    plan.elapsed_s = time.perf_counter() - t_all
    return plan


def _sum_usage(a: ModelUsage, b: ModelUsage) -> ModelUsage:
    return ModelUsage(**{k: getattr(a, k) + getattr(b, k) for k in ModelUsage.model_fields})


def _observe_more(rc: RunComponents, plan: PlanPhase, step: int, turn: TurnRef, paths: list[str], why: str,
                  parent: str) -> tuple[Observation, BeliefState]:
    obs = rc.env.observe_paths(turn.actor_id, paths).model_copy(update={"turn": turn})
    plan.observation_requests += 1
    belief = rc.loaded.belief(obs)
    key = event_key(rc.run_id, step, f"observe-more-{plan.observation_requests}", turn.actor_id)
    plan.events.append(EventDraft(key, EventType.OBSERVATION_REQUESTED, step,
                                  {"paths": paths, "reason": why, "observation": obs.model_dump(mode="json"),
                                   "belief": _belief_summary(belief)},
                                  [parent], turn.actor_id, turn, ExecutionStage.OBSERVE))
    plan.observation = obs
    return obs, belief


def _propose(rc: RunComponents, plan: PlanPhase, step: int, turn: TurnRef, obs: Observation, belief: BeliefState,
             usage: BudgetUsage, carry: CarryState, *, allow_request: bool = True) -> ActionProposal:
    m = rc.manifest
    actor = turn.actor_id
    participant = rc.participants[actor]
    last = rc.inputs[actor].outcome(carry.last_outcomes.get(actor))
    flags = carry.flags.get(actor, {})
    can_request = allow_request and caps.ENV_OBSERVE_ON_REQUEST in rc.env_caps and hasattr(rc.env, "observe_paths")
    context = PlanningContext(
        run_id=m.run_id, step=step, step_id=step_id(m.run_id, step), actor_id=actor, observation=obs,
        action_specs=rc.specs, candidates=plan.candidates, model=m.model, budget=m.budget, usage=usage, seed=m.seed,
        turn=turn, goal=goal_of(rc, actor), objective=m.objective, actor_budget=participant.budget,
        actor_usage=carry.usage_of(actor), participants=list(rc.scheduler.cycle),
        observation_request_allowed=can_request, assumptions=belief.assumptions,
        last_outcome=last,
        replan_requested=flags.get("replan"),
    )
    planner = rc.planners[actor]
    proposal = planner.propose(context)
    # model call records of this proposal (all attempts incl. transport / format failures when the strategy
    # keeps them; older strategies expose only the successful responses)
    # (phase 4A: every record names the participant and step it was made for)
    records = getattr(planner, "call_records", None)
    who = {"actor_id": actor, "step": step}
    if records is not None:
        plan.model_calls.extend({**r, **who} for r in records)
    else:
        for call in getattr(planner, "last_calls", []) or []:
            plan.model_calls.append({"call_id": call.call_id, "model": call.model, "request": call.request,
                                     "response": call.raw_text, "input_tokens": call.input_tokens,
                                     "output_tokens": call.output_tokens, "latency_ms": call.latency_ms,
                                     "usage_reported": getattr(call, "usage_reported", True), "outcome": "OK", **who})
    ids = {"proposal_id": f"{turn_id(m.run_id, step, actor)}:proposal", "turn": turn}
    if proposal.assumptions is None:
        from formal_lab_contracts import AssumptionSetRef, PlanBasis

        basis = PlanBasis.FULLY_OBSERVED if all(v.value == "KNOWN" for v in belief.provenance.values()) \
            else PlanBasis.ASSUMPTION_BASED
        ids["assumptions"] = AssumptionSetRef(digest=belief.assumptions.digest, count=len(belief.assumptions.items),
                                              basis=basis, counts={k: v for k, v in belief.assumptions.counts.items()
                                                                   if k != "KNOWN"})
    proposal = proposal.model_copy(update=ids)
    plan.usage_delta = proposal.usage
    return proposal


# ---------------------------------------------------------------------------- apply


@dataclass
class StepExecution:
    step: int
    turn: TurnRef | None = None
    observation: Observation | None = None
    candidates: list[CandidateAction] = field(default_factory=list)
    proposal: ActionProposal | None = None
    precheck: BoundedCheckResult | None = None
    outcome: ActionOutcome | None = None
    comparison: EffectComparison | None = None
    snapshot: EnvironmentSnapshot | None = None
    usage_delta: ModelUsage = field(default_factory=ModelUsage)
    terminal: RunStatus | None = None
    terminal_reason: str | None = None
    termination_reason: TerminationReason | None = None
    events: list[EventDraft] = field(default_factory=list)
    model_calls: list[dict[str, Any]] = field(default_factory=list)
    properties: dict[str, bool] = field(default_factory=dict)
    carry: CarryState | None = None
    operation: OperationRecord | None = None
    stages: list[StageRecord] = field(default_factory=list)
    probes: list[Any] = field(default_factory=list)
    pause_requested: str | None = None
    regression_case: RegressionCase | None = None
    acted: bool = False
    elapsed_s: float = 0.0
    batch_outcomes: dict[int, ActionOutcome] = field(default_factory=dict)  # JOINT_BATCH: earlier members' steps
    batch: BatchRecord | None = None  # JOINT_BATCH: the batch submitted at this step


def _merge_plan_into_carry(carry: CarryState, plan: PlanPhase) -> CarryState:
    new = carry.copy()
    for actor in plan.retired:
        new.turn = CycleScheduler.retire(new.turn, actor)
    if plan.round_observations:
        new.round_observations = dict(plan.round_observations)
    if plan.batch_open is not None:
        new.batch = {"record": plan.batch_open, "proposals": {}, "turns": {}, "observations": {}}
    if plan.turn is not None:
        actor = plan.turn.actor_id
        if plan.checkpoint is not None:
            new.checkpoints[actor] = plan.checkpoint
        flags = dict(new.flags.get(actor, {}))
        flags.pop("observe_paths", None)
        flags.pop("replan", None)
        if plan.last_request is not None:
            flags["last_request"] = plan.last_request
        new.flags[actor] = flags
    return new


def _gate_values(rc: RunComponents, actor: str, paths: list[str]) -> tuple[dict[str, Any], str, int | None]:
    """The locations a gate asked for, read right before the send: fresh when the environment answers observation
    requests, else from the actor's current observation (stale / unknown values are left out)."""
    if not paths:
        return {}, "NONE", None
    if caps.ENV_OBSERVE_ON_REQUEST in rc.env_caps and hasattr(rc.env, "observe_paths"):
        obs, source = rc.env.observe_paths(actor, list(paths)), "FRESH"
    else:
        obs, source = rc.env.observe(actor), "OBSERVATION"
    wanted = set(paths)
    return {f.path: f.value for f in obs.facts if f.path in wanted}, source, obs.state_revision


KERNEL_BASIS = PluginRef(plugin_id="formal-lab.kernel.execution-basis", version="1.0.0")


def _send_hook(rc: RunComponents, step: int, actor: str, turn: TurnRef | None = None) -> GateHook:
    """The coordinator's pre-send hook (phase 3A G2, phase 4A A2), consulted before every send: builds the
    authoritative execution context, refuses a proposal whose claimed identity is not the kernel's and a conditional
    write whose current revision cannot be read, then asks the scenario's execution gates in order (the first DENY
    stops the send). Every answer — the kernel's own refusals included — becomes an ExecutionDecision on the record."""

    def kernel_denial(record: OperationRecord, phase: ExecutionPhase, context: Any, reason: str) -> SendDecision:
        d = ExecutionDecision(
            decision_id=f"{record.operation_id}:basis:{phase.value.lower()}:{record.attempts}", run_id=rc.run_id,
            step=step, actor_id=actor, operation_id=record.operation_id, gate=KERNEL_BASIS, phase=phase,
            verdict=GateVerdict.DENY, reason=reason, values_source="NONE",
            checked_at_revision=context.current_revision, request_digest=record.request_digest or "", at=utcnow(),
            execution=context)
        return SendDecision(False, f"{KERNEL_BASIS.plugin_id}: {reason}", [d], execution=context)

    def hook(phase: ExecutionPhase, record: OperationRecord, proposal: ActionProposal) -> SendDecision:
        context = build_context(rc, step=step, turn=turn or proposal.turn, actor=actor, record=record,
                                proposal=proposal, phase=phase)
        problem = identity_problem(context, proposal)
        if problem:
            return kernel_denial(record, phase, context, problem)
        if caps.ENV_CONDITIONAL_STEP in rc.env_caps and context.current_revision is None:
            return kernel_denial(record, phase, context, f"BASIS_UNKNOWN: the write is conditional but the current "
                                                         f"revision is unknown ({context.revision_note}); nothing is sent")
        made: list[ExecutionDecision] = []
        for i, (ref, gate, cfg) in enumerate(rc.gates):
            values, source, revision = _gate_values(rc, actor, list(gate.paths(proposal.action)))
            request = GateRequest(run_id=rc.run_id, step=step, actor_id=actor, operation_id=record.operation_id,
                                  phase=phase, action=proposal.action, proposal_id=proposal.proposal_id,
                                  based_on_revision=proposal.based_on_revision, values=values, values_source=source,
                                  values_revision=revision, request_digest=record.request_digest or "", config=cfg,
                                  execution=context)
            answer = gate.decide(request)
            made.append(ExecutionDecision(
                decision_id=f"{record.operation_id}:gate{i}:{phase.value.lower()}:{record.attempts}",
                run_id=rc.run_id, step=step, actor_id=actor, operation_id=record.operation_id, gate=ref, phase=phase,
                verdict=answer.verdict, reason=answer.reason, conditions=answer.conditions, values_source=source,
                checked_at_revision=revision if revision is not None else context.current_revision,
                request_digest=request.request_digest, at=utcnow(), execution=context))
            if answer.verdict == GateVerdict.DENY:
                return SendDecision(False, f"{ref.plugin_id}: {answer.reason}", made, execution=context)
        why = "every execution gate allows the send" if rc.gates else "execution basis established (no gates)"
        return SendDecision(True, why, made, execution=context)

    return hook


_gate_hook = _send_hook  # phase-3A name, kept for callers outside the kernel


def apply_step(rc: RunComponents, snapshot: EnvironmentSnapshot, plan: PlanPhase, carry: CarryState,
               ledger: OperationLedger | None = None) -> StepExecution:
    """CHECK, EXECUTE (+RECONCILE), PROBE, COMPARE and TERMINATE. Deterministic w.r.t. snapshot + carry + plan for
    pure-data environments; for live sessions the ledger decides what may be (re)sent."""
    t_all = time.perf_counter()
    m = rc.manifest
    step = plan.step
    run_id = m.run_id
    ex = StepExecution(step=step, turn=plan.turn, observation=plan.observation, candidates=plan.candidates,
                       proposal=plan.proposal, usage_delta=plan.usage_delta, model_calls=plan.model_calls,
                       events=list(plan.events), terminal=plan.terminal, terminal_reason=plan.terminal_reason,
                       termination_reason=plan.termination_reason, stages=list(plan.stages))
    new = _merge_plan_into_carry(carry, plan)
    ex.carry = new
    if plan.terminal is not None or plan.turn is None:
        if plan.events:
            new.last_event_key = plan.events[-1].key
        return ex
    turn = plan.turn
    actor = turn.actor_id
    tkey = lambda kind: event_key(run_id, step, kind, actor)  # noqa: E731
    if rc.joint:
        return _apply_joint(rc, snapshot, plan, new, ex, ledger, t_all)
    if plan.skipped is not None:  # SKIP_ACTOR: record the pass, advance the turn, nothing changes in the world
        _restore(rc, snapshot)
        ex.snapshot = rc.env.snapshot()
        ex.events.append(EventDraft(tkey("skipped"), EventType.TURN_SKIPPED, step,
                                    {"actor_id": actor, "reason": plan.skipped, "retired": False},
                                    [tkey("candidates")], actor, turn, ExecutionStage.TURN))
        new.turn = rc.scheduler.advance(new.turn, turn, acted=False, progressed=False)
        new.last_event_key = tkey("skipped")
        _check_no_progress(rc, ex, new)
        ex.elapsed_s = plan.elapsed_s + time.perf_counter() - t_all
        return ex
    proposal = plan.proposal
    assert proposal is not None and plan.observation is not None
    _restore(rc, snapshot)
    belief = rc.loaded.belief(plan.observation)

    # ---- CHECK
    t0 = time.perf_counter()
    ex.precheck = rc.verifier.check(
        rc.package,
        CheckQuery(kind="ACTION_PRECONDITION", action=proposal.action, initial_state="GIVEN_STATE",
                   bound={"max_steps": 0, "timeout_ms": 5000}),
        state=belief.state, unknown_paths=belief.free_paths,
    )
    ex.events.append(EventDraft(tkey("check"), EventType.CHECK_COMPLETED, step,
                                {"purpose": "precondition of the proposed action on the actor's belief",
                                 "result": ex.precheck.model_dump(mode="json")},
                                [tkey("proposal")], actor, turn, ExecutionStage.CHECK))
    ex.stages.append(_stage(ExecutionStage.CHECK, StageStatus.OK if str(ex.precheck.verdict) != "UNSUPPORTED"
                            else StageStatus.SKIPPED, RetrySemantics.IDEMPOTENT, t0,
                            inp=proposal.action.model_dump(mode="json"), out=str(ex.precheck.verdict)))
    prediction = rc.loaded.predict(belief.state, proposal.action)
    expected_post = prediction.next_state if prediction.applicable else dict(belief.state)
    written = prediction.written_paths if prediction.applicable else []

    # ---- EXECUTE (+ RECONCILE) through the coordinator
    t0 = time.perf_counter()
    op_id = f"{turn_id(run_id, step, actor)}:apply"
    coordinator = Coordinator(rc.env, rc.env_caps, ledger or InMemoryLedger(), gate=_send_hook(rc, step, actor, turn))
    result = coordinator.execute(proposal, op_id, run_id=run_id, step=step)
    ex.operation = result.record
    # typed pre-execution decisions (phase 3A), keyed by gate / phase / attempt: every decision on the durable record,
    # including one made by an attempt that crashed before its events were committed (keys are idempotent)
    for d in {x.decision_id: x for x in [*result.record.decisions, *result.decisions]}.values():
        ex.events.append(EventDraft(tkey("decision-" + d.decision_id[len(op_id) + 1:].replace(":", "-")),
                                    EventType.EXECUTION_DECIDED, step, {"decision": d.model_dump(mode="json")},
                                    [tkey("check")], actor, turn, ExecutionStage.EXECUTE))
    if result.transitions:
        ex.events.append(EventDraft(tkey("operation"), EventType.OPERATION_STATE, step,
                                    {"operation_id": op_id, "state": result.record.state.value,
                                     "transitions": [{"state": s.value, "reason": r} for s, r in result.transitions],
                                     "attempts": result.record.attempts},
                                    [tkey("check")], actor, turn, ExecutionStage.EXECUTE))
    if result.record.reconciliation is not None and result.record.state.value == "RECONCILED":
        ex.events.append(EventDraft(tkey("reconciled"), EventType.OPERATION_RECONCILED, step,
                                    {"operation_id": op_id,
                                     "reconciliation": result.record.reconciliation.model_dump(mode="json")},
                                    [tkey("operation")], actor, turn, ExecutionStage.RECONCILE))
        ex.stages.append(_stage(ExecutionStage.RECONCILE, StageStatus.OK, RetrySemantics.RECONCILE_THEN_RETRY, t0,
                                inp=op_id, note=result.record.reconciliation.note))
    if result.unresolved or result.outcome is None:
        ex.stages.append(_stage(ExecutionStage.EXECUTE, StageStatus.UNKNOWN, RetrySemantics.RECONCILE_THEN_RETRY, t0,
                                inp=proposal.model_dump(mode="json"),
                                note=result.record.review.note if result.record.review else None))
        ex.events.append(EventDraft(tkey("review"), EventType.OPERATION_REVIEW, step,
                                    {"operation": result.record.model_dump(mode="json"),
                                     "conflict": result.conflict,
                                     "attempted_action": proposal.action.model_dump(mode="json"),
                                     "action": "run ends: the operation outcome cannot be settled automatically"},
                                    [tkey("proposal")], actor, turn, ExecutionStage.RECONCILE))
        ex.terminal, ex.termination_reason = RunStatus.FAILED, TerminationReason.OPERATION_UNRESOLVED
        why = result.conflict or (result.record.review.note if result.record.review else "")
        ex.terminal_reason = f"operation {op_id} unresolved: {why}"
        new.last_event_key = tkey("review")
        return ex
    outcome = result.outcome.model_copy(update={"turn": turn})
    retry = next((spec.retry for spec in rc.specs if spec.action_type == proposal.action.action_type),
                 RetrySemantics.RECONCILE_THEN_RETRY)
    ex.stages.append(_stage(ExecutionStage.EXECUTE, StageStatus.OK, retry, t0, inp=proposal.model_dump(mode="json"),
                            out=outcome.model_dump(mode="json"), note=outcome.status.value))
    ex.acted = True
    next_obs = rc.env.observe(actor)
    ex.snapshot = rc.env.snapshot()

    # ---- PROBE
    t0 = time.perf_counter()
    every = int(m.config.get("probe_every", 1))
    if rc.probes and hasattr(rc.env, "session") and step % max(1, every) == 0:
        session = rc.env.session()
        for probe in rc.probes:
            ex.probes.extend(probe.sample(session, step=step))
        ex.events.append(EventDraft(tkey("probes"), EventType.PROBE_SAMPLED, step,
                                    {"results": [p.model_dump(mode="json") for p in ex.probes],
                                     "session_id": session.session_id},
                                    [tkey("proposal")], actor, turn, ExecutionStage.PROBE))
        ex.stages.append(_stage(ExecutionStage.PROBE, StageStatus.OK, RetrySemantics.IDEMPOTENT, t0,
                                out=[p.model_dump(mode="json") for p in ex.probes]))

    # ---- COMPARE
    t0 = time.perf_counter()
    unknown_note = f" ({len(belief.free_paths)} unknown)" if belief.free_paths else ""
    # an action predicted inapplicable is predicted to change nothing (phase-1 semantics): compare against that
    # the prediction is from the actor's belief at `based_on_revision`; when another participant moved the world
    # before this action executed, a difference reflects that stale basis, not an error of the model
    stale_basis = outcome.revision_before is not None and proposal.based_on_revision < outcome.revision_before
    basis_note = (f"; basis stale: planned at revision {proposal.based_on_revision}, executed at revision "
                  f"{outcome.revision_before}" if stale_basis else "")
    if result.denied:  # not sent (execution gate): the world is expected to stay as the actor saw it
        expected_post, written = dict(belief.state), []
        basis_note += "; not sent: denied by an execution gate"
    ex.comparison = rc_compare(rc, expected_post=expected_post,
                               pre_state=belief.state, observation=next_obs, written=written,
                               expected_by=f"model:{rc.package.package_id}@{rc.package.version} on belief"
                                           f"{unknown_note}{basis_note}",
                               verified=outcome.result.get("verified") or {})
    outcome = outcome.model_copy(update={"effect_comparison": ex.comparison})
    ex.outcome = outcome
    ex.properties = dict(outcome.result.get("properties") or (rc.env.truth_properties()
                                                               if hasattr(rc.env, "truth_properties") else {}))
    ex.events.append(EventDraft(tkey("outcome"), EventType.ACTION_OUTCOME, step,
                                {"outcome": outcome.model_dump(mode="json"), "snapshot_digest": ex.snapshot.digest.value,
                                 "state_revision": ex.snapshot.state_revision,
                                 "operation": result.record.model_dump(mode="json"),
                                 "stages": [s.model_dump(mode="json") for s in ex.stages]},
                                [tkey("proposal"), tkey("check")], actor, turn, ExecutionStage.EXECUTE))
    ex.events.append(EventDraft(tkey("comparison"), EventType.EFFECT_COMPARED, step,
                                {"comparison": ex.comparison.model_dump(mode="json"),
                                 "observation_after": next_obs.model_dump(mode="json")},
                                [tkey("outcome")], actor, turn, ExecutionStage.COMPARE))
    ex.stages.append(_stage(ExecutionStage.COMPARE, StageStatus.OK, RetrySemantics.IDEMPOTENT, t0,
                            out=ex.comparison.model_dump(mode="json"), note=ex.comparison.verdict.value))
    last_key = tkey("comparison")
    model_difference = ex.comparison.verdict.value == "DIFFERENT" and not stale_basis and not result.denied
    if model_difference:  # only a difference on the revision the action was planned from points at the model
        last_key = _on_difference(rc, ex, belief, proposal, step, turn, last_key)

    # ---- rules on the outcome
    last_key = _outcome_rules(rc, ex, new, step, turn, outcome, ex.comparison, next_obs, model_difference, last_key)

    # ---- TERMINATE + carry
    new.last_outcomes[actor] = outcome.model_dump(mode="json")
    actor_usage = add_usage(new.usage_of(actor), plan.usage_delta, steps=1)
    new.actor_usage[actor] = actor_usage.model_dump()
    progressed = (outcome.revision_after or outcome.revision_before) != outcome.revision_before
    new.turn = rc.scheduler.advance(new.turn, turn, acted=True, progressed=progressed)
    _check_goals(rc, ex, new, actor)
    if ex.terminal is None:
        _check_no_progress(rc, ex, new)
    p = rc.participants[actor]
    dims = list(m.config.get("budget_dimensions", ["steps", "wall_seconds"]))
    if ex.terminal is None and p.budget and budget_exhausted(p.budget, actor_usage, dims):
        new.turn = CycleScheduler.retire(new.turn, actor)
        key = tkey("retired")
        ex.events.append(EventDraft(key, EventType.TURN_SKIPPED, step,
                                    {"actor_id": actor, "retired": True,
                                     "reason": f"participant budget: {budget_exhausted(p.budget, actor_usage, dims)}"},
                                    [last_key], actor, turn, ExecutionStage.TERMINATE))
        last_key = key
        if not rc.scheduler.active(new.turn):
            ex.terminal, ex.termination_reason = RunStatus.BUDGET_EXHAUSTED, TerminationReason.ACTOR_BUDGETS_EXHAUSTED
            ex.terminal_reason = "every participant exhausted its own budget"
    new.last_event_key = last_key
    ex.elapsed_s = plan.elapsed_s + time.perf_counter() - t_all
    return ex


# ---------------------------------------------------------------------------- joint batches (phase 3A, G4)


def _spent(rc: RunComponents, carry: CarryState, actor: str) -> bool:
    p = rc.participants[actor]
    dims = list(rc.manifest.config.get("budget_dimensions", ["steps", "wall_seconds"]))
    return bool(p.budget and budget_exhausted(p.budget, carry.usage_of(actor), dims))


def _precheck(rc: RunComponents, ex: StepExecution, belief: BeliefState, proposal: ActionProposal, step: int,
              turn: TurnRef) -> None:
    t0 = time.perf_counter()
    actor = turn.actor_id
    ex.precheck = rc.verifier.check(
        rc.package,
        CheckQuery(kind="ACTION_PRECONDITION", action=proposal.action, initial_state="GIVEN_STATE",
                   bound={"max_steps": 0, "timeout_ms": 5000}),
        state=belief.state, unknown_paths=belief.free_paths,
    )
    ex.events.append(EventDraft(event_key(rc.run_id, step, "check", actor), EventType.CHECK_COMPLETED, step,
                                {"purpose": "precondition of the proposed action on the actor's belief",
                                 "result": ex.precheck.model_dump(mode="json")},
                                [event_key(rc.run_id, step, "proposal", actor)], actor, turn, ExecutionStage.CHECK))
    ex.stages.append(_stage(ExecutionStage.CHECK, StageStatus.OK if str(ex.precheck.verdict) != "UNSUPPORTED"
                            else StageStatus.SKIPPED, RetrySemantics.IDEMPOTENT, t0,
                            inp=proposal.action.model_dump(mode="json"), out=str(ex.precheck.verdict)))


def _apply_joint(rc: RunComponents, snapshot: EnvironmentSnapshot, plan: PlanPhase, new: CarryState,
                 ex: StepExecution, ledger: OperationLedger | None, t_all: float) -> StepExecution:
    """One member's step of a JOINT_BATCH round: CHECK its proposal and keep it in the open batch; the round's last
    member (or the first one past the batch deadline) submits the batch."""
    m = rc.manifest
    step, turn = plan.step, plan.turn
    assert turn is not None
    actor = turn.actor_id
    tkey = lambda kind: event_key(m.run_id, step, kind, actor)  # noqa: E731
    if new.batch is None or new.batch["record"]["status"] != "OPEN":
        raise NonRetryableFailure(f"JOINT_BATCH step {step}: no open batch for round {turn.round}")
    record = BatchRecord.model_validate(new.batch["record"])
    _restore(rc, snapshot)
    last_key = plan.events[-1].key if plan.events else (new.last_event_key or event_key(m.run_id, 0, "snapshot"))
    timeout = m.turns.batch_timeout_s
    waited = ((datetime.fromisoformat(plan.proposed_at) - record.opened_at).total_seconds()
              if plan.proposed_at else 0.0)
    late = timeout is not None and plan.skipped is None and waited > timeout
    acted = False
    if plan.skipped is not None:
        member = BatchMember(actor_id=actor, status=BatchMemberStatus.PASSED, global_step=step,
                             actor_step=turn.actor_step, reason=plan.skipped)
        ex.events.append(EventDraft(tkey("skipped"), EventType.TURN_SKIPPED, step,
                                    {"actor_id": actor, "reason": plan.skipped, "retired": False,
                                     "batch_id": record.batch_id}, [last_key], actor, turn, ExecutionStage.TURN))
        last_key = tkey("skipped")
    elif late:
        assert plan.proposal is not None
        member = BatchMember(actor_id=actor, status=BatchMemberStatus.TIMED_OUT, proposal_id=plan.proposal.proposal_id,
                             global_step=step, actor_step=turn.actor_step,
                             reason=f"proposal ready {waited:.2f}s after the batch opened (limit {timeout}s): "
                                    "not submitted")
    else:
        assert plan.proposal is not None and plan.observation is not None
        _precheck(rc, ex, rc.loaded.belief(plan.observation), plan.proposal, step, turn)
        last_key = tkey("check")
        member = BatchMember(actor_id=actor, status=BatchMemberStatus.PROPOSED, proposal_id=plan.proposal.proposal_id,
                             global_step=step, actor_step=turn.actor_step)
        new.batch["proposals"][actor] = plan.proposal.model_dump(mode="json")
        new.batch["turns"][actor] = turn.model_dump(mode="json")
        new.batch["observations"][actor] = plan.observation.model_dump(mode="json")
        acted = True
    record.members.append(member)
    if acted or plan.usage_delta != ModelUsage():
        new.actor_usage[actor] = add_usage(new.usage_of(actor), plan.usage_delta, steps=1 if acted else 0).model_dump()
    new.turn = rc.scheduler.advance(new.turn, turn, acted=acted, progressed=None)
    if acted and _spent(rc, new, actor):
        new.turn = CycleScheduler.retire(new.turn, actor)
        ex.events.append(EventDraft(tkey("retired"), EventType.TURN_SKIPPED, step,
                                    {"actor_id": actor, "retired": True, "reason": "participant budget exhausted; "
                                     "its proposal stays in the batch"}, [last_key], actor, turn,
                                    ExecutionStage.TERMINATE))
        last_key = tkey("retired")
    done = {x.actor_id for x in record.members}
    remaining = [a for a in record.expected if a not in done and a not in new.turn.retired and not _spent(rc, new, a)]
    if remaining and not late:  # the round goes on: the world stays as it was at the round start
        new.batch["record"] = record.model_dump(mode="json")
        ex.snapshot = rc.env.snapshot()
        new.last_event_key = last_key
        ex.elapsed_s = plan.elapsed_s + time.perf_counter() - t_all
        return ex
    for a in record.expected:
        if a in done:
            continue
        if late and a in remaining:
            record.members.append(BatchMember(actor_id=a, status=BatchMemberStatus.TIMED_OUT,
                                              reason=f"the batch deadline ({timeout}s) passed before its turn"))
        else:
            record.members.append(BatchMember(actor_id=a, status=BatchMemberStatus.ABSENT,
                                              reason="retired: its own budget is exhausted"))
    if late and remaining:
        new.turn = rc.scheduler.close_round(new.turn, turn.round, remaining)
    return _submit_batch(rc, plan, new, ex, record, ledger, last_key, t_all)


def _joint_expectation(rc: RunComponents, state: dict[str, Any], actions: list[Any]) -> tuple[dict[str, Any], list[str]]:
    """The model's prediction of a batch under START_STATE_DISJOINT_WRITES: every action on `state`; writes of
    applicable actions merged; an action writing a location an earlier one wrote takes no effect."""
    merged, written = dict(state), set()
    for action in actions:
        pred = rc.loaded.predict(state, action)
        if not (pred.applicable and pred.next_state is not None):
            continue
        writes = set(pred.written_paths) | {p for p, v in pred.next_state.items() if state.get(p) != v}
        if writes & written:
            continue
        for path in writes:
            merged[path] = pred.next_state[path]
        written |= writes
    return merged, sorted(written)


def _submit_batch(rc: RunComponents, plan: PlanPhase, new: CarryState, ex: StepExecution, record: BatchRecord,
                  ledger: OperationLedger | None, last_key: str, t_all: float) -> StepExecution:
    m = rc.manifest
    step, turn = plan.step, plan.turn
    assert turn is not None and new.batch is not None
    actor = turn.actor_id
    tkey = lambda kind: event_key(m.run_id, step, kind, actor)  # noqa: E731
    t0 = time.perf_counter()
    order = {a: i for i, a in enumerate(record.expected)}
    record.members.sort(key=lambda x: order.get(x.actor_id, len(order)))
    proposing = [x.actor_id for x in record.members if x.status is BatchMemberStatus.PROPOSED]
    proposals = {a: ActionProposal.model_validate(new.batch["proposals"][a]) for a in proposing}
    turns = {a: TurnRef.model_validate(new.batch["turns"][a]) for a in proposing}
    op_id = f"{turn_id(m.run_id, step, actor)}:apply"
    ledger = ledger or InMemoryLedger()
    # ---- execution gates, member by member (a denied member is not sent; the others are)
    decisions: list[ExecutionDecision] = []
    denied: dict[str, SendDecision] = {}
    if rc.gates:
        phase = ExecutionPhase.FIRST_SEND if ledger.get(op_id) is None else ExecutionPhase.REEXECUTE
        for a in proposing:
            p = proposals[a]
            view = OperationRecord(operation_id=f"{op_id}:{a}", run_id=m.run_id, step=turns[a].global_step,
                                   actor_id=a, state="PREPARED", action=p.action, proposal_id=p.proposal_id,
                                   based_on_revision=p.based_on_revision, request_digest=request_digest(p),
                                   batch_id=record.batch_id)
            verdict = _gate_hook(rc, turns[a].global_step, a)(phase, view, p)
            decisions += verdict.decisions
            if not verdict.allowed:
                denied[a] = verdict
    send = [proposals[a] for a in proposing if a not in denied]
    # ---- EXECUTE: one environment step for the whole batch
    outcomes: dict[str, ActionOutcome] = {}
    result = None
    if send:
        result = Coordinator(rc.env, rc.env_caps, ledger).execute_batch(send, op_id, run_id=m.run_id, step=step,
                                                                         batch_id=record.batch_id)
        if decisions:
            result.record = result.record.model_copy(update={"decisions": decisions})
            ledger.put(result.record)
        ex.operation = result.record
        if result.unresolved:
            ex.events.append(EventDraft(tkey("review"), EventType.OPERATION_REVIEW, step,
                                        {"operation": result.record.model_dump(mode="json"),
                                         "conflict": result.conflict, "batch_id": record.batch_id,
                                         "action": "run ends: the batch outcome cannot be settled automatically"},
                                        [last_key], actor, turn, ExecutionStage.RECONCILE))
            ex.terminal, ex.termination_reason = RunStatus.FAILED, TerminationReason.OPERATION_UNRESOLVED
            ex.terminal_reason = f"batch operation {op_id} unresolved: {result.conflict or ''}"
            new.last_event_key = tkey("review")
            return ex
        outcomes = {p.actor_id: o for p, o in zip(send, result.outcomes, strict=True)}
    for a, verdict in denied.items():
        p = proposals[a]
        outcomes[a] = ActionOutcome(
            operation_id=f"{op_id}:{a}", run_id=m.run_id, step_id=p.step_id, proposal_id=p.proposal_id,
            action=p.action, status="REJECTED", effect_applied=False, revision_before=p.based_on_revision,
            revision_after=p.based_on_revision, turn=p.turn, operation_state="FAILED",
            result={"reason": f"EXECUTION_GATE: {verdict.reason}", "not_sent": True,
                    "decisions": [d.decision_id for d in verdict.decisions]})
    ex.snapshot = rc.env.snapshot()
    env_step = ex.snapshot.step
    ex.stages.append(_stage(ExecutionStage.EXECUTE, StageStatus.OK, RetrySemantics.RECONCILE_THEN_RETRY, t0,
                            inp=[p.model_dump(mode="json") for p in send],
                            note=f"batch {record.batch_id}: {len(send)} sent, {len(denied)} denied by a gate"))
    record = record.model_copy(update={
        "status": "SUBMITTED", "submitted_at_step": step, "env_step": env_step if send else None,
        "operation_id": op_id if send else None,
        "note": None if send else "nothing to submit: no member proposed an action that could be sent"})
    ex.batch = record
    ex.events.append(EventDraft(tkey("batch-submitted"), EventType.BATCH_SUBMITTED, step,
                                {"batch": record.model_dump(mode="json"),
                                 "operation": result.record.model_dump(mode="json") if result else None},
                                [last_key], actor, turn, ExecutionStage.EXECUTE))
    last_key = tkey("batch-submitted")
    for d in decisions:
        ex.events.append(EventDraft(tkey(f"decision-{d.actor_id}-{d.gate.plugin_id}"), EventType.EXECUTION_DECIDED,
                                    step, {"decision": d.model_dump(mode="json"), "batch_id": record.batch_id},
                                    [last_key], actor, turn, ExecutionStage.EXECUTE))
    if result is not None and result.transitions:
        ex.events.append(EventDraft(tkey("operation"), EventType.OPERATION_STATE, step,
                                    {"operation_id": op_id, "state": result.record.state.value, "kind": "batch",
                                     "batch_id": record.batch_id,
                                     "transitions": [{"state": st.value, "reason": r} for st, r in result.transitions],
                                     "attempts": result.record.attempts},
                                    [last_key], actor, turn, ExecutionStage.EXECUTE))
    # ---- COMPARE, member by member, at each member's own proposal step
    t0 = time.perf_counter()
    sent_actions = [p.action for p in send]
    applied_writes = {a: set(o.result.get("written_paths", [])) for a, o in outcomes.items()
                      if o.status.value == "APPLIED"}
    reported: set[str] = set()
    for a in proposing:
        mturn = turns[a].model_copy(update={"env_step": env_step, "batch_id": record.batch_id})
        mstep = mturn.global_step
        mkey = lambda kind, a=a, mstep=mstep: event_key(m.run_id, mstep, kind, a)  # noqa: E731
        belief = rc.loaded.belief(Observation.model_validate(new.batch["observations"][a]))
        next_obs = rc.env.observe(a)
        outcome = outcomes[a]
        others = set().union(*(w for b, w in applied_writes.items() if b != a))
        if a in denied:
            note = "not sent: denied by an execution gate"
        else:
            note = ""
        if rc.joint_prediction:
            expected_post, written = _joint_expectation(rc, belief.state, sent_actions)
            by = (f"model:{rc.package.package_id}@{rc.package.version} joint prediction "
                  f"({rc.driver_joint_semantics}) of batch {record.batch_id} on {a}'s belief")
        else:
            pred = rc.loaded.predict(belief.state, proposals[a].action)
            applies = pred.applicable and a not in denied
            expected_post = pred.next_state if applies else dict(belief.state)
            written = pred.written_paths if applies else []
            by = (f"model:{rc.package.package_id}@{rc.package.version} on {a}'s belief (own action only: the driver "
                  f"declares no joint semantics matching {rc.env_batch_semantics}; locations written by other batch "
                  f"members are not predicted)")
        comparison = rc_compare(rc, expected_post=expected_post, pre_state=belief.state, observation=next_obs,
                                written=written, expected_by=by + (f"; {note}" if note else ""),
                                verified=outcome.result.get("verified") or {})
        differing = {d.path for d in comparison.diffs if d.status == "DIFFERENT"}
        if not rc.joint_prediction:
            differing -= others
        new_paths = differing - reported
        model_difference = bool(new_paths) and a not in denied
        outcome = outcome.model_copy(update={"turn": mturn, "effect_comparison": comparison})
        ex.events.append(EventDraft(mkey("outcome"), EventType.ACTION_OUTCOME, mstep,
                                    {"outcome": outcome.model_dump(mode="json"), "batch_id": record.batch_id,
                                     "submitted_at_step": step, "snapshot_digest": ex.snapshot.digest.value,
                                     "state_revision": ex.snapshot.state_revision,
                                     "operation": result.record.model_dump(mode="json") if result else None},
                                    [mkey("proposal"), tkey("batch-submitted")], a, mturn, ExecutionStage.EXECUTE))
        ex.events.append(EventDraft(mkey("comparison"), EventType.EFFECT_COMPARED, mstep,
                                    {"comparison": comparison.model_dump(mode="json"),
                                     "observation_after": next_obs.model_dump(mode="json"),
                                     "batch_id": record.batch_id},
                                    [mkey("outcome")], a, mturn, ExecutionStage.COMPARE))
        member_last = mkey("comparison")
        if model_difference:
            reported |= new_paths
            suggestion = {"action": proposals[a].action.model_dump(mode="json"),
                          "batch_id": record.batch_id, "batch_actions": [x.model_dump(mode="json")
                                                                         for x in sent_actions],
                          "different_fields": [d.model_dump(mode="json") for d in comparison.diffs
                                               if d.path in new_paths],
                          "state_families": sorted({x.split("[", 1)[0] for x in new_paths}),
                          "regression_case": "not created: a regression case replays an action sequence, and a "
                                             "joint batch is not one",
                          "hint": "the model's prediction of this batch differs from the environment; edit the "
                                  "model (effects or joint semantics), re-check it and compare in a new run"}
            ex.events.append(EventDraft(mkey("revision-suggestion"), EventType.MODEL_REVISION_SUGGESTED, mstep,
                                        suggestion, [member_last], a, mturn, ExecutionStage.COMPARE))
            member_last = mkey("revision-suggestion")
        member_last = _outcome_rules(rc, ex, new, mstep, mturn, outcome, comparison, next_obs, model_difference,
                                     member_last)
        new.last_outcomes[a] = outcome.model_dump(mode="json")
        if a == actor:
            ex.outcome, ex.comparison, ex.acted, ex.turn = outcome, comparison, True, mturn
        else:
            ex.batch_outcomes[mstep] = outcome
        last_key = member_last
    ex.stages.append(_stage(ExecutionStage.COMPARE, StageStatus.OK, RetrySemantics.IDEMPOTENT, t0,
                            note=f"{len(proposing)} member comparison(s); joint prediction: {rc.joint_prediction}"))
    # ---- TERMINATE
    ex.properties = rc.env.truth_properties() if hasattr(rc.env, "truth_properties") else {}
    progressed = any(o.status.value == "APPLIED" for o in outcomes.values())
    new.turn = new.turn.model_copy(update={"no_progress": 0 if progressed else new.turn.no_progress + 1})
    new.batch = None
    _check_goals(rc, ex, new, actor)
    if ex.terminal is None:
        _check_no_progress(rc, ex, new)
    if ex.terminal is None and not rc.scheduler.active(new.turn):
        ex.terminal, ex.termination_reason = RunStatus.BUDGET_EXHAUSTED, TerminationReason.ACTOR_BUDGETS_EXHAUSTED
        ex.terminal_reason = "every participant exhausted its own budget"
    new.last_event_key = last_key
    ex.elapsed_s = plan.elapsed_s + time.perf_counter() - t_all
    return ex


def _outcome_rules(rc: RunComponents, ex: StepExecution, new: CarryState, step: int, turn: TurnRef,
                   outcome: ActionOutcome, comparison: EffectComparison, next_obs: Observation,
                   model_difference: bool, last_key: str) -> str:
    """Rules triggered by an outcome and its comparison (REPLAN / OBSERVE_MORE flags for the actor's next turn,
    PAUSE for the run). Returns the last event key."""
    actor = turn.actor_id
    flags = dict(new.flags.get(actor, {}))
    rejected = flags.get("rejected", 0) + 1 if outcome.status.value == "REJECTED" else 0
    flags["rejected"] = rejected
    different = sum(1 for d in comparison.diffs if d.status == "DIFFERENT") if model_difference else 0
    after_belief = rc.loaded.belief(next_obs)
    for trigger in ("ACTION_OUTCOME", "EFFECT_COMPARED"):
        decision = _apply_rules(rc, trigger, after_belief, _rule_context(
            next_obs, after_belief, verdict=comparison.verdict.value, outcome=outcome.status.value,
            different=different, step=step, rejected=rejected))
        if decision is None:
            continue
        key = event_key(rc.run_id, step, f"rules-{trigger.lower()}", actor)
        ex.events.append(EventDraft(key, EventType.RULE_EVALUATED, step, {"decision": decision.model_dump(mode="json")},
                                    [last_key], actor, turn, ExecutionStage.CHECK))
        last_key = key
        if decision.outcome is RuleOutcome.PAUSE:
            ex.pause_requested = f"rule {decision.winner or 'conflict'}: {decision.priority_explanation}"
        elif decision.outcome is RuleOutcome.REPLAN:
            flags["replan"] = f"rule {decision.winner}: {decision.priority_explanation}"
        elif decision.outcome is RuleOutcome.OBSERVE_MORE and decision.winner:
            winner = next(r for r in rc.rules.ruleset.rules if r.rule_id == decision.winner)
            flags["observe_paths"] = list(winner.observe_paths)
    new.flags[actor] = flags
    return last_key


def rc_compare(rc: RunComponents, **kw: Any) -> EffectComparison:
    from formal_lab_model.compare import compare_effects

    return compare_effects(expected_post=kw["expected_post"], pre_state=kw["pre_state"], observation=kw["observation"],
                           written_paths=kw["written"], expected_by=kw["expected_by"], verified=kw["verified"])


def _check_goals(rc: RunComponents, ex: StepExecution, carry: CarryState, actor: str) -> None:
    props = ex.properties
    term = rc.termination
    for inv in term.invariants:
        if props.get(inv) is False:
            ex.terminal, ex.termination_reason = RunStatus.FAILED, TerminationReason.INVARIANT_VIOLATED
            ex.terminal_reason = f"invariant {inv!r} violated"
            return
    if term.joint_goal and props.get(term.joint_goal):
        ex.terminal, ex.termination_reason = RunStatus.SUCCEEDED, TerminationReason.JOINT_GOAL_REACHED
        ex.terminal_reason = f"goal {term.joint_goal!r} reached"
        return
    reached = list(carry.turn.goals_reached)
    for p in rc.manifest.participants:
        if p.goal and props.get(p.goal) and p.actor_id not in reached:
            reached.append(p.actor_id)
    carry.turn = carry.turn.model_copy(update={"goals_reached": reached})
    with_goals = [p.actor_id for p in rc.manifest.participants if p.goal]
    if str(term.actor_goals) == "ANY" and reached:
        ex.terminal, ex.termination_reason = RunStatus.SUCCEEDED, TerminationReason.ACTOR_GOAL_REACHED
        ex.terminal_reason = f"participant {reached[0]} reached its goal"
    elif str(term.actor_goals) == "ALL" and with_goals and set(with_goals) <= set(reached):
        ex.terminal, ex.termination_reason = RunStatus.SUCCEEDED, TerminationReason.ALL_ACTOR_GOALS_REACHED
        ex.terminal_reason = f"all participants reached their goals ({', '.join(with_goals)})"


def _check_no_progress(rc: RunComponents, ex: StepExecution, carry: CarryState) -> None:
    limit = rc.termination.no_progress_limit
    if limit and carry.turn.no_progress >= limit and ex.terminal is None:
        ex.terminal, ex.termination_reason = RunStatus.FAILED, TerminationReason.NO_PROGRESS
        ex.terminal_reason = f"no state change in the last {carry.turn.no_progress} turn(s) (limit {limit})"


def _on_difference(rc: RunComponents, ex: StepExecution, belief: BeliefState, proposal: ActionProposal, step: int,
                   turn: TurnRef, parent: str) -> str:
    """Effect difference: suggest where the model may be wrong (P2-075) and keep a minimal regression case
    (P2-076). The actor's plan sees the difference through `last_outcome` and is revised by its planner."""
    assert ex.comparison is not None
    diffs = [d for d in ex.comparison.diffs if d.status == "DIFFERENT"]
    families = sorted({d.path.split("[", 1)[0] for d in diffs})
    suggestion: dict[str, Any] = {
        "action": proposal.action.model_dump(mode="json"),
        "different_fields": [d.model_dump(mode="json") for d in diffs],
        "state_families": families,
        "hint": "the effects of this action (or constants they read) predict values the environment did not "
                "produce; edit the model, re-check it and compare in a new run",
    }
    if rc.is_ir:
        from formal_lab_model.rules import read_set

        decl = rc.loaded.checked.actions.get(proposal.action.action_type)
        if decl is not None:
            consts = sorted({v.name for v in _vars_in(decl) if not rc.loaded.checked.families[v.name].is_state})
            suggestion["action_effects"] = [str(e.kind) for e in decl.effects]
            suggestion["constants_read"] = consts
            suggestion["precondition_reads"] = sorted(read_set(decl.precondition, rc.loaded.checked))[:20]
    actor = turn.actor_id
    key = event_key(rc.run_id, step, "revision-suggestion", actor)
    ex.events.append(EventDraft(key, EventType.MODEL_REVISION_SUGGESTED, step, suggestion, [parent], actor, turn,
                                ExecutionStage.COMPARE))
    if rc.manifest.config.get("regression_cases", True):
        case = RegressionCase(
            case_id=f"reg_{hashlib.sha256(f'{rc.run_id}:{step}:{actor}'.encode()).hexdigest()[:16]}",
            source="EFFECT_DIFFERENCE", model=rc.manifest.model, scenario=rc.manifest.scenario, seed=rc.manifest.seed,
            initial_state=dict(belief.state), actions=[proposal.action],
            expected={d.path: d.expected for d in diffs}, observed={d.path: d.observed for d in diffs},
            compared_paths=[d.path for d in diffs], minimized=True,
            origin={"run_id": rc.run_id, "step": step, "actor_id": actor,
                    "assumptions_digest": belief.assumptions.digest.value}, created_at=utcnow())
        ex.regression_case = case
        rkey = event_key(rc.run_id, step, "regression-case", actor)
        ex.events.append(EventDraft(rkey, EventType.REGRESSION_CASE_CREATED, step,
                                    {"case": case.model_dump(mode="json")}, [key], actor, turn,
                                    ExecutionStage.COMPARE))
        return rkey
    return key


def _vars_in(decl: Any) -> list[Any]:
    from formal_lab_contracts.ir import VarExpr
    from pydantic import BaseModel

    out: list[Any] = []

    def walk(node: Any) -> None:
        if isinstance(node, VarExpr):
            out.append(node)
        if isinstance(node, BaseModel):
            for name in type(node).model_fields:
                walk(getattr(node, name))
        elif isinstance(node, list):
            for x in node:
                walk(x)

    walk(decl.effects)
    return out


def execute_step(rc: RunComponents, snapshot: EnvironmentSnapshot, step: int, usage: BudgetUsage,
                 carry: CarryState, ledger: OperationLedger | None = None) -> StepExecution:
    """Execute global step `step` starting from `snapshot` + `carry` (the state after step-1)."""
    return apply_step(rc, snapshot, plan_step(rc, snapshot, step, usage, carry), carry, ledger)


def failure_status(exc: BaseException) -> tuple[RunStatus, str]:
    if isinstance(exc, FormalLabError):
        return RunStatus.FAILED, f"{exc.code}: {exc.message}"
    return RunStatus.FAILED, f"{type(exc).__name__}: {exc}"


# ---------------------------------------------------------------------------- finish


@dataclass
class FinishResult:
    metrics: list[Any]
    final_state: dict[str, Any]
    properties: dict[str, bool]
    events: list[EventDraft]


TERMINAL_EVENT = {
    RunStatus.SUCCEEDED: EventType.RUN_SUCCEEDED,
    RunStatus.FAILED: EventType.RUN_FAILED,
    RunStatus.CANCELLED: EventType.RUN_CANCELLED,
    RunStatus.BUDGET_EXHAUSTED: EventType.BUDGET_EXHAUSTED,
}


def finish_run(rc: RunComponents, *, status: RunStatus, reason: str | None, final_snapshot: EnvironmentSnapshot | None,
               usage: BudgetUsage, steps: list[Any], last_step: int, parent_key: str,
               termination_reason: TerminationReason | None = None, actor_usage: dict[str, Any] | None = None,
               probes: list[Any] | None = None, carry: CarryState | dict[str, Any] | None = None) -> FinishResult:
    """Score the episode from the environment's truth and emit metrics + terminal events. A JOINT_BATCH round still
    open at the end is cancelled: nothing of it was sent (BATCH_CANCELLED)."""
    from formal_lab_contracts import EpisodeRecord

    m = rc.manifest
    events: list[EventDraft] = []
    batch = carry.batch if isinstance(carry, CarryState) else (carry or {}).get("batch")
    if batch and batch["record"]["status"] == "OPEN":
        record = BatchRecord.model_validate(batch["record"])
        done = {x.actor_id for x in record.members}
        members = [x.model_copy(update={"status": BatchMemberStatus.CANCELLED,
                                        "reason": f"run ended ({status.value}) before the batch was submitted: "
                                                  "the proposal was not sent"})
                   if x.status is BatchMemberStatus.PROPOSED else x for x in record.members]
        retired = set(carry.turn.retired if isinstance(carry, CarryState) else
                       (carry or {}).get("turn", {}).get("retired", []))
        members += [BatchMember(actor_id=a, status=BatchMemberStatus.ABSENT, reason="retired: its own budget is "
                                "exhausted") if a in retired else
                    BatchMember(actor_id=a, status=BatchMemberStatus.CANCELLED,
                                reason=f"run ended ({status.value}) before its turn") for a in record.expected
                    if a not in done]
        record = record.model_copy(update={"status": "CANCELLED", "members": members,
                                           "note": f"run ended: {reason or status.value}"})
        key = event_key(m.run_id, None, f"batch-cancelled-{record.round}")
        events.append(EventDraft(key, EventType.BATCH_CANCELLED, last_step, {"batch": record.model_dump(mode="json")},
                                 [parent_key], stage=ExecutionStage.TERMINATE))
        parent_key = key
    final_state: dict[str, Any] = {}
    properties: dict[str, bool] = {}
    unavailable = None
    if final_snapshot is not None:
        try:
            _restore(rc, final_snapshot)
            final_state = rc.env.truth_state() if hasattr(rc.env, "truth_state") else {}
            properties = rc.env.truth_properties() if hasattr(rc.env, "truth_properties") else {}
        except FormalLabError as exc:  # a live service that is down: score what can be scored, say why
            final_state, properties = {}, {}
            unavailable = f"final environment state unavailable: {exc.message}"
    reason_enum = termination_reason or {RunStatus.CANCELLED: TerminationReason.CANCELLED,
                                         RunStatus.BUDGET_EXHAUSTED: TerminationReason.BUDGET_EXHAUSTED,
                                         RunStatus.FAILED: TerminationReason.FAILED}.get(status)
    episode = EpisodeRecord(run_id=m.run_id, scenario=m.scenario, status=status, steps=steps,
                            final_truth_state=final_state, final_step=last_step, usage=usage,
                            environment_summary={"properties": properties, "goal": goal_of(rc),
                                                 "capabilities": sorted(rc.env_caps),
                                                 **({"unavailable": unavailable} if unavailable else {})},
                            actor_usage={k: BudgetUsage.model_validate(v) for k, v in (actor_usage or {}).items()},
                            termination_reason=reason_enum, probes=probes or [],
                            backend="SERVICE" if caps.ENV_PERSISTENT_SESSION in rc.env_caps else "PURE_DATA")
    metrics = []
    for ev in rc.evaluators:
        metrics.extend(ev.score(episode))
    events += [
        EventDraft(event_key(m.run_id, None, "metrics"), EventType.METRICS_COMPUTED, last_step,
                   {"metrics": [x.model_dump(mode="json") for x in metrics],
                    "evaluators": [e.descriptor.plugin_id for e in rc.evaluators]}, [parent_key]),
    ]
    terminal_type = TERMINAL_EVENT[status]
    kind = "budget-final" if status == RunStatus.BUDGET_EXHAUSTED else "terminal"
    events.append(EventDraft(event_key(m.run_id, None, kind), terminal_type, last_step,
                             {"status": status.value, "reason": reason,
                              "termination_reason": reason_enum.value if reason_enum else None,
                              "usage": usage.model_dump(), "actor_usage": actor_usage or {},
                              "final_properties": properties},
                             [event_key(m.run_id, None, "metrics")], stage=ExecutionStage.TERMINATE))
    with contextlib.suppress(Exception):  # closing is best effort; the state is already persisted
        rc.env.close()
    return FinishResult(metrics, final_state, properties, events)

