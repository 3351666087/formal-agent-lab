#!/usr/bin/env python3
"""Generate docs/handoff/phase8.manifest.json (phase-handoff/v1) for the defensive attack-graph work: the study, the
verifier-grounded question kinds, and — once the real batch has run — the per-model, per-kind results read straight
from the committed report, so the manifest never drifts from the data.

    uv run --frozen python scripts/handoff_phase8.py
"""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "docs" / "execution" / "evidence" / "research"
STUDY = ROOT / "research" / "studies" / "cyber-attackgraph"
RESULTS = ROOT / "research" / "results" / "cyber-attackgraph"
MANIFEST = ROOT / "docs" / "handoff" / "phase8.manifest.json"


def git(*a: str) -> str:
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def load(p: Path) -> dict:
    return json.loads(p.read_text()) if p.exists() else {}


def main() -> int:
    check = load(EV / "cyber" / "check.json")
    run = load(EV / "cyber" / "run.json")
    report = load(RESULTS / "report.json")
    study = load(STUDY / "study.json")
    gt = load(STUDY / "ground-truth.json")

    conditions = []
    for c in report.get("tracks", {}).get("formal_model_analysis", {}).get("conditions", []):
        conditions.append({"condition": c["condition"], "planned": c.get("planned"),
                           "correct": c.get("metrics", {}).get("correct"),
                           "program_corresponds": c.get("metrics", {}).get("program_corresponds"),
                           "behaviors": c.get("behaviors")})

    costs = [v["shortest_cost"] for v in gt.values() if v.get("shortest_cost") is not None]
    cuts = [v["min_cut"]["size"] for v in gt.values() if v.get("min_cut", {}).get("size") is not None]
    manifest = {
        "format": "phase-handoff/v1", "phase": "8",
        "part": "defensive attack-graph analysis — verifier-grounded cyber study and the large real batch",
        "generated_at": datetime.now(UTC).isoformat(),
        "self_initiated": "expansion requested by the user: more/harder cases, a substantial cyber domain, and a "
                          "large real batch where every step is worthy of a frontier model",
        "handoff_revision": git("rev-parse", "HEAD"),
        "mechanism": {
            "what": "abstract AND/OR attack graphs (entry footholds → intermediate steps → target), the standard "
                    "object of defensive attack-graph / threat-model analysis; steps are abstract graph nodes, not "
                    "operational exploitation instructions",
            "module": "packages/domain-mal/src/formal_lab_domain_mal/analysis.py",
            "ground_truth": "Z3 verifier / model semantics, cross-checked (native oracle vs Z3)"},
        "question_kinds": {
            "shortest_cost": "minimum attack-path cost to the target (Z3 OPTIMIZE_OBJECTIVE)",
            "reachability": "is the target reachable under a deployed defence set (Z3 GOAL_REACHABILITY)",
            "min_defense": "smallest number of defences that cut every path (AND/OR min-cut, Z3-confirmed)",
            "step_enabled": "is a derived step enabled in a given state (AND/OR semantics)"},
        "difficulty_spread": {"graphs": len(gt), "nodes": [min((v["nodes"] for v in gt.values()), default=None),
                              max((v["nodes"] for v in gt.values()), default=None)],
                              "shortest_cost": [min(costs, default=None), max(costs, default=None)],
                              "min_cut": [min(cuts, default=None), max(cuts, default=None)]},
        "study": {"id": "cyber-attackgraph", "tasks": len(study.get("tasks", [])),
                  "planned_units": len(study.get("tasks", [])) * len(study.get("providers", [])) *
                  study.get("replicates", 0),
                  "models": [p.get("model") for p in study.get("providers", [])],
                  "replicates": study.get("replicates")},
        "check": {"command": "make research-check ARGS=\"--group p8\"",
                  "ground_truth_z3_confirmed": (check.get("conclusion") or {}).get("ground_truth_z3_confirmed"),
                  "scorer_verified_on_loopback": (check.get("conclusion") or {}).get("scorer_verified_on_loopback")},
        "real_batch": {
            "status": "COMPLETE" if run else "RUNNING_OR_NOT_RUN",
            "command": "uv run --frozen python scripts/cyber_run.py (resumable)",
            "planned": run.get("planned"), "model_produced": run.get("model_produced"),
            "budget": run.get("budget"), "conditions": conditions,
            "evidence": ["research/results/cyber-attackgraph/report.md",
                         "docs/execution/evidence/research/cyber/run.json"]},
        "caveats": [
            "both models answer through a relay — identity is relay-reported, so this is a hard discriminating "
            "experiment, not a verified GPT-vs-Claude ranking",
            "the attack graphs are abstract formal models for defensive analysis, not scans of a real network; "
            "`program_correspondence` here means the answer agrees with the Z3 verifier, not a program observation"],
        "tasks": {"P8-01": "study, scorer, check — DONE",
                  "P8-02": "the real ~1098-unit dual-model batch — " + ("DONE" if run else "RUNNING/PENDING")},
        "related": ["docs/handoff/phase7.md", "docs/research/protocol.md", "docs/research/known-gaps.md"],
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(f"phase8 manifest: study tasks={len(study.get('tasks', []))}, real_batch="
          f"{'COMPLETE' if run else 'pending'}, conditions={len(conditions)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
