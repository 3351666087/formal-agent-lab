"""Research cases and model–program conformance on the platform (phase 5A).

Import validates the case the same way the offline reader does — digests, model and property identity, before/after
sides, data separation — and rejects a case that fails any of them (a file existing is never enough). Artifacts are
put into the existing artifact store; the case document (with the stored refs) and a row per conformance result are
kept, so a model version or an imported run traces back to the cases and correspondence verdicts that reference it.
Software revision + tree digests are recorded and shown; the platform has no checkout, so it does not recompute them.
"""

from __future__ import annotations

import io
import zipfile
from typing import Any

from formal_lab_contracts import ModelPackage
from formal_lab_contracts.errors import Conflict, InvalidInput, NotFound
from formal_lab_contracts.research import ResearchCase
from formal_lab_runtime.research import definition_digest, load_case, validate_case
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import Artifact, Model, ModelVersion, Project, ResearchCaseRow, ResearchConformanceRow, Run
from .common import artifact_store, get_or_404, new_id


def _link_model(s: Session, project_id: str, package: ModelPackage) -> str:
    """The model version with this digest, created from the case's own package when the platform does not have it."""
    existing = s.scalar(select(ModelVersion).join(Model).where(
        Model.project_id == project_id, ModelVersion.digest == package.digest.value))
    if existing is not None:
        return existing.id
    model = s.scalar(select(Model).where(Model.project_id == project_id, Model.package_id == package.package_id))
    if model is None:
        model = Model(id=new_id("mdl"), project_id=project_id, package_id=package.package_id,
                      name=package.package_id, description="linked from a research case", latest_version=0)
        s.add(model)
        s.flush()
    row = ModelVersion(id=new_id("mv"), model_id=model.id, version=package.version, digest=package.digest.value,
                       semantic_profile=package.semantic_profile, package=package.model_dump(mode="json"),
                       note="linked from a research case")
    model.latest_version = max(model.latest_version, package.version)
    s.add(row)
    s.flush()
    return row.id


def import_case(s: Session, project_id: str, data: bytes) -> dict[str, Any]:
    get_or_404(s, Project, project_id, "project")
    files = load_case(data)
    report, case = validate_case(files, repo=None)  # offline: digests / identities / separation, not the git trees
    if not report.ok or case is None:
        raise InvalidInput("the research case did not validate: "
                           + "; ".join(f"{p.code} @ {p.where}" for p in report.problems))
    cid, cver = case.identity.case_id, case.identity.case_version
    if s.scalar(select(ResearchCaseRow).where(ResearchCaseRow.project_id == project_id,
                                              ResearchCaseRow.case_id == cid, ResearchCaseRow.case_version == cver)):
        raise Conflict(f"research case {cid} v{cver} already imported into this project")

    artifacts = {a.id: a for a in case.artifacts}
    packages: dict[str, ModelPackage] = {}
    doc = case.model_dump(mode="json")
    # artifacts into the store; record the stored ref on each artifact of the document
    for a in doc["artifacts"]:
        blob = files.read(a["path"])
        if blob is None:
            raise InvalidInput(f"artifact {a['id']} missing on import")
        ref = artifact_store().put(blob, name=f"{cid}/{a['path']}", media_type=a["media_type"],
                                   format_version=case.protocol)
        a["stored"] = ref.model_dump(mode="json")
        if s.scalar(select(Artifact).where(Artifact.run_id.is_(None), Artifact.digest == ref.digest.value,
                                           Artifact.kind == "research")) is None:
            s.add(Artifact(run_id=None, kind="research", digest=ref.digest.value, ref=ref.model_dump(mode="json")))
        if artifacts[a["id"]].role == "model":
            packages[a["id"]] = ModelPackage.model_validate_json(blob)

    # link each model version by digest (created from the case's package if the platform does not have it)
    version_ids: dict[str, str] = {}  # model digest -> model_version_id
    for m in case.models:
        pkg = packages[m.artifact_id]
        version_ids[pkg.digest.value] = _link_model(s, project_id, pkg)

    # import the one recorded observation run, so a conformance verdict can be traced to platform run events
    observation_run_id = None
    obs = next((a for a in case.artifacts if a.role == "observation"), None)
    if obs is not None:
        from .bundles import import_bundle

        blob = files.read(obs.path)
        try:
            run = import_bundle(s, project_id, blob)
            observation_run_id = run.id
        except (Conflict, InvalidInput):
            observation_run_id = None  # a run with that id already exists, or the bundle is not importable here

    row = ResearchCaseRow(
        id=new_id("rc"), project_id=project_id, case_id=cid, case_version=cver, protocol=case.protocol,
        track=case.identity.track.value, mechanism_family=case.identity.mechanism_family, title=case.identity.title,
        purpose=case.identity.purpose, software_revision=case.software.revision, case_digest=case.case_digest,
        definition_digest=definition_digest(doc), document=doc, observation_run_id=observation_run_id)
    s.add(row)
    s.flush()

    for aid in case.validation.conformance_ids:
        from formal_lab_contracts.research import ConformanceResult

        blob = files.read(artifacts[aid].path)
        res = ConformanceResult.model_validate_json(blob)
        s.add(ResearchConformanceRow(
            id=new_id("cf"), research_case_id=row.id, label=artifacts[aid].id, package_id=res.model.package_id,
            version=res.model.version, model_digest=res.model.digest.value,
            model_version_id=version_ids.get(res.model.digest.value), property_id=res.property_id,
            property_digest=res.property_digest, correspondence=res.correspondence,
            model_verdict=res.model_conclusion.verdict, regression_status=res.program_regression.status,
            document=res.model_dump(mode="json")))
    s.flush()
    return case_detail(s, row.id)


