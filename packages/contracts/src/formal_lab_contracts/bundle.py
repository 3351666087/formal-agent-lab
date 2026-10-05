"""Replay bundle format `formal-lab/replay-bundle@2` (a zip file, readable without a server).

Layout
    bundle.json            format, contract version/digest, run id, file digests (sha256), provenance
    manifest.json          RunManifest
    events.jsonl           TraceEvents in seq order
    model/package.json     ModelPackage the run pinned
    metrics.json           list[MetricResult]
    operations.json        list[OperationRecord] (environment operations and their coordination states)
    artifacts/<sha256>     artifacts referenced by events (snapshots, model-call records, query bundles, …)
    contracts/v2/...       the JSON Schemas + DIGEST.json of the contract version used

`read_bundle` verifies every file digest and the internal consistency (manifest ↔ package ↔ events: model digest,
run id, gap-free sequence, causal parents that exist). Phase-1 bundles (`formal-lab/replay-bundle@1`) are read with
the frozen v1 reader and upgraded to v2 objects; `info["upgraded_from"]` records that.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .common import CONTRACT_VERSION, CONTRACT_VERSION_V1, utcnow
from .errors import InvalidInput, VersionMismatch
from .execution import OperationRecord
from .objects import MetricResult, ModelPackage, RunManifest, TraceEvent

BUNDLE_FORMAT = "formal-lab/replay-bundle@2"
BUNDLE_FORMAT_V1 = "formal-lab/replay-bundle@1"
READABLE_FORMATS = (BUNDLE_FORMAT_V1, BUNDLE_FORMAT)

STEP_KEYS = {"OBSERVATION": "observation", "CANDIDATES": "candidates", "ACTION_PROPOSED": "proposal",
             "CHECK_COMPLETED": "check", "ACTION_OUTCOME": "outcome", "EFFECT_COMPARED": "comparison",
             "TURN_STARTED": "turn", "TURN_SKIPPED": "skipped", "PLAN_UPDATED": "plan",
             "OPERATION_STATE": "operation", "OPERATION_RECONCILED": "reconciliation", "PROBE_SAMPLED": "probes",
             "RULE_EVALUATED": "rules", "OBSERVATION_REQUESTED": "observation_request",
             "BATCH_OPENED": "batch_opened", "BATCH_SUBMITTED": "batch", "EXECUTION_DECIDED": "decisions"}


def summarize_batches(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """JOINT_BATCH rounds of a run (phase 3A) from its events ({event_type, logical_step, actor_id, payload}): the
    final batch record joined with each member's proposal, outcome and comparison verdict. A batch that is still
    open is listed with status OPEN."""
    by_member: dict[tuple[int, str], dict[str, Any]] = {}
    batches: dict[str, dict[str, Any]] = {}
    for e in events:
        kind, step, actor, payload = str(e["event_type"]), e.get("logical_step"), e.get("actor_id"), e["payload"]
        if kind in ("BATCH_OPENED", "BATCH_SUBMITTED", "BATCH_CANCELLED"):
            batches[payload["batch"]["batch_id"]] = dict(payload["batch"])
        elif kind in ("ACTION_PROPOSED", "ACTION_OUTCOME", "EFFECT_COMPARED") and step and actor:
            slot = by_member.setdefault((step, actor), {})
            if kind == "ACTION_PROPOSED":
                slot["action"] = payload["proposal"]["action"]
            elif kind == "ACTION_OUTCOME":
                out = payload["outcome"]
                slot.update(outcome=out["status"], reason=(out.get("result") or {}).get("reason"),
                            env_step=(out.get("turn") or {}).get("env_step"))
            else:
                slot["comparison"] = payload["comparison"]["verdict"]
    out = []
    for b in sorted(batches.values(), key=lambda b: b["round"]):
        members = [{**m, **by_member.get((m.get("global_step") or 0, m["actor_id"]), {})} for m in b["members"]]
        out.append({**b, "members": members})
    return out


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
    operations: list[OperationRecord] = field(default_factory=list)

    # ------------------------------------------------------------------ views for offline replay
    def steps(self) -> list[int]:
        return sorted({e.logical_step for e in self.events if e.logical_step and e.event_type == "ACTION_OUTCOME"})

    def step(self, n: int) -> dict[str, Any]:
        out: dict[str, Any] = {"step": n}
        for e in self.events:
            if str(e.event_type) == "EXECUTION_DECIDED":  # a decision belongs to the step of the proposal it judged
                if (e.payload.get("decision") or {}).get("step", e.logical_step) == n:
                    out.setdefault("decisions", []).append(e.payload)
                continue
            if e.logical_step != n:
                continue
            if e.turn is not None and "turn_ref" not in out:
                out["turn_ref"] = e.turn.model_dump(mode="json")
            if e.actor_id and "actor_id" not in out and str(e.event_type) != "CHECK_COMPLETED":
                out["actor_id"] = e.actor_id
            key = STEP_KEYS.get(str(e.event_type))
            if key in ("check", "rules", "probes", "plan", "operation"):
                out.setdefault(key + "s" if not key.endswith("s") else key, []).append(e.payload)
            elif key:
                out[key] = e.payload
        return out

    def turns(self) -> list[dict[str, Any]]:
        """One row per global step: actor, round, actor step, action and outcome status."""
        rows: dict[int, dict[str, Any]] = {}
        for e in self.events:
            if not e.logical_step:
                continue
            row = rows.setdefault(e.logical_step, {"step": e.logical_step})
            if e.turn is not None:
                row.update(round=e.turn.round, actor_id=e.turn.actor_id, actor_step=e.turn.actor_step)
            elif e.actor_id and "actor_id" not in row:
                row["actor_id"] = e.actor_id
            if str(e.event_type) == "ACTION_PROPOSED":
                a = e.payload.get("proposal", {}).get("action", {})
                row["action"] = f"{a.get('action_type')}({', '.join(f'{k}={v}' for k, v in a.get('params', {}).items())})"
            elif str(e.event_type) == "ACTION_OUTCOME":
                row["outcome"] = e.payload.get("outcome", {}).get("status")
            elif str(e.event_type) == "TURN_SKIPPED":
                row["outcome"] = "SKIPPED"
        return [rows[k] for k in sorted(rows)]

    def batches(self) -> list[dict[str, Any]]:
        """JOINT_BATCH rounds with their members' actions, outcomes and comparisons (phase 3A)."""
        return summarize_batches([{"event_type": e.event_type, "logical_step": e.logical_step, "actor_id": e.actor_id,
                                   "payload": e.payload} for e in self.events])

    def plans(self, actor_id: str | None = None) -> list[dict[str, Any]]:
        return [e.payload for e in self.events if str(e.event_type) == "PLAN_UPDATED"
                and (actor_id is None or e.actor_id == actor_id)]

    def probes(self) -> list[dict[str, Any]]:
        return [p for e in self.events if str(e.event_type) == "PROBE_SAMPLED" for p in e.payload.get("results", [])]

    def snapshot(self, digest: str) -> dict[str, Any] | None:
        data = self.artifacts.get(digest)
        return json.loads(data) if data is not None else None

    def timeline(self) -> list[dict[str, Any]]:
        return [{"seq": e.seq, "type": str(e.event_type), "step": e.logical_step, "actor": e.actor_id,
                 "stage": str(e.stage) if e.stage else None, "parents": e.causal_parents} for e in self.events]

    def verify_causality(self) -> list[str]:
        """Problems with causal links: parents must be earlier events of the same run."""
        seen: set[str] = set()
        problems = []
        for e in self.events:
            missing = [p for p in e.causal_parents if p not in seen]
            if missing:
                problems.append(f"event {e.seq} ({e.event_type}) has parents that do not precede it: {missing[:3]}")
            seen.add(e.event_id)
        return problems


