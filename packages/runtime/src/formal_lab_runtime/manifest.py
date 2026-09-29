"""RunManifest construction: pins model, scenario snapshot, driver and plugin versions/digests, turn and
termination semantics, budget and seed — after an explainable capability negotiation (P2-015 / P2-017).

Negotiation runs before the run exists, so an incompatible combination is refused with UNSUPPORTED and reasons:
the model's profile needs a semantic driver, the environment and every strategy must declare the profile, several
participants need an environment with `env.multi_actor`, and each plugin's `requires` (capabilities of its
driver / environment / verifier) must be granted. A verifier without the profile is allowed but recorded as
UNSUPPORTED for that role (checks will answer UNSUPPORTED, the run itself works through the driver).
"""

from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any

from formal_lab_contracts import (
    CapabilityNegotiation,
    ModelPackage,
    Participant,
    PluginInterface,
    PluginPin,
    PluginRef,
    ReleaseRef,
    RunManifest,
    RunStatus,
    ScenarioManifest,
    digest_of,
    utcnow,
)
from formal_lab_contracts import capabilities as caps
from formal_lab_contracts.capabilities import CapabilityRequirement
from formal_lab_contracts.errors import Unsupported, VersionMismatch

from .engine import DEFAULT_VERIFIER
from .registry import CatalogEntry, PluginRegistry

PLATFORM_VERSION = "0.2.0"
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


def _pin(role: str, entry: CatalogEntry) -> PluginPin:
    d = entry.descriptor
    return PluginPin(role=role, plugin_id=d.plugin_id, version=d.version, interface=d.interface,
                     interface_version=d.interface_version, descriptor_digest=digest_of(d))


def _profile_capability(profile: str) -> str:
    return f"{caps.PROFILE_PREFIX}{profile}"


def recovery_path(descriptor: Any) -> str:
    """How an interrupted step is recovered with this environment (P2-050), decided by its declared capabilities."""
    have = {c.id for c in descriptor.capabilities}
    if have & {caps.ENV_PURE_REPLAYABLE, caps.ENV_SNAPSHOT_RESTORE}:
        return "recovery: restore the pre-step snapshot and re-execute (pure-data replay)"
    if {caps.ENV_QUERY_OPERATION, caps.ENV_IDEMPOTENT_STEP} <= have:
        return ("recovery: re-attach to the live session; interrupted operations are looked up by id and re-sent "
                "with the same id only if never received")
    if caps.ENV_QUERY_OPERATION in have:
        return ("recovery: re-attach; interrupted operations are looked up by id — re-sending is not idempotent, so "
                "an operation not found is re-sent at most once more")
    return "recovery: an interrupted operation cannot be settled automatically and will need a manual review"


