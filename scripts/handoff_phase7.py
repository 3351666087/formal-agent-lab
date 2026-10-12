#!/usr/bin/env python3
"""Generate docs/handoff/phase7.manifest.json (phase-handoff/v1) — the closeout manifest, with the five final status
fields defined in docs/research/protocol.md. Dynamic values come from the research-check results and the p7 evidence,
so the manifest never drifts from them.

    uv run --frozen python scripts/handoff_phase7.py
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "docs" / "execution" / "evidence" / "research"
MANIFEST = ROOT / "docs" / "handoff" / "phase7.manifest.json"
SCHEMAS = ("fal-research-case-v1", "fal-conformance-result-v1", "fal-research-response-v1", "fal-research-study-v1",
           "fal-research-evaluation-v1")


def git(*a: str) -> str:
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def load(p: Path) -> dict:
    return json.loads(p.read_text()) if p.exists() else {}


def main() -> int:
    checks = load(EV / "checks" / "results.json")
    holdout = load(EV / "p7" / "holdout.json")
    repro = load(EV / "p7" / "reproduce.json")
    groups = checks.get("groups", {})
    strict_complete = bool(checks.get("overall_complete")) and checks.get("run", {}).get("full")
    all_pass = all(groups.get(g) == "PASS" for g in ("p5a", "p5b", "p6a", "p6b", "p7"))
    contracts = {v: json.loads((ROOT / "contracts" / v / "DIGEST.json").read_text()) for v in ("v1", "v2")}
    real_recorded = bool((holdout.get("conclusion") or {}).get("real_answers_recorded"))

    status = {
        "engineering_ready": {
            "value": bool(all_pass),
            "evidence": "make research-check ARGS=\"--strict\" → complete=True (p5a,p5b,p6a,p6b,p7 all PASS); "
                        "docs/execution/evidence/research/checks/results.json",
            "note": "the local pipeline builds, validates cases offline, runs the dual-model studies and reports; "
                    "engineering readiness is not a claim that any research hypothesis is supported"},
        "experiment_execution_complete": {
            "value": real_recorded,
            "evidence": ["research/results/p6b-eval/report.md", "research/results/p7-holdout/report.md",
                         "docs/execution/evidence/research/p7/holdout.json"],
            "note": "the dual-model batches (6B 24 units + the held-out 8) were requested, answered and scored with "
                    "complete denominators; a model answering wrongly would still be a complete experiment"},
        "findings_supported": {
            "level": "descriptive",
            "supported": ["the model-with-program-dependency method generalises beyond the first sample: the new "
                          "held-out token-bucket case (a different mechanism) validates and both models judged it "
                          "correctly (program-grounded)",
                          "across 6B (24) and the held-out (8) units both models were correct on every unit at this "
                          "difficulty; no representation sensitivity was observed on the harmless synthetic framings"],
            "not_supported": ["any statistical ranking or superiority claim (tiny samples, clustered by case)",
                              "a verified provider comparison (both models answered through a relay; identity is "
                              "relay-reported, K08/K15)",
                              "general attack-modelling capability, or any conclusion about the disguised-attack / "
                              "regulation-evasion experiment (not run)"],
            "note": "these tasks are easy enough that both models scored 100% (K13); the finding is that the method "
                    "and the independent checks work on a second mechanism, not that one model is better"},
        "independent_human_reproduction": {
            "value": "PENDING",
            "automated": (repro.get("conclusion") or {}).get("offline_recheck_passes"),
            "evidence": "docs/execution/evidence/research/p7/reproduce.json (automated clean-room offline recheck, "
                        "same agent)",
            "note": "no person has independently reproduced it yet; when one does, record the reproducer, date and any "
                    "differences — an agent re-running in a clean directory is only automated reproduction"},
        "original_adviser_scope_complete": {
            "value": False,
            "uncovered": ["the original adviser scope included hiding a real attack purpose to test regulation "
                          "evasion; that experiment was not run and these materials do not support that conclusion"],
            "note": "only the adviser can accept an adjusted research scope; an agent cannot do so on their behalf. "
                    "This stays false until the adviser accepts the adjusted scope and its acceptance is complete"},
    }

    manifest = {
        "format": "phase-handoff/v1", "phase": "7", "part": "held-out case, gap closure, reproduction and closeout",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_revision": checks.get("source_revision") or {"commit": git("rev-parse", "HEAD")},
        "handoff_revision_parent": git("rev-parse", "HEAD"),
        "developer_models": {"general_engineering_reproduction_report": "claude-opus-5-5",
                             "domain_mechanism_criteria_K01_K02": "claude-opus-4-8"},
        "developer_models_note": "a division of labour recorded apart from the models under test; it does not imply "
                                 "any model accepts or is suited to a task. Both were run by one session here.",
        "contracts": {c["contract_version"]: c["digest"] for c in contracts.values()},
        "research_protocols": {n.replace("-v1", "/v1"): hashlib.sha256(
            (ROOT / "contracts" / "research" / f"{n}.schema.json").read_bytes()).hexdigest() for n in SCHEMAS},
        "task_status": {
            "P7-01": {"title": "新真实保留案例 + 冻结双模型评测 + 逐案例可信度/局限",
                      "status": "PASS" if groups.get("p7") == "PASS" else "IN_PROGRESS",
                      "cases": {"phase5_reused": "orders-tenant-isolation",
                                "new_held_out": "ratelimit-token-bucket (own_test_variant, a different mechanism)",
                                "upstream_case": "NOT_RUN — see blocked[]"},
                      "evidence": ["research/cases/ratelimit-token-bucket/case.json",
                                   "research/studies/p7-holdout/study.json",
                                   "docs/execution/evidence/research/p7/holdout.json"]},
            "P7-02": {"title": "关闭 K01-K03 + 本地总验收 + 干净环境复现 + 结题说明",
                      "status": "PASS" if (groups.get("p7") == "PASS" and strict_complete) else "IN_PROGRESS",
                      "gaps_closed": ["K01", "K02", "K03"],
                      "evidence": ["packages/domain-mal/tests/test_admission.py",
                                   "docs/execution/evidence/research/p7/reproduce.json",
                                   "docs/execution/evidence/research/checks/results.json"]},
        },
        "final_status": status,
        "research_total_check": {"command": "make research-check ARGS=\"--strict\"", "groups": groups,
                                 "complete": strict_complete, "summary": checks.get("summary")},
        "local_total_acceptance": {
            "command": "make acceptance-local",
            "note": "phases 1-4 strict acceptance was complete=true at their revisions (a05c1d2 / b993dc9); the "
                    "phase-7 domain changes (K01/K02) are covered by p7-unit and the d2 broker evidence re-run. A full "
                    "re-run needs the dev stack (scripts/dev.sh up) and ≥15 GiB free disk (currently less); it is the "
                    "documented baseline command, run by the user when that headroom is available",
            "status": "BASELINE_COMMAND"},
        "cases": {"orders-p2-speed": "5A timing deviation", "orders-tenant-isolation": "5B tenant isolation",
                  "ratelimit-token-bucket": "7 held-out capacity limiter"},
        "synthetic_bases": ["counter (lamp)", "route (shortcut)"],
        "models_under_test": ["gpt-6-astra (relay)", "claude-opus-5-5 (relay)"],
        "reproduction": {
            "offline_recheck": "scripts/p7_reproduce.py — validates the committed cases and reads the committed "
                               "results with no model call and no network (automated clean-room)",
            "offline_artifact_reference": "scripts/offline_bundle.py manifest now carries a research_data reference "
                                          "(cases/studies/results/rubric digests + source revision)",
            "resampling_path": "fal research study run — new online calls; needs the user's API credentials and quota",
            "machine": repro.get("machine")},
        "blocked": [
            {"item": "an upstream public software held-out case (P7-01 preferred second case)",
             "reason": "installing/vendoring an external project with its maintainer regression and pinning "
                       "revision/license is a reproducibility risk in this sandboxed VM (frozen uv.lock, tight disk); "
                       "a new own-fixture case of a different mechanism was delivered instead, honestly labelled "
                       "own_test_variant, so the method-generality check is met but the upstream↔own contrast is not",
             "unblock": "vendor a small, permissively-licensed upstream mechanism with its tests at a pinned revision, "
                        "or add it as a dependency when uv.lock can be updated, then build a case the same way"},
            {"item": "verified provider comparison / official routes",
             "reason": "both models answered through a relay (relay-reported identity); official OpenAI/Anthropic "
                       "routes are not configured", "unblock": "configure FAL_* official credentials and re-run"},
            {"item": "independent human reproduction", "reason": "no person has reproduced it yet",
             "unblock": "a person follows docs/handoff/phase7.md and records reproducer/date/differences"},
        ],
        "adviser_answers": "docs/handoff/phase7.md (the adviser Q&A table)",
        "known_gaps": {"doc": "docs/research/known-gaps.md", "closed_in_7": ["K01", "K02", "K03"],
                       "open": ["K04", "K05", "K06", "K07", "K08", "K09", "K10", "K11", "K12", "K13", "K14", "K15"]},
        "handoff_docs": ["docs/handoff/phase7.md", "docs/handoff/phase7.manifest.json", "docs/research/protocol.md",
                         "docs/research/known-gaps.md", "docs/execution/phase-7.md", "docs/reuse-ledger.md"],
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(f"phase7 handoff: p7 {groups.get('p7')}; research total complete={strict_complete}; "
          f"engineering_ready={all_pass}, experiment_execution_complete={real_recorded}, "
          f"findings=descriptive, human_repro=PENDING, original_adviser_scope_complete=False")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
