"""Warehouse plugins besides the driver: model frontend, rule strategy (receiver / picker) and scorer.

Everything reads the model through the semantic driver (`services.loaded_model()`), never through the IR.
"""

from __future__ import annotations

import json
from typing import Any

from formal_lab_contracts import (
    ActionProposal,
    CandidateAction,
    EpisodeRecord,
    MetricDefinition,
    MetricResult,
    ModelPackage,
    ModelSource,
    PlanningContext,
    PluginDescriptor,
    ProposalSource,
    digest_of,
    utcnow,
)
from formal_lab_contracts import capabilities as caps
from formal_lab_contracts.errors import InvalidInput, NonRetryableFailure, Unsupported
from pydantic import ValidationError

from .model import NAMESPACE, PROFILE, SCHEMA_ID, SOURCE_FORMAT, WarehouseModel, json_schema

# ------------------------------------------------------------------ frontend

FRONTEND = PluginDescriptor(
    plugin_id="formal-lab.example.warehouse.frontend", version="1.0.0", interface="MODEL_FRONTEND",
    capabilities=[{"id": f"profile.{PROFILE}"}], semantic_profiles=[PROFILE], input_schema=json_schema(),
    entrypoint="formal_lab_example_warehouse.plugins:create_frontend",
    ui={"label": "Warehouse JSON", "category": "model_frontend",
        "description": "warehouse-json/v1 → ModelPackage with a namespaced warehouse_alloc_v1 payload"},
    license="Apache-2.0", source="formal-lab-example-warehouse")


def build_package(model: WarehouseModel, *, package_id: str = "warehouse", version: int = 1,
                  origin: str = "examples/warehouse-allocation") -> ModelPackage:
    data = json.loads(model.model_dump_json())
    body = {"namespace": NAMESPACE, "schema_id": SCHEMA_ID, "data": data}
    return ModelPackage(package_id=package_id, version=version, frontend=FRONTEND.ref(), semantic_profile=PROFILE,
                        digest=digest_of(body), payload={"kind": "namespaced", **body},
                        source=ModelSource(format=SOURCE_FORMAT, text=model.model_dump_json(indent=2), origin=origin),
                        created_at=utcnow())


class WarehouseFrontend:
    descriptor = FRONTEND

    def compile(self, source: ModelSource, *, package_id: str, version: int) -> ModelPackage:
        if source.format != SOURCE_FORMAT:
            raise Unsupported(f"source format {source.format!r} is not {SOURCE_FORMAT}")
        try:
            model = WarehouseModel.model_validate_json(source.text or "")
        except ValidationError as exc:
            raise InvalidInput("warehouse model does not match its schema",
                               details={"errors": [str(e["msg"]) for e in exc.errors()]}) from exc
        return build_package(model, package_id=package_id, version=version, origin=source.origin or "frontend")


def create_frontend(config: dict[str, Any] | None = None, services: Any = None) -> WarehouseFrontend:
    return WarehouseFrontend()


# ------------------------------------------------------------------ rule strategy

RULES = PluginDescriptor(
    plugin_id="formal-lab.example.warehouse.rules", version="1.0.0", interface="PLANNER",
    capabilities=[{"id": caps.PLAN_RULE}], semantic_profiles=[PROFILE],
    requires=[{"id": caps.DRIVER_CANDIDATES, "params": {"of": "driver"}}],
    config_schema={"type": "object", "properties": {
        "role": {"type": "string", "enum": ["receiver", "picker", "both"], "default": "both"}},
        "additionalProperties": False},
    entrypoint="formal_lab_example_warehouse.plugins:create_rules",
    ui={"label": "仓储规则（上架 / 拣选）", "category": "rule",
        "description": "Receiver: largest pallet into the zone with most room. Picker: earliest-due open line; "
                       "assign a free station to the zone that holds its SKU; otherwise wait (tick)."},
    license="Apache-2.0", source="formal-lab-example-warehouse")


