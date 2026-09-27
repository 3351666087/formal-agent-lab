"""Task plans for production scheduling (P2-040 … P2-043, P2-046, P2-047): orders decomposed into dependent tasks,
three generators through one code path, revisions with their trigger and parent, checkpoint / restore across a
process boundary, and no-progress behaviour under delayed observations."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest
from formal_lab_contracts import ScenarioManifest, TaskPlan
from formal_lab_contracts.errors import RetryableFailure
from formal_lab_example_scheduling.__main__ import EVALUATORS
from formal_lab_example_scheduling.scenarios import STRATEGIES, model_package, scenario, two_dispatchers
from formal_lab_example_scheduling.task_planner import TaskPlanner
from formal_lab_model import check_model
from formal_lab_model.interpreter import Interpreter
from formal_lab_runtime import default_registry, make_manifest, run_local
from formal_lab_runtime.local_runner import LocalRunState


@pytest.fixture(scope="module")
def reg():
    return default_registry()


@pytest.fixture(scope="module")
def pkg():
    return model_package()


def run(reg, pkg, sc, run_id="run_tp", **kw):
    m = make_manifest(run_id=run_id, project_id="p", scenario=sc, package=pkg, registry=reg, seed=sc.seed,
                      evaluators=EVALUATORS)
    return run_local(m, pkg, reg, **kw)


def of(res, kind: str) -> list:
    return [e for e in res.events if str(e.event_type) == kind]


def trajectory(res) -> list[tuple]:
    return [(e.logical_step, e.actor_id, json.dumps(e.payload["outcome"]["action"], sort_keys=True),
             e.payload["outcome"]["status"]) for e in of(res, "ACTION_OUTCOME")]


def cursors(res) -> list[tuple]:
    return [(e.logical_step, (e.payload["proposal"].get("plan") or {}).get("version"),
             (e.payload["proposal"].get("plan") or {}).get("node_id")) for e in of(res, "ACTION_PROPOSED")]


def test_orders_become_dependent_tasks_with_completion_criteria(reg, pkg):
    """P2-040: one task per operation, dependencies from the model's precedence table, `done_when` on the belief,
    a versioned plan and a cursor naming the dispatched task; dispatch order respects the dependencies."""
    res = run(reg, pkg, scenario("normal", pkg, seed=1, strategy=STRATEGIES["task-rule"]))
    assert res.status == "SUCCEEDED"
    first = TaskPlan.model_validate(of(res, "PLAN_UPDATED")[0].payload["plan"])
    model = check_model(pkg.ir)
    ops = list(model.domains["ops"])
    assert first.version == 1 and first.revision.trigger == "INITIAL" and first.parent_version is None
    assert sorted(n.node_id for n in first.nodes) == sorted(ops)
    pred = model.families["pred"].table
    for n in first.nodes:
        assert sorted(n.depends_on) == sorted(p for p in ops if pred.get(f"pred[{n.node_id},{p}]"))
        cond = n.done_when.model_dump(mode="json", exclude_none=True)
        assert cond["op"] == "eq" and cond["args"][1]["value"] == "done"
        assert Interpreter(model).evaluate(n.done_when, res.final_state)  # every task done at the end
    started: dict[str, int] = {}
    for e in of(res, "ACTION_PROPOSED"):
        p = e.payload["proposal"]
        if p["action"]["action_type"] == "assign":
            assert p["plan"]["node_id"] == p["action"]["params"]["op"]  # the cursor is the dispatched task
            started.setdefault(p["plan"]["node_id"], e.logical_step)
    assert set(started) == set(ops)
    assert all(started[d] < started[n.node_id] for n in first.nodes for d in n.depends_on)
    last = of(res, "PLANNER_CHECKPOINT")[-1].payload
    assert last["plan_version"] == first.version and sum(last["progress"].values()) == len(ops)


@pytest.mark.parametrize(("name", "kind"), [("task-rule", "RULE"), ("task-symbolic", "SYMBOLIC"),
                                            ("task-model-stub", "LLM_STUB")])
def test_three_generators_share_one_path(reg, pkg, name, kind):
    """P2-043: rule, symbolic (Z3) and model-assisted generators produce the same typed TaskPlan and run through
    the same engine path; the stub is labelled LLM_STUB, never LLM."""
    res = run(reg, pkg, scenario("normal", pkg, seed=2, strategy=STRATEGIES[name]), f"run_gen_{kind}")
    assert res.status == "SUCCEEDED"
    plans = [TaskPlan.model_validate(e.payload["plan"]) for e in of(res, "PLAN_UPDATED")]
    assert plans and {p.generator.kind for p in plans} == {kind}
    assert {e.payload["proposal"]["source"]["kind"] for e in of(res, "ACTION_PROPOSED")} == {kind}
    if kind == "SYMBOLIC":
        assert "Z3" in plans[0].revision.detail
    if kind == "LLM_STUB":
        assert plans[0].generator.model == "stub-deterministic-v1"


class _Client:
    is_stub = True
    model = "fake"

    def __init__(self, answer):
        self.answer, self.calls = answer, []

    def complete_json(self, **kw):
        from formal_lab_strategies.model_clients import ModelCall, ModelResponse

        if isinstance(self.answer, Exception):
            self.calls.append(ModelCall(call_id="c_err", model_requested="fake", outcome="TRANSPORT_ERROR",
                                        attempts=3, error=str(self.answer)))
            raise self.answer
        self.calls.append(ModelCall(call_id="c_ok", model_requested="fake", outcome="OK", attempts=1,
                                    model_returned="fake"))
        return ModelResponse(content=self.answer, raw_text=json.dumps(self.answer), model="fake", call_id="c_ok")


def test_model_generator_answers_are_checked_and_failures_fall_back(pkg):
    """P2-043 / P2-044: a model order must be a dependency-respecting permutation of the open tasks; anything else
    — or a transport failure — is recorded and the rule order is used."""
    planner = TaskPlanner(pkg, {"generator": "model", "client": "stub"}, services=None)
    state = check_model(pkg.ir).initial_state()
    rule = planner._rule_order(planner.ops, state)
    good = sorted(planner.ops, key=lambda op: (len(planner.preds[op]), op[::-1]))  # a different valid order
    good = planner._topological(good, {op: i for i, op in enumerate(good)})
    for answer, expect, note in [
        ({"order": good, "rationale": "r"}, good, "model order"),
        ({"order": list(reversed(rule)), "rationale": "r"}, rule, "model answer rejected"),
        ({"order": rule[:-1], "rationale": "r"}, rule, "model answer rejected"),
        (RetryableFailure("relay down"), rule, "model unavailable"),
    ]:
        planner._client = _Client(answer)
        order, usage = planner._model_order(planner.ops, state, None)
        assert order == expect and planner.generator_note.startswith(note)
        assert [r["outcome"] for r in planner.call_records] == ["TRANSPORT_ERROR" if isinstance(answer, Exception)
                                                                  else "OK"]
        failed = isinstance(answer, Exception)  # answered calls count as model calls, every attempt as an attempt
        assert (usage.model_calls, usage.attempts) == ((0, 3) if failed else (1, 1))


def test_revisions_record_trigger_parent_and_reason(reg, pkg):
    """P2-042: effect differences, another participant taking tasks and a short budget each produce a new plan
    version naming its trigger, its parent version and the reason; an unchanged order creates no version."""
    mism = run(reg, pkg, scenario("expectation-mismatch", pkg, seed=1, strategy=STRATEGIES["task-rule"]), "run_mm")
    two = run(reg, pkg, two_dispatchers(pkg, seed=1, strategies=("task-rule", "task-rule")), "run_two")
    sc = scenario("normal", pkg, seed=1, strategy=STRATEGIES["task-rule"])
    tight = ScenarioManifest.model_validate({**sc.model_dump(mode="json"),
                                             "budget": {**sc.budget.model_dump(mode="json"), "max_steps": 16}})
    budget = run(reg, pkg, tight, "run_budget")
    for res, trigger in [(mism, "EFFECT_DIFFERENCE"), (two, "RESOURCE_CHANGE"), (budget, "BUDGET")]:
        assert res.status == "SUCCEEDED"
        updates = of(res, "PLAN_UPDATED")
        revised = [e for e in updates if e.payload["plan"]["revision"]["trigger"] == trigger]
        assert revised, trigger
        for e in revised:
            plan = e.payload["plan"]
            assert plan["parent_version"] == e.payload["previous_version"] == plan["version"] - 1
            assert plan["revision"]["detail"] and plan["revision"]["at_step"] == e.logical_step
            before = [u for u in updates if u.actor_id == e.actor_id and
                      u.payload["plan"]["version"] == plan["parent_version"]]
            assert before, "the plan before the revision is on the record too"
        versions: dict[str, list[int]] = {}
        for e in updates:
            versions.setdefault(e.actor_id, []).append(e.payload["plan"]["version"])
        assert all(v == list(range(1, len(v) + 1)) for v in versions.values())
    assert [e.payload["plan"]["revision"]["trigger"] for e in of(budget, "PLAN_UPDATED")] == ["INITIAL", "BUDGET"]


RESUME = """
import json, sys
from formal_lab_example_scheduling.scenarios import model_package
from formal_lab_runtime import resume_local
res = resume_local(json.load(open(sys.argv[1])), model_package())
ev = lambda k: [e for e in res.events if str(e.event_type) == k]
print(json.dumps({
    "status": res.status.value, "turn": res.carry["turn"],
    "trajectory": [(e.logical_step, e.actor_id, json.dumps(e.payload["outcome"]["action"], sort_keys=True),
                    e.payload["outcome"]["status"]) for e in ev("ACTION_OUTCOME")],
    "cursors": [(e.logical_step, (e.payload["proposal"].get("plan") or {}).get("version"),
                 (e.payload["proposal"].get("plan") or {}).get("node_id")) for e in ev("ACTION_PROPOSED")],
    "checkpoints": [e.payload["digest"] for e in ev("PLANNER_CHECKPOINT")],
    "checks": [(e.logical_step, e.payload["result"]["verdict"]) for e in ev("CHECK_COMPLETED")],
    "metrics": {m.metric_id: m.value for m in res.metrics if m.metric_id != "wall_seconds"}}))
