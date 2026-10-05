"""Generate the phase-4 handoff records from the check results (phase 4A; completed for 4B in B3).

Reads the strict local acceptance report (docs/execution/evidence/phase4/acceptance-local.json) and, when it adopted a
phase-4 suite report, that report (out/acceptance/phase4/results.json — the same run, the same revision); otherwise
docs/execution/evidence/phase4/checks/results.json (written by `make phase4-check`). The heavy release checks
(docs/execution/evidence/phase4/heavy-release.json, or a complete phase-2 regression in the acceptance run, which
contains them) resolve the disk blocker. Produces:
  * docs/handoff/phase4-checks.json    — a copy of the check results (the handoff's check record);
  * docs/handoff/phase4.manifest.json  — phase-handoff/v1: source revision, contract digests, workspace packages,
                                         registered plugins, check groups, 4A status, what is left to B1–B3,
                                         remaining blockers, model endpoints used (real provider vs protocol test);
  * docs/api/openapi.json              — the API as it is now (participant endpoints added in 4A).

    uv run --frozen python scripts/handoff_phase4.py

`platform_4a_complete` / `domain_4b_complete` are true only when the check run covered a1–a5 / b1–b3 and every one of
them PASSED; `phase4_complete` additionally needs the strict acceptance to be complete (phase-2 and phase-3 regression
included) — the A stage, the B stage and the whole product are reported apart.
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
ACCEPTANCE_PHASE4 = ROOT / "out" / "acceptance" / "phase4" / "results.json"
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


CONDITIONAL = [  # outside the completion denominator by the 04B task book; recorded, never counted as done
    {"item": "RL-trained CAGE 4 agents (torch / ray)", "status": "NOT_RUN", "cause": "optional in the task book; "
     "torch / ray not installed", "unblock": "install them in ~/.venvs/fal-cage and add an RL baseline cell"},
    {"item": "probabilistic backend for the domain (PRISM-games binding)", "status": "NOT_RUN",
     "cause": "optional in the task book", "unblock": "a probabilistic profile + PRISM-games (docs/local-development.md)"},
    {"item": "cloud deployment", "status": "OUT_OF_SCOPE", "cause": "local delivery only in this phase",
     "unblock": "the Helm chart (deploy/helm) against a real cluster"},
]


def _blockers(heavy: dict | None, acceptance: dict | None = None) -> list[dict]:
    """The disk blocker is resolved by a heavy-release record in which every heavy check PASSED, or by a complete
    phase-2 regression in the strict acceptance run (its local-release group builds the images and the bundle)."""
    phase2 = ((acceptance or {}).get("suites") or {}).get("phase2") or {}
    if phase2.get("complete"):
        disk = {**BLOCKERS[0], "status": "RESOLVED", "resolved_by": "docs/execution/evidence/phase4/acceptance-local.json",
                "note": "the phase-2 local-release group (image release, Compose stacks, offline install, kind install / "
                        "upgrade) passed inside the strict acceptance run at its source revision"}
        return [disk, *BLOCKERS[1:]]
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


def _results(acceptance: dict | None) -> tuple[dict, str]:
    """The phase-4 check results: the acceptance run's own phase-4 report when the acceptance adopted it."""
    adopted = ((acceptance or {}).get("suites") or {}).get("phase4") or {}
    if ACCEPTANCE_PHASE4.exists() and adopted.get("verdict") not in (None, "REPORT_MISSING", "STALE_REPORT",
                                                                       "MALFORMED_REPORT", "RUNNER_CRASHED"):
        doc = json.loads(ACCEPTANCE_PHASE4.read_text())
        if (doc.get("run") or {}).get("acceptance_nonce") == acceptance.get("nonce"):
            return doc, "out/acceptance/phase4/results.json (strict acceptance run)"
    if not RESULTS.exists():
        raise SystemExit(f"no check results at {RESULTS}; run `make phase4-check` or `make acceptance-local` first")
    return json.loads(RESULTS.read_text()), str(RESULTS.relative_to(ROOT))


def _release() -> dict | None:
    m = EV / "release-manifest.json"
    if not m.exists():
        return None
    doc = json.loads(m.read_text())
    return {"version": doc.get("version"), "source": doc.get("source"), "wheels": len(doc.get("wheels", [])),
            "images": [i.get("refs") for i in doc.get("images", [])], "examples": [e["file"] for e in doc.get("examples", [])],
            "local_profiles": {k: v.get("profile") for k, v in (doc.get("local_profiles") or {}).items()},
            "github_release": f"https://github.com/3351666087/formal-agent-lab/releases/tag/v{doc.get('version')}",
            "packages": [f"ghcr.io/3351666087/formal-agent-lab/{n}" for n in ("api", "worker", "web", "orders")],
            "manifest": str(m.relative_to(ROOT))}


