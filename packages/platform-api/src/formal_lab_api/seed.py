"""Seed the demo projects (idempotent): `python -m formal_lab_api.seed`.

- 生产调度示例: the phase-1 scheduling project (model v1 and its four scenarios, unchanged) plus model v2 with the
  declared cost objectives, a two-dispatcher scenario and a cost-optimal Z3 strategy.
- 仓储分配示例: the second semantic profile (warehouse_alloc_v1) — one operator, or a receiver and a picker.
"""

from __future__ import annotations

import json

from formal_lab_example_scheduling.model import build_model
from formal_lab_example_scheduling.scenarios import (
    BUDGET,
    SCENARIO_CONFIGS,
    STOP,
    STRATEGIES,
    TWO_DISPATCHER_CONFIGS,
)
from formal_lab_example_warehouse import NAMESPACE, SCHEMA_ID, demo_model
from formal_lab_example_warehouse import scenarios as wh
from sqlalchemy import select

from .db import Model, ModelVersion, Project, Scenario, StrategyConfig, session_scope
from .services import catalog, modeling, scenarios

DEMO_PROJECT = "生产调度示例"
WAREHOUSE_PROJECT = "仓储分配示例"
ORDERS_PROJECT = "订单服务示例"
EXT = "formal-lab.examples"


def _ext(key: str) -> dict:
    return {EXT: {"version": "1.0.0", "schema_id": f"{EXT}/key@1", "data": {"key": key}}}


def _existing_keys(s, project_id: str) -> set[str]:
    return {sc.manifest.get("extensions", {}).get(EXT, {}).get("data", {}).get("key")
            for sc in s.scalars(select(Scenario).where(Scenario.project_id == project_id))}


def _strategies(s, project_id: str, specs: dict[str, tuple[str, str, dict]]) -> dict[str, str]:
    have = {st.name: st.id for st in s.scalars(select(StrategyConfig).where(StrategyConfig.project_id == project_id))}
    for name, (plugin_id, version, config) in specs.items():
        if name not in have:
            have[name] = scenarios.upsert_strategy(s, project_id, {"name": name, "plugin_id": plugin_id,
                                                                   "plugin_version": version, "config": config}).id
    return have


