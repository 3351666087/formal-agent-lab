"""A4 evidence: turns, joint rounds, the subprocess environment adapter and a hand-checkable paired report.

  turns        warehouse, receiver limited to put-away: idle turns (PASSED / skipped) while the picker advances, in
               round-robin and in joint batches; the receiver retired by its own budget while the picker finishes;
               and the two ways the whole experiment ends instead (every participant retired; no action under FAIL);
  recovery     a joint run stopped inside a round (after a proposal, before the submission), continued from JSON in
               fresh components: the same trajectory and batches as the uninterrupted run;
  subprocess   the SDK contract check of formal-lab.example.subprocess-world (session / request identity, idempotent
               re-send, one world step per batch, world-step report, snapshot, cleanup); batches against the child's
               own world-step log; automatic participants recorded apart; restore by loading vs rebuilding; timeout;
  paired       a report from known inputs, every number recomputed by plain arithmetic (written as JSON + Markdown).

Writes $FAL_EVIDENCE_DIR/a4-rounds.json and a4-paired-report.md; reports through check_result.py.
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_result import CheckResult

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / os.environ.get("FAL_EVIDENCE_DIR", "docs/execution/evidence/phase4")

from formal_lab_contracts import MetricDefinition, MetricResult, ScenarioManifest  # noqa: E402
from formal_lab_example_warehouse.scenarios import JOINT, package, receiver_and_picker  # noqa: E402
from formal_lab_runtime import default_registry, make_manifest, resume_local, run_local  # noqa: E402

SUB = {"plugin_id": "formal-lab.example.subprocess-world", "version": "1.0.0"}


def wh(turns=None, *, receiver_budget=None, picker_budget=None, on_no_action=None, env=None, run_id="run_a4"):
    pkg, reg = package(), default_registry()
    base = receiver_and_picker(pkg, turns=turns).model_dump(mode="json")
    base["participants"][0]["scope"] = {"action_types": ["putaway"]}
    if receiver_budget:
        base["participants"][0]["budget"] = receiver_budget
    if picker_budget:
        base["participants"][1]["budget"] = picker_budget
    if on_no_action:
        base["termination"]["on_no_action"] = on_no_action
    if env:
        base["environment"] = env
    m = make_manifest(run_id=run_id, project_id="a4", scenario=ScenarioManifest.model_validate(base), package=pkg,
                      registry=reg)
    return m, pkg, reg


def counts(res) -> dict[str, Any]:
    acted = Counter(s.actor_id for s in res.steps if s.proposal)
    skipped = Counter((e.actor_id, bool(e.payload.get("retired"))) for e in res.events
                      if e.event_type.value == "TURN_SKIPPED")
    members = Counter((mm["actor_id"], mm["status"]) for e in res.events if e.event_type.value == "BATCH_SUBMITTED"
                      for mm in e.payload["batch"]["members"])
    return {"status": res.status.value, "termination": str(res.termination_reason), "reason": (res.reason or "")[:120],
            "global_steps": len(res.steps), "acted": dict(acted),
            "skipped": {f"{a}{' (retired)' if r else ''}": n for (a, r), n in skipped.items()},
            "batch_members": {f"{a}:{s}": n for (a, s), n in members.items()},
            "batches": sum(1 for e in res.events if e.event_type.value == "BATCH_SUBMITTED"),
            "world_steps": sum(1 for e in res.events if e.event_type.value == "WORLD_STEPPED"),
            "turn_state": {k: res.carry["turn"].get(k) for k in ("skipped", "retired", "actor_steps")}}


def turns_section() -> dict[str, Any]:
    out = {}
    for label, kw in (("round_robin_idle", {}), ("joint_idle", {"turns": JOINT}),
                      ("receiver_retired", {"receiver_budget": {"max_steps": 2}}),
                      ("all_retired_run_ends", {"receiver_budget": {"max_steps": 2}, "picker_budget": {"max_steps": 3}}),
                      ("no_action_fails_run", {"on_no_action": "FAIL"})):
        m, pkg, reg = wh(run_id=f"run_a4_{label}", **kw)
        out[label] = counts(run_local(m, pkg, reg))
    return out


def recovery_section() -> dict[str, Any]:
    m, pkg, reg = wh(JOINT, run_id="run_a4_resume")
    full = run_local(m, pkg, reg)
    state = run_local(m, pkg, reg, stop_after=5)  # step 5: a proposal inside round 3, the batch still open
    open_batch = (state.carry.batch or {}).get("record", {})
    res = resume_local(json.loads(json.dumps(state.to_json())), pkg, reg)

    def traj(r):
        return [(s.step, s.actor_id, s.proposal.action.model_dump(mode="json") if s.proposal else None,
                 s.outcome.status.value if s.outcome else None) for s in r.steps]

    def batches(r):
        return [(e.payload["batch"]["round"], e.payload["batch"]["world_step"],
                 [(mm["actor_id"], mm["status"]) for mm in e.payload["batch"]["members"]])
                for e in r.events if e.event_type.value == "BATCH_SUBMITTED"]

    return {"stopped_after_step": 5, "open_batch_at_stop": {"round": open_batch.get("round"),
                                                             "status": open_batch.get("status"),
                                                             "members": len(open_batch.get("members", []))},
            "same_trajectory": traj(res) == traj(full), "same_batches": batches(res) == batches(full),
            "uninterrupted": counts(full), "resumed": counts(res)}


def subprocess_section(work: Path) -> dict[str, Any]:
    from formal_lab_example_subprocess import SubprocessWorldEnvironment
    from formal_lab_runtime.engine import RuntimeServices
    from formal_lab_sdk.plugin_testing import check_environment

    report = check_environment((SUB["plugin_id"], SUB["version"]), {})
    out: dict[str, Any] = {"contract_check": report.as_dict()}
    log = work / "world.jsonl"
    m, pkg, reg = wh(JOINT, env={"plugin": SUB, "config": {"world_log": str(log), "automatic": [
        {"actor_id": "clock", "actions": [{"action_type": "tick", "params": {}}]}]}}, run_id="run_a4_sub")
    res = run_local(m, pkg, reg)
    batches = [e.payload["batch"] for e in res.events if e.event_type.value == "BATCH_SUBMITTED"]
    worlds = [e.payload for e in res.events if e.event_type.value == "WORLD_STEPPED"]
    lines = [json.loads(x) for x in log.read_text().splitlines()]
    out["world_log"] = {"run": counts(res), "batches": [(b["round"], b["world_step"]) for b in batches],
                        "log": [(x["world_step"], x["actors"], x["automatic"]) for x in lines],
                        "match": [b["world_step"] for b in batches] == [x["world_step"] for x in lines]
                        == [w["world_step"] for w in worlds],
                        "automatic_applied": sum(1 for w in worlds for a in w["automatic"] if a["status"] == "APPLIED"),
                        "automatic_in_members": any(mm["actor_id"] == "clock" for b in batches
                                                    for mm in b["members"])}
    reg2 = default_registry()
    driver = reg2.create(reg2.driver_for(pkg.semantic_profile).descriptor.ref(), {}, RuntimeServices(pkg))
    services = RuntimeServices(pkg, loaded=driver.load(pkg))
    paths = {}
    for load in (True, False):
        env = SubprocessWorldEnvironment({"backend_load_state": load}, services)
        env.reset(m.scenario, pkg, run_id="run_a4_rb", seed=0)
        snap, truth = env.snapshot(), env.truth_state()
        other = SubprocessWorldEnvironment({"backend_load_state": load}, services)
        other.restore(snap)
        paths["load" if load else "rebuild"] = {"recovery_mode": other.session().recovery_modes,
                                                "same_state": other.truth_state() == truth,
                                                "same_digest": other.snapshot().digest == snap.digest}
        env.close()
        other.close()
    out["restore_paths"] = paths
    env = SubprocessWorldEnvironment({"timeout_s": 0.5}, services)
    env.reset(m.scenario, pkg, run_id="run_a4_to", seed=0)
    pid, t0 = env.pid, time.monotonic()
    try:
        env._request("sleep", {"seconds": 5})
        timed = "no timeout"
    except Exception as exc:
        timed = type(exc).__name__
    waited = time.monotonic() - t0
    try:
        os.kill(pid, 0)
        alive = os.waitpid(pid, os.WNOHANG)[0] != pid
    except (ProcessLookupError, ChildProcessError):
        alive = False
    out["timeout"] = {"raised": timed, "waited_s": round(waited, 2), "old_child_alive": alive}
    env.close()
    return out


COST = MetricDefinition(metric_id="delay_cost", label="cost", unit="cost", direction="LOWER_IS_BETTER",
                        aggregation="MEAN", observable="Σ late_cost × tardiness per order", window="whole run")
RULE = {0: 10.0, 1: 12.0, 2: 8.0, 3: 11.0, 4: 9.0}
Z3 = {0: 7.0, 1: 9.0, 2: 8.0, 3: None, 4: 5.0}


def paired_section() -> tuple[dict[str, Any], str]:
    from formal_lab_eval.experiments import CellKey, CellResult, build_report, conclusions, to_markdown

    def cell(strategy, seed, value, status="SUCCEEDED", reason=None, reused=False):
        key = CellKey(scenario="sc", participants=strategy, backend="scenario", rules="scenario", model="m@1",
                      ablation="none", budget="scenario-default", seed=seed, split="acceptance")
        metrics = {} if value is None else {"delay_cost": MetricResult(metric_id="delay_cost", metric_version="1",
                                                                       subject=f"{strategy}{seed}", value=value,
                                                                       status="OK")}
        return CellResult(cell_id=f"{strategy}-{seed}", key=key, run_id=f"run_{strategy}_{seed}", status=status,
                          termination_reason="JOINT_GOAL_REACHED" if status == "SUCCEEDED" else "FAILED",
                          metrics=metrics, labels={"participants": strategy}, status_reason=reason,
                          reused_from={"matrix_id": "mx_a"} if reused else None,
                          reuse_note="same full configuration completed in mx_a" if reused else None,
                          participants_digest=strategy, sampling="DETERMINISTIC")

    cells = [cell("rule", s, v, reused=s < 2) for s, v in RULE.items()]
    cells += [cell("z3", s, v) if v is not None else cell("z3", s, None, "FAILED", "worker error: solver crashed")
              for s, v in Z3.items()]
    report = build_report([COST], {"delay_cost": "evaluator (known inputs)"}, cells)
    report["conclusions"] = conclusions(report, [COST])
    sec = report["splits"]["acceptance"]
    cmp = next(c for c in sec["comparisons"] if not c.get("skipped"))
    # by hand: pairs on seeds 0, 1, 2, 4 (z3 seed 3 failed); diffs z3 − rule
    diffs = [Z3[s] - RULE[s] for s in sorted(RULE) if Z3[s] is not None]
    hand = {"pairs": len(diffs), "diffs": diffs, "mean_diff": statistics.fmean(diffs), "unpaired": 1,
            "success": f"{sum(1 for c in cells if c.status == 'SUCCEEDED')}/{len(cells)}",
            "better": "z3 (lower cost; mean difference < 0)", "reading": "ENGINEERING (4 pairs < 6)"}
    got = {"pairs": cmp["n_pairs"], "diffs": [p["diff"] for p in cmp["pairs"]], "mean_diff": cmp["mean_diff_b_minus_a"],
           "unpaired": cmp["unpaired"], "success": f"{sec['outcomes']['success']['numerator']}/"
                                                    f"{sec['outcomes']['success']['denominator']}",
           "better": cmp["better"], "reading": cmp["reading"], "unpaired_detail": cmp["unpaired_detail"]}
    return {"inputs": {"rule": RULE, "z3": Z3}, "hand": hand, "report": got,
            "outcomes": sec["outcomes"]}, to_markdown(report, "A4 paired report (known inputs)", [COST])


def main() -> int:
    r = CheckResult("p4-a4-rounds")
    work = Path(tempfile.mkdtemp(prefix="a4-evidence-"))
    turns, recovery = turns_section(), recovery_section()
    sub = subprocess_section(work)
    paired, md = paired_section()
    c = r.check
    rr, jt, ret = turns["round_robin_idle"], turns["joint_idle"], turns["receiver_retired"]
    c("idle_participant_does_not_stop_the_other", rr["status"] == "SUCCEEDED" and rr["skipped"].get("receiver", 0) > 0
      and rr["acted"].get("picker", 0) > 0 and jt["status"] == "SUCCEEDED"
      and jt["batch_members"].get("receiver:PASSED", 0) > 0 and jt["batches"] == jt["world_steps"],
      f"round-robin: receiver acted {rr['acted'].get('receiver')} / idle {rr['skipped'].get('receiver')}, picker "
      f"acted {rr['acted'].get('picker')}; joint: receiver PASSED {jt['batch_members'].get('receiver:PASSED')} "
      f"in {jt['batches']} batches = {jt['world_steps']} world steps")
    c("retire_is_not_run_end", ret["status"] == "SUCCEEDED" and ret["skipped"].get("receiver (retired)") == 1
      and ret["turn_state"]["retired"] == ["receiver"], f"receiver retired after {ret['acted'].get('receiver')} "
      f"step(s); picker finished: {ret['termination']}")
    end, fail = turns["all_retired_run_ends"], turns["no_action_fails_run"]
    c("run_end_is_distinct", "ACTOR_BUDGETS_EXHAUSTED" in end["termination"]
      and "NO_APPLICABLE_ACTION" in fail["termination"],
      f"all retired → {end['termination']}; no action under FAIL → {fail['termination']}")
    c("mid_round_recovery", recovery["same_trajectory"] and recovery["same_batches"]
      and recovery["open_batch_at_stop"]["status"] == "OPEN", str(recovery["open_batch_at_stop"]))
    cc = sub["contract_check"]
    c("subprocess_contract_check", cc["ok"], "; ".join(f"{s['name']}: {s['detail'][:50]}" for s in cc["stages"]))
    wl = sub["world_log"]
    c("one_world_step_per_batch", wl["match"] and wl["automatic_applied"] > 0 and not wl["automatic_in_members"],
      f"{len(wl['batches'])} batches = {len(wl['log'])} logged world steps; automatic actions "
      f"{wl['automatic_applied']} recorded apart from members")
    rp = sub["restore_paths"]
    c("restore_load_or_rebuild", all(v["same_state"] and v["same_digest"] for v in rp.values())
      and rp["load"]["recovery_mode"] == ["SNAPSHOT"] and rp["rebuild"]["recovery_mode"] == ["RESEED"], str(rp))
    to = sub["timeout"]
    c("timeout_kills_the_child", to["raised"] == "Timeout" and to["waited_s"] < 3 and not to["old_child_alive"],
      str(to))
    h, g = paired["hand"], paired["report"]
    c("paired_report_hand_check", (h["pairs"], h["diffs"], h["mean_diff"], h["unpaired"], h["success"])
      == (g["pairs"], g["diffs"], g["mean_diff"], g["unpaired"], g["success"]) and g["better"] == "z3"
      and g["reading"] == "ENGINEERING" and g["unpaired_detail"][0]["missing"] == "b",
      f"pairs {g['pairs']}, diffs {g['diffs']}, mean {g['mean_diff']}, unpaired {g['unpaired']} "
      f"({g['unpaired_detail'][0]['b'] if g['unpaired_detail'] else ''}), success {g['success']}")
    EV.mkdir(parents=True, exist_ok=True)
    (EV / "a4-paired-report.md").write_text(md)
    out = EV / "a4-rounds.json"
    out.write_text(json.dumps({"deliverable": "phase4A-A4", "turns": turns, "recovery": recovery,
                               "subprocess_environment": sub, "paired_report": paired,
                               "conclusion": {a["id"]: a["holds"] for a in r.assertions}},
                              indent=2, ensure_ascii=False, default=str) + "\n")
    r.evidence(out)
    r.evidence(EV / "a4-paired-report.md")
    return r.finish()


if __name__ == "__main__":
    sys.exit(main())
