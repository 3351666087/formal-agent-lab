"""Generate the phase-4 handoff records from this invocation's check results (phase 4A; B3 completes phase 4).

Reads docs/execution/evidence/phase4/checks/results.json (written by `make phase4-check`) and, when present, the
strict local acceptance report (docs/execution/evidence/phase4/acceptance-local.json) and the heavy release checks
(docs/execution/evidence/phase4/heavy-release.json: the disk blocker is RESOLVED only when all of them PASSED), and
produces:
  * docs/handoff/phase4-checks.json    — a copy of the check results (the handoff's check record);
  * docs/handoff/phase4.manifest.json  — phase-handoff/v1: source revision, contract digests, workspace packages,
                                         registered plugins, check groups, 4A status, what is left to B1–B3,
                                         remaining blockers, model endpoints used (real provider vs protocol test);
  * docs/api/openapi.json              — the API as it is now (participant endpoints added in 4A).

    uv run --frozen python scripts/handoff_phase4.py

`platform_4a_complete` is true only when the check run covered a1–a5 and every one of them PASSED. Phase 4 as a
whole stays incomplete here: groups b1–b3 have no checks until 04B registers them (scripts/phase4_domain_checks.py).
"""

from __future__ import annotations

import json
import subprocess
import tomllib
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EV = ROOT / "docs" / "execution" / "evidence" / "phase4"
RESULTS = EV / "checks" / "results.json"
ACCEPTANCE = EV / "acceptance-local.json"
HEAVY = EV / "heavy-release.json"  # the disk-heavy release checks, run one at a time (scripts/heavy_release_summary.py)
MANIFEST = ROOT / "docs" / "handoff" / "phase4.manifest.json"
CHECKS = ROOT / "docs" / "handoff" / "phase4-checks.json"
PLATFORM = ["a1", "a2", "a3", "a4", "a5"]
DOMAIN = ["b1", "b2", "b3"]

BLOCKERS = [
    {"item": "disk-heavy release items: image-based offline bundle (scripts/offline_bundle.py --verify), image release, "
             "Compose stacks, kind install / upgrade (phase-2 local-release, phase-3 extensions)",
     "status": "BLOCKED", "cause": "host disk: needs 8 GiB plus the 15 GiB reserve; see a5-release.json offline_stack",
     "unblock": "free ≥ 23 GiB on the host (then `uv run --frozen python scripts/offline_bundle.py --verify`)"},
    {"item": "multi-user sign-in (SSO) for the participant channel", "status": "OUT_OF_SCOPE",
     "cause": "deployment scope: participant tokens are issued by the local single-user operator API",
     "unblock": "an identity provider / gateway"},
    {"item": "order service read routes on loopback are unauthenticated", "status": "DEPLOYMENT_CONDITION",
     "cause": "a participant's view is kept from a process on the same host only if it cannot reach the service port",
     "unblock": "run the service on another host / container network for untrusted participants"},
]


