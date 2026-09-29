"""Execution gate of the warehouse example (phase 3A, G2): a zone fill-level policy checked right before each send.

`putaway(inbound, zone)` may go ahead only if the zone stays at or below `max_fill` of its capacity afterwards. The
model only requires the pallet to fit (≤ 100 %), so this keeps headroom as a resource policy decided at the execution
boundary. The driver-world environment does not answer observation requests, so the values come from the actor's
current observation (recorded as such on every decision).
"""

from __future__ import annotations

import math
from typing import Any

from formal_lab_contracts import ConditionCheck, GateRequest, GateResult, GroundAction, PluginDescriptor
from formal_lab_contracts import capabilities as caps

from .driver import parse_payload
from .model import PROFILE

CAPACITY_GATE = PluginDescriptor(
    plugin_id="formal-lab.example.warehouse.capacity-gate", version="1.0.0", interface="EXECUTION_GATE",
    interface_version="2", semantic_profiles=[PROFILE],
    capabilities=[{"id": caps.GATE_PRE_EXECUTION}],
    config_schema={"type": "object", "additionalProperties": False, "properties": {
        "max_fill": {"type": "number", "exclusiveMinimum": 0, "maximum": 1, "default": 1.0,
                     "description": "largest share of a zone's capacity a put-away may fill it to"}}},
    entrypoint="formal_lab_example_warehouse.gates:create_capacity_gate",
    ui={"label": "库区容量上限（执行前决策）", "category": "gate",
        "description": "putaway is sent only if the zone stays ≤ max_fill of its capacity",
        "condition_labels": {"zone_fill": "库区装载率"}},
    license="Apache-2.0", source="formal-lab-example-warehouse")


class CapacityGate:
    descriptor = CAPACITY_GATE

    def __init__(self, package: Any, max_fill: float):
        model = parse_payload(package)
        self.capacity = {z.id: z.capacity for z in model.zones}
        self.skus = list(model.skus)
        self.max_fill = max_fill

    def paths(self, action: GroundAction) -> list[str]:
        if action.action_type != "putaway":
            return []
        zone = action.params["zone"]
        return [f"dock[{action.params['inbound']}]", *(f"stock[{zone},{k}]" for k in self.skus)]

    def decide(self, request: GateRequest) -> GateResult:
        action = request.action
        if action.action_type != "putaway":
            return GateResult(verdict="ALLOW", reason=f"no capacity condition for {action.action_type}")
        zone, inbound = str(action.params["zone"]), str(action.params["inbound"])
        wanted = self.paths(action)
        missing = [p for p in wanted if p not in request.values]
        limit = math.floor(self.capacity[zone] * self.max_fill)
        if missing:
            return GateResult(verdict="DENY", reason=f"{len(missing)} location(s) unknown before sending",
                              conditions=[ConditionCheck(name="zone_fill", holds=None, required=f"<= {limit}",
                                                         paths=missing, detail="values unavailable")])
        used = sum(int(request.values[f"stock[{zone},{k}]"]) for k in self.skus)
        after = used + int(request.values[f"dock[{inbound}]"])
        holds = after <= limit
        check = ConditionCheck(name="zone_fill", holds=holds, observed=after, required=f"<= {limit}", paths=wanted,
                               detail=f"{zone}: {used}/{self.capacity[zone]} now, {after} after the put-away "
                                      f"(max_fill {self.max_fill:g}, {request.values_source.lower()} values)")
        if holds:
            return GateResult(verdict="ALLOW", reason=f"{zone} would hold {after} ≤ {limit}", conditions=[check])
        return GateResult(verdict="DENY", reason=f"{zone} would hold {after} > {limit} ({self.max_fill:g} of "
                                                 f"{self.capacity[zone]})", conditions=[check])


def create_capacity_gate(config: dict[str, Any] | None, services: Any) -> CapacityGate:
    return CapacityGate(services.pinned_model(), float((config or {}).get("max_fill", 1.0)))
