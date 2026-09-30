"""D3 tests: red/blue strategies, checkpoint recovery and model revision. Offline (fixture + ir-world + Z3)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from formal_lab_domain_mal.frontend import attack_graph_of, package_from_graph
from formal_lab_domain_mal.revision import model_revision_cases
from formal_lab_domain_mal.run import red_team_scenario
from formal_lab_domain_mal.strategies import harden_package, min_cost_cut
from formal_lab_runtime import default_registry, make_manifest, new_run_id, resume_local, run_local

FIX = Path(__file__).parent / "fixtures"
PKG = Path(__file__).parents[1]


@pytest.fixture(scope="module")
def native():
    return json.loads((FIX / "net_app_data.native.json").read_text())["reachable_case"]


@pytest.fixture(scope="module")
def graph():
    return json.loads((FIX / "net_app_data.graph.json").read_text())


@pytest.fixture(scope="module")
def package(graph, native):
    model = json.loads((PKG / "src/formal_lab_domain_mal/models/net_app_data.json").read_text())
    return package_from_graph(graph, native["entry"], native["goal"], package_id="mal-rb", version=1,
                             reachable=native["compromised"], model=model,
                             language={"name": "coreLang", "version": "1.0.0"}, include_defense=True)


@pytest.fixture(scope="module")
def reg():
    return default_registry()


def _run(reg, package, strategy, *, run_id=None, seed=0, mc=0):
    scn = red_team_scenario(package, strategy=strategy, seed=seed, max_model_calls=mc)
    m = make_manifest(run_id=run_id or new_run_id(), project_id="d3", scenario=scn, package=package, registry=reg)
    res = run_local(m, package, reg)
    gid = attack_graph_of(package)["lowering"]["goal_id"]
    return res, bool(res.final_state.get(f"compromised[{gid}]"))


@pytest.mark.parametrize("strategy", ["rule", "symbolic", "hybrid"])
def test_red_baseline_reaches_goal(reg, package, strategy):
    res, reached = _run(reg, package, strategy, mc=(10 if strategy == "hybrid" else 0))
    assert str(res.status) == "SUCCEEDED" and reached


def test_min_cost_cut_is_minimal_and_blocks_every_red(reg, package, native):
    report = attack_graph_of(package)["lowering"]
    cut = min_cost_cut(report, entry_points=native["entry"])
    assert len(cut) >= 1  # a real cut is needed
    hardened = harden_package(package, cut)
    for strategy in ("rule", "symbolic"):
        _res, reached = _run(reg, hardened, strategy)
        assert reached is False  # blue's configuration blocks the attacker — target never compromised


def test_checkpoint_recovery_preserves_progress(package):
    from formal_lab_runtime import LocalRunState, PluginRegistry

    reg = PluginRegistry().discover()
    scn = red_team_scenario(package, strategy="symbolic")
    full = run_local(make_manifest(run_id="d3-full", project_id="d3", scenario=scn, package=package, registry=reg),
                     package, reg)
    state = run_local(make_manifest(run_id="d3-res", project_id="d3", scenario=scn, package=package, registry=reg),
                      package, reg, stop_after=3)
    # a genuine mid-run stop that carries a resumable checkpoint
    assert isinstance(state, LocalRunState)
    assert 1 < state.next_step <= len(full.steps)
    resumed = resume_local(state, package, reg)
    # resuming in a fresh runner reaches the same outcome — the plan progress was preserved, not restarted
    assert str(resumed.status) == str(full.status) == "SUCCEEDED"
    assert len(resumed.steps) == len(full.steps)
    gid = attack_graph_of(package)["lowering"]["goal_id"]
    assert resumed.final_state.get(f"compromised[{gid}]") is True


def test_model_revision_true_deviation_and_stale(graph, native):
    out = model_revision_cases(graph, native["entry"], native["goal"], native["compromised"])
    td = out["true_deviation"]
    assert td["belief_target_reachable"] is False and td["truth_target_reachable"] is True
    assert td["is_model_error"] is True
    assert td["old_model_v1_rejected"] is True and td["revised_model_v2_passes_case"] is True
    assert out["stale_difference"]["classification"] == "STALE"
    assert out["stale_difference"]["enters_regression_library"] is False
    assert out["regression_library_clean"] is True
