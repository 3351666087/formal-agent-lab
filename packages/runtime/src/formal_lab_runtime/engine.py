"""Step engine shared by every entry point (Temporal activities, local runner, SDK, Inspect adapter).

It is persistence-agnostic: it restores the environment from a snapshot, executes exactly one logical step
and returns everything that must be persisted (events, snapshot, outcome, usage). Identifiers are derived
from (run_id, step), so a retried step produces the same ids and idempotency keys.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

from formal_lab_contracts import (
    ActionOutcome,
    ActionProposal,
    BoundedCheckResult,
    Budget,
    BudgetUsage,
    CandidateAction,
    CheckQuery,
    EffectComparison,
    EnvironmentSnapshot,
    EventType,
    GroundAction,
    ModelPackage,
    ModelUsage,
    Observation,
    PlanningContext,
    PluginInterface,
    PluginRef,
    PreconditionVerdict,
    RunManifest,
    RunStatus,
    StopConditionKind,
)
from formal_lab_contracts.errors import FormalLabError, NonRetryableFailure
from formal_lab_model import Interpreter, action_specs, check_model, compare_effects
from formal_lab_model.belief import Belief, belief_from_observation

from .registry import PluginRegistry
from .settings import get_setting

DEFAULT_VERIFIER = PluginRef(plugin_id="formal-lab.verifier.z3-bmc", version="1.0.0")


def step_id(run_id: str, step: int) -> str:
    return f"{run_id}:s{step}"


def event_key(run_id: str, step: int | None, kind: str) -> str:
    return f"{run_id}:{'run' if step is None else f's{step}'}:{kind}"


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

    @property
    def event_id(self) -> str:
        return event_id_for(self.key)

    @property
    def payload_schema(self) -> str:
        return f"formal-lab/events/{self.event_type.value}@1"


class RuntimeServices:
    """PluginServices implementation handed to plugin factories."""

    def __init__(self, package: ModelPackage, packages: dict[str, ModelPackage] | None = None):
        self._package = package
        self._packages = packages or {}

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


@dataclass
class RunComponents:
    manifest: RunManifest
    package: ModelPackage
    env: Any
    planners: dict[str, Any]
    verifier: Any
    evaluators: list[Any]
    registry: PluginRegistry

    def __post_init__(self) -> None:
        self.checked = check_model(self.package.ir)
        self.interp = Interpreter(self.checked)
        self.specs = action_specs(self.checked)
        self.actor_id = self.manifest.participants[0].actor_id

    @property
    def run_id(self) -> str:
        return self.manifest.run_id


def plugin_ref_for(manifest: RunManifest, role: str) -> PluginRef | None:
    for pin in manifest.plugins:
        if pin.role == role:
            return PluginRef(plugin_id=pin.plugin_id, version=pin.version)
    return None


def open_components(manifest: RunManifest, package: ModelPackage, registry: PluginRegistry) -> RunComponents:
    if package.digest != manifest.model.digest:
        raise NonRetryableFailure("model package digest differs from the run manifest (version drift)")
    services = RuntimeServices(package)
    scenario = manifest.scenario
    env = registry.create(scenario.environment.plugin, scenario.environment.config, services,
                          expect=PluginInterface.ENVIRONMENT)
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
    return RunComponents(manifest, package, env, planners, verifier, evaluators, registry)


# ---------------------------------------------------------------------------- start


@dataclass
class StartResult:
    observation: Observation
    snapshot: EnvironmentSnapshot
    initial_check: BoundedCheckResult | None
    events: list[EventDraft]


def start_run(rc: RunComponents) -> StartResult:
    m = rc.manifest
    obs = rc.env.reset(m.scenario, rc.package, run_id=m.run_id, seed=m.seed)
    events = [
        EventDraft(event_key(m.run_id, None, "started"), EventType.RUN_STARTED, 0,
                   {"manifest_digest": _digest(m.model_dump(mode="json")), "seed": m.seed,
                    "budget": m.budget.model_dump(exclude_none=True),
                    "budget_dimensions": m.config.get("budget_dimensions", [])},
                   [event_key(m.run_id, None, "queued")]),
        EventDraft(event_key(m.run_id, 0, "observation"), EventType.OBSERVATION, 0,
                   {"observation": obs.model_dump(mode="json")}, [event_key(m.run_id, None, "started")],
                   rc.actor_id),
    ]
    check = None
    horizon = int(m.config.get("initial_check_horizon", 16))
    goal = _goal_property(rc)
    if goal and horizon > 0:
        belief = belief_from_observation(obs, rc.checked)
        check = rc.verifier.check(
            rc.package,
            CheckQuery(kind="GOAL_REACHABILITY", property_id=goal, initial_state="GIVEN_STATE",
                       bound={"max_steps": horizon, "timeout_ms": int(m.config.get("check_timeout_ms", 20000))}),
            state=belief.state,
        )
        events.append(EventDraft(event_key(m.run_id, 0, "initial-check"), EventType.CHECK_COMPLETED, 0,
                                 {"purpose": "initial goal reachability from the actor's belief",
                                  "result": check.model_dump(mode="json")},
                                 [event_key(m.run_id, 0, "observation")]))
    snap = rc.env.snapshot()
    events.append(EventDraft(event_key(m.run_id, 0, "snapshot"), EventType.STATE_SNAPSHOT, 0,
                             {"snapshot_digest": snap.digest.value, "state_revision": snap.state_revision},
                             [event_key(m.run_id, 0, "observation")]))
    return StartResult(obs, snap, check, events)


def _goal_property(rc: RunComponents) -> str | None:
    for sc in rc.manifest.scenario.stop_conditions:
        if sc.kind == StopConditionKind.GOAL_REACHED and sc.property_id:
            return sc.property_id
    for obj in rc.manifest.scenario.objectives:
        if obj.property_id:
            return obj.property_id
    return None


# ---------------------------------------------------------------------------- budget


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


# ---------------------------------------------------------------------------- step


@dataclass
class StepExecution:
    step: int
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
    events: list[EventDraft] = field(default_factory=list)
    model_calls: list[dict[str, Any]] = field(default_factory=list)
    properties: dict[str, bool] = field(default_factory=dict)
    elapsed_s: float = 0.0


def compute_candidates(rc: RunComponents, belief: Belief) -> list[CandidateAction]:
    labels = {s.action_type: s.label for s in rc.specs}
    out: list[CandidateAction] = []
    for ga in rc.checked.ground_actions:
        action = GroundAction(action_type=ga.action, params=dict(ga.params))
        if not belief.unknown_paths:
            verdict = PreconditionVerdict.APPLICABLE if rc.interp.step(ga, belief.state).applicable \
                else PreconditionVerdict.INAPPLICABLE
        else:
            res = rc.verifier.check(
                rc.package,
                CheckQuery(kind="ACTION_PRECONDITION", action=action, initial_state="GIVEN_STATE",
                           bound={"max_steps": 0, "timeout_ms": 5000}),
                state=belief.state, unknown_paths=belief.unknown_paths,
            )
            verdict = PreconditionVerdict(str(res.verdict))
        out.append(CandidateAction(action=action, label=labels.get(ga.action), belief_applicability=verdict))
    return out


def execute_step(rc: RunComponents, snapshot: EnvironmentSnapshot, step: int, usage: BudgetUsage) -> StepExecution:
    """Execute logical step `step` starting from `snapshot` (the state after step-1)."""
    t0 = time.perf_counter()
    m = rc.manifest
    run_id, sid = m.run_id, step_id(m.run_id, step)
    ex = StepExecution(step=step)
    dims = list(m.config.get("budget_dimensions", ["steps", "wall_seconds"]))
    reason = budget_exhausted(m.budget, usage, dims)
    if reason:
        ex.terminal, ex.terminal_reason = RunStatus.BUDGET_EXHAUSTED, reason  # terminal event emitted by finish_run
        return ex

    rc.env.restore(snapshot)
    prev_key = event_key(run_id, step - 1, "comparison") if step > 1 else event_key(run_id, 0, "observation")
    obs = rc.env.observe(rc.actor_id)
    ex.observation = obs
    belief = belief_from_observation(obs, rc.checked)
    ex.events.append(EventDraft(event_key(run_id, step, "observation"), EventType.OBSERVATION, step,
                                {"observation": obs.model_dump(mode="json"),
                                 "belief": {"unknown_paths": belief.unknown_paths, "stale_paths": belief.stale_paths}},
                                [prev_key], rc.actor_id))

    ex.candidates = compute_candidates(rc, belief)
    counts = {v.value: sum(c.belief_applicability == v for c in ex.candidates) for v in PreconditionVerdict}
    ex.events.append(EventDraft(event_key(run_id, step, "candidates"), EventType.CANDIDATES, step,
                                {"candidates": [c.model_dump(mode="json") for c in ex.candidates], "counts": counts},
                                [event_key(run_id, step, "observation")], rc.actor_id))
    viable = [c for c in ex.candidates if c.belief_applicability in (PreconditionVerdict.APPLICABLE,
                                                                     PreconditionVerdict.UNKNOWN)]
    if not viable and any(sc.kind == StopConditionKind.NO_APPLICABLE_ACTION for sc in m.scenario.stop_conditions):
        ex.terminal, ex.terminal_reason = RunStatus.FAILED, "no applicable action on the actor's belief"
        ex.snapshot = rc.env.snapshot()
        ex.elapsed_s = time.perf_counter() - t0
        return ex

    context = PlanningContext(run_id=run_id, step=step, step_id=sid, actor_id=rc.actor_id, observation=obs,
                              action_specs=rc.specs, candidates=ex.candidates, model=m.model, budget=m.budget,
                              usage=usage, seed=m.seed)
    planner = rc.planners[rc.actor_id]
    proposal = planner.propose(context)
    ex.proposal = proposal
    ex.usage_delta = proposal.usage
    for call in getattr(planner, "last_calls", []) or []:
        ex.model_calls.append({"call_id": call.call_id, "model": call.model, "request": call.request,
                               "response": call.raw_text, "input_tokens": call.input_tokens,
                               "output_tokens": call.output_tokens, "latency_ms": call.latency_ms})
    ex.events.append(EventDraft(event_key(run_id, step, "proposal"), EventType.ACTION_PROPOSED, step,
                                {"proposal": proposal.model_dump(mode="json"),
                                 "model_call_ids": proposal.source.model_call_ids},
                                [event_key(run_id, step, "candidates")], rc.actor_id))

    ex.precheck = rc.verifier.check(
        rc.package,
        CheckQuery(kind="ACTION_PRECONDITION", action=proposal.action, initial_state="GIVEN_STATE",
                   bound={"max_steps": 0, "timeout_ms": 5000}),
        state=belief.state, unknown_paths=belief.unknown_paths,
    )
    ex.events.append(EventDraft(event_key(run_id, step, "check"), EventType.CHECK_COMPLETED, step,
                                {"purpose": "precondition of the proposed action on the actor's belief",
                                 "result": ex.precheck.model_dump(mode="json")},
                                [event_key(run_id, step, "proposal")]))

    try:
        ga = rc.interp.ground(proposal.action.action_type, dict(proposal.action.params))
        predicted = rc.interp.step(ga, belief.state)
        expected_post = predicted.next_state if predicted.applicable else dict(belief.state)
        written = sorted({p for p, _ in predicted.writes}) if predicted.applicable else []
    except KeyError:
        expected_post, written = None, []

    op_id = f"{sid}:apply"
    outcome = rc.env.step(proposal, operation_id=op_id)
    next_obs = rc.env.observe(rc.actor_id)
    ex.snapshot = rc.env.snapshot()
    ex.comparison = compare_effects(
        expected_post=expected_post, pre_state=belief.state, observation=next_obs, written_paths=written,
        expected_by=f"model:{rc.package.package_id}@{rc.package.version} on belief"
        + (f" ({len(belief.unknown_paths)} unknown)" if belief.unknown_paths else ""),
    )
    outcome = outcome.model_copy(update={"effect_comparison": ex.comparison})
    ex.outcome = outcome
    ex.properties = dict(outcome.result.get("properties", {}))
    ex.events.append(EventDraft(event_key(run_id, step, "outcome"), EventType.ACTION_OUTCOME, step,
                                {"outcome": outcome.model_dump(mode="json"), "snapshot_digest": ex.snapshot.digest.value,
                                 "state_revision": ex.snapshot.state_revision},
                                [event_key(run_id, step, "proposal"), event_key(run_id, step, "check")], rc.actor_id))
    ex.events.append(EventDraft(event_key(run_id, step, "comparison"), EventType.EFFECT_COMPARED, step,
                                {"comparison": ex.comparison.model_dump(mode="json"),
                                 "observation_after": next_obs.model_dump(mode="json")},
                                [event_key(run_id, step, "outcome")], rc.actor_id))

    for sc in m.scenario.stop_conditions:
        if sc.kind == StopConditionKind.GOAL_REACHED and sc.property_id and ex.properties.get(sc.property_id):
            ex.terminal, ex.terminal_reason = RunStatus.SUCCEEDED, f"goal {sc.property_id!r} reached"
        elif (sc.kind == StopConditionKind.INVARIANT_VIOLATED and sc.property_id
              and ex.properties.get(sc.property_id) is False):
            ex.terminal, ex.terminal_reason = RunStatus.FAILED, f"invariant {sc.property_id!r} violated"
    ex.elapsed_s = time.perf_counter() - t0
    return ex


def failure_status(exc: BaseException) -> tuple[RunStatus, str]:
    if isinstance(exc, FormalLabError):
        return RunStatus.FAILED, f"{exc.code}: {exc.message}"
    return RunStatus.FAILED, f"{type(exc).__name__}: {exc}"


def _digest(obj: Any) -> str:
    from formal_lab_contracts import digest_of

    return digest_of(obj).value


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
               usage: BudgetUsage, steps: list[Any], last_step: int, parent_key: str) -> FinishResult:
    """Score the episode from the simulator truth state and emit metrics + terminal events."""
    from formal_lab_contracts import EpisodeRecord

    m = rc.manifest
    final_state: dict[str, Any] = {}
    properties: dict[str, bool] = {}
    if final_snapshot is not None:
        rc.env.restore(final_snapshot)
        final_state = rc.env.truth_state() if hasattr(rc.env, "truth_state") else {}
        properties = rc.env.truth_properties() if hasattr(rc.env, "truth_properties") else {}
    episode = EpisodeRecord(run_id=m.run_id, scenario=m.scenario, status=status, steps=steps,
                            final_truth_state=final_state, final_step=last_step, usage=usage,
                            environment_summary={"properties": properties, "goal": _goal_property(rc)})
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
                             {"status": status.value, "reason": reason, "usage": usage.model_dump(),
                              "final_properties": properties},
                             [event_key(m.run_id, None, "metrics")]))
    try:
        rc.env.close()
    except Exception:  # closing is best effort; the state is already persisted
        pass
    return FinishResult(metrics, final_state, properties, events)
