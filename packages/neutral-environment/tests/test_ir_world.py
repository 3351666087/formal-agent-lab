from __future__ import annotations

import pytest
from formal_lab_contracts import ActionProposal, ScenarioManifest
from formal_lab_contracts.errors import Conflict, InvalidInput
from formal_lab_env import IRWorldEnvironment
from formal_lab_example_scheduling.scenarios import model_package, scenario


class _Services:
    def __init__(self, package):
        self.package = package

    def pinned_model(self):
        return self.package


def _proposal(sc: ScenarioManifest, step: int, action_type: str, **params) -> ActionProposal:
    return ActionProposal(proposal_id=f"r:s{step}:proposal", run_id="r", step_id=f"r:s{step}", step=step,
                          actor_id="dispatcher", action={"action_type": action_type, "params": params},
                          based_on_revision=0, source={"kind": "HUMAN", "strategy": {"plugin_id": "t", "version": "1.0.0"}})


@pytest.fixture(scope="module")
def pkg():
    return model_package()


def make_env(pkg, key: str, seed: int = 0):
    sc = scenario(key, pkg, seed=seed)
    from formal_lab_env.ir_world import create

    env = create(sc.environment.config, _Services(pkg))
    obs = env.reset(sc, pkg, run_id="r", seed=seed)
    return env, sc, obs


def test_reset_observe_step_and_truth_properties(pkg):
    env, sc, obs = make_env(pkg, "normal")
    assert obs.step == 0 and obs.state_revision == 0 and not obs.unknowns
    out = env.step(_proposal(sc, 1, "assign", op="o1_cut", m="m1"), operation_id="r:s1:apply")
    assert out.status == "APPLIED" and out.effect_applied and out.revision_after == 1
    assert "phase[o1_cut]" in out.result["written_paths"]
    assert out.result["properties"]["all_done"] is False and out.result["properties"]["machine_capacity"] is True
    rejected = env.step(_proposal(sc, 2, "assign", op="o1_cut", m="m2"), operation_id="r:s2:apply")
    assert rejected.status == "REJECTED" and rejected.effect_applied is False and rejected.revision_after == 1
    assert rejected.result["reason"] == "PRECONDITION_FALSE"
    assert env.observe("dispatcher").step == 2


def test_operation_idempotency_and_snapshot_restore(pkg):
    env, sc, _ = make_env(pkg, "normal")
    first = env.step(_proposal(sc, 1, "assign", op="o1_cut", m="m1"), operation_id="r:s1:apply")
    again = env.step(_proposal(sc, 1, "assign", op="o1_cut", m="m1"), operation_id="r:s1:apply")
    assert again == first and env.current_step == 1  # re-delivery does not advance the world
    snap = env.snapshot()
    env.step(_proposal(sc, 2, "advance"), operation_id="r:s2:apply")
    after = env.truth_state()
    env2 = make_env(pkg, "normal")[0]
    env2.restore(snap)
    assert env2.current_step == 1 and env2.truth_state() != after
    env2.step(_proposal(sc, 2, "advance"), operation_id="r:s2:apply")
    assert env2.truth_state() == after  # deterministic replay from the snapshot
    tampered = snap.model_copy(update={"data": {**snap.data, "config": {"observation": {"hidden": ["clock"]}}}})
    with pytest.raises(InvalidInput):
        env2.restore(tampered)


def test_observation_delay_produces_stale_facts_and_unknowns(pkg):
    env, sc, _ = make_env(pkg, "state-delay")
    env.step(_proposal(sc, 1, "assign", op="o1_cut", m="m1"), operation_id="r:s1:apply")
    obs = env.observe("dispatcher")
    unknown = {u.path: u for u in obs.unknowns}
    assert unknown["phase[o1_cut]"].reason == "OBSERVATION_DELAY"
    assert unknown["phase[o1_cut]"].last_known.value == "waiting"  # truth is already 'running'
    assert env.truth_state()["phase[o1_cut]"] == "running"
    assert {f.path for f in obs.facts} >= {"clock", "paused[m1]"}  # undelayed variables stay fresh


def test_truth_override_and_seeded_variation(pkg):
    env, _, _ = make_env(pkg, "expectation-mismatch")
    assert env._truth.families["degraded"].table["degraded[m2]"] is True
    a = make_env(pkg, "normal", seed=5)[0].truth_state()
    b = make_env(pkg, "normal", seed=5)[0].truth_state()
    c = make_env(pkg, "normal", seed=6)[0].truth_state()
    assert a == b and a != c
    assert all(1 <= a[f"proc_time[{op}]"] <= 9 for op in ("o1_cut", "o2_cut"))


def test_closed_environment_and_bad_config(pkg):
    env, sc, _ = make_env(pkg, "normal")
    env.close()
    with pytest.raises(Conflict):
        env.observe("dispatcher")
    with pytest.raises(InvalidInput):
        IRWorldEnvironment({"telepathy": True})
