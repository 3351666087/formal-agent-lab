"""Deterministic scheduling scorer (Evaluator interface): metrics come only from the simulator truth state.

- orders_completed: orders whose operations are all done.
- delay_cost: Σ_orders late_cost[o] × max(0, completion[o] − due[o]); an unfinished order is charged as if it
  completed at horizon + 1 (documented penalty), so incomplete runs are never cheaper than late ones.
- makespan: latest finish time; MISSING when not all operations are done.
- mean_tardiness: mean over orders of max(0, completion − due) with the same penalty rule.
"""

from __future__ import annotations

from typing import Any

from formal_lab_contracts import (
    EpisodeRecord,
    EvidenceRef,
    MetricDefinition,
    MetricResult,
    ModelPackage,
    PluginDescriptor,
)
from formal_lab_contracts import capabilities as caps
from formal_lab_model import check_model

from .model import HORIZON

EVALUATOR_ID = "formal-lab.example.scheduling.scorer"

DEFINITIONS = [
    MetricDefinition(metric_id="orders_completed", label="完工订单数", unit="orders", direction="HIGHER_IS_BETTER",
                     aggregation="MEAN", value_type="int",
                     observable="orders whose operations are all done in the final truth state",
                     window="whole run (read at the end)"),
    MetricDefinition(metric_id="delay_cost", label="模拟延期成本", unit="cost", direction="LOWER_IS_BETTER",
                     aggregation="MEAN", value_type="float",
                     description="Σ late_cost × tardiness; unfinished orders count as finishing at horizon+1",
                     observable="Σ late_cost × tardiness per order",
                     window="whole run (read at the end); unfinished orders at horizon + 1"),
    MetricDefinition(metric_id="makespan", label="完工时间", unit="ticks", direction="LOWER_IS_BETTER",
                     aggregation="MEAN", value_type="int", description="MISSING unless all operations finished",
                     observable="tick at which the last operation finished",
                     window="whole run (read at the end); MISSING unless all finished"),
    MetricDefinition(metric_id="mean_tardiness", label="平均延误", unit="ticks", direction="LOWER_IS_BETTER",
                     aggregation="MEAN", value_type="float",
                     observable="mean max(0, finish − due) per order", window="whole run (read at the end)"),
]

DESCRIPTOR = PluginDescriptor(
    plugin_id=EVALUATOR_ID,
    version="1.0.0",
    interface="EVALUATOR",
    capabilities=[{"id": caps.EVAL_DETERMINISTIC},
                  {"id": caps.EVAL_APPLIES_TO, "params": {"package_ids": ["neutral-scheduling"]}}],
    semantic_profiles=["deterministic_finite_v1"],
    config_schema={"type": "object", "properties": {}, "additionalProperties": False},
    output_schema={"type": "array", "items": {"$ref": "https://formal-lab.dev/contracts/v1/MetricResult.schema.json"}},
    entrypoint="formal_lab_example_scheduling.scorer:create",
    ui={"label": "调度评分", "category": "evaluator",
        "metric_labels": {d.metric_id: d.label for d in DEFINITIONS}},
    license="Apache-2.0",
    source="formal-lab-example-scheduling",
)


class SchedulingScorer:
    descriptor = DESCRIPTOR

    def __init__(self, package: ModelPackage):
        model = check_model(package.ir)
        self.orders = model.domains["orders"]
        self.ops = model.domains["ops"]
        self.order_of = model.families["order_of"].table
        self.due = model.families["due"].table
        self.late_cost = model.families["late_cost"].table

    def metric_definitions(self) -> list[MetricDefinition]:
        return list(DEFINITIONS)

    def score(self, episode: EpisodeRecord) -> list[MetricResult]:
        s = episode.final_truth_state
        evidence = [EvidenceRef(kind="snapshot", id=f"{episode.run_id}:final", note="final truth state")]
        done = {op: s[f"phase[{op}]"] == "done" for op in self.ops}
        completion: dict[str, int] = {}
        for order in self.orders:
            ops = [op for op in self.ops if self.order_of[f"order_of[{op}]"] == order]
            completion[order] = (max(int(s[f"finish[{op}]"]) for op in ops) if all(done[op] for op in ops)
                                 else HORIZON + 1)
        tardiness = {o: max(0, completion[o] - int(self.due[f"due[{o}]"])) for o in self.orders}
        cost = sum(int(self.late_cost[f"late_cost[{o}]"]) * tardiness[o] for o in self.orders)
        results = [
            _ok("orders_completed", episode.run_id, sum(completion[o] <= HORIZON for o in self.orders), evidence),
            _ok("delay_cost", episode.run_id, float(cost), evidence, unit="cost"),
            _ok("mean_tardiness", episode.run_id, sum(tardiness.values()) / len(self.orders), evidence, unit="ticks"),
        ]
        if all(done.values()):
            results.append(_ok("makespan", episode.run_id, max(int(s[f"finish[{op}]"]) for op in self.ops), evidence,
                               unit="ticks"))
        else:
            results.append(MetricResult(metric_id="makespan", metric_version="1", subject=episode.run_id, value=None,
                                        status="MISSING", missing_reason="not all operations finished",
                                        unit="ticks", evidence=evidence))
        return results


def _ok(metric_id: str, run_id: str, value: float, evidence: list[EvidenceRef], unit: str | None = None) -> MetricResult:
    return MetricResult(metric_id=metric_id, metric_version="1", subject=run_id, value=float(value), status="OK",
                        unit=unit, evidence=evidence)


def create(config: dict[str, Any] | None, services: Any) -> SchedulingScorer:
    return SchedulingScorer(services.pinned_model())
