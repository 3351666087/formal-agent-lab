"""Seed the neutral-scheduling demo project (idempotent): `python -m formal_lab_api.seed`."""

from __future__ import annotations

import json

from formal_lab_example_scheduling.model import build_model
from formal_lab_example_scheduling.scenarios import BUDGET, SCENARIO_CONFIGS, STOP, STRATEGIES
from sqlalchemy import select

from .db import Model, Project, Scenario, StrategyConfig, session_scope
from .services import catalog, modeling, scenarios

DEMO_PROJECT = "生产调度示例"


def seed() -> dict[str, object]:
    with session_scope() as s:
        catalog.sync_catalog(s)
        project = s.scalar(select(Project).where(Project.name == DEMO_PROJECT))
        if project is None:
            project = modeling.create_project(s, DEMO_PROJECT, "Neutral production-scheduling example (phase 1)",
                                              group="examples")
        model = s.scalar(select(Model).where(Model.project_id == project.id, Model.package_id == "neutral-scheduling"))
        if model is None:
            model, version = modeling.create_model(s, project.id, package_id="neutral-scheduling", name="生产调度模型",
                                                   ir=build_model().model_dump(mode="json"), origin="seed")
        else:
            version = modeling.add_version(s, model.id, ir=build_model().model_dump(mode="json"), note="seed refresh")
        existing = {sc.manifest.get("extensions", {}).get("formal-lab.examples", {}).get("data", {}).get("key")
                    for sc in s.scalars(select(Scenario).where(Scenario.project_id == project.id))}
        for key, cfg in SCENARIO_CONFIGS.items():
            if key in existing:
                continue
            scenarios.create_scenario(s, project.id, {
                "name": cfg["name"], "description": cfg["description"], "model_version_id": version.id,
                "environment": {"plugin": {"plugin_id": "formal-lab.env.ir-world", "version": "1.0.0"},
                                "config": cfg["env"]},
                "participants": [{"actor_id": "dispatcher", "role": "dispatcher", "strategy": STRATEGIES["rule"]}],
                "objectives": [{"property_id": "all_done", "description": "complete all orders"},
                               {"metric_id": "delay_cost", "description": "minimise simulated delay cost"}],
                "budget": BUDGET, "seed": 0, "stop_conditions": STOP,
                "extensions": {"formal-lab.examples": {"version": "1.0.0", "schema_id": "formal-lab.examples/key@1",
                                                       "data": {"key": key}}},
            })
        names = {st.name for st in s.scalars(select(StrategyConfig).where(StrategyConfig.project_id == project.id))}
        labels = {"rule": "EDD 规则", "z3": "Z3 有界规划", "llm": "LLM（真实模型）", "llm-stub": "LLM 替身（stub）"}
        for key, spec in STRATEGIES.items():
            if labels[key] in names:
                continue
            scenarios.upsert_strategy(s, project.id, {"name": labels[key], "plugin_id": spec["plugin"]["plugin_id"],
                                                      "plugin_version": spec["plugin"]["version"],
                                                      "config": spec["config"]})
        return {"project_id": project.id, "model_id": model.id, "model_version": version.version}


def main() -> None:
    print(json.dumps(seed(), ensure_ascii=False))


if __name__ == "__main__":
    main()
