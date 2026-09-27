from __future__ import annotations

import pytest
from formal_lab_contracts import PluginRef, RunStatus
from formal_lab_contracts.errors import NotFound, VersionMismatch
from formal_lab_contracts.interfaces import PluginRegistration
from formal_lab_example_scheduling.scenarios import STRATEGIES, model_package, scenario
from formal_lab_runtime import LocalArtifactStore, default_registry, make_manifest, new_run_id, run_local

EVALUATORS = [PluginRef(plugin_id="formal-lab.eval.generic", version="1.0.0"),
              PluginRef(plugin_id="formal-lab.example.scheduling.scorer", version="1.0.0")]


@pytest.fixture(scope="module")
def pkg():
    return model_package()


@pytest.fixture(scope="module")
def reg():
    return default_registry()


def run(pkg, reg, key="normal", strategy="rule", seed=1, **kw):
    m = make_manifest(run_id=new_run_id(), project_id="prj", scenario=scenario(key, pkg, seed=seed,
                                                                                   strategy=STRATEGIES[strategy]),
                      package=pkg, registry=reg, evaluators=EVALUATORS, **kw)
    return run_local(m, pkg, reg)


def test_registry_discovers_builtin_plugins_via_entry_points(reg):
    ids = {e.descriptor.plugin_id for e in reg.entries()}
    assert {"formal-lab.env.ir-world", "formal-lab.verifier.z3-bmc", "formal-lab.planner.z3-bounded",
            "formal-lab.planner.llm", "formal-lab.eval.generic", "formal-lab.frontend.ir-json",
            "formal-lab.example.scheduling.edd-dispatch", "formal-lab.example.scheduling.scorer"} <= ids
    assert not reg.load_errors
    with pytest.raises(NotFound):
        reg.get(("formal-lab.planner.nope", "1.0.0"))


def test_registry_interface_and_contract_versions(reg):
    """v1 plugins (interface 1, contract v1) keep registering; unknown versions and v1-declared v2-only interfaces
    are refused; the config schema itself must be a valid JSON Schema."""
    from formal_lab_runtime import PluginRegistry

    base = reg.get(("formal-lab.eval.generic", "1.0.0")).descriptor
    fresh = PluginRegistry()
    v1_plugin = base.model_copy(update={"plugin_id": "x.v1", "interface_version": "1",
                                        "contract_version": "formal-lab-contracts/v1"})
    fresh.register(PluginRegistration(v1_plugin, lambda c, s: None))
    with pytest.raises(VersionMismatch):
        fresh.register(PluginRegistration(base.model_copy(update={"plugin_id": "x.y", "interface_version": "3"}),
                                          lambda c, s: None))
    driver_v1 = base.model_copy(update={"plugin_id": "x.drv", "interface": "SEMANTIC_DRIVER", "interface_version": "1"})
    with pytest.raises(VersionMismatch):
        fresh.register(PluginRegistration(driver_v1, lambda c, s: None))
    from formal_lab_contracts.errors import InvalidInput

    with pytest.raises(InvalidInput):
        fresh.register(PluginRegistration(base.model_copy(update={"plugin_id": "x.bad",
                                                                  "config_schema": {"type": "no-such-type"}}),
                                          lambda c, s: None))


def test_registry_resolves_semver_compatible_versions(reg):
    """A scenario that names ir-world 1.0.0 runs on the installed, backward-compatible 1.1.0."""
    assert reg.resolve(("formal-lab.env.ir-world", "1.0.0")).descriptor.version == "1.1.0"
    with pytest.raises(NotFound):
        reg.resolve(("formal-lab.env.ir-world", "2.0.0"))
    assert reg.driver_for("deterministic_finite_v1").descriptor.plugin_id == "formal-lab.driver.ir-finite"


def test_manifest_pins_versions_and_budget_dimensions(pkg, reg):
    m = make_manifest(run_id="run_x", project_id="p", scenario=scenario("normal", pkg, strategy=STRATEGIES["llm-stub"]),
                      package=pkg, registry=reg)
    roles = {p.role: p for p in m.plugins}
    assert set(roles) >= {"environment", "strategy:dispatcher", "verifier", "evaluator:0"}
    assert m.model == pkg.ref() and m.config["budget_dimensions"] == ["steps", "wall_seconds", "model_calls", "tokens"]
    rule = make_manifest(run_id="run_y", project_id="p", scenario=scenario("normal", pkg), package=pkg, registry=reg)
    assert rule.config["budget_dimensions"] == ["steps", "wall_seconds"]
    other = model_package(version=2)
    with pytest.raises(VersionMismatch):
        make_manifest(run_id="run_z", project_id="p", scenario=scenario("normal", pkg), package=other, registry=reg)


