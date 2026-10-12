"""Imported research study results (phase 6A).

Studies run locally (`formal_lab_eval.research`, model calls from the host); the platform imports their results
read-only so the Web UI can show both result axes and the raw answer of every unit. The upload is a zip with
`study.json` and the results directory under `results/` (ledger.jsonl, responses/, evaluations/, report.json).
Import checks every latest response file against the sha256 the ledger recorded when it was written (a response
changed afterwards is rejected) and validates every record against its contract. Re-importing replaces the study.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from typing import Any

from formal_lab_contracts.errors import InvalidInput, NotFound
from formal_lab_contracts.research import ResearchEvaluation, ResearchResponse, ResearchStudy
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..db import Project, ResearchStudyRow, ResearchStudyUnitRow
from .common import get_or_404, new_id


def _read_zip(data: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = [n for n in zf.namelist() if not n.endswith("/")]
        prefix = next((n[: -len("study.json")] for n in names if n.endswith("study.json") and n.count("/") <= 1), None)
        if prefix is None:
            raise InvalidInput("no study.json in the upload")
        return {n[len(prefix):]: zf.read(n) for n in names if n.startswith(prefix)}


def _summary(resp: ResearchResponse, ev: ResearchEvaluation | None, sampling_index: int) -> dict[str, Any]:
    e, c, s, k = resp.experiment, resp.call, resp.status, resp.cost
    return {"unit_id": e.unit_id, "track": str(e.track), "task_id": e.task_id, "provider_config_id": c.provider_config_id,
            "assistance_mode": str(e.assistance_mode), "representation_id": e.representation_id,
            "replicate": e.replicate_id, "sampling_index": sampling_index, "outcome": str(s.outcome),
            "http_status": s.http_status, "route": str(c.route), "model_requested": c.model_requested,
            "model_returned": c.model_returned, "model_identity": str(c.model_identity),
            "model_switched": c.model_switched, "output_tokens": k.output_tokens, "usage_known": k.usage_known,
            "latency_ms": k.latency_ms, "http_attempts": k.http_attempts,
            "possibly_billed": k.possibly_billed_unconfirmed, "recorded_at": resp.recorded_at,
            "behavior": str(ev.behavior_label) if ev else None, "answer_status": str(ev.answer_status) if ev else None,
            "program_correspondence": ev.program_correspondence if ev else None}


def import_study(s: Session, project_id: str, data: bytes) -> dict[str, Any]:
    get_or_404(s, Project, project_id, "project")
    files = _read_zip(data)
    study = ResearchStudy.model_validate_json(files["study.json"])
    if "results/ledger.jsonl" not in files or "results/report.json" not in files:
        raise InvalidInput("the upload has no results/ledger.jsonl or results/report.json — run the study first")
    events = [json.loads(line) for line in files["results/ledger.jsonl"].decode().splitlines() if line.strip()]
    latest: dict[str, dict[str, Any]] = {}
    history: dict[str, list[dict[str, Any]]] = {}
    for e in events:
        if e["event"] == "response":
            latest[e["unit_id"]] = e
            history.setdefault(e["unit_id"], []).append({k: e.get(k) for k in ("sampling_index", "outcome", "at")})
    units, rows = [], []
    for unit_id, e in sorted(latest.items()):
        raw = files.get(f"results/{e['path']}")
        if raw is None:
            raise InvalidInput(f"response {e['path']} is missing from the upload")
        if hashlib.sha256(raw).hexdigest() != e["digest"]:
            raise InvalidInput(f"response {e['path']} changed after it was recorded (sha256 ≠ the ledger's)")
        resp = ResearchResponse.model_validate_json(raw)
        ev_raw = files.get(f"results/evaluations/{unit_id}--{e['sampling_index']}.json")
        ev = ResearchEvaluation.model_validate_json(ev_raw) if ev_raw else None
        if ev is not None and ev.response_digest != e["digest"]:
            raise InvalidInput(f"evaluation of {unit_id} was made for another response")
        units.append(_summary(resp, ev, e["sampling_index"]))
        rows.append((unit_id, resp, ev, history[unit_id][:-1]))
    old = s.scalar(select(ResearchStudyRow).where(ResearchStudyRow.project_id == project_id,
                                                  ResearchStudyRow.study_id == study.study_id))
    if old is not None:
        s.execute(delete(ResearchStudyUnitRow).where(ResearchStudyUnitRow.study_row_id == old.id))
        s.delete(old)
        s.flush()
    row = ResearchStudyRow(id=new_id("rs"), project_id=project_id, study_id=study.study_id, title=study.title,
                           study_digest=hashlib.sha256(files["study.json"]).hexdigest(),
                           study=study.model_dump(mode="json"), report=json.loads(files["results/report.json"]),
                           units=units)
    s.add(row)
    s.flush()
    for unit_id, resp, ev, hist in rows:
        s.add(ResearchStudyUnitRow(study_row_id=row.id, unit_id=unit_id, track=str(resp.experiment.track),
                                   outcome=str(resp.status.outcome),
                                   behavior=str(ev.behavior_label) if ev else None,
                                   response=resp.model_dump(mode="json"),
                                   evaluation=ev.model_dump(mode="json") if ev else None, history=hist))
    s.flush()
    return study_detail(s, row.id)


def _row_summary(r: ResearchStudyRow) -> dict[str, Any]:
    return {"id": r.id, "project_id": r.project_id, "study_id": r.study_id, "title": r.title,
            "study_digest": r.study_digest, "units": len(r.units), "imported_at": r.imported_at,
            "tracks": sorted((r.report.get("tracks") or {}).keys())}


def list_studies(s: Session, project_id: str) -> list[dict[str, Any]]:
    get_or_404(s, Project, project_id, "project")
    rows = s.scalars(select(ResearchStudyRow).where(ResearchStudyRow.project_id == project_id)
                     .order_by(ResearchStudyRow.imported_at.desc()))
    return [_row_summary(r) for r in rows]


def study_detail(s: Session, rs_id: str) -> dict[str, Any]:
    r = get_or_404(s, ResearchStudyRow, rs_id, "research study")
    return {**_row_summary(r), "study": r.study, "report": r.report, "unit_summaries": r.units}


def study_unit(s: Session, rs_id: str, unit_id: str) -> dict[str, Any]:
    get_or_404(s, ResearchStudyRow, rs_id, "research study")
    u = s.get(ResearchStudyUnitRow, (rs_id, unit_id))
    if u is None:
        raise NotFound(f"no unit {unit_id!r} in study {rs_id}")
    return {"unit_id": u.unit_id, "track": u.track, "outcome": u.outcome, "behavior": u.behavior,
            "response": u.response, "evaluation": u.evaluation, "history": u.history}
