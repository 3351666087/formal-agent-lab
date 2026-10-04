"""Projects, models and immutable model versions, validation, diffs and bounded checks."""

from __future__ import annotations

from typing import Any

from formal_lab_contracts import (
    CONTRACT_VERSION,
    CheckQuery,
    ModelIR,
    ModelPackage,
    ModelSource,
    PluginRef,
    compat,
    digest_of,
    utcnow,
)
from formal_lab_contracts.errors import Conflict, InvalidInput
from formal_lab_model import check_model, diff_models, ir_digest, parse_ir
from formal_lab_model.capability_matrix import MATRIX
from formal_lab_model.frontend import SOURCE_FORMAT, build_package
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import CheckRow, Model, ModelVersion, Project, Run, Scenario
from .common import get_or_404, new_id, registry

DEFAULT_VERIFIER = PluginRef(plugin_id="formal-lab.verifier.z3-bmc", version="1.1.0")


# ------------------------------------------------------------------------ projects


def project_dict(p: Project, s: Session | None = None) -> dict[str, Any]:
    out = {"id": p.id, "name": p.name, "description": p.description, "group": p.group,
           "created_at": p.created_at, "updated_at": p.updated_at}
    if s is not None:
        out["counts"] = {
            "models": s.scalar(select(func.count()).select_from(Model).where(Model.project_id == p.id)),
            "scenarios": s.scalar(select(func.count()).select_from(Scenario).where(Scenario.project_id == p.id)),
            "runs": s.scalar(select(func.count()).select_from(Run).where(Run.project_id == p.id)),
        }
    return out


def create_project(s: Session, name: str, description: str | None = None, group: str | None = None) -> Project:
    if not name.strip():
        raise InvalidInput("project name is required")
    p = Project(id=new_id("prj"), name=name.strip(), description=description, group=group)
    s.add(p)
    s.flush()
    return p


def update_project(s: Session, project_id: str, **fields: Any) -> Project:
    p = get_or_404(s, Project, project_id, "project")
    for k in ("name", "description", "group"):
        if fields.get(k) is not None:
            setattr(p, k, fields[k])
    return p


# ------------------------------------------------------------------------ validation


def validate_ir(data: dict[str, Any] | str) -> dict[str, Any]:
    """Type-check without saving; returns issues (never raises for model errors)."""
    try:
        ir = parse_ir(data)
    except InvalidInput as exc:
        return {"valid": False, "schema_errors": [e.model_dump() for e in exc.field_errors], "issues": []}
    checked = check_model(ir)
    out: dict[str, Any] = {"valid": not checked.issues, "schema_errors": [],
                           "issues": [i.model_dump() for i in checked.issues], "digest": ir_digest(ir).value}
    if not checked.issues:
        out["summary"] = {
            "state_locations": len(checked.state_paths()),
            "ground_actions": len(checked.ground_actions),
            "properties": {pid: p.kind for pid, p in checked.properties.items()},
            "domains": {k: len(v) for k, v in checked.domains.items()},
        }
    return out


# ------------------------------------------------------------------------ models / versions


def model_dict(m: Model) -> dict[str, Any]:
    return {"id": m.id, "project_id": m.project_id, "package_id": m.package_id, "name": m.name,
            "description": m.description, "latest_version": m.latest_version, "created_at": m.created_at,
            "updated_at": m.updated_at}


def version_dict(v: ModelVersion, *, full: bool = True) -> dict[str, Any]:
    out = {"id": v.id, "model_id": v.model_id, "version": v.version, "digest": v.digest,
           "semantic_profile": v.semantic_profile, "parent_version": v.parent_version, "note": v.note,
           "created_at": v.created_at, "stored_contract_version": v.contract_version}
    if full:
        out["package"] = package_of(v).model_dump(mode="json")  # v2 view; v1 rows are upgraded on the way
    return out


def package_of(v: ModelVersion) -> ModelPackage:
    """The v2 ModelPackage of a stored version (phase-1 rows are validated as v1, then upgraded)."""
    return compat.upgrade_model_package(v.package)


