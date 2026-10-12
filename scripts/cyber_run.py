#!/usr/bin/env python3
"""Run the real, large dual-model batch for the defensive attack-graph study (P8-02): every unit is a hard,
verifier-grounded question, called against the two relay models. Resumable — a unit whose saved response already
carries a model answer is reused, so re-running continues where it stopped. Writes research/results/cyber-attackgraph/
and docs/execution/evidence/research/cyber/run.json.

Needs the relay credentials in the git-ignored .env (FAL_RESEARCH_*); BLOCKED (no calls) if they are absent.

    uv run --frozen python scripts/cyber_run.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "research" / "studies" / "cyber-attackgraph"
RESULTS = ROOT / "research" / "results" / "cyber-attackgraph"
EV = ROOT / "docs" / "execution" / "evidence" / "research" / "cyber"


def main() -> int:
    from formal_lab_eval.research import Ledger, build_report, load_study, plan_units, run_study
    from formal_lab_strategies.model_clients import read_setting

    study = load_study(STUDY)
    units, _ = plan_units(study)
    secrets = {p.api_key_setting: read_setting(p.api_key_setting) for p in study.providers if p.api_key_setting}
    if not any(secrets.values()):
        print(f"BLOCKED: no relay credential ({', '.join(sorted(secrets))} empty); {len(units)} units NOT_RUN")
        return 2

    done = {"n": 0}
    t0 = time.time()

    def log(msg: object = "", *args: object, **kw: object) -> None:
        done["n"] += 1
        if done["n"] % 50 == 0:
            print(f"  [{done['n']} log events] {time.time() - t0:.0f}s elapsed — {str(msg)[:80]}", flush=True)

    print(f"running {len(units)} units ({len(study.tasks)} tasks × {len(study.providers)} models × "
          f"{study.replicates} reps) against the relay; resumable", flush=True)
    summary = run_study(STUDY, RESULTS, log=log)
    report = build_report(STUDY, RESULTS)
    latest = Ledger(RESULTS).latest_responses()
    produced = sum(1 for e in latest.values() if e["outcome"] in
                   ("ANSWERED", "TRUNCATED", "CONTENT_REFUSAL", "EMPTY_CONTENT"))
    rows = []
    for cond in report["tracks"].get("formal_model_analysis", {}).get("conditions", []):
        rows.append({"condition": cond["condition"], "planned": cond["planned"],
                     "correct": cond["metrics"].get("correct"), "behaviors": cond.get("behaviors")})
    EV.mkdir(parents=True, exist_ok=True)
    (EV / "run.json").write_text(json.dumps({
        "study_id": summary["study_id"], "planned": len(units), "responses_recorded": len(latest),
        "model_produced": produced, "budget": summary["budget"], "tally": summary["tally"], "conditions": rows,
        "configured_credentials": sorted(k for k, v in secrets.items() if v),
        "conclusion": {"real_batch": True, "mechanism": "defensive attack-graph analysis",
                       "ground_truth": "Z3 verifier / model semantics", "provider_comparison_verified": False,
                       "elapsed_seconds": round(time.time() - t0)}}, indent=2, ensure_ascii=False) + "\n")
    print(f"done: {len(latest)} responses, {produced} model-produced, {summary['budget']['calls']} calls, "
          f"{time.time() - t0:.0f}s → {RESULTS}/report.md", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
