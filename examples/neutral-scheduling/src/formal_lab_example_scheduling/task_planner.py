"""Task-plan strategy for production scheduling (P2-040 … P2-043).

Orders are decomposed into one task per operation; a task depends on its predecessor operations (the model's
`pred` table) and is done when `phase[op] = done` holds on the belief. The *order* in which ready tasks are
dispatched comes from one of three generators, all producing the same typed `TaskPlan` and running through the same
code path:

- rule      — earliest due date (queue priority, due, processing time, name), dependencies respected; once the
              budget runs short, orders closest to completion (fewest open operations) come first;
- symbolic  — the order in which a Z3 plan (cost-optimal for the scenario objective, else shortest) starts the
              operations; operations the plan does not reach are appended by the rule;
- model     — a language model orders the tasks (JSON schema); the answer must be a permutation that respects the
              dependencies, otherwise it is recorded as a format / business failure and the rule order is used.

Every step: task statuses are updated from the belief; the plan is revised (new version with its trigger) on an
effect difference, a rejected action, another participant starting a task of this plan (RESOURCE_CHANGE), a task
finishing out of the expected order (NEW_OBSERVATION), the budget becoming short (BUDGET, once: fewer than two
steps left per open task) or a REPLAN rule; then the
first ready task is dispatched to its first eligible machine (or time advances / a stale task is probed).
The plan, its generator record and the RNG state are the planner checkpoint (restore = continue exactly).

No-progress handling (P2-047). With delayed observations the belief the engine hands over lags behind the world,
so the planner keeps its own *working state*: the freshest value seen per location (by `observed_at_step`, so the
answer to an observation request is not forgotten when the next, delayed observation repeats an older value),
overlaid with the model-predicted effects of its own applied actions (ranked just after the step they were applied
at, so any newer observation wins). A candidate is only dispatched when its precondition holds on the working state:
a task it started stays running even while the delayed belief still shows it idle, and a machine it learnt is busy
is not tried again. An action the world rejected is not proposed again until a newer observation of the locations
its precondition reads (its operation and predecessors, the occupancy of its machine's station, the operations
sharing its resources) shows a different value; after a rejection the planner asks for fresh observations of those
locations (when the environment answers requests). A revision that leaves the task order unchanged does not create
a new plan version. The working state, the pending prediction and the rejection memory are part of the checkpoint.
"""

from __future__ import annotations

import heapq
import random
from typing import Any

from formal_lab_contracts import (
    ActionProposal,
    CandidateAction,
    CheckQuery,
    ModelPackage,
    ModelUsage,
    PlanGenerator,
    PlannerCheckpoint,
    PlanningContext,
    PlanRef,
    PlanRevision,
    PluginDescriptor,
    ProposalSource,
    TaskNode,
    TaskPlan,
    TaskStatus,
    digest_of,
)
from formal_lab_contracts import capabilities as caps
from formal_lab_contracts.errors import FormalLabError, InvalidInput, NonRetryableFailure
from formal_lab_model import check_model
from formal_lab_model.belief import belief_from_observation
from formal_lab_model.interpreter import Interpreter

PLANNER_ID = "formal-lab.example.scheduling.task-planner"
LEVEL_RANK = {"high": 0, "normal": 1, "low": 2}

CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "generator": {"type": "string", "enum": ["rule", "symbolic", "model"], "default": "rule"},
        "client": {"type": "string", "enum": ["openai_compatible", "stub"], "default": "openai_compatible",
                   "description": "model generator: real endpoint or the labelled stub"},
        "model": {"type": "string"},
        "horizon": {"type": "integer", "minimum": 1, "maximum": 40, "default": 18},
        "timeout_ms": {"type": "integer", "minimum": 100, "default": 20000},
        "replan_on": {"type": "array", "items": {"type": "string", "enum": [
            "EFFECT_DIFFERENCE", "ACTION_REJECTED", "RESOURCE_CHANGE", "NEW_OBSERVATION", "BUDGET", "RULE"]},
            "default": ["EFFECT_DIFFERENCE", "ACTION_REJECTED", "RESOURCE_CHANGE", "NEW_OBSERVATION", "BUDGET",
                        "RULE"]},
    },
    "additionalProperties": False,
}

