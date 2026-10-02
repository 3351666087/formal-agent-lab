#!/usr/bin/env python3
"""Phase-4 local checks (A1 registers the suite; A2–A5 and B1–B3 add their checks) on scripts/check_runner.py.

    make phase4-check ARGS="--group a1,a2,a3,a4,a5"     # the 4A platform packages
    make phase4-check                                    # every group; complete only when b1–b3 pass too
    uv run --frozen python scripts/check_runner.py --suite phase4 --list

Groups are fixed: a1–a5 (platform closure, 04A) and b1–b3 (domain closure, 04B, registered in
scripts/phase4_domain_checks.py). Status protocol: docs/execution/check-protocol.md. Evidence goes to
$FAL_EVIDENCE_DIR (default docs/execution/evidence/phase4).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_runner import ROOT, Check, Suite, main
from phase4_domain_checks import DOMAIN_CHECKS, DOMAIN_GROUPS

PYTEST = "uv run --frozen pytest -p no:cacheprovider -q"
PY = "uv run --frozen python"
EV = os.environ.get("FAL_EVIDENCE_DIR", "docs/execution/evidence/phase4")
IT = f"{PYTEST} -m integration"
GROUPS = ["a1", "a2", "a3", "a4", "a5", *DOMAIN_GROUPS]

PLATFORM_CHECKS = [
    # ------------------------------------------------------------ A1 checker and acceptance status
    Check("p4-a1-engine", "a1",
          "状态协议：结构化结果 / 证据存在与新鲜 / pytest 全跳过 / 条件触发 / 本次调用聚合 / 严格总验收（单元）",
          f"{PYTEST} tests/tools", ["P4A-A1"]),
    Check("p4-a1-fault-injection", "a1",
          "对真实引擎注入七种已知风险：退出 0 却 BLOCKED、必需断言 false、报告丢失、旧 PASS 残留、只选一组、配置变更后复用、完整通过",
          f"{PY} scripts/a1_status_evidence.py", ["P4A-A1"], protocol=True, produces=[f"{EV}/a1-status-protocol.json"]),
]

for c in DOMAIN_CHECKS:
    if c.group not in DOMAIN_GROUPS:
        raise ValueError(f"domain check {c.id} registered in {c.group!r}; only {DOMAIN_GROUPS} are domain groups")

SUITE = Suite(
    name="phase4",
    groups=GROUPS,
    checks=[*PLATFORM_CHECKS, *DOMAIN_CHECKS],
    out=ROOT / EV / "checks",
    # what the checks and the handoff write themselves: never part of what is being checked (no code lives here)
    outputs=("docs/execution/evidence/", "docs/handoff/", "docs/licenses.md", "docs/api/openapi.json", "out/"),
    required_groups=GROUPS,
)

if __name__ == "__main__":
    sys.exit(main(["--suite", "phase4", *sys.argv[1:]]))
