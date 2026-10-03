"""B2 evidence (phase 4B): CAGE Challenge 4 as a platform environment — local, toolchain-backed checks.

In order (each result computed here, nothing asserted from source code):
  1. toolchain — CybORG version, the cage-challenge-4 checkout's full revision and licence, a digest of every package
     installed in the isolated venv, the Scenario4 host universe and official agent classes;
  2. native vs platform, world step by world step (state + RNG digests included):
       sleep  (platform)  vs the official baseline (native SleepAgent, no external action);
       monitor (platform) vs the native direct path with the same Monitor actions (CybORG 4.0's MonitorAgent is a
       CAGE-2-era class that Scenario4's generator cannot build — recorded, not worked around);
       react  (platform, dev and holdout) vs the native direct path driven with the same blue actions;
  3. mapping — who the platform controls and who acts natively, per world step, with one world step spelled out;
  4. recovery — a run stopped inside a round and resumed in a new process (rebuild + digest check) equals the
     uninterrupted run; a worker lost between world steps is rebuilt from the committed log; after a lost answer the
     kernel's path (restore the pre-step snapshot, execute once) reaches the uninterrupted world; a forged history
     is refused ("rebuild diverged").
Writes $FAL_EVIDENCE_DIR/b2-cage.json (default docs/execution/evidence/phase4); reports through check_result.py.
The platform path (API + Temporal worker + matrix) is checked by tests/integration/test_cage_platform.py.
"""

from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_result import CheckResult

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / os.environ.get("FAL_EVIDENCE_DIR", "docs/execution/evidence/phase4")
STEPS = 30


def _toolchain(bridge) -> dict:
    py = bridge.locate()
    listing = subprocess.run([str(py), "-c", "import importlib.metadata as m, json; print(json.dumps(sorted("
                              "(d.metadata['Name'], d.version) for d in m.distributions())))"],
                             capture_output=True, text=True, timeout=120).stdout.strip()
    dists = json.loads(listing or "[]")
    src = Path(os.environ.get("FAL_CAGE_SRC", Path.home() / "cage-src"))
    lic = (src / "LICENSE.txt").read_text().splitlines()[:3] if (src / "LICENSE.txt").exists() else []
    v = bridge.versions()
    return {"cyborg_version": v["cyborg_version"], "scenario": v["scenario"], "python": v["python"],
            "cage_src_revision": v.get("cage_src_revision"), "cage_src_license": " ".join(x.strip() for x in lic),
            "key_packages": v["packages"], "venv_packages": len(dists),
            "venv_packages_sha256": hashlib.sha256(json.dumps(dists).encode()).hexdigest(),
            "venv_python": str(py)}


def _platform_run(pkg, reg, policy: str, variant: str, seed: int, log: Path, **kw):
    from formal_lab_contracts import PluginRef
    from formal_lab_env_cage import scenarios
    from formal_lab_runtime import make_manifest, run_local

    log.write_text("")
    sc = scenarios.scenario(pkg, policy=policy, variant=variant, steps=STEPS, seed=seed, world_log=str(log))
    m = make_manifest(run_id=f"run_b2_{policy}_{variant}_{seed}", project_id="b2", scenario=sc, package=pkg,
                      registry=reg, evaluators=[PluginRef(plugin_id="formal-lab.cage4.metrics", version="1.0.0")])
    return run_local(m, pkg, reg, **kw), m


def _det(metrics: dict) -> dict:
    return {k: v for k, v in metrics.items() if k != "wall_seconds"}  # elapsed time is not part of the episode


def _rows(log: Path) -> list[dict]:
    seen: dict[int, dict] = {}
    for line in log.read_text().splitlines():
        rec = json.loads(line)
        seen[rec["world_step"]] = rec
    return [seen[k] for k in sorted(seen)]


