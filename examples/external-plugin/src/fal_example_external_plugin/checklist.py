"""`org.example.checklist-planner`: an out-of-tree planner that keeps a TaskPlan (phase-2 extension, P2-124).

It works through a short checklist: the next `batch` APPLICABLE actions in the configured preference order, each
task depending on the one before. The previous outcome moves the cursor (APPLIED → DONE, anything else → FAILED and a
new plan version with trigger ACTION_REJECTED); a task whose action is no longer applicable gives a new version with
trigger NEW_OBSERVATION; a finished checklist is followed by the next batch. Its whole state — the plan and the
counters — is a PlannerCheckpoint, so the kernel resumes it exactly after a pause or a worker restart.

Only `formal_lab_sdk.plugins` is imported; the plugin never sees the kernel, the platform or the environment.
"""

from __future__ import annotations

import json
from typing import Any

from formal_lab_sdk.plugins import (
    ActionProposal,
    CandidateAction,
    PlanGenerator,
    PlannerCheckpoint,
    PlanningContext,
    PlanRevision,
    PlanTrigger,
    PluginDescriptor,
    ProposalSource,
    TaskNode,
    TaskPlan,
    TaskStatus,
    capabilities,
)

DESCRIPTOR = PluginDescriptor(
    plugin_id="org.example.checklist-planner",
    version="0.2.0",
    interface="PLANNER",
    capabilities=[{"id": capabilities.PLAN_RULE}, {"id": capabilities.PLAN_TASK_PLAN},
                  {"id": capabilities.PLAN_CHECKPOINT}],
    semantic_profiles=["deterministic_finite_v1"],
    config_schema={"type": "object", "additionalProperties": False, "properties": {
        "preference": {"type": "array", "items": {"type": "string"}, "description": "action types, most wanted first"},
        "batch": {"type": "integer", "minimum": 1, "maximum": 10, "default": 3,
                  "description": "tasks per checklist version"}}},
    entrypoint="fal_example_external_plugin.checklist:create",
    ui={"label": "Example: checklist planner (external, task plan)", "category": "rule",
        "description": "Keeps a versioned checklist with checkpoint / restore; packaged outside the core"},
    license="Apache-2.0",
    source="fal-example-external-plugin",
)


def _key(action: Any) -> str:
    return json.dumps(action.model_dump(mode="json"), sort_keys=True)


