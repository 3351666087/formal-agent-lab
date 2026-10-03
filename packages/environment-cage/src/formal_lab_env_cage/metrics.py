"""CAGE 4 metrics (phase 4B, B2): CybORG's native score kept apart from platform metrics, each with its source.

Input: the episode's final truth state — the referee timeline the worker recorded per world step (team rewards, green
results, hosts where red holds a session) — and the steps' outcomes. Nothing here comes from a blue observation or a
strategy's own account.

  native_blue_reward       CybORG's own reward to the blue team, summed over the episode (NATIVE score; unit = CAGE
                           reward points — not comparable with other environments' metrics)
  green_success_rate       normal business: share of the green agents' work / service-access actions that CybORG
                           reported successful (TRUE) among those it reported TRUE or FALSE
  green_failed_actions     count of green work / access actions CybORG reported FALSE
  red_footholds_final      hosts where a red agent holds a session at the end (referee data)
  red_foothold_host_steps  Σ over world steps of such hosts — how long red held how much
  recovery_time            mean world steps from a host gaining a red session to losing all of them (a recovery =
                           the host left the foothold set before the end); MISSING when no host recovered
  unrecovered_hosts        hosts holding a red session at the end that had one for at least one step
  blue_actions_not_started blue proposals CybORG did not start (AGENT_BUSY: a previous action still in progress)
  blue_agent_count         platform-controlled blue agents — a count of agents, NOT business survival
Model calls, tokens and wall time come from the platform's generic evaluator (formal-lab.eval.generic).
"""

from __future__ import annotations

import json
from typing import Any

from formal_lab_contracts import EpisodeRecord, EvidenceRef, MetricDefinition, MetricResult, PluginDescriptor
from formal_lab_contracts import capabilities as caps

from .model import PACKAGE_ID, PROFILE

EVALUATOR_ID = "formal-lab.cage4.metrics"
WINDOW = "whole episode (world steps 1..end), from the referee timeline"

DEFINITIONS = [
    MetricDefinition(metric_id="native_blue_reward", label="CAGE 原生蓝方奖励", unit="CAGE reward",
                     direction="HIGHER_IS_BETTER", aggregation="MEAN", value_type="float",
                     description="NATIVE: CybORG's own blue-team reward summed over the episode",
                     observable="CybORG get_rewards()['Blue'] per world step", window=WINDOW),
    MetricDefinition(metric_id="green_success_rate", label="正常业务成功率", unit="ratio",
                     direction="HIGHER_IS_BETTER", aggregation="MEAN", value_type="float",
                     description="green work / service-access actions reported TRUE among TRUE + FALSE",
                     observable="each green agent's last action and its observation `success`", window=WINDOW),
    MetricDefinition(metric_id="green_failed_actions", label="正常业务失败次数", unit="actions",
                     direction="LOWER_IS_BETTER", aggregation="MEAN", value_type="int",
                     observable="green work / access actions reported FALSE", window=WINDOW),
    MetricDefinition(metric_id="red_footholds_final", label="结束时红方立足主机", unit="hosts",
                     direction="LOWER_IS_BETTER", aggregation="MEAN", value_type="int",
                     observable="hosts with a red session in CybORG's state (referee)", window="the last world step"),
    MetricDefinition(metric_id="red_foothold_host_steps", label="红方立足主机·步", unit="host-steps",
                     direction="LOWER_IS_BETTER", aggregation="MEAN", value_type="int",
                     observable="Σ over world steps of hosts with a red session (referee)", window=WINDOW),
    MetricDefinition(metric_id="recovery_time", label="恢复时间", unit="world steps",
                     direction="LOWER_IS_BETTER", aggregation="MEAN", value_type="float",
                     description="mean steps from a host gaining a red session to losing all of them; MISSING when "
                                 "no host recovered",
                     observable="enter / leave events of the red foothold set per host (referee)", window=WINDOW),
    MetricDefinition(metric_id="unrecovered_hosts", label="未恢复主机", unit="hosts",
                     direction="LOWER_IS_BETTER", aggregation="MEAN", value_type="int",
                     observable="hosts in the foothold set at the end", window="the last world step"),
    MetricDefinition(metric_id="blue_actions_not_started", label="未启动的蓝方动作", unit="actions",
                     direction="LOWER_IS_BETTER", aggregation="MEAN", value_type="int",
                     observable="outcomes REJECTED with AGENT_BUSY", window="whole run"),
    MetricDefinition(metric_id="blue_agent_count", label="蓝方代理数量（不是业务存活）", unit="agents",
                     direction="HIGHER_IS_BETTER", aggregation="MEAN", value_type="int",
                     description="a count of platform-controlled blue agents; it is not a business metric",
                     observable="the scenario's participants", window="the run"),
]

