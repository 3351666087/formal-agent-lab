"""formal-lab-contracts/v1 → v2 adapters (P2-013 / P2-014).

Every reader in the platform (database rows, API inputs, replay bundles, plugin catalogs) passes stored JSON
through `upgrade(kind, data)`. v1 data is first validated against the frozen v1 contract — so it keeps its exact
v1 meaning — and then mapped to v2:

- ModelPackage: `ir` becomes `payload = {kind: fal-ir, ir}`; the digest is unchanged (v2 canonical form of a v1
  model is byte-identical, see `ir.canonical_ir_dump`).
- ScenarioManifest / RunManifest: new fields take their defaults; the v1 stop conditions stay and are interpreted
  by `ScenarioManifest.effective_termination()` exactly as in phase 1. A RunManifest also records that
  termination explicitly.
- BoundedCheckResult: contract_version bumped; verdicts and semantics identical.
- FieldDiff (inside outcomes / comparisons): v1 UNKNOWN fields get evidence `unknown` / freshness MISSING, observed
  fields `observed` / FRESH — the evidence vocabulary of v2 made explicit, nothing re-interpreted.
- PluginDescriptor: v1 descriptors remain valid v2 descriptors (contract v1, interface version 1).
- TraceEvent: the envelope is unchanged; `upgrade_event_payload` upgrades embedded objects per event type.

v2 JSON passes through `model_validate` unchanged. Anything else raises VersionMismatch.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from .common import CONTRACT_VERSION, CONTRACT_VERSION_V1
from .errors import InvalidInput, VersionMismatch
from .execution import EpisodeRecord, StepRecord
from .ir import canonical_ir_dump
from .objects import (
    ActionOutcome,
    ActionProposal,
    BoundedCheckResult,
    EffectComparison,
    MetricResult,
    ModelIR,
    ModelPackage,
    Observation,
    PluginDescriptor,
    RunManifest,
    ScenarioManifest,
    TraceEvent,
)


def version_of(data: dict[str, Any], kind: str | None = None) -> str:
    """Contract version of a stored object; objects without the field are v1 when they carry v1-only shapes."""
    declared = data.get("contract_version")
    if declared:
        return str(declared)
    if kind == "ModelPackage" and "ir" in data and "payload" not in data:
        return CONTRACT_VERSION_V1
    return CONTRACT_VERSION


def _v1():
    from .v1 import objects as v1objects

    return v1objects


def _check_v1(model_name: str, data: dict[str, Any]) -> dict[str, Any]:
    """Validate against the frozen v1 contract and return its canonical JSON dump."""
    cls = getattr(_v1(), model_name)
    try:
        return cls.model_validate(data).model_dump(mode="json")
    except Exception as exc:  # pydantic.ValidationError
        raise InvalidInput(f"invalid formal-lab-contracts/v1 {model_name}: {exc}") from exc


# ------------------------------------------------------------------------ per-kind upgrades


def _field_diffs(comparison: dict[str, Any] | None) -> dict[str, Any] | None:
    if not comparison:
        return comparison
    out = dict(comparison)
    diffs = []
    for d in comparison.get("diffs", []):
        d = dict(d)
        if "evidence" not in d:
            unknown = d.get("status") == "UNKNOWN"
            d["evidence"] = "unknown" if unknown else "observed"
            d["freshness"] = "MISSING" if unknown else "FRESH"
            d.setdefault("observed_at_step", None)
        diffs.append(d)
    out["diffs"] = diffs
    if "evidence_counts" not in out:
        counts: dict[str, int] = {}
        for d in diffs:
            counts[d["evidence"]] = counts.get(d["evidence"], 0) + 1
        out["evidence_counts"] = counts
    return out


def upgrade_model_package(data: dict[str, Any]) -> ModelPackage:
    if version_of(data, "ModelPackage") == CONTRACT_VERSION:
        return ModelPackage.model_validate(data)
    v1 = _check_v1("ModelPackage", data)
    ir = v1.pop("ir")
    v1["payload"] = {"kind": "fal-ir", "ir": ir}
    v1["contract_version"] = CONTRACT_VERSION
    package = ModelPackage.model_validate(v1)
    from .common import digest_of

    recomputed = digest_of(canonical_ir_dump(ModelIR.model_validate(ir)))
    if recomputed != package.digest:
        raise VersionMismatch(f"v1 package {package.package_id}@{package.version}: digest {package.digest.value} "
                              f"does not match its IR ({recomputed.value})")
    return package


def upgrade_scenario(data: dict[str, Any]) -> ScenarioManifest:
    if version_of(data) == CONTRACT_VERSION:
        return ScenarioManifest.model_validate(data)
    v1 = _check_v1("ScenarioManifest", data)
    v1["contract_version"] = CONTRACT_VERSION
    return ScenarioManifest.model_validate(v1)


def upgrade_run_manifest(data: dict[str, Any]) -> RunManifest:
    if version_of(data) == CONTRACT_VERSION:
        return RunManifest.model_validate(data)
    v1 = _check_v1("RunManifest", data)
    scenario = upgrade_scenario(v1["scenario"])
    v1["scenario"] = scenario.model_dump(mode="json")
    v1["contract_version"] = CONTRACT_VERSION
    v1["termination"] = scenario.effective_termination().model_dump(mode="json")
    return RunManifest.model_validate(v1)


def upgrade_check_result(data: dict[str, Any]) -> BoundedCheckResult:
    if version_of(data) == CONTRACT_VERSION:
        return BoundedCheckResult.model_validate(data)
    v1 = _check_v1("BoundedCheckResult", data)
    v1["contract_version"] = CONTRACT_VERSION
    return BoundedCheckResult.model_validate(v1)


def upgrade_outcome(data: dict[str, Any]) -> ActionOutcome:
    data = dict(data)
    data["effect_comparison"] = _field_diffs(data.get("effect_comparison"))
    return ActionOutcome.model_validate(data)


def upgrade_comparison(data: dict[str, Any]) -> EffectComparison:
    return EffectComparison.model_validate(_field_diffs(data))


def upgrade_plugin_descriptor(data: dict[str, Any]) -> PluginDescriptor:
    return PluginDescriptor.model_validate(data)


UPGRADERS: dict[str, Callable[[dict[str, Any]], BaseModel]] = {
    "ModelPackage": upgrade_model_package,
    "ScenarioManifest": upgrade_scenario,
    "RunManifest": upgrade_run_manifest,
    "BoundedCheckResult": upgrade_check_result,
    "ActionOutcome": upgrade_outcome,
    "EffectComparison": upgrade_comparison,
    "PluginDescriptor": upgrade_plugin_descriptor,
    "Observation": Observation.model_validate,
    "ActionProposal": ActionProposal.model_validate,
    "MetricResult": MetricResult.model_validate,
    "TraceEvent": TraceEvent.model_validate,
    "StepRecord": StepRecord.model_validate,
    "EpisodeRecord": EpisodeRecord.model_validate,
}


def upgrade(kind: str, data: dict[str, Any]) -> BaseModel:
    """Validate stored JSON of contract type `kind` (v1 or v2) and return the v2 object."""
    if kind not in UPGRADERS:
        raise InvalidInput(f"no upgrade path for {kind}")
    declared = data.get("contract_version") if isinstance(data, dict) else None
    if declared and declared not in (CONTRACT_VERSION, CONTRACT_VERSION_V1):
        raise VersionMismatch(f"{kind} uses {declared}; this reader speaks v1 (via adapters) and v2")
    return UPGRADERS[kind](data)


# ------------------------------------------------------------------------ event payloads

_PAYLOAD_OBJECTS: dict[str, list[tuple[str, str]]] = {
    "RUN_CREATED": [("manifest", "RunManifest")],
    "OBSERVATION": [("observation", "Observation")],
    "ACTION_PROPOSED": [("proposal", "ActionProposal")],
    "CHECK_COMPLETED": [("result", "BoundedCheckResult")],
    "ACTION_OUTCOME": [("outcome", "ActionOutcome")],
    "EFFECT_COMPARED": [("comparison", "EffectComparison"), ("observation_after", "Observation")],
}


def upgrade_event_payload(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Payload with its embedded contract objects upgraded to v2 JSON (other keys untouched)."""
    specs = _PAYLOAD_OBJECTS.get(str(event_type))
    if not specs:
        return payload
    out = dict(payload)
    for key, kind in specs:
        if isinstance(out.get(key), dict):
            out[key] = upgrade(kind, out[key]).model_dump(mode="json")
    if str(event_type) == "METRICS_COMPUTED":
        out["metrics"] = [MetricResult.model_validate(m).model_dump(mode="json") for m in out.get("metrics", [])]
    return out


def upgrade_event(data: dict[str, Any]) -> TraceEvent:
    event = TraceEvent.model_validate(data)
    return event.model_copy(update={"payload": upgrade_event_payload(str(event.event_type), event.payload)})