class WarehouseRules:
    descriptor = RULES

    def __init__(self, loaded: Any, config: dict[str, Any]):
        self.m = loaded
        self.role = config.get("role", "both")

    def _free(self, state: dict[str, Any], zone: str) -> int:
        return self.m.capacity[zone] - sum(int(state[f"stock[{zone},{k}]"]) for k in self.m.skus)

    def propose(self, context: PlanningContext) -> ActionProposal:
        belief = self.m.belief(context.observation)
        s = belief.state
        last = context.last_outcome  # a put-away an execution gate just refused goes elsewhere next turn (phase 3A)
        refused = (last.action if last is not None and last.status.value == "REJECTED"
                   and str(last.result.get("reason", "")).startswith("EXECUTION_GATE") else None)
        ok = lambda t: [c for c in context.candidates  # noqa: E731
                        if c.action.action_type == t and str(c.belief_applicability) == "APPLICABLE"
                        and c.action != refused]
        choice: CandidateAction | None = None
        reason = ""
        if self.role in ("receiver", "both") and (puts := ok("putaway")):
            choice = min(puts, key=lambda c: (-int(s[f"dock[{c.action.params['inbound']}]"]),
                                              -self._free(s, c.action.params["zone"]), c.action.params["zone"]))
            reason = "put the largest waiting pallet into the zone with the most room"
        if choice is None and self.role in ("picker", "both"):
            choice, reason = self._pick(context, s, ok)
        if choice is None and (ticks := ok("tick")):
            choice, reason = ticks[0], "nothing to do now: advance time"
        if choice is None:
            viable = [c for c in context.candidates if str(c.belief_applicability) in ("APPLICABLE", "UNKNOWN")]
            if not viable:
                raise NonRetryableFailure("no viable warehouse action")
            choice, reason = viable[0], "fallback: first viable candidate"
        return ActionProposal(proposal_id=f"{context.step_id}:proposal", run_id=context.run_id,
                              step_id=context.step_id, step=context.step, actor_id=context.actor_id,
                              action=choice.action, based_on_revision=context.observation.state_revision,
                              source=ProposalSource(kind="RULE", strategy=RULES.ref()), rationale=reason,
                              candidates_considered=len(context.candidates))

    def _pick(self, context: PlanningContext, s: dict[str, Any], ok) -> tuple[CandidateAction | None, str]:
        open_lines = sorted((o.due, o.id, n) for o in self.m.m.orders for n in range(len(o.lines))
                             if not s[f"picked[{o.id},{n}]"])
        picks = ok("pick")
        assigns = ok("assign")
        stations = [st.id for st in self.m.m.stations]
        for _, oid, n in open_lines:
            here = [c for c in picks if c.action.params["order"] == oid and int(c.action.params["line"]) == n]
            if here:
                return here[0], f"pick {oid} line {n} (earliest due open line)"
            line = self.m.orders[oid].lines[n]
            holders = [z for z in self.m.zones if int(s[f"stock[{z},{line.sku}]"]) >= line.qty]
            for z in holders:
                if any(s[f"serves[{st}]"] == z for st in stations):
                    continue  # served but pick not applicable (another reason): look further
                demand = {zz for _, o2, n2 in open_lines for zz in self.m.zones
                          if int(s[f"stock[{zz},{self.m.orders[o2].lines[n2].sku}]"]) >= self.m.orders[o2].lines[n2].qty}
                free_first = sorted(assigns, key=lambda c: (s[f"serves[{c.action.params['station']}]"] != "none",
                                                            s[f"serves[{c.action.params['station']}]"] in demand,
                                                            c.action.params["station"]))
                for c in free_first:
                    if c.action.params["zone"] == z:
                        return c, f"assign station {c.action.params['station']} to {z} (holds {line.sku} for {oid})"
        return None, ""


def create_rules(config: dict[str, Any] | None, services: Any) -> WarehouseRules:
    return WarehouseRules(services.loaded_model(), dict(config or {}))


