#!/usr/bin/env python3
"""Generate docs/handoff/phase5.manifest.json (phase-handoff/v1 compatible, extended for the research track).

5A writes the base; 5B–7 update the task status, evidence and next-phase interfaces in place. The dynamic values —
source revision, work-tree digest, contract and protocol schema digests, and the research-check summary — are read
from the repository and docs/execution/evidence/research/checks/results.json, so the manifest never drifts from them.

    uv run --frozen python scripts/handoff_phase5.py
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import tomllib
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKS = ROOT / "docs" / "execution" / "evidence" / "research" / "checks" / "results.json"
CASE = ROOT / "research" / "cases" / "orders-p2-speed"
MANIFEST = ROOT / "docs" / "handoff" / "phase5.manifest.json"


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def sha256_file(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def main() -> int:
    results = json.loads(CHECKS.read_text()) if CHECKS.exists() else {}
    groups = results.get("groups", {})
    p5a_pass = groups.get("p5a") == "PASS"
    contracts = {v: json.loads((ROOT / "contracts" / v / "DIGEST.json").read_text()) for v in ("v1", "v2")}
    schemas = {name: sha256_file(ROOT / "contracts" / "research" / f"{name}.schema.json")
               for name in ("fal-research-case-v1", "fal-conformance-result-v1")}
    reference = json.loads((CASE / "reference" / "expected.json").read_text()) if (CASE / "reference" /
                                                                                   "expected.json").exists() else {}

    task_status = {
        "P5A-01": {"title": "最小案例协议、导入校验与来源展示；一个普通业务案例跑通",
                   "status": "PASS" if p5a_pass else "IN_PROGRESS",
                   "evidence": "docs/execution/evidence/research/p5a/case.json"},
        "P5A-02": {"title": "模型—程序对应验证接口、案例证据视图、共用检查入口",
                   "status": "PASS" if p5a_pass else "IN_PROGRESS",
                   "evidence": "docs/execution/evidence/research/checks/results.json"},
    }

    manifest = {
        "format": "phase-handoff/v1", "phase": "5", "part": "5A (案例、模型与证据基础)",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_revision": results.get("source_revision") or {"commit": git("rev-parse", "HEAD")},
        "handoff_revision_parent": git("rev-parse", "HEAD"),
        "developer_models": ["claude-opus-5-5", "claude-opus-4-8"],
        "developer_models_note": "developer (coding) models in this session; recorded apart from any in-experiment "
                                 "provider model (phase 6 uses an online provider, counted separately).",
        "tracks": {"implementation_conformance": "software model verification with its real purpose kept",
                   "synthetic_representation": "fixed, reviewed synthetic problems (not opened in 5A)"},
        "contracts": {c["contract_version"]: c["digest"] for c in contracts.values()},
        "research_protocols": {"fal-research-case/v1": schemas["fal-research-case-v1"],
                               "fal-conformance-result/v1": schemas["fal-conformance-result-v1"]},
        "workspace_packages": tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["uv"]["workspace"]["members"],
        "config_digest": results.get("config", {}).get("sha256"),
        "commands": {
            "research_check": "make research-check ARGS=\"--group p5a\"",
            "build_case": "uv run --frozen python scripts/p5a_orders_case.py",
            "validate_offline": "uv run --frozen fal research validate research/cases/orders-p2-speed --repo .",
            "conformance_offline": "uv run --frozen fal research conformance research/cases/orders-p2-speed "
                                   "--model v1 --property all_completed",
            "import_to_platform": "uv run --frozen fal research import research/cases/orders-p2-speed --project <id>",
        },
        "check_command": results.get("command"),
        "check_groups": groups,
        "check_summary": results.get("summary"),
        "selected_passed": results.get("selected_passed"),
        "overall_complete": results.get("overall_complete"),
        "overall_complete_note": "p5a is the only registered group; p5b–p7 are NO_CHECKS until their executors "
                                 "register checks, so the suite is complete only once every required group passes.",
        "task_status": task_status,
        "ordinary_case": {
            "case_id": "orders-p2-speed", "track": "implementation_conformance",
            "mechanism_family": "timing-model-deviation",
            "program": "examples/local-order-service (own_test_variant: deviation operating condition, station p2 slow)",
            "models": {"v1": "belief (nominal speed)", "v2": "revised (slow[p2]=true)"},
            "property": "all_completed (goal)",
            "result": {"v1": reference.get("v1"), "v2": reference.get("v2"), "regression": reference.get("regression")},
            "layers_kept_apart": "model conclusion (Z3 verdict) · program regression · correspondence (within scope)",
            "location": "research/cases/orders-p2-speed/ (case.json + artifacts)",
        },
        "interfaces_for_5b": {
            "contracts": ["formal_lab_contracts.research.ResearchCase (fal-research-case/v1)",
                          "formal_lab_contracts.research.ConformanceResult (fal-conformance-result/v1)",
                          "Track / ArtifactRole / CaseArtifact / SoftwareSource / CaseModel / PropertySpec / Bounds / "
                          "Correspondence / Validation / Reproduction / CounterexampleEvidence"],
            "runtime": ["load_case(src) -> CaseFiles", "validate_case(files, repo=None) -> (ValidationReport, case)",
                        "replay_items(package, bundle_bytes, scope=None) -> (items, meta)",
                        "replay_conformance(files, case, model_label, property_id, observation_id, "
                        "model_conclusion, program_regression, scope=None, counterexample=None) -> ConformanceResult",
                        "decide_correspondence(items, has_observation, counterexample=None, model_conclusion=None)",
                        "compute_case_digest / definition_digest / property_digest / tree_digests / sha256_bytes"],
            "platform": ["services/research.py: import_case / list_cases / case_detail / export_case / "
                         "cases_for_model_version / conformance_for_run",
                         "POST /projects/{pid}/research/cases (zip) · GET …/research/cases · GET /research/cases/{id}"
                         " · GET /research/cases/{id}/export · GET /model-versions/{vid}/research · GET /runs/{rid}/research"],
            "sdk_cli": ["Client.import_research_case / research_cases / research_case / export_research_case / "
                        "model_version_research / run_research",
                        "fal research validate|conformance|import|list|show|export"],
            "checks": ["scripts/research_checks.py (RESEARCH_CHECKS, RESEARCH_GROUPS) — add p5b checks here",
                       "scripts/research_check.py suite 'research'; make research-check"],
            "web": ["ModelWorkbench 研究案例 tab (per model version)", "Evidence 对应验证 tab (per observation run)"],
        },
        "assumptions": [
            "5A uses Z3 and the local order service only; CBMC is a 5B per-language conditional, not a 5A prerequisite.",
            "The platform validates a case offline (digests, identities, separation); software tree digests are "
            "verified only where a repository is at hand (fal research validate --repo, or the research check).",
            "The model conclusion (Z3 bounded verdict) is timeout-bounded and recorded as-is; the correspondence layer "
            "is deterministic from the recorded observation, so the checks assert on correspondence, not on the verdict.",
        ],
        "known_gaps": {"doc": "docs/research/known-gaps.md",
                       "carried_from_phase4": ["K01 目标性质与凭据错配", "K02 LabPolicy.max_attack_steps 未执行",
                                               "K03 门控详情未显示 detail"],
                       "note": "recorded, not reopened in 5A; 5B judges K01/K02 for its path, phase 7 confirms closure."},
        "blocked": [],
        "method": {"approach": "independent program observation checks the abstract conclusion",
                   "reference": "Formal Verification at Higher Levels of Abstraction "
                                "(https://www.kroening.com/papers/iccad2007.pdf)",
                   "note": "the correspondence wording is used accurately; a formal abstraction-preservation proof is "
                           "separate and not claimed."},
        "handoff_docs": ["docs/handoff/phase5.md", "docs/handoff/phase5.manifest.json",
                         "docs/research/protocol.md", "docs/research/known-gaps.md", "docs/execution/phase-5a.md"],
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(f"phase5 handoff: p5a {'PASS' if p5a_pass else 'incomplete'}; "
          f"selected_passed={results.get('selected_passed')} overall_complete={results.get('overall_complete')}; "
          f"case v1={reference.get('v1', {}).get('correspondence')} v2={reference.get('v2', {}).get('correspondence')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
