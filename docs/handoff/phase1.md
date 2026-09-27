# 阶段一交接（phase-handoff/v1）

机器可读版本：[phase1.manifest.json](phase1.manifest.json)（状态、源码修订、契约摘要、路径、命令、能力、检查结果）；验收明细：[phase1-checks.json](phase1-checks.json)（每项检查的命令、结果、退出码、时间与日志）。任务书与逐项证据：[../execution/phase-1.md](../execution/phase-1.md)；决策：[../execution/decisions.md](../execution/decisions.md)。

## 1. 已完成能力与本地入口

| 能力 | 入口 |
|---|---|
| 契约 formal-lab-contracts/v1（Pydantic 单一来源 → JSON Schema / TypeScript / 文档） | `contracts/v1/`、[docs/contracts/v1.md](../contracts/v1.md)、`make contracts` |
| 有限状态 IR、参考解释器、Z3 编译器与有界查询（可达、不变量反例、单步前提，含未知项） | Web 模型工作台“编译与检查”；`POST /api/v1/model-versions/{id}/checks`；`python -m formal_lab_example_scheduling check` |
| 纯数据环境与生产调度示例（四个场景、规则 / Z3 / LLM 策略、确定性评分） | `examples/neutral-scheduling/`；`python -m formal_lab_example_scheduling run|compare` |
| 持久实验编排（Temporal）：启动、逻辑步边界暂停、继续、取消、预算、Worker 崩溃恢复 | Web 实验运行台；`fal run start/pause/resume/cancel`；`POST /api/v1/projects/{id}/runs` |
| 事件流与回放：有序幂等事件、SSE 断线续传、回放包（离线查看）、导入与重跑 | Web 证据与回放；`fal export`、`fal replay view|step|verify`、`fal import` |
| 评测：矩阵、指标聚合（缺失语义、区间、配对比较）、Inspect 适配 | Web 基准对比；`fal matrix run`；`inspect eval …/inspect_task.py` + `python -m formal_lab_eval.inspect_import` |
| Web 六个功能区、CLI、Python SDK、包外插件 | http://127.0.0.1:5173（开发）/ :8080（Compose）；`fal --help`；`formal_lab_sdk.Client`；`examples/external-plugin` |
| 构建与发行：镜像、Compose、Helm、发行清单、离线包 | `make images`、`make compose-up`、`make helm-lint`、`scripts/helm-install-check.sh`、`make release`、`make offline-bundle` |

## 2. 真实命令

```bash
bash scripts/bootstrap-dev-vm.sh && make bootstrap   # 工具链与锁定依赖
make services-up && make dev-up                       # 开发栈：web :5173 / api :8000 / worker
make demo                                             # 无服务独立示例
make phase1-check                                     # 全部验收 → docs/handoff/phase1-checks.json
make handoff                                          # 重新生成 phase1.manifest.json（与本文件的检查表）
fal export <run_id> -o run.zip && fal replay view run.zip
make build && make images && make release             # wheel、Web、镜像、发行清单
```

## 3. 验收结果

<!-- checks:begin -->
状态：**complete**

`make phase1-check` 于 2026-09-27T02:00:08Z 在提交 `5f0af4a5b2a6` 上运行（Ubuntu 24.04.4 LTS，aarch64，Python 3.12.3，Docker 29.5.2，z3 5.1.0，temporalio 1.33.0，inspect_ai 0.3.269）：{'PASS': 20, 'FAIL': 0, 'NOT_RUN': 0}。

