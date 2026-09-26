"""Shared service helpers: ids, lookups, the artifact store and the plugin registry singletons."""

from __future__ import annotations

import json
import uuid
from functools import lru_cache
from typing import Any, TypeVar

from formal_lab_contracts import ArtifactRef, canonical_json
from formal_lab_contracts.errors import NotFound
from formal_lab_runtime import PluginRegistry, default_registry, store_from_settings
from sqlalchemy.orm import Session

from ..db import Artifact

T = TypeVar("T")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:20]}"


def get_or_404(s: Session, model: type[T], key: Any, what: str | None = None) -> T:
    obj = s.get(model, key)
    if obj is None:
        raise NotFound(f"{what or model.__name__} {key!r} not found")
    return obj


@lru_cache(maxsize=1)
def registry() -> PluginRegistry:
    return default_registry()


@lru_cache(maxsize=1)
def artifact_store():
    return store_from_settings()


def put_json_artifact(s: Session, *, run_id: str | None, kind: str, name: str, obj: Any,
                      format_version: str) -> ArtifactRef:
    data = canonical_json(obj)
    ref = artifact_store().put(data, name=name, media_type="application/json", format_version=format_version)
    exists = s.query(Artifact).filter_by(run_id=run_id, digest=ref.digest.value, kind=kind).first()
    if exists is None:
        s.add(Artifact(run_id=run_id, kind=kind, digest=ref.digest.value, ref=ref.model_dump(mode="json")))
    return ref


def get_json_artifact(ref: ArtifactRef | dict[str, Any]) -> Any:
    ref = ArtifactRef.model_validate(ref)
    return json.loads(artifact_store().get(ref))
