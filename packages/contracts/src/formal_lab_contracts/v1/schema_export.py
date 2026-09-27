"""FROZEN formal-lab-contracts/v1 — do not edit (contracts/v1 must stay byte-identical).

Generate contracts/v1 JSON Schemas and the contract digest from the Pydantic source of truth.

    python -m formal_lab_contracts.schema_export --out contracts/v1
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from pydantic import BaseModel
from pydantic.json_schema import models_json_schema

from . import capabilities, errors, ir, objects
from .common import CONTRACT_VERSION, ArtifactRef, EvidenceRef, Extension

# The frozen objects (section 4 of the phase-1 task book) followed by supporting types.
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
SUPPORTING: list[type[BaseModel]] = [
    ir.ModelIR,
    objects.CheckQuery,
    objects.PlanningContext,
    objects.CandidateAction,
    objects.EnvironmentSnapshot,
    objects.EpisodeRecord,
    objects.BudgetUsage,
    errors.ErrorInfo,
    capabilities.CapabilityRequirement,
    capabilities.CapabilityNegotiation,
    EvidenceRef,
    Extension,
]
ALL_MODELS = FROZEN_OBJECTS + SUPPORTING


def _dump(obj: object) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def build_schemas() -> dict[str, str]:
    """Return {relative file name: file content}."""
    files: dict[str, str] = {}
    for model in ALL_MODELS:
        schema = model.model_json_schema(mode="validation")
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        schema["$id"] = f"https://formal-lab.dev/contracts/v1/{model.__name__}.schema.json"
        files[f"schemas/{model.__name__}.schema.json"] = _dump(schema)

    _, bundle = models_json_schema([(m, "validation") for m in ALL_MODELS], ref_template="#/$defs/{model}")
    bundle = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://formal-lab.dev/contracts/v1/bundle.schema.json",
        "title": "FormalLabContractsV1",
        "description": f"{CONTRACT_VERSION}: all contract types (generated, do not edit)",
        "type": "object",
        "properties": {m.__name__: {"$ref": f"#/$defs/{m.__name__}"} for m in ALL_MODELS},
        "$defs": bundle["$defs"],
    }
    files["bundle.schema.json"] = _dump(bundle)
    # Serialization view: what the platform emits (fields with defaults are always present). TypeScript types
    # for consumers are generated from this view; validators use the validation bundle above.
    _, out_bundle = models_json_schema([(m, "serialization") for m in ALL_MODELS], ref_template="#/$defs/{model}")
    files["bundle.serialization.schema.json"] = _dump({
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://formal-lab.dev/contracts/v1/bundle.serialization.schema.json",
        "title": "FormalLabContractsV1",
        "description": f"{CONTRACT_VERSION}: all contract types as serialized by the platform (generated, do not edit)",
        "type": "object",
        "properties": {m.__name__: {"$ref": f"#/$defs/{m.__name__}"} for m in ALL_MODELS},
        "$defs": out_bundle["$defs"],
    })
    files["objects.json"] = _dump(
        {
            "contract_version": CONTRACT_VERSION,
            "frozen_objects": [m.__name__ for m in FROZEN_OBJECTS],
            "supporting_types": [m.__name__ for m in SUPPORTING],
            "error_codes": [c.value for c in errors.ErrorCode],
            "query_kinds": [k.value for k in objects.QueryKind],
            "search_verdicts": [v.value for v in objects.SearchVerdict],
            "precondition_verdicts": [v.value for v in objects.PreconditionVerdict],
            "run_statuses": [s.value for s in objects.RunStatus],
            "event_types": [e.value for e in objects.EventType],
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
    parser.add_argument("--out", type=Path, default=Path("contracts/v1"))
    args = parser.parse_args()
    digest = write(args.out)
    print(f"{CONTRACT_VERSION} digest sha256:{digest['digest']} ({len(digest['files'])} files)")


if __name__ == "__main__":
    main()
