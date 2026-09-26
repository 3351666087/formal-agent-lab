"""RunManifest construction: pins model, scenario snapshot, plugin versions/digests, budget and seed."""

from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any

from formal_lab_contracts import (
    ModelPackage,
    Participant,
    PluginPin,
    PluginRef,
    RunManifest,
    RunStatus,
    ScenarioManifest,
    digest_of,
    utcnow,
)
from formal_lab_contracts import capabilities as caps
from formal_lab_contracts.errors import InvalidInput, VersionMismatch

from .engine import DEFAULT_VERIFIER
from .registry import PluginRegistry

PLATFORM_VERSION = "0.1.0"
GENERIC_EVALUATOR = PluginRef(plugin_id="formal-lab.eval.generic", version="1.0.0")


@lru_cache(maxsize=1)
def source_revision() -> str | None:
    try:
        root = Path(__file__).resolve().parents[4]
        rev = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True,
                             timeout=5, check=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(root), "status", "--porcelain"], capture_output=True, text=True,
                               timeout=5, check=True).stdout.strip()
        return rev + ("+dirty" if dirty else "")
    except Exception:
        import os

        return os.environ.get("FAL_SOURCE_REVISION")


def _pin(registry: PluginRegistry, role: str, ref: PluginRef) -> PluginPin:
    entry = registry.get(ref)
    d = entry.descriptor
    return PluginPin(role=role, plugin_id=d.plugin_id, version=d.version, interface=d.interface,
                     interface_version=d.interface_version, descriptor_digest=digest_of(d))


def make_manifest(
    *,
    run_id: str,
    project_id: str,
    scenario: ScenarioManifest,
    package: ModelPackage,
    registry: PluginRegistry,
    participants: list[Participant] | None = None,
    evaluators: list[PluginRef] | None = None,
    verifier: PluginRef | None = None,
    config: dict[str, Any] | None = None,
    source_run_id: str | None = None,
    matrix_id: str | None = None,
    seed: int | None = None,
    budget: Any = None,
) -> RunManifest:
    if scenario.model.digest != package.digest or scenario.model.version != package.version:
        raise VersionMismatch(f"scenario pins {scenario.model.package_id}@{scenario.model.version} "
                              f"({scenario.model.digest}) but package {package.package_id}@{package.version} "
                              f"({package.digest}) was supplied")
    effective = participants or scenario.participants
    pins = [_pin(registry, "environment", scenario.environment.plugin)]
    llm = False
    for p in effective:
        pin = _pin(registry, f"strategy:{p.actor_id}", p.strategy.plugin)
        llm |= registry.get(p.strategy.plugin).descriptor.has_capability(caps.PLAN_LLM)
        pins.append(pin)
    pins.append(_pin(registry, "verifier", verifier or DEFAULT_VERIFIER))
    for i, ref in enumerate(evaluators or [GENERIC_EVALUATOR]):
        pins.append(_pin(registry, f"evaluator:{i}", ref))
    env_desc = registry.get(scenario.environment.plugin).descriptor
    if package.semantic_profile not in env_desc.semantic_profiles:
        raise InvalidInput(f"environment {env_desc.plugin_id} does not support profile {package.semantic_profile}")
    dims = ["steps", "wall_seconds"] + (["model_calls", "tokens"] if llm else [])
    cfg = {"budget_dimensions": dims, **(config or {})}
    return RunManifest(
        run_id=run_id,
        project_id=project_id,
        created_at=utcnow(),
        scenario=scenario,
        scenario_digest=digest_of(scenario),
        model=package.ref(),
        plugins=pins,
        participants=effective,
        config=cfg,
        budget=budget or scenario.budget,
        seed=scenario.seed if seed is None else seed,
        status=RunStatus.CREATED,
        source_run_id=source_run_id,
        matrix_id=matrix_id,
        platform={"version": PLATFORM_VERSION, "source_revision": source_revision()},
    )