def main() -> int:
    r = CheckResult("p4-b2-native-platform")
    from formal_lab_env_cage import bridge, model, scenarios, trajectory

    why = bridge.available()
    if why:
        return r.blocked(f"CAGE toolchain unavailable: {why}")
    from formal_lab_runtime import default_registry

    reg = default_registry()
    tool = _toolchain(bridge)
    describe = bridge.describe()
    pkg = model.package(describe)
    work = Path(tempfile.mkdtemp(prefix="b2-", dir=ROOT / "var"))
    discovered = sorted(e.descriptor.plugin_id for e in reg.entries()
                        if e.descriptor.plugin_id.startswith(("formal-lab.env.cage4", "formal-lab.driver.cage4",
                                                              "formal-lab.cage4.")))

    # ---- 2. native vs platform
    paths = {}
    for name, policy, variant, native_kw in [
            ("sleep_vs_official_baseline", "sleep", "dev", {"blue_native": "SleepAgent"}),
            ("monitor_vs_same_actions", "monitor", "dev", None),  # CybORG's MonitorAgent cannot run in Scenario4
            ("react_dev_vs_same_actions", "react", "dev", None),
            ("react_holdout_vs_same_actions", "react", "holdout", None)]:
        log = work / f"{name}.jsonl"
        res, _ = _platform_run(pkg, reg, policy, variant, 1, log)
        platform = _rows(log)
        red = scenarios.VARIANTS[variant]
        if native_kw is None:
            native = bridge.native(seed=1, steps=STEPS, red=red, controlled=scenarios.BLUE,
                                   actions=trajectory.platform_actions(platform))["steps"]
            driven = "the platform run's committed blue actions"
        else:
            native = bridge.native(seed=1, steps=STEPS, red=red, **native_kw)["steps"]
            driven = f"native {native_kw['blue_native']} (no external action)"
        cmp = trajectory.compare(native, platform)
        paths[name] = {"platform_status": str(res.status), "native_driven_by": driven, "red": red,
                       **{k: cmp[k] for k in ("equal", "world_steps", "equal_world_steps", "first_difference",
                                              "termination", "reward_totals")},
                       "metrics": {m.metric_id: m.value for m in res.metrics}}
        if name == "react_dev_vs_same_actions":
            sample = next((st for st in platform if any(b.get("started") is False for b in st["blue"].values())),
                          platform[-1])
            mapping = {"world_steps": len(platform),
                       "platform_controlled": sorted(a for a, b in platform[0]["blue"].items() if b["controlled"]),
                       "native_automatic": {"red_agents_seen": sorted({a for st in platform for a in st["red"]}),
                                            "green": "EnterpriseGreenAgent (aggregated per world step)"},
                       "one_world_step": {"world_step": sample["world_step"], "blue": sample["blue"],
                                          "red": sample["red"], "green": sample["green"]},
                       "batch_semantics": "one JOINT_BATCH round = one CybORG parallel_step = one native world step"}
    for name, p in paths.items():
        r.check(f"native_equals_platform:{name}", p["equal"] and p["platform_status"] == "SUCCEEDED",
                f"{p['equal_world_steps']}/{p['world_steps']} world steps equal; first difference "
                f"{p['first_difference']}; rewards {p['reward_totals']}")

    # ---- 4a. stop inside a round, resume in a new process
    rec_a, rec_b = work / "uninterrupted.jsonl", work / "resumed.jsonl"
    full, _ = _platform_run(pkg, reg, "react", "dev", 5, rec_a)
    stopped, _ = _platform_run(pkg, reg, "react", "dev", 5, rec_b, stop_after=63)
    state_file = work / "state.json"
    state_file.write_text(json.dumps(stopped.to_json(), default=str))
    code = ("import json, sys, os\nfrom formal_lab_env_cage import bridge, model\nfrom formal_lab_runtime import "
            "default_registry\nfrom formal_lab_runtime.local_runner import resume_local\nreg = default_registry()\n"
            "pkg = model.package(bridge.describe())\nres = resume_local(json.load(open(sys.argv[1])), pkg, reg)\n"
            "print(json.dumps({'status': str(res.status), 'pid': os.getpid(), 'metrics': {m.metric_id: m.value "
            "for m in res.metrics}}))")
    out = subprocess.run([sys.executable, "-c", code, str(state_file)], capture_output=True, text=True, cwd=ROOT,
                         timeout=1800)
    resumed = json.loads(out.stdout.strip().splitlines()[-1]) if out.stdout.strip() else {"error": out.stderr[-800:]}
    cmp = trajectory.compare(_rows(rec_a), _rows(rec_b))
    recovery = {"stopped_after_global_step": 63, "resumed_in_new_process": resumed.get("pid") != os.getpid(),
                "status": resumed.get("status"), "trajectory_equal": cmp["equal"],
                "equal_world_steps": cmp["equal_world_steps"], "world_steps": cmp["world_steps"],
                "same_metrics_except_elapsed_time": _det(resumed.get("metrics") or {})
                == _det({m.metric_id: m.value for m in full.metrics})}
    r.check("resume_in_a_new_process_equals_uninterrupted", recovery["trajectory_equal"]
            and recovery["resumed_in_new_process"] and recovery["status"] == "SUCCEEDED"
            and recovery["same_metrics_except_elapsed_time"], str(recovery))

    # ---- 4b. a worker lost between world steps; 4c. a lost answer; 4d. a forged history
    lost = _lost_worker(pkg, reg, work)
    r.check("lost_worker_rebuilt_from_the_committed_log", lost["between"]["equal"]
            and lost["between"]["rebuilds"] == 1 and lost["between"]["sessions"] == 2, str(lost["between"]))
    r.check("lost_answer_restore_and_execute_once", lost["lost_answer"]["equal"]
            and lost["lost_answer"]["raised"] == "ResultUnknown", str(lost["lost_answer"]))
    r.check("forged_history_refused", lost["forged"]["refused"], lost["forged"]["detail"])
    r.check("plugins_discovered", {"formal-lab.env.cage4", "formal-lab.driver.cage4", "formal-lab.cage4.blue-sleep",
                                   "formal-lab.cage4.blue-monitor", "formal-lab.cage4.blue-react",
                                   "formal-lab.cage4.metrics"} <= set(discovered), ", ".join(discovered))
    r.check("toolchain_recorded", bool(tool["cage_src_revision"]) and tool["cyborg_version"].startswith("4"),
            f"CybORG {tool['cyborg_version']} @ {tool['cage_src_revision']}; {tool['venv_packages']} packages "
            f"sha256 {tool['venv_packages_sha256'][:12]}")

    EV.mkdir(parents=True, exist_ok=True)
    out_file = EV / "b2-cage.json"
    out_file.write_text(json.dumps({
        "deliverable": "phase4B-B2", "toolchain": tool, "plugins": discovered,
        "model": {"package_id": pkg.package_id, "profile": pkg.semantic_profile, "digest": pkg.digest.value,
                  "hosts": len(describe["hosts"]), "blue_actions": pkg.payload.data["blue_actions"],
                  "not_mapped": ["BlockTrafficZone", "AllowTrafficZone"],
                  "prediction": "applicability only — native effects not predicted (comparisons INSUFFICIENT_INFORMATION)"},
        "variants": {k: v for k, v in scenarios.VARIANTS.items()}, "steps_per_episode": STEPS,
        "native_classes": {"SleepAgent": "runnable — the official baseline",
                           "MonitorAgent": "not runnable as a Scenario4 blue class (constructor takes no name; monitors "
                                           "as agent 'Blue'): TypeError in EnterpriseScenarioGenerator",
                           "cc4BlueRandomAgent": "runnable, not mapped (draws from CybORG's RNG)"},
        "native_vs_platform": paths, "mapping": mapping, "recovery": recovery, "lost_worker": lost,
        "conclusion": {a["id"]: a["holds"] for a in r.assertions}}, indent=2, ensure_ascii=False, default=str) + "\n")
    r.evidence(out_file)
    return r.finish()


