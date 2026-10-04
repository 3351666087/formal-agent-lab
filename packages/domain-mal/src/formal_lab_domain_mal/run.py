"""Run a lowered MAL model on the platform (phase 3B, D1).

The formal closed loop's `run` step: a red-team attacker, played by the bounded Z3 planner, drives the neutral
`ir-world` environment on the lowered package until it reaches the target step — a real platform episode (import →
lower → run), not just a static reachability check. D3 adds richer red/blue strategies and model revision; this is the
minimal single-attacker episode D1 needs.
"""

from __future__ import annotations

from typing import Any

from formal_lab_contracts import ModelPackage, ScenarioManifest

IR_WORLD = {"plugin_id": "formal-lab.env.ir-world", "version": "1.0.0"}
Z3_PLANNER = {"plugin_id": "formal-lab.planner.z3-bounded", "version": "1.1.0"}


RED_STRATEGIES = {
    "symbolic": lambda horizon, gp: {"plugin": Z3_PLANNER,
                                     "config": {"goal_property": gp, "horizon": horizon,
                                                "fallback_order": ["compromise"]}},
    "rule": lambda horizon, gp: {"plugin": {"plugin_id": "formal-lab.domain.mal.red-rule", "version": "1.0.0"},
                                 "config": {}},
    "hybrid": lambda horizon, gp: {"plugin": {"plugin_id": "formal-lab.domain.mal.red-hybrid", "version": "1.0.0"},
                                   "config": {"client": "stub"}},
}


def red_team_scenario(package: ModelPackage, *, goal_property: str = "target_reached", horizon: int = 60,
                      seed: int = 0, scenario_id: str | None = None, name: str = "MAL red-team",
                      description: str = "", execution_gates: list[dict] | None = None,
                      strategy: str = "symbolic", max_model_calls: int = 0,
                      env_config: dict | None = None, red_config: dict | None = None) -> ScenarioManifest:
    """A single-attacker scenario in the ir-world environment. `strategy` picks the red planner (symbolic = Z3
    bounded, rule = greedy, hybrid = model-assisted). `execution_gates` (D2) wires pre-send gates like the Broker.
    `env_config` passes ir-world options such as `truth_constant_overrides` (D3 model-deviation) or `observation`.
    `red_config` merges into the red strategy config (e.g. {"client": "openai_compatible"} for a real-model hybrid)."""
    strat = RED_STRATEGIES[strategy](horizon, goal_property)
    if red_config:
        strat = {**strat, "config": {**strat.get("config", {}), **red_config}}
    return ScenarioManifest(
        scenario_id=scenario_id or f"mal-{package.package_id}",
        name=name,
        description=description or f"A red-team attacker plans its way to {goal_property} on {package.package_id}.",
        model=package.ref(),
        environment={"plugin": IR_WORLD, "config": env_config or {}},
        participants=[{"actor_id": "red", "role": "attacker", "strategy": strat}],
        objectives=[{"property_id": goal_property, "description": "the attacker reaches the target step"}],
        budget={"max_steps": horizon, "max_wall_seconds": 300, "max_model_calls": max_model_calls,
                "max_tokens": 200_000 if max_model_calls else 0},
        seed=seed,
        execution_gates=execution_gates or [],
        stop_conditions=[{"kind": "GOAL_REACHED", "property_id": goal_property}, {"kind": "NO_APPLICABLE_ACTION"}],
    )


BLUE = {"plugin_id": "formal-lab.domain.mal.blue-defender", "version": "1.0.0"}


def red_blue_scenario(package: ModelPackage, *, goal_property: str = "target_reached", horizon: int = 120,
                      seed: int = 0, strategy: str = "rule", max_model_calls: int = 0, scenario_id: str | None = None,
                      env_config: dict | None = None, no_progress_limit: int = 4,
                      red_config: dict | None = None, execution_gates: list[dict] | None = None) -> ScenarioManifest:
    """A turn-taking red/blue episode (phase 4B, B1): red (rule / hybrid / symbolic) and a reactive blue defender
    alternate (ROUND_ROBIN) on a defence-enabled package. Red compromises steps; blue, from its observation, hardens
    steps. The referee (the environment state) decides the outcome: red reaches `goal_property`, or blue contains it
    (red runs out of applicable steps and no progress is made). Needs a package built with `include_defense=True`."""
    strat = RED_STRATEGIES[strategy](horizon, goal_property)
    if red_config:
        strat = {**strat, "config": {**strat.get("config", {}), **red_config}}
    return ScenarioManifest(
        scenario_id=scenario_id or f"mal-rb-{package.package_id}",
        name="MAL 红蓝对抗",
        description=f"Red ({strategy}) and a reactive blue defender take turns on {package.package_id}; red reaches "
                    f"{goal_property}, or blue contains it.",
        model=package.ref(),
        environment={"plugin": IR_WORLD, "config": env_config or {}},
        participants=[
            {"actor_id": "red", "role": "attacker", "strategy": strat, "scope": {"action_types": ["compromise"]}},
            {"actor_id": "blue", "role": "defender", "strategy": {"plugin": BLUE, "config": {}},
             "scope": {"action_types": ["harden"]}},
        ],
        objectives=[{"property_id": goal_property, "description": "the attacker reaches the target step"}],
        budget={"max_steps": horizon, "max_wall_seconds": 300, "max_model_calls": max_model_calls,
                "max_tokens": 200_000 if max_model_calls else 0},
        seed=seed,
        turns={"mode": "ROUND_ROBIN"},
        execution_gates=execution_gates or [],
        termination={"joint_goal": goal_property, "on_no_action": "SKIP_ACTOR", "no_progress_limit": no_progress_limit},
    )


def run_red_team(package: ModelPackage, *, registry: Any = None, goal_property: str = "target_reached",
                 horizon: int = 60, seed: int = 0, project_id: str = "phase3b-d1") -> Any:
    """Run one red-team episode in-process and return the LocalRunResult."""
    from formal_lab_runtime import default_registry, make_manifest, new_run_id, run_local

    reg = registry or default_registry()
    scn = red_team_scenario(package, goal_property=goal_property, horizon=horizon, seed=seed)
    manifest = make_manifest(run_id=new_run_id(), project_id=project_id, scenario=scn, package=package, registry=reg)
    return run_local(manifest, package, reg)


def run_summary(result: Any, id_map: dict[str, str] | None = None) -> dict[str, Any]:
    """A compact, offline-readable summary of a red-team episode: status, why it ended, and the attack it performed."""
    inv = {v: k for k, v in (id_map or {}).items()}
    plan = []
    for st in result.steps:
        action = (st.proposal.action if st.proposal else None)
        if action is not None:
            n = action.params.get("n")
            plan.append({"step": st.step, "action": action.action_type, "target": inv.get(n, n)})
    return {"status": str(result.status), "reason": result.reason,
            "termination_reason": str(result.termination_reason), "steps": len(result.steps),
            "attack_path": plan}
