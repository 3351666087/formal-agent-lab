"""Z3 planning strategy: receding-horizon shortest plan on the actor's belief state.

Each call computes the shortest action sequence (≤ horizon) from the belief state to the goal with the
bounded verifier, and proposes its first action. Plans are memoised by (model digest, belief digest) so
following a plan whose predictions keep matching the observations does not re-solve. When no plan exists
within the horizon, the planner falls back to a declared deterministic choice among candidates that are
applicable on the belief state, and says so in the rationale.
"""

from __future__ import annotations

from typing import Any

from formal_lab_contracts import (
    ActionProposal,
    CheckQuery,
    GroundAction,
    ModelPackage,
    PlanningContext,
    PluginDescriptor,
    ProposalSource,
    digest_of,
)
from formal_lab_contracts import capabilities as caps
from formal_lab_contracts.errors import InvalidInput, NonRetryableFailure
from formal_lab_model.belief import belief_from_observation

from .verifier import Z3Verifier, compile_package

PLANNER_ID = "formal-lab.planner.z3-bounded"
PLANNER_VERSION = "1.0.0"

CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "goal_property": {"type": "string", "description": "goal property id (default: first goal in the model)"},
        "horizon": {"type": "integer", "minimum": 1, "maximum": 60, "default": 16},
        "timeout_ms": {"type": "integer", "minimum": 10, "default": 8000},
        "fallback_order": {"type": "array", "items": {"type": "string"},
                           "description": "action types preferred when no plan exists (in order)"},
    },
    "additionalProperties": False,
}

DESCRIPTOR = PluginDescriptor(
    plugin_id=PLANNER_ID,
    version=PLANNER_VERSION,
    interface="PLANNER",
    capabilities=[{"id": caps.PLAN_BOUNDED_SEARCH}, {"id": caps.PROFILE_DETERMINISTIC_FINITE_V1}],
    semantic_profiles=["deterministic_finite_v1"],
    config_schema=CONFIG_SCHEMA,
    entrypoint="formal_lab_solver_z3.planner:create",
    ui={"label": "Z3 bounded planner", "category": "symbolic",
        "description": "Shortest plan to the goal within a horizon (Z3 BMC), receding horizon"},
    license="z3: MIT; adapter: UNLICENSED (owner has not chosen a license yet)",
    source="formal-lab-solver-z3",
)

_PLAN_CACHE: dict[tuple[str, str, str], list[tuple[str, GroundAction]]] = {}


class Z3BoundedPlanner:
    descriptor = DESCRIPTOR

    def __init__(self, package: ModelPackage, config: dict[str, Any] | None = None):
        cfg = {"horizon": 16, "timeout_ms": 8000, **(config or {})}
        unknown = set(cfg) - set(CONFIG_SCHEMA["properties"])
        if unknown:
            raise InvalidInput(f"unknown planner config keys {sorted(unknown)}")
        self.package = package
        self.checked, self.zm, self.interp = compile_package(package)
        goals = [pid for pid, p in self.checked.properties.items() if p.kind == "goal"]
        self.goal = cfg.get("goal_property") or (goals[0] if goals else None)
        if self.goal is None or self.goal not in self.checked.properties:
            raise InvalidInput(f"planner needs a goal property (model goals: {goals})")
        self.horizon = int(cfg["horizon"])
        self.timeout_ms = int(cfg["timeout_ms"])
        self.fallback_order = list(cfg.get("fallback_order") or [])
        self.verifier = Z3Verifier(default_timeout_ms=self.timeout_ms)

    def _plan(self, belief_state: dict) -> tuple[list[tuple[str, GroundAction]] | None, str]:
        key = (self.package.digest.value, self.goal, digest_of(belief_state).value)
        if key in _PLAN_CACHE:
            return _PLAN_CACHE[key], "cached plan"
        result = self.verifier.check(
            self.package,
            CheckQuery(kind="GOAL_REACHABILITY", property_id=self.goal, initial_state="GIVEN_STATE",
                       bound={"max_steps": self.horizon, "timeout_ms": self.timeout_ms}),
            state=belief_state,
        )
        if result.verdict != "WITNESS" or result.witness is None:
            return None, f"{result.verdict}: {result.explanation}"
        steps = result.witness.steps
        plan = [(digest_of(steps[i].state).value, steps[i + 1].action) for i in range(len(steps) - 1)]
        # memoise every suffix: if later observations match the predicted states, no re-solve is needed
        for i in range(len(plan)):
            _PLAN_CACHE[(self.package.digest.value, self.goal, plan[i][0])] = plan[i:]
        if len(_PLAN_CACHE) > 5000:
            _PLAN_CACHE.clear()
        return plan, f"new plan of {len(plan)} step(s) ({result.stats.elapsed_ms:.0f} ms)"

    def propose(self, context: PlanningContext) -> ActionProposal:
        belief = belief_from_observation(context.observation, self.checked)
        plan, note = self._plan(belief.state)
        source = ProposalSource(kind="SYMBOLIC", strategy=self.descriptor.ref())
        if plan:
            action = plan[0][1]
            rationale = f"Z3 {note}; goal {self.goal!r} reachable in {len(plan)} step(s) from the belief state"
        else:
            if self.interp.holds(self.goal, belief.state):
                rationale_prefix = f"goal {self.goal!r} already holds on the belief state"
            else:
                rationale_prefix = f"no plan within horizon {self.horizon} ({note})"
            candidates = [c for c in context.candidates if c.belief_applicability == "APPLICABLE"]
            if not candidates:
                raise NonRetryableFailure("no applicable candidate action on the belief state")
            order = {t: i for i, t in enumerate(self.fallback_order)}
            chosen = min(candidates, key=lambda c: (order.get(c.action.action_type, len(order)),
                                                    context.candidates.index(c)))
            action = chosen.action
            rationale = f"{rationale_prefix}; fallback to first applicable candidate by declared order"
        if belief.unknown_paths:
            rationale += f"; planned with last-known values for {len(belief.unknown_paths)} unknown location(s)"
        return ActionProposal(
            proposal_id=f"{context.step_id}:proposal",
            run_id=context.run_id,
            step_id=context.step_id,
            step=context.step,
            actor_id=context.actor_id,
            action=action,
            based_on_revision=context.observation.state_revision,
            source=source,
            rationale=rationale,
            candidates_considered=len(context.candidates),
        )


def create(config: dict[str, Any] | None, services: Any) -> Z3BoundedPlanner:
    return Z3BoundedPlanner(services.pinned_model(), config)