DESCRIPTOR = PluginDescriptor(
    plugin_id=PLANNER_ID, version="1.0.0", interface="PLANNER",
    capabilities=[{"id": caps.PLAN_TASK_PLAN}, {"id": caps.PLAN_CHECKPOINT}, {"id": caps.PLAN_RULE},
                  {"id": caps.PLAN_BOUNDED_SEARCH}, {"id": caps.PLAN_LLM}],
    requires=[{"id": caps.DRIVER_IR, "params": {"of": "driver"}}],
    semantic_profiles=["deterministic_finite_v1"], config_schema=CONFIG_SCHEMA,
    entrypoint="formal_lab_example_scheduling.task_planner:create",
    ui={"label": "任务计划调度（规则 / 符号 / 模型辅助）", "category": "plan",
        "description": "Order → operation tasks with dependencies; the task order comes from EDD, a Z3 plan or a "
                       "language model; checkpointed, revised on effect differences / conflicts / new observations"},
    license="Apache-2.0", source="formal-lab-example-scheduling")

ORDER_SCHEMA = {
    "type": "object",
    "properties": {"order": {"type": "array", "items": {"type": "string"}},
                   "rationale": {"type": "string"}},
    "required": ["order", "rationale"],
    "additionalProperties": False,
}
ORDER_PROMPT = (
    "You plan a production line. You receive the operations (tasks) that still have to run, with the order they "
    "belong to, its due time and queue priority, the processing time and the operations each depends on. Return "
    "all task ids in the order they should be started; a task must come after every task it depends on. Minimise "
    "late orders. Respond only with the JSON object requested."
)


