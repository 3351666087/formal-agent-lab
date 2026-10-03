"""Phase 4B (B2) with the CAGE toolchain (marked `cage`, skipped without the fal-cage venv): the session worker, the
platform adapter's refusals and its rebuild check, and native vs platform paths on a short episode."""

from __future__ import annotations

import json
import os
import subprocess

import pytest
from formal_lab_env_cage import adapter, bridge, model, scenarios, trajectory

pytestmark = pytest.mark.cage
_UNAVAILABLE = bridge.available()
needs_cage = pytest.mark.skipif(_UNAVAILABLE is not None, reason=f"CAGE toolchain unavailable: {_UNAVAILABLE}")


class Session:
    def __init__(self):
        self.p = subprocess.Popen([str(bridge.locate()), str(bridge.WORKER), "serve"], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1,
                                  env={**os.environ, "PYTHONWARNINGS": "ignore"})
        self.n = 0

    def __call__(self, op, args=None):
        self.n += 1
        self.p.stdin.write(json.dumps({"id": self.n, "op": op, "args": args or {}}) + "\n")
        self.p.stdin.flush()
        answer = json.loads(self.p.stdout.readline())
        assert answer["id"] == self.n
        return answer

    def close(self):
        self("close")
        self.p.wait(timeout=10)


@needs_cage
def test_session_steps_once_per_request_and_refuses_undeclared_actions():
    s = Session()
    try:
        assert s("hello")["result"]["protocol"] == adapter.PROTOCOL
        s("reset", {"seed": 4, "steps": 10})
        o = s("observe", {"agent": "blue_agent_0"})["result"]
        assert o["world_step"] == 0 and o["alerts"] == []  # the step-0 inventory is not an alert
        host = o["allowed_hosts"][0]
        first = s("step", {"operation_id": "a", "actions": {"blue_agent_0": {"name": "Restore", "hostname": host}}})
        assert first["result"]["record"]["world_step"] == 1
        busy = s("step", {"operation_id": "b", "actions": {"blue_agent_0": {"name": "Monitor"}}})["result"]
        assert busy["record"]["blue"]["blue_agent_0"]["started"] is False  # Restore takes 5 ticks
        again = s("step", {"operation_id": "b", "actions": {"blue_agent_0": {"name": "Monitor"}}})["result"]
        assert again["replayed"] and again["record"]["world_step"] == 2  # the same id is answered, not applied
        bad = s("step", {"operation_id": "c", "actions": {"blue_agent_0": {"name": "Shell"}}})
        assert not bad["ok"] and "not a declared blue action" in bad["error"]["message"]
        other = sorted(set(model.package(bridge.describe()).payload.data["hosts"]) - set(o["allowed_hosts"]))[0]
        out = s("step", {"operation_id": "d", "actions": {"blue_agent_0": {"name": "Remove", "hostname": other}}})
        assert not out["ok"] and "action space" in out["error"]["message"]
        assert s("truth")["result"]["world_step"] == 2  # refused requests did not advance the world
    finally:
        s.close()


class _Services:
    def __init__(self, pkg):
        self.pkg = pkg

    def pinned_model(self):
        return self.pkg


@needs_cage
def test_rebuild_accepts_the_true_history_and_refuses_a_forged_one():
    from formal_lab_contracts import ActionProposal, digest_of
    from formal_lab_contracts.errors import NonRetryableFailure

    pkg = model.package(bridge.describe())
    sc = scenarios.scenario(pkg, policy="sleep", steps=12, seed=6)
    env = adapter.create(sc.environment.config, _Services(pkg))
    try:
        env.reset(sc, pkg, run_id="r", seed=6)
        for i in range(4):
            props = [ActionProposal(proposal_id=f"p{i}{a}", run_id="r", step_id=f"r:s{i}", step=i, actor_id=a,
                                    action={"action_type": "monitor"}, based_on_revision=i,
                                    source={"kind": "RULE", "strategy": {"plugin_id": "t", "version": "1.0.0"}})
                     for a in scenarios.BLUE]
            env.step_batch(props, operation_id=f"r:b{i}")
        assert env.rebuild_check()["equal"] is True
        snap = env.snapshot()
        forged = json.loads(json.dumps(snap.data))
        # Monitor vs the native Sleep changes no CybORG state and draws no randomness — the same world, so the
        # digest rightly matches; a decoy deployed instead is a different world (an extra process on that host)
        host = next(f.path[len("allowed["):-1] for f in env.observe("blue_agent_0").facts
                    if f.path.startswith("allowed[") and f.value is True)
        forged["history"][0]["actions"] = {"blue_agent_0": {"name": "DeployDecoy", "hostname": host}}
        bad = snap.model_copy(update={"data": forged, "digest": digest_of(forged)})
        other = adapter.create(sc.environment.config, _Services(pkg))
        with pytest.raises(NonRetryableFailure, match="rebuild diverged"):
            other.restore(bad)
        other.close()
    finally:
        env.close()


@needs_cage
def test_sleep_policy_equals_the_official_native_baseline(tmp_path):
    from formal_lab_runtime import default_registry, make_manifest, run_local

    reg = default_registry()
    pkg = model.package(bridge.describe())
    log = tmp_path / "w.jsonl"
    sc = scenarios.scenario(pkg, policy="sleep", steps=10, seed=8, world_log=str(log))
    res = run_local(make_manifest(run_id="run_cage_unit", project_id="t", scenario=sc, package=pkg, registry=reg),
                    pkg, reg)
    assert str(res.status) == "SUCCEEDED"
    platform = [json.loads(x) for x in log.read_text().splitlines()]
    cmp = trajectory.compare(bridge.native(seed=8, steps=10)["steps"], platform)
    assert cmp["equal"], cmp["first_difference"]
