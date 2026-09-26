"""Build the contract compatibility samples in tests/contracts/fixtures.

valid/*.json   — one instance per frozen object; later phases must keep accepting these.
invalid/*.json — {"object": <type>, "reason": <why>, "instance": {...}} that every validator must reject.

    uv run python tests/contracts/build_fixtures.py
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
    BoundedCheckResult,
    MetricDefinition,
    MetricResult,
    ModelPackage,
    Observation,
    PluginDescriptor,
    RunManifest,
    ScenarioManifest,
    TraceEvent,
    digest_of,
)
from formal_lab_contracts.ir import ModelIR

HERE = Path(__file__).parent / "fixtures"
T0 = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)

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
}


def build_valid() -> dict[str, dict]:
    ir = ModelIR.model_validate(LAMP_IR)
    model_digest = digest_of(ir)
    plugin_ref = {"plugin_id": "formal-lab.env.ir-world", "version": "1.0.0"}
    planner_ref = {"plugin_id": "formal-lab.planner.z3-bounded", "version": "1.0.0"}
    artifact = ArtifactRef(
        uri="file://var/artifacts/ab/abcdef.json",
        media_type="application/json",
        size_bytes=42,
        digest=digest_of(b"x"),
        format_version="formal-lab/snapshot@1",
        name="snapshot-step-1.json",
    )
    model_ref = {"package_id": "lamp", "version": 1, "digest": model_digest.model_dump()}
    scenario = ScenarioManifest(
        scenario_id="lamp-basic",
        name="lamp basic",
        model=model_ref,
        environment={"plugin": plugin_ref, "config": {}},
        participants=[{"actor_id": "agent", "strategy": {"plugin": planner_ref, "config": {"horizon": 3}}}],
        objectives=[{"property_id": "lit"}],
        budget={"max_steps": 5, "max_wall_seconds": 30},
        seed=7,
        stop_conditions=[{"kind": "GOAL_REACHED", "property_id": "lit"}],
    )
    observation = Observation(
        run_id="run_0001",
        actor_id="agent",
        step=1,
        state_revision=1,
        facts=[{"path": "on", "value": True, "observed_at_step": 1}],
        unknowns=[{"path": "toggles", "reason": "OBSERVATION_DELAY",
                   "last_known": {"path": "toggles", "value": 0, "observed_at_step": 0, "source": "DELAYED"}}],
    )
    action = {"action_type": "toggle", "params": {}}
    proposal = ActionProposal(
        proposal_id="run_0001:s1:proposal",
        run_id="run_0001",
        step_id="run_0001:s1",
        step=1,
        actor_id="agent",
        action=action,
        based_on_revision=1,
        source={"kind": "SYMBOLIC", "strategy": planner_ref},
        rationale="shortest witness path",
        candidates_considered=1,
    )
    outcome = ActionOutcome(
        operation_id="run_0001:s1:apply",
        run_id="run_0001",
        step_id="run_0001:s1",
        proposal_id=proposal.proposal_id,
        action=action,
        status="APPLIED",
        effect_applied=True,
        revision_before=1,
        revision_after=2,
        effect_comparison={
            "verdict": "DIFFERENT",
            "expected_by": "model:lamp@1",
            "diffs": [{"path": "on", "expected": False, "observed": True, "status": "DIFFERENT"}],
        },
    )
    check = BoundedCheckResult(
        check_id="chk_0001",
        query={"kind": "GOAL_REACHABILITY", "property_id": "lit", "bound": {"max_steps": 3, "timeout_ms": 5000}},
        semantics="EXISTS_PATH",
        verdict="WITNESS",
        bound={"max_steps": 3, "timeout_ms": 5000},
        assumptions=["initial state = model initial state"],
        model_digest=model_digest,
        witness={
            "steps": [
                {"step": 0, "action": None, "state": {"on": False, "toggles": 0}},
                {"step": 1, "action": action, "state": {"on": True, "toggles": 1}},
            ],
            "replay": "CONFIRMED",
        },
        variable_mapping={"on@0": "on"},
        backend={"name": "z3", "version": "5.1.0"},
        stats={"solver_status": "sat", "steps_explored": 1, "elapsed_ms": 1.5, "timeout_ms": 5000},
    )
    unsupported = BoundedCheckResult(
        check_id="chk_0002",
        query={"kind": "ACTION_PRECONDITION", "action": action, "bound": {"max_steps": 0}},
        semantics="SINGLE_STEP",
        verdict="UNSUPPORTED",
        bound={"max_steps": 0},
        model_digest=model_digest,
        backend={"name": "z3", "version": "5.1.0"},
        stats={"solver_status": "not-run"},
        unsupported={"feature": "probabilistic_effects", "reason": "outside deterministic_finite_v1",
                     "extension_point": "Verifier plugin declaring profile.probabilistic_*"},
    )
    event = TraceEvent(
        event_id="evt_0001",
        run_id="run_0001",
        seq=1,
        event_type="ACTION_PROPOSED",
        causal_parents=[],
        logical_step=1,
        wall_time=T0,
        actor_id="agent",
        payload_schema="formal-lab/events/ACTION_PROPOSED@1",
        payload={"proposal": proposal.model_dump(mode="json")},
        idempotency_key="run_0001:s1:proposal",
    )
    metric_def = MetricDefinition(metric_id="goal_reached", label="Goal reached", unit="bool",
                                  direction="HIGHER_IS_BETTER", aggregation="RATE", value_type="bool")
    metric = MetricResult(metric_id="goal_reached", metric_version="1", subject="run_0001", value=1.0, status="OK")
    missing = MetricResult(metric_id="total_tardiness", metric_version="1", subject="run_0002", value=None,
                           status="MISSING", missing_reason="run failed before completion")
    package = ModelPackage(
        package_id="lamp",
        version=1,
        frontend={"plugin_id": "formal-lab.frontend.ir-json", "version": "1.0.0"},
        semantic_profile="deterministic_finite_v1",
        digest=model_digest,
        ir=ir,
        source={"format": "fal-ir-json/v1", "origin": "tests/contracts"},
        created_at=T0,
        extensions={"org.example.lab": {"version": "1.0.0", "schema_id": "org.example.lab/tags@1", "data": {"tags": ["demo"]}}},
    )
    descriptor = PluginDescriptor(
        plugin_id="formal-lab.planner.z3-bounded",
        version="1.0.0",
        interface="PLANNER",
        capabilities=[{"id": "plan.bounded_search"}, {"id": "profile.deterministic_finite_v1"}],
        semantic_profiles=["deterministic_finite_v1"],
        config_schema={"type": "object", "properties": {"horizon": {"type": "integer", "minimum": 1}}},
        entrypoint="formal_lab_solver_z3.planner:create",
        ui={"label": "Z3 bounded planner"},
    )
    spec = ActionSpec(
        action_type="toggle",
        params_schema={"type": "object", "properties": {}, "additionalProperties": False},
        preconditions=["always applicable"],
        expected_effects=["on := not on", "toggles := toggles + 1"],
        retry="RECONCILE_THEN_RETRY",
    )
    manifest = RunManifest(
        run_id="run_0001",
        project_id="prj_0001",
        created_at=T0,
        scenario=scenario,
        scenario_digest=digest_of(scenario),
        model=model_ref,
        plugins=[{"role": "environment", "plugin_id": plugin_ref["plugin_id"], "version": "1.0.0",
                  "interface": "ENVIRONMENT", "interface_version": "1", "descriptor_digest": digest_of({"x": 1})}],
        participants=scenario.participants,
        budget=scenario.budget,
        seed=7,
        status="SUCCEEDED",
        platform={"version": "0.1.0", "source_revision": "0000000"},
        artifacts=[artifact],
        budget_usage={"steps": 1, "wall_seconds": 0.2},
    )
    objs = {
        "PluginDescriptor": descriptor,
        "ModelPackage": package,
        "ScenarioManifest": scenario,
        "Observation": observation,
        "ActionSpec": spec,
        "ActionProposal": proposal,
        "ActionOutcome": outcome,
        "BoundedCheckResult": check,
        "BoundedCheckResult.unsupported": unsupported,
        "TraceEvent": event,
        "ArtifactRef": artifact,
        "MetricDefinition": metric_def,
        "MetricResult": metric,
        "MetricResult.missing": missing,
        "RunManifest": manifest,
    }
    return {name: obj.model_dump(mode="json", exclude_none=False) for name, obj in objs.items()}


def build_invalid(valid: dict[str, dict]) -> dict[str, dict]:
    def mutate(name: str, fn) -> dict:
        inst = json.loads(json.dumps(valid[name]))
        fn(inst)
        return inst

    cases = {
        "unknown-core-field": ("RunManifest", "core objects reject unknown fields",
                               lambda i: i.__setitem__("surprise", 1)),
        "bad-digest": ("ArtifactRef", "digest must be 64 lowercase hex chars",
                       lambda i: i["digest"].__setitem__("value", "xyz")),
        "negative-seq": ("TraceEvent", "seq is >= 1", lambda i: i.__setitem__("seq", 0)),
        "bad-contract-version": ("ScenarioManifest", "contract_version is fixed",
                                 lambda i: i.__setitem__("contract_version", "formal-lab-contracts/v2")),
        "bad-plugin-id": ("PluginDescriptor", "plugin ids are lowercase dotted",
                          lambda i: i.__setitem__("plugin_id", "Not A Plugin")),
        "bad-query-kind": ("BoundedCheckResult", "query kind is a closed enum",
                           lambda i: i["query"].__setitem__("kind", "LIVENESS")),
        "unknown-expr-op": ("ModelPackage", "expression ops are a closed set",
                            lambda i: i["ir"]["properties"][0].__setitem__("expr", {"op": "xor", "args": []})),
        "empty-int-range-missing-max": ("ModelPackage", "int type needs min and max",
                                        lambda i: i["ir"]["state"][1]["type"].pop("max")),
        "bad-extension-namespace": ("ModelPackage", "extension keys are reverse-DNS namespaces",
                                    lambda i: i.__setitem__("extensions", {"NoDots": {"version": "1.0.0",
                                                                                       "schema_id": "x", "data": {}}})),
        "outcome-status-enum": ("ActionOutcome", "outcome status is a closed enum",
                                lambda i: i.__setitem__("status", "MAYBE")),
        "metric-direction": ("MetricDefinition", "direction is a closed enum",
                             lambda i: i.__setitem__("direction", "SIDEWAYS")),
    }
    return {
        key: {"object": obj, "reason": reason, "instance": mutate(obj, fn)} for key, (obj, reason, fn) in cases.items()
    }


# Semantic rules enforced by model validators (JSON Schema cannot express them); Python must reject.
def build_semantic_invalid(valid: dict[str, dict]) -> dict[str, dict]:
    def mutate(name: str, fn) -> dict:
        inst = json.loads(json.dumps(valid[name]))
        fn(inst)
        return inst

    cases = {
        "witness-verdict-without-witness": ("BoundedCheckResult", "WITNESS requires a witness",
                                            lambda i: i.__setitem__("witness", None)),
        "precondition-verdict-on-search-query": ("BoundedCheckResult", "APPLICABLE is not a search verdict",
                                                 lambda i: i.__setitem__("verdict", "APPLICABLE")),
        "semantics-mismatch": ("BoundedCheckResult", "GOAL_REACHABILITY has EXISTS_PATH semantics",
                               lambda i: i.__setitem__("semantics", "ALL_PATHS")),
        "unsupported-without-details": ("BoundedCheckResult.unsupported", "UNSUPPORTED requires details",
                                        lambda i: i.__setitem__("unsupported", None)),
        "applied-without-effect": ("ActionOutcome", "APPLIED implies effect_applied=true",
                                   lambda i: i.__setitem__("effect_applied", None)),
        "ok-metric-without-value": ("MetricResult", "OK metric needs a value", lambda i: i.__setitem__("value", None)),
        "missing-metric-with-value": ("MetricResult.missing", "MISSING metric carries no value",
                                      lambda i: i.__setitem__("value", 3.0)),
    }
    return {
        key: {"object": obj.split(".")[0], "reason": reason, "instance": mutate(obj, fn)}
        for key, (obj, reason, fn) in cases.items()
    }


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
    print(f"wrote fixtures to {HERE}")


if __name__ == "__main__":
    main()
