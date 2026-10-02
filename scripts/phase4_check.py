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
    # ------------------------------------------------------------ A3 model calls and recoverable decisions
    Check("p4-a3-unit", "a3",
          "可复用模型决策（单元）：决策随应答改变、无效应答重问/回退/失败、失败分类、来源取自应答端点、预算在发送前拦截、调用记录摘要与去凭据、任务规划器复用与续跑一致",
          f"{PYTEST} packages/strategies/tests examples/neutral-scheduling/tests/test_task_planner.py "
          "packages/evaluation/tests", ["P4A-A3"]),
    Check("p4-a3-decision", "a3",
          "真实策略工厂 + 本地运行器（协议测试服务 / 关闭端口 / 替身）：不同合法应答改变决策、无效应答回退或失败、不可达端点为失败记录、替身标签、续跑不重复已提交调用、调用与尝试预算拦截请求、任务规划器继承计划引用原调用",
          f"{PY} scripts/a3_model_decision_evidence.py", ["P4A-A3"], protocol=True,
          produces=[f"{EV}/a3-model-decision.json"]),
    Check("p4-a3-platform", "a3",
          "持久路径（Temporal + PostgreSQL）：暂停/恢复/SIGKILL worker 不重复已提交的模型调用，提交的调用 ID 均为服务实际应答，来源取自应答端点",
          f"{IT} tests/integration/test_llm_decision_platform.py", ["P4A-A3"]),
    Check("p4-a3-real-endpoint", "a3",
          "已配置真实端点的最小例子（普通调度场景任务规划器 + 订单场景 LLM 策略，小额调用预算）；未配置或不可达记 BLOCKED，协议测试服务不充当真实模型",
          f"{PY} scripts/a3_model_decision_evidence.py --real", ["P4A-A3"], protocol=True,
          produces=[f"{EV}/a3-real-endpoint.json"]),
    # ------------------------------------------------------------ A4 joint rounds, recovery, matrix and paired metrics
    Check("p4-a4-unit", "a4",
          "轮次与评测（单元）：子进程环境适配与合同检查、恢复/重建、超时与清理、自动参与者、联合批次、可手算配对报告（失败与不完整配对）",
          f"{PYTEST} examples/subprocess-env/tests packages/neutral-environment/tests examples/warehouse-allocation/tests "
          "packages/evaluation/tests "
          "packages/runtime/tests/test_multi_actor.py", ["P4A-A4"]),
    Check("p4-a4-rounds", "a4",
          "两参与者完整运行 / 空闲跳过 / 退场 / 整个实验结束的真实计数，轮中恢复，子进程环境世界步逐轮对应，可手算配对报告",
          f"{PY} scripts/a4_rounds_evidence.py", ["P4A-A4"], protocol=True,
          produces=[f"{EV}/a4-rounds.json", f"{EV}/a4-paired-report.md"]),
    Check("p4-a4-platform", "a4",
          "持久路径：子进程环境上联合批次轮中暂停 + SIGKILL worker 后批次与子进程世界步逐轮对应；矩阵相同配置复用、变更配置新执行、模型单元保守重跑，原因与计数可见",
          f"{IT} tests/integration/test_rounds_reuse_platform.py tests/integration/test_matrix_v2_platform.py "
          "tests/integration/test_joint_batch_platform.py", ["P4A-A4"]),
    # ------------------------------------------------------------ A5 product entries, narrow screens, release
    Check("p4-a5-web-types", "a5", "Web 类型检查（批次面板、来源徽标与报告的改动）",
          "pnpm --dir web exec tsc --noEmit -p tsconfig.json", ["P4A-A5"]),
    Check("p4-a5-product-web", "a5",
          "普通业务场景经 CLI 导入、SDK 配置、CLI 运行、API/CLI/Web 解释、Web/CLI 导出，API 停止后离线回放；批次面板 390 px / 平板 / 桌面 × 明暗：宽度、无截断、全文 title、键盘可达、对比度、减少动态",
          f"{IT} tests/integration/test_product_flow_a5.py", ["P4A-A5"],
          produces=[f"{EV}/a5-product-flow.json", f"{EV}/a5-narrow.json"]),
    Check("p4-a5-release", "a5",
          "发行：wheel（全部工作区成员）、Web 包、本地运行配置与清单；干净目录在线安装 + 离线回放、完全离线（--no-index）安装 + 普通场景离线回放；镜像离线包按磁盘保留量判定",
          f"{PY} scripts/a5_release_evidence.py", ["P4A-A5"], protocol=True,
          produces=[f"{EV}/a5-release.json", f"{EV}/release-manifest.json"]),
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
