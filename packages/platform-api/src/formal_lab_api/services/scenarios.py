"""Scenarios (versioned by revision) and strategy configurations, validated against plugin schemas."""

from __future__ import annotations

from typing import Any

from formal_lab_contracts import (
    CONTRACT_VERSION,
    PluginInterface,
    PluginRef,
    ReleaseRef,
    RuleSetRef,
    ScenarioManifest,
    compat,
)
from formal_lab_contracts.errors import FieldError, InvalidInput
from formal_lab_runtime.settings import llm_configured
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import Model, ModelVersion, Project, ReleaseRow, RuleSetRow, Scenario, StrategyConfig
from .common import get_or_404, new_id, registry
from .modeling import loaded_of, package_of

DEFAULT_ENV = {"plugin_id": "formal-lab.env.ir-world", "version": "1.1.0"}


def validate_plugin_config(ref: PluginRef, config: dict[str, Any], interface: PluginInterface,
                           path: str = "/config") -> None:
    """The same schema check the registry applies in the worker (P2-017): field-level errors."""
    entry = registry().resolve(ref)
    if entry.descriptor.interface != interface:
        raise InvalidInput(f"{ref.plugin_id} is a {entry.descriptor.interface.value}, expected {interface.value}")
    registry().validate_config(ref, config, path=path)


def scenario_of(row: Scenario) -> ScenarioManifest:
    return compat.upgrade_scenario(row.manifest)


# ------------------------------------------------------------------------ scenarios


def scenario_dict(sc: Scenario, s: Session) -> dict[str, Any]:
    v = s.get(ModelVersion, sc.model_version_id)
    model = s.get(Model, v.model_id) if v else None
    return {"id": sc.id, "project_id": sc.project_id, "name": sc.name, "revision": sc.revision,
            "model_version_id": sc.model_version_id, "model_id": model.id if model else None,
            "model_name": model.name if model else None, "model_version": v.version if v else None,
            "manifest": scenario_of(sc).model_dump(mode="json"), "stored_contract_version": sc.contract_version,
            "copied_from": sc.copied_from, "created_at": sc.created_at, "updated_at": sc.updated_at}


def _ref(s: Session, project_id: str | None, body: dict[str, Any]) -> tuple[RuleSetRef | None, ReleaseRef | None]:
    rules = release = None
    if body.get("rules"):
        r = body["rules"]
        q = select(RuleSetRow).where(RuleSetRow.ruleset_id == r["ruleset_id"], RuleSetRow.version == int(r["version"]))
        if project_id:
            q = q.where(RuleSetRow.project_id == project_id)
        row = s.scalar(q)
        if row is None:
            raise InvalidInput(f"rule set {r['ruleset_id']}@{r['version']} not found",
                               field_errors=[FieldError(path="/rules", message="unknown rule set version")])
        rules = RuleSetRef(ruleset_id=row.ruleset_id, version=row.version, digest={"value": row.digest})
    if body.get("release_id"):
        rel = get_or_404(s, ReleaseRow, body["release_id"], "release")
        if rel.status != "RELEASED":
            raise InvalidInput(f"release {rel.release_id} was rejected; it cannot be run")
        release = ReleaseRef(release_id=rel.release_id, digest={"value": rel.digest})
    return rules, release


