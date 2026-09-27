"""Phase-1 acceptance: run every check, keep its log, write docs/handoff/phase1-checks.json.

    uv run --frozen python scripts/phase1_check.py [--only ID,ID] [--skip ID,ID]

Each check records task ids, command, result (PASS / FAIL / NOT_RUN + reason), exit code, start/end time,
duration, log file and evidence paths. Conditional checks (real LLM endpoint, Kubernetes install) are recorded
as NOT_RUN with the reason when their prerequisite is missing.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGS = ROOT / "docs" / "execution" / "evidence" / "checks"
OUT = ROOT / "docs" / "handoff" / "phase1-checks.json"
PYTEST = "uv run --frozen pytest -p no:cacheprovider"


@dataclass
class Check:
    id: str
    tasks: list[str]
    title: str
    command: str
    evidence: list[str] = field(default_factory=list)
    requires: str | None = None  # name of a prerequisite probe


CHECKS: list[Check] = [
    Check("contracts", ["P1-040", "P1-047", "P1-120", "P1-134"], "契约：Python/TS/schema 一致，漂移检查",
          f"make contracts-check && {PYTEST} tests/contracts -q && pnpm --filter @formal-lab/contracts run test",
          ["contracts/v1/DIGEST.json", "docs/contracts/v1.md"]),
    Check("contract-semantics", ["P1-120", "P1-043", "P1-045", "P1-049", "P1-050"],
          "错误输入、未知与未支持语义",
          f"{PYTEST} -q packages/model-core/tests/test_model_core.py::test_frontend_errors "
          "packages/solver-adapters/z3/tests/test_z3_engine.py::test_unsupported_profile_feature "
          "packages/solver-adapters/z3/tests/test_z3_engine.py::test_precondition_with_unknowns_matches_interpreter "
          "packages/solver-adapters/z3/tests/test_z3_engine.py::test_timeout_yields_unknown_with_reason "
          "tests/contracts/test_contracts.py::test_error_model_round_trip_and_retryability "
          "tests/contracts/test_contracts.py::test_capability_negotiation"),
    Check("engine", ["P1-121", "P1-022", "P1-023"], "引擎：可达、不可达、不变量反例、超时/未知",
          f"{PYTEST} -q packages/solver-adapters/z3/tests/test_z3_engine.py -k 'not differential' "
          "packages/model-core"),
    Check("semantics-differential", ["P1-122", "P1-063"], "语义：解释器与 Z3 小模型对照，见证可重放",
          f"{PYTEST} -q packages/solver-adapters/z3/tests/test_z3_engine.py -k differential"),
    Check("runtime-integration", ["P1-123", "P1-024", "P1-025", "P1-026", "P1-027", "P1-028", "P1-080", "P1-081",
                                  "P1-082", "P1-083", "P1-084", "P1-085", "P1-086"],
          "运行：持久化、Worker 恢复、取消、重复提交、断线续传",
          f"{PYTEST} -q -m integration tests/integration/test_platform_runs.py", requires="services"),
    Check("product-ui", ["P1-124", "P1-090", "P1-091", "P1-092", "P1-093", "P1-094", "P1-095", "P1-096"],
          "产品：UI 创建运行并查看结果（Playwright，截图与溢出检查）",
          f"{PYTEST} -q -m 'integration and ui' tests/integration/test_web_ui.py",
          ["docs/execution/evidence/ui/"], requires="services"),
    Check("sdk-cli-replay-matrix", ["P1-124", "P1-125", "P1-126", "P1-100", "P1-103", "P1-104", "P1-105", "P1-106",
                                    "P1-029", "P1-032"],
          "CLI 导出、SDK 读取、回放、导入与重跑、矩阵、Inspect 导入、包外插件",
          f"{PYTEST} -q -m integration tests/integration/test_sdk_cli_replay.py", requires="services"),
    Check("evaluation-stats", ["P1-101", "P1-102", "P1-030", "P1-031"], "统计、区间、配对比较与 Inspect 互转",
          f"{PYTEST} -q packages/evaluation"),
    Check("strategy-comparison", ["P1-125", "P1-075", "P1-135"],
          "两种非替身策略在多个固定种子/场景下可比（独立运行，无服务）",
          "uv run --frozen python -m formal_lab_example_scheduling compare --strategies rule,z3,llm-stub "
          "--seeds 1,2,3 --out docs/execution/evidence/checks/strategy-comparison.json",
          ["docs/execution/evidence/checks/strategy-comparison.json",
           "examples/neutral-scheduling/results/comparison.json"]),
    Check("example-sentinel", ["P1-135", "P1-070", "P1-071"], "生产调度示例独立运行（回归哨兵）",
          f"{PYTEST} -q examples/neutral-scheduling"),
    Check("interface-examples", ["P1-042", "P1-041"], "每个接口的可运行示例", f"{PYTEST} -q tests/examples"),
    Check("boundaries", ["P1-128", "P1-010", "P1-012"], "边界：主路径仅调用中性模拟器，核心不依赖插件",
          f"{PYTEST} -q tests/architecture"),
    Check("unit-suite", ["P1-129"], "全部非集成测试（单元/契约/架构/示例）",
          f"{PYTEST} -q -m 'not integration and not llm and not ui'"),
    Check("lint", ["P1-129"], "ruff", "make lint"),
    Check("web-build", ["P1-090"], "Web 类型检查与构建", "make web-build"),
    Check("compose-e2e", ["P1-127", "P1-111", "P1-112"], "部署：Compose 完整路径实测",
          "scripts/compose-smoke.sh", ["docs/execution/evidence/compose-smoke.json"], requires="docker"),
    Check("helm-render", ["P1-127", "P1-113"], "Helm lint / template / kubeconform", "make helm-lint",
          ["docs/execution/evidence/helm/"]),
    Check("helm-install", ["P1-127", "P1-113"], "Helm 安装（kind 临时集群，状态单独记录）",
          "scripts/helm-install-check.sh", ["docs/execution/evidence/helm/install.json"], requires="docker"),
    Check("llm-real", ["P1-074"], "真实模型集成检查（OpenAI 兼容端点）",
          f"FAL_LLM_EVIDENCE=docs/execution/evidence/P1-074-llm-integration.json {PYTEST} -q -m llm "
          "tests/integration/test_llm_real.py",
          ["docs/execution/evidence/P1-074-llm-integration.json"], requires="llm"),
    Check("ci-remote", ["P1-040"], "GitHub Actions 最近一次 CI 运行（远端）", "(GitHub API)",
          ["docs/execution/evidence/ci-run.json"], requires="network"),
]


def probe(name: str) -> str | None:
    """Return None if the prerequisite is available, else the NOT_RUN reason."""
    if name == "services":
        r = subprocess.run("docker compose -f deploy/compose/services.dev.yaml -p fal-dev up -d --wait && "
                           "uv run --frozen python -m formal_lab_api.migrate upgrade", shell=True, cwd=ROOT,
                           capture_output=True, text=True)
        return None if r.returncode == 0 else f"backing services could not start: {r.stderr[-300:]}"
    if name == "docker":
        return None if subprocess.run(["docker", "info"], capture_output=True).returncode == 0 else "no Docker daemon"
    if name == "llm":
        sys.path.insert(0, str(ROOT / "packages" / "runtime" / "src"))
        from formal_lab_runtime.settings import llm_configured

        return None if llm_configured() else "FAL_LLM_API_KEY not configured"
    if name == "network":
        return None
    return None


def versions() -> dict[str, str]:
    def out(cmd: str) -> str:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=ROOT)
        return (r.stdout or r.stderr).strip().splitlines()[0] if (r.stdout or r.stderr).strip() else "?"

    return {
        "os": out(". /etc/os-release && echo $PRETTY_NAME"), "arch": platform.machine(), "kernel": platform.release(),
        "python": platform.python_version(), "uv": out("uv --version"), "node": out("node --version"),
        "pnpm": out("pnpm --version"), "docker": out("docker version --format '{{.Server.Version}}'"),
        "z3": out("uv run --frozen python -c 'import z3;print(z3.get_version_string())'"),
        "temporalio": out("uv run --frozen python -c 'import temporalio.service as s, importlib.metadata as m;print(m.version(\"temporalio\"))'"),
        "inspect_ai": out("uv run --frozen python -c 'import inspect_ai;print(inspect_ai.__version__)'"),
        "helm": out("helm version --short"), "temporal_cli": out("temporal --version"),
    }


def run_remote_ci(check: Check, log: Path) -> tuple[str, int, str]:
    """Result of the GitHub Actions run for exactly this HEAD; waits (up to 40 min) while it is still running."""
    rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    url = "https://api.github.com/repos/3351666087/formal-agent-lab/actions/runs?per_page=20&branch=main"
    deadline = time.time() + 40 * 60
    while True:
        data = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "fal-phase1-check"}),
                                                timeout=30))
        runs = data.get("workflow_runs", [])
        log.write_text("\n".join(f"{r['head_sha'][:10]} {r['status']} {r['conclusion']} {r['html_url']}"
                                 for r in runs) + "\n")
        mine = [r for r in runs if r["head_sha"] == rev]
        if not mine:
            return "NOT_RUN", 0, f"no CI run for HEAD {rev[:10]} (not pushed?)"
        latest = mine[0]
        if latest["status"] == "completed":
            note = f"CI run {latest['html_url']} on HEAD {rev[:10]}: {latest['conclusion']}"
            return ("PASS" if latest["conclusion"] == "success" else "FAIL"), 0, note
        if time.time() > deadline:
            return "NOT_RUN", 0, f"CI run {latest['html_url']} on HEAD {rev[:10]} still {latest['status']}"
        time.sleep(30)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--skip", default="")
    args = ap.parse_args()
    only = {x for x in args.only.split(",") if x}
    skip = {x for x in args.skip.split(",") if x}
    LOGS.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "UV_PROJECT_ENVIRONMENT": os.environ.get("UV_PROJECT_ENVIRONMENT",
                                                                    str(Path.home() / ".venvs" / "formal-agent-lab"))}
    rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    previous = json.loads(OUT.read_text()) if OUT.exists() and (only or skip) else None
    results = {r["id"]: r for r in (previous or {}).get("checks", [])}
    probes: dict[str, str | None] = {}
    t_all = time.time()
    for check in CHECKS:
        if (only and check.id not in only) or check.id in skip:
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
            result, code, note = "NOT_RUN", None, reason
            log.write_text(f"NOT_RUN: {reason}\n")
        elif check.id == "ci-remote":
            try:
                result, code, note = run_remote_ci(check, log)
            except Exception as exc:
                result, code, note = "NOT_RUN", None, f"GitHub API unreachable: {exc}"
        else:
            print(f"==> {check.id}: {check.command}", flush=True)
            with log.open("w") as fh:
                fh.write(f"$ {check.command}\n# started {started} at revision {rev}\n\n")
                fh.flush()
                proc = subprocess.run(check.command, shell=True, cwd=ROOT, env=env, stdout=fh, stderr=subprocess.STDOUT)
            code = proc.returncode
            result = "PASS" if code == 0 else "FAIL"
            tail = [ln for ln in log.read_text().strip().splitlines() if ln.strip() and not ln.startswith("make[")]
            note = tail[-1][:300] if tail else ""
        finished = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        results[check.id] = {
            "id": check.id, "tasks": check.tasks, "title": check.title, "command": check.command, "result": result,
            "exit_code": code, "started_at": started, "finished_at": finished,
            "duration_s": round(time.time() - t0, 1), "log": str(log.relative_to(ROOT)), "summary": note,
            "evidence": check.evidence,
        }
        print(f"    {result} ({results[check.id]['duration_s']} s) {note}", flush=True)
    ordered = [results[c.id] for c in CHECKS if c.id in results]
    summary = {k: sum(1 for r in ordered if r["result"] == k) for k in ("PASS", "FAIL", "NOT_RUN")}
    doc = {
        "format": "phase1-checks@1",
        "handoff_version": "phase-handoff/v1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_revision": {"commit": rev, "dirty": bool(dirty)},
        "command": "make phase1-check",
        "environment": versions(),
        "summary": summary,
        "duration_s": round(time.time() - t_all, 1) if not previous else None,
        "checks": ordered,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    print(f"==> {summary} → {OUT.relative_to(ROOT)}")
    return 0 if summary["FAIL"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
