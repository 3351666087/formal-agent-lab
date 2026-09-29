"""Build the formal-lab-contracts/v2 samples in tests/contracts/fixtures/v2.

valid/*.json            — at least one instance per object (phase-1 names with v2 content + phase-2 objects);
                          later phases must keep accepting these.
invalid/*.json          — {"object", "reason", "instance"} every validator (Pydantic, JSON Schema, ajv) must reject.
semantic-invalid/*.json — rules only the Pydantic validators can express.

The phase-1 samples in fixtures/v1/ are frozen: they are never regenerated and must keep validating as v1 and
upgrading to v2 (tests/contracts/test_contracts.py).

    uv run python tests/contracts/build_fixtures_v2.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from formal_lab_contracts import (
    ActionOutcome,
    ActionProposal,
    ActionSpec,
    ArtifactRef,
    AssumptionSet,
    BeliefState,
    BoundedCheckResult,
    CapabilityReport,
    EnvironmentSession,
    ExecutionDecision,
    MatrixCellSpec,
    MetricDefinition,
    MetricResult,
    ModelPackage,
    ModelReleaseRecord,
    ObjectiveSpec,
    Observation,
    OperationRecord,
    PlannerCheckpoint,
    PluginDescriptor,
    ProbeResult,
    QueryBundle,
    RegressionCase,
    ReleaseConfig,
    RuleDecision,
    RuleEvaluation,
    RuleSet,
    RunManifest,
    ScenarioManifest,
    StageRecord,
    TaskPlan,
    TerminationPolicy,
    TraceEvent,
    TurnPolicy,
    TurnState,
    canonical_ir_dump,
    digest_of,
)
from formal_lab_contracts.ir import ModelIR

HERE = Path(__file__).parent / "fixtures" / "v2"
T0 = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)

LAMP_IR = {
    "semantic_profile": "deterministic_finite_v1",
    "name": "lamp-counter",
    "description": "a lamp that can be toggled; a counter records toggles (bounded)",
    "state": [
        {"name": "on", "type": {"kind": "bool"}, "initial": {"default": False}},
        {"name": "toggles", "type": {"kind": "int", "min": 0, "max": 3}, "initial": {"default": 0}},
    ],
    "actions": [
        {
            "name": "toggle",
            "cost": 2,
            "precondition": {"op": "const", "value": True},
            "effects": [
                {"kind": "assign", "target": {"var": "on"}, "value": {"op": "not", "args": [{"op": "var", "name": "on"}]}},
                {
                    "kind": "assign",
                    "target": {"var": "toggles"},
                    "value": {"op": "add", "args": [{"op": "var", "name": "toggles"}, {"op": "const", "value": 1}]},
                },
            ],
        }
    ],
    "properties": [
        {"id": "lit", "kind": "goal", "expr": {"op": "var", "name": "on"}},
        {
            "id": "few_toggles",
            "kind": "invariant",
            "expr": {"op": "le", "args": [{"op": "var", "name": "toggles"}, {"op": "const", "value": 2}]},
        },
    ],
    "objectives": [
        {"id": "toggle_cost", "label": "toggle cost", "terms": [{"kind": "action_cost"}]},
    ],
}

ACTION = {"action_type": "toggle", "params": {}}
ENV = {"plugin_id": "formal-lab.env.ir-world", "version": "1.0.0"}
PLANNER = {"plugin_id": "formal-lab.planner.z3-bounded", "version": "2.0.0"}
RULE = {"plugin_id": "formal-lab.example.scheduling.edd-dispatch", "version": "2.0.0"}
TURN_A = {"global_step": 1, "round": 1, "actor_id": "a", "actor_step": 1}


def build_valid() -> dict[str, dict]:
    ir = ModelIR.model_validate(LAMP_IR)
    model_digest = digest_of(canonical_ir_dump(ir))
    model_ref = {"package_id": "lamp", "version": 1, "digest": model_digest.model_dump()}
    artifact = ArtifactRef(uri="file://var/artifacts/ab/abcdef.json", media_type="application/json", size_bytes=42,
                           digest=digest_of(b"x"), format_version="formal-lab/snapshot@1", name="snapshot-step-1.json")
    objective = ObjectiveSpec(objective_id="cheapest", goal_property="lit", horizon=4,
                              levels=[{"id": "cost", "model_objective": "toggle_cost"}])
    scenario = ScenarioManifest(
        scenario_id="lamp-two-actors",
        name="lamp, two participants",
        model=model_ref,
        environment={"plugin": ENV, "config": {}},
        participants=[
            {"actor_id": "a", "strategy": {"plugin": PLANNER, "config": {"horizon": 3}}, "goal": "lit",
             "budget": {"max_steps": 3}},
            {"actor_id": "b", "strategy": {"plugin": RULE, "config": {}},
             "scope": {"action_types": ["toggle"], "params": {}}},
        ],
        objectives=[{"property_id": "lit"}],
        budget={"max_steps": 6, "max_wall_seconds": 30},
        seed=7,
        turns={"mode": "FIXED_TABLE", "table": ["a", "b", "b"], "observation_timing": "ROUND_START",
               "conflict_policy": "REJECT_STALE"},
        termination={"joint_goal": "lit", "actor_goals": "ALL", "invariants": ["few_toggles"],
                     "on_no_action": "SKIP_ACTOR", "no_progress_limit": 4},
        objective=objective,
    )
    v1_style = ScenarioManifest(
        scenario_id="lamp-basic", name="lamp basic", model=model_ref, environment={"plugin": ENV, "config": {}},
        participants=[{"actor_id": "agent", "strategy": {"plugin": PLANNER, "config": {}}}],
        budget={"max_steps": 5}, stop_conditions=[{"kind": "GOAL_REACHED", "property_id": "lit"}])
    assumptions = AssumptionSet(
        items=[{"path": "toggles", "provenance": "STALE", "value": 0, "as_of_step": 0, "reason": "OBSERVATION_DELAY"}],
        digest=digest_of({"toggles": 0}), counts={"STALE": 1, "KNOWN": 1})
    observation = Observation(
        run_id="run_0002", actor_id="a", step=1, state_revision=1, turn=TURN_A, timing="ROUND_START",
        facts=[{"path": "on", "value": True, "observed_at_step": 1}],
        unknowns=[{"path": "toggles", "reason": "OBSERVATION_DELAY",
                   "last_known": {"path": "toggles", "value": 0, "observed_at_step": 0, "source": "DELAYED"}}],
    )
    proposal = ActionProposal(
        proposal_id="run_0002:s1:a:proposal", run_id="run_0002", step_id="run_0002:s1", step=1, actor_id="a",
        action=ACTION, based_on_revision=1, source={"kind": "SYMBOLIC", "strategy": PLANNER},
        rationale="cost-optimal plan", candidates_considered=1, turn=TURN_A,
        plan={"plan_id": "plan_a", "version": 2, "node_id": "n1"},
        assumptions={"digest": assumptions.digest.model_dump(), "count": 1, "basis": "ASSUMPTION_BASED",
                     "counts": {"STALE": 1}},
        usage={"model_calls": 0, "attempts": 0},
    )
    outcome = ActionOutcome(
        operation_id="run_0002:s1:a:apply", run_id="run_0002", step_id="run_0002:s1", proposal_id=proposal.proposal_id,
        action=ACTION, status="APPLIED", effect_applied=True, revision_before=1, revision_after=2, turn=TURN_A,
        operation_state="COMPLETED",
        effect_comparison={
            "verdict": "DIFFERENT", "expected_by": "model:lamp@1",
            "diffs": [{"path": "on", "expected": False, "observed": True, "status": "DIFFERENT",
                       "evidence": "observed", "observed_at_step": 2, "freshness": "FRESH"},
                      {"path": "toggles", "expected": 1, "observed": None, "status": "UNKNOWN",
                       "evidence": "unknown", "freshness": "MISSING"}],
            "evidence_counts": {"observed": 1, "unknown": 1},
        },
    )
    rejected = ActionOutcome(
        operation_id="run_0002:s2:b:apply", run_id="run_0002", step_id="run_0002:s2", action=ACTION,
        status="REJECTED", effect_applied=False, revision_before=2, revision_after=2,
        conflict={"policy": "REJECT_STALE", "based_on_revision": 1, "current_revision": 2, "changed_paths": ["on"],
                  "reason": "observed at revision 1; 'on' changed since"},
    )
    witness = {"steps": [{"step": 0, "action": None, "state": {"on": False, "toggles": 0}},
                         {"step": 1, "action": ACTION, "state": {"on": True, "toggles": 1}}], "replay": "CONFIRMED"}
    check = BoundedCheckResult(
        check_id="chk_0001",
        query={"kind": "GOAL_REACHABILITY", "property_id": "lit", "bound": {"max_steps": 3, "timeout_ms": 5000},
               "initial_state": "GIVEN_STATE"},
        semantics="EXISTS_PATH", verdict="WITNESS", bound={"max_steps": 3, "timeout_ms": 5000},
        model_digest=model_digest, witness=witness, backend={"name": "z3", "version": "5.1.0"},
        stats={"solver_status": "sat", "steps_explored": 1, "elapsed_ms": 1.5, "timeout_ms": 5000},
        assumption_set=assumptions,
    )
    optimize = BoundedCheckResult(
        check_id="chk_0003",
        query={"kind": "OPTIMIZE_OBJECTIVE", "objective": objective.model_dump(mode="json"),
               "bound": {"max_steps": 4, "timeout_ms": 5000}},
        semantics="OPTIMAL_PATH", verdict="FEASIBLE", bound={"max_steps": 4, "timeout_ms": 5000},
        model_digest=model_digest, witness=witness, backend={"name": "z3", "version": "5.1.0"},
        stats={"solver_status": "unknown", "reason_unknown": "timeout", "elapsed_ms": 5000.0},
        optimization={"objective_id": "cheapest", "status": "FEASIBLE", "horizon": 4, "plan_length": 1,
                      "levels": [{"level": "cost", "value": 2, "proven_lower": 1, "proven_upper": 2,
                                  "optimal": False}], "solver_calls": 3},
    )
    robust = BoundedCheckResult(
        check_id="chk_0004",
        query={"kind": "ROBUST_SEQUENCE", "sequence": [ACTION, ACTION], "property_id": "lit",
               "bound": {"max_steps": 2}, "initial_state": "GIVEN_STATE"},
        semantics="ALL_COMPLETIONS", verdict="NOT_ROBUST", bound={"max_steps": 2},
        model_digest=model_digest, backend={"name": "z3", "version": "5.1.0"}, stats={"solver_status": "sat"},
        robustness={"verdict": "NOT_ROBUST", "sequence": ["toggle()", "toggle()"], "require_goal": "lit",
                    "counterexample": {"toggles": 2}, "failing_index": 1, "unknown_paths": ["toggles"]},
    )
    unknown_pre = BoundedCheckResult(
        check_id="chk_0005",
        query={"kind": "ACTION_PRECONDITION", "action": ACTION, "bound": {"max_steps": 0},
               "initial_state": "GIVEN_STATE"},
        semantics="SINGLE_STEP", verdict="UNKNOWN", bound={"max_steps": 0}, model_digest=model_digest,
        backend={"name": "z3", "version": "5.1.0"}, stats={"solver_status": "can=sat,cannot=sat"},
        observation_request={"paths": ["toggles"], "reason": "applicability depends on toggles",
                             "for_action": "toggle()", "applicable_completion": {"toggles": 0},
                             "inapplicable_completion": {"toggles": 3}},
    )
    unsupported = BoundedCheckResult(
        check_id="chk_0002",
        query={"kind": "ACTION_PRECONDITION", "action": ACTION, "bound": {"max_steps": 0}},
        semantics="SINGLE_STEP", verdict="UNSUPPORTED", bound={"max_steps": 0}, model_digest=model_digest,
        backend={"name": "z3", "version": "5.1.0"}, stats={"solver_status": "not-run"},
        unsupported={"feature": "semantic_profile", "reason": "warehouse_alloc_v1 is not the neutral IR",
                     "extension_point": "Verifier plugin declaring profile.warehouse_alloc_v1"},
    )
    event = TraceEvent(
        event_id="evt_0002", run_id="run_0002", seq=4, event_type="ACTION_PROPOSED",
        causal_parents=["evt_0001"], logical_step=1, wall_time=T0, actor_id="a",
        payload_schema="formal-lab/events/ACTION_PROPOSED@2", payload={"proposal": proposal.model_dump(mode="json")},
        idempotency_key="run_0002:s1:a:proposal", turn=TURN_A, stage="PROPOSE",
    )
    metric_def = MetricDefinition(metric_id="goal_reached", label="Goal reached", unit="bool",
                                  direction="HIGHER_IS_BETTER", aggregation="RATE", value_type="bool")
    metric = MetricResult(metric_id="goal_reached", metric_version="1", subject="run_0002", value=1.0, status="OK")
    missing = MetricResult(metric_id="delay_cost", metric_version="1", subject="run_0003", value=None,
                           status="MISSING", missing_reason="run failed before completion")
    source = {"format": "fal-ir-json/v1", "origin": "tests/contracts"}
    package = ModelPackage(
        package_id="lamp", version=1, frontend={"plugin_id": "formal-lab.frontend.ir-json", "version": "1.0.0"},
        semantic_profile="deterministic_finite_v1", digest=model_digest, payload={"kind": "fal-ir", "ir": ir},
        source=source, created_at=T0,
        extensions={"org.example.lab": {"version": "1.0.0", "schema_id": "org.example.lab/tags@1",
                                        "data": {"tags": ["demo"]}}},
    )
    wh_data = {"zones": [{"id": "z1", "capacity": 2}], "skus": ["s1"], "arrivals": [{"sku": "s1", "qty": 1}]}
    namespaced = ModelPackage(
        package_id="warehouse", version=1,
        frontend={"plugin_id": "formal-lab.example.warehouse.frontend", "version": "1.0.0"},
        semantic_profile="warehouse_alloc_v1",
        digest=digest_of({"namespace": "formal-lab.example.warehouse", "schema_id": "warehouse-model@1",
                          "data": wh_data}),
        payload={"kind": "namespaced", "namespace": "formal-lab.example.warehouse", "schema_id": "warehouse-model@1",
                 "data": wh_data},
        source={"format": "warehouse-json/v1", "origin": "tests/contracts"}, created_at=T0,
    )
    descriptor = PluginDescriptor(
        plugin_id="formal-lab.planner.z3-bounded", version="2.0.0", interface="PLANNER",
        capabilities=[{"id": "plan.bounded_search"}, {"id": "plan.cost_optimal"}, {"id": "plan.checkpoint"}],
        requires=[{"id": "driver.ir", "params": {"of": "driver"}}],
        semantic_profiles=["deterministic_finite_v1"],
        config_schema={"type": "object", "properties": {"horizon": {"type": "integer", "minimum": 1}}},
        entrypoint="formal_lab_solver_z3.planner:create", ui={"label": "Z3 planner"}, license="Apache-2.0",
    )
    v1_plugin = PluginDescriptor(
        contract_version="formal-lab-contracts/v1", interface_version="1", plugin_id="org.example.old-planner",
        version="0.1.0", interface="PLANNER", entrypoint="old:create", ui={"label": "v1 plugin"})
    driver = PluginDescriptor(
        plugin_id="formal-lab.driver.warehouse-alloc", version="1.0.0", interface="SEMANTIC_DRIVER",
        capabilities=[{"id": "profile.warehouse_alloc_v1"}, {"id": "driver.candidates"}, {"id": "driver.predict"}],
        semantic_profiles=["warehouse_alloc_v1"], input_schema={"type": "object"},
        entrypoint="formal_lab_example_warehouse.driver:create", ui={"label": "Warehouse allocation driver"})
    spec = ActionSpec(action_type="toggle", params_schema={"type": "object", "properties": {},
                                                           "additionalProperties": False},
                      preconditions=["always applicable"], expected_effects=["on := not on"], cost=2.0)
    manifest = RunManifest(
        run_id="run_0002", project_id="prj_0001", created_at=T0, scenario=scenario,
        scenario_digest=digest_of(scenario), model=model_ref,
        plugins=[{"role": "environment", "plugin_id": ENV["plugin_id"], "version": "1.0.0",
                  "interface": "ENVIRONMENT", "interface_version": "2", "descriptor_digest": digest_of({"x": 1})},
                 {"role": "driver", "plugin_id": "formal-lab.driver.ir-finite", "version": "1.0.0",
                  "interface": "SEMANTIC_DRIVER", "interface_version": "2", "descriptor_digest": digest_of({"y": 2})}],
        participants=scenario.participants, budget=scenario.budget, seed=7, status="SUCCEEDED",
        platform={"version": "0.2.0", "source_revision": "0000000"}, artifacts=[artifact],
        budget_usage={"steps": 2, "wall_seconds": 0.2, "model_attempts": 1, "unconfirmed_calls": 1},
        turns=scenario.turns, termination=scenario.termination, objective=objective,
        negotiation=[{"plugin_id": ENV["plugin_id"], "plugin_version": "1.0.0", "compatible": True,
                      "granted": ["env.pure_replayable"], "role": "environment", "verdict": "SUPPORTED"}],
        actor_usage={"a": {"steps": 1}, "b": {"steps": 1}}, termination_reason="JOINT_GOAL_REACHED",
    )
    turn_state = TurnState(global_step=2, round=1, position=2, actor_steps={"a": 1, "b": 1}, skipped={"b": 0},
                           goals_reached=["a"])
    belief = BeliefState(actor_id="a", step=1, world_revision=1, state={"on": True, "toggles": 0},
                         provenance={"on": "KNOWN", "toggles": "STALE"}, as_of_step={"toggles": 0}, free_paths=["toggles"],
                         assumptions=assumptions)
    plan = TaskPlan(
        plan_id="plan_a", actor_id="a", version=2,
        generator={"kind": "SYMBOLIC", "strategy": PLANNER, "method": "OPTIMIZE_OBJECTIVE"},
        created_at_step=1, cursor="n1",
        nodes=[{"node_id": "n1", "label": "toggle", "action": ACTION, "status": "IN_PROGRESS",
                "done_when": {"op": "var", "name": "on"}},
               {"node_id": "n2", "depends_on": ["n1"], "status": "PENDING"}],
        revision={"trigger": "EFFECT_DIFFERENCE", "detail": "'on' differed from the prediction", "at_step": 1},
        parent_version=1, objective_value=2.0,
    )
    checkpoint = PlannerCheckpoint(actor_id="a", planner=PLANNER, step=1, plan=plan, progress={"done": ["n0"]},
                                   rng_state=[3, [1, 2], None], cache_refs=["plan:ab12"],
                                   remaining_budget={"steps": 2})
    session = EnvironmentSession(
        session_id="ses_0001", environment={"plugin_id": "formal-lab.env.order-service", "version": "1.0.0"},
        backend="SERVICE", status="READY",
        capabilities=["env.persistent_session", "env.query_operation", "env.idempotent_step"],
        recovery_modes=["SERVICE_RESET", "STATE_IMPORT"], endpoint="http://127.0.0.1:8090",
        project_label="fal-prj_0001", owner={"project_id": "prj_0001", "profile": "local-services"},
        revision=12, created_at=T0, updated_at=T0,
    )
    operation = OperationRecord(
        operation_id="run_0002:s3:a:apply", run_id="run_0002", step=3, actor_id="a", state="RECONCILED",
        transitions=[{"state": "PREPARED", "at": T0, "reason": "intent recorded"},
                     {"state": "DISPATCHED", "at": T0, "reason": "POST /orders/o1/reserve"},
                     {"state": "OUTCOME_UNKNOWN", "at": T0, "reason": "connection reset after send"},
                     {"state": "RECONCILED", "at": T0, "reason": "GET /operations/<id>: completed"}],
        proposal_id="run_0002:s3:a:proposal", action=ACTION, based_on_revision=11,
        reconciliation={"method": "QUERY_OPERATION", "found": True, "note": "service applied it once"},
        attempts=1,
    )
    exec_decision = ExecutionDecision(
        decision_id="run_0002:s3:a:apply:gate0:first_send:0", run_id="run_0002", step=3, actor_id="a",
        operation_id="run_0002:s3:a:apply", gate={"plugin_id": "formal-lab.example.orders.inventory-gate",
                                                  "version": "1.0.0"},
        phase="FIRST_SEND", verdict="DENY", reason="stock[a] = 4 < 5: reserving 3 would leave less than the safety "
                                                   "stock of 2",
        conditions=[{"name": "safety_stock", "holds": False, "observed": 4, "required": ">= 5",
                     "paths": ["stock[a]"], "detail": "fresh value at revision 11"}],
        values_source="FRESH", checked_at_revision=11, request_digest="0" * 64, at=T0)
    gated = OperationRecord(
        operation_id="run_0002:s3:a:apply", run_id="run_0002", step=3, actor_id="a", state="FAILED",
        transitions=[{"state": "PREPARED", "at": T0, "reason": "intent recorded", "effect": "NONE"},
                     {"state": "FAILED", "at": T0, "reason": "denied before sending: inventory gate",
                      "effect": "NONE"}],
        proposal_id="run_0002:s3:a:proposal", action=ACTION, based_on_revision=11, request_digest="0" * 64,
        decisions=[exec_decision])
    stage = StageRecord(stage="EXECUTE", status="UNKNOWN", retry="RECONCILE_THEN_RETRY", input_digest="ab",
                        elapsed_ms=12.0, note="response lost; reconcile next")
    probe = ProbeResult(probe_id="prb_1", probe={"plugin_id": "formal-lab.probe.order-service", "version": "1.0.0"},
                        source="GET /metrics", metric="queue_length", value=3.0, unit="orders",
                        window={"kind": "LOGICAL_STEPS", "size": 5, "start": 0, "end": 5}, logical_step=5,
                        wall_time=T0)
    bundle = QueryBundle(bundle_id="qb_1", created_at=T0, model=model_ref, verifier={"plugin_id":
                         "formal-lab.verifier.z3-bmc", "version": "2.0.0"}, query=check.query,
                         state={"on": False, "toggles": 0}, result=check,
                         explanation=["shortest path to goal 'lit' has 1 step"], replay={"witness": "CONFIRMED"})
    ruleset = RuleSet(
        ruleset_id="lamp-rules", version=1, name="lamp rules", model=model_ref,
        rules=[{"rule_id": "pause_on_difference", "trigger": {"events": ["EFFECT_COMPARED"]},
                "condition": {"op": "eq", "args": [{"op": "ref", "name": "ev_verdict"},
                                                   {"op": "const", "value": "DIFFERENT"}]},
                "priority": 10, "outcome": "PAUSE", "message": "prediction differs: pause and review the model"},
               {"rule_id": "observe_toggles", "trigger": {"events": ["OBSERVATION"]},
                "condition": {"op": "gt", "args": [{"op": "ref", "name": "ev_unknown_count"},
                                                   {"op": "const", "value": 0}]},
                "outcome": "OBSERVE_MORE", "observe_paths": ["toggles"], "message": "ask for the counter"}],
        digest=digest_of({"r": 1}), created_at=T0)
    evaluation = RuleEvaluation(rule_id="pause_on_difference", result="TRUE", outcome="PAUSE", priority=10,
                                explanation="ev_verdict = DIFFERENT")
    decision = RuleDecision(event_type="EFFECT_COMPARED", evaluations=[evaluation], outcome="PAUSE",
                            winner="pause_on_difference", priority_explanation="highest priority rule that fired")
    release = ModelReleaseRecord(
        release_id="rel_0001", model=model_ref, ruleset=ruleset.ref(), objective=objective,
        checks=[{"kind": "TYPE_CHECK", "subject": "model", "verdict": "OK", "passed": True},
                {"kind": "GOAL_REACHABILITY", "subject": "lit", "bound": {"max_steps": 3}, "verdict": "WITNESS",
                 "passed": True}],
        regression=[{"case_id": "reg_0001", "status": "PASS", "detail": "replay matches"}],
        bounds=["≤ 3 steps"], assumptions=["model initial state"], status="RELEASED",
        digest=digest_of({"rel": 1}), created_at=T0)
    case = RegressionCase(case_id="reg_0001", source="EFFECT_DIFFERENCE", model=model_ref, seed=7,
                          initial_state={"on": False, "toggles": 0}, actions=[ACTION], expected={"on": True},
                          observed={"on": False}, compared_paths=["on"], minimized=True,
                          origin={"run_id": "run_0002", "step": 1}, created_at=T0)
    cell = MatrixCellSpec(cell_id="c_ab12cd34", scenario_id="scn_1", scenario_revision=2,
                          participants={"a": {"plugin": PLANNER, "config": {}}, "b": {"plugin": RULE, "config": {}}},
                          environment={"plugin": ENV, "config": {}}, seed=3, budget={"max_steps": 60},
                          ablations={"observation_delay": False}, split="acceptance", config_digest="ab12cd34")
    objs = {
        "PluginDescriptor": descriptor, "PluginDescriptor.v1-plugin": v1_plugin, "PluginDescriptor.driver": driver,
        "ModelPackage": package, "ModelPackage.namespaced": namespaced,
        "ScenarioManifest": scenario, "ScenarioManifest.v1-style": v1_style,
        "Observation": observation, "ActionSpec": spec, "ActionProposal": proposal,
        "ActionOutcome": outcome, "ActionOutcome.conflict": rejected,
        "BoundedCheckResult": check, "BoundedCheckResult.optimize": optimize, "BoundedCheckResult.robust": robust,
        "BoundedCheckResult.unknown-precondition": unknown_pre, "BoundedCheckResult.unsupported": unsupported,
        "TraceEvent": event, "ArtifactRef": artifact, "MetricDefinition": metric_def, "MetricResult": metric,
        "MetricResult.missing": missing, "RunManifest": manifest,
        "ObjectiveSpec": objective, "TurnPolicy": TurnPolicy(), "TerminationPolicy": TerminationPolicy(),
        "AssumptionSet": assumptions, "BeliefState": belief, "TurnState": turn_state, "TaskPlan": plan,
        "PlannerCheckpoint": checkpoint, "EnvironmentSession": session, "OperationRecord": operation,
        "OperationRecord.gated": gated, "ExecutionDecision": exec_decision,
        "CapabilityReport": CapabilityReport(
            model={"package_id": "counter", "version": 1, "digest": {"algorithm": "sha256", "value": "a" * 64}},
            semantic_profile="counter_v1", driver={"plugin_id": "org.example.counter-driver", "version": "0.1.0"},
            features=[{"feature": "release.type_check", "status": "SUPPORTED",
                       "provider": {"plugin_id": "org.example.counter-driver", "version": "0.1.0"}, "requires": [],
                       "reason": "validates counter_v1 payloads"},
                      {"feature": "query.goal_reachability", "status": "UNSUPPORTED", "provider": None,
                       "requires": ["profile.counter_v1", "query.goal_reachability"],
                       "reason": "no installed verifier declares query.goal_reachability for profile counter_v1"}],
            generated_at=T0),
        "ReleaseConfig": ReleaseConfig(required_checks=["TYPE_CHECK", "GOAL_REACHABILITY"],
                                       required_holds=["lit"], horizon=4, timeout_ms=5000),
        "StageRecord": stage, "ProbeResult": probe, "QueryBundle": bundle, "RuleSet": ruleset,
        "RuleEvaluation": evaluation, "RuleDecision": decision, "ModelReleaseRecord": release,
        "RegressionCase": case, "MatrixCellSpec": cell,
    }
    return {name: obj.model_dump(mode="json", exclude_none=False) for name, obj in objs.items()}


def _mutate(valid: dict[str, dict], name: str, fn) -> dict:
    inst = json.loads(json.dumps(valid[name]))
    fn(inst)
    return inst


def build_invalid(valid: dict[str, dict]) -> dict[str, dict]:
    cases = {
        "unknown-core-field": ("RunManifest", "core objects reject unknown fields",
                               lambda i: i.__setitem__("surprise", 1)),
        "bad-digest": ("ArtifactRef", "digest must be 64 lowercase hex chars",
                       lambda i: i["digest"].__setitem__("value", "xyz")),
        "negative-seq": ("TraceEvent", "seq is >= 1", lambda i: i.__setitem__("seq", 0)),
        "bad-contract-version": ("ScenarioManifest", "v2 objects declare formal-lab-contracts/v2",
                                 lambda i: i.__setitem__("contract_version", "formal-lab-contracts/v9")),
        "v1-contract-on-v2-object": ("RunManifest", "a v1 object must be upgraded, not relabelled",
                                     lambda i: i.__setitem__("contract_version", "formal-lab-contracts/v1")),
        "bad-plugin-id": ("PluginDescriptor", "plugin ids are lowercase dotted",
                          lambda i: i.__setitem__("plugin_id", "Not A Plugin")),
        "bad-interface": ("PluginDescriptor", "interface is a closed enum",
                          lambda i: i.__setitem__("interface", "ORACLE")),
        "bad-query-kind": ("BoundedCheckResult", "query kind is a closed enum",
                           lambda i: i["query"].__setitem__("kind", "LIVENESS")),
        "unknown-expr-op": ("ModelPackage", "expression ops are a closed set",
                            lambda i: i["payload"]["ir"]["properties"][0].__setitem__("expr", {"op": "xor",
                                                                                              "args": []})),
        "v1-ir-field": ("ModelPackage", "v2 packages carry `payload`, not `ir`",
                        lambda i: i.__setitem__("ir", i.pop("payload")["ir"])),
        "bad-payload-kind": ("ModelPackage", "payload kind is fal-ir or namespaced",
                             lambda i: i["payload"].__setitem__("kind", "pickle")),
        "empty-int-range-missing-max": ("ModelPackage", "int type needs min and max",
                                        lambda i: i["payload"]["ir"]["state"][1]["type"].pop("max")),
        "bad-extension-namespace": ("ModelPackage", "extension keys are reverse-DNS namespaces",
                                    lambda i: i.__setitem__("extensions", {"NoDots": {"version": "1.0.0",
                                                                                       "schema_id": "x", "data": {}}})),
        "outcome-status-enum": ("ActionOutcome", "outcome status is a closed enum",
                                lambda i: i.__setitem__("status", "MAYBE")),
        "evidence-status-enum": ("ActionOutcome", "effect evidence is observed/verified-within-scope/predicted/"
                                 "unknown", lambda i: i["effect_comparison"]["diffs"][0].__setitem__("evidence",
                                                                                                   "guessed")),
        "metric-direction": ("MetricDefinition", "direction is a closed enum",
                             lambda i: i.__setitem__("direction", "SIDEWAYS")),
        "turn-mode": ("ScenarioManifest", "turn mode is a closed enum",
                      lambda i: i["turns"].__setitem__("mode", "SIMULTANEOUS")),
        "operation-state": ("OperationRecord", "operation state is a closed enum",
                            lambda i: i.__setitem__("state", "HALF_DONE")),
        "horizon-zero": ("ObjectiveSpec", "horizon is at least 1", lambda i: i.__setitem__("horizon", 0)),
        "provenance-enum": ("BeliefState", "provenance is KNOWN/STALE/UNKNOWN/ASSUMED_INITIAL",
                            lambda i: i["provenance"].__setitem__("on", "GUESSED")),
        "probe-window": ("ProbeResult", "window kind is logical steps or wall seconds",
                         lambda i: i["window"].__setitem__("kind", "FOREVER")),
        "rule-outcome": ("RuleSet", "rule outcomes are CONTINUE/OBSERVE_MORE/REPLAN/PAUSE",
                         lambda i: i["rules"][0].__setitem__("outcome", "IGNORE")),
    }
    return {key: {"object": obj, "reason": reason, "instance": _mutate(valid, obj, fn)}
            for key, (obj, reason, fn) in cases.items()}


def build_semantic_invalid(valid: dict[str, dict]) -> dict[str, dict]:
    def set_(path: list, value):
        def fn(i):
            node = i
            for p in path[:-1]:
                node = node[p]
            node[path[-1]] = value
        return fn

    cases = {
        "witness-verdict-without-witness": ("BoundedCheckResult", "WITNESS requires a witness", set_(["witness"], None)),
        "precondition-verdict-on-search-query": ("BoundedCheckResult", "APPLICABLE is not a search verdict",
                                                 set_(["verdict"], "APPLICABLE")),
        "semantics-mismatch": ("BoundedCheckResult", "GOAL_REACHABILITY has EXISTS_PATH semantics",
                               set_(["semantics"], "ALL_PATHS")),
        "optimal-without-witness": ("BoundedCheckResult.optimize", "FEASIBLE/OPTIMAL need a witness",
                                    set_(["witness"], None)),
        "not-robust-without-counterexample": ("BoundedCheckResult.robust", "NOT_ROBUST needs a counterexample",
                                              set_(["robustness", "counterexample"], None)),
        "optimize-without-objective": ("BoundedCheckResult.optimize", "OPTIMIZE_OBJECTIVE needs an objective",
                                       set_(["query", "objective"], None)),
        "unsupported-without-details": ("BoundedCheckResult.unsupported", "UNSUPPORTED requires details",
                                        set_(["unsupported"], None)),
        "applied-without-effect": ("ActionOutcome", "APPLIED implies effect_applied=true",
                                   set_(["effect_applied"], None)),
        "ok-metric-without-value": ("MetricResult", "OK metric needs a value", set_(["value"], None)),
        "missing-metric-with-value": ("MetricResult.missing", "MISSING metric carries no value", set_(["value"], 3.0)),
        "duplicate-actors": ("ScenarioManifest", "participant actor ids are unique",
                             lambda i: i["participants"][1].__setitem__("actor_id", "a")),
        "table-names-unknown-actor": ("ScenarioManifest", "turn table only names participants",
                                      set_(["turns", "table"], ["a", "zz"])),
        "fixed-table-empty": ("TurnPolicy", "FIXED_TABLE needs a table", set_(["mode"], "FIXED_TABLE")),
        "termination-and-stop-conditions": ("ScenarioManifest", "v1 stop conditions and v2 termination exclude "
                                            "each other", set_(["stop_conditions"],
                                                               [{"kind": "GOAL_REACHED", "property_id": "lit"}])),
        "illegal-operation-transition": ("OperationRecord", "COMPLETED is final",
                                         lambda i: i["transitions"].append({"state": "DISPATCHED",
                                                                            "at": "2026-09-27T12:00:00Z",
                                                                            "reason": "x", "attempt": 1})),
        "plan-unknown-dependency": ("TaskPlan", "dependencies name existing nodes",
                                    set_(["nodes", 1, "depends_on"], ["n9"])),
        "objective-level-without-terms": ("ObjectiveSpec", "a level needs terms or a model objective",
                                          set_(["levels", 0, "model_objective"], None)),
        "observe-more-without-paths": ("RuleSet", "OBSERVE_MORE rules name observe_paths",
                                       set_(["rules", 1, "observe_paths"], [])),
        "probe-ok-without-value": ("ProbeResult", "OK probe results carry a value", set_(["value"], None)),
    }
    return {key: {"object": obj.split(".")[0], "reason": reason, "instance": _mutate(valid, obj, fn)}
            for key, (obj, reason, fn) in cases.items()}


def main() -> None:
    valid = build_valid()
    for sub, data in (("valid", valid), ("invalid", build_invalid(valid)),
                      ("semantic-invalid", build_semantic_invalid(valid))):
        target = HERE / sub
        target.mkdir(parents=True, exist_ok=True)
        for old in target.glob("*.json"):
            old.unlink()
        for name, inst in data.items():
            (target / f"{name}.json").write_text(json.dumps(inst, indent=2, sort_keys=True) + "\n")
    print(f"wrote {len(valid)} valid samples and the invalid cases to {HERE}")


if __name__ == "__main__":
    main()
