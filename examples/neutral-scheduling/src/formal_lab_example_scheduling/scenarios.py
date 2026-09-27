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
TASK = {"plugin_id": "formal-lab.example.scheduling.task-planner", "version": "1.0.0"}
TASK_RULE = {"plugin": TASK, "config": {"generator": "rule"}}
TASK_SYMBOLIC = {"plugin": TASK, "config": {"generator": "symbolic", "horizon": 18}}
TASK_MODEL = {"plugin": TASK, "config": {"generator": "model"}}
TASK_MODEL_STUB = {"plugin": TASK, "config": {"generator": "model", "client": "stub"}}
Z3_COST = {"plugin": {"plugin_id": "formal-lab.planner.z3-bounded", "version": "1.1.0"},
           "config": {"mode": "cost", "horizon": 18, "timeout_ms": 30000, "fallback_order": ["assign", "resume",
                                                                                            "advance"]}}
STRATEGIES = {"rule": RULE_STRATEGY, "z3": Z3_STRATEGY, "llm": LLM_STRATEGY, "llm-stub": LLM_STUB_STRATEGY,
              "task-rule": TASK_RULE, "task-symbolic": TASK_SYMBOLIC, "task-model": TASK_MODEL,
              "task-model-stub": TASK_MODEL_STUB, "z3-cost": Z3_COST}
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


def scenario(key: str, package: ModelPackage, *, seed: int = 0, strategy: dict | None = None,
             no_progress_limit: int | None = None) -> ScenarioManifest:
    """One of the single-dispatcher scenarios. With `no_progress_limit` the v1 stop conditions are replaced by the
    equivalent v2 termination policy plus a stop after that many consecutive turns without a state change (P2-047);
    without it the manifest is exactly the phase-1 one."""
    cfg = SCENARIO_CONFIGS[key]
    ending: dict = {"stop_conditions": STOP}
    if no_progress_limit is not None:
        ending = {"termination": {"joint_goal": "all_done", "on_no_action": "FAIL",
                                  "no_progress_limit": no_progress_limit}}
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
        **ending,
    )


def all_scenarios(package: ModelPackage) -> list[ScenarioManifest]:
    return [scenario(k, package) for k in SCENARIO_CONFIGS]


# the three delivered two-participant configurations (P2-039); the model one needs a configured endpoint
TWO_DISPATCHER_CONFIGS: dict[str, tuple[str, str]] = {"rule+rule": ("rule", "rule"),
                                                      "rule+symbolic": ("rule", "z3"),
                                                      "model+symbolic": ("llm", "z3")}


def two_dispatchers(package: ModelPackage, *, seed: int = 0, strategies: tuple[str, str] = ("rule", "rule"),
                    timing: str = "TURN_START", conflict_policy: str = "REVALIDATE", key: str = "normal",
                    turns: dict | None = None, env: dict | None = None,
                    configs: tuple[dict | None, dict | None] = (None, None)) -> ScenarioManifest:
    """Two production dispatchers share the line and take turns (one action per logical step).

    Both may assign any operation to any machine, so with ROUND_START observations the second dispatcher acts on
    the state of the round's start and can ask for a machine the first one just took — the environment arbitrates
    by world revision (REVALIDATE: apply if still applicable; REJECT_STALE: reject when what the action depends on
    changed since the proposal's revision). Joint goal: all orders done.
    """
    cfg = SCENARIO_CONFIGS[key]

    def strat(name: str, extra: dict | None) -> dict:
        spec = dict(STRATEGIES[name])
        if extra:
            spec = {"plugin": spec["plugin"], "config": {**spec["config"], **extra}}
        return spec

    return ScenarioManifest(
        scenario_id=f"sched-two-{key}",
        name=f"两名调度员：{cfg['name']}",
        description="Two dispatchers coordinate the same machines, taking turns; " + cfg["description"],
        model=package.ref(),
        environment={"plugin": ENV_REF, "config": {**cfg["env"], **(env or {})}},
        participants=[
            {"actor_id": "dispatcher_a", "role": "dispatcher", "label": "调度员 A",
             "strategy": strat(strategies[0], configs[0])},
            {"actor_id": "dispatcher_b", "role": "dispatcher", "label": "调度员 B",
             "strategy": strat(strategies[1], configs[1])},
        ],
        objectives=[{"property_id": "all_done", "description": "complete all orders"}],
        budget=BUDGET,
        seed=seed,
        termination={"joint_goal": "all_done", "on_no_action": "SKIP_ACTOR", "no_progress_limit": 12},
        turns=turns or {"mode": "ROUND_ROBIN", "observation_timing": timing, "conflict_policy": conflict_policy},
    )
