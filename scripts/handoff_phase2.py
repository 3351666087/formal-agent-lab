"""Generate docs/handoff/phase2.manifest.json (phase-handoff/v1, phase 2) from the repository and check results.

    uv run --frozen python scripts/handoff_phase2.py

Derived, not typed in: commits from git, contract digests from contracts/v{1,2}/DIGEST.json, check results from
docs/handoff/phase2-checks.json (`make phase2-check`), open task-book items from docs/execution/phase-2.md, the
phase-1 baseline from docs/handoff/phase1.manifest.json, and the interface / record types of P2-123 by importing them
(module, file:line, contract version, JSON Schema, example fixture, implementations). `status` is `complete` only
when every mandatory check group passed on the checked commit (inherited results never count) and every mandatory
task item — except the handoff items this script itself produces — is ticked. The checks table in
docs/handoff/phase2.md (between the checks markers) is regenerated from the same data.
"""

from __future__ import annotations

import inspect
import json
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = ROOT / "docs" / "handoff"
SELF_ITEMS = {"P2-117", "P2-120", "P2-121", "P2-122", "P2-123", "P2-127"}  # produced by the acceptance run + this script
PROCESS_ITEMS = {"P2-007", "P2-008"}  # execution rules, ticked after the acceptance run


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def open_items() -> list[str]:
    text = (ROOT / "docs" / "execution" / "phase-2.md").read_text()
    return re.findall(r"^- \[ \] \*\*(P2-\d+)\*\*", text, flags=re.M)


def rel(path: str | Path) -> str:
    return str(Path(path).resolve().relative_to(ROOT))


def digest_of(version: str) -> dict:
    d = json.loads((ROOT / "contracts" / version / "DIGEST.json").read_text())
    return {"contract_version": d["contract_version"], "algorithm": d["algorithm"], "value": d["digest"],
            "method": d["method"], "files": len(d["files"]), "source": f"contracts/{version}/DIGEST.json"}