def seed_scheduling(s) -> dict[str, object]:
    project = s.scalar(select(Project).where(Project.name == DEMO_PROJECT))
    if project is None:
        project = modeling.create_project(s, DEMO_PROJECT, "Neutral production-scheduling example", group="examples")
    model = s.scalar(select(Model).where(Model.project_id == project.id, Model.package_id == "neutral-scheduling"))
    if model is None:
        model, version = modeling.create_model(s, project.id, package_id="neutral-scheduling", name="生产调度模型",
                                               ir=build_model().model_dump(mode="json"), origin="seed")
    else:
        version = modeling.get_version(s, model.id, 1)
    existing = _existing_keys(s, project.id)
    for key, cfg in SCENARIO_CONFIGS.items():
        if key in existing:
            continue
        scenarios.create_scenario(s, project.id, {
            "name": cfg["name"], "description": cfg["description"], "model_version_id": version.id,
            "environment": {"plugin": {"plugin_id": "formal-lab.env.ir-world", "version": "1.1.0"},
                            "config": cfg["env"]},
            "participants": [{"actor_id": "dispatcher", "role": "dispatcher", "strategy": STRATEGIES["rule"]}],
            "objectives": [{"property_id": "all_done", "description": "complete all orders"},
                           {"metric_id": "delay_cost", "description": "minimise simulated delay cost"}],
            "budget": BUDGET, "seed": 0, "stop_conditions": STOP, "extensions": _ext(key),
        })
    labels = {"rule": "EDD 规则", "z3": "Z3 有界规划", "llm": "LLM（真实模型）", "llm-stub": "LLM 替身（stub）",
              "task-rule": "任务计划（规则生成）", "task-symbolic": "任务计划（符号生成）",
              "task-model": "任务计划（模型生成，真实模型）", "task-model-stub": "任务计划（模型生成，替身）",
              "z3-cost": "Z3 成本最优"}
    specs = {labels[k]: (v["plugin"]["plugin_id"], v["plugin"]["version"], v["config"]) for k, v in STRATEGIES.items()}
    ids = _strategies(s, project.id, specs)
    # model v2: the same scheduling semantics plus the declared cost objectives (delay_cost, effort)
    from formal_lab_model import ir_digest

    with_objectives = build_model(with_objectives=True)
    v2 = s.scalar(select(ModelVersion).where(ModelVersion.model_id == model.id,
                                             ModelVersion.digest == ir_digest(with_objectives).value))
    if v2 is None:
        v2 = modeling.add_version(s, model.id, ir=with_objectives.model_dump(mode="json"),
                                  note="declare cost objectives delay_cost and effort", origin="seed")
    objective = {"objective_id": "delay_then_effort", "goal_property": "all_done", "horizon": 18,
                 "levels": [{"id": "delay", "model_objective": "delay_cost"},
                            {"id": "effort", "model_objective": "effort"}]}
    if "cost-shortage" not in existing:
        cfg = SCENARIO_CONFIGS["resource-shortage"]
        scenarios.create_scenario(s, project.id, {
            "name": "资源不足（成本目标）", "description": cfg["description"] + " Objective: delay cost, then effort.",
            "model_version_id": v2.id,
            "environment": {"plugin": {"plugin_id": "formal-lab.env.ir-world", "version": "1.1.0"},
                            "config": cfg["env"]},
            "participants": [{"actor_id": "dispatcher", "role": "dispatcher", "strategy": STRATEGIES["rule"]}],
            "budget": BUDGET, "seed": 0, "objective": objective,
            "termination": {"joint_goal": "all_done", "on_no_action": "FAIL"}, "extensions": _ext("cost-shortage"),
        })
    if "two-dispatchers" not in existing:
        scenarios.create_scenario(s, project.id, {
            "name": "两名调度员（轮流）", "model_version_id": v2.id,
            "description": "Two dispatchers share all machines and take turns; round-start observations, conflicts "
                           "decided by world revision.",
            "environment": {"plugin": {"plugin_id": "formal-lab.env.ir-world", "version": "1.1.0"},
                            "config": SCENARIO_CONFIGS["normal"]["env"]},
            "participants": [
                {"actor_id": "dispatcher_a", "role": "dispatcher", "label": "调度员 A", "strategy": STRATEGIES["rule"]},
                {"actor_id": "dispatcher_b", "role": "dispatcher", "label": "调度员 B", "strategy": STRATEGIES["z3"]}],
            "budget": BUDGET, "seed": 0, "objective": objective,
            "turns": {"mode": "ROUND_ROBIN", "observation_timing": "ROUND_START", "conflict_policy": "REVALIDATE"},
            "termination": {"joint_goal": "all_done", "on_no_action": "SKIP_ACTOR", "no_progress_limit": 12},
            "extensions": _ext("two-dispatchers"),
        })
    for key, (label, pair) in {"two-rule-rule": ("两名调度员：规则+规则", TWO_DISPATCHER_CONFIGS["rule+rule"]),
                               "two-model-symbolic": ("两名调度员：模型+符号（需模型配置）",
                                                      TWO_DISPATCHER_CONFIGS["model+symbolic"])}.items():
        if key in existing:
            continue
        scenarios.create_scenario(s, project.id, {
            "name": label, "model_version_id": v2.id,
            "description": "Two dispatchers share all machines and take turns (" + " + ".join(pair) + ")"
                           + ("; the model participant needs FAL_LLM_* configured, otherwise the run fails at "
                              "start with that reason" if "llm" in pair else ""),
            "environment": {"plugin": {"plugin_id": "formal-lab.env.ir-world", "version": "1.1.0"},
                            "config": SCENARIO_CONFIGS["normal"]["env"]},
            "participants": [
                {"actor_id": "dispatcher_a", "role": "dispatcher", "label": "调度员 A", "strategy": STRATEGIES[pair[0]]},
                {"actor_id": "dispatcher_b", "role": "dispatcher", "label": "调度员 B", "strategy": STRATEGIES[pair[1]]}],
            "budget": BUDGET, "seed": 0, "objective": objective,
            "turns": {"mode": "ROUND_ROBIN", "observation_timing": "ROUND_START", "conflict_policy": "REVALIDATE"},
            "termination": {"joint_goal": "all_done", "on_no_action": "SKIP_ACTOR", "no_progress_limit": 12},
            "extensions": _ext(key),
        })
    return {"project_id": project.id, "model_id": model.id, "model_version": version.version, "strategies": ids}


