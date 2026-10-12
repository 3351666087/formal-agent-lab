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
CASE_5B = ROOT / "research" / "cases" / "orders-tenant-isolation"
MANIFEST = ROOT / "docs" / "handoff" / "phase5.manifest.json"


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def sha256_file(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def main() -> int:
    results = json.loads(CHECKS.read_text()) if CHECKS.exists() else {}
    groups = results.get("groups", {})
    p5a_pass = groups.get("p5a") == "PASS"
    p5b_pass = groups.get("p5b") == "PASS"
    contracts = {v: json.loads((ROOT / "contracts" / v / "DIGEST.json").read_text()) for v in ("v1", "v2")}
    schemas = {name: sha256_file(ROOT / "contracts" / "research" / f"{name}.schema.json")
               for name in ("fal-research-case-v1", "fal-conformance-result-v1")}

    def _reference(case_dir: Path) -> dict:
        p = case_dir / "reference" / "expected.json"
        return json.loads(p.read_text()) if p.exists() else {}

    reference = _reference(CASE)
    reference_5b = _reference(CASE_5B)

    task_status = {
        "P5A-01": {"title": "最小案例协议、导入校验与来源展示；一个普通业务案例跑通",
                   "status": "PASS" if p5a_pass else "IN_PROGRESS",
                   "evidence": "docs/execution/evidence/research/p5a/case.json"},
        "P5A-02": {"title": "模型—程序对应验证接口、案例证据视图、共用检查入口",
                   "status": "PASS" if p5a_pass else "IN_PROGRESS",
                   "evidence": "docs/execution/evidence/research/checks/results.json"},
        "P5B-01": {"title": "一个主体能力与动作语义明确、可在本地真实服务观测的软件安全性质案例",
                   "status": "PASS" if p5b_pass else "IN_PROGRESS",
                   "evidence": "docs/execution/evidence/research/p5b/case.json"},
        "P5B-02": {"title": "缺陷/修复独立回归、模型—程序对应报告、Phase 6 任务材料交接",
                   "status": "PASS" if p5b_pass else "IN_PROGRESS",
                   "evidence": "docs/execution/evidence/research/p5b/case.json"},
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
            "research_check": "make research-check ARGS=\"--group p5a,p5b\"",
            "build_case_5a": "uv run --frozen python scripts/p5a_orders_case.py",
            "build_case_5b": "uv run --frozen python scripts/p5b_isolation_case.py",
            "run_isolation_fixture": "python -m formal_lab_example_orders.research_isolation --mode per_tenant",
            "validate_offline": "uv run --frozen fal research validate research/cases/orders-tenant-isolation --repo .",
            "import_to_platform": "uv run --frozen fal research import research/cases/orders-tenant-isolation "
                                  "--project <id>",
        },
        "check_command": results.get("command"),
        "check_groups": groups,
        "check_summary": results.get("summary"),
        "selected_passed": results.get("selected_passed"),
        "overall_complete": results.get("overall_complete"),
        "overall_complete_note": "p5a is the only registered group; p5b–p7 are NO_CHECKS until their executors "
                                 "register checks, so the suite is complete only once every required group passes.",
        "task_status": task_status,
        "cases": {
            "orders-p2-speed": {
                "track": "implementation_conformance", "mechanism_family": "timing-model-deviation",
                "program": "examples/local-order-service (own_test_variant: deviation condition, station p2 slow)",
                "models": {"v1": "belief (nominal speed)", "v2": "revised (slow[p2]=true)"},
                "property": "all_completed (goal)",
                "result": {"v1": reference.get("v1"), "v2": reference.get("v2"),
                           "regression": reference.get("regression")},
                "location": "research/cases/orders-p2-speed/"},
            "orders-tenant-isolation": {
                "track": "implementation_conformance", "mechanism_family": "access-control-isolation",
                "program": "examples/local-order-service + research_isolation.py fixture (separate from default "
                           "startup); defect/fix = authorization mode authenticate_only vs per_tenant",
                "models": {"secure-spec": "tenant_isolation invariant (reference specification)"},
                "property": "tenant_isolation (invariant)",
                "result": {"defect": reference_5b.get("defect"), "fix": reference_5b.get("fix"),
                           "partial": reference_5b.get("partial"), "model_conclusion": reference_5b.get("model_conclusion"),
                           "regression": reference_5b.get("regression")},
                "three_result_classes": "defect DEVIATES · fix CORRESPONDS · rejected-write UNKNOWN",
                "mechanism_note": "research/cases/orders-tenant-isolation/MECHANISM.md",
                "location": "research/cases/orders-tenant-isolation/"},
        },
        "layers_kept_apart": "model conclusion (Z3 verdict) · program regression · correspondence (within scope); "
                             "a passing regression is not a semantic-equivalence proof",
        "phase6_handoff": {
            "contract": "docs/research/protocol.md#phase-6-handoff-contract-what-a-provider-model-may-be-given",
            "task_input_artifacts": "role=task_input in each case (model + property + fixture/mechanism only)",
            "reference_answers": "role=reference in each case (provider-invisible; REFERENCE_IN_TASK_INPUT enforced)",
            "scoring": "fal-conformance-result/v1 via replay_conformance / derive_items + decide_correspondence and "
                       "the case's own regression tests; the oracle never scores a model's own answer",
            "no_free_text_execution": "model answers are to-be-verified analysis products; nothing translates free "
                                      "text into executable instructions",
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
            "5A/5B use Z3 and the local order service only; CBMC stays a per-language conditional (the cases are "
            "Python), not installed or depended on this phase.",
            "5B's tenant isolation is enforced by the research fixture (research_isolation.py), kept apart from the "
            "default startup path; it is not a claim that the shipped service isolates tenants (K06). The oracle reads "
            "real HTTP results and stored state through each tenant's authorized principal, never a self-reported pass.",
            "The platform validates a case offline (digests, identities, separation); software tree digests are "
            "verified only where a repository is at hand (fal research validate --repo, or the research check).",
            "The model conclusion (Z3 bounded verdict) is timeout-bounded and recorded as-is; the correspondence layer "
            "is deterministic from the recorded observation, so the checks assert on correspondence, not on the verdict.",
        ],
        "known_gaps": {"doc": "docs/research/known-gaps.md",
                       "carried_from_phase4": {"K01": "OPEN", "K02": "OPEN", "K03": "OPEN"},
                       "opened_in_5a": {"K04": "Z3 UNKNOWN at the case bound", "K05": "platform skips tree digests offline"},
                       "opened_in_5b": {"K06": "base service has no per-tenant auth; isolation is a research fixture",
                                        "K07": "isolation abstraction: read/write as one access, fixed 2×2 grant"},
                       "note": "5B's isolation case reuses neither K01 (MAL issuer/target) nor K02 (attack-step "
                               "budget), so both stay OPEN with their phase-4 impact unchanged; phase 7 closes "
                               "K01–K03 in domain-mal / the UI."},
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
    print(f"phase5 handoff: p5a {'PASS' if p5a_pass else 'incomplete'} · p5b {'PASS' if p5b_pass else 'incomplete'}; "
          f"selected_passed={results.get('selected_passed')} overall_complete={results.get('overall_complete')}; "
          f"5A v1={reference.get('v1', {}).get('correspondence')} v2={reference.get('v2', {}).get('correspondence')}; "
          f"5B defect={reference_5b.get('defect', {}).get('correspondence')} "
          f"fix={reference_5b.get('fix', {}).get('correspondence')} "
          f"partial={reference_5b.get('partial', {}).get('correspondence')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
