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
"""

from __future__ import annotations

import contextlib
import copy
import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

from formal_lab_contracts import (
    ActionOutcome,
    ActionProposal,
    BeliefState,
    BoundedCheckResult,
    Budget,
    BudgetUsage,
    CandidateAction,
    CheckQuery,
    EffectComparison,
    EnvironmentSnapshot,
    EventType,
    ExecutionStage,
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
    TurnRef,
    TurnState,
    digest_of,
    utcnow,
)
from formal_lab_contracts import capabilities as caps
from formal_lab_contracts.errors import FormalLabError, NonRetryableFailure

from .coordination import Coordinator, InMemoryLedger, OperationLedger
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

    def to_json(self) -> dict[str, Any]:
        return {"turn": self.turn.model_dump(mode="json"), "checkpoints": self.checkpoints,
                "last_outcomes": self.last_outcomes, "actor_usage": self.actor_usage, "flags": self.flags,
                "round_observations": self.round_observations, "last_event_key": self.last_event_key}

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> CarryState:
        return cls(turn=TurnState.model_validate(data["turn"]), checkpoints=data.get("checkpoints", {}),
                   last_outcomes=data.get("last_outcomes", {}), actor_usage=data.get("actor_usage", {}),
                   flags=data.get("flags", {}), round_observations=data.get("round_observations", {}),
                   last_event_key=data.get("last_event_key"))

    def copy(self) -> CarryState:
        return CarryState.from_json(copy.deepcopy(self.to_json()))

    def usage_of(self, actor: str) -> BudgetUsage:
        return BudgetUsage.model_validate(self.actor_usage.get(actor, {}))


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

    def __post_init__(self) -> None:
        self.participants: dict[str, Participant] = {p.actor_id: p for p in self.manifest.participants}
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
    planners = {
        p.actor_id: registry.create(p.strategy.plugin, p.strategy.config, services, expect=PluginInterface.PLANNER)
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
    rules = None
    if manifest.rules is not None and manifest.config.get("rules_enabled", True):
        ruleset = (rulesets or {}).get(manifest.rules.digest.value)
        if ruleset is None:
            raise NonRetryableFailure(f"rule set {manifest.rules.ruleset_id}@{manifest.rules.version} is not "
                                      "available to this runner")
        if hasattr(loaded, "checked"):
            from formal_lab_model.rules import RuleEvaluator

            rules = RuleEvaluator(ruleset, loaded.checked, loaded.interp)
    return RunComponents(manifest, package, env, planners, verifier, evaluators, registry, loaded=loaded,
                         driver_ref=driver_ref, env_caps=env_caps, probes=probes, rules=rules)


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
    elapsed_s: float = 0.0

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
            "elapsed_s": self.elapsed_s,
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
            elapsed_s=data.get("elapsed_s", 0.0),
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
    plan.turn = turn
    actor = turn.actor_id
    tkey = lambda kind: event_key(run_id, step, kind, actor)  # noqa: E731
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
    plan.events.append(EventDraft(tkey("observation"), EventType.OBSERVATION, step,
                                  {"observation": obs.model_dump(mode="json"), "belief": _belief_summary(belief)},
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

    # ---- candidates
    t0 = time.perf_counter()
    participant = rc.participants[actor]
    plan.candidates = rc.loaded.candidates(belief, scope=participant.scope, partial_checker=partial_checker(rc))
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
            holds = bool(goal) and rc.loaded.properties(belief.state).get(goal, False)
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
    proposal = _propose(rc, plan, step, turn, obs, belief, usage, carry)
    if proposal.observation_request is not None and can_request and plan.observation_requests == 0:
        obs, belief = _observe_more(rc, plan, step, turn, proposal.observation_request.paths,
                                    f"strategy: {proposal.observation_request.reason}", tkey("candidates"))
        plan.candidates = rc.loaded.candidates(belief, scope=participant.scope, partial_checker=partial_checker(rc))
        first = plan.usage_delta
        proposal = _propose(rc, plan, step, turn, obs, belief, usage, carry, allow_request=False)
        plan.usage_delta = _sum_usage(first, plan.usage_delta)
    plan.proposal = proposal
    plan.observation = obs
    for call in getattr(planner, "last_calls", []) or []:
        plan.model_calls.append({"call_id": call.call_id, "model": call.model, "request": call.request,
                                 "response": call.raw_text, "input_tokens": call.input_tokens,
                                 "output_tokens": call.output_tokens, "latency_ms": call.latency_ms,
                                 "usage_reported": getattr(call, "usage_reported", True)})
    plan.events.append(EventDraft(tkey("proposal"), EventType.ACTION_PROPOSED, step,
                                  {"proposal": proposal.model_dump(mode="json"),
                                   "model_call_ids": proposal.source.model_call_ids},
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
    last = carry.last_outcomes.get(actor)
    flags = carry.flags.get(actor, {})
    can_request = allow_request and caps.ENV_OBSERVE_ON_REQUEST in rc.env_caps and hasattr(rc.env, "observe_paths")
    context = PlanningContext(
        run_id=m.run_id, step=step, step_id=step_id(m.run_id, step), actor_id=actor, observation=obs,
        action_specs=rc.specs, candidates=plan.candidates, model=m.model, budget=m.budget, usage=usage, seed=m.seed,
        turn=turn, goal=goal_of(rc, actor), objective=m.objective, actor_budget=participant.budget,
        actor_usage=carry.usage_of(actor), participants=list(rc.scheduler.cycle),
        observation_request_allowed=can_request, assumptions=belief.assumptions,
        last_outcome=ActionOutcome.model_validate(last) if last else None,
        replan_requested=flags.get("replan"),
    )
    proposal = rc.planners[actor].propose(context)
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


def _merge_plan_into_carry(carry: CarryState, plan: PlanPhase) -> CarryState:
    new = carry.copy()
    for actor in plan.retired:
        new.turn = CycleScheduler.retire(new.turn, actor)
    if plan.round_observations:
        new.round_observations = dict(plan.round_observations)
    if plan.turn is not None:
        actor = plan.turn.actor_id
        if plan.checkpoint is not None:
            new.checkpoints[actor] = plan.checkpoint
        flags = dict(new.flags.get(actor, {}))
        flags.pop("observe_paths", None)
        flags.pop("replan", None)
        new.flags[actor] = flags
    return new


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
    coordinator = Coordinator(rc.env, rc.env_caps, ledger or InMemoryLedger())
    result = coordinator.execute(proposal, op_id, run_id=run_id, step=step)
    ex.operation = result.record
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
                                     "action": "run ends: the operation outcome cannot be settled automatically"},
                                    [tkey("proposal")], actor, turn, ExecutionStage.RECONCILE))
        ex.terminal, ex.termination_reason = RunStatus.FAILED, TerminationReason.OPERATION_UNRESOLVED
        ex.terminal_reason = f"operation {op_id} unresolved: {result.record.review.note if result.record.review else ''}"
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
    ex.comparison = rc_compare(rc, expected_post=expected_post,
                               pre_state=belief.state, observation=next_obs, written=written,
                               expected_by=f"model:{rc.package.package_id}@{rc.package.version} on belief{unknown_note}",
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
    if ex.comparison.verdict.value == "DIFFERENT":
        last_key = _on_difference(rc, ex, belief, proposal, step, turn, last_key)

    # ---- rules on the outcome
    flags = dict(new.flags.get(actor, {}))
    rejected = flags.get("rejected", 0) + 1 if outcome.status.value == "REJECTED" else 0
    flags["rejected"] = rejected
    different = sum(1 for d in ex.comparison.diffs if d.status == "DIFFERENT")
    after_belief = rc.loaded.belief(next_obs)
    for trigger in ("ACTION_OUTCOME", "EFFECT_COMPARED"):
        decision = _apply_rules(rc, trigger, after_belief, _rule_context(
            next_obs, after_belief, verdict=ex.comparison.verdict.value, outcome=outcome.status.value,
            different=different, step=step, rejected=rejected))
        if decision is None:
            continue
        key = tkey(f"rules-{trigger.lower()}")
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
               probes: list[Any] | None = None) -> FinishResult:
    """Score the episode from the environment's truth and emit metrics + terminal events."""
    from formal_lab_contracts import EpisodeRecord

    m = rc.manifest
    final_state: dict[str, Any] = {}
    properties: dict[str, bool] = {}
    if final_snapshot is not None:
        _restore(rc, final_snapshot)
        final_state = rc.env.truth_state() if hasattr(rc.env, "truth_state") else {}
        properties = rc.env.truth_properties() if hasattr(rc.env, "truth_properties") else {}
    reason_enum = termination_reason or {RunStatus.CANCELLED: TerminationReason.CANCELLED,
                                         RunStatus.BUDGET_EXHAUSTED: TerminationReason.BUDGET_EXHAUSTED,
                                         RunStatus.FAILED: TerminationReason.FAILED}.get(status)
    episode = EpisodeRecord(run_id=m.run_id, scenario=m.scenario, status=status, steps=steps,
                            final_truth_state=final_state, final_step=last_step, usage=usage,
                            environment_summary={"properties": properties, "goal": goal_of(rc),
                                                 "capabilities": sorted(rc.env_caps)},
                            actor_usage={k: BudgetUsage.model_validate(v) for k, v in (actor_usage or {}).items()},
                            termination_reason=reason_enum, probes=probes or [],
                            backend="SERVICE" if caps.ENV_PERSISTENT_SESSION in rc.env_caps else "PURE_DATA")
    metrics = []
    for ev in rc.evaluators:
        metrics.extend(ev.score(episode))
    events = [
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

