"""Z3 planning strategy: receding horizon on the actor's belief, with a checkpointed task plan.

Modes
- shortest (default, phase-1 behaviour): the shortest action sequence (≤ horizon) from the belief state to the goal
  (GOAL_REACHABILITY witness);
- cost: the lexicographically cheapest sequence for the scenario's (or the configured) ObjectiveSpec
  (OPTIMIZE_OBJECTIVE); a timeout still yields the best plan found, labelled as not proven optimal.

The current plan is a TaskPlan (one node per action, each with the state it expects before running) kept in the
planner checkpoint (P2-040 / P2-041): a fresh process restores it and continues exactly as an uninterrupted run.
Each call follows the plan while the belief equals one of its expected states; otherwise the plan is revised —
the new version records why (NEW_OBSERVATION, RESOURCE_CHANGE when another participant changed the state,
EFFECT_DIFFERENCE, ACTION_REJECTED, BUDGET, RULE) (P2-042).

Solver answers are memoised in a bounded LRU cache whose key covers everything the answer depends on (P2-028):
model digest, driver, mode, goal / objective digest, effective horizon (after the budget cap), belief-state digest
and the assumption set. Definitive answers (plan found / none within the bound) are cached; a timed-out search is
cached only under its timeout. Plans computed from last-known or assumed values are labelled ASSUMPTION_BASED.
With `request_observations`, a plan whose next action is UNKNOWN on the belief first asks the environment for
the locations that would settle it (P2-027).
"""

from __future__ import annotations

import random
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from formal_lab_contracts import (
    ActionProposal,
    CheckQuery,
    GroundAction,
    ModelPackage,
    ObjectiveSpec,
    PlannerCheckpoint,
    PlanningContext,
    PlanRef,
    PluginDescriptor,
    ProposalSource,
    TaskPlan,
    TaskStatus,
    digest_of,
)
from formal_lab_contracts import capabilities as caps
from formal_lab_contracts.errors import InvalidInput, NonRetryableFailure
from formal_lab_model.belief import belief_from_observation

from .verifier import Z3Verifier, compile_package

PLANNER_ID = "formal-lab.planner.z3-bounded"
PLANNER_VERSION = "1.1.0"

CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "mode": {"type": "string", "enum": ["shortest", "cost"], "default": "shortest",
                 "description": "shortest plan (phase 1) or cheapest plan for the objective"},
        "goal_property": {"type": "string", "description": "goal property id (default: the actor's goal)"},
        "objective": {"type": "object", "description": "cost mode: ObjectiveSpec (default: the scenario's)"},
        "horizon": {"type": "integer", "minimum": 1, "maximum": 60, "default": 16},
        "timeout_ms": {"type": "integer", "minimum": 10, "default": 8000},
        "fallback_order": {"type": "array", "items": {"type": "string"},
                           "description": "action types preferred when no plan exists (in order)"},
        "plan_memory": {"type": "boolean", "default": True,
                        "description": "follow the current plan while the belief matches it (ablation: false)"},
        "request_observations": {"type": "boolean", "default": False,
                                 "description": "ask for observations when the next action is UNKNOWN on the belief"},
        "cache_size": {"type": "integer", "minimum": 0, "maximum": 100000, "default": 2048},
    },
    "additionalProperties": False,
}

DESCRIPTOR = PluginDescriptor(
    plugin_id=PLANNER_ID,
    version=PLANNER_VERSION,
    interface="PLANNER",
    capabilities=[{"id": caps.PLAN_BOUNDED_SEARCH}, {"id": caps.PROFILE_DETERMINISTIC_FINITE_V1},
                  {"id": caps.PLAN_COST_OPTIMAL}, {"id": caps.PLAN_TASK_PLAN}, {"id": caps.PLAN_CHECKPOINT},
                  {"id": caps.PLAN_OBSERVATION_REQUESTS}],
    requires=[{"id": caps.DRIVER_IR, "params": {"of": "driver"}}],
    semantic_profiles=["deterministic_finite_v1"],
    config_schema=CONFIG_SCHEMA,
    entrypoint="formal_lab_solver_z3.planner:create",
    ui={"label": "Z3 bounded planner", "category": "symbolic",
        "description": "Shortest or cost-optimal plan to the goal within a horizon (Z3), receding horizon with a "
                       "checkpointed task plan"},
    license="Apache-2.0 (adapter); z3-solver: MIT",
    source="formal-lab-solver-z3",
)


@dataclass
class CacheEntry:
    kind: str  # "plan" | "none" (no plan within the bound) | "partial" (timed out; cached under its timeout)
    actions: list[GroundAction] = field(default_factory=list)
    states: list[str] = field(default_factory=list)  # digests of the states before each action (+ the final one)
    value: dict[str, Any] = field(default_factory=dict)
    note: str = ""