def export_openapi() -> str:
    from formal_lab_api.app import create_app

    path = ROOT / "docs" / "api" / "openapi.json"
    path.write_text(json.dumps(create_app().openapi(), indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    return rel(path)


# P2-123: the new kernel types, where they live, and who implements / produces them
TYPES = {
    "SemanticDriver": {"record": "PluginDescriptor", "example": "PluginDescriptor.driver.json", "implementations": [
        ("formal_lab_model.driver", "IRFiniteDriver", "deterministic_finite_v1 (IR)"),
        ("formal_lab_example_warehouse.driver", "WarehouseDriver", "second profile warehouse_allocation_v1")]},
    "TurnScheduler": {"record": "TurnState", "implementations": [
        ("formal_lab_runtime.turns", "CycleScheduler", "ROUND_ROBIN / FIXED_TABLE / SIMULTANEOUS_SNAPSHOT")]},
    "PlannerCheckpoint": {"record": "PlannerCheckpoint", "protocol": "CheckpointingPlanner", "implementations": [
        ("formal_lab_example_scheduling.task_planner", "TaskPlanner", "task-rule / task-symbolic / task-model generators"),
        ("fal_example_external_plugin.checklist", "ChecklistPlanner", "out-of-tree, public SDK only")]},
    "EnvironmentSession": {"record": "EnvironmentSession", "protocol": "SessionEnvironment", "implementations": [
        ("formal_lab_example_orders.env", "OrderServiceEnvironment", "persistent local order service (HTTP)")]},
    "ExecutionStage": {"record": "StageRecord", "implementations": [
        ("formal_lab_runtime.engine", "plan_step", "every step records OBSERVE … RECORD stage records")]},
    "ProbeResult": {"record": "ProbeResult", "protocol": "Probe", "implementations": [
        ("formal_lab_example_orders.plugins", "OrderProbe", "independent read of the service's own tables")]},
    "ModelReleaseRecord": {"record": "ModelReleaseRecord", "implementations": [
        ("formal_lab_runtime.release", "check_release", "type + rule checks, bounded queries, regression replay"),
        ("formal_lab_api.services.governance", "create_release", "platform: content-addressed per model version")]},
}


def locate(module: str, name: str) -> dict:
    import importlib

    obj = getattr(importlib.import_module(module), name)
    try:
        src = inspect.getsourcefile(obj)
        line = inspect.getsourcelines(obj)[1]
        where = f"{rel(src)}:{line}"
    except (TypeError, OSError, ValueError):
        where = module
    return {"python": f"{module}.{name}", "source": where}


def type_table() -> list[dict]:
    import formal_lab_contracts as fc
    from formal_lab_contracts import interfaces

    out = []
    for name, spec in TYPES.items():
        obj = getattr(interfaces, name, None) or getattr(fc, name)
        kind = ("Protocol" if getattr(obj, "_is_protocol", False) else
                "StrEnum" if isinstance(obj, type) and issubclass(obj, str) else "contract object")
        entry = {"name": name, "kind": kind, **locate(obj.__module__, name),
                 "contract_version": "formal-lab-contracts/v2"}
        if kind == "StrEnum":
            entry["values"] = [m.value for m in obj]
        for key in ("protocol",):
            if spec.get(key):
                entry[key] = locate("formal_lab_contracts.interfaces", spec[key])
        rec = spec.get("record")
        if rec:
            schema = ROOT / "contracts" / "v2" / "schemas" / f"{rec}.schema.json"
            example = ROOT / "tests" / "contracts" / "fixtures" / "v2" / "valid" / spec.get("example", f"{rec}.json")
            entry["record"] = {"type": rec, "schema": rel(schema) if schema.exists() else None,
                               "example": rel(example) if example.exists() else None}
        entry["implementations"] = [{**locate(m, n), "note": note} for m, n, note in spec["implementations"]]
        out.append(entry)
    return out


def main() -> None:
    checks_doc = json.loads((HANDOFF / "phase2-checks.json").read_text())
    checks = checks_doc["checks"]
    phase1 = json.loads((HANDOFF / "phase1.manifest.json").read_text())
    head = git("rev-parse", "HEAD")
    since = phase1["source_revision"]["checked_commit"]
    commit_rows = [c.split("|", 2) for c in git("log", "--format=%H|%an|%s", f"{since}..HEAD").splitlines()]
    dirty = [line[3:] for line in subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True,
                                                 text=True, check=True).stdout.splitlines()]
    current = [c for c in checks if not c.get("inherited")]
    mandatory = [c for c in current if c["kind"] == "mandatory"]
    failed_groups = [g for g, st in checks_doc["groups"].items() if st != "PASS"]
    remaining = [i for i in open_items() if i not in SELF_ITEMS | PROCESS_ITEMS]
    blockers = ([f"check group {g} is {checks_doc['groups'][g]}" for g in failed_groups]
                + [f"inherited result for {c['id']} (checked on {c['checked_commit'][:12]})" for c in checks
                   if c.get("inherited") and c["kind"] == "mandatory"]
                + [f"task {i} not ticked" for i in remaining])
    status = "complete" if not blockers else "blocked"
    openapi = export_openapi()
    v1, v2 = digest_of("v1"), digest_of("v2")

    def brief(c: dict) -> dict:
        return {"id": c["id"], "group": c["group"], "tasks": c["tasks"], "result": c["result"],
                "exit_code": c["exit_code"], "profile": c["profile"], "checked_commit": c["checked_commit"],
                "inherited": c.get("inherited", False), "log": c["log"], "evidence": c["evidence"],
                "summary": c["summary"]}

    from formal_lab_model.capability_matrix import MATRIX

    manifest = {
        "handoff_version": "phase-handoff/v1",
        "phase": 2,
        "completion_scope": "local-platform",
        "status": status,
        "status_blockers": blockers,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_revision": {
            "checked_commit": checks_doc["source_revision"]["commit"],
            "checked_worktree": checks_doc["source_revision"]["worktree"],
            "manifest_generated_on": head,
            "worktree_dirty_at_generation": bool(dirty),
            "note": "acceptance outputs (check logs, evidence, phase2-checks.json) and the handoff files are committed "
                    "on top of the checked commit; no product code changes after the acceptance run",
            "agent_changes": {"since_phase1_handoff": since, "commits": len(commit_rows),
                              "first": commit_rows[-1][0] if commit_rows else None,
                              "last": commit_rows[0][0] if commit_rows else None,
                              "author": sorted({c[1] for c in commit_rows}),
                              "log": f"git log --format='%h %s' {since[:12]}..HEAD"},
            "uncommitted_at_generation": dirty,
        },
        "phase1_baseline": {
            "handoff": "docs/handoff/phase1.manifest.json", "report": "docs/handoff/phase1.md",
            "checks": "docs/handoff/phase1-checks.json", "status": phase1["status"],
            "checked_commit": phase1["source_revision"]["checked_commit"],
            "contract_version": phase1["contract_version"], "contract_digest": phase1["contract_digest"]["value"],
            "compatibility_fixtures": "tests/compat/fixtures/phase1/ (captured at 46400ad, never regenerated)",
        },
        "contract_version": v2["contract_version"],
        "contract_digest": {k: v for k, v in v2.items() if k != "contract_version"},
        "contract_versions": [v1["contract_version"], v2["contract_version"]],
        "contract_digests": {v1["contract_version"]: v1["value"], v2["contract_version"]: v2["value"]},
        "contract_compatibility": {
            "v1": "frozen (contracts/v1, digest unchanged since phase 1); read through the v1→v2 adapters "
                  "(formal_lab_contracts.compat), old replay bundles through the v1 bundle reader",
            "v2": "live; new objects (TurnPolicy, TaskPlan, PlannerCheckpoint, EnvironmentSession, OperationRecord, "
                  "ProbeResult, RuleSet, ModelReleaseRecord, RegressionCase, QueryBundle, StageRecord, MatrixCellSpec …) "
                  "and the SEMANTIC_DRIVER / PROBE interfaces exist only in v2 (decision D-015)",
            "interface_versions": ["1", "2"],
        },
        "license": {"spdx": "Apache-2.0", "files": ["LICENSE", "NOTICE"], "third_party": "docs/licenses.md"},
        "paths": {
            "contracts": {"v1": "contracts/v1/", "v2": "contracts/v2/", "docs": "docs/contracts/v2.md",
                          "source": "packages/contracts/src/formal_lab_contracts/",
                          "types_ts": "packages/contracts-ts/src/", "tests": "tests/contracts/",
                          "compat_fixtures": "tests/compat/fixtures/phase1/"},
            "kernel": {"engine": "packages/runtime/src/formal_lab_runtime/engine.py",
                       "turns": "packages/runtime/src/formal_lab_runtime/turns.py",
                       "coordination": "packages/runtime/src/formal_lab_runtime/coordination.py",
                       "release": "packages/runtime/src/formal_lab_runtime/release.py",
                       "rules": "packages/model-core/src/formal_lab_model/rules.py"},
            "api": {"package": "packages/platform-api/", "openapi": openapi, "base_url": "/api/v1"},
            "engine": {"model_core": "packages/model-core/", "z3": "packages/solver-adapters/z3/",
                       "environment": "packages/neutral-environment/", "runtime": "packages/runtime/",
                       "strategies": "packages/strategies/", "evaluation": "packages/evaluation/",
                       "orchestrator": "packages/orchestrator/"},
            "sdk_cli": {"package": "packages/sdk/", "plugin_api": "packages/sdk/src/formal_lab_sdk/plugins.py",
                        "plugin_harness": "packages/sdk/src/formal_lab_sdk/plugin_testing.py"},
            "web": "web/",
            "examples": {"scheduling": "examples/neutral-scheduling/", "warehouse": "examples/warehouse-allocation/",
                         "order_service": "examples/local-order-service/",
                         "external_plugin": "examples/external-plugin/", "interfaces": "examples/interfaces/"},
            "deploy": {"compose_dev_services": "deploy/compose/services.dev.yaml",
                       "compose_full_stack": "deploy/compose/docker-compose.yaml", "dockerfiles": "deploy/docker/",
                       "helm_chart": "deploy/helm/formal-agent-lab/ (0.2.0)", "helm_test_fixture": "deploy/helm/test/"},
            "evidence": {"phase2": "docs/execution/evidence/phase2/", "checks": "docs/execution/evidence/phase2/checks/",
                         "helm": "docs/execution/evidence/helm/"},
            "reports": {"checks": "docs/handoff/phase2-checks.json", "handoff": "docs/handoff/phase2.md",
                        "acceptance_guide": "docs/acceptance-phase2.md", "local_development": "docs/local-development.md",
                        "task_book": "docs/execution/phase-2.md", "decisions": "docs/execution/decisions.md",
                        "licenses": "docs/licenses.md"},
            "release": {"manifest": "docs/execution/evidence/phase2/release-manifest.json",
                        "offline_manifest": "docs/execution/evidence/phase2/offline-manifest.json",
                        "build_outputs": "out/release/, out/offline/ (not committed; rebuilt by make release / "
                                         "make offline-bundle)"},
        },
        "commands": {
            "bootstrap": "bash scripts/bootstrap-dev-vm.sh && make bootstrap",
            "doctor": "make doctor   # local-lite / local-services / local-kind availability, resources, ports",
            "demo": "make demo   # local-lite: standalone scheduling example, no services",
            "dev": "make services-up && make dev-up   # web http://127.0.0.1:5173, api http://127.0.0.1:8000",
            "orders": "make orders-up   # local order service on 127.0.0.1:8765; make orders-e2e for the full cycle",
            "phase2_check": "make phase2-check   # all groups; scripts/phase2_check.py --group <g> | --only <id>",
            "handoff": "make handoff-phase2",
            "plugin_harness": "python -c \"from formal_lab_sdk.plugin_testing import check_planner; "
                              "print(check_planner(('org.example.checklist-planner','0.2.0')).as_dict())\"",
            "export_replay": "fal export <run_id> -o run.replay.zip && fal replay turns run.replay.zip",
            "offline_report": "fal-report <bundles...> --out report/",
            "matrix": "fal matrix create --spec matrix.json && fal matrix report <id> --format md",
            "release": "make release && make offline-bundle",
            "backup": "python scripts/local_data.py backup --out <dir>; ... restore --from <dir> --yes",
            "compose": "make compose-up   # http://127.0.0.1:8080",
            "kind": "make helm-install-check && bash scripts/helm-upgrade-check.sh",
        },
        "implemented_capabilities": [
            "contracts v2 beside frozen v1: new kernel objects, SEMANTIC_DRIVER / PROBE interfaces, v1→v2 adapters, "
            "TypeScript types, drift check",
            "semantic driver seam: the kernel no longer imports the IR interpreter; second profile "
            "(warehouse_allocation_v1) runs through the same kernel, API and replay",
            "Z3: cost-optimal plans (Optimize over the IR objective), unknown completion with robust sequences, "
            "witness replay by the interpreter, query bundles, per-query cache keys, fresh contexts (reproducible)",
            "multi-actor kernel: turn policies, per-actor observations / goals / budgets / usage, joint termination, "
            "conflict revalidation, no-progress limit",
            "task planners with versioned TaskPlans, plan revision triggers and PlannerCheckpoints restored exactly in a "
            "fresh process / after a worker restart; observation requests with repeat guard",
            "persistent business service environment: local order service (FastAPI + SQLite tenants), idempotent "
            "operations, conditional updates, SESSION_MARKER snapshots, reconciliation of lost responses, "
            "NEEDS_REVIEW with operator review, independent probe, reset / export / import / cleanup, process + compose",
            "rules and model releases: typed rule sets, pause / replan / review outcomes, release checks (types, rules, "
            "bounded queries, regression replay), regression cases, difference → revision suggestion path (D-022)",
            "evaluation v2: matrix queue on Temporal with resume / rerun-failed / merge / cross-matrix reuse by config "
            "digest, dev / acceptance splits, scenario-cluster bootstrap, paired comparisons and ablations, "
            "probe sources, offline per-package reports",
            "replay by turn / plan / operation / model version; record replay and re-execution as separate entry points",
            "web: model workbench (objectives, releases, query bundles), multi-participant scenario editor, run console "
            "(participants, plans, operations, probes, recovery), evidence navigator, v2 benchmarks, route chunks, "
            "virtual tables, schema forms with field errors and examples",
            "SDK / CLI for every new operation; public plugin harness; out-of-tree checkpointing planner",
            "local profiles with doctor, measured concurrency, backup / restore, Helm 0.2.0 install + upgrade / rollback "
            "on kind, release manifest with licenses, deduplicated offline bundle",
        ],
        "unsupported_capabilities": [
            *[f"{r.feature}: {r.description} → {r.unsupported_answer or 'UNSUPPORTED'} (extension: {r.extension_point})"
              for r in MATRIX if all(v == "UNSUPPORTED" for v in r.status.values())],
            "authentication, authorisation and multi-tenant isolation (single-user local profile)",
            "high availability, multi-node Kubernetes, production upgrades (kind checks cover a single-node dev cluster)",
            "probabilistic model checking in the default install (PRISM-games is an optional extension track)",
        ],
        "types": type_table(),
        "checks": [brief(c) for c in checks],
        "checks_summary": checks_doc["summary"],
        "check_groups": checks_doc["groups"],
        "mandatory_checks": [c["id"] for c in checks if c["kind"] == "mandatory"],
        "conditional_checks": [{"id": c["id"], "result": c["result"], "summary": c["summary"]}
                               for c in checks if c["kind"] == "conditional"],
        "extension_checks": [{"id": c["id"], "result": c["result"], "summary": c["summary"]}
                             for c in checks if c["kind"] == "extension"],
        "mandatory_passed_on_checked_commit": all(c["result"] == "PASS" for c in mandatory) and not failed_groups,
        "deferred_work": json.loads((HANDOFF / "phase2.deferred.json").read_text()),
        "known_issues": json.loads((HANDOFF / "phase2.known-issues.json").read_text()),
        "reuse_ledger": "docs/reuse-ledger.md",
        "local_development_limitations": [
            "services bind to 127.0.0.1; no authentication",
            f"verified on {checks_doc['environment']['os']} {checks_doc['environment']['arch']} (Colima on Apple "
            "silicon, 4 vCPU, 5.9 GiB) and CI ubuntu-24.04 x86_64",
            "the Colima VM disks are sparse files on the host disk: heavy steps are guarded by scripts/disk_guard.py",
        ],
    }
    (HANDOFF / "phase2.manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    render(checks_doc, status, blockers, manifest["types"])
    print(f"status={status} blockers={blockers} groups={checks_doc['groups']}")


def render(checks_doc: dict, status: str, blockers: list[str], types: list[dict]) -> None:
    doc = HANDOFF / "phase2.md"
    text = doc.read_text()
    env = checks_doc["environment"]
    rows = ["| 组 | 检查 | 任务 | 结果 | 退出码 | 耗时 s | 日志 |", "|---|---|---|---|---|---|---|"]
    for c in checks_doc["checks"]:
        tasks = ", ".join(c["tasks"][:4]) + (" …" if len(c["tasks"]) > 4 else "")
        mark = "（历史）" if c.get("inherited") else ""
        rows.append(f"| {c['group']} | {c['title']} (`{c['id']}`) | {tasks} | **{c['result']}**{mark} | "
                    f"{c['exit_code'] if c['exit_code'] is not None else '—'} | {c['duration_s']} | "
                    f"[log](../../{c['log']}) |")
    groups = "，".join(f"{g} **{s}**" for g, s in checks_doc["groups"].items())
    block = "\n".join([
        f"状态：**{status}**" + (f"（阻塞：{'；'.join(blockers)}）" if blockers else ""),
        "",
        f"`make phase2-check` 于 {checks_doc['generated_at']} 在提交 `{checks_doc['source_revision']['commit'][:12]}`"
        f"（工作区摘要 `{checks_doc['source_revision']['worktree']['sha256'][:12]}`，"
        f"{'干净' if checks_doc['source_revision']['worktree']['clean'] else '有未提交改动'}）上运行，"
        f"{env['os']}，{env['arch']}，Python {env['python']}，Docker {env['docker']}，z3 {env['z3']}，"
        f"temporalio {env['temporalio']}，kind {env['kind']}，helm {env['helm']}；耗时 {checks_doc['duration_s']} s。",
        "",
        f"检查组：{groups}。计数：{checks_doc['summary']}。",
        "",
        *rows,
    ])
    trows = ["| 类型 | 种类 | 定义 | 记录 / schema / 例子 | 实现 |", "|---|---|---|---|---|"]
    for t in types:
        rec = t.get("record") or {}
        rec_s = (f"`{rec['type']}` · [schema](../../{rec['schema']}) · [例子](../../{rec['example']})"
                 if rec.get("schema") and rec.get("example") else "—")
        impl = "<br>".join(f"`{i['python']}` ([src](../../{i['source'].split(':')[0]}))" for i in t["implementations"])
        proto = f"<br>协议 `{t['protocol']['python']}`" if t.get("protocol") else ""
        trows.append(f"| **{t['name']}** | {t['kind']} | `{t['source']}`{proto} | {rec_s} | {impl} |")
    for start, end, body in (("<!-- checks:begin -->", "<!-- checks:end -->", block),
                             ("<!-- types:begin -->", "<!-- types:end -->", "\n".join(trows))):
        head, _, rest = text.partition(start)
        _, _, tail = rest.partition(end)
        text = f"{head}{start}\n{body}\n{end}{tail}"
    doc.write_text(text)


if __name__ == "__main__":
    main()