def _build_manifest(s: Session, scenario_id: str, revision: int, body: dict[str, Any],
                    project_id: str | None = None) -> tuple[ScenarioManifest, str]:
    version = get_or_404(s, ModelVersion, body.get("model_version_id"), "model version")
    package = package_of(version)
    loaded = loaded_of(package)
    kinds = loaded.property_kinds()
    env = body.get("environment") or {"plugin": DEFAULT_ENV, "config": {}}
    env_ref = PluginRef.model_validate(env["plugin"])
    validate_plugin_config(env_ref, env.get("config", {}), PluginInterface.ENVIRONMENT, "/environment/config")
    participants = body.get("participants") or []
    if not participants:
        raise InvalidInput("a scenario needs at least one participant with a strategy",
                           field_errors=[FieldError(path="/participants", message="at least one participant")])
    action_types = {spec.action_type for spec in loaded.action_specs()}
    errors: list[FieldError] = []
    for i, p in enumerate(participants):
        ref = PluginRef.model_validate(p["strategy"]["plugin"])
        validate_plugin_config(ref, p["strategy"].get("config", {}), PluginInterface.PLANNER,
                               f"/participants/{i}/strategy/config")
        if p.get("goal") and p["goal"] not in kinds:
            errors.append(FieldError(path=f"/participants/{i}/goal", message=f"unknown property {p['goal']!r}"))
        for t in (p.get("scope") or {}).get("action_types", []):
            if t not in action_types:
                errors.append(FieldError(path=f"/participants/{i}/scope/action_types",
                                         message=f"unknown action type {t!r}"))
    for i, sc in enumerate(body.get("stop_conditions", [])):
        if sc.get("property_id") and sc["property_id"] not in kinds:
            errors.append(FieldError(path=f"/stop_conditions/{i}/property_id",
                                     message=f"unknown property {sc['property_id']!r}"))
    term = body.get("termination") or {}
    for name in [term.get("joint_goal"), *term.get("invariants", [])]:
        if name and name not in kinds:
            errors.append(FieldError(path="/termination", message=f"unknown property {name!r}"))
    objective = body.get("objective")
    if objective:
        if objective.get("goal_property") not in kinds:
            errors.append(FieldError(path="/objective/goal_property",
                                     message=f"unknown property {objective.get('goal_property')!r}"))
        declared = {o.id for o in package.ir.objectives} if package.is_ir else set()
        for j, level in enumerate(objective.get("levels", [])):
            if level.get("model_objective") and level["model_objective"] not in declared:
                errors.append(FieldError(path=f"/objective/levels/{j}/model_objective",
                                         message=f"the model declares no objective {level['model_objective']!r}"))
    if errors:
        raise InvalidInput("invalid scenario", field_errors=errors)
    rules, release = _ref(s, project_id, body)
    try:
        manifest = ScenarioManifest(
            scenario_id=scenario_id, revision=revision, name=body["name"], description=body.get("description"),
            model=package.ref(), environment=env, participants=participants, objectives=body.get("objectives", []),
            budget=body.get("budget") or {"max_steps": 60}, seed=int(body.get("seed", 0)),
            stop_conditions=body.get("stop_conditions", []), extensions=body.get("extensions", {}),
            turns=body.get("turns") or {}, termination=body.get("termination"), objective=objective,
            driver=body.get("driver"), rules=rules, release=release,
        )
    except ValidationError as exc:
        raise InvalidInput("invalid scenario", field_errors=[
            FieldError(path="/" + "/".join(map(str, e["loc"])), message=e["msg"]) for e in exc.errors()]) from exc
    return manifest, version.id


def create_scenario(s: Session, project_id: str, body: dict[str, Any], copied_from: str | None = None) -> Scenario:
    get_or_404(s, Project, project_id, "project")
    sid = new_id("scn")
    manifest, version_id = _build_manifest(s, sid, 1, body, project_id)
    row = Scenario(id=sid, project_id=project_id, model_version_id=version_id, name=manifest.name, revision=1,
                   manifest=manifest.model_dump(mode="json"), copied_from=copied_from,
                   contract_version=CONTRACT_VERSION)
    s.add(row)
    s.flush()
    return row


def update_scenario(s: Session, scenario_id: str, body: dict[str, Any]) -> Scenario:
    row = get_or_404(s, Scenario, scenario_id, "scenario")
    if body.get("expected_revision") is not None and int(body["expected_revision"]) != row.revision:
        from formal_lab_contracts.errors import Conflict

        raise Conflict(f"scenario was modified (revision {row.revision}); reload before saving")
    merged = {**_editable(row), **{k: v for k, v in body.items() if k != "expected_revision"}}
    manifest, version_id = _build_manifest(s, row.id, row.revision + 1, merged, row.project_id)
    row.revision += 1
    row.manifest, row.model_version_id, row.name = manifest.model_dump(mode="json"), version_id, manifest.name
    row.contract_version = CONTRACT_VERSION
    return row