class PlanCache:
    """Bounded LRU of solver answers, shared by all planner instances of a process."""

    def __init__(self, capacity: int = 2048):
        self.capacity = capacity
        self.entries: OrderedDict[str, CacheEntry] = OrderedDict()
        self.hits = self.misses = self.evictions = 0

    def get(self, key: str) -> CacheEntry | None:
        entry = self.entries.get(key)
        if entry is None:
            self.misses += 1
            return None
        self.entries.move_to_end(key)
        self.hits += 1
        return entry

    def put(self, key: str, entry: CacheEntry) -> None:
        if self.capacity <= 0:
            return
        self.entries[key] = entry
        self.entries.move_to_end(key)
        while len(self.entries) > self.capacity:
            self.entries.popitem(last=False)
            self.evictions += 1

    def stats(self) -> dict[str, int]:
        return {"entries": len(self.entries), "capacity": self.capacity, "hits": self.hits, "misses": self.misses,
                "evictions": self.evictions}


CACHE = PlanCache()


def cache_key(**parts: Any) -> str:
    return digest_of(parts).value


class Z3BoundedPlanner:
    descriptor = DESCRIPTOR

    def __init__(self, package: ModelPackage, config: dict[str, Any] | None = None):
        cfg = {"horizon": 16, "timeout_ms": 8000, "mode": "shortest", "plan_memory": True,
               "request_observations": False, **(config or {})}
        unknown = set(cfg) - set(CONFIG_SCHEMA["properties"])
        if unknown:
            raise InvalidInput(f"unknown planner config keys {sorted(unknown)}")
        self.package = package
        self.checked, _, self.interp = compile_package(package)
        self.goals = [pid for pid, p in self.checked.properties.items() if p.kind == "goal"]
        self.goal_override = cfg.get("goal_property")
        if self.goal_override and self.goal_override not in self.checked.properties:
            raise InvalidInput(f"unknown goal property {self.goal_override!r}")
        self.mode = cfg["mode"]
        self.objective = ObjectiveSpec.model_validate(cfg["objective"]) if cfg.get("objective") else None
        self.horizon = int(cfg["horizon"])
        self.timeout_ms = int(cfg["timeout_ms"])
        self.fallback_order = list(cfg.get("fallback_order") or [])
        self.plan_memory = bool(cfg["plan_memory"])
        self.request_observations = bool(cfg["request_observations"])
        if "cache_size" in cfg:
            CACHE.capacity = int(cfg["cache_size"])
        self.verifier = Z3Verifier(default_timeout_ms=self.timeout_ms)
        self.plan: TaskPlan | None = None
        self.expected: list[str] = []  # state digest expected before node i (len = nodes + 1)
        self.rng = random.Random(0)
        self.solves = 0
        self.last_trigger: str | None = None
        self.actor_id = ""
        self.step = 0

    # ------------------------------------------------------------------ checkpoint / restore (P2-041)
    def checkpoint(self) -> PlannerCheckpoint:
        progress = {"expected": self.expected, "mode": self.mode, "solves": self.solves,
                    "last_trigger": self.last_trigger}
        cp = PlannerCheckpoint(actor_id=self.actor_id, planner=self.descriptor.ref(), step=self.step,
                               plan=self.plan, progress=progress, rng_state=_rng_state(self.rng),
                               cache_refs=[self.plan.assumptions_digest] if self.plan and self.plan.assumptions_digest
                               else [])
        return cp.model_copy(update={"digest": digest_of(cp.model_dump(mode="json", exclude={"digest"}))})

    def restore(self, checkpoint: PlannerCheckpoint) -> None:
        self.actor_id, self.step = checkpoint.actor_id, checkpoint.step
        self.plan = checkpoint.plan
        self.expected = list(checkpoint.progress.get("expected", []))
        self.solves = int(checkpoint.progress.get("solves", 0))
        self.last_trigger = checkpoint.progress.get("last_trigger")
        if checkpoint.rng_state:
            self.rng.setstate(_rng_tuple(checkpoint.rng_state))

    def current_plan(self) -> TaskPlan | None:
        return self.plan

    # ------------------------------------------------------------------ planning
    def _goal(self, context: PlanningContext) -> str:
        goal = self.goal_override or context.goal or (self.goals[0] if self.goals else None)
        if goal is None or goal not in self.checked.properties:
            raise InvalidInput(f"planner needs a goal property (model goals: {self.goals})")
        return goal

    def _horizon(self, context: PlanningContext) -> int:
        """Planning horizon capped by what the budgets still allow (steps)."""
        caps_ = [self.horizon]
        if context.budget.max_steps is not None:
            caps_.append(max(1, context.budget.max_steps - context.usage.steps))
        if context.actor_budget and context.actor_budget.max_steps is not None and context.actor_usage is not None:
            caps_.append(max(1, context.actor_budget.max_steps - context.actor_usage.steps))
        return min(caps_)

    def _solve(self, state: dict, goal: str, horizon: int, assumptions: str, objective: ObjectiveSpec | None
               ) -> tuple[CacheEntry, bool]:
        key = cache_key(model=self.package.digest.value, driver="formal-lab.driver.ir-finite", mode=self.mode,
                        goal=goal, objective=objective.model_dump(mode="json") if objective else None,
                        horizon=horizon, state=digest_of(state).value, assumptions=assumptions)
        hit = CACHE.get(key)
        if hit is not None:
            return hit, True
        self.solves += 1
        if self.mode == "cost" and objective is not None:
            spec = objective.model_copy(update={"horizon": min(objective.horizon, horizon), "goal_property": goal})
            res = self.verifier.check(self.package, CheckQuery(kind="OPTIMIZE_OBJECTIVE", objective=spec,
                                                               initial_state="GIVEN_STATE",
                                                               bound={"max_steps": spec.horizon,
                                                                      "timeout_ms": self.timeout_ms}), state=state)
            verdict = str(res.verdict)
            if verdict in ("OPTIMAL", "FEASIBLE") and res.witness is not None:
                entry = self._entry_from_witness(res.witness, "plan" if verdict == "OPTIMAL" else "partial")
                entry.value = {lv.level: lv.value for lv in res.optimization.levels}
                entry.note = (f"{verdict.lower()} plan ({res.optimization.solver_calls} solver calls, "
                              f"{res.stats.elapsed_ms:.0f} ms): "
                              + ", ".join(f"{lv.level}={lv.value}" for lv in res.optimization.levels))
            else:
                entry = CacheEntry(kind="none" if verdict == "NO_PLAN_WITHIN_HORIZON" else "partial",
                                   note=f"{verdict}: {res.explanation}")
        else:
            res = self.verifier.check(self.package, CheckQuery(kind="GOAL_REACHABILITY", property_id=goal,
                                                               initial_state="GIVEN_STATE",
                                                               bound={"max_steps": horizon,
                                                                      "timeout_ms": self.timeout_ms}), state=state)
            if res.verdict == "WITNESS" and res.witness is not None:
                entry = self._entry_from_witness(res.witness, "plan")
                entry.note = f"new plan of {len(entry.actions)} step(s) ({res.stats.elapsed_ms:.0f} ms)"
            else:
                entry = CacheEntry(kind="none" if res.verdict == "NO_WITNESS_WITHIN_BOUND" else "partial",
                                   note=f"{res.verdict}: {res.explanation}")
        if entry.kind != "partial":
            CACHE.put(key, entry)
        else:
            CACHE.put(cache_key(base=key, timeout=self.timeout_ms), entry)
        return entry, False

    @staticmethod
    def _entry_from_witness(witness, kind: str) -> CacheEntry:
        steps = witness.steps
        return CacheEntry(kind=kind, actions=[steps[i + 1].action for i in range(len(steps) - 1)],
                          states=[digest_of(s.state).value for s in steps])

    def _new_plan(self, context: PlanningContext, entry: CacheEntry, trigger: str, detail: str,
                  assumptions: str) -> None:
        from formal_lab_contracts import PlanGenerator, PlanRevision, TaskNode

        version = (self.plan.version + 1) if self.plan else 1
        nodes = [TaskNode(node_id=f"n{i + 1}", label=f"{a.action_type}({', '.join(f'{k}={v}' for k, v in a.params.items())})",
                          action=a, depends_on=[f"n{i}"] if i else [], status=TaskStatus.PENDING)
                 for i, a in enumerate(entry.actions)]
        self.plan = TaskPlan(
            plan_id=f"{context.run_id}:{context.actor_id}:z3", actor_id=context.actor_id, version=version,
            generator=PlanGenerator(kind="SYMBOLIC", strategy=self.descriptor.ref(),
                                    method="OPTIMIZE_OBJECTIVE" if self.mode == "cost" else "GOAL_REACHABILITY"),
            created_at_step=context.step, nodes=nodes, cursor=nodes[0].node_id if nodes else None,
            revision=PlanRevision(trigger=trigger, detail=detail, at_step=context.step),
            parent_version=self.plan.version if self.plan else None,
            objective_value=float(next(iter(entry.value.values()))) if entry.value else None,
            assumptions_digest=assumptions,
        )
        self.expected = list(entry.states)
        self.last_trigger = trigger

    def _classify(self, context: PlanningContext) -> tuple[str, str]:
        """Why the current plan no longer matches (P2-042)."""
        last = context.last_outcome
        if context.replan_requested:
            return "RULE", context.replan_requested
        if last is not None and str(last.status) == "REJECTED":
            return "ACTION_REJECTED", f"{last.action.action_type} was rejected: {last.result.get('reason')}"
        if last is not None and last.effect_comparison is not None and str(last.effect_comparison.verdict) == \
                "DIFFERENT":
            return "EFFECT_DIFFERENCE", "observed effects differ from the model prediction"
        if len(context.participants) > 1 and last is not None and str(last.status) == "APPLIED":
            return "RESOURCE_CHANGE", "the world changed by other participants' actions since the plan was made"
        return "NEW_OBSERVATION", "the belief differs from the state the plan expected"

    def propose(self, context: PlanningContext) -> ActionProposal:
        self.actor_id, self.step = context.actor_id, context.step
        belief = belief_from_observation(context.observation, self.checked)
        goal = self._goal(context)
        horizon = self._horizon(context)
        objective = self.objective or context.objective
        assumptions = context.assumptions.digest.value if context.assumptions else ""
        state_digest = digest_of(belief.state).value
        source = ProposalSource(kind="SYMBOLIC", strategy=self.descriptor.ref())
        note = ""
        action = None
        position = None
        if self.plan_memory and self.plan is not None and not context.replan_requested and state_digest in \
                self.expected[:-1]:
            position = self.expected.index(state_digest)  # follow the plan from the matching node
            note = "following plan"
        elif self.interp.holds(goal, belief.state):
            note = f"goal {goal!r} already holds on the belief state"
        else:
            entry, cached = self._solve(belief.state, goal, horizon, assumptions, objective)
            if entry.actions:
                trigger, detail = ("INITIAL", "first plan") if self.plan is None else self._classify(context)
                if len(entry.actions) > horizon:
                    trigger, detail = "BUDGET", f"remaining budget allows {horizon} step(s)"
                self._new_plan(context, entry, trigger, detail + ("; cached answer" if cached else ""), assumptions)
                position = 0
                note = ("cached " if cached else "") + entry.note
            else:
                note = f"no plan within horizon {horizon} ({entry.note})"
                if self.plan is not None:
                    self.plan = self.plan.model_copy(update={"status": "INVALIDATED"})
        plan_ref = None
        if position is not None and self.plan is not None:
            nodes = []
            for i, n in enumerate(self.plan.nodes):
                status = TaskStatus.DONE if i < position else (TaskStatus.IN_PROGRESS if i == position
                                                                else TaskStatus.PENDING)
                nodes.append(n.model_copy(update={"status": status,
                                                  "completed_at_step": n.completed_at_step or (context.step if i <
                                                                                               position else None)}))
            node = nodes[position]
            self.plan = self.plan.model_copy(update={"nodes": nodes, "cursor": node.node_id, "status": "ACTIVE"})
            action = node.action
            plan_ref = PlanRef(plan_id=self.plan.plan_id, version=self.plan.version, node_id=node.node_id)
            remaining = len(nodes) - position
            rationale = (f"Z3 {note}; goal {goal!r} reachable in {remaining} step(s) from the belief state"
                         if self.mode == "shortest" else
                         f"Z3 cost mode, {note}; {remaining} step(s) left in plan v{self.plan.version}")
        else:
            candidates = [c for c in context.candidates if c.belief_applicability == "APPLICABLE"]
            if not candidates:
                raise NonRetryableFailure("no applicable candidate action on the belief state")
            order = {t: i for i, t in enumerate(self.fallback_order)}
            chosen = min(candidates, key=lambda c: (order.get(c.action.action_type, len(order)),
                                                    context.candidates.index(c)))
            action = chosen.action
            rationale = f"{note}; fallback to first applicable candidate by declared order"
        if belief.unknown_paths:
            rationale += f"; planned with last-known values for {len(belief.unknown_paths)} unknown location(s)"
        request = None
        if self.request_observations and context.observation_request_allowed:
            cand = next((c for c in context.candidates if c.action == action), None)
            if cand is not None and str(cand.belief_applicability) == "UNKNOWN" and cand.observation_request:
                request = cand.observation_request
                rationale += f"; asking to observe {request.paths} first (applicability UNKNOWN)"
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
            plan=plan_ref,
            observation_request=request,
        )


def _rng_state(rng: random.Random) -> list[Any]:
    version, internal, gauss = rng.getstate()
    return [version, list(internal), gauss]


def _rng_tuple(state: list[Any]) -> tuple:
    return (state[0], tuple(state[1]), state[2])


def create(config: dict[str, Any] | None, services: Any) -> Z3BoundedPlanner:
    return Z3BoundedPlanner(services.pinned_model(), config)
