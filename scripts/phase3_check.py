#!/usr/bin/env python3
"""Phase-3A local checks (G6): the checks of this round, on the engine of scripts/check_runner.py.

    make phase3-check                                   # everything → docs/execution/evidence/phase3/checks/
    make phase3-check ARGS="--group g4-batch"           # one group
    make phase3-check ARGS="--only p3-matrix-kept-db --out out/checks/p3-matrix"
    uv run --frozen python scripts/check_runner.py --suite phase3 --list

Groups follow the task book's packages G1 … G6 plus `regression` (unit suite, full integration suite, the phase-1
sentinel). The phase-2 acceptance (docs/handoff/phase2-checks.json) is historical evidence and is not re-run here;
its checks stay loadable with `--suite phase2`. A check whose precondition is missing ends NOT_RUN (services,
Docker, running dev stack) or BLOCKED (disk below the guard, optional backend absent) with the reason — never PASS.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_runner import ROOT, Check, Suite, main

PYTEST = "uv run --frozen pytest -p no:cacheprovider -q"
PY = "uv run --frozen python"
EV = "docs/execution/evidence/phase3"
IT = f"{PYTEST} -m integration"

CHECKS = [
    # ------------------------------------------------------------ G1 contracts and plugin compatibility
    Check("p3-contracts", "g1-contracts", "契约 v2 增量无漂移（v1 冻结），Python / JSON Schema / TypeScript 样例往返",
          f"make contracts-check && {PYTEST} tests/contracts packages/contracts && pnpm --filter @formal-lab/contracts run test",
          ["P3A-G1"], ["contracts/v2/DIGEST.json", "docs/contracts/v2.md"]),
    Check("p3-compat", "g1-contracts", "阶段二 v2 回放样本可读、包外插件合同检查、架构约束、SDK",
          f"{PYTEST} tests/compat examples/external-plugin tests/architecture packages/sdk",
          ["P3A-G1"], ["tests/compat/fixtures/phase2/CAPTURE.json"]),
    # ------------------------------------------------------------ G2 execution gates and operation identity
    Check("p3-ops-unit", "g2-operations", "执行门控、请求摘要、复用 / 冲突 / 安全重发（单元与订单示例）",
          f"{PYTEST} packages/runtime/tests/test_operation_consistency.py examples/warehouse-allocation/tests/test_capacity_gate.py "
          "examples/local-order-service", ["P3A-G2"]),
    Check("p3-ops-evidence", "g2-operations", "真实订单服务进程：9 种一致性场景（逐项统计服务的操作表）",
          f"{PY} scripts/operation_consistency_evidence.py", ["P3A-G2"], [f"{EV}/g2-operations.json"]),
    Check("p3-ops-platform", "g2-operations", "持久路径：门控运行中杀 Worker、订单服务丢失应答与对账",
          f"{IT} tests/integration/test_operation_consistency_platform.py tests/integration/test_order_service_platform.py",
          ["P3A-G2"], requires="services", profile="local-services", retries=1),
    # ------------------------------------------------------------ G3 drivers, rules, releases
    Check("p3-release-unit", "g3-release", "能力报告、发布配置、流程完成与性质成立分开、最小驱动",
          f"{PYTEST} packages/runtime/tests/test_release.py", ["P3A-G3"]),
    Check("p3-release-evidence", "g3-release", "真实修订：差异 → 回归案例 → 旧版拒绝、修订版发布；陈旧依据分类",
          f"{PY} scripts/model_revision_evidence.py", ["P3A-G3"], [f"{EV}/g3-release.json"]),
    Check("p3-governance-platform", "g3-release", "API 能力报告、必需检查、差异 → 修订 → 新实验",
          f"{IT} tests/integration/test_governance_platform.py", ["P3A-G3"], requires="services",
          profile="local-services"),
    # ------------------------------------------------------------ G4 joint batches, participant input
    Check("p3-batch-unit", "g4-batch", "同步批次、成员状态、参与者视图与设置、顺序模式不变",
          f"{PYTEST} examples/warehouse-allocation/tests packages/runtime/tests/test_participants.py "
          "packages/runtime/tests/test_multi_actor.py", ["P3A-G4"]),
    Check("p3-batch-evidence", "g4-batch", "仓储批次：一轮一个环境步、轮中重启、各看各的字段、阶段二轨迹不变",
          f"{PY} scripts/joint_batch_evidence.py", ["P3A-G4"], [f"{EV}/g4-batch.json"]),
    Check("p3-batch-platform", "g4-batch", "持久路径：轮中暂停 + 杀 Worker 继续批次、轮中取消、视图校验；多参与者回归",
          f"{IT} tests/integration/test_joint_batch_platform.py tests/integration/test_multi_actor_platform.py",
          ["P3A-G4"], requires="services", profile="local-services", retries=1),
    # ------------------------------------------------------------ G5 product, design, media
    Check("p3-design-sources", "g5-product", "tokens.css 与 design/tokens.json 一致；演示 SVG / 封面 / 预览 / 架构图与源一致",
          "python3 scripts/design_tokens.py --check && python3 scripts/render_demo.py svg && "
          "git diff --exit-code -- docs/assets/demo.svg docs/assets/demo-cover.svg docs/assets/demo.html docs/assets/architecture.svg",
          ["P3A-G5"], ["web/src/tokens.css", "docs/assets/demo.svg"]),
    Check("p3-web-build", "g5-product", "Web 类型检查与生产构建", "pnpm --dir web exec tsc --noEmit -p tsconfig.json && "
          "pnpm --dir web exec vite build", ["P3A-G5"]),
    Check("p3-web-ui", "g5-product", "Playwright：六个区域、新项目到两参与者成本对比、离线回放",
          f"{PYTEST} -m 'integration and ui' tests/integration/test_web_ui.py tests/integration/test_web_product.py",
          ["P3A-G5"], requires="services", profile="local-services"),
    Check("p3-product-flows", "g5-product", "SDK / CLI：仓储批次与订单恢复的运行、查询、导出、离线读取",
          f"{PY} scripts/product_flow_evidence.py", ["P3A-G5"], [f"{EV}/g5-flows.json"], requires="devstack",
          profile="local-services"),
    Check("p3-web-flows", "g5-product", "Web：同样两个流程 + 复用标记、窄屏、键盘、减少动态（截图写到检查目录）",
          f"{PY} scripts/capture_screens.py --shots out/checks/phase3-screens", ["P3A-G5"], [f"{EV}/g5-web.json"],
          requires="devstack", profile="local-services"),
    # ------------------------------------------------------------ G6 local check and release tooling
    Check("p3-matrix-kept-db", "g6-release", "矩阵测试在保留的数据库上连续两次通过（两个独立会话）",
          f"{IT} tests/integration/test_matrix_v2_platform.py && {IT} tests/integration/test_matrix_v2_platform.py",
          ["P3A-G6"], requires="services", profile="local-services"),
    Check("p3-resources", "g6-release", "资源探测：宿主共享盘与 VM / Docker 盘（disk_guard）、profile 可用性",
          f"python3 scripts/disk_guard.py --need 12 --label phase3-check && python3 scripts/doctor.py --record {EV}/doctor.json",
          ["P3A-G6"], [f"{EV}/doctor.json"]),
    Check("p3-release-light", "g6-release", "发行（不建镜像）：全部 wheel、Web 包、干净 venv 中的 SDK/CLI、许可证清单",
          f"{PY} scripts/release.py --skip-images --out out/release-p3 --evidence {EV}/release-manifest.json",
          ["P3A-G6"], [f"{EV}/release-manifest.json", "docs/licenses.md"], heavy_gib=1),
    Check("p3-release-images", "g6-release", "发行（含 OCI 镜像与异架构构建）", f"{PY} scripts/release.py --out out/release-p3-images "
          f"--evidence {EV}/release-manifest-images.json", ["P3A-G6"], [f"{EV}/release-manifest-images.json"],
          requires="docker", kind="extension", heavy_gib=8),
    Check("p3-offline-bundle", "g6-release", "去重离线包：空目录无包仓库安装与整栈实验", f"{PY} scripts/offline_bundle.py --verify",
          ["P3A-G6"], [f"{EV}/offline-manifest.json"], requires="docker", kind="extension",
          heavy_gib=12),
    # ------------------------------------------------------------ D1 MAL model and native simulator
    Check("p3-mal-lowering", "d1-mal",
          "coreLang 攻击图降低到确定性 IR；原生模拟器 / 参考解释器 / Z3 三引擎一致；红队在 ir-world 中到达目标；配置往返（离线夹具，无需 MAL 工具链）",
          f"{PYTEST} packages/domain-mal/tests packages/environment-mal/tests", ["P3B-D1"]),
    Check("p3-mal-evidence", "d1-mal",
          "版本固定场景包导入 / 展示 / 运行；主动动作与自动效果对照；见证 / 未知 / 超时不支持 / 无法比较真实记录；原生工具链缺失时回退到固定夹具",
          f"{PY} scripts/d1_mal_evidence.py", ["P3B-D1"], [f"{EV}/d1-mal.json"]),
    # ------------------------------------------------------------ D2 broker, receipts and role boundaries
    Check("p3-broker-unit", "d2-broker",
          "验证凭据签名 / 绑定 / 状态修订 / 期限；准入规则集发布与未知条件；红蓝角色边界与凭据泄漏防护；MAL 领域准入",
          f"{PYTEST} packages/domain-broker/tests packages/domain-mal/tests/test_admission.py", ["P3B-D2"]),
    Check("p3-broker-evidence", "d2-broker",
          "准入分类（正常 + 8 类零副作用拒绝）；Broker 门控真实运行：有凭据全部放行且到达目标，无凭据全部拒绝且零副作用；标记数据泄漏检查",
          f"{PY} scripts/d2_broker_evidence.py", ["P3B-D2"], [f"{EV}/d2-broker.json"]),
    # ------------------------------------------------------------ D3 red/blue strategies and model revision
    Check("p3-strategies-unit", "d3-strategies",
          "红方规则/符号/混合三基线到达目标；蓝方最小代价割阻断全部红方；检查点恢复保持计划进度；真实偏差修订成功、旧观测差异不入回归库",
          f"{PYTEST} packages/domain-mal/tests/test_strategies.py", ["P3B-D3"]),
    Check("p3-strategies-evidence", "d3-strategies",
          "固定场景/种子/预算下红蓝基线完成实验（裁判以环境状态判定）；检查点恢复；真实模型条件项如实报告；一次修订 + 一次陈旧不污染",
          f"{PY} scripts/d3_strategies_evidence.py", ["P3B-D3"], [f"{EV}/d3-strategies.json"]),
    # ------------------------------------------------------------ D4 local service experiment loop
    Check("p3-service-unit", "d4-service",
          "领域准入规则集；Broker 门控特权动作（拒绝不触达服务）；服务/模型性质对照（一致/偏差/无法判断）",
          f"{PYTEST} examples/local-order-service/tests/test_domain_lab.py", ["P3B-D4"]),
    Check("p3-service-evidence", "d4-service",
          "真实订单服务进程全生命周期：创建→就绪→正常业务+领域实验→探针→导出→复位→二次运行→异常终止资源核对→清理；合同动作只经 Broker",
          f"{PY} scripts/d4_service_lab_evidence.py", ["P3B-D4"], [f"{EV}/d4-service-lab.json"]),
    # ------------------------------------------------------------ regression
    Check("p3-unit-all", "regression", "全部单元 / 契约 / 架构 / 示例测试（含阶段一哨兵）",
          f"{PYTEST} -m 'not integration and not llm and not ui'"),
    Check("p3-phase1-parity", "regression", "阶段一单参与者轨迹与哨兵",
          f"{PYTEST} examples/neutral-scheduling/tests/test_sentinel.py "
          "packages/runtime/tests/test_kernel.py::test_single_participant_run_reproduces_the_phase1_trajectory"),
    Check("p3-integration-all", "regression", "与 CI 相同的平台集成测试（API、Worker、Temporal、SDK/CLI、回放）",
          f"{PYTEST} tests/integration -m 'integration and not ui and not llm'", requires="services",
          profile="local-services", retries=1),
]

SUITE = Suite(
    name="phase3",
    groups=["g1-contracts", "g2-operations", "g3-release", "g4-batch", "g5-product", "g6-release", "d1-mal",
            "d2-broker", "d3-strategies", "d4-service", "regression"],
    checks=CHECKS,
    out=ROOT / "docs" / "execution" / "evidence" / "phase3" / "checks",
    # what the checks and the handoff write themselves: never part of what is being checked
    outputs=("docs/execution/evidence/", "docs/handoff/", "docs/licenses.md", "docs/api/openapi.json", "out/"),
)

if __name__ == "__main__":
    sys.exit(main(["--suite", "phase3", *sys.argv[1:]]))