def loaded_of(package: ModelPackage):
    """The package loaded by the semantic driver of its profile (any profile)."""
    driver = registry().create(registry().driver_for(package.semantic_profile).descriptor.ref(), {}, None)
    return driver.load(package)


def create_model(s: Session, project_id: str, *, package_id: str, name: str | None, ir: dict[str, Any] | None = None,
                 description: str | None = None, origin: str = "api", payload: dict[str, Any] | None = None,
                 source: dict[str, Any] | None = None,
                 frontend: dict[str, Any] | None = None) -> tuple[Model, ModelVersion]:
    get_or_404(s, Project, project_id, "project")
    if s.scalar(select(Model).where(Model.project_id == project_id, Model.package_id == package_id)):
        raise Conflict(f"model {package_id!r} already exists in this project")
    model = Model(id=new_id("mdl"), project_id=project_id, package_id=package_id, name=name or package_id,
                  description=description)
    s.add(model)
    s.flush()
    version = add_version(s, model.id, ir=ir, payload=payload, source=source, frontend=frontend,
                          note="initial version", origin=origin)
    return model, version


def _source_package(model: Model, version: int, source: dict[str, Any], frontend: dict[str, Any] | None, origin: str,
                    parent_version: int | None) -> ModelPackage:
    """A model given as a frontend source envelope (P2-013, phase 4B): a registered MODEL_FRONTEND plugin compiles it
    into the package, so the package keeps everything the frontend records (for MAL, the attack-graph extension the
    gates and strategies read). The frontend is named explicitly; the source format must be the one it accepts."""
    from formal_lab_contracts import PluginInterface

    if not frontend:
        raise InvalidInput("a source import needs `frontend` (the MODEL_FRONTEND plugin id/version)")
    if "format" not in source or "text" not in source:
        raise InvalidInput("a source import needs `source.format` and `source.text`")
    entry = registry().resolve(PluginRef.model_validate(frontend))
    if entry.descriptor.interface != PluginInterface.MODEL_FRONTEND:
        raise InvalidInput(f"{entry.descriptor.plugin_id} is not a MODEL_FRONTEND")
    fe = registry().create(entry.descriptor.ref(), {}, None)
    src = ModelSource(format=source["format"], text=source["text"], origin=origin, parent_version=parent_version)
    package = fe.compile(src, package_id=model.package_id, version=version)
    return package.model_copy(update={"frontend": entry.descriptor.ref()})


def _namespaced_package(model: Model, version: int, payload: dict[str, Any], origin: str,
                        parent_version: int | None) -> ModelPackage:
    """A model in a profile-specific format: validated by the semantic driver of its profile (P2-013)."""
    profile = payload.get("semantic_profile")
    if not profile:
        raise InvalidInput("a namespaced model needs `semantic_profile`")
    body = {k: payload[k] for k in ("namespace", "schema_id", "data") if k in payload}
    if len(body) != 3:
        raise InvalidInput("a namespaced model needs namespace, schema_id and data")
    entry = registry().driver_for(profile)
    frontend = payload.get("frontend") or entry.descriptor.ref().model_dump()
    package = ModelPackage(package_id=model.package_id, version=version, frontend=frontend,
                           semantic_profile=profile, digest=digest_of(body),
                           payload={"kind": "namespaced", **body},
                           source=ModelSource(format=payload.get("source_format", f"{body['schema_id']}+json"),
                                              origin=origin, parent_version=parent_version),
                           created_at=utcnow())
    problems = registry().create(entry.descriptor.ref(), {}, None).validate(package)
    if problems:
        raise InvalidInput(f"model does not satisfy {entry.descriptor.plugin_id}",
                           details={"problems": problems[:20]})
    return package


