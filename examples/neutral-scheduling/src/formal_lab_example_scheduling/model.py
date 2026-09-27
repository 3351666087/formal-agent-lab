"""Production-scheduling model in the neutral deterministic_finite_v1 IR.

Entities: orders, operations (ops), machines, stations, finite resources.
Actions: assign(op, machine), advance() (logical time +1), pause(machine), resume(machine),
         reprioritize(order, level) (re-orders the dispatch queue).
Conditions: machine capacity (1 op), station capacity, finite resources, operation precedence,
            machine eligibility, paused machines do not progress.
Hidden-reality hook: constant `degraded[m]` — a degraded machine progresses only on every other tick.
"""

from __future__ import annotations

from typing import Any

from formal_lab_contracts import ModelIR
from formal_lab_model.samples import ap, assign, c, r, v

HORIZON = 24

ORDERS = ["o1", "o2", "o3"]
OPS = {  # op: (order, nominal processing time, eligible machines, predecessor ops, resources)
    "o1_cut": ("o1", 2, ["m1", "m2"], [], ["fixture"]),
    "o1_weld": ("o1", 3, ["m3", "m2"], ["o1_cut"], ["operator"]),
    "o2_cut": ("o2", 3, ["m1", "m2"], [], ["fixture"]),
    "o2_paint": ("o2", 2, ["m2", "m3"], ["o2_cut"], []),
    "o3_cut": ("o3", 1, ["m1"], [], ["fixture"]),
    "o3_weld": ("o3", 2, ["m3", "m2"], ["o3_cut"], ["operator"]),
    "o3_paint": ("o3", 2, ["m2", "m3"], ["o3_weld"], []),
}
MACHINES = {"m1": "s1", "m2": "s1", "m3": "s2"}
STATIONS = {"s1": 2, "s2": 1}
RESOURCES = {"fixture": 2, "operator": 2}
DUE = {"o1": 6, "o2": 7, "o3": 8}
LATE_COST = {"o1": 3, "o2": 2, "o3": 1}  # simulated delay cost per late tick


def _count(var: str, domain: str, body: dict[str, Any], where: dict[str, Any] | None = None) -> dict[str, Any]:
    q: dict[str, Any] = {"op": "count", "var": var, "domain": domain, "body": body}
    if where is not None:
        q["where"] = where
    return q


def _forall(var: str, domain: str, body: dict[str, Any], where: dict[str, Any] | None = None) -> dict[str, Any]:
    q: dict[str, Any] = {"op": "forall", "var": var, "domain": domain, "body": body}
    if where is not None:
        q["where"] = where
    return q


def _exists(var: str, domain: str, body: dict[str, Any]) -> dict[str, Any]:
    return {"op": "exists", "var": var, "domain": domain, "body": body}


def _table(cells: dict[tuple[str, ...], Any], default: Any = None) -> dict[str, Any]:
    out: dict[str, Any] = {"cells": [{"index": list(k), "value": val} for k, val in cells.items()]}
    if default is not None:
        out["default"] = default
    return out


