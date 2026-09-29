"""Stable plugin interfaces of formal-lab-contracts/v2.

Every plugin exposes a `descriptor: PluginDescriptor` and implements exactly one of these protocols.
Implementations must be pure with respect to the platform: they receive contract objects and return
contract objects; persistence, eventing and orchestration belong to the platform.

v1 protocols are unchanged (a v1 plugin keeps working; it receives v2 objects whose v1 fields keep their meaning).
v2 adds: SemanticDriver (+ LoadedModel), TurnScheduler, optional session/coordination methods of Environment,
Probe, and optional checkpoint/restore of Planner; phase 3A adds ExecutionGate (a decision right before each send).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from .common import StateScalar
from .execution import (
    BeliefState,
    EnvironmentSession,
    EpisodeRecord,
    GateRequest,
    GateResult,
    PlannerCheckpoint,
    ProbeResult,
    TaskPlan,
    TurnState,
)
from .kernel import ActionScope, ObservationRequest, TurnPolicy, TurnRef
from .objects import (
    ActionOutcome,
    ActionProposal,
    ActionSpec,
    ArtifactRef,
    BoundedCheckResult,
    CandidateAction,
    CheckQuery,
    EnvironmentSnapshot,
    GroundAction,
    MetricDefinition,
    MetricResult,
    ModelPackage,
    ModelRef,
    ModelSource,
    Observation,
    PlanningContext,
    PluginDescriptor,
    PreconditionVerdict,
    ScenarioManifest,
)


@runtime_checkable
class Plugin(Protocol):
    descriptor: PluginDescriptor


class PluginServices(Protocol):
    """Resources the platform hands to plugin factories: `create(config, services) -> plugin`."""

    def get_model(self, ref: ModelRef) -> ModelPackage:
        """Load a model package by reference (digest-checked)."""
        ...

    def pinned_model(self) -> ModelPackage:
        """The model package pinned by the current run / scenario."""
        ...

    def get_setting(self, key: str) -> str | None:
        """Deployment setting (e.g. FAL_LLM_BASE_URL); secrets never appear in contract objects."""
        ...

    # v2 (optional for services implementations; plugins must tolerate its absence)
    def loaded_model(self) -> LoadedModel:
        """The pinned model loaded by the run's semantic driver (candidates, predictions, properties)."""
        ...


class PluginFactory(Protocol):
    def __call__(self, config: dict[str, Any], services: PluginServices) -> Plugin: ...


@runtime_checkable
class ModelFrontend(Plugin, Protocol):
    def compile(self, source: ModelSource, *, package_id: str, version: int) -> ModelPackage:
        """Parse, type-check and normalise a source into a versioned ModelPackage (raises InvalidInput)."""
        ...


@runtime_checkable
class Planner(Plugin, Protocol):
    def propose(self, context: PlanningContext) -> ActionProposal:
        """Choose one action for the actor from the observation and candidate set."""
        ...


@runtime_checkable
class CheckpointingPlanner(Planner, Protocol):
    """v2, optional: planners with memory (task plans, caches, RNG) expose it so a fresh process can continue
    exactly where the previous one stopped (P2-041)."""

    def checkpoint(self) -> PlannerCheckpoint | None: ...

    def restore(self, checkpoint: PlannerCheckpoint) -> None: ...

    def current_plan(self) -> TaskPlan | None: ...


@runtime_checkable
class Verifier(Plugin, Protocol):
    def check(
        self,
        package: ModelPackage,
        query: CheckQuery,
        *,
        state: dict[str, StateScalar] | None = None,
        unknown_paths: list[str] | None = None,
    ) -> BoundedCheckResult:
        """Answer a bounded query. Unsupported semantics → verdict UNSUPPORTED (never an exception)."""
        ...


@runtime_checkable
class Environment(Plugin, Protocol):
    def reset(self, scenario: ScenarioManifest, package: ModelPackage, *, run_id: str, seed: int) -> Observation: ...

    def observe(self, actor_id: str) -> Observation: ...

    def step(self, proposal: ActionProposal, *, operation_id: str) -> ActionOutcome: ...

    def snapshot(self) -> EnvironmentSnapshot: ...

    def restore(self, snapshot: EnvironmentSnapshot) -> None: ...

    def close(self) -> None: ...