def _blockers(heavy: dict | None) -> list[dict]:
    """The disk blocker is resolved only by a heavy-release record in which every heavy check PASSED."""
    if not heavy or not heavy.get("all_passed"):
        return BLOCKERS
    disk = {**BLOCKERS[0], "status": "RESOLVED",
            "resolved_by": "docs/execution/evidence/phase4/heavy-release.json",
            "checked_commits": heavy.get("checked_commits"), "summary": heavy.get("summary"),
            "note": "host disk freed (files moved to the user's Google Drive), disk guard split into a host reserve "
                    "and a VM Docker-disk margin; every heavy check run one at a time — earlier FAIL / BLOCKED runs "
                    "stay in each check's history"}
    return [disk, *BLOCKERS[1:]]


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def _openapi() -> str:
    from formal_lab_api.app import create_app

    path = ROOT / "docs" / "api" / "openapi.json"
    path.write_text(json.dumps(create_app().openapi(), indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    return str(path.relative_to(ROOT))


def _plugins() -> list[str]:
    from formal_lab_runtime import default_registry

    reg = default_registry()
    return sorted(f"{e.descriptor.plugin_id}@{e.descriptor.version}" for e in reg.entries())


def main() -> int:
    if not RESULTS.exists():
        raise SystemExit(f"no check results at {RESULTS}; run `make phase4-check` first")
    results = json.loads(RESULTS.read_text())
    CHECKS.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
    groups = results.get("groups", {})
    status = {g: groups.get(g) if isinstance(groups.get(g), str) else (groups.get(g) or {}).get("status")
              for g in PLATFORM + DOMAIN}
    platform_ok = all(status[g] == "PASS" for g in PLATFORM)
    contracts = {v: json.loads((ROOT / "contracts" / v / "DIGEST.json").read_text()) for v in ("v1", "v2")}
    acceptance = json.loads(ACCEPTANCE.read_text()) if ACCEPTANCE.exists() else None
    heavy = json.loads(HEAVY.read_text()) if HEAVY.exists() else None
    real = EV / "a3-real-endpoint.json"
    real_doc = json.loads(real.read_text()) if real.exists() else {}
    manifest = {
        "format": "phase-handoff/v1", "phase": "4", "part": "4A (A1–A5, platform closure)",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_revision": results.get("source_revision") or {"commit": _git("rev-parse", "HEAD")},
        "handoff_revision_parent": _git("rev-parse", "HEAD"),
        "contracts": {c["contract_version"]: c["digest"] for c in contracts.values()},
        "workspace_packages": tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["uv"]["workspace"]["members"],
        "plugins": _plugins(),
        "check_command": results.get("command"),
        "check_groups": status,
        "check_summary": results.get("summary"),
        "platform_4a_complete": platform_ok,
        "phase4_complete": False,
        "phase4_complete_note": "left to B3: groups b1–b3 have no checks until 04B registers them in "
                                "scripts/phase4_domain_checks.py (strict acceptance stays INCOMPLETE until then)",
        "acceptance_local": {"source_revision": acceptance.get("source_revision"), "complete": acceptance.get("complete"),
                             "started_at": acceptance.get("started_at"), "finished_at": acceptance.get("finished_at"),
                             "suites": {k: {"verdict": v.get("verdict"), "summary": v.get("summary"),
                                            "unmet": v.get("unmet")} for k, v in (acceptance.get("suites") or {}).items()},
                             "report": "docs/execution/evidence/phase4/acceptance-local.json"}
        if acceptance else None,
        "model_endpoints": {
            "real_provider": {"endpoint": real_doc.get("endpoint"), "model": real_doc.get("model_configured"),
                              "evidence": "docs/execution/evidence/phase4/a3-real-endpoint.json",
                              "label": "LLM (endpoint_kind PROVIDER)"},
            "protocol_test_service": {"module": "formal_lab_strategies.protocol_server", "model": "protocol-test-v1",
                                      "label": "LLM_PROTOCOL_TEST — not a model"},
            "stub": {"label": "LLM_STUB — deterministic stand-in"}},
        "heavy_release": {k: heavy.get(k) for k in ("generated_at", "checked_commits", "summary", "all_passed")}
        | {"record": "docs/execution/evidence/phase4/heavy-release.json"} if heavy else None,
        "remaining_blockers": _blockers(heavy),
        "for_04b": {"register_checks": "scripts/phase4_domain_checks.py (groups b1–b3 only)",
                    "reuse": ["formal_lab_strategies.decision (model decisions)", "ExecutionContext / env.conditional_step "
                              "(execution basis)", "examples/subprocess-env (process-backed environments)",
                              "formal_lab_eval.experiments (paired reports)", "scripts/check_result.py (evidence scripts)"]},
        "openapi": _openapi(),
        "handoff_docs": ["docs/handoff/phase4.md", "docs/handoff/phase4.manifest.json", "docs/handoff/phase4-checks.json",
                         "docs/execution/phase-4a.md", "docs/execution/check-protocol.md", "docs/assurance-scope.md"],
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    acc = manifest["acceptance_local"] or {}
    print(f"phase4 handoff: platform 4A {'complete' if platform_ok else 'NOT complete'} {status}; acceptance "
          f"{ {k: v['verdict'] for k, v in (acc.get('suites') or {}).items()} } at {str(acc.get('source_revision'))[:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
