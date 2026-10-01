"""Generate the phase-3 handoff manifest and the acceptance summary from the check results (phase 3B, D6).

Reads docs/execution/evidence/phase3/checks/results.json (written by `make phase3-check`) and produces:
  * docs/handoff/phase3.manifest.json  — phase-handoff/v1 manifest: source revision, contract digest, workspace
                                         packages, registered plugins, check groups, conditional items;
  * docs/handoff/phase3-checks.json    — a copy of the check results (the handoff's check record);
  * docs/acceptance-phase3.md          — the acceptance table (groups, summary, non-PASS with cause).

    uv run --frozen python scripts/handoff_phase3.py
"""

from __future__ import annotations

import json
import subprocess
import tomllib
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "docs" / "execution" / "evidence" / "phase3" / "checks" / "results.json"
MANIFEST = ROOT / "docs" / "handoff" / "phase3.manifest.json"
CHECKS = ROOT / "docs" / "handoff" / "phase3-checks.json"
ACCEPT = ROOT / "docs" / "acceptance-phase3.md"

CONDITIONAL = [
    "真实 LLM 端点（D3 混合策略；未配置则以标注替身运行，不冒充交付）",
    "CAGE RL 训练智能体（需 torch/ray，本环境未安装；交付的是官方脚本基线）",
    "PRISM-games 领域概率绑定（备选清单；通用任务分配扩展已完成，不作为领域绑定）",
    "带 OCI 镜像的发行与去重离线包（宿主盘低于 15 GiB 保留量时 BLOCKED，非代码缺陷）",
]


def _rev() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def _workspace_packages() -> list[str]:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    return data["tool"]["uv"]["workspace"]["members"]


def _contract_digest() -> str | None:
    p = ROOT / "contracts" / "v2" / "DIGEST.json"
    if p.exists():
        try:
            return json.loads(p.read_text()).get("sha256") or json.loads(p.read_text()).get("digest")
        except Exception:
            return None
    return None


def main() -> int:
    if not RESULTS.exists():
        raise SystemExit(f"no check results at {RESULTS}; run `make phase3-check` first")
    results = json.loads(RESULTS.read_text())
    CHECKS.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")

    manifest = {
        "format": "phase-handoff/v1", "phase": "3", "generated_at": datetime.now(UTC).isoformat(),
        "source_revision": _rev(),
        "contract_version": "formal-lab-contracts/v2", "contract_digest": _contract_digest(),
        "workspace_packages": _workspace_packages(),
        "domain_packages": ["packages/domain-mal", "packages/domain-broker", "packages/environment-mal",
                            "packages/environment-cage"],
        "external_prerequisites": {
            "mal_toolchain": "~/.venvs/fal-mal (mal-toolbox 2.11.0, mal-simulator 3.2.1, coreLang v1.0.0)",
            "cage_toolchain": "~/.venvs/fal-cage (CybORG 4.0, git 8c3c50ca; core deps only)",
            "prism_games": "~/.local/opt (GPL-2.0; not distributed, D-023)",
        },
        "check_groups": results.get("groups", {}),
        "check_summary": results.get("summary", {}),
        "mandatory_passed": results.get("mandatory_passed"),
        "conditional_items": CONDITIONAL,
        "handoff_docs": ["docs/handoff/phase3.md", "docs/handoff/phase3-draft.md", "docs/assurance-scope.md",
                         "docs/acceptance-phase3.md", "docs/research-readout.md", "docs/reuse-ledger.md"],
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")

    groups = results.get("groups", {})
    summary = results.get("summary", {})
    non_pass = [(c["id"], c["result"], c.get("group", ""), (c.get("note") or c.get("reason") or ""))
                for c in results.get("checks", []) if c.get("result") != "PASS" and not c.get("inherited")]
    lines = [
        "# 阶段三本地验收（Phase 3）", "",
        f"源修订：`{manifest['source_revision'][:12]}` · 生成：{manifest['generated_at'][:19]}Z · "
        f"引擎 `scripts/check_runner.py`（format {results.get('format')}）。配套 "
        "[phase3.md](handoff/phase3.md) · [assurance-scope.md](assurance-scope.md)。", "",
        "命令：`make phase3-check`（阶段三全部组）、`make acceptance-local`（阶段二必做 + 阶段三 D1–D6）。"
        "带服务的检查未起栈时记 NOT_RUN，磁盘低于保留量的发行检查记 BLOCKED，均非代码缺陷。", "",
        f"**必做全部通过：{manifest['mandatory_passed']}** · 汇总 "
        + " · ".join(f"{k}={v}" for k, v in summary.items()), "",
        "## 检查组", "", "| 组 | 结果 |", "|---|---|",
    ]
    lines += [f"| {g} | {s} |" for g, s in groups.items()]
    lines += ["", "## 非 PASS 项（原因）", ""]
    if non_pass:
        lines += ["| 检查 | 结果 | 组 | 说明 |", "|---|---|---|---|"]
        lines += [f"| {i} | {r} | {g} | {n[:80]} |" for i, r, g, n in non_pass]
    else:
        lines += ["（全部 PASS）"]
    lines += ["", "## 条件项 / 备选（未在本环境执行，不冒充交付）", ""]
    lines += [f"- {c}" for c in CONDITIONAL]
    lines += [""]
    ACCEPT.write_text("\n".join(lines))

    print(f"wrote {MANIFEST.relative_to(ROOT)}, {CHECKS.relative_to(ROOT)}, {ACCEPT.relative_to(ROOT)}")
    print(f"  mandatory_passed={manifest['mandatory_passed']} groups={groups} summary={summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