# ------------------------------------------------------------------ scorer

DEFINITIONS = [
    MetricDefinition(metric_id="orders_completed", label="完成订单数", unit="orders", direction="HIGHER_IS_BETTER",
                     aggregation="MEAN", value_type="int",
                     observable="orders picked in the final truth state", window="whole run (read at the end)"),
    MetricDefinition(metric_id="late_orders", label="延期订单数", unit="orders", direction="LOWER_IS_BETTER",
                     aggregation="MEAN", value_type="int",
                     observable="orders picked after their due time or not picked",
                     window="whole run (read at the end)"),
    MetricDefinition(metric_id="total_lateness", label="总延误", unit="ticks", direction="LOWER_IS_BETTER",
                     aggregation="MEAN", value_type="int",
                     description="Σ max(0, done_at − due); an open order counts as done at horizon + 1",
                     observable="Σ max(0, done_at − due) over all orders",
                     window="whole run (read at the end); open orders at horizon + 1"),
    MetricDefinition(metric_id="station_changes", label="工位调整次数", unit="actions", direction="LOWER_IS_BETTER",
                     aggregation="MEAN", value_type="int",
                     observable="assign / release actions applied", window="whole run (read at the end)"),
    MetricDefinition(metric_id="units_put_away", label="上架件数", unit="units", direction="HIGHER_IS_BETTER",
                     aggregation="MEAN", value_type="int",
                     observable="units moved from docks to stock", window="whole run (read at the end)"),
]

SCORER = PluginDescriptor(
    plugin_id="formal-lab.example.warehouse.scorer", version="1.0.0", interface="EVALUATOR",
    capabilities=[{"id": caps.EVAL_DETERMINISTIC}, {"id": caps.EVAL_APPLIES_TO,
                                                   "params": {"package_ids": ["warehouse", "warehouse-two-stations"]}}],
    semantic_profiles=[PROFILE], entrypoint="formal_lab_example_warehouse.plugins:create_scorer",
    ui={"label": "仓储评分", "category": "evaluator",
        "metric_labels": {d.metric_id: d.label for d in DEFINITIONS}},
    license="Apache-2.0", source="formal-lab-example-warehouse")


class WarehouseScorer:
    descriptor = SCORER

    def __init__(self, loaded: Any):
        self.m = loaded

    def metric_definitions(self) -> list[MetricDefinition]:
        return list(DEFINITIONS)

    def score(self, episode: EpisodeRecord) -> list[MetricResult]:
        s = episode.final_truth_state
        subject = episode.run_id
        if not s:
            return [MetricResult(metric_id=d.metric_id, metric_version="1", subject=subject, value=None,
                                 status="MISSING", missing_reason="no final truth state") for d in DEFINITIONS]
        orders = self.m.m.orders
        done = {o.id: int(s[f"done_at[{o.id}]"]) for o in orders}
        penalty = self.m.m.horizon + 1
        lateness = sum(max(0, (done[o.id] or penalty) - o.due) for o in orders)
        late = sum(1 for o in orders if (done[o.id] or penalty) > o.due)
        changes = sum(1 for st in episode.steps if st.outcome is not None and st.outcome.status == "APPLIED"
                      and st.outcome.action.action_type == "assign")
        units = sum(i.qty for i in self.m.m.inbound) - sum(int(s[f"dock[{i.id}]"]) for i in self.m.m.inbound)
        values = {"orders_completed": sum(1 for v in done.values() if v > 0), "late_orders": late,
                  "total_lateness": lateness, "station_changes": changes, "units_put_away": units}
        return [MetricResult(metric_id=k, metric_version="1", subject=subject, value=float(v), status="OK",
                             unit=next(d.unit for d in DEFINITIONS if d.metric_id == k)) for k, v in values.items()]


def create_scorer(config: dict[str, Any] | None, services: Any) -> WarehouseScorer:
    return WarehouseScorer(services.loaded_model())
