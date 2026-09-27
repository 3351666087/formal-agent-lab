"""Out-of-tree plugin example: registered only through the public SDK plugin API (formal_lab_sdk.plugins).

`org.example.preference-planner` chooses the first candidate whose applicability on the actor's belief is
APPLICABLE, by a configured action-type preference order. `org.example.checklist-planner` (checklist.py) uses the
phase-2 extension points: a versioned TaskPlan with checkpoint / restore. Both depend on nothing but `formal-lab-sdk`.
"""

from __future__ import annotations

from typing import Any

from formal_lab_sdk.plugins import (
    ActionProposal,
    PlanningContext,
    PluginDescriptor,
    PluginRegistration,
    ProposalSource,
    capabilities,
)

DESCRIPTOR = PluginDescriptor(
    plugin_id="org.example.preference-planner",
    version="0.1.0",
    interface="PLANNER",
    capabilities=[{"id": capabilities.PLAN_RULE}],
    semantic_profiles=["deterministic_finite_v1"],
    config_schema={"type": "object", "properties": {"preference": {"type": "array", "items": {"type": "string"}}},
                   "additionalProperties": False},
    entrypoint="fal_example_external_plugin:create",
    ui={"label": "Example: preference planner (external)", "category": "rule",
        "description": "Packaged outside the core; registered via the formal_lab.plugins entry point"},
    license="Apache-2.0",
    source="fal-example-external-plugin",
)


class PreferencePlanner:
    descriptor = DESCRIPTOR

    def __init__(self, preference: list[str]):
        self.preference = preference

    def propose(self, context: PlanningContext) -> ActionProposal:
        def rank(i_c):
            i, c = i_c
            t = c.action.action_type
            return (0 if c.belief_applicability == "APPLICABLE" else 1,
                    self.preference.index(t) if t in self.preference else len(self.preference), i)

        _, chosen = min(enumerate(context.candidates), key=rank)
        return ActionProposal(
            proposal_id=f"{context.step_id}:proposal", run_id=context.run_id, step_id=context.step_id,
            step=context.step, actor_id=context.actor_id, action=chosen.action,
            based_on_revision=context.observation.state_revision,
            source=ProposalSource(kind="EXTERNAL", strategy=DESCRIPTOR.ref()),
            rationale=f"first APPLICABLE candidate by preference {self.preference}",
            candidates_considered=len(context.candidates),
        )


def create(config: dict[str, Any] | None, services: Any) -> PreferencePlanner:
    return PreferencePlanner(list((config or {}).get("preference", [])))


def registrations() -> list[PluginRegistration]:
    from . import checklist

    return [PluginRegistration(DESCRIPTOR, create), PluginRegistration(checklist.DESCRIPTOR, checklist.create)]
