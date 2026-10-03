"""Phase-4 domain checks (B1–B3) — the registration point for the 04B executor.

scripts/phase4_check.py imports `DOMAIN_CHECKS` from here and appends them to the phase-4 suite. Until something is
registered, the groups `b1`, `b2`, `b3` report `NO_CHECKS`, which keeps `complete` false: finishing 4A can never look
like a finished Phase 4.

How to register (see docs/execution/check-protocol.md):

    from check_runner import Check
    PY = "uv run --frozen python"
    DOMAIN_CHECKS = [
        Check("p4-b1-mal-loop", "b1", "MAL 闭环 …", f"{PY} scripts/b1_mal_evidence.py", ["P4B-B1"],
              protocol=True, produces=[f"{EV}/b1-mal.json"]),
    ]

Rules: only groups b1 / b2 / b3; `protocol=True` for evidence scripts (they report through scripts/check_result.py:
required assertions, BLOCKED with the missing prerequisite); a real-endpoint or optional backend item is
`kind="conditional"` with a `trigger` probe fixed here, never decided at run time.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_runner import Check

EV = os.environ.get("FAL_EVIDENCE_DIR", "docs/execution/evidence/phase4")
DOMAIN_GROUPS = ("b1", "b2", "b3")

PYTEST = "uv run --frozen pytest -p no:cacheprovider -q"
PY = "uv run --frozen python"

DOMAIN_CHECKS: list[Check] = [
    # ------------------------------------------------------------ B2 CAGE 4 on the platform and paired comparison
    Check("p4-b2-unit", "b2",
          "CAGE 4 平台接入（单元 + 工具链）：蓝方接口模型/驱动只预测适用性、指标原生分数与平台指标分开、轨迹逐步比较、"
          "会话一步一原生世界步/占用中不启动/越权主机与未声明动作拒绝、伪造历史重建被拒",
          f"{PYTEST} packages/environment-cage/tests", ["P4B-B2"]),
    Check("p4-b2-native-platform", "b2",
          "原生直接路径与平台适配路径逐世界步一致（含状态与随机数摘要）：sleep=官方基线 SleepAgent、monitor（恒定监控）与 react（dev / holdout）=同一动作序列的原生直接路径；"
          "参与者映射；轮中停止新进程续跑、丢失 worker 重建、丢失应答后恢复执行一次",
          f"{PY} scripts/b2_cage_evidence.py", ["P4B-B2"], protocol=True, produces=[f"{EV}/b2-cage.json"]),
    Check("p4-b2-platform", "b2",
          "持久路径（API + Temporal + PostgreSQL）：插件发现、经 API 建模型、轮中暂停 + SIGKILL worker 后完成且与原生路径一致、"
          "参与者下载无裁判数据；平台矩阵 2 场景变体 × 3 方法 × 3 共享种子配对报告（参照官方基线）与同种子复跑",
          f"{PYTEST} -m 'integration and cage' tests/integration/test_cage_platform.py", ["P4B-B2"],
          requires="services",
          produces=[f"{EV}/b2-platform-run.json", f"{EV}/b2-matrix.json", f"{EV}/b2-paired-report.md"]),
]