def main() -> int:
    acceptance = json.loads(ACCEPTANCE.read_text()) if ACCEPTANCE.exists() else None
    results, results_source = _results(acceptance)
    CHECKS.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
    groups = results.get("groups", {})
    status = {g: groups.get(g) if isinstance(groups.get(g), str) else (groups.get(g) or {}).get("status")
              for g in PLATFORM + DOMAIN}
    platform_ok = all(status[g] == "PASS" for g in PLATFORM)
    domain_ok = all(status[g] == "PASS" for g in DOMAIN)
    contracts = {v: json.loads((ROOT / "contracts" / v / "DIGEST.json").read_text()) for v in ("v1", "v2")}
    heavy = json.loads(HEAVY.read_text()) if HEAVY.exists() else None
    real = EV / "a3-real-endpoint.json"
    real_doc = json.loads(real.read_text()) if real.exists() else {}
    b1_real = EV / "b1-real-endpoint.json"
    b1_doc = json.loads(b1_real.read_text()) if b1_real.exists() else {}
    complete = bool(acceptance and acceptance.get("complete")) and platform_ok and domain_ok
    manifest = {
        "format": "phase-handoff/v1", "phase": "4", "part": "4A + 4B (A1–A5 platform closure, B1–B3 domain closure)",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_revision": results.get("source_revision") or {"commit": _git("rev-parse", "HEAD")},
        "handoff_revision_parent": _git("rev-parse", "HEAD"),
        "contracts": {c["contract_version"]: c["digest"] for c in contracts.values()},
        "workspace_packages": tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["uv"]["workspace"]["members"],
        "plugins": _plugins(),
        "check_command": results.get("command"),
        "check_results_source": results_source,
        "check_groups": status,
        "check_summary": results.get("summary"),
        "platform_4a_complete": platform_ok,
        "domain_4b_complete": domain_ok,
        "phase4_complete": complete,
        "phase4_complete_note": ("strict acceptance complete at its source revision; every group a1–a5 and b1–b3 PASSED"
                                 if complete else "not complete: see check_groups, acceptance_local.unmet and stages"),
        "stages": (acceptance or {}).get("stages"),
        "acceptance_local": {"source_revision": acceptance.get("source_revision"), "complete": acceptance.get("complete"),
                             "started_at": acceptance.get("started_at"), "finished_at": acceptance.get("finished_at"),
                             "suites": {k: {"verdict": v.get("verdict"), "summary": v.get("summary"),
                                            "unmet": v.get("unmet")} for k, v in (acceptance.get("suites") or {}).items()},
                             "unmet": acceptance.get("unmet"),
                             "report": "docs/execution/evidence/phase4/acceptance-local.json"}
        if acceptance else None,
        "model_endpoints": {
            "real_provider": {"endpoint": real_doc.get("endpoint"), "model": real_doc.get("model_configured"),
                              "evidence": "docs/execution/evidence/phase4/a3-real-endpoint.json",
                              "label": "LLM (endpoint_kind PROVIDER)"},
            "real_provider_b1": {"endpoint": b1_doc.get("endpoint"),
                                 "adopted_from_model": (b1_doc.get("live_model_red") or {}).get("adopted_from_model"),
                                 "evidence": "docs/execution/evidence/phase4/b1-real-endpoint.json",
                                 "label": "LLM (endpoint_kind PROVIDER), phase 4B B1"} if b1_doc else None,
            "protocol_test_service": {"module": "formal_lab_strategies.protocol_server", "model": "protocol-test-v1",
                                      "label": "LLM_PROTOCOL_TEST — not a model"},
            "stub": {"label": "LLM_STUB — deterministic stand-in"}},
        "heavy_release": {k: heavy.get(k) for k in ("generated_at", "checked_commits", "summary", "all_passed")}
        | {"record": "docs/execution/evidence/phase4/heavy-release.json"} if heavy else None,
        "remaining_blockers": _blockers(heavy, acceptance),
        "conditional_items": CONDITIONAL,
        "release": _release(),
        "openapi": _openapi(),
        "handoff_docs": ["docs/handoff/phase4.md", "docs/handoff/phase4.manifest.json", "docs/handoff/phase4-checks.json",
                         "docs/execution/phase-4a.md", "docs/execution/phase-4b.md", "docs/execution/check-protocol.md",
                         "docs/assurance-scope.md", "docs/research-readout.md", "docs/reuse-ledger.md"],
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    acc = manifest["acceptance_local"] or {}
    print(f"phase4 handoff: phase 4 {'complete' if complete else 'NOT complete'} (A {platform_ok}, B {domain_ok}) {status}; "
          f"acceptance "
          f"{ {k: v['verdict'] for k, v in (acc.get('suites') or {}).items()} } at {str(acc.get('source_revision'))[:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
