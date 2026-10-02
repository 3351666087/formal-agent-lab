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
    # ------------------------------------------------------------ A2 execution basis and participant boundary
    Check("p4-a2-kernel", "a2",
          "执行依据（单元）：身份取自内核、当前版本与提案版本分开、条件写、BASIS_UNKNOWN、重发/双 worker、统一绑定与逐字段拒绝、投影与凭据设置",
          f"{PYTEST} packages/runtime/tests/test_execution_basis.py packages/runtime/tests/test_participant_projection.py "
          "packages/runtime/tests/test_participants.py packages/runtime/tests/test_operation_consistency.py "
          "packages/domain-broker/tests tests/contracts", ["P4A-A2"]),
    Check("p4-a2-order-service", "a2",
          "真实订单服务进程：写凭据、事务内 expected_revision（EXACT/LOCATIONS）、同 ID 复用/异参冲突、签发→准入→条件写的内核运行",
          f"{PYTEST} examples/local-order-service/tests/test_execution_basis_orders.py "
          "examples/local-order-service/tests/test_order_service.py", ["P4A-A2"]),
    Check("p4-a2-evidence", "a2",
          "必须复现：凭据 5/服务 7 写入 0、检查后变化被条件更新拒绝、同版本合法动作成功、ID 复用/冲突、环境/session/turn/版本错配、"
          "恢复与重发同规则、真实策略工厂 + 实际序列化/下载路径中标记字段与测试凭据不外泄（写计数取自服务记录）",
          f"{PY} scripts/a2_execution_evidence.py", ["P4A-A2"], protocol=True,
          produces=[f"{EV}/a2-execution-basis.json"]),
    Check("p4-a2-participant-api", "a2",
          "平台参与者通道：令牌绑定 run/actor、actor 参数越权 403、无/伪造/过期令牌 401、下载为投影且可离线读取（真实 API + worker）",
          f"{IT} tests/integration/test_participant_access_platform.py", ["P4A-A2"]),
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
