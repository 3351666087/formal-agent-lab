"""Shared building blocks of formal-lab-contracts/v1."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

CONTRACT_VERSION = "formal-lab-contracts/v1"
ContractVersion = Literal["formal-lab-contracts/v1"]

# Scalar value carried by a state location, fact or action parameter.
# bool is listed first so JSON true/false never degrades to int.
StateScalar = bool | int | str
JsonScalar = bool | int | float | str | None

ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,254}$"
PLUGIN_ID_PATTERN = r"^[a-z0-9]+([.-][a-z0-9]+)*(/[a-z0-9]+([.-][a-z0-9]+)*)?$"
SEMVER_PATTERN = r"^[0-9]+\.[0-9]+\.[0-9]+([-+][0-9A-Za-z.-]+)?$"
NAMESPACE_PATTERN = r"^[a-z0-9][a-z0-9-]*(\.[a-z0-9_-]+)+$"
NAME_PATTERN = r"^[A-Za-z_][A-Za-z0-9_]*$"

# Constraints are expressed as JSON-Schema-visible patterns so every contract consumer enforces them.
Identifier = Annotated[str, StringConstraints(pattern=ID_PATTERN)]
PluginId = Annotated[str, StringConstraints(pattern=PLUGIN_ID_PATTERN)]
SemVer = Annotated[str, StringConstraints(pattern=SEMVER_PATTERN)]
Namespace = Annotated[str, StringConstraints(pattern=NAMESPACE_PATTERN)]
Name = Annotated[str, StringConstraints(pattern=NAME_PATTERN)]


class ContractModel(BaseModel):
    """Base for all contract objects: unknown fields are rejected (extensions go in `extensions`)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, use_enum_values=False,
                              json_schema_serialization_defaults_required=True)


class Digest(ContractModel):
    algorithm: Literal["sha256"] = "sha256"
    value: str = Field(pattern=r"^[0-9a-f]{64}$")

    def __str__(self) -> str:
        return f"{self.algorithm}:{self.value}"


class Extension(ContractModel):
    """Namespaced, versioned extension payload. `schema_id` names the JSON Schema that validates `data`."""

    version: SemVer
    schema_id: str = Field(min_length=1)
    data: dict[str, Any]


Extensions = dict[Namespace, Extension]


class ExtensibleModel(ContractModel):
    extensions: Extensions = Field(
        default_factory=dict,
        description="namespaced extension slots; keys are reverse-DNS namespaces, formal-lab.core.* is reserved",
        json_schema_extra={"propertyNames": {"pattern": NAMESPACE_PATTERN, "not": {"pattern": "^formal[-_]lab\\.core"}}},
    )

    @field_validator("extensions")
    @classmethod
    def _namespaces(cls, value: Extensions) -> Extensions:
        for key in value:
            if key.startswith(("formal-lab.core", "formal_lab.core")):
                raise ValueError(f"extension namespace {key!r} is reserved for core fields")
        return value


def utcnow() -> datetime:
    return datetime.now(UTC)


def canonical_json(obj: Any) -> bytes:
    """Deterministic JSON encoding used for digests: sorted keys, no whitespace, UTF-8."""
    if isinstance(obj, BaseModel):
        obj = obj.model_dump(mode="json", by_alias=True)
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def digest_of(obj: Any) -> Digest:
    data = obj if isinstance(obj, bytes) else canonical_json(obj)
    return Digest(value=hashlib.sha256(data).hexdigest())


class PluginRef(ContractModel):
    plugin_id: PluginId
    version: SemVer


class ArtifactRef(ContractModel):
    """Pointer to a large object held by an ArtifactStore (never inlined into events)."""

    uri: str = Field(min_length=1, description="object location, e.g. file://… or s3://bucket/key")
    media_type: str = Field(min_length=3)
    size_bytes: int = Field(ge=0)
    digest: Digest
    format_version: str = Field(min_length=1)
    name: str | None = None


class EvidenceRef(ContractModel):
    """Reference to something that supports a claim: an event, artifact, check or snapshot."""

    kind: Literal["event", "artifact", "check", "snapshot", "operation", "model_call"]
    id: str = Field(min_length=1)
    artifact: ArtifactRef | None = None
    note: str | None = None


def state_path(var: str, index: tuple[str, ...] | list[str] = ()) -> str:
    """Canonical location path: `var` or `var[a,b]`."""
    return f"{var}[{','.join(index)}]" if index else var


def parse_state_path(path: str) -> tuple[str, tuple[str, ...]]:
    if path.endswith("]") and "[" in path:
        name, _, rest = path.partition("[")
        return name, tuple(rest[:-1].split(",")) if rest[:-1] else ()
    return path, ()
