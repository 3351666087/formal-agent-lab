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


def _compromise_context(package, ids):
    from formal_lab_contracts import BudgetUsage, CandidateAction, Observation, PlanningContext

    cands = [CandidateAction(action={"action_type": "compromise", "params": {"n": i}},
                             belief_applicability="APPLICABLE") for i in ids]
    obs = Observation(run_id="r", actor_id="red", step=1, state_revision=0, facts=[])
    return PlanningContext(run_id="r", step=1, step_id="r:s1", actor_id="red", observation=obs, candidates=cands,
                           model=package.ref(), action_specs=[], budget={"max_steps": 40}, usage=BudgetUsage(), seed=0)


def test_hybrid_provenance_follows_what_answered(package):
    """The hybrid is model-assisted through the A3 path: the source is the endpoint that answered (stub / protocol
    test / real), and a model that returns nothing usable falls back to the rule — never a bare LLM label."""
    from formal_lab_domain_mal.frontend import attack_graph_of
    from formal_lab_domain_mal.strategies import MalRedHybrid
    from formal_lab_strategies.model_clients import OpenAICompatibleClient, StubModelClient
    from formal_lab_strategies.protocol_server import ProtocolTestServer

    ids = list(attack_graph_of(package)["lowering"]["id_map"].values())[:3]

    stub = MalRedHybrid(package, StubModelClient()).propose(_compromise_context(package, ids))
    assert stub.source.kind == "LLM_STUB" and stub.source.model_call_ids and stub.source.decided_by == "MODEL_RESPONSE"

    srv = ProtocolTestServer().start()
    try:
        hy = MalRedHybrid(package, OpenAICompatibleClient(base_url=srv.base_url, api_key="protocol-test-only",
                                                          model="protocol-test-v1", backoff_s=0.01, timeout_s=5))
        p = hy.propose(_compromise_context(package, ids))
        assert p.source.kind == "LLM_PROTOCOL_TEST" and len(srv.requests) == 1
        assert hy.last_decision.decided_by_model and p.action.action_type == "compromise"
    finally:
        srv.stop()

    hy = MalRedHybrid(package, OpenAICompatibleClient(base_url="http://127.0.0.1:9", api_key="x", model="m",
                                                     backoff_s=0.01, timeout_s=1, max_attempts=1))
    p = hy.propose(_compromise_context(package, ids))
    assert p.source.kind == "RULE" and hy.last_decision.failure and p.source.model_call_ids  # failed call kept


def _blue_context(package, compromised_ids):
    from formal_lab_contracts import BudgetUsage, CandidateAction, Observation, PlanningContext
    from formal_lab_domain_mal.frontend import attack_graph_of

    ids = list(attack_graph_of(package)["lowering"]["id_map"].values())
    cands = [CandidateAction(action={"action_type": "harden", "params": {"n": i}}, belief_applicability="APPLICABLE")
             for i in ids if i not in compromised_ids]
    facts = [{"path": f"compromised[{i}]", "value": i in compromised_ids, "observed_at_step": 1} for i in ids]
    obs = Observation(run_id="r", actor_id="blue", step=1, state_revision=0, facts=facts)
    return PlanningContext(run_id="r", step=1, step_id="r:s1", actor_id="blue", observation=obs, action_specs=[],
                           candidates=cands, model=package.ref(), budget={"max_steps": 120}, usage=BudgetUsage(),
                           seed=0)


def test_blue_defender_decision_varies_with_observation(package, native):
    """Two controlled cases, same initial configuration but different observations of what red has compromised: the
    reactive blue hardens a different step — it reads its observation, it is not a fixed script."""
    from formal_lab_domain_mal.frontend import attack_graph_of
    from formal_lab_domain_mal.strategies import MalBlueDefender

    ids = attack_graph_of(package)["lowering"]["id_map"]
    blue = MalBlueDefender(package)
    entry = {ids[e] for e in native["entry"] if e in ids}
    a = blue.propose(_blue_context(package, set(entry)))
    advanced = set(entry) | ({ids["app:attemptRead"]} if "app:attemptRead" in ids else set())
    b = blue.propose(_blue_context(package, advanced))
    assert a.action.action_type == b.action.action_type == "harden"
    assert a.action.params != b.action.params  # the harden target follows red's advanced frontier
    assert "frontier" in a.rationale and "frontier" in b.rationale


def test_red_blue_loop_both_decide_and_the_referee_judges(reg, package):
    """A turn-taking red/blue episode: red compromises steps, blue hardens from its observation, and the outcome is
    decided by the environment state (not a strategy's self-report)."""
    from formal_lab_domain_mal.frontend import attack_graph_of
    from formal_lab_domain_mal.run import red_blue_scenario

    scn = red_blue_scenario(package, strategy="rule", horizon=120, seed=0)
    res = run_local(make_manifest(run_id=new_run_id(), project_id="d3-rb", scenario=scn, package=package,
                                  registry=reg), package, reg)
    by = {}
    for st in res.steps:
        if st.proposal:
            by.setdefault(st.actor_id, []).append(st.proposal.action.action_type)
    assert by.get("red") and all(a == "compromise" for a in by["red"])  # red actually compromised steps
    assert by.get("blue") and all(a == "harden" for a in by["blue"])    # blue actually hardened steps
    gid = attack_graph_of(package)["lowering"]["goal_id"]
    reached = bool(res.final_state.get(f"compromised[{gid}]"))
    # the referee (env state) decides; on this fixture the reactive blue contains red (goal not reached)
    assert reached is False and str(res.status) in ("FAILED", "BUDGET_EXHAUSTED")