class ChecklistPlanner:
    descriptor = DESCRIPTOR

    def __init__(self, preference: list[str], batch: int):
        self.preference = preference
        self.batch = batch
        self.actor_id = ""
        self.plan: TaskPlan | None = None
        self.proposals = 0
        self.revisions: list[str] = []

    # ------------------------------------------------------------------ CheckpointingPlanner
    def checkpoint(self) -> PlannerCheckpoint:
        return PlannerCheckpoint(actor_id=self.actor_id, planner=DESCRIPTOR.ref(), step=0,
                                 plan=self.plan, progress={"proposals": self.proposals, "revisions": self.revisions})

    def restore(self, checkpoint: PlannerCheckpoint) -> None:
        self.actor_id = checkpoint.actor_id
        self.plan = checkpoint.plan
        self.proposals = int(checkpoint.progress.get("proposals", 0))
        self.revisions = list(checkpoint.progress.get("revisions", []))

    def current_plan(self) -> TaskPlan | None:
        return self.plan

    # ------------------------------------------------------------------ Planner
    def _rank(self, c: CandidateAction) -> int:
        t = c.action.action_type
        return self.preference.index(t) if t in self.preference else len(self.preference)

    def _new_version(self, ctx: PlanningContext, applicable: list[CandidateAction], trigger: PlanTrigger,
                     detail: str) -> None:
        chosen = sorted(applicable, key=self._rank)[: self.batch]
        nodes, prev = [], None
        for i, c in enumerate(chosen):
            nodes.append(TaskNode(node_id=f"t{i + 1}", label=c.label or c.action.action_type, action=c.action,
                                  depends_on=[prev] if prev else []))
            prev = f"t{i + 1}"
        old = self.plan
        self.plan = TaskPlan(
            plan_id=f"checklist_{ctx.actor_id}", actor_id=ctx.actor_id, version=(old.version + 1) if old else 1,
            generator=PlanGenerator(kind="EXTERNAL", strategy=DESCRIPTOR.ref(), method="preference checklist"),
            created_at_step=ctx.step, nodes=nodes, parent_version=old.version if old else None,
            revision=PlanRevision(trigger=trigger, detail=detail, at_step=ctx.step))
        self.revisions.append(trigger.value)

    def _settle_previous(self, ctx: PlanningContext) -> str | None:
        """Mark the task in progress from the actor's previous outcome; the reason to re-plan, if any."""
        if self.plan is None or self.plan.cursor is None:
            return None
        node = self.plan.node(self.plan.cursor)
        if node.status != TaskStatus.IN_PROGRESS or ctx.last_outcome is None:
            return None
        applied = str(getattr(ctx.last_outcome.status, "value", ctx.last_outcome.status)) == "APPLIED"
        nodes = [n.model_copy(update={"status": TaskStatus.DONE if applied else TaskStatus.FAILED,
                                      "completed_at_step": ctx.step if applied else None})
                 if n.node_id == node.node_id else n for n in self.plan.nodes]
        done = all(n.status == TaskStatus.DONE for n in nodes)
        self.plan = self.plan.model_copy(update={"nodes": nodes, "cursor": None,
                                                 "status": "COMPLETED" if done else self.plan.status})
        return None if applied else f"{node.node_id} ({node.label}) was not applied"

    def propose(self, context: PlanningContext) -> ActionProposal:
        self.actor_id = context.actor_id
        applicable = [c for c in context.candidates if c.belief_applicability == "APPLICABLE"]
        rejected = self._settle_previous(context)
        if applicable:
            offered = {_key(c.action) for c in applicable}
            if self.plan is None:
                self._new_version(context, applicable, PlanTrigger.INITIAL, "first checklist")
            elif rejected:
                self._new_version(context, applicable, PlanTrigger.ACTION_REJECTED, rejected)
            elif self.plan.status == "COMPLETED":
                self._new_version(context, applicable, PlanTrigger.NEW_OBSERVATION, "checklist done; next batch")
            else:
                ready = self.plan.ready()
                if not ready or _key(ready[0].action) not in offered:
                    what = ready[0].label if ready else "no task is ready"
                    self._new_version(context, applicable, PlanTrigger.NEW_OBSERVATION,
                                      f"{what} is no longer applicable")
        task = self.plan.ready()[0] if self.plan is not None and applicable and self.plan.ready() else None
        if task is not None:
            action, why = task.action, f"checklist v{self.plan.version} task {task.node_id} ({task.label})"
            nodes = [n.model_copy(update={"status": TaskStatus.IN_PROGRESS, "attempts": n.attempts + 1})
                     if n.node_id == task.node_id else n for n in self.plan.nodes]
            self.plan = self.plan.model_copy(update={"nodes": nodes, "cursor": task.node_id})
        else:  # nothing applicable on the belief: the most preferred candidate (the environment decides)
            action = min(context.candidates, key=self._rank).action
            why = "no APPLICABLE candidate; most preferred of the offered ones"
        self.proposals += 1
        return ActionProposal(
            proposal_id=f"{context.step_id}:proposal", run_id=context.run_id, step_id=context.step_id,
            step=context.step, actor_id=context.actor_id, action=action,
            based_on_revision=context.observation.state_revision,
            source=ProposalSource(kind="EXTERNAL", strategy=DESCRIPTOR.ref()), rationale=why,
            candidates_considered=len(context.candidates))


def create(config: dict[str, Any] | None, services: Any) -> ChecklistPlanner:
    cfg = config or {}
    return ChecklistPlanner(list(cfg.get("preference", [])), int(cfg.get("batch", 3)))