def negotiate_run(registry: PluginRegistry, *, scenario: ScenarioManifest, package: ModelPackage,
                  participants: list[Participant], driver: CatalogEntry, verifier: CatalogEntry,
                  probes: list[CatalogEntry]) -> list[CapabilityNegotiation]:
    """Capability negotiation of every role. Raises Unsupported (with all reasons) when the run cannot work."""
    profile = package.semantic_profile
    env = registry.resolve(scenario.environment.plugin)
    by_role = {"driver": driver.descriptor, "environment": env.descriptor, "verifier": verifier.descriptor}
    results: list[CapabilityNegotiation] = []
    fatal: list[str] = []

    def needs(entry: CatalogEntry, role: str, reqs: list[CapabilityRequirement], why: dict[str, str]) -> None:
        res = registry.negotiate(entry.descriptor.ref(), reqs, role=role, why=why)
        results.append(res)
        if not res.compatible:
            fatal.extend(res.reasons)

    needs(driver, "driver", [CapabilityRequirement(id=_profile_capability(profile)),
                             CapabilityRequirement(id=caps.DRIVER_CANDIDATES),
                             CapabilityRequirement(id=caps.DRIVER_PREDICT)],
          {_profile_capability(profile): f"the model's profile {profile}"})
    generic = any(c.id == "env.driver_generic" for c in env.descriptor.capabilities)
    # a driver-generic environment simulates any profile through the model's semantic driver
    env_reqs = [CapabilityRequirement(id="env.driver_generic" if generic else _profile_capability(profile))]
    env_why = {_profile_capability(profile): f"simulating/serving a {profile} model",
               "env.driver_generic": f"simulating a {profile} model through its driver"}
    if len(participants) > 1:
        env_reqs.append(CapabilityRequirement(id=caps.ENV_MULTI_ACTOR))
        env_why[caps.ENV_MULTI_ACTOR] = f"{len(participants)} participants taking turns"
    env_reqs += [CapabilityRequirement(id=c, optional=True) for c in
                 (caps.ENV_PURE_REPLAYABLE, caps.ENV_PERSISTENT_SESSION, caps.ENV_QUERY_OPERATION,
                  caps.ENV_OBSERVE_ON_REQUEST)]
    needs(env, "environment", env_reqs, env_why)
    results[-1] = results[-1].model_copy(update={"reasons": [*results[-1].reasons, recovery_path(env.descriptor)]})
    if not ({c.id for c in env.descriptor.capabilities} & {caps.ENV_PURE_REPLAYABLE, caps.ENV_SNAPSHOT_RESTORE,
                                                          caps.ENV_PERSISTENT_SESSION}):
        fatal.append(f"{env.descriptor.plugin_id} declares neither env.pure_replayable nor env.persistent_session: "
                     "the kernel cannot tell how to recover it")
    ver = registry.negotiate(verifier.descriptor.ref(), [CapabilityRequirement(id=_profile_capability(profile))],
                             role="verifier", why={_profile_capability(profile): "bounded checks of this model"})
    if not ver.compatible:  # allowed: checks answer UNSUPPORTED, the driver still decides candidates
        ver = ver.model_copy(update={"reasons": [*ver.reasons, "checks of this model will answer UNSUPPORTED"]})
    results.append(ver)
    for p in participants:
        entry = registry.resolve(p.strategy.plugin)
        d = entry.descriptor
        if d.semantic_profiles and profile not in d.semantic_profiles:
            fatal.append(f"strategy {d.plugin_id} of {p.actor_id} does not support profile {profile} "
                         f"(supports {d.semantic_profiles})")
        reqs = [r for r in d.requires]
        for req in reqs:
            of = str(req.params.get("of", "driver"))
            target = by_role.get(of)
            if target is None:
                continue
            res = registry.negotiate(target.ref(), [CapabilityRequirement(id=req.id, min_version=req.version)],
                                     role=f"{of} for strategy:{p.actor_id}",
                                     why={req.id: f"{d.plugin_id} of {p.actor_id}"})
            results.append(res)
            if not res.compatible:
                fatal.extend(res.reasons)
        results.append(CapabilityNegotiation(plugin_id=d.plugin_id, plugin_version=d.version, compatible=True,
                                             granted=[c.id for c in d.capabilities], role=f"strategy:{p.actor_id}",
                                             verdict="SUPPORTED"))
    for probe in probes:
        results.append(registry.negotiate(probe.descriptor.ref(), [CapabilityRequirement(id=caps.PROBE_METRICS)],
                                          role="probe"))
    env_have = {c.id for c in env.descriptor.capabilities}
    for i, spec in enumerate(scenario.execution_gates):  # phase 3A: pre-execution decisions
        gd = registry.resolve(spec.plugin).descriptor
        if gd.interface != PluginInterface.EXECUTION_GATE:
            fatal.append(f"execution gate {i} ({gd.plugin_id}) is a {gd.interface.value} plugin, not EXECUTION_GATE")
            continue
        if gd.semantic_profiles and profile not in gd.semantic_profiles:
            fatal.append(f"execution gate {gd.plugin_id} does not support profile {profile}")
        res = registry.negotiate(gd.ref(), [CapabilityRequirement(id=caps.GATE_PRE_EXECUTION)], role=f"gate:{i}",
                                 why={caps.GATE_PRE_EXECUTION: "decides before every send of an operation"})
        source = ("values read fresh from the environment right before each send"
                  if caps.ENV_OBSERVE_ON_REQUEST in env_have else
                  "values taken from the actor's current observation (the environment does not answer "
                  "observation requests)")
        results.append(res.model_copy(update={"reasons": [*res.reasons, source]}))
        if not res.compatible:
            fatal.extend(res.reasons)
    if fatal:
        raise Unsupported("the scenario cannot run with these plugins: " + "; ".join(fatal),
                          details={"negotiation": [r.model_dump(mode="json") for r in results], "reasons": fatal})
    return results


