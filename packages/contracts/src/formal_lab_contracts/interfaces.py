"""Stable plugin interfaces of formal-lab-contracts/v1.

Every plugin exposes a `descriptor: PluginDescriptor` and implements exactly one of these protocols.
Implementations must be pure with respect to the platform: they receive contract objects and return
contract objects; persistence, eventing and orchestration belong to the platform.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from .objects import (
    ActionOutcome,
    ActionProposal,
    ArtifactRef,
    BoundedCheckResult,
    CheckQuery,
    EnvironmentSnapshot,
    EpisodeRecord,
    MetricDefinition,
    MetricResult,
    ModelPackage,
    ModelSource,
    Observation,
    PlanningContext,
    PluginDescriptor,
    ScenarioManifest,
)
from .common import StateScalar


@runtime_checkable
class Plugin(Protocol):
    descriptor: PluginDescriptor


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
class Evaluator(Plugin, Protocol):
    def metric_definitions(self) -> list[MetricDefinition]: ...

    def score(self, episode: EpisodeRecord) -> list[MetricResult]: ...


@runtime_checkable
class ArtifactStore(Protocol):
    def put(self, data: bytes, *, name: str, media_type: str, format_version: str) -> ArtifactRef: ...

    def get(self, ref: ArtifactRef) -> bytes: ...

    def describe(self) -> dict[str, Any]: ...
