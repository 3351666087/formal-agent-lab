"""Generic, domain-neutral evaluator: metrics derived from the episode record and final truth properties."""

from __future__ import annotations

from typing import Any

from formal_lab_contracts import (
    EpisodeRecord,
    EvidenceRef,
    MetricDefinition,
    MetricResult,
    PluginDescriptor,
)
from formal_lab_contracts import capabilities as caps
from formal_lab_contracts.interfaces import PluginRegistration

EVALUATOR_ID = "formal-lab.eval.generic"

DEFINITIONS = [
    MetricDefinition(metric_id="goal_reached", label="目标达成", unit="rate", direction="HIGHER_IS_BETTER",
                     aggregation="RATE", value_type="bool", description="goal property holds on the final truth state"),
    MetricDefinition(metric_id="steps_used", label="使用步数", unit="steps", direction="LOWER_IS_BETTER",
                     aggregation="MEAN", value_type="int"),
    MetricDefinition(metric_id="rejected_actions", label="被拒动作", unit="actions", direction="LOWER_IS_BETTER",
                     aggregation="MEAN", value_type="int"),
    MetricDefinition(metric_id="effect_mismatches", label="效果差异", unit="steps", direction="NONE",
                     aggregation="MEAN", value_type="int",
                     description="steps whose observed effect differed from the model's expectation"),
    MetricDefinition(metric_id="model_calls", label="模型调用", unit="calls", direction="LOWER_IS_BETTER",
                     aggregation="MEAN", value_type="int"),
    MetricDefinition(metric_id="tokens", label="Tokens", unit="tokens", direction="LOWER_IS_BETTER",
                     aggregation="MEAN", value_type="int"),
    MetricDefinition(metric_id="wall_seconds", label="墙钟时间", unit="s", direction="LOWER_IS_BETTER",
                     aggregation="MEAN", value_type="float"),
]

DESCRIPTOR = PluginDescriptor(
    plugin_id=EVALUATOR_ID,
    version="1.0.0",
    interface="EVALUATOR",
    capabilities=[{"id": caps.EVAL_DETERMINISTIC}, {"id": caps.EVAL_APPLIES_TO, "params": {"all": True}}],
    semantic_profiles=["deterministic_finite_v1"],
    config_schema={"type": "object", "properties": {}, "additionalProperties": False},
    entrypoint="formal_lab_eval.generic:create",
    ui={"label": "通用评分", "category": "evaluator", "metric_labels": {d.metric_id: d.label for d in DEFINITIONS}},
    license="Apache-2.0",
    source="formal-lab-evaluation",
)


class GenericEvaluator:
    descriptor = DESCRIPTOR

    def metric_definitions(self) -> list[MetricDefinition]:
        return list(DEFINITIONS)

    def score(self, episode: EpisodeRecord) -> list[MetricResult]:
        run = episode.run_id
        ev = [EvidenceRef(kind="snapshot", id=f"{run}:final")]

        def ok(mid: str, value: float) -> MetricResult:
            return MetricResult(metric_id=mid, metric_version="1", subject=run, value=float(value), status="OK",
                                evidence=ev)

        goal = episode.environment_summary.get("goal")
        props = episode.environment_summary.get("properties", {})
        out = []
        if goal and goal in props:
            out.append(ok("goal_reached", 1.0 if props[goal] else 0.0))
        else:
            out.append(MetricResult(metric_id="goal_reached", metric_version="1", subject=run, value=None,
                                    status="NOT_APPLICABLE", missing_reason="scenario declares no goal property"))
        outcomes = [s.outcome for s in episode.steps if s.outcome is not None]
        out.append(ok("steps_used", len(episode.steps)))
        out.append(ok("rejected_actions", sum(o.status == "REJECTED" for o in outcomes)))
        out.append(ok("effect_mismatches", sum(o.effect_comparison is not None and o.effect_comparison.verdict ==
                                               "DIFFERENT" for o in outcomes)))
        out.append(ok("wall_seconds", round(episode.usage.wall_seconds, 3)))
        # phase 4A: a strategy that asked a model counts, also when every call failed and a rule fallback acted
        llm = episode.usage.model_attempts > 0 or any(
            s.proposal and (s.proposal.source.kind in ("LLM", "LLM_STUB", "LLM_PROTOCOL_TEST")
                            or s.proposal.source.model_call_ids) for s in episode.steps)
        for mid, value in (("model_calls", episode.usage.model_calls), ("tokens", episode.usage.tokens)):
            if llm:
                out.append(ok(mid, value))
            else:
                out.append(MetricResult(metric_id=mid, metric_version="1", subject=run, value=None,
                                        status="NOT_APPLICABLE", missing_reason="strategy makes no model calls"))
        return out


def create(config: dict[str, Any] | None = None, services: Any = None) -> GenericEvaluator:
    return GenericEvaluator()


def registrations() -> list[PluginRegistration]:
    return [PluginRegistration(DESCRIPTOR, create)]
