"""The order-handling model in the neutral deterministic_finite_v1 IR (the pure-data backend and the planners' model).

Entities: orders, SKUs, processing stations.
Actions (the action contract shared with the business service):
  reserve(o)       — a submitted order reserves its quantity of its SKU from stock;
  enqueue(o)       — a reserved order joins the processing queue (FIFO sequence number);
  start(o, st)     — the head of the queue starts on a free station (processing time = the order's);
  tick()           — logical time +1: processing advances (a slow station only on every other tick), orders whose
                     processing ends complete, orders due to arrive are submitted (background order flow);
  restock(sku)     — one delivery of RESTOCK_QTY units per SKU.
Conditions: stock never negative, one order per station, FIFO start, time bounded by the horizon.
Hidden-reality hook: constant `slow[st]` — the service may run a station at half speed.
"""

from __future__ import annotations

from typing import Any

from formal_lab_contracts import ModelIR, ModelPackage, ModelSource
from formal_lab_model import build_package
from formal_lab_model.samples import ap, assign, c, r, v

from .instance import BASE_ORDERS, BASE_STOCK, HORIZON, MAX_STOCK, ORDERS, RESTOCK_QTY, SKUS, STATIONS

PACKAGE_ID = "local-order-service"
STATUS = ["pending", "submitted", "reserved", "queued", "processing", "completed"]


def _table(cells: dict[tuple[str, ...], Any], default: Any = None) -> dict[str, Any]:
    out: dict[str, Any] = {"cells": [{"index": list(k), "value": val} for k, val in cells.items()]}
    if default is not None:
        out["default"] = default
    return out


def _q(op: str, var: str, domain: str, body: dict[str, Any], where: dict[str, Any] | None = None) -> dict[str, Any]:
    q: dict[str, Any] = {"op": op, "var": var, "domain": domain, "body": body}
    if where is not None:
        q["where"] = where
    return q


def status_is(o: dict[str, Any], value: str) -> dict[str, Any]:
    return ap("eq", v("status", o), c(value))


