"""Deterministic dispatch rule for the scheduling example (Planner interface, source RULE).

Rule (earliest due date with priority and shortest processing time as tie-breaks):
1. Among `assign` candidates judged APPLICABLE on the belief state, pick the operation with the best
   (queue priority, order due date, processing time, name) and its first listed eligible machine.
2. Otherwise resume a paused machine if that is applicable.
3. Otherwise advance logical time if applicable.
4. Otherwise (facts are stale, applicability UNKNOWN) probe deterministically: on odd steps try `advance`,
   on even steps try the next-ranked UNKNOWN `assign` (rotating by step) — the environment is the arbiter
   and rejects inapplicable actions.
"""

from __future__ import annotations

from typing import Any

from formal_lab_contracts import (
    ActionProposal,
    CandidateAction,
    ModelPackage,
    PlanningContext,
    PluginDescriptor,
    ProposalSource,
)
from formal_lab_contracts import capabilities as caps
from formal_lab_contracts.errors import NonRetryableFailure
from formal_lab_model import check_model
from formal_lab_model.belief import belief_from_observation

PLANNER_ID = "formal-lab.example.scheduling.edd-dispatch"
LEVEL_RANK = {"high": 0, "normal": 1, "low": 2}

DESCRIPTOR = PluginDescriptor(
    plugin_id=PLANNER_ID,
    version="1.0.0",
    interface="PLANNER",
    capabilities=[{"id": caps.PLAN_RULE}],
    semantic_profiles=["deterministic_finite_v1"],
    config_schema={"type": "object", "properties": {}, "additionalProperties": False},
    entrypoint="formal_lab_example_scheduling.rule_planner:create",
    ui={"label": "EDD 规则调度", "category": "rule",
        "description": "Earliest-due-date dispatch with priority and SPT tie-breaks (deterministic)"},
    license="Apache-2.0",
    source="formal-lab-example-scheduling",
)


class EddDispatchPlanner:
    descriptor = DESCRIPTOR

    def __init__(self, package: ModelPackage):
        self.model = check_model(package.ir)
        self.due = self.model.families["due"].table
        self.order_of = self.model.families["order_of"].table

    def _op_key(self, cand: CandidateAction, state: dict[str, Any]) -> tuple:
        op = str(cand.action.params["op"])
        order = self.order_of[f"order_of[{op}]"]
        return (LEVEL_RANK.get(str(state.get(f"priority[{order}]", "normal")), 1), self.due[f"due[{order}]"],
                state.get(f"proc_time[{op}]", 0), op, list(cand.action.params.values()))

    def propose(self, context: PlanningContext) -> ActionProposal:
        belief = belief_from_observation(context.observation, self.model)
        by = lambda kind, verdict: [c for c in context.candidates  # noqa: E731
                                    if c.action.action_type == kind and c.belief_applicability == verdict]
        choice: CandidateAction | None = None
        reason = ""
        if assigns := by("assign", "APPLICABLE"):
            choice = min(assigns, key=lambda c: self._op_key(c, belief.state))
            reason = "EDD: earliest-due applicable operation (priority, due, processing time)"
        elif resumes := by("resume", "APPLICABLE"):
            choice, reason = resumes[0], "resume a paused machine"
        elif advances := by("advance", "APPLICABLE"):
            choice, reason = advances[0], "nothing assignable: advance logical time"
        elif (assigns_unknown := by("assign", "UNKNOWN")) or by("advance", "UNKNOWN"):
            advances_unknown = by("advance", "UNKNOWN")
            if advances_unknown and (context.step % 2 == 1 or not assigns_unknown):
                choice, reason = advances_unknown[0], "facts are stale: probe by advancing time (odd step)"
            else:
                ranked = sorted(assigns_unknown, key=lambda c: self._op_key(c, belief.state))
                choice = ranked[(context.step // 2) % len(ranked)]
                reason = "facts are stale: probe the next-ranked assignment whose applicability is UNKNOWN"
        if choice is None:
            raise NonRetryableFailure("no candidate action for the dispatch rule")
        return ActionProposal(
            proposal_id=f"{context.step_id}:proposal",
            run_id=context.run_id,
            step_id=context.step_id,
            step=context.step,
            actor_id=context.actor_id,
            action=choice.action,
            based_on_revision=context.observation.state_revision,
            source=ProposalSource(kind="RULE", strategy=DESCRIPTOR.ref()),
            rationale=reason,
            candidates_considered=len(context.candidates),
        )


def create(config: dict[str, Any] | None, services: Any) -> EddDispatchPlanner:
    return EddDispatchPlanner(services.pinned_model())