def seed_warehouse(s) -> dict[str, object]:
    project = s.scalar(select(Project).where(Project.name == WAREHOUSE_PROJECT))
    if project is None:
        project = modeling.create_project(s, WAREHOUSE_PROJECT, "Second semantic profile: warehouse_alloc_v1",
                                          group="examples")
    model = s.scalar(select(Model).where(Model.project_id == project.id, Model.package_id == "warehouse"))
    payload = {"semantic_profile": "warehouse_alloc_v1", "namespace": NAMESPACE, "schema_id": SCHEMA_ID,
               "data": json.loads(demo_model().model_dump_json()),
               "frontend": {"plugin_id": "formal-lab.example.warehouse.frontend", "version": "1.0.0"},
               "source_format": "warehouse-json/v1"}
    if model is None:
        model, version = modeling.create_model(s, project.id, package_id="warehouse", name="仓储分配模型",
                                               payload=payload, origin="seed")
    else:
        version = modeling.get_version(s, model.id, 1)
    rules = {"plugin_id": wh.RULES["plugin_id"], "version": wh.RULES["version"]}
    ids = _strategies(s, project.id, {"仓储规则（全部）": (rules["plugin_id"], rules["version"], {"role": "both"}),
                                      "仓储规则（收货）": (rules["plugin_id"], rules["version"], {"role": "receiver"}),
                                      "仓储规则（拣货）": (rules["plugin_id"], rules["version"], {"role": "picker"})})
    existing = _existing_keys(s, project.id)
    package = modeling.package_of(version)
    for key, manifest in (("wh-single", wh.single(package)), ("wh-two-roles", wh.receiver_and_picker(package))):
        if key in existing:
            continue
        body = manifest.model_dump(mode="json", exclude={"scenario_id", "revision", "model", "contract_version"})
        scenarios.create_scenario(s, project.id, {**body, "model_version_id": version.id, "extensions": _ext(key)})
    return {"project_id": project.id, "model_id": model.id, "strategies": ids}


def seed_orders(s) -> dict[str, object]:
    """The local order service example: the five cases on the business service (endpoint FAL_ORDERS_ENDPOINT,
    default the loopback port of `make orders-up`; `http://orders:8765` inside the Compose stack) and the same
    cases on the pure-data model for comparison."""
    from formal_lab_example_orders.instance import CASES
    from formal_lab_example_orders.model import PACKAGE_ID, build_model
    from formal_lab_example_orders.scenarios import STRATEGIES as ORDER_STRATEGIES
    from formal_lab_example_orders.scenarios import scenario as order_scenario
    from formal_lab_runtime.settings import get_setting

    endpoint = get_setting("FAL_ORDERS_ENDPOINT", "http://127.0.0.1:8765") or "http://127.0.0.1:8765"
    project = s.scalar(select(Project).where(Project.name == ORDERS_PROJECT))
    if project is None:
        project = modeling.create_project(s, ORDERS_PROJECT, "Independent business service (FastAPI + SQLite) as a "
                                          "persistent environment, next to a pure-data model of it", group="examples")
    model = s.scalar(select(Model).where(Model.project_id == project.id, Model.package_id == PACKAGE_ID))
    if model is None:
        model, version = modeling.create_model(s, project.id, package_id=PACKAGE_ID, name="订单处理模型",
                                               ir=build_model().model_dump(mode="json"), origin="seed")
    else:
        version = modeling.get_version(s, model.id, 1)
    ids = _strategies(s, project.id, {name: (spec["plugin"]["plugin_id"], spec["plugin"]["version"], spec["config"])
                                      for name, spec in {"订单处理规则": ORDER_STRATEGIES["rule"],
                                                         "Z3 有界规划（订单）": ORDER_STRATEGIES["z3"]}.items()})
    existing = _existing_keys(s, project.id)
    run_defaults = {"version": "1.0.0", "schema_id": "formal-lab.run-defaults/config@1",
                    "data": {"config": {"initial_check_horizon": 0}}}
    specs = [(f"orders-{case}", case, "service") for case in CASES] + \
            [(f"orders-{case}-pure", case, "pure") for case in ("normal", "deviation")]
    for key, case, backend in specs:
        if key in existing:
            continue
        manifest = order_scenario(case, backend=backend, endpoint=endpoint)
        body = manifest.model_dump(mode="json", exclude={"scenario_id", "revision", "model", "contract_version"})
        body["extensions"] = {**_ext(key), "formal-lab.run-defaults": run_defaults}
        scenarios.create_scenario(s, project.id, {**body, "model_version_id": version.id})
    return {"project_id": project.id, "model_id": model.id, "strategies": ids, "endpoint": endpoint}


def seed() -> dict[str, object]:
    with session_scope() as s:
        catalog.sync_catalog(s)
        out = {"scheduling": seed_scheduling(s)}
        out["warehouse"] = seed_warehouse(s)
        out["orders"] = seed_orders(s)
        return out


def main() -> None:
    print(json.dumps(seed(), ensure_ascii=False))


if __name__ == "__main__":
    main()