def add_version(s: Session, model_id: str, *, ir: dict[str, Any] | ModelIR | None = None, note: str | None = None,
                parent_version: int | None = None, origin: str = "editor", payload: dict[str, Any] | None = None,
                source: dict[str, Any] | None = None, frontend: dict[str, Any] | None = None) -> ModelVersion:
    """Editing a model = inserting a new immutable version. Unchanged content returns the latest version."""
    model = s.get(Model, model_id, with_for_update=True)
    if model is None:
        raise InvalidInput(f"model {model_id} not found")
    if source is not None:
        version_no = model.latest_version + 1
        package = _source_package(model, version_no, source, frontend, origin,
                                  parent_version or (model.latest_version or None))
        if model.latest_version:
            latest = s.scalar(select(ModelVersion).where(ModelVersion.model_id == model_id,
                                                         ModelVersion.version == model.latest_version))
            if latest is not None and latest.digest == package.digest.value:
                return latest
        row = ModelVersion(id=new_id("mv"), model_id=model_id, version=version_no, digest=package.digest.value,
                           semantic_profile=package.semantic_profile, package=package.model_dump(mode="json"),
                           contract_version=CONTRACT_VERSION, parent_version=package.source.parent_version, note=note)
        model.latest_version = version_no
        s.add(row)
        s.flush()
        return row
    if payload is not None:
        version_no = model.latest_version + 1
        package = _namespaced_package(model, version_no, payload, origin,
                                      parent_version or (model.latest_version or None))
        if model.latest_version:
            latest = s.scalar(select(ModelVersion).where(ModelVersion.model_id == model_id,
                                                         ModelVersion.version == model.latest_version))
            if latest is not None and latest.digest == package.digest.value:
                return latest
        row = ModelVersion(id=new_id("mv"), model_id=model_id, version=version_no, digest=package.digest.value,
                           semantic_profile=package.semantic_profile, package=package.model_dump(mode="json"),
                           contract_version=CONTRACT_VERSION, parent_version=package.source.parent_version,
                           note=note)
        model.latest_version = version_no
        s.add(row)
        s.flush()
        return row
    if ir is None:
        raise InvalidInput("give `ir` (neutral IR model) or `payload` (profile-specific model)")
    parsed = ir if isinstance(ir, ModelIR) else parse_ir(ir)
    digest = ir_digest(parsed).value
    if model.latest_version:
        latest = s.scalar(select(ModelVersion).where(ModelVersion.model_id == model_id,
                                                     ModelVersion.version == model.latest_version))
        if latest is not None and latest.digest == digest:
            return latest
    version = model.latest_version + 1
    package = build_package(parsed, package_id=model.package_id, version=version,
                            source=ModelSource(format=SOURCE_FORMAT, text=parsed.model_dump_json(indent=2),
                                               origin=origin, parent_version=parent_version or
                                               (model.latest_version or None)))
    row = ModelVersion(id=new_id("mv"), model_id=model_id, version=version, digest=digest,
                       semantic_profile=package.semantic_profile, package=package.model_dump(mode="json"),
                       contract_version=CONTRACT_VERSION,
                       parent_version=parent_version or (model.latest_version or None), note=note)
    model.latest_version = version
    s.add(row)
    s.flush()
    return row


def get_version(s: Session, model_id: str, version: int) -> ModelVersion:
    row = s.scalar(select(ModelVersion).where(ModelVersion.model_id == model_id, ModelVersion.version == version))
    if row is None:
        raise InvalidInput(f"model {model_id} has no version {version}")
    return row


def list_versions(s: Session, model_id: str) -> list[ModelVersion]:
    return list(s.scalars(select(ModelVersion).where(ModelVersion.model_id == model_id)
                          .order_by(ModelVersion.version)))


def diff_versions(s: Session, model_id: str, a: int, b: int) -> list[dict[str, Any]]:
    va, vb = get_version(s, model_id, a), get_version(s, model_id, b)
    pa, pb = package_of(va), package_of(vb)
    if not (pa.is_ir and pb.is_ir):
        from formal_lab_model.diff import ModelChange

        changes = [] if pa.digest == pb.digest else [ModelChange(
            section="payload", name=pa.semantic_profile, kind="changed", before=pa.digest.value,
            after=pb.digest.value)]
        return [c.model_dump() for c in changes]
    return [c.model_dump() for c in diff_models(pa.ir, pb.ir)]