def build_model(
    *,
    ops: dict[str, tuple] | None = None,
    resources: dict[str, int] | None = None,
    stations: dict[str, int] | None = None,
    due: dict[str, int] | None = None,
    horizon: int = HORIZON,
    name: str = "neutral-scheduling",
    with_objectives: bool = False,
) -> ModelIR:
    """The scheduling model. `with_objectives` adds the declared cost objectives (model version 2 of the example);
    without them the model is byte-identical to phase 1 (same digest)."""
    ops = ops or OPS
    resources = resources or RESOURCES
    stations = stations or STATIONS
    due = due or DUE
    running = lambda o: ap("eq", v("phase", o), c("running"))  # noqa: E731

    assign_pre = ap(
        "and",
        ap("eq", v("phase", r("op")), c("waiting")),
        _forall("p", "ops", ap("eq", v("phase", r("p")), c("done")), where=v("pred", r("op"), r("p"))),
        v("eligible", r("op"), r("m")),
        ap("not", v("paused", r("m"))),
        ap("eq", _count("o", "ops", v("on", r("o"), r("m"))), c(0)),
        ap(
            "lt",
            _count("o", "ops", _exists("mm", "machines", ap("and", v("on", r("o"), r("mm")),
                                                           ap("eq", v("station_of", r("mm")), v("station_of", r("m")))))),
            v("station_cap", v("station_of", r("m"))),
        ),
        _forall("res", "resources",
                ap("lt", _count("o", "ops", ap("and", running(r("o")), v("needs", r("o"), r("res")))),
                   v("res_cap", r("res"))),
                where=v("needs", r("op"), r("res"))),
    )
    progresses = ap(
        "and",
        running(r("o")),
        _exists("m", "machines", ap("and", v("on", r("o"), r("m")), ap("not", v("paused", r("m"))),
                                    ap("or", ap("not", v("degraded", r("m"))), v("tick_parity")))),
    )
    ir = {
        "name": name,
        "description": "Neutral production scheduling: assign operations to machines under station, "
        "resource and precedence constraints; finish all orders and keep simulated delay cost low.",
        "enums": [
            {"name": "op_phase", "values": ["waiting", "running", "done"]},
            {"name": "level", "values": ["high", "normal", "low"]},
        ],
        "entity_sets": [
            {"name": "orders", "members": sorted({o for o, *_ in ops.values()}), "label": "订单"},
            {"name": "ops", "members": list(ops), "label": "工序"},
            {"name": "machines", "members": list(MACHINES), "label": "机器"},
            {"name": "stations", "members": list(stations), "label": "工位"},
            {"name": "resources", "members": list(resources), "label": "有限资源"},
        ],
        "constants": [
            {"name": "order_of", "type": {"kind": "entity", "set": "orders"}, "index": ["ops"],
             "value": _table({(op,): spec[0] for op, spec in ops.items()})},
            {"name": "pred", "type": {"kind": "bool"}, "index": ["ops", "ops"],
             "value": _table({(op, p): True for op, spec in ops.items() for p in spec[3]}, default=False),
             "description": "pred[a, b]: operation a requires b to be done"},
            {"name": "eligible", "type": {"kind": "bool"}, "index": ["ops", "machines"],
             "value": _table({(op, m): True for op, spec in ops.items() for m in spec[2]}, default=False)},
            {"name": "needs", "type": {"kind": "bool"}, "index": ["ops", "resources"],
             "value": _table({(op, res): True for op, spec in ops.items() for res in spec[4]}, default=False)},
            {"name": "station_of", "type": {"kind": "entity", "set": "stations"}, "index": ["machines"],
             "value": _table({(m,): s for m, s in MACHINES.items()})},
            {"name": "station_cap", "type": {"kind": "int", "min": 0, "max": 3}, "index": ["stations"],
             "value": _table({(s,): cap for s, cap in stations.items()})},
            {"name": "due", "type": {"kind": "int", "min": 0, "max": horizon}, "index": ["orders"],
             "value": _table({(o,): d for o, d in due.items()})},
            {"name": "late_cost", "type": {"kind": "int", "min": 0, "max": 9}, "index": ["orders"],
             "value": _table({(o,): LATE_COST.get(o, 1) for o in due})},
            {"name": "degraded", "type": {"kind": "bool"}, "index": ["machines"], "value": {"default": False},
             "description": "a degraded machine progresses only on every other tick (hidden-reality hook)"},
        ],
        "state": [
            {"name": "phase", "type": {"kind": "enum", "name": "op_phase"}, "index": ["ops"],
             "initial": {"default": "waiting"}, "label": "工序状态"},
            {"name": "on", "type": {"kind": "bool"}, "index": ["ops", "machines"], "initial": {"default": False},
             "label": "工序所在机器"},
            {"name": "remaining", "type": {"kind": "int", "min": 0, "max": 9}, "index": ["ops"],
             "initial": {"default": 0}, "label": "剩余加工时间"},
            {"name": "proc_time", "type": {"kind": "int", "min": 1, "max": 9}, "index": ["ops"],
             "initial": _table({(op,): spec[1] for op, spec in ops.items()}), "label": "加工时间",
             "description": "instance data (varied per seed by the environment); never changed by actions"},
            {"name": "res_cap", "type": {"kind": "int", "min": 0, "max": 3}, "index": ["resources"],
             "initial": _table({(res,): cap for res, cap in resources.items()}), "label": "资源容量",
             "description": "instance data (set per scenario by the environment); never changed by actions"},
            {"name": "finish", "type": {"kind": "int", "min": 0, "max": horizon}, "index": ["ops"],
             "initial": {"default": 0}, "label": "完工时刻"},
            {"name": "paused", "type": {"kind": "bool"}, "index": ["machines"], "initial": {"default": False},
             "label": "机器暂停"},
            {"name": "priority", "type": {"kind": "enum", "name": "level"}, "index": ["orders"],
             "initial": {"default": "normal"}, "label": "队列优先级"},
            {"name": "clock", "type": {"kind": "int", "min": 0, "max": horizon}, "initial": {"default": 0},
             "label": "逻辑时间"},
            {"name": "tick_parity", "type": {"kind": "bool"}, "initial": {"default": False}},
        ],
        "actions": [
            {
                "name": "assign",
                "label": "分配工序",
                "params": [{"name": "op", "type": {"kind": "entity", "set": "ops"}},
                           {"name": "m", "type": {"kind": "entity", "set": "machines"}}],
                "precondition": assign_pre,
                "effects": [
                    assign("phase", c("running"), r("op")),
                    assign("on", c(True), r("op"), r("m")),
                    assign("remaining", v("proc_time", r("op")), r("op")),
                ],
                "retry": "RECONCILE_THEN_RETRY",
            },
            {
                "name": "advance",
                "label": "推进逻辑时间",
                "precondition": _exists("o", "ops", running(r("o"))),
                "effects": [
                    assign("clock", ap("add", v("clock"), c(1))),
                    assign("tick_parity", ap("not", v("tick_parity"))),
                    {"kind": "forall", "var": "o", "domain": "ops", "where": progresses, "effects": [
                        assign("remaining", ap("sub", v("remaining", r("o")), c(1)), r("o")),
                        {"kind": "when", "condition": ap("le", v("remaining", r("o")), c(1)), "then": [
                            assign("phase", c("done"), r("o")),
                            assign("finish", ap("add", v("clock"), c(1)), r("o")),
                            {"kind": "forall", "var": "m", "domain": "machines",
                             "effects": [assign("on", c(False), r("o"), r("m"))]},
                        ]},
                    ]},
                ],
                "retry": "RECONCILE_THEN_RETRY",
            },
            {"name": "pause", "label": "暂停机器", "params": [{"name": "m", "type": {"kind": "entity", "set": "machines"}}],
             "precondition": ap("not", v("paused", r("m"))), "effects": [assign("paused", c(True), r("m"))],
             "retry": "IDEMPOTENT"},
            {"name": "resume", "label": "恢复机器", "params": [{"name": "m", "type": {"kind": "entity", "set": "machines"}}],
             "precondition": v("paused", r("m")), "effects": [assign("paused", c(False), r("m"))],
             "retry": "IDEMPOTENT"},
            {"name": "reprioritize", "label": "重排队列",
             "params": [{"name": "ord", "type": {"kind": "entity", "set": "orders"}},
                        {"name": "lvl", "type": {"kind": "enum", "name": "level"}}],
             "precondition": ap("ne", v("priority", r("ord")), r("lvl")),
             "effects": [assign("priority", r("lvl"), r("ord"))], "retry": "IDEMPOTENT"},
        ],
        "properties": [
            {"id": "all_done", "kind": "goal", "label": "全部订单完工",
             "expr": _forall("o", "ops", ap("eq", v("phase", r("o")), c("done")))},
            {"id": "machine_capacity", "kind": "invariant", "label": "机器容量",
             "expr": _forall("m", "machines", ap("le", _count("o", "ops", v("on", r("o"), r("m"))), c(1)))},
            {"id": "resource_capacity", "kind": "invariant", "label": "资源容量",
             "expr": _forall("res", "resources", ap("le", _count("o", "ops", ap("and", running(r("o")),
                                                                                  v("needs", r("o"), r("res")))),
                                                    v("res_cap", r("res"))))},
            {"id": "precedence", "kind": "invariant", "label": "工序依赖",
             "expr": _forall("o", "ops", _forall("p", "ops", ap("implies", ap("ne", v("phase", r("o")), c("waiting")),
                                                                ap("eq", v("phase", r("p")), c("done"))),
                                                 where=v("pred", r("o"), r("p"))))},
            {"id": "on_time", "kind": "invariant", "label": "无延期",
             "expr": _forall("o", "ops", ap("implies", ap("gt", v("clock"), v("due", v("order_of", r("o")))),
                                            ap("eq", v("phase", r("o")), c("done"))))},
        ],
    }
    if with_objectives:
        completion = {"op": "max_over", "var": "p", "domain": "ops",
                      "where": ap("eq", v("order_of", r("p")), r("o")), "body": v("finish", r("p")), "default": c(0)}
        ir["objectives"] = [
            {"id": "delay_cost", "label": "模拟延期成本", "unit": "cost",
             "description": "Σ_orders late_cost × max(0, completion − due); completion = latest finish of the "
                            "order's operations (the scorer's delay_cost on the goal state)",
             "terms": [{"kind": "terminal", "expr": {
                 "op": "sum", "var": "o", "domain": "orders",
                 "body": ap("mul", v("late_cost", r("o")),
                            ap("max", c(0), ap("sub", completion, v("due", r("o")))))}}]},
            {"id": "effort", "label": "调度动作数", "unit": "actions",
             "description": "one unit per dispatching action (assign / advance / pause / resume / reprioritize)",
             "terms": [{"kind": "action_cost"}]},
        ]
    return ModelIR.model_validate(ir)
