#!/usr/bin/env python3
"""Joint batches and per-participant planner input on the warehouse example (phase 3A, G4).

1. Batch: receiver + picker under JOINT_BATCH — each round is two global steps (one proposal each, on the round-start
   observation) and one environment step; every member's outcome and comparison sit on its own proposal step; the
   joint prediction (START_STATE_DISJOINT_WRITES) foresees the write conflicts inside a batch.
2. Restart mid-round: the local run stops after the receiver's proposal of round 3 (batch OPEN in the carry state,
   nothing sent), its state goes through JSON into fresh plugins; the continued run equals the uninterrupted one —
   trajectory and the digest of every planner's input.
3. Views: the receiver's planner receives clock / dock / stock only, the picker's everything but the docks; settings
   come from the participant first; effect comparisons handed back through last_outcome are filtered the same way.
4. Deterministic member outcomes: ABSENT (own budget exhausted), TIMED_OUT (a planner slower than batch_timeout_s),
   CANCELLED (the run ends inside a round), a member denied by an execution gate (not sent, the others are).
5. Sequential runs unchanged: the round-robin warehouse run equals the phase-2 capture (tests/compat/fixtures/phase2,
   recorded at 0ae4571) action by action.
Evidence: docs/execution/evidence/phase3/g4-batch.json.

    scripts/in-vm.sh 'uv run --frozen python scripts/joint_batch_evidence.py'
"""

from __future__ import annotations

import json
import sys
import time
import zipfile
from pathlib import Path
from typing import Any

from formal_lab_contracts import Budget, PlanningContext
from formal_lab_contracts.interfaces import PluginRegistration
from formal_lab_example_warehouse.model import demo_model
from formal_lab_example_warehouse.plugins import RULES, WarehouseRules, build_package
from formal_lab_example_warehouse.scenarios import JOINT, VIEWS, package, receiver_and_picker
from formal_lab_runtime import default_registry, make_manifest, resume_local, run_local

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "execution" / "evidence" / "phase3" / "g4-batch.json"
CAPTURE = ROOT / "tests" / "compat" / "fixtures" / "phase2" / "warehouse.replay.zip"
SPY = RULES.model_copy(update={
    "plugin_id": "evidence.warehouse.recording-rules",
    "config_schema": {"type": "object", "properties": {"role": {"type": "string"}, "sleep": {"type": "number"}},
                      "additionalProperties": False}})
SEEN: dict[str, list[dict[str, Any]]] = {}


class RecordingRules(WarehouseRules):
    """The warehouse rules, recording which locations and settings the planner receives (optionally slow)."""

    def __init__(self, services: Any, config: dict[str, Any]):
        super().__init__(services.loaded_model(), {"role": config.get("role", "both")})
        self.sleep, self.actor, self.style = float(config.get("sleep", 0)), services.actor_id, services.get_setting(
            "style")

    def propose(self, context: PlanningContext):
        last = context.last_outcome
        SEEN.setdefault(self.actor, []).append({
            "families": sorted({f.path.split("[", 1)[0] for f in context.observation.facts}),
            "style": self.style,
            "last_outcome_diff_families": sorted({d.path.split("[", 1)[0] for d in (
                last.effect_comparison.diffs if last is not None and last.effect_comparison else [])})})
        if self.sleep:
            time.sleep(self.sleep)
        return super().propose(context)


def registry():
    reg = default_registry()
    reg.register(PluginRegistration(SPY, lambda config, services: RecordingRules(services, dict(config or {}))))
    return reg


def recording(sc, extra: dict[str, dict] | None = None):
    parts = [p.model_copy(update={"strategy": p.strategy.model_copy(update={
        "plugin": SPY.ref(), "config": {**p.strategy.config, **(extra or {}).get(p.actor_id, {})}})})
             for p in sc.participants]
    return sc.model_copy(update={"participants": parts})


def manifest(pkg, sc, reg, run_id, seed=1):
    return make_manifest(run_id=run_id, project_id="wh", scenario=sc, package=pkg, registry=reg, seed=seed,
                         config={"initial_check_horizon": 0})


def of(res, kind):
    return [e for e in res.events if str(e.event_type) == kind]


def trajectory(res):
    return [(s.step, s.actor_id, s.proposal.action.model_dump(mode="json") if s.proposal else None,
             s.outcome.status.value if s.outcome else None, s.turn.round if s.turn else None,
             s.turn.env_step if s.turn else None) for s in res.steps]


def planner_inputs(res):
    return [(e.logical_step, e.actor_id, e.payload.get("planner_input_digest")) for e in of(res, "ACTION_PROPOSED")]


