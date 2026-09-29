"""Execution gate of the order example (phase 3A, G2): a safety-stock policy checked right before each send.

`reserve(o)` may go ahead only if, after taking the order's quantity, at least `min_stock_after` units of its SKU stay
in stock. The model (and the service) only require stock ≥ qty, so this is a business policy on top of the model,
decided at the execution boundary on values read fresh from the service (env.observe_on_request) — a reservation the
service would have accepted is simply not sent. Other actions carry no inventory condition and are allowed.
"""

from __future__ import annotations

from typing import Any

from formal_lab_contracts import (
    ConditionCheck,
    GateRequest,
    GateResult,
    GroundAction,
    ModelPackage,
    PluginDescriptor,
)
from formal_lab_contracts import capabilities as caps

INVENTORY_GATE = PluginDescriptor(
    plugin_id="formal-lab.example.orders.inventory-gate", version="1.0.0", interface="EXECUTION_GATE",
    interface_version="2", semantic_profiles=["deterministic_finite_v1"],
    capabilities=[{"id": caps.GATE_PRE_EXECUTION}, {"id": caps.GATE_FRESH_VALUES}],
    config_schema={"type": "object", "additionalProperties": False, "properties": {
        "min_stock_after": {"type": "integer", "minimum": 0, "default": 0,
                            "description": "units of the SKU that must remain after a reservation (safety stock)"}}},
    entrypoint="formal_lab_example_orders.gates:create_inventory_gate",
    ui={"label": "库存安全线（执行前决策）", "category": "gate",
        "description": "reserve(o) is sent only if stock[sku] − qty ≥ min_stock_after, read fresh from the service",
        "condition_labels": {"safety_stock": "库存安全线"}},
    license="Apache-2.0", source="formal-lab-example-orders")


def _table(package: ModelPackage, name: str) -> dict[str, Any]:
    """An IR constant indexed by one entity set, as {member: value}."""
    const = next(c for c in package.ir.constants if c.name == name)
    value = const.model_dump(mode="json")["value"]
    return {cell["index"][0]: cell["value"] for cell in value.get("cells", [])}


class InventoryGate:
    descriptor = INVENTORY_GATE

    def __init__(self, package: ModelPackage, min_stock_after: int):
        self.sku_of = _table(package, "sku_of")
        self.qty = _table(package, "qty")
        self.min_after = min_stock_after

    def paths(self, action: GroundAction) -> list[str]:
        if action.action_type != "reserve":
            return []
        return [f"stock[{self.sku_of[action.params['o']]}]"]

    def decide(self, request: GateRequest) -> GateResult:
        action = request.action
        if action.action_type != "reserve":
            return GateResult(verdict="ALLOW", reason=f"no inventory condition for {action.action_type}")
        order = str(action.params["o"])
        path = f"stock[{self.sku_of[order]}]"
        qty = int(self.qty[order])
        need = qty + self.min_after
        if path not in request.values:
            return GateResult(verdict="DENY", reason=f"{path} could not be read before sending",
                              conditions=[ConditionCheck(name="safety_stock", holds=None, required=f">= {need}",
                                                         paths=[path], detail="value unavailable")])
        stock = int(request.values[path])
        holds = stock >= need
        check = ConditionCheck(name="safety_stock", holds=holds, observed=stock, required=f">= {need}", paths=[path],
                               detail=f"reserve {qty} of {self.sku_of[order]} keeping {self.min_after} in stock "
                                      f"({request.values_source.lower()} value at revision {request.values_revision})")
        if holds:
            return GateResult(verdict="ALLOW", reason=f"{path} = {stock} ≥ {need}", conditions=[check])
        return GateResult(verdict="DENY", reason=f"{path} = {stock} < {need}: reserving {qty} would leave less than "
                                                 f"the safety stock of {self.min_after}", conditions=[check])


def create_inventory_gate(config: dict[str, Any] | None, services: Any) -> InventoryGate:
    return InventoryGate(services.pinned_model(), int((config or {}).get("min_stock_after", 0)))