@pytest.mark.parametrize("key", ["normal", "resource-shortage", "state-delay", "expectation-mismatch"])
@pytest.mark.parametrize("strategy", ["rule", "z3"])
def test_scenarios_complete_with_non_stub_strategies(pkg, reg, key, strategy):
    res = run(pkg, reg, key, strategy)
    assert res.status == RunStatus.SUCCEEDED, res.reason
    metrics = {m.metric_id: m for m in res.metrics}
    assert metrics["goal_reached"].value == 1.0 and metrics["orders_completed"].value == 3
    assert metrics["model_calls"].status == "NOT_APPLICABLE"
    seqs = [e.seq for e in res.events]
    assert seqs == list(range(1, len(seqs) + 1))
    ids = {e.event_id for e in res.events}
    assert all(p in ids for e in res.events for p in e.causal_parents)  # causal graph is closed
    if key == "expectation-mismatch":
        assert metrics["effect_mismatches"].value > 0
    if key == "state-delay":
        assert any(e.event_type == "OBSERVATION" and e.payload["observation"]["unknowns"] for e in res.events)


def test_runs_are_deterministic_for_same_seed(pkg, reg):
    a, b = run(pkg, reg, "normal", "z3", seed=3), run(pkg, reg, "normal", "z3", seed=3)
    assert [s.proposal.action for s in a.steps] == [s.proposal.action for s in b.steps]
    assert a.final_state == b.final_state


def test_budget_exhaustion(pkg, reg):
    res = run(pkg, reg, "normal", "rule", budget={"max_steps": 3})
    assert res.status == RunStatus.BUDGET_EXHAUSTED and res.usage.steps == 3
    assert res.events[-1].event_type == "BUDGET_EXHAUSTED"
    assert {m.metric_id: m for m in res.metrics}["makespan"].status == "MISSING"


def test_llm_stub_results_are_labelled(pkg, reg):
    res = run(pkg, reg, "normal", "llm-stub")
    assert res.status == RunStatus.SUCCEEDED
    assert {s.proposal.source.kind for s in res.steps} == {"LLM_STUB"}
    assert {m.metric_id: m for m in res.metrics}["model_calls"].value == res.usage.steps


def test_local_artifact_store_roundtrip(tmp_path):
    store = LocalArtifactStore(tmp_path)
    ref = store.put(b'{"a":1}', name="x.json", media_type="application/json", format_version="t@1")
    assert store.put(b'{"a":1}', name="y", media_type="application/json", format_version="t@1").uri == ref.uri
    assert store.get(ref) == b'{"a":1}'
    (tmp_path / ref.digest.value[:2] / ref.digest.value).write_bytes(b"tampered")
    with pytest.raises(Exception, match="digest"):
        store.get(ref)


def test_budget_dimensions():
    from formal_lab_contracts import Budget, BudgetUsage
    from formal_lab_runtime.engine import budget_exhausted

    b = Budget(max_steps=10, max_wall_seconds=5, max_model_calls=3, max_tokens=100)
    rule_dims = ["steps", "wall_seconds"]
    llm_dims = [*rule_dims, "model_calls", "tokens"]
    assert budget_exhausted(b, BudgetUsage(steps=9, wall_seconds=4.9), rule_dims) is None
    assert "step" in budget_exhausted(b, BudgetUsage(steps=10), rule_dims)
    assert "wall-clock" in budget_exhausted(b, BudgetUsage(wall_seconds=5.0), rule_dims)
    many_calls = BudgetUsage(model_calls=3, input_tokens=90, output_tokens=20)
    assert budget_exhausted(b, many_calls, rule_dims) is None  # not an applicable dimension for rule runs
    assert "model-call" in budget_exhausted(b, many_calls, llm_dims)
    assert "token" in budget_exhausted(b, BudgetUsage(model_calls=1, input_tokens=90, output_tokens=20), llm_dims)
