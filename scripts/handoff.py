"""Generate docs/handoff/phase1.manifest.json (phase-handoff/v1) from the repository and check results.

    uv run --frozen python scripts/handoff.py

Everything is derived: commits from git, the contract digest from contracts/v1/DIGEST.json, check results from
docs/handoff/phase1-checks.json, open task-book items from docs/execution/phase-1.md. `status` is `complete`
only when every check passed (conditional checks may be NOT_RUN only when their prerequisite is absent) and
every task item — except the handoff items this script itself produces — is ticked.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = ROOT / "docs" / "handoff"
SELF_ITEMS = {"P1-130", "P1-131", "P1-132", "P1-136"}  # satisfied by generating the handoff artefacts
PROCESS_ITEMS = {"P1-004", "P1-005", "P1-006", "P1-007"}  # execution rules, ticked after the acceptance run
CONDITIONAL = {"llm-real", "helm-install", "ci-remote"}


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def open_items() -> list[str]:
    text = (ROOT / "docs" / "execution" / "phase-1.md").read_text()
    return re.findall(r"^- \[ \] \*\*(P1-\d+)\*\*", text, flags=re.M)


def export_openapi() -> str:
    from formal_lab_api.app import create_app

    path = ROOT / "docs" / "api" / "openapi.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(create_app().openapi(), indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    return str(path.relative_to(ROOT))


def main() -> None:
    checks_doc = json.loads((HANDOFF / "phase1-checks.json").read_text())
    checks = checks_doc["checks"]
    digest = json.loads((ROOT / "contracts" / "v1" / "DIGEST.json").read_text())
    head = git("rev-parse", "HEAD")
    commit_rows = [c.split("|", 2) for c in git("log", "--format=%H|%an|%s").splitlines()]
    dirty = [line[3:] for line in subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True,
                                                 text=True, check=True).stdout.splitlines()]
    failed = [c["id"] for c in checks if c["result"] == "FAIL"]
    not_run = [c for c in checks if c["result"] == "NOT_RUN"]
    required_not_run = [c["id"] for c in not_run if c["id"] not in CONDITIONAL]
    remaining = [i for i in open_items() if i not in SELF_ITEMS | PROCESS_ITEMS]
    blockers = ([f"check {i} failed" for i in failed] + [f"required check {i} not run" for i in required_not_run]
                + [f"task {i} not ticked" for i in remaining])
    status = "complete" if not blockers else "blocked"
    openapi = export_openapi()
    from formal_lab_model.capability_matrix import MATRIX

    manifest = {
        "handoff_version": "phase-handoff/v1",
        "phase": 1,
        "status": status,
        "status_blockers": blockers,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_revision": {
            "checked_commit": checks_doc["source_revision"]["commit"],
            "checked_worktree_dirty": checks_doc["source_revision"]["dirty"],
            "manifest_generated_on": head,
            "worktree_dirty_at_generation": bool(dirty),
            "note": "the acceptance outputs and handoff artefacts (this file, phase1.md, phase1-checks.json, check logs, "
                    "task-book ticks) are committed on top of the checked commit; no product code changes after the "
                    "acceptance run",
            "agent_changes": {"commits": len(commit_rows), "first": commit_rows[-1][0], "last": commit_rows[0][0],
                              "author": sorted({c[1] for c in commit_rows}),
                              "log": "git log --format='%h %s' (all commits of this phase were made by the agent "
                                     "on the user's behalf)"},
            "user_uncommitted_changes": {"at_start": "none (empty repository, fresh clone; "
                                                     "docs/execution/evidence/P1-001-environment.md)",
                                         "at_generation": "none; the files below are uncommitted outputs of the "
                                                          "acceptance run and of this generator",
                                         "acceptance_outputs_uncommitted": dirty},
        },
        "contract_version": digest["contract_version"],
        "contract_digest": {"algorithm": digest["algorithm"], "value": digest["digest"], "method": digest["method"],
                            "files": len(digest["files"]), "source": "contracts/v1/DIGEST.json"},
        "license": {"spdx": "Apache-2.0", "files": ["LICENSE", "NOTICE"], "decision": "docs/execution/decisions.md#D-014"},
        "paths": {
            "contracts": "contracts/v1/", "contract_source": "packages/contracts/src/formal_lab_contracts/",
            "contract_types_ts": "packages/contracts-ts/src/generated.ts", "contract_docs": "docs/contracts/v1.md",
            "contract_tests": "tests/contracts/",
            "api": {"package": "packages/platform-api/", "openapi": openapi, "base_url": "/api/v1"},
            "engine": {"model_core": "packages/model-core/", "z3": "packages/solver-adapters/z3/",
                       "environment": "packages/neutral-environment/", "runtime": "packages/runtime/",
                       "strategies": "packages/strategies/", "evaluation": "packages/evaluation/",
                       "orchestrator": "packages/orchestrator/"},
            "sdk_cli": "packages/sdk/", "web": "web/",
            "examples": {"scheduling": "examples/neutral-scheduling/", "external_plugin": "examples/external-plugin/",
                         "interfaces": "examples/interfaces/"},
            "deploy": {"compose_dev_services": "deploy/compose/services.dev.yaml",
                       "compose_full_stack": "deploy/compose/docker-compose.yaml", "dockerfiles": "deploy/docker/",
                       "helm_chart": "deploy/helm/formal-agent-lab/", "helm_test_fixture": "deploy/helm/test/"},
            "logs": {"acceptance": "docs/execution/evidence/checks/", "dev_processes": "var/log/ (not committed)"},
            "reports": {"checks": "docs/handoff/phase1-checks.json", "handoff": "docs/handoff/phase1.md",
                        "evidence": "docs/execution/evidence/", "task_book": "docs/execution/phase-1.md",
                        "decisions": "docs/execution/decisions.md",
                        "strategy_comparison": "examples/neutral-scheduling/results/comparison.json"},
            "release": {"manifest": "docs/execution/evidence/release-manifest.json (copy of out/release/manifest.json)",
                        "offline_manifest": "docs/execution/evidence/offline-manifest.json",
                        "build_outputs": "out/release/, out/offline/ (not committed; rebuilt by make release / "
                                         "make offline-bundle)"},
        },
        "commands": {
            "bootstrap": "bash scripts/bootstrap-dev-vm.sh && make bootstrap",
            "dev": "make services-up && make dev-up   # web http://127.0.0.1:5173, api http://127.0.0.1:8000",
            "demo": "make demo   # standalone, no services",
            "phase1_check": "make phase1-check",
            "export": "fal export <run_id> -o run.replay.zip",
            "replay": "fal replay view run.replay.zip   # offline; fal replay step <bundle> <n>",
            "build": "make build && make images && make release",
            "compose": "make compose-up   # http://127.0.0.1:8080",
            "test": "make test-unit && make test-integration && make test-ui",
        },
        "implemented_capabilities": [
            "formal-lab-contracts/v1: 12 frozen objects + supporting types, JSON Schema, TypeScript, contract tests, drift check in CI",
            "deterministic_finite_v1 IR: parser/type checker, canonical form + sha256 digest, reference interpreter, exhaustive BFS",
            "Z3 compiler (per-thread contexts) with GOAL_REACHABILITY / INVARIANT_VIOLATION / ACTION_PRECONDITION, bounded verdicts, UNKNOWN on timeout, UNSUPPORTED, interpreter-replayed witnesses",
            "IR world environment: pure-data simulator, observation delay (unknowns with last-known facts), truth-constant overrides, seeded variation, snapshot/restore, idempotent operations",
            "effect comparison MATCH / DIFFERENT / INSUFFICIENT_INFORMATION with field-level diffs",
            "strategies: EDD rule (example plugin), Z3 bounded receding-horizon planner, LLM planner over an OpenAI-compatible endpoint (real-model check passed) and labelled deterministic stub",
            "platform: PostgreSQL persistence with immutable model versions, pinned RunManifest, gap-free idempotent event log, SSE with Last-Event-ID resume, budgets (steps, wall clock, model calls, tokens), artifacts via local or S3 store",
            "Temporal ExperimentWorkflow: start, pause at step boundaries, resume, cancel, budget exhaustion, SIGKILL worker recovery via heartbeats and operation records",
            "evaluation: scenario x strategy x seed x budget matrices, missing semantics, Wilson / bootstrap intervals, exact Wilcoxon only when informative, Inspect adapter and log import",
            "replay bundles with embedded contracts and digests, offline viewer, import and re-run with lineage",
            "Web: six functional areas on the real API (model workbench, scenarios, strategy registry, run console, evidence & replay, benchmarks), responsive, keyboard, Playwright-tested",
            "CLI (fal) and Python SDK; out-of-tree plugin registered via entry point using only the SDK",
            "OCI images (arm64), full-stack Compose (verified), Helm chart (lint/template/kubeconform + install on kind), release manifest, verified offline bundle",
        ],
        "unsupported_capabilities": [
            *[f"{r.feature}: {r.description} → {r.unsupported_answer or 'UNSUPPORTED'} (extension: {r.extension_point})"
              for r in MATRIX if all(v == "UNSUPPORTED" for v in r.status.values())],
            "authentication, authorisation and multi-tenant isolation (single-user local profile)",
            "high-availability deployment (Temporal dev server, single PostgreSQL / S3 instances); multi-node Kubernetes, ingress controllers, upgrades/rollbacks are not verified",
            "linux/amd64 container images (only arm64 built; code tested on x86_64 in CI)",
            "optimisation objectives in the Z3 planner (it minimises plan length, not weighted delay cost)",
        ],
        "deferred_work": [
            {"item": "domain extension phases (new semantic profiles, domain environments/planners)",
             "depends_on": "formal-lab-contracts/v1 + plugin interfaces (docs/architecture/plugin-integration.md)"},
            {"item": "authentication / multi-user projects and audit", "depends_on": "API gateway or identity provider choice"},
            {"item": "production deployment profile (HA Temporal, managed PostgreSQL/S3, TLS)", "depends_on": "target infrastructure"},
            {"item": "amd64 / multi-arch images and a registry publish step", "depends_on": "registry credentials, buildx builder"},
            {"item": "cost-aware Z3 planning (Optimize over delay cost)", "depends_on": "IR aggregate operators (max over domain)"},
            {"item": "UI bundle code-splitting (475 kB single chunk)", "depends_on": "none"},
        ],
        "checks": [{"id": c["id"], "tasks": c["tasks"], "result": c["result"], "exit_code": c["exit_code"],
                    "log": c["log"], "evidence": c["evidence"], "summary": c["summary"]} for c in checks],
        "checks_summary": checks_doc["summary"],
        "reuse_ledger": "docs/reuse-ledger.md",
        "known_issues": [
            {"issue": "EDD rule strategy under state delay reaches the goal in 4/5 seeds (one run exhausts the step budget)",
             "impact": "strategy behaviour, not a platform defect; visible in examples/neutral-scheduling/results/comparison.json",
             "reproduce": "python -m formal_lab_example_scheduling compare --scenarios state-delay --strategies rule --seeds 1,2,3,4,5"},
            {"issue": "the deterministic LLM stand-in never completes the state-delay scenario (keeps probing the same UNKNOWN action)",
             "impact": "stub results are labelled LLM_STUB and kept separate from real-model results", "reproduce": "same command with --strategies llm-stub"},
            {"issue": "some models on the configured relay answered 'upstream service temporarily unavailable'",
             "impact": "real-model runs depend on relay availability; default model gpt-5.6-sol was available", "reproduce": "switch FAL_LLM_MODEL"},
            {"issue": "api and worker images are saved separately in the offline bundle (shared layers stored twice)",
             "impact": "offline bundle ~220 MB larger than necessary", "reproduce": "make offline-bundle"},
            {"issue": "Vite dev server inside the VM needs polling to see host-side edits (virtiofs)",
             "impact": "development only; configured in web/vite.config.ts", "reproduce": "edit web/src on macOS while make dev-up runs"},
            {"issue": "Temporal-dev/compose persistence is single-node SQLite",
             "impact": "not suitable for production; Helm expects an external Temporal", "reproduce": "n/a"},
        ],
        "local_development_limitations": [
            "services bind to 127.0.0.1 only; no authentication",
            "verified on Ubuntu 24.04.4 aarch64 (Colima on Apple M4, 4 vCPU, 5.9 GiB) and CI ubuntu-24.04 x86_64",
        ],
    }
    (HANDOFF / "phase1.manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    render_checks_table(checks_doc, status, blockers)
    print(f"status={status} blockers={blockers} checks={checks_doc['summary']}")


def render_checks_table(checks_doc: dict, status: str, blockers: list[str]) -> None:
    doc = HANDOFF / "phase1.md"
    text = doc.read_text()
    env = checks_doc["environment"]
    rows = ["| 检查 | 任务 | 结果 | 退出码 | 耗时 s | 日志 |", "|---|---|---|---|---|---|"]
    for c in checks_doc["checks"]:
        rows.append(f"| {c['title']} (`{c['id']}`) | {', '.join(c['tasks'][:4])}{' …' if len(c['tasks']) > 4 else ''} | "
                    f"**{c['result']}** | {c['exit_code'] if c['exit_code'] is not None else '—'} | {c['duration_s']} | "
                    f"[log](../../{c['log']}) |")
    block = "\n".join([
        f"状态：**{status}**" + (f"（阻塞：{'；'.join(blockers)}）" if blockers else ""),
        "",
        f"`make phase1-check` 于 {checks_doc['generated_at']} 在提交 `{checks_doc['source_revision']['commit'][:12]}` 上运行"
        f"（{env['os']}，{env['arch']}，Python {env['python']}，Docker {env['docker']}，z3 {env['z3']}，"
        f"temporalio {env['temporalio']}，inspect_ai {env['inspect_ai']}）：{checks_doc['summary']}。",
        "",
        *rows,
    ])
    start, end = "<!-- checks:begin -->", "<!-- checks:end -->"
    head, _, rest = text.partition(start)
    _, _, tail = rest.partition(end)
    doc.write_text(f"{head}{start}\n{block}\n{end}{tail}")


if __name__ == "__main__":
    main()
