"""Order-service plugins besides the environment: an independent probe, a rule strategy and a scorer."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
from formal_lab_contracts import (
    ActionProposal,
    CandidateAction,
    EnvironmentSession,
    EpisodeRecord,
    EvidenceRef,
    MetricDefinition,
    MetricResult,
    PlanningContext,
    PluginDescriptor,
    ProbeResult,
    ProposalSource,
)
from formal_lab_contracts import capabilities as caps
from formal_lab_contracts.errors import NonRetryableFailure

from .env import ENV_ID
from .instance import BASE_ORDERS, HORIZON
from .model import PACKAGE_ID
from .net import trust_env

# ------------------------------------------------------------------ probe (P2-064)

PROBE_METRICS = [
    MetricDefinition(metric_id="throughput", label="吞吐", unit="orders/tick", direction="HIGHER_IS_BETTER",
                     aggregation="MEAN", value_type="float",
                     description="orders completed in the last W logical ticks ÷ W (logical window)"),
    MetricDefinition(metric_id="completion_rate", label="完成率", unit="ratio", direction="HIGHER_IS_BETTER",
                     aggregation="MEAN", value_type="float", description="completed ÷ arrived orders (to date)"),
    MetricDefinition(metric_id="queue_length", label="队列长度", unit="orders", direction="LOWER_IS_BETTER",
                     aggregation="MEAN", value_type="int", description="orders waiting in the processing queue now"),
    MetricDefinition(metric_id="backlog", label="积压", unit="orders", direction="LOWER_IS_BETTER",
                     aggregation="MEAN", value_type="int", description="arrived orders not yet processing"),
    MetricDefinition(metric_id="latency_ticks", label="订单时延", unit="ticks", direction="LOWER_IS_BETTER",
                     aggregation="MEAN", value_type="float",
                     description="mean done_at − arrive_at of orders completed in the window (logical ticks)"),
    MetricDefinition(metric_id="op_latency_ms", label="操作处理耗时", unit="ms", direction="LOWER_IS_BETTER",
                     aggregation="MEAN", value_type="float",
                     description="median service-side handling time of the last 4·W operations (wall clock)"),
    MetricDefinition(metric_id="recovery_seconds", label="恢复时间", unit="s", direction="LOWER_IS_BETTER",
                     aggregation="MAX", value_type="float",
                     description="last restart: process start − last committed operation before it (wall clock)"),
]

PROBE = PluginDescriptor(
    plugin_id="formal-lab.example.orders.probe", version="1.0.0", interface="PROBE", interface_version="2",
    capabilities=[{"id": caps.PROBE_METRICS, "params": {"environments": [ENV_ID]}}],
    config_schema={"type": "object", "properties": {"window": {"type": "integer", "minimum": 1, "default": 4}},
                   "additionalProperties": False},
    entrypoint="formal_lab_example_orders.plugins:create_probe",
    ui={"label": "订单服务探针", "category": "probe",
        "description": "Reads the service's own metrics (GET /metrics), independent of any agent's observation",
        "metric_labels": {d.metric_id: d.label for d in PROBE_METRICS}},
    license="Apache-2.0", source="formal-lab-example-orders")


class OrderProbe:
    descriptor = PROBE

    def __init__(self, config: dict[str, Any] | None = None):
        self.window = int((config or {}).get("window", 4))

    def definitions(self) -> list[MetricDefinition]:
        return list(PROBE_METRICS)

    def sample(self, session: EnvironmentSession, *, step: int | None) -> list[ProbeResult]:
        tenant = session.owner.get("tenant")
        url = f"{session.endpoint}/t/{tenant}/metrics"
        now = datetime.now(UTC)
        try:
            data = httpx.get(url, params={"window": self.window}, timeout=5, trust_env=trust_env(url)).json()
        except (httpx.HTTPError, ValueError) as exc:
            return [ProbeResult(probe_id=f"{d.metric_id}@{step}", probe=PROBE.ref(), source=f"GET {url}",
                                metric=d.metric_id, value=None, unit=d.unit or "", status="ERROR",
                                missing_reason=f"{type(exc).__name__}: {exc}"[:200],
                                window={"kind": "LOGICAL_STEPS", "size": self.window, "start": 0, "end": 0},
                                logical_step=step, wall_time=now) for d in PROBE_METRICS]
        window = data["window"]
        values = {"throughput": data["throughput"], "completion_rate": data["completion_rate"],
                  "queue_length": data["queue_length"], "backlog": data["backlog"],
                  "latency_ticks": data["latency_ticks"], "op_latency_ms": data["op_latency_ms_p50"],
                  "recovery_seconds": data["recovery_seconds"]}
        out = []
        for d in PROBE_METRICS:
            v = values[d.metric_id]
            wall = d.metric_id in ("op_latency_ms", "recovery_seconds")
            win = ({"kind": "WALL_SECONDS", "size": 1.0, "start": 0.0, "end": 1.0} if wall else window)
            out.append(ProbeResult(
                probe_id=f"{d.metric_id}@{step}", probe=PROBE.ref(), source=f"GET {url}", metric=d.metric_id,
                value=None if v is None else float(v), unit=d.unit or "", status="OK" if v is not None else "MISSING",
                missing_reason=None if v is not None else ("no restart so far" if d.metric_id == "recovery_seconds"
                                                           else "nothing completed / arrived in the window"),
                window=win, logical_step=step, wall_time=now,
                evidence=[EvidenceRef(kind="probe", id=f"{tenant}@clock{data['clock']}",
                                      note=f"restarts so far: {data['restarts']}")]))
        return out


def create_probe(config: dict[str, Any] | None, services: Any = None) -> OrderProbe:
    return OrderProbe(config)


# ------------------------------------------------------------------ rule strategy

RULES = PluginDescriptor(
    plugin_id="formal-lab.example.orders.rules", version="1.0.0", interface="PLANNER",
    capabilities=[{"id": caps.PLAN_RULE}], semantic_profiles=["deterministic_finite_v1"],
    requires=[{"id": caps.DRIVER_CANDIDATES, "params": {"of": "driver"}}],
    config_schema={"type": "object", "properties": {}, "additionalProperties": False},
    entrypoint="formal_lab_example_orders.plugins:create_rules",
    ui={"label": "订单处理规则", "category": "rule",
        "description": "start the queue head on a free station > queue the reserved order due first > reserve the "
                       "submitted order due first > restock a SKU an order is waiting for > advance time"},
    license="Apache-2.0", source="formal-lab-example-orders")

DUE = {o: spec[3] for o, spec in BASE_ORDERS.items()}
SKU = {o: spec[0] for o, spec in BASE_ORDERS.items()}


class OrderRules:
    descriptor = RULES

    def propose(self, context: PlanningContext) -> ActionProposal:
        ok = [c for c in context.candidates if str(c.belief_applicability) == "APPLICABLE"]
        by = lambda t: [c for c in ok if c.action.action_type == t]  # noqa: E731
        facts = {f.path: f.value for f in context.observation.facts}
        choice: CandidateAction | None = None
        reason = ""
        if starts := by("start"):
            choice, reason = sorted(starts, key=lambda c: c.action.params["st"])[0], "start the queue head"
        elif enq := by("enqueue"):
            choice = min(enq, key=lambda c: (DUE[c.action.params["o"]], c.action.params["o"]))
            reason = "queue the reserved order due first"
        elif res := by("reserve"):
            choice = min(res, key=lambda c: (DUE[c.action.params["o"]], c.action.params["o"]))
            reason = "reserve stock for the submitted order due first"
        else:
            waiting = {SKU[o] for o in DUE if facts.get(f"status[{o}]") == "submitted"}
            restock = [c for c in by("restock") if c.action.params["s"] in waiting]
            if restock:
                choice, reason = restock[0], f"restock {restock[0].action.params['s']}: an order waits for it"
            elif ticks := by("tick"):
                choice, reason = ticks[0], "nothing to start, queue or reserve: advance time"
        if choice is None:
            raise NonRetryableFailure("no applicable order-handling action")
        return ActionProposal(proposal_id=f"{context.step_id}:proposal", run_id=context.run_id,
                              step_id=context.step_id, step=context.step, actor_id=context.actor_id,
                              action=choice.action, based_on_revision=context.observation.state_revision,
                              source=ProposalSource(kind="RULE", strategy=RULES.ref()), rationale=reason,
                              candidates_considered=len(context.candidates))


def create_rules(config: dict[str, Any] | None, services: Any = None) -> OrderRules:
    return OrderRules()


# ------------------------------------------------------------------ scorer

SCORES = [
    MetricDefinition(metric_id="orders_completed", label="完成订单数", unit="orders", direction="HIGHER_IS_BETTER",
                     aggregation="MEAN", value_type="int"),
    MetricDefinition(metric_id="late_orders", label="延期订单数", unit="orders", direction="LOWER_IS_BETTER",
                     aggregation="MEAN", value_type="int",
                     description="completed after the due time, or not completed (counted as done at horizon + 1)"),
    MetricDefinition(metric_id="mean_latency", label="平均订单时延", unit="ticks", direction="LOWER_IS_BETTER",
                     aggregation="MEAN", value_type="float", description="mean done_at − arrive_at of completed orders"),
]

SCORER = PluginDescriptor(
    plugin_id="formal-lab.example.orders.scorer", version="1.0.0", interface="EVALUATOR",
    capabilities=[{"id": caps.EVAL_DETERMINISTIC}, {"id": caps.EVAL_APPLIES_TO, "params": {"package_ids": [PACKAGE_ID]}}],
    semantic_profiles=["deterministic_finite_v1"], entrypoint="formal_lab_example_orders.plugins:create_scorer",
    ui={"label": "订单评分", "category": "evaluator", "metric_labels": {d.metric_id: d.label for d in SCORES}},
    license="Apache-2.0", source="formal-lab-example-orders")


class OrderScorer:
    descriptor = SCORER

    def metric_definitions(self) -> list[MetricDefinition]:
        return list(SCORES)

    def score(self, episode: EpisodeRecord) -> list[MetricResult]:
        s = episode.final_truth_state
        sub = episode.run_id
        if not s:
            return [MetricResult(metric_id=d.metric_id, metric_version="1", subject=sub, value=None, status="MISSING",
                                 missing_reason="no final state") for d in SCORES]
        done = {o: int(s[f"done_at[{o}]"]) for o in DUE if s.get(f"status[{o}]") == "completed"}
        late = sum(1 for o in DUE if done.get(o, HORIZON + 1) > DUE[o])
        arrive = {o: spec[2] for o, spec in BASE_ORDERS.items()}
        lat = [done[o] - arrive[o] for o in done]
        vals = {"orders_completed": float(len(done)), "late_orders": float(late),
                "mean_latency": (sum(lat) / len(lat)) if lat else None}
        return [MetricResult(metric_id=k, metric_version="1", subject=sub, value=v,
                             status="OK" if v is not None else "MISSING",
                             missing_reason=None if v is not None else "no completed orders",
                             unit=next(d.unit for d in SCORES if d.metric_id == k)) for k, v in vals.items()]


def create_scorer(config: dict[str, Any] | None, services: Any = None) -> OrderScorer:
    return OrderScorer()