def build_model() -> ModelIR:
    progresses = ap("and", status_is(r("o"), "processing"),
                    _q("exists", "st", "stations", ap("and", v("on", r("o"), r("st")),
                                                      ap("or", ap("not", v("slow", r("st"))), v("tick_parity")))))
    ir = {
        "name": "local-order-service",
        "description": "Order handling: reserve stock, queue, process on stations, complete; orders keep arriving.",
        "enums": [{"name": "order_status", "values": STATUS}],
        "entity_sets": [
            {"name": "orders", "members": ORDERS, "label": "订单"},
            {"name": "skus", "members": SKUS, "label": "库存品"},
            {"name": "stations", "members": STATIONS, "label": "处理工位"},
        ],
        "constants": [
            {"name": "sku_of", "type": {"kind": "entity", "set": "skus"}, "index": ["orders"],
             "value": _table({(o,): spec[0] for o, spec in BASE_ORDERS.items()})},
            {"name": "qty", "type": {"kind": "int", "min": 1, "max": 4}, "index": ["orders"],
             "value": _table({(o,): spec[1] for o, spec in BASE_ORDERS.items()})},
            {"name": "arrive_at", "type": {"kind": "int", "min": 0, "max": HORIZON}, "index": ["orders"],
             "value": _table({(o,): spec[2] for o, spec in BASE_ORDERS.items()})},
            {"name": "due", "type": {"kind": "int", "min": 0, "max": HORIZON}, "index": ["orders"],
             "value": _table({(o,): spec[3] for o, spec in BASE_ORDERS.items()})},
            {"name": "slow", "type": {"kind": "bool"}, "index": ["stations"], "value": {"default": False},
             "description": "a slow station advances processing only on every other tick (hidden-reality hook)"},
        ],
        "state": [
            {"name": "status", "type": {"kind": "enum", "name": "order_status"}, "index": ["orders"],
             "initial": _table({(o,): ("submitted" if spec[2] == 0 else "pending")
                                for o, spec in BASE_ORDERS.items()}), "label": "订单状态"},
            {"name": "stock", "type": {"kind": "int", "min": 0, "max": MAX_STOCK}, "index": ["skus"],
             "initial": _table({(s,): q for s, q in BASE_STOCK.items()}), "label": "可用库存"},
            {"name": "restocked", "type": {"kind": "bool"}, "index": ["skus"], "initial": {"default": False},
             "label": "已补货"},
            {"name": "on", "type": {"kind": "bool"}, "index": ["orders", "stations"], "initial": {"default": False},
             "label": "订单所在工位"},
            {"name": "remaining", "type": {"kind": "int", "min": 0, "max": 9}, "index": ["orders"],
             "initial": {"default": 0}, "label": "剩余处理时间"},
            {"name": "proc_time", "type": {"kind": "int", "min": 1, "max": 9}, "index": ["orders"],
             "initial": _table({(o,): spec[4] for o, spec in BASE_ORDERS.items()}), "label": "处理时间",
             "description": "instance data (set per case and seed); never changed by actions"},
            {"name": "queued_seq", "type": {"kind": "int", "min": 0, "max": 9}, "index": ["orders"],
             "initial": {"default": 0}, "label": "排队序号", "description": "0 = not queued"},
            {"name": "next_seq", "type": {"kind": "int", "min": 1, "max": 9}, "initial": {"default": 1}},
            {"name": "done_at", "type": {"kind": "int", "min": 0, "max": HORIZON}, "index": ["orders"],
             "initial": {"default": 0}, "label": "完成时刻"},
            {"name": "clock", "type": {"kind": "int", "min": 0, "max": HORIZON}, "initial": {"default": 0},
             "label": "逻辑时间"},
            {"name": "tick_parity", "type": {"kind": "bool"}, "initial": {"default": False}},
        ],
        "actions": [
            {"name": "reserve", "label": "预约库存", "params": [{"name": "o", "type": {"kind": "entity", "set": "orders"}}],
             "precondition": ap("and", status_is(r("o"), "submitted"),
                                ap("ge", v("stock", v("sku_of", r("o"))), v("qty", r("o")))),
             "effects": [
                 assign("status", c("reserved"), r("o")),
                 {"kind": "forall", "var": "s", "domain": "skus", "where": ap("eq", v("sku_of", r("o")), r("s")),
                  "effects": [assign("stock", ap("sub", v("stock", r("s")), v("qty", r("o"))), r("s"))]},
             ], "retry": "RECONCILE_THEN_RETRY"},
            {"name": "enqueue", "label": "加入处理队列",
             "params": [{"name": "o", "type": {"kind": "entity", "set": "orders"}}],
             "precondition": ap("and", status_is(r("o"), "reserved"), ap("lt", v("next_seq"), c(9))),
             "effects": [assign("status", c("queued"), r("o")), assign("queued_seq", v("next_seq"), r("o")),
                         assign("next_seq", ap("add", v("next_seq"), c(1)))],
             "retry": "RECONCILE_THEN_RETRY"},
            {"name": "start", "label": "开始处理",
             "params": [{"name": "o", "type": {"kind": "entity", "set": "orders"}},
                        {"name": "st", "type": {"kind": "entity", "set": "stations"}}],
             "precondition": ap(
                 "and", status_is(r("o"), "queued"),
                 ap("not", _q("exists", "x", "orders", v("on", r("x"), r("st")))),
                 _q("forall", "x", "orders", ap("ge", v("queued_seq", r("x")), v("queued_seq", r("o"))),
                    where=status_is(r("x"), "queued"))),
             "effects": [assign("status", c("processing"), r("o")), assign("on", c(True), r("o"), r("st")),
                         assign("remaining", v("proc_time", r("o")), r("o")), assign("queued_seq", c(0), r("o"))],
             "retry": "RECONCILE_THEN_RETRY"},
            {"name": "tick", "label": "推进时间", "precondition": ap("lt", v("clock"), c(HORIZON)),
             "effects": [
                 assign("clock", ap("add", v("clock"), c(1))),
                 assign("tick_parity", ap("not", v("tick_parity"))),
                 {"kind": "forall", "var": "o", "domain": "orders", "where": progresses, "effects": [
                     assign("remaining", ap("sub", v("remaining", r("o")), c(1)), r("o")),
                     {"kind": "when", "condition": ap("le", v("remaining", r("o")), c(1)), "then": [
                         assign("status", c("completed"), r("o")),
                         assign("done_at", ap("add", v("clock"), c(1)), r("o")),
                         {"kind": "forall", "var": "st", "domain": "stations",
                          "effects": [assign("on", c(False), r("o"), r("st"))]},
                     ]},
                 ]},
                 {"kind": "forall", "var": "o", "domain": "orders",
                  "where": ap("and", status_is(r("o"), "pending"),
                              ap("eq", v("arrive_at", r("o")), ap("add", v("clock"), c(1)))),
                  "effects": [assign("status", c("submitted"), r("o"))]},
             ], "retry": "RECONCILE_THEN_RETRY"},
            {"name": "restock", "label": "补货", "params": [{"name": "s", "type": {"kind": "entity", "set": "skus"}}],
             "precondition": ap("and", ap("not", v("restocked", r("s"))),
                                ap("le", ap("add", v("stock", r("s")), c(RESTOCK_QTY)), c(MAX_STOCK))),
             "effects": [assign("stock", ap("add", v("stock", r("s")), c(RESTOCK_QTY)), r("s")),
                         assign("restocked", c(True), r("s"))], "retry": "RECONCILE_THEN_RETRY"},
        ],
        "properties": [
            {"id": "all_completed", "kind": "goal", "label": "全部订单完成",
             "expr": _q("forall", "o", "orders", status_is(r("o"), "completed"))},
            {"id": "station_capacity", "kind": "invariant", "label": "工位容量",
             "expr": _q("forall", "st", "stations",
                        ap("le", {"op": "count", "var": "o", "domain": "orders", "body": v("on", r("o"), r("st"))},
                           c(1)))},
            {"id": "on_time", "kind": "invariant", "label": "无延期",
             "expr": _q("forall", "o", "orders", ap("implies", ap("gt", v("clock"), v("due", r("o"))),
                                                      status_is(r("o"), "completed")))},
        ],
    }
    return ModelIR.model_validate(ir)


def model_package(version: int = 1) -> ModelPackage:
    ir = build_model()
    return build_package(ir, package_id=PACKAGE_ID, version=version,
                         source=ModelSource(format="fal-ir-json/v1", text=ir.model_dump_json(indent=2),
                                            origin="examples/local-order-service"))
