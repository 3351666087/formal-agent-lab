"""FROZEN formal-lab-contracts/v1 — do not edit (contracts/v1 must stay byte-identical).

Replay bundle format `formal-lab/replay-bundle@1` (a zip file, readable without a server).

Layout
    bundle.json            format, contract version/digest, run id, file digests (sha256), provenance
    manifest.json          RunManifest
    events.jsonl           TraceEvents in seq order
    model/package.json     ModelPackage the run pinned
    metrics.json           list[MetricResult]
    artifacts/<sha256>     artifacts referenced by events (snapshots, model-call records, …)
    contracts/v1/...       the JSON Schemas + DIGEST.json of the contract version used

`read_bundle` verifies every file digest and the internal consistency (manifest ↔ package ↔ events).
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..errors import InvalidInput, VersionMismatch
from .common import CONTRACT_VERSION, utcnow
from .objects import MetricResult, ModelPackage, RunManifest, TraceEvent

BUNDLE_FORMAT = "formal-lab/replay-bundle@1"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _dump(obj: Any) -> bytes:
    return (json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


@dataclass
class ReplayBundle:
    manifest: RunManifest
    events: list[TraceEvent]
    package: ModelPackage
    metrics: list[MetricResult]
    artifacts: dict[str, bytes] = field(default_factory=dict)
    info: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------ views for offline replay
    def steps(self) -> list[int]:
        return sorted({e.logical_step for e in self.events if e.logical_step and e.event_type == "ACTION_OUTCOME"})

    def step(self, n: int) -> dict[str, Any]:
        out: dict[str, Any] = {"step": n}
        for e in self.events:
            if e.logical_step != n:
                continue
            key = {"OBSERVATION": "observation", "CANDIDATES": "candidates", "ACTION_PROPOSED": "proposal",
                   "CHECK_COMPLETED": "check", "ACTION_OUTCOME": "outcome", "EFFECT_COMPARED": "comparison"}.get(
                str(e.event_type))
            if key:
                out[key] = e.payload
        return out

    def snapshot(self, digest: str) -> dict[str, Any] | None:
        data = self.artifacts.get(digest)
        return json.loads(data) if data is not None else None

    def timeline(self) -> list[dict[str, Any]]:
        return [{"seq": e.seq, "type": str(e.event_type), "step": e.logical_step, "parents": e.causal_parents}
                for e in self.events]


def write_bundle(bundle: ReplayBundle, *, provenance: dict[str, Any] | None = None) -> bytes:
    files: dict[str, bytes] = {
        "manifest.json": _dump(bundle.manifest.model_dump(mode="json")),
        "events.jsonl": "".join(json.dumps(e.model_dump(mode="json"), sort_keys=True, ensure_ascii=False) + "\n"
                                for e in sorted(bundle.events, key=lambda e: e.seq)).encode(),
        "model/package.json": _dump(bundle.package.model_dump(mode="json")),
        "metrics.json": _dump([m.model_dump(mode="json") for m in bundle.metrics]),
    }
    for digest, data in sorted(bundle.artifacts.items()):
        if _sha(data) != digest:
            raise InvalidInput(f"artifact {digest} does not match its content")
        files[f"artifacts/{digest}"] = data
    from .schema_export import build_schemas
    from .schema_export import contract_digest as compute_digest

    schemas = build_schemas()  # the exact contract this code speaks, embedded for offline validation
    for name, content in schemas.items():
        files[f"contracts/v1/{name}"] = content.encode()
    digest_info = compute_digest(schemas)
    files["contracts/v1/DIGEST.json"] = _dump(digest_info)
    contract_digest = digest_info["digest"]
    info = {
        "format": BUNDLE_FORMAT,
        "contract_version": CONTRACT_VERSION,
        "contract_digest": contract_digest,
        "run_id": bundle.manifest.run_id,
        "created_at": utcnow().isoformat(),
        "event_count": len(bundle.events),
        "provenance": provenance or {},
        "files": {name: _sha(data) for name, data in sorted(files.items())},
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("bundle.json", _dump(info))
        for name, data in sorted(files.items()):
            zf.writestr(name, data)
    return buf.getvalue()


def read_bundle(data: bytes | Path) -> ReplayBundle:
    raw = data.read_bytes() if isinstance(data, Path) else data
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise InvalidInput("not a replay bundle (zip expected)") from exc
    with zf:
        try:
            info = json.loads(zf.read("bundle.json"))
        except KeyError as exc:
            raise InvalidInput("bundle.json missing") from exc
        if info.get("format") != BUNDLE_FORMAT:
            raise VersionMismatch(f"unsupported bundle format {info.get('format')!r}")
        if info.get("contract_version") != CONTRACT_VERSION:
            raise VersionMismatch(f"bundle uses {info.get('contract_version')}, this reader speaks {CONTRACT_VERSION}")
        names = set(zf.namelist()) - {"bundle.json"}
        if names != set(info["files"]):
            raise InvalidInput(f"bundle file list mismatch: {sorted(names ^ set(info['files']))[:5]}")
        contents = {name: zf.read(name) for name in names}
    for name, digest in info["files"].items():
        if _sha(contents[name]) != digest:
            raise InvalidInput(f"bundle file {name} is corrupted (digest mismatch)")
    manifest = RunManifest.model_validate_json(contents["manifest.json"])
    package = ModelPackage.model_validate_json(contents["model/package.json"])
    events = [TraceEvent.model_validate_json(line) for line in contents["events.jsonl"].decode().splitlines() if line]
    metrics = [MetricResult.model_validate(m) for m in json.loads(contents["metrics.json"])]
    if package.digest != manifest.model.digest:
        raise InvalidInput("bundle model package does not match the manifest's pinned model")
    if any(e.run_id != manifest.run_id for e in events):
        raise InvalidInput("bundle contains events of another run")
    if [e.seq for e in events] != list(range(1, len(events) + 1)):
        raise InvalidInput("bundle event sequence is not contiguous")
    artifacts = {name.split("/", 1)[1]: data for name, data in contents.items() if name.startswith("artifacts/")}
    return ReplayBundle(manifest=manifest, events=events, package=package, metrics=metrics, artifacts=artifacts,
                        info=info)
