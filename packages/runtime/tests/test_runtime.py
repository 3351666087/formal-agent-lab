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


def test_registry_rejects_incompatible_interface_version(reg):
    d = reg.get(("formal-lab.eval.generic", "1.0.0")).descriptor.model_copy(
        update={"plugin_id": "x.y", "interface_version": "2"})
    from formal_lab_runtime import PluginRegistry

    with pytest.raises(VersionMismatch):
        PluginRegistry().register(PluginRegistration(d, lambda c, s: None))


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