class TaskPlanner:
    descriptor = DESCRIPTOR

    def __init__(self, package: ModelPackage, config: dict[str, Any], services: Any):
        cfg = {"generator": "rule", "horizon": 18, "timeout_ms": 20000,
               "replan_on": CONFIG_SCHEMA["properties"]["replan_on"]["default"], **config}
        unknown = set(cfg) - set(CONFIG_SCHEMA["properties"])
        if unknown:
            raise InvalidInput(f"unknown task-planner config keys {sorted(unknown)}")
        self.package = package
        self.cfg = cfg
        self.services = services
        self.model = check_model(package.ir)
        fam = self.model.families
        self.ops = list(self.model.domains["ops"])
        self.order_of = {op: fam["order_of"].table[f"order_of[{op}]"] for op in self.ops}
        self.due = {o: fam["due"].table[f"due[{o}]"] for o in self.model.domains["orders"]}
        self.preds = {op: [p for p in self.ops if fam["pred"].table.get(f"pred[{op},{p}]")] for op in self.ops}
        self.plan: TaskPlan | None = None
        self.generator_note = ""
        self.rng = random.Random(0)
        self.actor_id = ""
        self.last_calls: list[Any] = []
        self.call_records: list[dict[str, Any]] = []
        self._client = None
        self.rejected: dict[str, str] = {}  # action key → digest of the facts it depended on when it was rejected
        self.budget_mode = False  # entered once the budget is short (BUDGET trigger fires on entering it)
        self.pending: list[Any] = []  # [action key, predicted writes, step] of the last proposal
        self.interp = Interpreter(self.model)
        self.last_evidence: dict[str, str] = {}  # action key → evidence digest at the time it was proposed
        self.fresh: dict[str, list[Any]] = {}  # path → [value, observed_at_step], the freshest observation seen
        self.station_of = {m: fam["station_of"].table[f"station_of[{m}]"] for m in self.model.domains["machines"]}
        resources = self.model.domains["resources"]
        self.needs = {op: {res for res in resources if fam["needs"].table.get(f"needs[{op},{res}]")}
                      for op in self.ops}

    # ------------------------------------------------------------------ checkpoint
    def checkpoint(self) -> PlannerCheckpoint:
        v, internal, g = self.rng.getstate()
        cp = PlannerCheckpoint(actor_id=self.actor_id, planner=self.descriptor.ref(), step=0, plan=self.plan,
                               progress={"generator": self.cfg["generator"], "note": self.generator_note,
                                         "rejected": self.rejected, "pending": self.pending,
                                         "budget_mode": self.budget_mode,
                                         "last_evidence": self.last_evidence, "fresh": self.fresh},
                               rng_state=[v, list(internal), g])
        return cp.model_copy(update={"digest": digest_of(cp.model_dump(mode="json", exclude={"digest"}))})

    def restore(self, checkpoint: PlannerCheckpoint) -> None:
        self.actor_id = checkpoint.actor_id
        self.plan = checkpoint.plan
        self.generator_note = checkpoint.progress.get("note", "")
        self.rejected = dict(checkpoint.progress.get("rejected", {}))
        self.pending = list(checkpoint.progress.get("pending", []))
        self.budget_mode = bool(checkpoint.progress.get("budget_mode", False))
        self.last_evidence = dict(checkpoint.progress.get("last_evidence", {}))
        self.fresh = {k: list(v) for k, v in checkpoint.progress.get("fresh", {}).items()}
        if checkpoint.rng_state:
            self.rng.setstate((checkpoint.rng_state[0], tuple(checkpoint.rng_state[1]), checkpoint.rng_state[2]))

    def current_plan(self) -> TaskPlan | None:
        return self.plan

    # ------------------------------------------------------------------ generators
    def _edd_key(self, op: str, state: dict[str, Any]) -> tuple:
        order = self.order_of[op]
        return (LEVEL_RANK.get(str(state.get(f"priority[{order}]", "normal")), 1), self.due[order],
                state.get(f"proc_time[{op}]", 0), op)

    def _topological(self, ops: list[str], rank: dict[str, Any]) -> list[str]:
        pending = set(ops)
        indeg = {op: sum(1 for p in self.preds[op] if p in pending) for op in ops}
        heap = [(rank[op], op) for op in ops if indeg[op] == 0]
        heapq.heapify(heap)
        out = []
        while heap:
            _, op = heapq.heappop(heap)
            out.append(op)
            for nxt in ops:
                if op in self.preds[nxt] and nxt in pending:
                    indeg[nxt] -= 1
                    if indeg[nxt] == 0:
                        heapq.heappush(heap, (rank[nxt], nxt))
            pending.discard(op)
        return out

    def _rule_order(self, open_ops: list[str], state: dict[str, Any]) -> list[str]:
        if not self.budget_mode:
            return self._topological(open_ops, {op: self._edd_key(op, state) for op in open_ops})
        left = {o: sum(1 for op in open_ops if self.order_of[op] == o) for o in self.due}
        return self._topological(open_ops, {op: (left[self.order_of[op]], *self._edd_key(op, state))
                                            for op in open_ops})

    def _symbolic_order(self, open_ops: list[str], state: dict[str, Any], context: PlanningContext) -> list[str]:
        from formal_lab_solver_z3.verifier import Z3Verifier

        goal = context.goal or "all_done"
        horizon = min(int(self.cfg["horizon"]), max(1, (context.budget.max_steps or 60) - context.usage.steps))
        if context.objective is not None:
            objective = context.objective.model_copy(update={"horizon": min(context.objective.horizon, horizon),
                                                             "goal_property": goal})
            query = CheckQuery(kind="OPTIMIZE_OBJECTIVE", objective=objective, initial_state="GIVEN_STATE",
                               bound={"max_steps": objective.horizon, "timeout_ms": self.cfg["timeout_ms"]})
        else:
            query = CheckQuery(kind="GOAL_REACHABILITY", property_id=goal, initial_state="GIVEN_STATE",
                               bound={"max_steps": horizon, "timeout_ms": self.cfg["timeout_ms"]})
        res = Z3Verifier(default_timeout_ms=int(self.cfg["timeout_ms"])).check(self.package, query, state=state)
        started = []
        if res.witness is not None:
            for s in res.witness.steps[1:]:
                if s.action and s.action.action_type == "assign" and s.action.params["op"] in open_ops \
                        and s.action.params["op"] not in started:
                    started.append(str(s.action.params["op"]))
        self.generator_note = f"Z3 {res.query.kind.value}: {res.verdict} ({res.explanation})"[:300]
        rest = [op for op in self._rule_order(open_ops, state) if op not in started]
        return started + rest

    def _model_order(self, open_ops: list[str], state: dict[str, Any], context: PlanningContext) -> tuple[list[str],
                                                                                                    ModelUsage]:
        from formal_lab_strategies.llm_planner import usage_of
        from formal_lab_strategies.model_clients import StubModelClient

        if self._client is None:
            if self.cfg.get("client") == "stub":
                self._client = StubModelClient()
            else:
                from formal_lab_strategies.llm_planner import client_from_settings

                self._client = client_from_settings({"client": "openai_compatible", "model": self.cfg.get("model")},
                                                    self.services)
        start = len(self._client.calls)
        rule = self._rule_order(open_ops, state)
        tasks = [{"id": op, "order": self.order_of[op], "due": self.due[self.order_of[op]],
                  "priority": state.get(f"priority[{self.order_of[op]}]", "normal"),
                  "processing_time": state.get(f"proc_time[{op}]"), "depends_on": self.preds[op]} for op in rule]
        order: list[str] = rule
        try:
            resp = self._client.complete_json(system=ORDER_PROMPT, user="Tasks (JSON):\n" + str(tasks),
                                              schema=ORDER_SCHEMA, schema_name="order_tasks",
                                              payload={"tasks": tasks})
            proposed = [str(x) for x in resp.content.get("order", [])]
            if sorted(proposed) == sorted(open_ops) and all(
                    proposed.index(p) < proposed.index(op) for op in proposed for p in self.preds[op] if p in proposed):
                order = proposed
                self.generator_note = f"model order: {resp.content.get('rationale', '')}"[:300]
            else:
                self.generator_note = ("model answer rejected (not a dependency-respecting permutation of the open "
                                       "tasks); rule order used")
        except FormalLabError as exc:
            self.generator_note = f"model unavailable ({exc.message[:200]}); rule order used"
        calls = self._client.calls[start:]
        self.call_records = [c.as_record() for c in calls]
        return order, usage_of(calls)

    # ------------------------------------------------------------------ planning
    def _statuses(self, state: dict[str, Any]) -> dict[str, TaskStatus]:
        out = {}
        for op in self.ops:
            phase = state.get(f"phase[{op}]")
            out[op] = TaskStatus.DONE if phase == "done" else (TaskStatus.IN_PROGRESS if phase == "running"
                                                                else TaskStatus.PENDING)
        return out

    def _trigger(self, context: PlanningContext, statuses: dict[str, TaskStatus]) -> tuple[str, str] | None:
        if self.plan is None:
            return "INITIAL", "first plan"
        allowed = set(self.cfg["replan_on"])
        last = context.last_outcome
        checks = []
        if context.replan_requested:
            checks.append(("RULE", context.replan_requested))
        if last is not None and last.effect_comparison is not None and \
                str(last.effect_comparison.verdict) == "DIFFERENT":
            checks.append(("EFFECT_DIFFERENCE", "observed effects differ from the model prediction"))
        if last is not None and str(last.status) == "REJECTED":
            checks.append(("ACTION_REJECTED", f"{last.action.action_type} rejected: {last.result.get('reason')}"))
        expected = {n.node_id: n.status for n in self.plan.nodes}
        mine = {n.node_id for n in self.plan.nodes if n.attempts > 0}
        taken = [op for op, st in statuses.items() if st is not TaskStatus.PENDING and op in expected
                 and expected[op] is TaskStatus.PENDING and op not in mine]
        if taken and len(context.participants) > 1:
            checks.append(("RESOURCE_CHANGE", f"tasks started by another participant: {taken}"))
        elif taken:
            checks.append(("NEW_OBSERVATION", f"tasks observed in a state the plan did not expect: {taken}"))
        remaining = sum(1 for st in statuses.values() if st is not TaskStatus.DONE)
        left = (context.budget.max_steps or 10**6) - context.usage.steps
        if remaining * 2 > left and not self.budget_mode and "BUDGET" in allowed:
            self.budget_mode = True
            checks.append(("BUDGET", f"{remaining} open task(s) with {left} step(s) left: orders closest to "
                                     "completion first"))
        return next(((t, d) for t, d in checks if t in allowed), None)

    def _replan(self, context: PlanningContext, state: dict[str, Any], statuses: dict[str, TaskStatus],
                trigger: str, detail: str) -> ModelUsage:
        open_ops = [op for op in self.ops if statuses[op] is not TaskStatus.DONE]
        usage = ModelUsage()
        gen = self.cfg["generator"]
        if gen == "symbolic":
            order = self._symbolic_order(open_ops, state, context)
        elif gen == "model":
            order, usage = self._model_order(open_ops, state, context)
        else:
            order = self._rule_order(open_ops, state)
            self.generator_note = "earliest due date, dependencies respected"
        done = [op for op in self.ops if statuses[op] is TaskStatus.DONE]
        if self.plan is not None and [n.node_id for n in self.plan.nodes] == order + done:
            return usage  # re-validated: the task order did not change, no new version
        attempts = {n.node_id: n.attempts for n in self.plan.nodes} if self.plan else {}
        nodes = [TaskNode(node_id=op, label=f"{op} ({self.order_of[op]}, due {self.due[self.order_of[op]]})",
                          depends_on=list(self.preds[op]), status=statuses[op], attempts=attempts.get(op, 0),
                          done_when={"op": "eq", "args": [{"op": "var", "name": "phase",
                                                           "index": [{"op": "const", "value": op}]},
                                                          {"op": "const", "value": "done"}]})
                 for op in order + done]
        kind = {"rule": "RULE", "symbolic": "SYMBOLIC", "model": "LLM_STUB" if self.cfg.get("client") == "stub"
                else "LLM"}[gen]
        self.plan = TaskPlan(
            plan_id=f"{context.run_id}:{context.actor_id}:tasks", actor_id=context.actor_id,
            version=(self.plan.version + 1) if self.plan else 1,
            generator=PlanGenerator(kind=kind, strategy=self.descriptor.ref(), method=gen,
                                    model=self._client.model if self._client is not None else None),
            created_at_step=context.step, nodes=nodes, cursor=None,
            revision=PlanRevision(trigger=trigger, detail=f"{detail}; {self.generator_note}"[:500],
                                  at_step=context.step),
            parent_version=self.plan.version if self.plan else None,
            assumptions_digest=context.assumptions.digest.value if context.assumptions else None)
        return usage

    @staticmethod
    def _key(action) -> str:
        return f"{action.action_type}:{sorted(action.params.items())}"

    def _related_paths(self, action) -> list[str]:
        """Locations an assignment's precondition reads: its operation and predecessors, the occupancy of every
        machine on its machine's station, the phases of operations sharing its resources and the machine's pause."""
        op, m = action.params.get("op"), action.params.get("m")
        if action.action_type != "assign" or op not in self.preds or m not in self.station_of:
            return []
        mates = [mm for mm, st in self.station_of.items() if st == self.station_of[m]]
        sharing = [o for o in self.ops if self.needs[o] & self.needs[op]]
        paths = [f"phase[{p}]" for p in [op, *self.preds[op], *sharing]]
        paths += [f"on[{o},{mm}]" for o in self.ops for mm in mates] + [f"paused[{m}]"]
        return list(dict.fromkeys(paths))

    def _ground(self, action):
        return self.interp.ground(action.action_type, dict(action.params))

    def _holds(self, action, working: dict[str, Any]) -> bool:
        try:
            return self.interp.precondition(self._ground(action), working)
        except KeyError:
            return False

    def _absorb(self, facts) -> None:
        for f in facts:
            cur = self.fresh.get(f.path)
            if cur is None or f.observed_at_step >= cur[1]:
                self.fresh[f.path] = [f.value, f.observed_at_step]

    def _evidence(self, action, whole: str) -> str:
        """What an action's applicability rests on: the freshest known values of the locations its precondition
        reads (or, for actions without such a list, the whole observation)."""
        paths = self._related_paths(action)
        return digest_of([(p, (self.fresh.get(p) or [None])[0]) for p in paths]).value if paths else whole

    def propose(self, context: PlanningContext) -> ActionProposal:
        self.actor_id = context.actor_id
        self.call_records = []
        belief = belief_from_observation(context.observation, self.model)
        state = belief.state
        whole = digest_of(sorted((f.path, f.value) for f in context.observation.facts)).value
        last = context.last_outcome
        if last is not None and str(last.status) == "REJECTED":
            key = self._key(last.action)
            self.rejected[key] = self.last_evidence.get(key, self._evidence(last.action, whole))
        self._absorb(context.observation.facts)
        if last is not None and str(last.status) == "APPLIED" and self.pending \
                and self.pending[0] == self._key(last.action):
            for path, value in self.pending[1].items():  # my own effect, unless a newer observation says otherwise
                cur = self.fresh.get(path)
                if cur is None or cur[1] <= self.pending[2]:
                    self.fresh[path] = [value, self.pending[2] + 1]
        self.pending = []
        working = {**state, **{p: v for p, (v, _) in self.fresh.items() if p in state}}
        cand_by_key = {self._key(c.action): c for c in context.candidates}
        # new information about the facts a rejected action depends on: it may be tried again
        self.rejected = {k: d for k, d in self.rejected.items()
                         if k in cand_by_key and self._evidence(cand_by_key[k].action, whole) == d}
        request = None
        if last is not None and str(last.status) == "REJECTED" and context.observation_request_allowed \
                and last.action.action_type == "assign":
            from formal_lab_contracts import ObservationRequest

            request = ObservationRequest(paths=self._related_paths(last.action),
                                         reason=f"{last.action.action_type} was rejected on a possibly stale belief")
        statuses = self._statuses(working)
        usage = ModelUsage()
        trigger = self._trigger(context, statuses)
        if trigger is not None:
            usage = self._replan(context, working, statuses, *trigger)
        assert self.plan is not None
        nodes = [n.model_copy(update={"status": statuses[n.node_id]}) for n in self.plan.nodes]
        done = {n.node_id for n in nodes if n.status is TaskStatus.DONE}
        ready = [n for n in nodes if n.status is TaskStatus.PENDING and all(d in done for d in n.depends_on)]
        cands = {(c.action.action_type, tuple(sorted(c.action.params.items()))): c for c in context.candidates}
        choice: CandidateAction | None = None
        node_id = None
        reason = ""
        blocked = set(self.rejected)

        def feasible(c: CandidateAction) -> bool:
            return str(c.belief_applicability) in ("APPLICABLE", "UNKNOWN") and self._key(c.action) not in blocked \
                and self._holds(c.action, working)

        rank = lambda c: 0 if str(c.belief_applicability) == "APPLICABLE" else 1  # noqa: E731
        for n in ready:
            assigns = sorted((c for c in context.candidates if c.action.action_type == "assign"
                              and c.action.params.get("op") == n.node_id and feasible(c)), key=rank)
            if assigns:
                choice, node_id = assigns[0], n.node_id
                reason = (f"task {n.node_id} is next ready in plan v{self.plan.version}" if rank(assigns[0]) == 0 else
                          f"task {n.node_id} is next ready in plan v{self.plan.version}; its machine is free on the "
                          "working state (facts stale)")
                break
        if choice is None:
            resumes = [c for c in context.candidates if c.action.action_type == "resume" and feasible(c)]
            advance = cands.get(("advance", ()))
            if resumes:
                choice, reason = resumes[0], "resume a paused machine"
            elif advance is not None and feasible(advance):
                choice, reason = advance, "no ready task can start now: advance time"
            else:
                probes = [c for c in context.candidates if c.action.action_type == "assign"
                          and str(c.belief_applicability) == "UNKNOWN" and self._key(c.action) not in blocked
                          and c.action.params.get("op") in {n.node_id for n in ready}]
                if probes:
                    choice, node_id = probes[0], str(probes[0].action.params["op"])
                    reason = "working state is out of date: probe the next ready task whose applicability is UNKNOWN"
                elif advance is not None and str(advance.belief_applicability) in ("APPLICABLE", "UNKNOWN"):
                    choice, reason = advance, "working state is out of date: probe by advancing time"
        if choice is None:
            raise NonRetryableFailure("no action for the task plan")
        self.last_evidence = {self._key(choice.action): self._evidence(choice.action, whole)}
        predicted = self.interp.step(self._ground(choice.action), working)
        self.pending = [self._key(choice.action), dict(predicted.writes) if predicted.applicable else {}, context.step]
        if node_id is not None:
            nodes = [n.model_copy(update={"attempts": n.attempts + 1, "status": TaskStatus.IN_PROGRESS})
                     if n.node_id == node_id else n for n in nodes]
        self.plan = self.plan.model_copy(update={"nodes": nodes, "cursor": node_id,
                                                 "status": "COMPLETED" if len(done) == len(nodes) else "ACTIVE"})
        progress = self.plan.progress()
        return ActionProposal(
            proposal_id=f"{context.step_id}:proposal", run_id=context.run_id, step_id=context.step_id,
            step=context.step, actor_id=context.actor_id, action=choice.action,
            based_on_revision=context.observation.state_revision,
            source=ProposalSource(kind=self.plan.generator.kind, strategy=self.descriptor.ref(),
                                  model=self.plan.generator.model,
                                  model_call_ids=[r["call_id"] for r in self.call_records]),
            rationale=f"{reason}; tasks {progress}" + (f"; {len(blocked)} rejected action(s) not retried until newer "
                                                        "observations of what they depend on differ" if blocked
                                                        else ""),
            candidates_considered=len(context.candidates),
            plan=PlanRef(plan_id=self.plan.plan_id, version=self.plan.version, node_id=node_id), usage=usage,
            observation_request=request)


def create(config: dict[str, Any] | None, services: Any) -> TaskPlanner:
    return TaskPlanner(services.pinned_model(), dict(config or {}), services)