# ------------------------------------------------------------------------------------------------- read / provenance
def _case_summary(row: ResearchCaseRow) -> dict[str, Any]:
    return {"id": row.id, "project_id": row.project_id, "case_id": row.case_id, "case_version": row.case_version,
            "protocol": row.protocol, "track": row.track, "mechanism_family": row.mechanism_family,
            "title": row.title, "purpose": row.purpose, "software_revision": row.software_revision,
            "case_digest": row.case_digest, "observation_run_id": row.observation_run_id,
            "created_at": row.created_at}


def list_cases(s: Session, project_id: str) -> list[dict[str, Any]]:
    get_or_404(s, Project, project_id, "project")
    rows = s.scalars(select(ResearchCaseRow).where(ResearchCaseRow.project_id == project_id)
                     .order_by(ResearchCaseRow.created_at.desc()))
    return [_case_summary(r) for r in rows]


def case_detail(s: Session, rc_id: str) -> dict[str, Any]:
    row = get_or_404(s, ResearchCaseRow, rc_id, "research case")
    case = ResearchCase.model_validate(row.document)
    conf = s.scalars(select(ResearchConformanceRow).where(ResearchConformanceRow.research_case_id == rc_id)
                     .order_by(ResearchConformanceRow.label))
    return {
        **_case_summary(row),
        "software": case.software.model_dump(mode="json"),
        "comparison": case.comparison.model_dump(mode="json"),
        "models": [m.model_dump(mode="json") for m in case.models],
        "correspondence": [c.model_dump(mode="json") for c in case.correspondence],
        "validation": case.validation.model_dump(mode="json"),
        "reproduction": case.reproduction.model_dump(mode="json"),
        "artifacts": [a.model_dump(mode="json") for a in case.artifacts],
        "conformance": [{"id": c.id, "label": c.label, "package_id": c.package_id, "version": c.version,
                         "model_digest": c.model_digest, "model_version_id": c.model_version_id,
                         "property_id": c.property_id, "property_digest": c.property_digest,
                         "correspondence": c.correspondence, "model_verdict": c.model_verdict,
                         "regression_status": c.regression_status, "result": c.document} for c in conf],
    }


def export_case(s: Session, rc_id: str) -> tuple[bytes, str]:
    """Rebuild the exact case directory (case.json without the platform-local stored refs + every artifact file)."""
    row = get_or_404(s, ResearchCaseRow, rc_id, "research case")
    from formal_lab_contracts import ArtifactRef

    doc = {k: v for k, v in row.document.items()}
    prefix = f"{row.case_id}/"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        clean_artifacts = []
        for a in doc["artifacts"]:
            stored = a.get("stored")
            if stored is None:
                raise NotFound(f"artifact {a['id']} has no stored reference")
            blob = artifact_store().get(ArtifactRef.model_validate(stored))
            zf.writestr(prefix + a["path"], blob)
            clean_artifacts.append({k: v for k, v in a.items() if k != "stored"})
        doc["artifacts"] = clean_artifacts
        import json as _json

        zf.writestr(prefix + "case.json", _json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    return buf.getvalue(), f"{row.case_id}-v{row.case_version}.case.zip"


def cases_for_model_version(s: Session, version_id: str) -> list[dict[str, Any]]:
    """The research cases whose conformance results reference this model version (by digest link)."""
    version = get_or_404(s, ModelVersion, version_id, "model version")
    out = []
    conf_rows = s.scalars(select(ResearchConformanceRow).where(
        ResearchConformanceRow.model_digest == version.digest))
    seen = {}
    for c in conf_rows:
        case_row = s.get(ResearchCaseRow, c.research_case_id)
        if case_row is None:
            continue
        entry = seen.setdefault(case_row.id, {**_case_summary(case_row), "conformance": []})
        entry["conformance"].append({"label": c.label, "property_id": c.property_id, "correspondence": c.correspondence,
                                     "model_verdict": c.model_verdict, "regression_status": c.regression_status})
    out = list(seen.values())
    return out


def conformance_for_run(s: Session, run_id: str) -> list[dict[str, Any]]:
    """The conformance verdicts of the cases whose recorded observation is this run."""
    get_or_404(s, Run, run_id, "run")
    case_rows = s.scalars(select(ResearchCaseRow).where(ResearchCaseRow.observation_run_id == run_id))
    out = []
    for case_row in case_rows:
        conf = s.scalars(select(ResearchConformanceRow).where(
            ResearchConformanceRow.research_case_id == case_row.id).order_by(ResearchConformanceRow.label))
        out.append({**_case_summary(case_row),
                    "conformance": [{"label": c.label, "property_id": c.property_id,
                                     "correspondence": c.correspondence, "model_verdict": c.model_verdict,
                                     "regression_status": c.regression_status} for c in conf]})
    return out
