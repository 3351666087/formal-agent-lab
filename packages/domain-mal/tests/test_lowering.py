"""D1 offline: the committed coreLang fixture lowers to the deterministic IR and the three engines agree.

No MAL toolchain needed — this reads the captured attack graph and native reachable set, so it runs in CI.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from formal_lab_contracts import CheckQuery
from formal_lab_domain_mal.config import BusinessSLO, LabPolicy, TargetSecurity
from formal_lab_domain_mal.frontend import MalFrontend, attack_graph_of, package_from_graph
from formal_lab_model import Interpreter, bfs, check_model
from formal_lab_model.driver import IRFiniteDriver
from formal_lab_solver_z3.verifier import Z3Verifier

FIX = Path(__file__).parent / "fixtures"
PKG = Path(__file__).parents[1]


@pytest.fixture(scope="module")
def graph():
    return json.loads((FIX / "net_app_data.graph.json").read_text())


@pytest.fixture(scope="module")
def native():
    return json.loads((FIX / "net_app_data.native.json").read_text())["reachable_case"]


@pytest.fixture(scope="module")
def model():
    return json.loads((PKG / "src/formal_lab_domain_mal/models/net_app_data.json").read_text())


def _build(graph, entry, goal, reachable, model):
    return package_from_graph(graph, entry, goal, package_id="mal-test", version=1,
                             reachable=reachable, model=model, language={"name": "coreLang", "version": "1.0.0"})


def test_reachable_target_three_engines_agree(graph, native, model):
    entry, goal, reach = native["entry"], native["goal"], native["compromised"]
    pkg = _build(graph, entry, goal, reach, model)
    drv = IRFiniteDriver()
    assert drv.validate(pkg) == []
    drv.load(pkg)  # the platform driver compiles it

    interp = Interpreter(check_model(pkg.ir))
    ref = bfs(interp, interp.initial_state(), lambda s: interp.holds("target_reached", s), max_depth=60)
    z = Z3Verifier().check(pkg, CheckQuery(kind="GOAL_REACHABILITY", property_id="target_reached",
                                           bound={"max_steps": 60, "timeout_ms": 30000}))
    native_reached = goal in set(reach)
    assert native_reached is True
    assert ref.found is True
    assert z.verdict == "WITNESS" and z.witness.replay == "CONFIRMED"
    # the three engines agree on reachability
    assert native_reached == ref.found == (z.verdict == "WITNESS")
    # the witness is a real attack plan ending at the goal
    inv = {v: k for k, v in attack_graph_of(pkg)["lowering"]["id_map"].items()}
    plan = [inv[s.action.params["n"]] for s in z.witness.steps if getattr(s, "action", None)]
    assert plan[-1] == goal
    assert all(step in set(reach) for step in plan)


def test_no_entry_point_target_holds(graph, native, model):
    goal = native["goal"]
    pkg = _build(graph, [], goal, [], model)
    interp = Interpreter(check_model(pkg.ir))
    ref = bfs(interp, interp.initial_state(), lambda s: interp.holds("target_reached", s), max_depth=60)
    z = Z3Verifier().check(pkg, CheckQuery(kind="GOAL_REACHABILITY", property_id="target_reached",
                                           bound={"max_steps": 60, "timeout_ms": 30000}))
    assert ref.found is False
    assert z.verdict == "NO_WITNESS_WITHIN_BOUND"


def test_cheapest_attack_is_optimal(graph, native, model):
    from formal_lab_contracts import ObjectiveSpec

    entry, goal, reach = native["entry"], native["goal"], native["compromised"]
    pkg = _build(graph, entry, goal, reach, model)
    spec = ObjectiveSpec.model_validate({"objective_id": "cheap", "goal_property": "target_reached", "horizon": 60,
                                         "levels": [{"id": "cost", "model_objective": "attack_cost"}]})
    z = Z3Verifier().check(pkg, CheckQuery(kind="OPTIMIZE_OBJECTIVE", objective=spec,
                                           bound={"max_steps": 60, "timeout_ms": 30000}))
    assert z.verdict == "OPTIMAL"
    assert z.optimization.levels[0].value == 6  # attemptRead→successfulRead→read on app, then the same three on secret


def test_provenance_preserved(graph, native, model):
    entry, goal, reach = native["entry"], native["goal"], native["compromised"]
    pkg = _build(graph, entry, goal, reach, model)
    ag = attack_graph_of(pkg)
    assert ag["language"] == {"name": "coreLang", "version": "1.0.0"}
    assert ag["goal"] == goal and ag["entry_points"] == entry
    assert ag["model"]["name"] == "corelang-net-app-data"
    assert ag["graph_sha256"] and len(ag["native_reachable"]) == len(set(reach))
    assert pkg.ir.semantic_profile == "deterministic_finite_v1"


def test_frontend_compiles_json_envelope(graph, native, model):
    entry, goal, reach = native["entry"], native["goal"], native["compromised"]
    src_text = json.dumps({"language": {"name": "coreLang", "version": "1.0.0"}, "model": model,
                           "graph": graph, "entry_points": entry, "goal": goal, "reachable": reach})
    from formal_lab_contracts import ModelSource

    pkg = MalFrontend().compile(ModelSource(format="mal-attack-graph/v1", text=src_text),
                                package_id="mal-env", version=2)
    assert pkg.ir.semantic_profile == "deterministic_finite_v1"
    assert IRFiniteDriver().validate(pkg) == []


def test_platform_red_team_run_reaches_the_goal(graph, native, model):
    from formal_lab_domain_mal.frontend import attack_graph_of
    from formal_lab_domain_mal.run import run_red_team, run_summary

    entry, goal, reach = native["entry"], native["goal"], native["compromised"]
    pkg = _build(graph, entry, goal, reach, model)
    res = run_red_team(pkg)
    summary = run_summary(res, attack_graph_of(pkg)["lowering"]["id_map"])
    assert summary["status"] == "SUCCEEDED"
    assert summary["attack_path"][-1]["target"] == goal
    assert [s["action"] for s in summary["attack_path"]] == ["compromise"] * len(summary["attack_path"])


def test_config_roundtrip():
    lab = LabPolicy(allowed_assets=["app"], forbidden_steps=["app:read"], max_attack_steps=10, note="x")
    assert LabPolicy.from_dict(lab.to_dict()) == lab
    assert lab.permits("app:attemptRead", "app") is True
    assert lab.permits("app:read", "app") is False  # forbidden
    assert lab.permits("net:eavesdrop", "net") is False  # asset not allowed
    tgt = TargetSecurity(property_id="c", reach_forbidden="secret:read", kind="confidentiality")
    assert TargetSecurity.from_dict(tgt.to_dict()) == tgt
    slo = BusinessSLO(metric="cost", threshold=6, unit="steps")
    assert BusinessSLO.from_dict(slo.to_dict()) == slo
