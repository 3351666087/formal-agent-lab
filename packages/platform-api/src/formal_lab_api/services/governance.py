"""Rule sets, model releases, regression cases and revision suggestions (P2-070 … P2-077).

- Rule sets are immutable versions: an edit inserts version n+1 (parent n). Saving compiles and type-checks every
  rule against the model version it is written for; an invalid rule is rejected with its field path.
- A release runs the pre-release checks (`formal_lab_runtime.release.check_release`: type checks, rules, bounded
  queries, the project's regression cases) and stores the ModelReleaseRecord with its log as an artifact. Releases
  are content-addressed: the same model, rules and results give the same release id. Runs may pin a RELEASED release;
  the model and rules they use must be the released ones.
- Regression cases come from runs (effect differences, counterexamples); any case can be replayed on any version of
  its model.
- Revision suggestions are the MODEL_REVISION_SUGGESTED events of a run, with the regression case each produced.
"""

from __future__ import annotations

from typing import Any

from formal_lab_contracts import (
    ModelReleaseRecord,
    RegressionCase,
    ReleaseRef,
    RuleSet,
    RuleSetRef,
    utcnow,
)
from formal_lab_contracts.errors import FieldError, InvalidInput, NotFound
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import Model, ModelVersion, RegressionCaseRow, ReleaseRow, RuleSetRow, RunEvent
from .common import get_or_404, new_id, put_json_artifact, registry
from .modeling import loaded_of, package_of

# ------------------------------------------------------------------ rule sets


def ruleset_dict(row: RuleSetRow) -> dict[str, Any]:
    return {"id": row.id, "project_id": row.project_id, "ruleset_id": row.ruleset_id, "version": row.version,
            "digest": row.digest, "model_version_id": row.model_version_id, "ruleset": row.body,
            "created_at": row.created_at}