| 检查 | 任务 | 结果 | 退出码 | 耗时 s | 日志 |
|---|---|---|---|---|---|
| 契约：Python/TS/schema 一致，漂移检查 (`contracts`) | P1-040, P1-047, P1-120, P1-134 | **PASS** | 0 | 1.9 | [log](../../docs/execution/evidence/checks/contracts.log) |
| 错误输入、未知与未支持语义 (`contract-semantics`) | P1-120, P1-043, P1-045, P1-049 … | **PASS** | 0 | 0.5 | [log](../../docs/execution/evidence/checks/contract-semantics.log) |
| 引擎：可达、不可达、不变量反例、超时/未知 (`engine`) | P1-121, P1-022, P1-023 | **PASS** | 0 | 2.4 | [log](../../docs/execution/evidence/checks/engine.log) |
| 语义：解释器与 Z3 小模型对照，见证可重放 (`semantics-differential`) | P1-122, P1-063 | **PASS** | 0 | 5.6 | [log](../../docs/execution/evidence/checks/semantics-differential.log) |
| 运行：持久化、Worker 恢复、取消、重复提交、断线续传 (`runtime-integration`) | P1-123, P1-024, P1-025, P1-026 … | **PASS** | 0 | 96.4 | [log](../../docs/execution/evidence/checks/runtime-integration.log) |
| 产品：UI 创建运行并查看结果（Playwright，截图与溢出检查） (`product-ui`) | P1-124, P1-090, P1-091, P1-092 … | **PASS** | 0 | 150.0 | [log](../../docs/execution/evidence/checks/product-ui.log) |
| CLI 导出、SDK 读取、回放、导入与重跑、矩阵、Inspect 导入、包外插件 (`sdk-cli-replay-matrix`) | P1-124, P1-125, P1-126, P1-100 … | **PASS** | 0 | 288.7 | [log](../../docs/execution/evidence/checks/sdk-cli-replay-matrix.log) |
| 统计、区间、配对比较与 Inspect 互转 (`evaluation-stats`) | P1-101, P1-102, P1-030, P1-031 | **PASS** | 0 | 4.8 | [log](../../docs/execution/evidence/checks/evaluation-stats.log) |
| 两种非替身策略在多个固定种子/场景下可比（独立运行，无服务） (`strategy-comparison`) | P1-125, P1-075, P1-135 | **PASS** | 0 | 183.7 | [log](../../docs/execution/evidence/checks/strategy-comparison.log) |
| 生产调度示例独立运行（回归哨兵） (`example-sentinel`) | P1-135, P1-070, P1-071 | **PASS** | 0 | 54.1 | [log](../../docs/execution/evidence/checks/example-sentinel.log) |
| 每个接口的可运行示例 (`interface-examples`) | P1-042, P1-041 | **PASS** | 0 | 7.1 | [log](../../docs/execution/evidence/checks/interface-examples.log) |
| 边界：主路径仅调用中性模拟器，核心不依赖插件 (`boundaries`) | P1-128, P1-010, P1-012 | **PASS** | 0 | 0.5 | [log](../../docs/execution/evidence/checks/boundaries.log) |
| 全部非集成测试（单元/契约/架构/示例） (`unit-suite`) | P1-129 | **PASS** | 0 | 117.3 | [log](../../docs/execution/evidence/checks/unit-suite.log) |
| ruff (`lint`) | P1-129 | **PASS** | 0 | 0.1 | [log](../../docs/execution/evidence/checks/lint.log) |
| Web 类型检查与构建 (`web-build`) | P1-090 | **PASS** | 0 | 0.8 | [log](../../docs/execution/evidence/checks/web-build.log) |
| 部署：Compose 完整路径实测 (`compose-e2e`) | P1-127, P1-111, P1-112 | **PASS** | 0 | 114.7 | [log](../../docs/execution/evidence/checks/compose-e2e.log) |
| Helm lint / template / kubeconform (`helm-render`) | P1-127, P1-113 | **PASS** | 0 | 2.0 | [log](../../docs/execution/evidence/checks/helm-render.log) |
| Helm 安装（kind 临时集群，状态单独记录） (`helm-install`) | P1-127, P1-113 | **PASS** | 0 | 142.9 | [log](../../docs/execution/evidence/checks/helm-install.log) |
| 真实模型集成检查（OpenAI 兼容端点） (`llm-real`) | P1-074 | **PASS** | 0 | 97.1 | [log](../../docs/execution/evidence/checks/llm-real.log) |
| GitHub Actions 最近一次 CI 运行（远端） (`ci-remote`) | P1-040 | **PASS** | 0 | 1.1 | [log](../../docs/execution/evidence/checks/ci-remote.log) |
<!-- checks:end -->

