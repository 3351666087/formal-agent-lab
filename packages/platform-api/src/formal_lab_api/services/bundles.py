"""Replay bundle export (from the database) and import (into a project)."""

from __future__ import annotations

import json
from typing import Any

from formal_lab_contracts import ArtifactRef, MetricResult, ModelPackage, RunManifest
from formal_lab_contracts.bundle import ReplayBundle, read_bundle, write_bundle
from formal_lab_contracts.errors import Conflict
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import Artifact, MetricRow, Model, ModelVersion, Project, Run, RunEvent, Snapshot
from .common import artifact_store, get_or_404, new_id
from .events import to_trace_event
from .modeling import package_of


def export_run(s: Session, run_id: str) -> tuple[bytes, str]:
    run = get_or_404(s, Run, run_id, "run")
    manifest = RunManifest.model_validate(run.manifest)
    version = s.scalar(select(ModelVersion).where(ModelVersion.digest == manifest.model.digest.value,
                                                  ModelVersion.version == manifest.model.version))
    package = package_of(version)
    events = [to_trace_event(r) for r in s.scalars(select(RunEvent).where(RunEvent.run_id == run_id)
                                                   .order_by(RunEvent.seq))]
    metrics = [MetricResult.model_validate(m.result) for m in s.scalars(select(MetricRow).where(MetricRow.run_id == run_id))]
    artifacts: dict[str, bytes] = {}
    for row in s.scalars(select(Artifact).where(Artifact.run_id == run_id)):
        artifacts[row.digest] = artifact_store().get(ArtifactRef.model_validate(row.ref))
    bundle = ReplayBundle(manifest=manifest, events=events, package=package, metrics=metrics, artifacts=artifacts)
    data = write_bundle(bundle, provenance={"exported_from": "formal-lab platform", "status": run.status,
                                            "source_run_id": run.source_run_id,
                                            "snapshot_steps": [x.step for x in s.scalars(
                                                select(Snapshot).where(Snapshot.run_id == run_id))]})
    return data, f"{run_id}.replay.zip"


def import_bundle(s: Session, project_id: str, data: bytes, *, matrix_id: str | None = None) -> Run:
    get_or_404(s, Project, project_id, "project")
    bundle = read_bundle(data)
    m = bundle.manifest
    if s.get(Run, m.run_id) is not None:
        raise Conflict(f"run {m.run_id} already exists on this server")
    version = _ensure_model(s, project_id, bundle.package)
    run = Run(id=m.run_id, project_id=project_id, scenario_id=None, strategy_config_id=None, matrix_id=matrix_id,
              source_run_id=m.source_run_id, status=m.status.value, status_reason=m.status_reason,
              manifest=m.model_dump(mode="json"), workflow_id=None, event_seq=len(bundle.events),
              last_step=max([e.logical_step or 0 for e in bundle.events] + [0]),
              usage={**m.budget_usage.model_dump(), "tokens": m.budget_usage.tokens}, imported=True,
              final_state=_final_state(bundle), created_at=m.created_at, finished_at=bundle.events[-1].wall_time)
    s.add(run)
    s.flush()
    for e in bundle.events:
        s.add(RunEvent(run_id=run.id, seq=e.seq, event_id=e.event_id, event_type=str(e.event_type),
                       logical_step=e.logical_step, wall_time=e.wall_time, actor_id=e.actor_id,
                       causal_parents=e.causal_parents, payload_schema=e.payload_schema, payload=e.payload,
                       idempotency_key=e.idempotency_key or e.event_id))
    for mres in bundle.metrics:
        s.add(MetricRow(run_id=run.id, metric_id=mres.metric_id, result=mres.model_dump(mode="json"),
                        value=mres.value, status=mres.status.value))
    for digest, blob in bundle.artifacts.items():
        ref = artifact_store().put(blob, name=digest, media_type="application/json", format_version="imported")
        s.add(Artifact(run_id=run.id, kind="imported", digest=digest, ref=ref.model_dump(mode="json")))
    _ = version
    return run


def _ensure_model(s: Session, project_id: str, package: ModelPackage) -> ModelVersion:
    existing = s.scalar(select(ModelVersion).where(ModelVersion.digest == package.digest.value,
                                                   ModelVersion.version == package.version))
    if existing is not None:
        return existing
    package_id = f"imported:{package.package_id}"
    model = s.scalar(select(Model).where(Model.project_id == project_id, Model.package_id == package_id))
    if model is None:
        model = Model(id=new_id("mdl"), project_id=project_id, package_id=package_id,
                      name=f"{package.ir.name} (imported)", description="imported with a replay bundle",
                      latest_version=0)
        s.add(model)
        s.flush()
    row = ModelVersion(id=new_id("mv"), model_id=model.id, version=package.version, digest=package.digest.value,
                       semantic_profile=package.semantic_profile, package=package.model_dump(mode="json"),
                       note="imported from replay bundle")
    model.latest_version = max(model.latest_version, package.version)
    s.add(row)
    s.flush()
    return row


def _final_state(bundle: ReplayBundle) -> dict[str, Any] | None:
    for data in bundle.artifacts.values():
        try:
            obj = json.loads(data)
        except ValueError:
            continue
        if isinstance(obj, dict) and "truth_state" in obj:
            return {"truth_state": obj["truth_state"], "properties": {}}
    terminal = bundle.events[-1].payload if bundle.events else {}
    return {"truth_state": {}, "properties": terminal.get("final_properties", {})}
