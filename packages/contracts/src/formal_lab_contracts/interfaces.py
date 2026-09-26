"""Stable plugin interfaces of formal-lab-contracts/v1.

Every plugin exposes a `descriptor: PluginDescriptor` and implements exactly one of these protocols.
Implementations must be pure with respect to the platform: they receive contract objects and return
contract objects; persistence, eventing and orchestration belong to the platform.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from .common import StateScalar
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
    ModelRef,
    ModelSource,
    Observation,
    PlanningContext,
    PluginDescriptor,
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


@dataclass(frozen=True)
class PluginRegistration:
    """What a plugin module exports (via the `formal_lab.plugins` entry-point group).

    The entry point names a zero-argument callable returning a list of registrations.
    """

    descriptor: PluginDescriptor
    factory: PluginFactory


ENTRY_POINT_GROUP = "formal_lab.plugins"