@runtime_checkable
class SessionEnvironment(Environment, Protocol):
    """v2, optional environment methods, each backed by a declared capability (P2-050):

    - env.persistent_session: `session()` describes the live session; its state is never rolled back.
    - env.query_operation: `query_operation(id)` answers what happened to an operation (None = never seen).
    - env.observe_on_request: `observe_paths(actor, paths)` returns fresh values for the requested locations.
    - env.reset_session / env.state_import: `reset_session(seed)`, `export_state()`, `import_state(state)`.
    """

    def session(self) -> EnvironmentSession: ...

    def query_operation(self, operation_id: str) -> ActionOutcome | None: ...

    def observe_paths(self, actor_id: str, paths: list[str]) -> Observation: ...

    def reset_session(self, *, seed: int) -> Observation: ...

    def export_state(self) -> dict[str, Any]: ...

    def import_state(self, state: dict[str, Any]) -> None: ...


@runtime_checkable
class Probe(Plugin, Protocol):
    """v2: independent observations of a business environment (not the agent's view)."""

    def definitions(self) -> list[MetricDefinition]: ...

    def sample(self, session: EnvironmentSession, *, step: int | None) -> list[ProbeResult]: ...


@runtime_checkable
class ExecutionGate(Plugin, Protocol):
    """Phase 3A: decides right before each send of an operation — first send, re-send after an unknown outcome, and
    re-execution on a pure-data environment — whether it may go ahead. Never consulted when a recorded or queried
    result is reused (no new side effect). DENY → nothing is sent; the action is REJECTED with the gate's reason.

    `paths(action)` names the state locations the gate needs; the kernel reads them right before the send (fresh
    from the environment when it declares env.observe_on_request) and passes them in `GateRequest.values`.
    """

    def paths(self, action: GroundAction) -> list[str]: ...

    def decide(self, request: GateRequest) -> GateResult: ...


# ------------------------------------------------------------------ semantic drivers (v2)


@dataclass
class Prediction:
    """A driver's prediction for one action on a (belief) state."""

    applicable: bool
    reason: str | None
    next_state: dict[str, StateScalar] | None
    written_paths: list[str] = field(default_factory=list)


PartialChecker = Callable[[GroundAction, dict[str, StateScalar], list[str]],
                          tuple[PreconditionVerdict, ObservationRequest | None]]


@runtime_checkable
class LoadedModel(Protocol):
    """A model loaded by its semantic driver: the only way the run kernel reads model semantics (P2-010)."""

    package: ModelPackage

    def action_specs(self) -> list[ActionSpec]: ...

    def state_paths(self) -> list[str]: ...

    def initial_state(self) -> dict[str, StateScalar]: ...

    def belief(self, observation: Observation) -> BeliefState: ...

    def candidates(self, belief: BeliefState, *, scope: ActionScope | None = None,
                   partial_checker: PartialChecker | None = None) -> list[CandidateAction]: ...

    def predict(self, state: dict[str, StateScalar], action: GroundAction) -> Prediction: ...

    def properties(self, state: dict[str, StateScalar]) -> dict[str, bool]: ...

    def property_kinds(self) -> dict[str, str]:
        """property id → "goal" | "invariant"."""
        ...

    def display(self) -> dict[str, Any]:
        """Structure for the UI (entities, state families, actions, properties, graph)."""
        ...


@runtime_checkable
class SemanticDriver(Plugin, Protocol):
    """v2: owns one semantic profile's payload — validation, loading and the semantics the kernel needs."""

    def validate(self, package: ModelPackage) -> list[str]:
        """Problems with the payload (empty when valid)."""
        ...

    def load(self, package: ModelPackage) -> LoadedModel: ...


# ------------------------------------------------------------------ turns (v2)


@runtime_checkable
class TurnScheduler(Protocol):
    """Chooses the next participant and keeps the persistent cursor (P2-030 / P2-031)."""

    policy: TurnPolicy

    def next_turn(self, state: TurnState) -> TurnRef | None:
        """The next turn, or None when no participant can act (all retired)."""
        ...

    def advance(self, state: TurnState, turn: TurnRef, *, acted: bool, progressed: bool) -> TurnState: ...


@runtime_checkable
class Evaluator(Plugin, Protocol):
    def metric_definitions(self) -> list[MetricDefinition]: ...

    def score(self, episode: EpisodeRecord) -> list[MetricResult]: ...


@runtime_checkable
class ArtifactStore(Protocol):
    def put(self, data: bytes, *, name: str, media_type: str, format_version: str) -> ArtifactRef: ...

    def get(self, ref: ArtifactRef) -> bytes: ...

    def describe(self) -> dict[str, Any]: ...


@dataclass(frozen=True)
class PluginRegistration:
    """What a plugin module exports (via the `formal_lab.plugins` entry-point group).

    The entry point names a zero-argument callable returning a list of registrations.
    """

    descriptor: PluginDescriptor
    factory: PluginFactory


ENTRY_POINT_GROUP = "formal_lab.plugins"
