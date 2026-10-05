"""ModelFrontend for the neutral IR JSON format (fal-ir-json/v1) plus package helpers."""

from __future__ import annotations

import json
from typing import Any

from formal_lab_contracts import (
    ModelIR,
    ModelPackage,
    ModelSource,
    PluginDescriptor,
    canonical_ir_dump,
    digest_of,
    utcnow,
)
from formal_lab_contracts import capabilities as caps
from formal_lab_contracts.errors import FieldError, InvalidInput, Unsupported
from pydantic import ValidationError

from .checker import CheckedModel, check_model

SOURCE_FORMAT = "fal-ir-json/v1"
FRONTEND_ID = "formal-lab.frontend.ir-json"
FRONTEND_VERSION = "1.0.0"

DESCRIPTOR = PluginDescriptor(
    plugin_id=FRONTEND_ID,
    version=FRONTEND_VERSION,
    interface="MODEL_FRONTEND",
    capabilities=[{"id": caps.PROFILE_DETERMINISTIC_FINITE_V1},
                  {"id": caps.FRONTEND_SOURCE_FORMAT, "params": {"formats": [SOURCE_FORMAT]}}],
    semantic_profiles=["deterministic_finite_v1"],
    input_schema={"$ref": "https://formal-lab.dev/contracts/v2/ModelIR.schema.json"},
    output_schema={"$ref": "https://formal-lab.dev/contracts/v2/ModelPackage.schema.json"},
    entrypoint="formal_lab_model.frontend:create",
    ui={"label": "IR JSON", "description": "Neutral finite-state IR (fal-ir-json/v1) with type checking",
        "category": "model_frontend"},
    license="Apache-2.0",
    source="formal-lab-model-core",
)


def canonical_ir(ir: ModelIR) -> dict[str, Any]:
    """Normal form: every v1 field explicit (defaults filled), JSON types only; fields introduced in v2 are left out
    while they hold their default, so phase-1 models keep their digests. Key order is irrelevant because digests
    use canonical JSON (sorted keys); list order is semantic and preserved."""
    return canonical_ir_dump(ir)


def ir_digest(ir: ModelIR):
    return digest_of(canonical_ir(ir))


def canonical_text(ir: ModelIR) -> str:
    return json.dumps(canonical_ir(ir), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def parse_ir(data: str | bytes | dict[str, Any]) -> ModelIR:
    try:
        raw = json.loads(data) if isinstance(data, (str, bytes)) else data
    except json.JSONDecodeError as exc:
        raise InvalidInput(f"model source is not valid JSON: {exc}") from exc
    try:
        return ModelIR.model_validate(raw)
    except ValidationError as exc:
        raise InvalidInput(
            "model source does not match the ModelIR schema",
            field_errors=[FieldError(path="/" + "/".join(str(p) for p in e["loc"]), message=e["msg"])
                          for e in exc.errors()],
        ) from exc


def raise_for_issues(checked: CheckedModel) -> None:
    if not checked.issues:
        return
    unsupported = [i for i in checked.issues if i.code in ("UNSUPPORTED_PROFILE", "UNSUPPORTED_FEATURE")]
    errors = [FieldError(path=i.path, message=f"[{i.code}] {i.message}") for i in checked.issues]
    if unsupported and len(unsupported) == len(checked.issues):
        raise Unsupported(unsupported[0].message, field_errors=errors,
                          details={"extension_point": "ModelFrontend / Verifier plugins declaring the profile"})
    raise InvalidInput(f"model has {len(checked.issues)} issue(s)", field_errors=errors,
                       details={"issues": [i.model_dump() for i in checked.issues]})


def build_package(ir: ModelIR, *, package_id: str, version: int, source: ModelSource) -> ModelPackage:
    checked = check_model(ir)
    raise_for_issues(checked)
    return ModelPackage(
        package_id=package_id,
        version=version,
        frontend=DESCRIPTOR.ref(),
        semantic_profile=ir.semantic_profile,
        digest=ir_digest(ir),
        payload={"kind": "fal-ir", "ir": ir},
        source=source,
        created_at=utcnow(),
    )


class IRJsonFrontend:
    descriptor = DESCRIPTOR

    def compile(self, source: ModelSource, *, package_id: str, version: int) -> ModelPackage:
        if source.format != SOURCE_FORMAT:
            raise Unsupported(f"source format {source.format!r} is not handled by {FRONTEND_ID}")
        if source.text is None:
            raise InvalidInput("source.text is required for fal-ir-json/v1")
        ir = parse_ir(source.text)
        return build_package(ir, package_id=package_id, version=version, source=source)


def create(config: dict[str, Any] | None = None, services: Any = None) -> IRJsonFrontend:
    return IRJsonFrontend()


def registrations():
    from formal_lab_contracts.interfaces import PluginRegistration

    from . import driver

    return [PluginRegistration(DESCRIPTOR, create), PluginRegistration(driver.DESCRIPTOR, driver.create)]
