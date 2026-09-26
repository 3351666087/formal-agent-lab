"""Scenarios (versioned by revision) and strategy configurations, validated against plugin schemas."""

from __future__ import annotations

from typing import Any

import jsonschema
from formal_lab_contracts import (
    PluginInterface,
    PluginRef,
    ScenarioManifest,
)
from formal_lab_contracts.errors import FieldError, InvalidInput
from formal_lab_runtime.settings import llm_configured
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import Model, ModelVersion, Project, Scenario, StrategyConfig
from .common import get_or_404, new_id, registry
from .modeling import package_of

DEFAULT_ENV = {"plugin_id": "formal-lab.env.ir-world", "version": "1.0.0"}


def validate_plugin_config(ref: PluginRef, config: dict[str, Any], interface: PluginInterface) -> None:
    entry = registry().get(ref)
    if entry.descriptor.interface != interface:
        raise InvalidInput(f"{ref.plugin_id} is a {entry.descriptor.interface.value}, expected {interface.value}")
    try:
        jsonschema.validate(config, entry.descriptor.config_schema)
    except jsonschema.ValidationError as exc:
        raise InvalidInput(f"invalid config for {ref.plugin_id}: {exc.message}",
                           field_errors=[FieldError(path="/config/" + "/".join(map(str, exc.absolute_path)),
                                                    message=exc.message)]) from exc


# ------------------------------------------------------------------------ scenarios


def scenario_dict(sc: Scenario, s: Session) -> dict[str, Any]:
    v = s.get(ModelVersion, sc.model_version_id)
    model = s.get(Model, v.model_id) if v else None
    return {"id": sc.id, "project_id": sc.project_id, "name": sc.name, "revision": sc.revision,
            "model_version_id": sc.model_version_id, "model_id": model.id if model else None,
            "model_name": model.name if model else None, "model_version": v.version if v else None,
            "manifest": sc.manifest, "copied_from": sc.copied_from, "created_at": sc.created_at,
            "updated_at": sc.updated_at}


def _build_manifest(s: Session, scenario_id: str, revision: int, body: dict[str, Any]) -> tuple[ScenarioManifest, str]:
    version = get_or_404(s, ModelVersion, body.get("model_version_id"), "model version")
    package = package_of(version)
    env = body.get("environment") or {"plugin": DEFAULT_ENV, "config": {}}
    env_ref = PluginRef.model_validate(env["plugin"])
    validate_plugin_config(env_ref, env.get("config", {}), PluginInterface.ENVIRONMENT)
    participants = body.get("participants") or []
    if not participants:
        raise InvalidInput("a scenario needs at least one participant with a strategy")
    for p in participants:
        ref = PluginRef.model_validate(p["strategy"]["plugin"])
        validate_plugin_config(ref, p["strategy"].get("config", {}), PluginInterface.PLANNER)
    goals = {pr.id for pr in package.ir.properties}
    for sc in body.get("stop_conditions", []):
        if sc.get("property_id") and sc["property_id"] not in goals:
            raise InvalidInput(f"stop condition refers to unknown property {sc['property_id']!r}")
    try:
        manifest = ScenarioManifest(
            scenario_id=scenario_id, revision=revision, name=body["name"], description=body.get("description"),
            model=package.ref(), environment=env, participants=participants, objectives=body.get("objectives", []),
            budget=body.get("budget") or {"max_steps": 60}, seed=int(body.get("seed", 0)),
            stop_conditions=body.get("stop_conditions", []), extensions=body.get("extensions", {}),
        )
    except ValidationError as exc:
        raise InvalidInput("invalid scenario", field_errors=[
            FieldError(path="/" + "/".join(map(str, e["loc"])), message=e["msg"]) for e in exc.errors()]) from exc
    return manifest, version.id


def create_scenario(s: Session, project_id: str, body: dict[str, Any], copied_from: str | None = None) -> Scenario:
    get_or_404(s, Project, project_id, "project")
    sid = new_id("scn")
    manifest, version_id = _build_manifest(s, sid, 1, body)
    row = Scenario(id=sid, project_id=project_id, model_version_id=version_id, name=manifest.name, revision=1,
                   manifest=manifest.model_dump(mode="json"), copied_from=copied_from)
    s.add(row)
    s.flush()
    return row


def update_scenario(s: Session, scenario_id: str, body: dict[str, Any]) -> Scenario:
    row = get_or_404(s, Scenario, scenario_id, "scenario")
    if body.get("expected_revision") is not None and int(body["expected_revision"]) != row.revision:
        from formal_lab_contracts.errors import Conflict

        raise Conflict(f"scenario was modified (revision {row.revision}); reload before saving")
    merged = {**_editable(row), **{k: v for k, v in body.items() if k != "expected_revision"}}
    manifest, version_id = _build_manifest(s, row.id, row.revision + 1, merged)
    row.revision += 1
    row.manifest, row.model_version_id, row.name = manifest.model_dump(mode="json"), version_id, manifest.name
    return row


def copy_scenario(s: Session, scenario_id: str, name: str | None = None) -> Scenario:
    row = get_or_404(s, Scenario, scenario_id, "scenario")
    body = _editable(row)
    body["name"] = name or f"{row.name} (copy)"
    return create_scenario(s, row.project_id, body, copied_from=row.id)


def _editable(row: Scenario) -> dict[str, Any]:
    m = row.manifest
    return {"name": m["name"], "description": m.get("description"), "model_version_id": row.model_version_id,
            "environment": m["environment"], "participants": m["participants"], "objectives": m["objectives"],
            "budget": m["budget"], "seed": m["seed"], "stop_conditions": m["stop_conditions"],
            "extensions": m.get("extensions", {})}


# ------------------------------------------------------------------------ strategies


def strategy_dict(st: StrategyConfig) -> dict[str, Any]:
    entry = registry().get((st.plugin_id, st.plugin_version))
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
    d = registry().get((st.plugin_id, st.plugin_version)).descriptor
    problems = []
    if version.semantic_profile not in d.semantic_profiles:
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
