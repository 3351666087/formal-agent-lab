#!/usr/bin/env python3
"""Generate docs/handoff/phase6.manifest.json (phase-handoff/v1 compatible; 6A writes it, 6B extends it).

Dynamic values come from the repository, the research-check results and the p6a evidence (the real-endpoint record
in particular), so the manifest never drifts from them. Phase 6 as a whole stays incomplete until 6B passes.

    uv run --frozen python scripts/handoff_phase6.py
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "docs" / "execution" / "evidence" / "research"
MANIFEST = ROOT / "docs" / "handoff" / "phase6.manifest.json"
SCHEMAS = ("fal-research-case-v1", "fal-conformance-result-v1", "fal-research-response-v1", "fal-research-study-v1",
           "fal-research-evaluation-v1")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def load(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def main() -> int:
    checks = load(EV / "checks" / "results.json")
    real = load(EV / "p6a" / "real-endpoint.json")
    protocol = load(EV / "p6a" / "protocol.json")
    groups = checks.get("groups", {})
    p6a = groups.get("p6a") == "PASS"
    contracts = {v: json.loads((ROOT / "contracts" / v / "DIGEST.json").read_text()) for v in ("v1", "v2")}
    manifest = {
        "format": "phase-handoff/v1", "phase": "6", "part": "6A (双模型调用、原始回答与评测基础); 6B pending",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_revision": checks.get("source_revision") or {"commit": git("rev-parse", "HEAD")},
        "handoff_revision_parent": git("rev-parse", "HEAD"),
        "developer_models": ["claude-opus-5-5"],
        "developer_models_note": "the coding model of 6A; every experiment unit records its own provider, route and "
                                 "returned model — results are not attributed to the developer model",
        "contracts": {c["contract_version"]: c["digest"] for c in contracts.values()},
        "research_protocols": {name.replace("-v1", "/v1"): hashlib.sha256(
            (ROOT / "contracts" / "research" / f"{name}.schema.json").read_bytes()).hexdigest() for name in SCHEMAS},
        "task_status": {
            "P6A-01": {"title": "两个提供方的可靠调用适配与研究响应记录", "status": "PASS" if p6a else "IN_PROGRESS",
                       "evidence": ["docs/execution/evidence/research/p6a/protocol.json",
                                    "docs/execution/evidence/research/p6a/real-endpoint.json"]},
            "P6A-02": {"title": "研究任务入口、独立评分接口、两条实验线分开的矩阵与报告", "status": "PASS" if p6a else "IN_PROGRESS",
                       "evidence": ["docs/execution/evidence/research/p6a/protocol.json",
                                    "research/results/p6a-protocol/report.md"]},
        },
        "phase6_complete": False,
        "phase6_complete_note": "Phase 6 waits for 6B (domain evaluation); 6A delivers the generic foundation only",
        "check_command": checks.get("command"), "check_groups": groups, "check_summary": checks.get("summary"),
        "selected_passed": checks.get("selected_passed"), "overall_complete": checks.get("overall_complete"),
        "config_digest": (checks.get("config") or {}).get("sha256"),
        "where_answers_live": {
            "raw_response": "research/results/<study_id>/responses/<unit>--<n>.json (fal-research-response/v1: "
                            "raw.body as the provider returned it, raw.visible_text, status, cost)",
            "sent_prompt": "research/results/<study_id>/prompts/<task_input_digest>.json",
            "evaluation": "research/results/<study_id>/evaluations/<unit>--<n>.json (fal-research-evaluation/v1)",
            "history": "research/results/<study_id>/ledger.jsonl (every sample, including earlier failed ones)",
            "report": "research/results/<study_id>/report.md / report.json",
            "cli": "fal research study show <study_dir> --unit <unit_id>",
            "web": "基准对比 → 研究评测 (after fal research study import)"},
        "refusal_and_error_taxonomy": "docs/research/protocol.md#two-result-axes-stable-classes (CallOutcome / "
                                      "AnswerStatus / BehaviorLabel)",
        "model_identity": "CallIdentity.model_identity: CONFIRMED_BY_PROVIDER only on an OFFICIAL_NATIVE route that "
                          "names the model; RELAY_REPORTED on a relay; UNKNOWN when unnamed; model_switched when the "
                          "returned model differs from the requested one",
        "scorer_registration_for_6b": {
            "interface": "formal_lab_eval.research_scorers.ResearchScorer: scorer_id, version, score(parsed, reference, "
                         "*, repo_root, truncated) -> ScoreOutcome",
            "register": "register_scorer(...) in-process, or entry-point group formal_lab.research_scorers",
            "task_binding": "StudyTask.scorer_id + scorer_version; the reference file is scorer-only",
            "built_in": ["orders.deviation-diagnosis@1", "synthetic.shortest-plan@1"]},
        "access_boundary": "a model gets only StudyTask.inputs (+ assisted_inputs in ASSISTED); the reference is "
                           "scorer-only; load_study rejects a reference that is, or copies, a task input",
        "real_endpoints": {
            "providers": real.get("providers"), "configured_credentials": real.get("configured_credentials"),
            "conclusion": real.get("conclusion"), "evidence": "docs/execution/evidence/research/p6a/real-endpoint.json",
            "results": "research/results/p6a-real/"},
        "protocol_validation": {"planned_units": protocol.get("planned_units"),
                                "evidence": "docs/execution/evidence/research/p6a/protocol.json",
                                "results": "research/results/p6a-protocol/"},
        "commands": {
            "research_check": "make research-check ARGS=\"--group p6a\"",
            "build_studies": "uv run --frozen python scripts/p6a_studies.py",
            "run_study": "uv run --frozen fal research study run research/studies/<study_id>",
            "rescore": "uv run --frozen fal research study score research/studies/<study_id> [--force]",
            "import_to_platform": "uv run --frozen fal research study import research/studies/<study_id> "
                                  "--project <project>"},
        "blocked": [
            {"item": "Claude Opus 5.5 on the official Anthropic route (OFFICIAL_NATIVE)",
             "reason": "no FAL_ANTHROPIC_API_KEY configured; the environment's ANTHROPIC_API_KEY is never read",
             "unblock": "put FAL_ANTHROPIC_API_KEY in the git-ignored .env and run the study again"},
            {"item": "GPT-6 Astra on the official OpenAI route", "reason": "no official OpenAI credential configured",
             "unblock": "add an OFFICIAL_NATIVE provider config with an FAL_* key setting"}],
        "assumptions": [
            "relay results verify the adapters and give an engineering reading only; no provider comparison is drawn "
            "from a relay route (K08)",
            "the call cap of p6a-real was raised once (8 → 12) at the user's request after relay route changes, with "
            "the reason written into the study (K09)",
            "studies run locally from the host; the platform imports results read-only (K12)"],
        "known_gaps": {"doc": "docs/research/known-gaps.md", "opened_in_6a": ["K08", "K09", "K10", "K11", "K12"],
                       "carried": {"K01": "OPEN", "K02": "OPEN", "K03": "OPEN"}},
        "handoff_docs": ["docs/handoff/phase6.md", "docs/handoff/phase6.manifest.json", "docs/research/protocol.md",
                         "docs/research/known-gaps.md", "docs/execution/phase-6a.md", "docs/reuse-ledger.md"],
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(f"phase6 handoff: p6a {'PASS' if p6a else 'incomplete'}; real-endpoint "
          f"{(real.get('conclusion') or {}).get('routes')}; phase 6 complete = False (6B pending)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
