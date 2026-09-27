"""Replay bundles for in-process runs (the platform exports its own runs from the database)."""

from __future__ import annotations

from formal_lab_contracts import ModelPackage, canonical_json
from formal_lab_contracts.bundle import ReplayBundle, write_bundle

from .local_runner import LocalRunResult


def bundle_from_local(result: LocalRunResult, package: ModelPackage, provenance: dict | None = None) -> bytes:
    final = canonical_json({"truth_state": result.final_state})
    import hashlib

    artifacts = {hashlib.sha256(final).hexdigest(): final}
    for call in result.model_calls:
        data = canonical_json(call)
        artifacts[hashlib.sha256(data).hexdigest()] = data
    bundle = ReplayBundle(manifest=result.manifest, events=result.events, package=package, metrics=result.metrics,
                          artifacts=artifacts, operations=list(result.operations))
    return write_bundle(bundle, provenance={"runner": "local", **(provenance or {})})
