"""Synthetic order data shared by both backends (the pure-data model and the business service).

An *instance* is what a case and a seed fix before the first action: the orders (SKU, quantity, arrival, due time,
processing time), the stock, the stations and — for the service — the case's operating conditions (a slow station,
delayed responses, a crash point). Both backends start from the same instance; they implement the order-handling
rules independently (the model as IR, the service in SQL), which is what the backend comparison checks.

All data are synthetic.
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field
from typing import Any

ORDERS = ["o1", "o2", "o3", "o4", "o5", "o6"]
SKUS = ["a", "b"]
STATIONS = ["p1", "p2"]
HORIZON = 24
RESTOCK_QTY = 4
MAX_STOCK = 12

# order: (sku, qty, arrive_at, due, nominal processing time) — o4…o6 arrive while the run is under way
BASE_ORDERS = {
    "o1": ("a", 2, 0, 6, 2),
    "o2": ("b", 1, 0, 7, 3),
    "o3": ("a", 3, 0, 9, 2),
    "o4": ("b", 2, 2, 11, 2),
    "o5": ("a", 1, 3, 12, 3),
    "o6": ("b", 3, 4, 14, 2),
}
BASE_STOCK = {"a": 6, "b": 6}

CASES: dict[str, dict[str, Any]] = {
    "normal": {"label": "正常处理", "stock": BASE_STOCK,
               "description": "enough stock, both stations at nominal speed, prompt responses"},
    "shortage": {"label": "资源短缺", "stock": {"a": 2, "b": 3},
                 "description": "too little stock for the order book: SKUs must be restocked (once each)"},
    "delayed": {"label": "延迟响应", "stock": BASE_STOCK,
                "service": {"hold_after_commit_ms": 1500, "hold_every": 4},
                "description": "every 4th operation's response is held past the client timeout after it was "
                               "committed: the outcome is unknown until the operation is looked up"},
    "restart": {"label": "进程重启", "stock": BASE_STOCK, "service": {"crash_after_op": 5},
                "description": "the service process exits right after committing its 5th operation and is "
                               "restarted by its supervisor; the run continues against the restarted service"},
    "deviation": {"label": "预测效果偏差", "stock": BASE_STOCK, "service": {"slow_stations": ["p2"]},
                  "description": "station p2 works at half speed in the service while the model predicts nominal "
                                 "speed: effects of `tick` differ from the prediction"},
}


@dataclass
class OrderSpec:
    order_id: str
    sku: str
    qty: int
    arrive_at: int
    due: int
    proc_time: int


@dataclass
class Instance:
    case: str
    seed: int
    orders: list[OrderSpec]
    stock: dict[str, int]
    stations: list[str] = field(default_factory=lambda: list(STATIONS))
    service: dict[str, Any] = field(default_factory=dict)  # operating conditions of the business service

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Instance:
        return cls(case=data["case"], seed=data["seed"], orders=[OrderSpec(**o) for o in data["orders"]],
                   stock=dict(data["stock"]), stations=list(data["stations"]), service=dict(data.get("service", {})))


def instance(case: str, seed: int) -> Instance:
    """The case's instance for a seed: processing times vary by −1…+1 (clamped to 1…5) per order."""
    if case not in CASES:
        raise KeyError(f"unknown case {case!r}; known: {sorted(CASES)}")
    spec = CASES[case]
    rng = random.Random(seed)
    orders = []
    for oid in ORDERS:
        sku, qty, arrive, due, proc = BASE_ORDERS[oid]
        orders.append(OrderSpec(oid, sku, qty, arrive, due, max(1, min(5, proc + rng.randint(-1, 1)))))
    return Instance(case=case, seed=seed, orders=orders, stock=dict(spec["stock"]),
                    service=dict(spec.get("service", {})))


def initial_overrides(inst: Instance) -> dict[str, Any]:
    """The instance as initial-state overrides of the pure-data model (ir-world `initial_overrides`)."""
    out: dict[str, Any] = {f"stock[{s}]": q for s, q in inst.stock.items()}
    out.update({f"proc_time[{o.order_id}]": o.proc_time for o in inst.orders})
    return out
