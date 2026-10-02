"""Generate contracts/v2 JSON Schemas and the contract digest from the Pydantic source of truth.

    python -m formal_lab_contracts.schema_export --out contracts/v2 --v1-out contracts/v1

contracts/v1 is regenerated from the frozen `formal_lab_contracts.v1` sub-package (it must never change).
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from pydantic import BaseModel
from pydantic.json_schema import models_json_schema

from . import errors, execution, governance, ir, kernel, objects
from .common import CONTRACT_VERSION, ArtifactRef, EvidenceRef, Extension

# The objects named in the phase-1 task book (v2 content, same names and meaning) …
FROZEN_OBJECTS: list[type[BaseModel]] = [
    objects.PluginDescriptor,
    objects.ModelPackage,
    objects.ScenarioManifest,
    objects.Observation,
    objects.ActionSpec,
    objects.ActionProposal,
    objects.ActionOutcome,
    objects.BoundedCheckResult,
    objects.TraceEvent,
    ArtifactRef,
    objects.MetricDefinition,
    objects.MetricResult,
    objects.RunManifest,
]
# … the objects introduced by phase 2 …
V2_OBJECTS: list[type[BaseModel]] = [
    kernel.ObjectiveSpec,
    kernel.TurnPolicy,
    kernel.TerminationPolicy,
    kernel.AssumptionSet,
    execution.BeliefState,
    execution.TurnState,
    execution.TaskPlan,
    execution.PlannerCheckpoint,
    execution.EnvironmentSession,
    execution.OperationRecord,
    execution.ExecutionDecision,
    execution.BatchRecord,
    execution.StageRecord,
    execution.ProbeResult,
    execution.QueryBundle,
    governance.RuleSet,
    governance.RuleEvaluation,
    governance.RuleDecision,
    governance.ModelReleaseRecord,
    governance.CapabilityReport,
    governance.ReleaseConfig,
    governance.RegressionCase,
    governance.MatrixCellSpec,
]
# … and supporting types.
SUPPORTING: list[type[BaseModel]] = [
    ir.ModelIR,
    objects.IRPayload,
    objects.NamespacedPayload,
    objects.CheckQuery,
    objects.PlanningContext,
    objects.CandidateAction,
    objects.EnvironmentSnapshot,
    execution.StepRecord,
    execution.EpisodeRecord,
    objects.BudgetUsage,
    errors.ErrorInfo,
    kernel.CapabilityRequirement,
    kernel.CapabilityNegotiation,
    kernel.TurnRef,
    kernel.OptimizationResult,
    kernel.RobustnessResult,
    kernel.ObservationRequest,
    execution.GateRequest,
    execution.ExecutionContext,
    execution.AutomaticAction,
    execution.GateResult,
    execution.ConditionCheck,
    governance.FeatureSupport,
    execution.BatchMember,
    objects.ParticipantView,
    EvidenceRef,
    Extension,
]
ALL_MODELS = FROZEN_OBJECTS + V2_OBJECTS + SUPPORTING
BASE_URL = "https://formal-lab.dev/contracts/v2"


def _dump(obj: object) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def build_schemas() -> dict[str, str]:
    """Return {relative file name: file content}."""
    files: dict[str, str] = {}
    for model in ALL_MODELS:
        schema = model.model_json_schema(mode="validation")
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        schema["$id"] = f"{BASE_URL}/{model.__name__}.schema.json"
        files[f"schemas/{model.__name__}.schema.json"] = _dump(schema)

    _, bundle = models_json_schema([(m, "validation") for m in ALL_MODELS], ref_template="#/$defs/{model}")
    files["bundle.schema.json"] = _dump({
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"{BASE_URL}/bundle.schema.json",
        "title": "FormalLabContractsV2",
        "description": f"{CONTRACT_VERSION}: all contract types (generated, do not edit)",
        "type": "object",
        "properties": {m.__name__: {"$ref": f"#/$defs/{m.__name__}"} for m in ALL_MODELS},
        "$defs": bundle["$defs"],
    })
    # Serialization view: what the platform emits (fields with defaults are always present). TypeScript types
    # for consumers are generated from this view; validators use the validation bundle above.
    _, out_bundle = models_json_schema([(m, "serialization") for m in ALL_MODELS], ref_template="#/$defs/{model}")
    files["bundle.serialization.schema.json"] = _dump({
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"{BASE_URL}/bundle.serialization.schema.json",
        "title": "FormalLabContractsV2",
        "description": f"{CONTRACT_VERSION}: all contract types as serialized by the platform (generated, do not edit)",
        "type": "object",
        "properties": {m.__name__: {"$ref": f"#/$defs/{m.__name__}"} for m in ALL_MODELS},
        "$defs": out_bundle["$defs"],
    })
    files["objects.json"] = _dump(
        {
            "contract_version": CONTRACT_VERSION,
            "compatible_with": ["formal-lab-contracts/v1 (read through formal_lab_contracts.compat)"],
            "frozen_objects": [m.__name__ for m in FROZEN_OBJECTS],
            "v2_objects": [m.__name__ for m in V2_OBJECTS],
            "supporting_types": [m.__name__ for m in SUPPORTING],
            "error_codes": [c.value for c in errors.ErrorCode],
            "plugin_interfaces": [i.value for i in objects.PluginInterface],
            "interface_versions": list(objects.SUPPORTED_INTERFACE_VERSIONS),
            "query_kinds": [k.value for k in objects.QueryKind],
            "search_verdicts": [v.value for v in objects.SearchVerdict],
            "precondition_verdicts": [v.value for v in objects.PreconditionVerdict],
            "optimization_statuses": [v.value for v in kernel.OptimizationStatus],
            "robustness_verdicts": [v.value for v in kernel.RobustnessVerdict],
            "run_statuses": [s.value for s in objects.RunStatus],
            "termination_reasons": [r.value for r in kernel.TerminationReason],
            "event_types": [e.value for e in objects.EventType],
            "execution_stages": [s.value for s in kernel.ExecutionStage],
            "operation_states": [s.value for s in kernel.OperationState],
            "turn_modes": [m.value for m in kernel.TurnMode],
            "provenance": [p.value for p in kernel.Provenance],
            "rule_outcomes": [o.value for o in kernel.RuleOutcome],
            "rule_results": [r.value for r in governance.RuleResult],
        }
    )
    return files


def contract_digest(files: dict[str, str]) -> dict[str, object]:
    """sha256 over `name\\0sha256(content)\\n` lines of all files sorted by name."""
    per_file = {name: hashlib.sha256(content.encode()).hexdigest() for name, content in sorted(files.items())}
    manifest = "".join(f"{name}\0{h}\n" for name, h in per_file.items())
    return {
        "contract_version": CONTRACT_VERSION,
        "algorithm": "sha256",
        "method": "sha256 over lines 'relative_path NUL sha256(file)' + LF, files sorted by relative path "
        "(DIGEST.json itself excluded)",
        "digest": hashlib.sha256(manifest.encode()).hexdigest(),
        "files": per_file,
    }


def write(out: Path) -> dict[str, object]:
    files = build_schemas()
    out.mkdir(parents=True, exist_ok=True)
    stale = {p for p in out.rglob("*.json")} - {out / n for n in files} - {out / "DIGEST.json"}
    for path in stale:
        path.unlink()
    for name, content in files.items():
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    digest = contract_digest(files)
    (out / "DIGEST.json").write_text(_dump(digest), encoding="utf-8")
    return digest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("contracts/v2"))
    parser.add_argument("--v1-out", type=Path, default=None, help="also regenerate the frozen v1 contract here")
    args = parser.parse_args()
    if args.v1_out is not None:
        from .v1 import schema_export as v1export

        d1 = v1export.write(args.v1_out)
        print(f"{v1export.CONTRACT_VERSION} digest sha256:{d1['digest']} ({len(d1['files'])} files, frozen)")
    digest = write(args.out)
    print(f"{CONTRACT_VERSION} digest sha256:{digest['digest']} ({len(digest['files'])} files)")


if __name__ == "__main__":
    main()
