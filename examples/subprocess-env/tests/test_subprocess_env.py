"""The subprocess environment adapter (phase 4A, A4): a world in its own process behind the Environment interface,
checked by the SDK contract check and by the cases a later adapter has to handle — recovery or rebuild by backend
capability, timeouts, cleanup, one world step per batch and automatic participants recorded apart."""

from __future__ import annotations

import gc
import json
import os
import time

import pytest
from formal_lab_contracts import ScenarioManifest
from formal_lab_contracts.errors import NonRetryableFailure, Timeout
from formal_lab_example_subprocess import ENV_ID, SubprocessWorldEnvironment
from formal_lab_example_warehouse.scenarios import JOINT, package, receiver_and_picker
from formal_lab_runtime import default_registry, make_manifest, run_local
from formal_lab_runtime.engine import RuntimeServices
from formal_lab_sdk.plugin_testing import check_environment

REF = {"plugin_id": ENV_ID, "version": "1.0.0"}


@pytest.fixture(scope="module")
def pkg():
    return package()


def gone(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    done, _ = os.waitpid(pid, os.WNOHANG)
    return done == pid


def env_for(pkg, **cfg) -> SubprocessWorldEnvironment:
    reg = default_registry()
    driver = reg.create(reg.driver_for(pkg.semantic_profile).descriptor.ref(), {}, RuntimeServices(pkg))
    return SubprocessWorldEnvironment(cfg, RuntimeServices(pkg, loaded=driver.load(pkg)))


def scenario(pkg) -> ScenarioManifest:
    return receiver_and_picker(pkg, turns=JOINT)


def test_contract_check_covers_the_declared_capabilities():
    report = check_environment((ENV_ID, "1.0.0"), {})
    assert report.ok, report.failures()
    names = {s.name: s.detail for s in report.stages}
    assert "applied once" in names["idempotent re-send"] and "one batch = one world step" in names["batch step"]
    assert names["world step report"].startswith("world step") and "subproc-" in names["session identity"]
    assert "exited" in names["cleanup"] or "gone" in names["cleanup"]


def test_restore_loads_or_rebuilds_by_backend_capability(pkg):
    for load_state in (True, False):
        env = env_for(pkg, backend_load_state=load_state)
        sc = scenario(pkg)
        obs = env.reset(sc, pkg, run_id="run_rb", seed=0)
        loaded = env.services.loaded_model()
        cands = [c for c in loaded.candidates(loaded.belief(obs)) if str(c.belief_applicability) == "APPLICABLE"]
        from formal_lab_contracts import ActionProposal

        prop = ActionProposal(proposal_id="p", run_id="run_rb", step_id="s1", step=1, actor_id="receiver",
                              action=cands[0].action, based_on_revision=0,
                              source={"kind": "RULE", "strategy": REF}, rationale="t")
        env.step_batch([prop], operation_id="b1")
        snap, truth = env.snapshot(), env.truth_state()
        other = env_for(pkg, backend_load_state=load_state)
        other.restore(snap)
        assert other.truth_state() == truth and other.snapshot().digest == snap.digest
        assert other.session().recovery_modes == (["SNAPSHOT"] if load_state else ["RESEED"])
        if not load_state:  # a rebuild must reproduce the snapshot, or the restore fails
            bad = snap.model_copy(deep=True)
            bad.data["history"] = []
            from formal_lab_contracts import digest_of

            bad = bad.model_copy(update={"digest": digest_of(bad.data)})
            with pytest.raises(NonRetryableFailure, match="rebuild diverged"):
                env_for(pkg, backend_load_state=False).restore(bad)
        env.close()
        other.close()


def test_a_child_that_does_not_answer_is_killed_and_replaced(pkg):
    env = env_for(pkg, timeout_s=0.5)
    env.reset(scenario(pkg), pkg, run_id="run_to", seed=0)
    snap, first = env.snapshot(), env.pid
    t0 = time.monotonic()
    with pytest.raises(Timeout):
        env._request("sleep", {"seconds": 5})
    assert time.monotonic() - t0 < 3 and gone(first)
    with pytest.raises(NonRetryableFailure, match="before reset/restore"):
        env.observe("picker")  # a new child has no state: it is never mistaken for the old one
    env.restore(snap)  # what the kernel does: restore the pre-step snapshot
    assert env.observe("picker").state_revision == 0
    assert env.pid != first and len(env.sessions) == 2
    env.close()


def test_no_child_outlives_its_adapter(pkg):
    env = env_for(pkg)
    env.reset(scenario(pkg), pkg, run_id="run_gc", seed=0)
    pid = env.pid
    del env
    gc.collect()
    deadline = time.monotonic() + 5
    while not gone(pid) and time.monotonic() < deadline:
        time.sleep(0.1)
    assert gone(pid)


def test_batches_match_the_worlds_own_steps_and_automatic_participants_are_recorded_apart(pkg, tmp_path):
    log = tmp_path / "world.jsonl"
    base = scenario(pkg).model_dump(mode="json")
    base["environment"] = {"plugin": REF, "config": {
        "world_log": str(log), "automatic": [{"actor_id": "clock", "actions": [{"action_type": "tick",
                                                                                 "params": {}}]}]}}
    sc = ScenarioManifest.model_validate(base)
    reg = default_registry()
    m = make_manifest(run_id="run_sub_auto", project_id="t", scenario=sc, package=pkg, registry=reg)
    res = run_local(m, pkg, reg)
    batches = [e.payload["batch"] for e in res.events if e.event_type.value == "BATCH_SUBMITTED"]
    worlds = [e.payload for e in res.events if e.event_type.value == "WORLD_STEPPED"]
    lines = [json.loads(x) for x in log.read_text().splitlines()]
    assert res.status.value in ("SUCCEEDED", "BUDGET_EXHAUSTED", "FAILED") and batches
    assert [b["world_step"] for b in batches] == [w["world_step"] for w in worlds] == [x["world_step"] for x in lines]
    assert all(w["source"] == "environment report" for w in worlds)
    assert all(a["actor_id"] == "clock" for w in worlds for a in w["automatic"])
    assert any(a["status"] == "APPLIED" for w in worlds for a in w["automatic"])
    members = {mm["actor_id"] for b in batches for mm in b["members"]}
    assert "clock" not in members  # the automatic participant is not a batch member