## 4. 目录地图

```
contracts/v1/                    生成的契约 schema、摘要（勿手改）
packages/contracts/              契约唯一来源（Pydantic）、接口、错误、能力、回放包格式、文档生成
packages/contracts-ts/           生成的 TypeScript 类型 + ajv/tsc 契约测试
packages/model-core/             IR 检查、规范化/摘要、参考解释器、BFS、效果比较、模型差异、能力矩阵
packages/solver-adapters/z3/     IR→Z3 编译器、有界验证器、Z3 规划策略
packages/neutral-environment/    IR 世界纯数据模拟器（Environment）
packages/strategies/             LLM 策略与模型客户端（OpenAI 兼容、替身）
packages/runtime/                插件注册表、产物存储、步骤引擎、本地运行器、manifest
packages/evaluation/             通用评分器、统计、矩阵、Inspect 适配与导入
packages/platform-api/           FastAPI、持久化与迁移、服务层、SSE、种子数据
packages/orchestrator/           Temporal 工作流、活动、Worker
packages/sdk/                    Python SDK、fal CLI、公开插件 API
web/                             React Web（六个功能区）
examples/neutral-scheduling/     生产调度示例（模型、场景、规则策略、评分器、Inspect 任务、回归哨兵、比较结果）
examples/external-plugin/        包外插件示例
examples/interfaces/             每个稳定接口的可运行示例
deploy/                          Dockerfile、Compose（开发服务 / 整栈）、Helm Chart（+ 测试夹具）
scripts/                         虚拟机工具链、开发进程、验收、发行、离线包、Helm 安装检查、交接
tests/                           契约、架构边界、接口示例、集成（平台/SDK/CLI/回放/Inspect/UI/真实模型）
docs/                            执行记录与证据、决策、契约、架构、部署、入门、复用记录、交接
```

## 5. 问题、未验证项与本地开发限制

- 已知问题（影响与复现方法见 manifest `known_issues`）：规则策略在状态延迟场景 1/5 种子预算耗尽；LLM 替身在状态延迟场景不收敛；中转站部分模型上游不可用；离线包中 api/worker 共享层重复存放；开发时 Vite 需轮询监听 virtiofs。
- 未验证：多节点 Kubernetes、Ingress 控制器、外部高可用 PostgreSQL/Temporal、Helm 升级与回滚；amd64 镜像（CI 在 x86_64 上验证了代码与集成测试）；认证与多租户。
- 能力等级：单用户本地开发配置（服务仅绑定 127.0.0.1，无认证）；Temporal 为 dev server。
- 语义范围：只支持 deterministic_finite_v1；概率、并发、稠密时间、无界整数、模型内部分观测返回 UNSUPPORTED（[能力矩阵](../architecture/capability-matrix.md)）。

## 6. 扩展入口与接续条件

- 插件：`formal_lab.plugins` entry point + `PluginDescriptor`（[plugin-integration.md](../architecture/plugin-integration.md)），前端 / 语义 profile / 规划器 / 验证器 / 环境 / 评分器 / 产物存储各有接口与参考实现。
- 契约：只通过带命名空间与版本的 `extensions` 扩展 v1；不兼容修改发布 v2；`tests/contracts/` 样例与测试供后续阶段复用。
- 回归哨兵：`python -m formal_lab_example_scheduling …` 与 `examples/neutral-scheduling/tests/test_sentinel.py`。
- 后续阶段接续前提：保持 `make phase1-check` 全部通过；领域能力以新插件包接入，不修改核心包；如需真实模型实验，配置 `FAL_LLM_*`（当前使用用户提供的 OpenAI 兼容中转站）。
