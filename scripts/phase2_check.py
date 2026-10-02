"""Phase-2 acceptance: `make phase2-check` → docs/handoff/phase2-checks.json.

    uv run --frozen python scripts/phase2_check.py [--only ID,ID] [--skip ID,ID] [--group GROUP]

Every check is bound to what it ran on (P2-117): the checked commit, a digest of the working tree (tracked changes
and untracked files included, so a dirty tree is visible), the local profile, the command, exit code, start / end
time, duration, log file and evidence paths. A partial re-run keeps earlier results only as history: a result
recorded on another commit or tree is marked `inherited` and never counts as a current PASS of the group.

Groups (the machine-readable check_ids of the task book): compatibility, semantic-driver, planning-objectives,
multi-actor-recovery, service-operations, model-release, evaluation-replay, product-path, local-release,
resource-profile. A group passes when all its mandatory checks pass on the checked commit. Conditional checks
(a real model endpoint) and extension checks (PRISM-games) are recorded separately with PASS / NOT_RUN /
NOT_SELECTED / BLOCKED and the reason.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGS = ROOT / "docs" / "execution" / "evidence" / "phase2" / "checks"
OUT = ROOT / "docs" / "handoff" / "phase2-checks.json"
PYTEST = "uv run --frozen pytest -p no:cacheprovider -q"
PY = "uv run --frozen python"
EV = "docs/execution/evidence/phase2"
GROUPS = ["compatibility", "semantic-driver", "planning-objectives", "multi-actor-recovery", "service-operations",
          "model-release", "evaluation-replay", "product-path", "local-release", "resource-profile"]


@dataclass
class Check:
    id: str
    group: str
    tasks: list[str]
    title: str
    command: str
    evidence: list[str] = field(default_factory=list)
    requires: str | None = None
    profile: str = "local-lite"
    kind: str = "mandatory"  # mandatory | conditional | extension
    heavy_gib: float = 0.0  # phase 4A: disk it may write; the shared runner keeps the host reserve free before it


CHECKS: list[Check] = [
    # ------------------------------------------------------------ compatibility (P2-110)
    Check("contracts-v1-v2", "compatibility", ["P2-110", "P2-010", "P2-011"],
          "契约 v1 冻结、v2 生成一致、v1→v2 升级，TS 类型与样例",
          f"make contracts-check && {PYTEST} tests/contracts && "
          "pnpm --filter @formal-lab/contracts run test",
          ["contracts/v1/DIGEST.json", "contracts/v2/DIGEST.json", "docs/contracts/v2.md"]),
    Check("phase1-parity", "compatibility", ["P2-110", "P2-001", "P2-002"],
          "阶段一单参与者调度轨迹、哨兵与旧回放包",
          f"{PYTEST} examples/neutral-scheduling/tests/test_sentinel.py "
          "packages/runtime/tests/test_kernel.py::test_single_participant_run_reproduces_the_phase1_trajectory",
          [f"{EV}/baseline/"]),
    Check("unit-all", "compatibility", ["P2-110"], "全部单元 / 架构 / 示例测试（无外部服务）",
          f"{PYTEST} -m 'not integration and not llm and not ui'"),
    Check("api-cli-sdk-old-bundles", "compatibility", ["P2-110", "P2-093"],
          "API / CLI / SDK 与阶段一回放包读取（平台）",
          f"{PYTEST} -m integration tests/integration/test_sdk_cli_replay.py tests/integration/test_platform_runs.py",
          requires="services", profile="local-services"),
    # ------------------------------------------------------------ semantic-driver (P2-111)
    Check("driver-and-second-profile", "semantic-driver", ["P2-111", "P2-012", "P2-013", "P2-018"],
          "语义驱动替换、第二语义 profile（仓储）、插件合同工具与包外插件",
          f"{PYTEST} packages/model-core tests/examples tests/architecture examples/external-plugin "
          "packages/runtime/tests/test_multi_actor.py"),
    Check("second-profile-platform", "semantic-driver", ["P2-111", "P2-012"], "第二 profile 经平台持久路径运行",
          f"{PYTEST} -m integration tests/integration/test_multi_actor_platform.py", requires="services",
          profile="local-services"),
    # ------------------------------------------------------------ planning-objectives (P2-111)
    Check("objectives-unknowns-cache", "planning-objectives", ["P2-111", "P2-020", "P2-021", "P2-022", "P2-023",
                                                               "P2-024", "P2-025", "P2-026", "P2-027", "P2-028"],
          "成本优化、未知补全与稳健序列、见证重放、缓存边界与 Z3 可复现",
          f"{PYTEST} packages/solver-adapters/z3 packages/runtime/tests/test_kernel.py packages/runtime/tests/test_runtime.py",
          [f"{EV}/z3-reproducibility.json"]),
    # ------------------------------------------------------------ multi-actor-recovery (P2-112)
    Check("task-plans-and-turns", "multi-actor-recovery", ["P2-112", "P2-030", "P2-040", "P2-041", "P2-046",
                                                          "P2-047"],
          "两种确定性策略的轮次运行、任务计划检查点与新进程恢复、无进展处理",
          f"{PYTEST} examples/neutral-scheduling/tests/test_task_planner.py packages/runtime/tests/test_multi_actor.py "
          f"&& {PY} scripts/state_delay_report.py", [f"{EV}/state-delay/report.md"]),
    Check("multi-actor-platform-recovery", "multi-actor-recovery", ["P2-112", "P2-037"],
          "暂停 / 继续 / 取消 / Worker 重启后的轮次、计数与计划进度",
          f"{PYTEST} -m integration tests/integration/test_multi_actor_platform.py", requires="services",
          profile="local-services"),
    # ------------------------------------------------------------ service-operations (P2-113)
    Check("order-service", "service-operations", ["P2-113", "P2-050", "P2-051", "P2-052", "P2-053", "P2-054",
                                                  "P2-056", "P2-060", "P2-064", "P2-065", "P2-066", "P2-067",
                                                  "P2-068"],
          "订单服务：业务动作、独立探针、响应丢失对账、重复提交、重置与清理、五种案例、纯数据对照",
          f"{PYTEST} examples/local-order-service && {PY} scripts/orders_report.py",
          [f"{EV}/orders/comparison.md"]),
    Check("order-service-platform", "service-operations", ["P2-113", "P2-054", "P2-055", "P2-057", "P2-058"],
          "订单服务经持久路径：Worker 被杀、取消交错、本地与 Temporal 一致、人工复核",
          f"{PYTEST} -m integration tests/integration/test_order_service_platform.py", requires="services",
          profile="local-services"),
    Check("order-service-e2e", "service-operations", ["P2-113", "P2-069", "P2-062"],
          "空目录创建环境 → 实验 → 导出 → 重置 → 重跑 → 清理（进程模式，真实日志）",
          f"rm -rf var/orders-e2e-check && {PY} -m formal_lab_example_orders.e2e --workdir var/orders-e2e-check "
          f"--mode process --project p2check --log {EV}/orders/e2e-process.log --summary {EV}/orders/e2e-process.json",
          [f"{EV}/orders/e2e-process.log"]),
    # ------------------------------------------------------------ model-release (P2-070 … P2-077)
    Check("rules-releases", "model-release", ["P2-070", "P2-071", "P2-072", "P2-073", "P2-074", "P2-076"],
          "规则类型检查、发布记录、回归案例、效果证据等级",
          f"{PYTEST} packages/runtime/tests/test_release.py "
          "packages/model-core/tests/test_model_core.py::test_effect_evidence_levels_and_freshness"),
    Check("difference-to-revision", "model-release", ["P2-075", "P2-077"],
          "差异 → 定位 → 新版本 → 检查 → 新实验（API / CLI）与规则暂停",
          f"{PYTEST} -m integration tests/integration/test_governance_platform.py", requires="services",
          profile="local-services"),
    # ------------------------------------------------------------ evaluation-replay (P2-115)
    Check("reports-offline", "evaluation-replay", ["P2-115", "P2-082", "P2-083", "P2-084", "P2-085", "P2-087"],
          "配对比较与消融、划分、聚类统计、探针来源、空目录离线报告",
          f"{PYTEST} packages/evaluation && {PY} scripts/offline_report_evidence.py; test $? -le 1",
          [f"{EV}/offline-report/index.md"]),
    Check("matrix-v2-platform", "evaluation-replay", ["P2-115", "P2-080", "P2-081", "P2-086"],
          "矩阵队列：中断恢复、失败重跑、增量合并、复用；回放定位与重新执行",
          f"{PYTEST} -m integration tests/integration/test_matrix_v2_platform.py "
          "tests/integration/test_sdk_cli_replay.py::test_offline_replay_navigation_and_reexecution",
          requires="services", profile="local-services"),
    # ------------------------------------------------------------ product-path (P2-114)
    Check("web-product", "product-path", ["P2-114", "P2-090", "P2-091", "P2-092", "P2-093", "P2-094", "P2-095",
                                          "P2-096", "P2-098", "P2-099"],
          "Web：新项目 → 两参与者成本对比 → 离线回放；界面状态与测量；六个区域",
          f"{PYTEST} -m 'integration and ui' tests/integration/test_web_ui.py tests/integration/test_web_product.py",
          [f"{EV}/ui/", f"{EV}/web/measurements.json", f"{EV}/web/product-acceptance.log"], requires="services",
          profile="local-services"),
    Check("sdk-vertical", "product-path", ["P2-114", "P2-097"], "公共客户端完成与 Web 等价的纵向路径",
          f"{PYTEST} -m integration tests/integration/test_sdk_vertical.py", requires="services",
          profile="local-services"),
    # ------------------------------------------------------------ local-release (P2-116)
    Check("compose-smoke", "local-release", ["P2-116", "P2-101", "P2-103"],
          "原生本地 Compose 整栈：实验、矩阵、订单服务、两参与者、SSE、S3 产物",
          "bash scripts/compose-smoke.sh", [f"{EV}/compose-smoke.json"], requires="docker",
          profile="local-services", heavy_gib=8),
    Check("orders-compose", "local-release", ["P2-116", "P2-062", "P2-069"], "订单服务 Compose 生命周期（项目标签、清理）",
          f"rm -rf var/orders-e2e-compose && {PY} -m formal_lab_example_orders.e2e --workdir var/orders-e2e-compose "
          f"--mode compose --project p2compose --log {EV}/orders/e2e-compose.log "
          f"--summary {EV}/orders/e2e-compose.json", [f"{EV}/orders/e2e-compose.log"], requires="docker",
          profile="local-services", heavy_gib=4),
    Check("offline-install", "local-release", ["P2-116", "P2-106", "P2-107"],
          "离线包：镜像去重、空目录无包仓库安装、规则 / 符号演示、整栈实验",
          f"{PY} scripts/offline_bundle.py --verify", [f"{EV}/offline-manifest.json"], requires="docker",
          profile="local-services", heavy_gib=12),
    Check("release-manifest", "local-release", ["P2-105", "P2-109", "P2-006"],
          "发行 manifest：wheel / Web / 镜像摘要、异架构构建状态、许可证清单、资源读数",
          f"{PY} scripts/release.py", [f"{EV}/release-manifest.json", "docs/licenses.md"], requires="docker",
          heavy_gib=8),
    Check("kind-install-upgrade", "local-release", ["P2-116", "P2-101", "P2-104"],
          "kind：Chart 安装、从阶段一版本升级（迁移）与回滚（仅单节点开发集群）",
          "bash scripts/helm-install-check.sh && bash scripts/helm-upgrade-check.sh",
          ["docs/execution/evidence/helm/install.json", "docs/execution/evidence/helm/upgrade.json"],
          requires="docker", profile="local-kind", heavy_gib=12),
    Check("backup-restore", "local-release", ["P2-108"], "备份 → 重置 → 恢复，用一次实际实验验证",
          f"{PY} scripts/backup_restore_check.py", [f"{EV}/backup-restore.json"], requires="services",
          profile="local-services"),
    # ------------------------------------------------------------ resource-profile (P2-100 / P2-102)
    Check("doctor", "resource-profile", ["P2-100", "P2-004"], "三个 profile 的可用性、资源估计与端口冲突",
          f"python3 scripts/doctor.py --record {EV}/doctor.json", [f"{EV}/doctor.json"]),
    Check("concurrency", "resource-profile", ["P2-102"], "按实测资源设置并发：1 并发基线与 2 并发测量",
          f"{PY} scripts/concurrency_bench.py", [f"{EV}/concurrency.json"]),
    # ------------------------------------------------------------ conditional / extension
    Check("model-real", "conditional", ["P2-039", "P2-045", "P2-046"], "真实模型端点：请求可复现与证据完整",
          f"{PY} scripts/model_evidence.py", [f"{EV}/model/evidence.json"], requires="llm", kind="conditional"),
    Check("prism-games", "extension", ["P2-X01", "P2-X02", "P2-X03", "P2-X04"],
          "深化轨道：PRISM-games 随机博弈概率查询、策略导出与模型内核对、类型化扩展与 UI",
          f"{PY} scripts/prism_games_check.py && {PYTEST} packages/solver-adapters/prism-games && "
          f"{PYTEST} -m integration tests/integration/test_probabilistic_platform.py",
          [f"{EV}/prism-games/summary.json", f"{EV}/prism-games/workbench-probabilistic.jpg"], requires="prism",
          profile="local-services", kind="extension"),
]


# outputs the acceptance run and the handoff generator write themselves: they never change what is being checked,
# so they stay out of the worktree digest (otherwise a partial re-run would disown the results of the full run)
OUTPUTS = ("docs/execution/evidence/", "docs/handoff/", "docs/execution/phase-2.md", "docs/licenses.md",
           "docs/api/openapi.json")


def worktree_digest() -> dict:
    """sha256 over `git diff HEAD` and the untracked files, i.e. every uncommitted change to the checked sources."""
    excludes = [f":(exclude){p}" for p in OUTPUTS]
    diff = subprocess.run(["git", "diff", "HEAD", "--binary", "--", ".", *excludes], cwd=ROOT,
                          capture_output=True).stdout
    untracked = [u for u in subprocess.run(["git", "ls-files", "--others", "--exclude-standard"], cwd=ROOT,
                                           capture_output=True, text=True).stdout.split()
                 if not u.startswith(OUTPUTS)]
    h = hashlib.sha256(diff)
    for path in sorted(untracked):
        p = ROOT / path
        if p.is_file():
            h.update(path.encode() + b"\0" + hashlib.sha256(p.read_bytes()).digest())
    return {"sha256": h.hexdigest(), "clean": not diff and not untracked, "changed_bytes": len(diff),
            "untracked_files": len(untracked), "excluded_outputs": list(OUTPUTS)}


def probe(name: str) -> str | None:
    if name == "services":
        r = subprocess.run("docker compose -f deploy/compose/services.dev.yaml -p fal-dev up -d --wait && "
                           f"{PY} -m formal_lab_api.migrate upgrade", shell=True, cwd=ROOT, capture_output=True,
                           text=True)
        return None if r.returncode == 0 else f"backing services could not start: {r.stderr[-300:]}"
    if name == "docker":
        return None if subprocess.run(["docker", "info"], capture_output=True).returncode == 0 else "no Docker daemon"
    if name == "llm":
        sys.path.insert(0, str(ROOT / "packages" / "runtime" / "src"))
        from formal_lab_runtime.settings import llm_configured

        return None if llm_configured() else "FAL_LLM_API_KEY not configured"
    if name == "prism":  # optional track: BLOCKED (with the reason) when the binary is not installed
        sys.path.insert(0, str(ROOT / "packages" / "solver-adapters" / "prism-games" / "src"))
        from formal_lab_solver_prism import Unavailable, locate

        try:
            locate()
        except Unavailable as exc:
            return f"BLOCKED: {exc}"
        return probe("services")
    return None


def versions() -> dict[str, str]:
    def out(cmd: str) -> str:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=ROOT)
        text = (r.stdout or r.stderr).strip()
        return text.splitlines()[0] if text else "?"

    return {"os": out(". /etc/os-release && echo $PRETTY_NAME"), "arch": platform.machine(),
            "kernel": platform.release(), "python": platform.python_version(), "uv": out("uv --version"),
            "node": out("node --version"), "pnpm": out("pnpm --version"),
            "docker": out("docker version --format '{{.Server.Version}}'"),
            "z3": out(f"{PY} -c 'import z3;print(z3.get_version_string())'"),
            "temporalio": out(f"{PY} -c 'import importlib.metadata as m;print(m.version(\"temporalio\"))'"),
            "kind": out("kind version"), "helm": out("helm version --short")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--skip", default="")
    ap.add_argument("--group", default="")
    args = ap.parse_args()
    only = {x for x in args.only.split(",") if x}
    skip = {x for x in args.skip.split(",") if x}
    groups = {x for x in args.group.split(",") if x}
    LOGS.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "UV_PROJECT_ENVIRONMENT": os.environ.get("UV_PROJECT_ENVIRONMENT",
                                                                    str(Path.home() / ".venvs" / "formal-agent-lab"))}
    env["FAL_EVIDENCE_DIR"] = EV  # tests and tools that write evidence write phase 2's (history) only from here
    for key in ("NO_PROXY", "no_proxy"):  # loopback never through a proxy from the environment (local-development §7)
        env[key] = ",".join(x for x in (env.get(key), "127.0.0.1,localhost,::1") if x)
    rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    tree = worktree_digest()
    previous = json.loads(OUT.read_text()) if OUT.exists() else None
    results = {r["id"]: r for r in (previous or {}).get("checks", [])}
    for r in results.values():  # earlier results stay as history; they count only when bound to this commit + tree
        r["inherited"] = not (r.get("checked_commit") == rev and r.get("worktree_sha256") == tree["sha256"])
    probes: dict[str, str | None] = {}
    t_all = time.time()
    for check in CHECKS:
        if (only and check.id not in only) or check.id in skip or (groups and check.group not in groups):
            continue
        log = LOGS / f"{check.id}.log"
        started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        t0 = time.time()
        reason = None
        if check.requires:
            if check.requires not in probes:
                probes[check.requires] = probe(check.requires)
            reason = probes[check.requires]
        if reason:
            result = next((k for k in ("NOT_SELECTED", "BLOCKED") if reason.startswith(k)), "NOT_RUN")
            code, note = None, reason
            log.write_text(f"{result}: {reason}\n")
        else:
            print(f"==> [{check.group}] {check.id}: {check.command}", flush=True)
            with log.open("w") as fh:
                fh.write(f"$ {check.command}\n# started {started} at {rev} (tree {tree['sha256'][:12]}, "
                         f"profile {check.profile})\n\n")
                fh.flush()
                proc = subprocess.run(check.command, shell=True, cwd=ROOT, env=env, stdout=fh, stderr=subprocess.STDOUT)
            code = proc.returncode
            result = "PASS" if code == 0 else "FAIL"
            if check.requires in ("docker", "services"):  # give the host back what the check freed in the VM
                subprocess.run([sys.executable, "scripts/disk_guard.py", "--need", "0", "--trim",
                                "--label", f"after {check.id}"], cwd=ROOT)
            tail = [ln for ln in log.read_text().strip().splitlines() if ln.strip() and not ln.startswith("make[")]
            note = tail[-1][:300] if tail else ""
        results[check.id] = {
            "id": check.id, "group": check.group, "kind": check.kind, "tasks": check.tasks, "title": check.title,
            "profile": check.profile, "command": check.command, "result": result, "exit_code": code,
            "checked_commit": rev, "worktree_sha256": tree["sha256"], "worktree_clean": tree["clean"],
            "started_at": started, "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "duration_s": round(time.time() - t0, 1), "log": str(log.relative_to(ROOT)), "summary": note,
            "evidence": check.evidence, "inherited": False}
        print(f"    {result} ({results[check.id]['duration_s']} s) {note}", flush=True)
    ordered = [results[c.id] for c in CHECKS if c.id in results]
    group_status = {}
    for g in GROUPS:
        members = [r for r in ordered if r["group"] == g]
        declared = [c.id for c in CHECKS if c.group == g]
        current = [r for r in members if not r.get("inherited")]
        if len(current) == len(declared) and all(r["result"] == "PASS" for r in current):
            group_status[g] = "PASS"
        elif any(r["result"] == "FAIL" for r in current):
            group_status[g] = "FAIL"
        else:
            group_status[g] = "INCOMPLETE"
    summary = {k: sum(1 for r in ordered if r["result"] == k and not r.get("inherited"))
               for k in ("PASS", "FAIL", "NOT_RUN", "NOT_SELECTED", "BLOCKED")}
    doc = {
        "format": "phase2-checks@1", "handoff_version": "phase-handoff/v1", "phase": 2,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_revision": {"commit": rev, "worktree": tree}, "command": "make phase2-check",
        "environment": versions(), "summary": summary, "groups": group_status,
        "mandatory_passed": all(group_status[g] == "PASS" for g in GROUPS),
        "duration_s": round(time.time() - t_all, 1), "checks": ordered,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    print(f"==> groups {group_status} → {OUT.relative_to(ROOT)}")
    return 0 if all(r["result"] != "FAIL" for r in ordered if not r.get("inherited")) else 1


if __name__ == "__main__":
    sys.exit(main())