def copy_scenario(s: Session, scenario_id: str, name: str | None = None) -> Scenario:
    row = get_or_404(s, Scenario, scenario_id, "scenario")
    body = _editable(row)
    body["name"] = name or f"{row.name} (copy)"
    return create_scenario(s, row.project_id, body, copied_from=row.id)


def _editable(row: Scenario) -> dict[str, Any]:
    m = scenario_of(row).model_dump(mode="json")
    out = {"name": m["name"], "description": m.get("description"), "model_version_id": row.model_version_id,
           "environment": m["environment"], "participants": m["participants"], "objectives": m["objectives"],
           "budget": m["budget"], "seed": m["seed"], "stop_conditions": m["stop_conditions"],
           "extensions": m.get("extensions", {}), "turns": m["turns"], "termination": m.get("termination"),
           "objective": m.get("objective"), "driver": m.get("driver")}
    if m.get("rules"):
        out["rules"] = {"ruleset_id": m["rules"]["ruleset_id"], "version": m["rules"]["version"]}
    if m.get("release"):
        out["release_id"] = m["release"]["release_id"]
    return out


# ------------------------------------------------------------------------ strategies


def strategy_dict(st: StrategyConfig) -> dict[str, Any]:
    entry = registry().resolve((st.plugin_id, st.plugin_version))
    return {"id": st.id, "project_id": st.project_id, "name": st.name, "plugin_id": st.plugin_id,
            "plugin_version": st.plugin_version, "config": st.config, "created_at": st.created_at,
            "updated_at": st.updated_at, "descriptor": entry.descriptor.model_dump(mode="json"),
            "source_kind": entry.descriptor.ui.category}


def upsert_strategy(s: Session, project_id: str, body: dict[str, Any], strategy_id: str | None = None) -> StrategyConfig:
    get_or_404(s, Project, project_id, "project")
    ref = PluginRef(plugin_id=body["plugin_id"], version=body.get("plugin_version") or
                    registry().latest(body["plugin_id"]).descriptor.version)
    config = body.get("config", {}) or {}
    validate_plugin_config(ref, config, PluginInterface.PLANNER)
    if strategy_id is None:
        row = StrategyConfig(id=new_id("stg"), project_id=project_id, name=body.get("name") or ref.plugin_id,
                             plugin_id=ref.plugin_id, plugin_version=ref.version, config=config)
        s.add(row)
    else:
        row = get_or_404(s, StrategyConfig, strategy_id, "strategy")
        row.name, row.plugin_id, row.plugin_version, row.config = (body.get("name") or row.name, ref.plugin_id,
                                                                   ref.version, config)
    s.flush()
    return row


def compatibility(s: Session, strategy_id: str, scenario_id: str) -> dict[str, Any]:
    st = get_or_404(s, StrategyConfig, strategy_id, "strategy")
    sc = get_or_404(s, Scenario, scenario_id, "scenario")
    version = get_or_404(s, ModelVersion, sc.model_version_id, "model version")
    d = registry().resolve((st.plugin_id, st.plugin_version)).descriptor
    problems = []
    if d.semantic_profiles and version.semantic_profile not in d.semantic_profiles:
        problems.append(f"strategy does not support profile {version.semantic_profile}")
    if d.has_capability("plan.llm") and st.config.get("client", "openai_compatible") != "stub" and not llm_configured():
        problems.append("LLM strategy needs FAL_LLM_API_KEY (or client=stub for a labelled stand-in)")
    return {"compatible": not problems, "problems": problems, "strategy": st.id, "scenario": sc.id,
            "semantic_profile": version.semantic_profile}


def list_scenarios(s: Session, project_id: str) -> list[Scenario]:
    return list(s.scalars(select(Scenario).where(Scenario.project_id == project_id).order_by(Scenario.created_at)))


def list_strategies(s: Session, project_id: str) -> list[StrategyConfig]:
    return list(s.scalars(select(StrategyConfig).where(StrategyConfig.project_id == project_id)
                          .order_by(StrategyConfig.created_at)))
