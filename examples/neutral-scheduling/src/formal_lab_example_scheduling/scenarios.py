"""The four required production-scheduling scenarios (all driven by the pure-data IR world)."""

from __future__ import annotations

from formal_lab_contracts import ModelPackage, ModelSource, ScenarioManifest
from formal_lab_model import build_package

from .model import build_model

PACKAGE_ID = "neutral-scheduling"
ENV_REF = {"plugin_id": "formal-lab.env.ir-world", "version": "1.0.0"}
RULE_STRATEGY = {"plugin": {"plugin_id": "formal-lab.example.scheduling.edd-dispatch", "version": "1.0.0"},
                 "config": {}}
Z3_STRATEGY = {"plugin": {"plugin_id": "formal-lab.planner.z3-bounded", "version": "1.0.0"},
               "config": {"horizon": 18, "fallback_order": ["assign", "resume", "advance"]}}
LLM_STRATEGY = {"plugin": {"plugin_id": "formal-lab.planner.llm", "version": "1.0.0"}, "config": {}}
LLM_STUB_STRATEGY = {"plugin": {"plugin_id": "formal-lab.planner.llm", "version": "1.0.0"},
                     "config": {"client": "stub", "stub_preference": ["assign", "resume", "advance"]}}
STRATEGIES = {"rule": RULE_STRATEGY, "z3": Z3_STRATEGY, "llm": LLM_STRATEGY, "llm-stub": LLM_STUB_STRATEGY}
BUDGET = {"max_steps": 60, "max_wall_seconds": 600, "max_model_calls": 80, "max_tokens": 800_000}
STOP = [{"kind": "GOAL_REACHED", "property_id": "all_done"}, {"kind": "NO_APPLICABLE_ACTION"}]
VARIATION = [{"var": "proc_time", "delta_min": -1, "delta_max": 1}]

SCENARIO_CONFIGS: dict[str, dict] = {
    "normal": {
        "name": "正常调度",
        "description": "Adequate machines and resources; processing times vary ±1 per seed.",
        "env": {"seeded_variation": VARIATION},
    },
    "resource-shortage": {
        "name": "资源不足",
        "description": "Only one fixture and one operator: operations contend for resources and orders run late.",
        "env": {"seeded_variation": VARIATION,
                "initial_overrides": {"res_cap[fixture]": 1, "res_cap[operator]": 1}},
    },
    "state-delay": {
        "name": "状态延迟",
        "description": "Line state (phase / machine occupancy / remaining time) reaches the dispatcher 2 steps late; "
        "current values are unknown and preconditions may be UNKNOWN.",
        "env": {"seeded_variation": VARIATION,
                "observation": {"delay_steps": {"phase": 2, "on": 2, "remaining": 2, "finish": 2}}},
    },
    "expectation-mismatch": {
        "name": "预期与模拟结果不一致",
        "description": "Machine m2 is secretly degraded in the simulated world (progresses every other tick); "
        "the dispatcher's model predicts normal progress, so effect comparisons report differences.",
        "env": {"seeded_variation": VARIATION, "truth_constant_overrides": {"degraded[m2]": True}},
    },
}


def model_package(version: int = 1) -> ModelPackage:
    ir = build_model()
    return build_package(ir, package_id=PACKAGE_ID, version=version,
                         source=ModelSource(format="fal-ir-json/v1", text=ir.model_dump_json(indent=2),
                                            origin="examples/neutral-scheduling"))


def scenario(key: str, package: ModelPackage, *, seed: int = 0, strategy: dict | None = None) -> ScenarioManifest:
    cfg = SCENARIO_CONFIGS[key]
    return ScenarioManifest(
        scenario_id=f"sched-{key}",
        name=cfg["name"],
        description=cfg["description"],
        model=package.ref(),
        environment={"plugin": ENV_REF, "config": cfg["env"]},
        participants=[{"actor_id": "dispatcher", "role": "dispatcher", "strategy": strategy or RULE_STRATEGY}],
        objectives=[{"property_id": "all_done", "description": "complete all orders"},
                    {"metric_id": "delay_cost", "description": "minimise simulated delay cost"}],
        budget=BUDGET,
        seed=seed,
        stop_conditions=STOP,
    )


def all_scenarios(package: ModelPackage) -> list[ScenarioManifest]:
    return [scenario(k, package) for k in SCENARIO_CONFIGS]
