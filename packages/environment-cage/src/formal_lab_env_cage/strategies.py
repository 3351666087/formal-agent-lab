"""Blue strategies for CAGE 4 on the platform (phase 4B, B2) — each decides from the agent's own observation only.

Baselines:
  * `formal-lab.cage4.blue-sleep`   = SleepAgent, the official Scenario4 baseline blue (does nothing) — a mapping of a
    runnable native class, compared with it world step by world step;
  * `formal-lab.cage4.blue-monitor` — Monitor every step. CybORG 4.0 ships a `MonitorAgent`, but it is a CAGE-2-era
    class (it monitors as agent "Blue" and its constructor takes no name, so Scenario4's generator cannot build it):
    this policy is therefore NOT called a native mapping; it is compared with the native direct path driven with the
    same Monitor actions.
`cc4BlueRandomAgent` is not mapped: it draws from CybORG's RNG, a platform copy would draw differently and would not
be the same agent.

Platform policy:
  * `formal-lab.cage4.blue-react` — a reactive rule over the agent's own alerts: while an action is in progress it
    waits (CybORG would not start another); a file reported by Analyse on a host → Restore it; a connection alert →
    Analyse that host; otherwise Monitor. Ties go to the lexicographically first host, so it is deterministic.
"""

from __future__ import annotations

from typing import Any

from formal_lab_contracts import (
    ActionProposal,
    GroundAction,
    PlanningContext,
    PluginDescriptor,
    ProposalSource,
)
from formal_lab_contracts import capabilities as caps

from .model import PROFILE


def _descriptor(name: str, label: str, description: str) -> PluginDescriptor:
    return PluginDescriptor(
        plugin_id=f"formal-lab.cage4.blue-{name}", version="1.0.0", interface="PLANNER",
        capabilities=[{"id": caps.PLAN_RULE}], semantic_profiles=[PROFILE],
        config_schema={"type": "object", "additionalProperties": False},
        entrypoint=f"formal_lab_env_cage.strategies:create_{name}",
        ui={"label": label, "category": "rule", "description": description},
        license="Apache-2.0", source="formal-lab-env-cage")


SLEEP = _descriptor("sleep", "CAGE 蓝方·等待（=SleepAgent 官方基线）", "always Sleep — the official Scenario4 blue baseline")
MONITOR = _descriptor("monitor", "CAGE 蓝方·恒定监控", "always Monitor (CybORG's MonitorAgent intent; that class "
                      "cannot run in Scenario4)")
REACT = _descriptor("react", "CAGE 蓝方·告警响应（平台规则）",
                    "own alerts only: busy → wait; file → Restore; connection → Analyse; else Monitor")


def _proposal(context: PlanningContext, action: GroundAction, descriptor: PluginDescriptor, why: str) -> ActionProposal:
    return ActionProposal(
        proposal_id=f"{context.step_id}:proposal", run_id=context.run_id, step_id=context.step_id, step=context.step,
        actor_id=context.actor_id, action=action, based_on_revision=context.observation.state_revision,
        source=ProposalSource(kind="RULE", strategy=descriptor.ref()), rationale=why,
        candidates_considered=len(context.candidates))


class _Constant:
    def __init__(self, descriptor: PluginDescriptor, action_type: str, why: str):
        self.descriptor, self.action_type, self.why = descriptor, action_type, why

    def propose(self, context: PlanningContext) -> ActionProposal:
        return _proposal(context, GroundAction(action_type=self.action_type), self.descriptor, self.why)


class BlueReact:
    descriptor = REACT

    def propose(self, context: PlanningContext) -> ActionProposal:
        state = _state(context)
        if state.get("busy") is True:
            return _proposal(context, GroundAction(action_type="sleep"), REACT,
                             "an action is still in progress: CybORG would not start another, so wait")
        alerts = {k[len("alert_kind["):-1]: v for k, v in state.items()
                  if k.startswith("alert_kind[") and v not in (None, "none")}
        allowed = {k[len("allowed["):-1] for k, v in state.items() if k.startswith("allowed[") and v is True}
        files = sorted(h for h, kind in alerts.items() if kind == "file" and h in allowed)
        if files:
            return _proposal(context, GroundAction(action_type="restore", params={"host": files[0]}), REACT,
                             f"Analyse found files on {files[0]}: restore the host")
        conns = sorted(h for h, kind in alerts.items() if kind == "connection" and h in allowed)
        if conns:
            return _proposal(context, GroundAction(action_type="analyse", params={"host": conns[0]}), REACT,
                             f"connection alert on {conns[0]} ({len(conns)} host(s) alerting): analyse it")
        return _proposal(context, GroundAction(action_type="monitor"), REACT, "no alert in my zone: monitor")


def _state(context: PlanningContext) -> dict[str, Any]:
    """The agent's own observation (facts) — the projected input of this participant."""
    return {f.path: f.value for f in context.observation.facts}


def create_sleep(config: dict[str, Any] | None, services: Any) -> _Constant:
    return _Constant(SLEEP, "sleep", "official baseline (SleepAgent): sleep")


def create_monitor(config: dict[str, Any] | None, services: Any) -> _Constant:
    return _Constant(MONITOR, "monitor", "constant policy: monitor")


def create_react(config: dict[str, Any] | None, services: Any) -> BlueReact:
    return BlueReact()