def version_details(v: ModelVersion) -> dict[str, Any]:
    package = package_of(v)
    loaded = loaded_of(package)
    out = {
        **version_dict(v),
        "action_specs": [spec.model_dump(mode="json") for spec in loaded.action_specs()],
        "summary": {"state_locations": len(loaded.state_paths()),
                    "ground_actions": loaded.display().get("ground_actions")},
        "display": loaded.display(),
        "driver": registry().driver_for(package.semantic_profile).descriptor.ref().model_dump(),
        "capability_matrix": [row.model_dump() for row in MATRIX],
    }
    if package.is_ir:
        checked = check_model(package.ir)
        out["summary"] = {"state_locations": len(checked.state_paths()),
                          "ground_actions": len(checked.ground_actions)}
        out["objectives"] = [o.model_dump(mode="json") for o in package.ir.objectives]
    return out


# ------------------------------------------------------------------------ checks


def run_check(s: Session, model_version_id: str, query: dict[str, Any],
              state: dict[str, Any] | None = None, unknown_paths: list[str] | None = None,
              verifier: PluginRef | None = None) -> CheckRow:
    """Run a bounded check and store it with its replayable query bundle (P2-029)."""
    from formal_lab_runtime.query import run_query

    from ..db import QueryBundleRow

    v = get_or_404(s, ModelVersion, model_version_id, "model version")
    model = get_or_404(s, Model, v.model_id, "model")
    package = package_of(v)
    q = CheckQuery.model_validate(query)
    bundle = run_query(registry(), package, q, verifier=verifier or DEFAULT_VERIFIER, state=state,
                       unknown_paths=unknown_paths, services=_Services(package))
    result = bundle.result
    row = CheckRow(id=result.check_id, project_id=model.project_id, model_version_id=v.id,
                   query=q.model_dump(mode="json"), result=result.model_dump(mode="json"), verdict=str(result.verdict))
    s.add(row)
    s.add(QueryBundleRow(id=bundle.bundle_id, project_id=model.project_id, model_version_id=v.id,
                         check_id=result.check_id, bundle=bundle.model_dump(mode="json")))
    s.flush()
    return row


def check_dict(c: CheckRow, s: Session | None = None) -> dict[str, Any]:
    out = {"id": c.id, "model_version_id": c.model_version_id, "query": c.query, "verdict": c.verdict,
           "result": c.result, "created_at": c.created_at}
    if s is not None:
        from ..db import QueryBundleRow

        qb = s.scalar(select(QueryBundleRow).where(QueryBundleRow.check_id == c.id))
        if qb is not None:
            out["query_bundle_id"] = qb.id
            out["explanation"] = qb.bundle.get("explanation", [])
            out["replay"] = qb.bundle.get("replay", {})
    if "explanation" not in out:
        from formal_lab_contracts import compat
        from formal_lab_model.explain import explain_check

        out["explanation"] = explain_check(compat.upgrade_check_result(c.result))
    return out


def query_bundle(s: Session, bundle_id: str, *, embed_package: bool = False) -> dict[str, Any]:
    from ..db import QueryBundleRow

    row = get_or_404(s, QueryBundleRow, bundle_id, "query bundle")
    data = dict(row.bundle)
    if embed_package:
        data["package"] = package_of(get_or_404(s, ModelVersion, row.model_version_id, "model version")).model_dump(
            mode="json")
    return data


def replay_bundle(s: Session, bundle: dict[str, Any]) -> dict[str, Any]:
    """Replay an uploaded / stored query bundle against the stored model version with the same digest."""
    from formal_lab_contracts import QueryBundle
    from formal_lab_runtime.query import replay_query

    qb = QueryBundle.model_validate(bundle)
    row = s.scalar(select(ModelVersion).where(ModelVersion.digest == qb.model.digest.value))
    if row is not None:
        package = package_of(row)
    elif qb.package is not None:
        package = qb.package
    else:
        raise InvalidInput(f"model {qb.model.package_id}@{qb.model.version} ({qb.model.digest.value[:12]}) is not "
                           "stored on this server and the bundle does not embed it")
    return replay_query(registry(), package, qb, services=_Services(package))


class _Services:
    def __init__(self, package: ModelPackage):
        self.package = package

    def pinned_model(self) -> ModelPackage:
        return self.package

    def get_model(self, ref):
        return self.package

    def get_setting(self, key: str) -> str | None:
        from formal_lab_runtime.settings import get_setting

        return get_setting(key)