def write_bundle(bundle: ReplayBundle, *, provenance: dict[str, Any] | None = None) -> bytes:
    files: dict[str, bytes] = {
        "manifest.json": _dump(bundle.manifest.model_dump(mode="json")),
        "events.jsonl": "".join(json.dumps(e.model_dump(mode="json"), sort_keys=True, ensure_ascii=False) + "\n"
                                for e in sorted(bundle.events, key=lambda e: e.seq)).encode(),
        "model/package.json": _dump(bundle.package.model_dump(mode="json")),
        "metrics.json": _dump([m.model_dump(mode="json") for m in bundle.metrics]),
        "operations.json": _dump([o.model_dump(mode="json") for o in bundle.operations]),
    }
    for digest, data in sorted(bundle.artifacts.items()):
        if _sha(data) != digest:
            raise InvalidInput(f"artifact {digest} does not match its content")
        files[f"artifacts/{digest}"] = data
    from .schema_export import build_schemas
    from .schema_export import contract_digest as compute_digest

    schemas = build_schemas()  # the exact contract this code speaks, embedded for offline validation
    for name, content in schemas.items():
        files[f"contracts/v2/{name}"] = content.encode()
    digest_info = compute_digest(schemas)
    files["contracts/v2/DIGEST.json"] = _dump(digest_info)
    info = {
        "format": BUNDLE_FORMAT,
        "contract_version": CONTRACT_VERSION,
        "contract_digest": digest_info["digest"],
        "run_id": bundle.manifest.run_id,
        "created_at": utcnow().isoformat(),
        "event_count": len(bundle.events),
        "participants": [p.actor_id for p in bundle.manifest.participants],
        "model": bundle.manifest.model.model_dump(mode="json"),
        "provenance": provenance or {},
        "files": {name: _sha(data) for name, data in sorted(files.items())},
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("bundle.json", _dump(info))
        for name, data in sorted(files.items()):
            zf.writestr(name, data)
    return buf.getvalue()


def _read_v1(raw: bytes) -> ReplayBundle:
    from . import compat
    from .v1 import bundle as v1bundle

    old = v1bundle.read_bundle(raw)  # validates every file digest and the v1 objects
    events = [compat.upgrade_event(e.model_dump(mode="json")) for e in old.events]
    info = dict(old.info)
    info["upgraded_from"] = BUNDLE_FORMAT_V1
    info["contract_version_original"] = CONTRACT_VERSION_V1
    bundle = ReplayBundle(
        manifest=compat.upgrade_run_manifest(old.manifest.model_dump(mode="json")),
        events=events,
        package=compat.upgrade_model_package(old.package.model_dump(mode="json")),
        metrics=[MetricResult.model_validate(m.model_dump(mode="json")) for m in old.metrics],
        artifacts=old.artifacts,
        info=info,
    )
    # phase-1 data cannot be repaired: causal problems are reported, not fatal
    info["causality_problems"] = bundle.verify_causality()
    return bundle


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
        if info.get("format") not in READABLE_FORMATS:
            raise VersionMismatch(f"unsupported bundle format {info.get('format')!r}")
        if info["format"] == BUNDLE_FORMAT_V1:
            return _read_v1(raw)
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
    operations = [OperationRecord.model_validate(o) for o in json.loads(contents.get("operations.json", b"[]"))]
    if package.digest != manifest.model.digest:
        raise InvalidInput("bundle model package does not match the manifest's pinned model")
    if any(e.run_id != manifest.run_id for e in events):
        raise InvalidInput("bundle contains events of another run")
    if [e.seq for e in events] != list(range(1, len(events) + 1)):
        raise InvalidInput("bundle event sequence is not contiguous")
    if any(o.run_id != manifest.run_id for o in operations):
        raise InvalidInput("bundle contains operations of another run")
    artifacts = {name.split("/", 1)[1]: data for name, data in contents.items() if name.startswith("artifacts/")}
    bundle = ReplayBundle(manifest=manifest, events=events, package=package, metrics=metrics, artifacts=artifacts,
                          info=info, operations=operations)
    problems = bundle.verify_causality()
    if problems:
        raise InvalidInput(f"bundle event causality is broken: {problems[0]}")
    return bundle