"""


@pytest.mark.parametrize("name", ["task-rule", "task-symbolic", "task-model-stub"])
def test_resume_in_a_fresh_process_equals_the_uninterrupted_run(reg, pkg, tmp_path, name):
    """P2-041 / P2-046: stop after step 6, serialise, continue in a new interpreter: the action trajectory, turn
    cursor, task cursor, planner checkpoints (plan, working state, rejection memory, RNG), check verdicts and
    metrics equal the uninterrupted run with the same seed."""
    sc = scenario("state-delay", pkg, seed=2, strategy=STRATEGIES[name])
    full = run(reg, pkg, sc, "run_fresh")
    part = run(reg, pkg, sc, "run_fresh", stop_after=6)
    assert isinstance(part, LocalRunState)
    cp = part.carry.checkpoints["dispatcher"]
    assert cp["plan"]["nodes"] and cp["rng_state"] and {"fresh", "rejected", "pending"} <= set(cp["progress"])
    path = tmp_path / "state.json"
    path.write_text(json.dumps(part.to_json()))
    out = subprocess.run([sys.executable, "-c", RESUME, str(path)], capture_output=True, text=True, check=True,
                         cwd=tmp_path).stdout.strip().splitlines()[-1]
    got = json.loads(out)
    assert got["status"] == full.status.value == "SUCCEEDED"
    assert [tuple(t) for t in got["trajectory"]] == trajectory(full)
    assert [tuple(c) for c in got["cursors"]] == cursors(full)
    assert got["checkpoints"] == [e.payload["digest"] for e in of(full, "PLANNER_CHECKPOINT")]
    assert [tuple(c) for c in got["checks"]] == [(e.logical_step, e.payload["result"]["verdict"])
                                                 for e in of(full, "CHECK_COMPLETED")]
    assert got["turn"] == full.carry["turn"]
    assert got["metrics"] == {m.metric_id: m.value for m in full.metrics if m.metric_id != "wall_seconds"}


def test_delayed_observations_neither_double_dispatch_nor_retry_a_busy_machine(reg, pkg):
    """P2-047: under state-delay the task planner's working state (freshest facts + its own predicted effects)
    keeps it from starting an operation twice or trying a machine it knows is busy."""
    for seed in (1, 2, 3):
        res = run(reg, pkg, scenario("state-delay", pkg, seed=seed, strategy=STRATEGIES["task-rule"]), f"run_sd{seed}")
        assert res.status == "SUCCEEDED" and res.usage.steps <= 20
        outcomes = [e.payload["outcome"] for e in of(res, "ACTION_OUTCOME")]
        assert not [o for o in outcomes if o["status"] == "REJECTED"]
        ops = [o["action"]["params"]["op"] for o in outcomes if o["action"]["action_type"] == "assign"]
        assert len(ops) == len(set(ops)), "no operation dispatched twice"


def test_a_stalled_strategy_ends_with_a_reason_instead_of_the_budget(reg, pkg):
    """P2-047: the model-planner stand-in stalls on state-delay; with a no-progress limit the run ends early as
    FAILED / NO_PROGRESS with the stall in its stop text (without it, the budget runs out)."""
    stalled = run(reg, pkg, scenario("state-delay", pkg, seed=1, strategy=STRATEGIES["llm-stub"], no_progress_limit=8),
                  "run_np")
    assert stalled.status == "FAILED" and stalled.termination_reason == "NO_PROGRESS"
    assert "no state change in the last 8 turn(s)" in stalled.reason and stalled.usage.steps < 60
    ok = run(reg, pkg, scenario("state-delay", pkg, seed=1, strategy=STRATEGIES["task-rule"], no_progress_limit=8),
             "run_np_ok")
    assert ok.status == "SUCCEEDED"