def _lost_worker(pkg, reg, work: Path) -> dict:
    """Adapter-level: (b) kill the CAGE worker between world steps and keep going; (c) lose the answer of a step
    after the worker applied it, then do what the kernel does — restore the pre-step snapshot, execute once;
    (d) a forged history is refused. Each is compared with an uninterrupted adapter on the same seed."""
    from formal_lab_contracts import ActionProposal, digest_of
    from formal_lab_contracts.errors import NonRetryableFailure, ResultUnknown
    from formal_lab_env_cage import adapter, scenarios

    class Svc:
        def pinned_model(self):
            return pkg

    sc = scenarios.scenario(pkg, policy="react", steps=STEPS, seed=9)

    def batch(i: int, action: dict) -> list:
        return [ActionProposal(proposal_id=f"p{i}{a}", run_id="r", step_id=f"r:s{i}", step=i, actor_id=a,
                               action=action, based_on_revision=i,
                               source={"kind": "RULE", "strategy": {"plugin_id": "e", "version": "1.0.0"}})
                for a in scenarios.BLUE]

    def fresh():
        e = adapter.create(sc.environment.config, Svc())
        e.reset(sc, pkg, run_id="r", seed=9)
        return e

    plan = [{"action_type": "monitor"}] * 8
    ref = fresh()
    for i, a in enumerate(plan):
        ref.step_batch(batch(i, a), operation_id=f"r:b{i}")
    want = ref._request("digest")
    ref.close()

    env = fresh()
    for i, a in enumerate(plan):
        if i == 4:
            os.kill(env.pid, signal.SIGKILL)  # the worker dies between world steps
            env._proc.wait(timeout=10)
        env.step_batch(batch(i, a), operation_id=f"r:b{i}")
    between = {"killed_before_world_step": 5, "equal": env._request("digest") == want, "rebuilds": len(env.rebuilds),
               "sessions": len(env.sessions)}
    env.close()

    env = fresh()
    for i, a in enumerate(plan[:5]):
        env.step_batch(batch(i, a), operation_id=f"r:b{i}")
    pre = env.snapshot()
    raised = None
    real = env._request

    def lossy(op, args=None, *, step=False):  # the worker applies world step 6, then its answer is lost
        if op == "step" and not lossy.fired:
            lossy.fired = True
            real(op, args, step=step)
            os.kill(env.pid, signal.SIGKILL)
            env._proc.wait(timeout=10)
            raise ResultUnknown("answer lost after the worker applied the world step (simulated at the pipe)")
        return real(op, args, step=step)

    lossy.fired = False
    env._request = lossy
    try:
        env.step_batch(batch(5, plan[5]), operation_id="r:b5")
    except (ResultUnknown, NonRetryableFailure) as exc:
        raised = type(exc).__name__
    env._request = real
    env.restore(pre)  # the kernel's recovery: back to the verified pre-step state ...
    for i, a in enumerate(plan[5:], start=5):  # ... and each remaining world step executed once (step 6 too)
        env.step_batch(batch(i, a), operation_id=f"r:b{i}")
    lost_answer = {"raised": raised, "equal": env._request("digest") == want,
                   "note": "the pipe to a killed worker breaks: ResultUnknown; restore = verified rebuild of the "
                           "pre-step state, then the step runs once"}
    env.close()

    env = fresh()
    for i, a in enumerate(plan[:4]):
        env.step_batch(batch(i, a), operation_id=f"r:b{i}")
    snap = env.snapshot()
    host = next(f.path[len("allowed["):-1] for f in env.observe("blue_agent_0").facts
                if f.path.startswith("allowed[") and f.value is True)
    forged = json.loads(json.dumps(snap.data))
    forged["history"][0]["actions"] = {"blue_agent_0": {"name": "DeployDecoy", "hostname": host}}
    other = adapter.create(sc.environment.config, Svc())
    try:
        other.restore(snap.model_copy(update={"data": forged, "digest": digest_of(forged)}))
        refused, detail = False, "a forged history was accepted"
    except NonRetryableFailure as exc:
        refused, detail = "rebuild diverged" in str(exc), str(exc)[:300]
    other.close()
    env.close()
    return {"between": between, "lost_answer": lost_answer, "forged": {"refused": refused, "detail": detail}}


if __name__ == "__main__":
    sys.exit(main())