def probes_for(registry: PluginRegistry, environment: PluginRef) -> list[CatalogEntry]:
    """Probe plugins that declare they observe this environment (capability probe.metrics, params.environments)."""
    out = []
    for entry in registry.entries(PluginInterface.PROBE):
        for cap in entry.descriptor.capabilities:
            if cap.id == caps.PROBE_METRICS and environment.plugin_id in cap.params.get("environments", []):
                out.append(entry)
    return out


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
    release: ReleaseRef | None = None,
) -> RunManifest:
    if scenario.model.digest != package.digest or scenario.model.version != package.version:
        raise VersionMismatch(f"scenario pins {scenario.model.package_id}@{scenario.model.version} "
                              f"({scenario.model.digest}) but package {package.package_id}@{package.version} "
                              f"({package.digest}) was supplied")
    effective = participants or scenario.participants
    cfg = dict(config or {})
    probe_entries = probes_for(registry, scenario.environment.plugin) if cfg.get("probes", True) else []
    driver_entry = registry.resolve(driver_ref_for_scenario(scenario, package, registry))
    verifier_entry = registry.resolve(verifier or DEFAULT_VERIFIER)
    negotiation = negotiate_run(registry, scenario=scenario, package=package, participants=effective,
                                driver=driver_entry, verifier=verifier_entry, probes=probe_entries)
    pins = [_pin("environment", registry.resolve(scenario.environment.plugin)), _pin("driver", driver_entry)]
    llm = False
    for p in effective:
        entry = registry.resolve(p.strategy.plugin)
        llm |= entry.descriptor.has_capability(caps.PLAN_LLM)
        pins.append(_pin(f"strategy:{p.actor_id}", entry))
    pins.append(_pin("verifier", verifier_entry))
    for i, ref in enumerate(evaluators or [GENERIC_EVALUATOR]):
        pins.append(_pin(f"evaluator:{i}", registry.resolve(ref)))
    for i, entry in enumerate(probe_entries):
        pins.append(_pin(f"probe:{i}", entry))
    for i, spec in enumerate(scenario.execution_gates):
        pins.append(_pin(f"gate:{i}", registry.resolve(spec.plugin)))
    # participants pin the resolved strategy versions too (a scenario may name an older compatible version)
    resolved = {pin.role.split(":", 1)[1]: pin for pin in pins if pin.role.startswith("strategy:")}
    effective = [p.model_copy(update={"strategy": p.strategy.model_copy(update={"plugin": PluginRef(
        plugin_id=resolved[p.actor_id].plugin_id, version=resolved[p.actor_id].version)})}) for p in effective]
    dims = ["steps", "wall_seconds"] + (["model_calls", "tokens"] if llm else [])
    cfg = {"budget_dimensions": dims, **cfg}
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
        turns=scenario.turns,
        termination=scenario.effective_termination(),
        objective=scenario.objective,
        rules=scenario.rules,
        release=release or scenario.release,
        negotiation=negotiation,
    )


def driver_ref_for_scenario(scenario: ScenarioManifest, package: ModelPackage, registry: PluginRegistry) -> PluginRef:
    if scenario.driver is not None:
        return scenario.driver
    return registry.driver_for(package.semantic_profile).descriptor.ref()


def budget_dimensions(manifest: RunManifest) -> list[str]:
    return list(manifest.config.get("budget_dimensions", ["steps", "wall_seconds"]))