def main() -> int:
    t0 = time.time()
    reg, pkg = registry(), package()
    out: dict[str, Any] = {}

    # 1. one environment step per round
    views = {"receiver": {**VIEWS["receiver"], "settings": {"style": "careful"}}, "picker": VIEWS["picker"]}
    sc = recording(receiver_and_picker(pkg, turns=JOINT, views=views))
    SEEN.clear()
    m = manifest(pkg, sc, reg, "run_g4_batch")
    full = run_local(m, pkg, reg)
    seen_full = json.loads(json.dumps(SEEN))
    batches = [e.payload["batch"] for e in of(full, "BATCH_SUBMITTED")]
    out["batch"] = {
        "status": full.status.value, "reason": full.reason, "global_steps": len(full.steps), "rounds": len(batches),
        "environment_steps": batches[-1]["env_step"],
        "batches": [{"round": b["round"], "env_step": b["env_step"], "submitted_at_step": b["submitted_at_step"],
                     "members": {x["actor_id"]: [x["status"], x["global_step"]] for x in b["members"]}}
                    for b in batches],
        "steps": [{"step": s.step, "actor": s.actor_id, "round": s.turn.round, "env_step": s.turn.env_step,
                   "action": s.proposal.action.action_type, "outcome": s.outcome.status.value,
                   "comparison": s.outcome.effect_comparison.verdict.value,
                   "conflict": s.outcome.conflict.reason if s.outcome.conflict else None} for s in full.steps],
        "negotiation": next(n.reasons for n in m.negotiation if n.role == "environment"),
    }

    # 2. restart in the middle of round 3
    SEEN.clear()
    part = run_local(m, pkg, reg, stop_after=5)
    state = json.loads(json.dumps(part.to_json()))
    open_batch = state["carry"]["batch"]["record"]
    resumed = resume_local(state, pkg, registry())
    out["restart"] = {
        "stopped_after_step": 5, "open_batch": {"batch_id": open_batch["batch_id"], "status": open_batch["status"],
                                                "members": [[x["actor_id"], x["status"]]
                                                            for x in open_batch["members"]]},
        "environment_step_at_stop": state["snapshot"]["step"],
        "same_trajectory": trajectory(resumed) == trajectory(full),
        "same_planner_inputs": planner_inputs(resumed) == planner_inputs(full) and all(
            d for *_, d in planner_inputs(full)),
        "same_recorded_planner_view": json.loads(json.dumps(SEEN)) == seen_full,
        "status": resumed.status.value}

    # 3. what each planner received
    withheld = {}
    for e in of(full, "OBSERVATION"):
        if "planner_input" in e.payload:
            withheld.setdefault(e.actor_id, set()).update(p.split("[", 1)[0] for p in e.payload["planner_input"]
                                                          ["withheld"])
    out["views"] = {a: {"view": views[a], "received_families": sorted({f for c in calls for f in c["families"]}),
                        "withheld_families": sorted(withheld.get(a, set())),
                        "settings_style": sorted({str(c["style"]) for c in calls}),
                        "last_outcome_diff_families": sorted({f for c in calls
                                                              for f in c["last_outcome_diff_families"]})}
                    for a, calls in seen_full.items()}

    # 4. member outcomes that are decided without the member
    plain = receiver_and_picker(pkg, turns=JOINT)
    absent_sc = plain.model_copy(update={"participants": [
        p.model_copy(update={"budget": Budget(max_steps=2)}) if p.actor_id == "receiver" else p
        for p in plain.participants]})
    absent = run_local(manifest(pkg, absent_sc, reg, "run_g4_absent"), pkg, reg)
    slow_sc = recording(receiver_and_picker(pkg, turns={**JOINT, "batch_timeout_s": 0.2}), {"picker": {"sleep": 0.4}})
    slow_sc = slow_sc.model_copy(update={"budget": slow_sc.budget.model_copy(update={"max_steps": 4})})
    slow = run_local(manifest(pkg, slow_sc, reg, "run_g4_timeout"), pkg, reg)
    short = plain.model_copy(update={"budget": plain.budget.model_copy(update={"max_steps": 5})})
    cancelled = run_local(manifest(pkg, short, reg, "run_g4_cancel"), pkg, reg)
    gpkg = build_package(demo_model(zones=[{"id": "z1", "capacity": 4}, {"id": "z2", "capacity": 8}]),
                         package_id="warehouse-gate")
    gated = run_local(manifest(gpkg, receiver_and_picker(gpkg, turns=JOINT, max_fill=0.5), reg, "run_g4_gate"),
                      gpkg, reg)
    members = lambda b: [[x["actor_id"], x["status"], x.get("reason")] for x in b["members"]]  # noqa: E731
    denied = [s for s in gated.steps if s.outcome and s.outcome.result.get("not_sent")]
    gate_batch = next(e.payload for e in of(gated, "BATCH_SUBMITTED")
                      if denied and e.payload["batch"]["batch_id"] == denied[0].turn.batch_id)
    out["member_outcomes"] = {
        "absent": {"status": absent.status.value,
                   "round_3": members(of(absent, "BATCH_SUBMITTED")[2].payload["batch"])},
        "timed_out": {"batch_timeout_s": 0.2, "picker_planner_seconds": 0.4,
                      "round_1": members(of(slow, "BATCH_SUBMITTED")[0].payload["batch"]),
                      "picker_step_outcome": next(s.outcome for s in slow.steps if s.actor_id == "picker") is None},
        "cancelled": {"status": cancelled.status.value, "reason": cancelled.reason,
                      "batch": members(of(cancelled, "BATCH_CANCELLED")[0].payload["batch"]),
                      "operation_id": of(cancelled, "BATCH_CANCELLED")[0].payload["batch"]["operation_id"]},
        "gate_denied": {"status": gated.status.value, "denied_members": len(denied),
                        "example": {"actor": denied[0].actor_id, "reason": denied[0].outcome.result["reason"],
                                    "sent_in_batch": [o["operation_id"] for o in
                                                      (gate_batch["operation"] or {}).get("batch_outcomes", [])]}
                        if denied else None},
    }

    # 5. sequential runs keep their phase-2 trajectory
    with zipfile.ZipFile(CAPTURE) as z:
        captured = [json.loads(line) for line in z.read("events.jsonl").decode().splitlines() if line.strip()]
    then = [(e["logical_step"], e["actor_id"], e["payload"]["outcome"]["action"], e["payload"]["outcome"]["status"])
            for e in captured if e["event_type"] == "ACTION_OUTCOME"]
    seq = run_local(manifest(pkg, receiver_and_picker(pkg, seed=1), reg, "run_phase2_warehouse"), pkg, reg)
    now = [(e.logical_step, e.actor_id, e.payload["outcome"]["action"], e.payload["outcome"]["status"])
           for e in of(seq, "ACTION_OUTCOME")]
    out["sequential"] = {"captured_at": "0ae4571", "steps": len(now), "same_as_phase2_capture": now == then,
                         "no_batch_events": not any(str(e.event_type).startswith("BATCH_") for e in seq.events),
                         "carry_has_no_batch": "batch" not in seq.carry}

    b, r, v, mo = out["batch"], out["restart"], out["views"], out["member_outcomes"]
    checks = {
        "batch: one environment step per round": b["status"] == "SUCCEEDED"
                                                 and all(x["env_step"] == x["round"] for x in b["batches"])
                                                 and b["global_steps"] == 2 * b["rounds"],
        "batch: outcomes on each member's own step": all(s["env_step"] == s["round"] for s in b["steps"]),
        "batch: joint prediction matches (conflicts foreseen)": {s["comparison"] for s in b["steps"]} == {"MATCH"}
                                                               and any(s["conflict"] for s in b["steps"]),
        "restart mid-round: batch open, nothing sent": r["open_batch"]["status"] == "OPEN"
                                                      and r["environment_step_at_stop"] == 2,
        "restart mid-round: same trajectory and planner inputs": r["same_trajectory"] and r["same_planner_inputs"]
                                                                 and r["same_recorded_planner_view"],
        "views: each planner received only its fields": v["receiver"]["received_families"] == ["clock", "dock",
                                                                                                 "stock"]
                                                        and "dock" not in v["picker"]["received_families"]
                                                        and v["picker"]["withheld_families"] == ["dock"],
        "views: participant settings first": v["receiver"]["settings_style"] == ["careful"]
                                             and v["picker"]["settings_style"] == ["None"],
        "member outcomes: ABSENT / TIMED_OUT / CANCELLED / gate": (
            mo["absent"]["round_3"][0][:2] == ["receiver", "ABSENT"]
            and [m[1] for m in mo["timed_out"]["round_1"]] == ["PROPOSED", "TIMED_OUT"]
            and {m[1] for m in mo["cancelled"]["batch"]} == {"CANCELLED"} and mo["cancelled"]["operation_id"] is None
            and mo["gate_denied"]["denied_members"] > 0),
        "sequential: phase-2 trajectory unchanged": out["sequential"]["same_as_phase2_capture"]
                                                    and out["sequential"]["no_batch_events"],
    }
    doc = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "duration_s": round(time.time() - t0, 1),
           "checks": checks, "ok": all(checks.values()), **out}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False, default=str) + "\n")
    print(json.dumps(checks, indent=1, ensure_ascii=False))
    return 0 if doc["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