def save_ruleset(s: Session, project_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """New rule-set version (edits never overwrite): compiled and type-checked against its model version."""
    from formal_lab_model.rules import check_rule, ruleset_digest

    version_row = get_or_404(s, ModelVersion, body.get("model_version_id"), "model version")
    model = s.get(Model, version_row.model_id)
    if model is None or model.project_id != project_id:
        raise InvalidInput("the model version belongs to another project")
    ruleset_id = str(body.get("ruleset_id") or "").strip()
    if not ruleset_id:
        raise InvalidInput("ruleset_id is required", field_errors=[FieldError(path="/ruleset_id", message="required")])
    latest = s.scalar(select(func.max(RuleSetRow.version)).where(RuleSetRow.project_id == project_id,
                                                                 RuleSetRow.ruleset_id == ruleset_id)) or 0
    package = package_of(version_row)
    try:
        rs = RuleSet.model_validate({"ruleset_id": ruleset_id, "version": latest + 1, "name": body.get("name") or
                                     ruleset_id, "model": package.ref().model_dump(mode="json"),
                                     "rules": body.get("rules", []), "parent_version": latest or None,
                                     "note": body.get("note"), "created_at": utcnow().isoformat()})
    except ValidationError as exc:
        raise InvalidInput("rule set does not match its schema", field_errors=[
            FieldError(path="/" + "/".join(str(x) for x in e["loc"]), message=e["msg"]) for e in exc.errors()]) from exc
    loaded = loaded_of(package)
    if not hasattr(loaded, "checked"):
        raise InvalidInput(f"rules need a model with an expression semantics; {package.semantic_profile} has none")
    errors = [FieldError(path=f"/rules/{i}{issue.path.split(rule.rule_id, 1)[-1]}", message=issue.message)
              for i, rule in enumerate(rs.rules) for issue in check_rule(rule, loaded.checked)]
    if errors:
        raise InvalidInput(f"{len(errors)} problem(s) in the rules", field_errors=errors)
    rs = rs.model_copy(update={"digest": None})
    rs = RuleSet.model_validate({**rs.model_dump(mode="json"), "digest": {"value": ruleset_digest(rs)}})
    row = RuleSetRow(id=new_id("rls"), project_id=project_id, ruleset_id=ruleset_id, version=rs.version,
                     digest=rs.digest.value, model_version_id=version_row.id, body=rs.model_dump(mode="json"))
    s.add(row)
    s.flush()
    return ruleset_dict(row)


def list_rulesets(s: Session, project_id: str, ruleset_id: str | None = None) -> list[dict[str, Any]]:
    q = select(RuleSetRow).where(RuleSetRow.project_id == project_id)
    if ruleset_id:
        q = q.where(RuleSetRow.ruleset_id == ruleset_id)
    return [ruleset_dict(r) for r in s.scalars(q.order_by(RuleSetRow.ruleset_id, RuleSetRow.version))]


def _ruleset_row(s: Session, project_id: str, ref: dict[str, Any]) -> RuleSetRow:
    row = s.scalar(select(RuleSetRow).where(RuleSetRow.project_id == project_id,
                                            RuleSetRow.ruleset_id == ref.get("ruleset_id"),
                                            RuleSetRow.version == int(ref.get("version") or 0)))
    if row is None:
        raise NotFound(f"rule set {ref.get('ruleset_id')}@{ref.get('version')} not found")
    return row


# ------------------------------------------------------------------ releases


def release_dict(row: ReleaseRow) -> dict[str, Any]:
    return {"release_id": row.release_id, "project_id": row.project_id, "model_version_id": row.model_version_id,
            "ruleset_row_id": row.ruleset_row_id, "status": row.status, "digest": row.digest, "record": row.record,
            "created_at": row.created_at}


def create_release(s: Session, model_version_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """Run the pre-release checks and store the record (content-addressed: re-checking the same inputs returns the
    existing release)."""
    from formal_lab_runtime.release import check_release

    version_row = get_or_404(s, ModelVersion, model_version_id, "model version")
    model = get_or_404(s, Model, version_row.model_id, "model")
    package = package_of(version_row)
    rs_row = _ruleset_row(s, model.project_id, body["ruleset"]) if body.get("ruleset") else None
    ruleset = RuleSet.model_validate(rs_row.body) if rs_row else None
    if rs_row is not None and rs_row.model_version_id != version_row.id:
        raise InvalidInput(f"rule set {rs_row.ruleset_id}@{rs_row.version} was written for another model version; "
                           "save it as a new version against this one first (rules are checked with their model)")
    selection = body.get("regression", "model")
    q = select(RegressionCaseRow).where(RegressionCaseRow.project_id == model.project_id)
    rows = list(s.scalars(q.order_by(RegressionCaseRow.created_at)))
    cases = [RegressionCase.model_validate(r.case) for r in rows]
    if selection == "model":  # every case recorded for this model (any version)
        cases = [c for c in cases if c.model.package_id == package.package_id]
    elif selection == "none":
        cases = []
    elif isinstance(selection, list):
        wanted = set(selection)
        cases = [c for c in cases if c.case_id in wanted]
        missing = wanted - {c.case_id for c in cases}
        if missing:
            raise NotFound(f"regression case(s) not found: {sorted(missing)}")
    record, log = check_release(package, registry(), ruleset=ruleset, cases=cases,
                                horizon=int(body.get("horizon", 6)), timeout_ms=int(body.get("timeout_ms", 10000)))
    existing = s.get(ReleaseRow, record.release_id)
    if existing is not None:
        return release_dict(existing)
    ref = put_json_artifact(s, run_id=None, kind="release_log", name=f"{record.release_id}.log.json",
                            obj={"release_id": record.release_id, "log": log},
                            format_version="formal-lab/release-log@1")
    record = record.model_copy(update={"log": ref})
    record = ModelReleaseRecord.model_validate(record.model_dump(mode="json"))
    row = ReleaseRow(release_id=record.release_id, project_id=model.project_id, model_version_id=version_row.id,
                     ruleset_row_id=rs_row.id if rs_row else None, status=record.status, digest=record.digest.value,
                     record=record.model_dump(mode="json"))
    s.add(row)
    s.flush()
    return release_dict(row)


def list_releases(s: Session, project_id: str) -> list[dict[str, Any]]:
    rows = s.scalars(select(ReleaseRow).where(ReleaseRow.project_id == project_id).order_by(ReleaseRow.created_at))
    return [release_dict(r) for r in rows]


def get_release(s: Session, release_id: str) -> dict[str, Any]:
    return release_dict(get_or_404(s, ReleaseRow, release_id, "release"))


def pinned_release(s: Session, release_id: str, package_ref: Any, rules: RuleSetRef | None) -> ReleaseRef:
    """A run may pin only a RELEASED release of exactly the model (and rules) it uses (P2-072)."""
    rel = get_or_404(s, ReleaseRow, release_id, "release")
    if rel.status != "RELEASED":
        raise InvalidInput(f"release {rel.release_id} was rejected; it cannot be run")
    record = ModelReleaseRecord.model_validate(rel.record)
    if record.model.digest != package_ref.digest:
        raise InvalidInput(f"release {release_id} is for {record.model.package_id}@{record.model.version}; this run "
                           f"uses {package_ref.package_id}@{package_ref.version}")
    if rules is not None and (record.ruleset is None or record.ruleset.digest != rules.digest):
        raise InvalidInput(f"release {release_id} was not checked with rule set {rules.ruleset_id}@{rules.version}")
    return ReleaseRef(release_id=rel.release_id, digest={"value": rel.digest})


# ------------------------------------------------------------------ regression cases


def case_dict(row: RegressionCaseRow) -> dict[str, Any]:
    return {"case_id": row.case_id, "project_id": row.project_id, "model_digest": row.model_digest,
            "source": row.source, "origin_run_id": row.origin_run_id, "case": row.case, "created_at": row.created_at}


def list_cases(s: Session, project_id: str, package_id: str | None = None) -> list[dict[str, Any]]:
    rows = s.scalars(select(RegressionCaseRow).where(RegressionCaseRow.project_id == project_id)
                     .order_by(RegressionCaseRow.created_at))
    out = [case_dict(r) for r in rows]
    return [c for c in out if package_id is None or c["case"]["model"]["package_id"] == package_id]


def replay_case(s: Session, case_id: str, model_version_id: str) -> dict[str, Any]:
    from formal_lab_runtime.release import replay_regression_case

    row = get_or_404(s, RegressionCaseRow, case_id, "regression case")
    version_row = get_or_404(s, ModelVersion, model_version_id, "model version")
    package = package_of(version_row)
    case = RegressionCase.model_validate(row.case)
    if case.model.package_id != package.package_id:
        raise InvalidInput(f"case {case_id} was recorded for model {case.model.package_id}, not {package.package_id}")
    result = replay_regression_case(case, package, registry())
    return {"case_id": case_id, "model": package.ref().model_dump(mode="json"),
            "recorded_with": case.model.model_dump(mode="json"), **result.model_dump(mode="json")}


# ------------------------------------------------------------------ revision suggestions


def revision_suggestions(s: Session, run_id: str) -> list[dict[str, Any]]:
    rows = list(s.scalars(select(RunEvent).where(RunEvent.run_id == run_id, RunEvent.event_type.in_(
        ["MODEL_REVISION_SUGGESTED", "REGRESSION_CASE_CREATED"])).order_by(RunEvent.seq)))
    cases = {(r.logical_step, r.actor_id): r.payload["case"]["case_id"] for r in rows
             if r.event_type == "REGRESSION_CASE_CREATED"}
    return [{"step": r.logical_step, "actor_id": r.actor_id, "seq": r.seq, **r.payload,
             "regression_case_id": cases.get((r.logical_step, r.actor_id))}
            for r in rows if r.event_type == "MODEL_REVISION_SUGGESTED"]
