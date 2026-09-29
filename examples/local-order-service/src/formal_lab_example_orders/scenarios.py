"""The five repeatable order-handling cases on either backend (P2-065 / P2-066).

`scenario(case, backend="service" | "pure", …)` builds the same scenario for the business service (through the
environment adapter) or the pure-data model (ir-world running the order IR from the same instance). The service's
operating conditions (slow station, held responses, crash point) come with the case; on the pure backend the slow
station is the model's hidden-reality constant `slow[p2]`, the others do not exist (a pure simulator neither loses
answers nor crashes).
"""

from __future__ import annotations

from typing import Any

from formal_lab_contracts import PluginRef, ScenarioManifest

from .env import ENV_ID, ENV_VERSION
from .instance import CASES, initial_overrides, instance
from .model import model_package

INVENTORY_GATE_ID = "formal-lab.example.orders.inventory-gate"

RULES = {"plugin": {"plugin_id": "formal-lab.example.orders.rules", "version": "1.0.0"}, "config": {}}
Z3 = {"plugin": {"plugin_id": "formal-lab.planner.z3-bounded", "version": "1.1.0"},
      "config": {"horizon": 12, "fallback_order": ["start", "enqueue", "reserve", "restock", "tick"]}}
STRATEGIES = {"rule": RULES, "z3": Z3}
EVALUATORS = [PluginRef(plugin_id="formal-lab.eval.generic", version="1.0.0"),
              PluginRef(plugin_id="formal-lab.example.orders.scorer", version="1.0.0")]
BUDGET = {"max_steps": 60, "max_wall_seconds": 900}
TERMINATION = {"joint_goal": "all_completed", "on_no_action": "FAIL", "no_progress_limit": 20}
CASE_TIMEOUTS = {"delayed": 1.0}  # client timeout (s) below the service's hold, so the answer is lost


def scenario(case: str, *, backend: str = "service", seed: int = 0, strategy: str | dict = "rule",
             endpoint: str = "http://127.0.0.1:8765", tenant: str | None = None, two_actors: bool = False,
             conflict_policy: str = "REVALIDATE", timing: str = "TURN_START",
             env_extra: dict[str, Any] | None = None, safety_stock: int | None = None) -> ScenarioManifest:
    """`safety_stock` (phase 3A): consult the inventory execution gate before every send, keeping that many units of
    each SKU after a reservation; None = no gate (phase-2 behaviour)."""
    if case not in CASES:
        raise KeyError(f"unknown case {case!r}")
    spec = CASES[case]
    pkg = model_package()
    if backend == "service":
        env_cfg: dict[str, Any] = {"endpoint": endpoint, "case": case,
                                   "timeout_s": CASE_TIMEOUTS.get(case, 5.0), **(env_extra or {})}
        if tenant:
            env_cfg["tenant"] = tenant
        environment = {"plugin": {"plugin_id": ENV_ID, "version": ENV_VERSION}, "config": env_cfg}
    elif backend == "pure":
        inst = instance(case, seed)
        env_cfg = {"initial_overrides": initial_overrides(inst)}
        slow = inst.service.get("slow_stations", [])
        if slow:
            env_cfg["truth_constant_overrides"] = {f"slow[{st}]": True for st in slow}
        environment = {"plugin": {"plugin_id": "formal-lab.env.ir-world", "version": "1.1.0"}, "config": env_cfg}
    else:
        raise KeyError(f"unknown backend {backend!r}")
    strat = STRATEGIES[strategy] if isinstance(strategy, str) else strategy
    participants = [{"actor_id": "handler", "role": "order_handler", "strategy": strat}]
    turns: dict[str, Any] = {}
    if two_actors:
        participants = [{"actor_id": "handler_a", "role": "order_handler", "label": "处理员 A", "strategy": strat},
                        {"actor_id": "handler_b", "role": "order_handler", "label": "处理员 B", "strategy": strat}]
        turns = {"mode": "ROUND_ROBIN", "observation_timing": timing, "conflict_policy": conflict_policy}
    return ScenarioManifest(
        scenario_id=f"orders-{case}-{backend}" + ("-two" if two_actors else ""),
        name=f"订单：{spec['label']}（{'业务服务' if backend == 'service' else '纯数据模型'}）",
        description=spec["description"], model=pkg.ref(), environment=environment, participants=participants,
        objectives=[{"property_id": "all_completed", "description": "complete every order"}],
        budget=BUDGET, seed=seed, termination=TERMINATION, **({"turns": turns} if turns else {}),
        execution_gates=[] if safety_stock is None else [
            {"plugin": {"plugin_id": INVENTORY_GATE_ID, "version": "1.0.0"},
             "config": {"min_stock_after": safety_stock}}])


def run(case: str, *, backend: str = "service", seed: int = 0, strategy: str | dict = "rule", run_id: str | None = None,
        registry: Any = None, initial_check_horizon: int = 0, stop_after: int | None = None,
        config: dict[str, Any] | None = None, **kw: Any) -> Any:
    """One local run of a case (local runner). The start-of-run reachability check is off by default: the order
    book needs ~24 steps, so a bounded check at the default horizon only reports 'not within the bound' slowly."""
    from formal_lab_runtime import default_registry, make_manifest, run_local

    reg = registry or default_registry()
    pkg = model_package()
    sc = scenario(case, backend=backend, seed=seed, strategy=strategy, **kw)
    m = make_manifest(run_id=run_id or f"run_{case}_{backend}_{seed}", project_id="orders", scenario=sc, package=pkg,
                      registry=reg, seed=seed, evaluators=EVALUATORS,
                      config={"initial_check_horizon": initial_check_horizon, **(config or {})})
    return run_local(m, pkg, reg, stop_after=stop_after)
