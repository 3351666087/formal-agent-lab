"""Warehouse scenarios: one operator, or a receiver and a picker taking turns (driver-world environment)."""

from __future__ import annotations

from formal_lab_contracts import ModelPackage, ScenarioManifest

from .model import demo_model, two_station_model
from .plugins import build_package

ENV = {"plugin_id": "formal-lab.env.driver-world", "version": "1.0.0"}
RULES = {"plugin_id": "formal-lab.example.warehouse.rules", "version": "1.0.0"}
TERMINATION = {"joint_goal": "all_picked", "invariants": ["capacity_ok"], "on_no_action": "SKIP_ACTOR",
               "no_progress_limit": 12}
BUDGET = {"max_steps": 80, "max_wall_seconds": 300}


def package(version: int = 1) -> ModelPackage:
    return build_package(demo_model(), package_id="warehouse", version=version)


def two_station_package() -> ModelPackage:
    return build_package(two_station_model(), package_id="warehouse-two-stations")


def single(pkg: ModelPackage, *, seed: int = 0, env: dict | None = None) -> ScenarioManifest:
    return ScenarioManifest(
        scenario_id="wh-single", name="仓储：单人作业", model=pkg.ref(), environment={"plugin": ENV, "config": env or {}},
        participants=[{"actor_id": "operator", "role": "operator",
                       "strategy": {"plugin": RULES, "config": {"role": "both"}}}],
        budget=BUDGET, seed=seed, termination=TERMINATION)


def receiver_and_picker(pkg: ModelPackage, *, seed: int = 0, env: dict | None = None,
                        turns: dict | None = None) -> ScenarioManifest:
    """Two participants with separate action scopes, one shared world, round-robin turns: the receiver puts
    pallets away (its own goal: clear docks), the picker assigns the station and picks (joint goal)."""
    return ScenarioManifest(
        scenario_id="wh-two-roles", name="仓储：收货员 + 拣货员轮流作业", model=pkg.ref(),
        environment={"plugin": ENV, "config": env or {}},
        participants=[
            {"actor_id": "receiver", "role": "receiver", "goal": "docks_clear", "budget": {"max_steps": 30},
             "strategy": {"plugin": RULES, "config": {"role": "receiver"}},
             "scope": {"action_types": ["putaway", "tick"]}},
            {"actor_id": "picker", "role": "picker", "strategy": {"plugin": RULES, "config": {"role": "picker"}},
             "scope": {"action_types": ["assign", "release", "pick", "tick"]}},
        ],
        budget=BUDGET, seed=seed, termination=TERMINATION, turns=turns or {})