DESCRIPTOR = PluginDescriptor(
    plugin_id=EVALUATOR_ID, version="1.0.0", interface="EVALUATOR",
    capabilities=[{"id": caps.EVAL_DETERMINISTIC}, {"id": caps.EVAL_APPLIES_TO, "params": {"package_ids": [PACKAGE_ID]}}],
    semantic_profiles=[PROFILE],
    config_schema={"type": "object", "properties": {}, "additionalProperties": False},
    output_schema={"type": "array", "items": {"$ref": "https://formal-lab.dev/contracts/v1/MetricResult.schema.json"}},
    entrypoint="formal_lab_env_cage.metrics:create",
    ui={"label": "CAGE 4 指标（原生分数与平台指标分开）", "category": "evaluator",
        "metric_labels": {d.metric_id: d.label for d in DEFINITIONS}},
    license="Apache-2.0", source="formal-lab-env-cage")


def recoveries(timeline: list[dict[str, Any]]) -> tuple[list[int], set[str]]:
    """Durations (world steps) of foothold episodes that ended before the last step, and hosts still held at the end."""
    since: dict[str, int] = {}
    done: list[int] = []
    for row in timeline:
        now = set(row["red_foothold_hosts"])
        for h in sorted(now - set(since)):
            since[h] = int(row["world_step"])
        for h in sorted(set(since) - now):
            done.append(int(row["world_step"]) - since.pop(h))
    return done, set(since)


class Cage4Metrics:
    descriptor = DESCRIPTOR

    def metric_definitions(self) -> list[MetricDefinition]:
        return list(DEFINITIONS)

    def score(self, episode: EpisodeRecord) -> list[MetricResult]:
        rid = episode.run_id
        ev = [EvidenceRef(kind="snapshot", id=f"{rid}:final", note="referee timeline in the final truth state")]
        raw = episode.final_truth_state.get("referee_timeline")
        busy = sum(1 for st in episode.steps if st.outcome is not None and st.outcome.status == "REJECTED"
                   and "AGENT_BUSY" in str(st.outcome.result.get("reason", "")))
        agents = len(episode.scenario.participants)
        if not raw:
            why = episode.environment_summary.get("unavailable") or "no referee timeline in the final truth state"
            return [*(_missing(d.metric_id, rid, why) for d in DEFINITIONS
                      if d.metric_id not in ("blue_actions_not_started", "blue_agent_count")),
                    _ok("blue_actions_not_started", rid, busy, ev), _ok("blue_agent_count", rid, agents, ev)]
        timeline = json.loads(raw)
        reward = sum(float(r["rewards"].get("Blue", 0.0)) for r in timeline)
        ok = sum(v for r in timeline for k, v in r["green"].items() if k.endswith(":TRUE"))
        bad = sum(v for r in timeline for k, v in r["green"].items() if k.endswith(":FALSE"))
        held = [len(r["red_foothold_hosts"]) for r in timeline]
        durations, open_ = recoveries(timeline)
        out = [_ok("native_blue_reward", rid, round(reward, 4), ev),
               _ok("green_failed_actions", rid, bad, ev),
               _ok("red_footholds_final", rid, held[-1] if held else 0, ev),
               _ok("red_foothold_host_steps", rid, sum(held), ev),
               _ok("unrecovered_hosts", rid, len(open_), ev),
               _ok("blue_actions_not_started", rid, busy, ev),
               _ok("blue_agent_count", rid, agents, ev)]
        out.append(_ok("green_success_rate", rid, ok / (ok + bad), ev) if ok + bad else
                   _missing("green_success_rate", rid, "no green work / access action was reported TRUE or FALSE"))
        out.append(_ok("recovery_time", rid, sum(durations) / len(durations), ev) if durations else
                   _missing("recovery_time", rid, "no host left the red foothold set before the end"))
        return out


def _ok(metric_id: str, rid: str, value: float, ev: list[EvidenceRef]) -> MetricResult:
    return MetricResult(metric_id=metric_id, metric_version="1", subject=rid, value=float(value), status="OK",
                        evidence=ev)


def _missing(metric_id: str, rid: str, why: str) -> MetricResult:
    return MetricResult(metric_id=metric_id, metric_version="1", subject=rid, value=None, status="MISSING",
                        missing_reason=why)


def create(config: dict[str, Any] | None, services: Any) -> Cage4Metrics:
    return Cage4Metrics()
