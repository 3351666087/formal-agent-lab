# 阶段二交接（phase-handoff/v1，completion_scope = local-platform）

机器可读版本：[phase2.manifest.json](phase2.manifest.json)（状态、源码修订、阶段一基线、契约版本与摘要、路径、命令、能力、类型、检查分类、后续事项、已知问题）；验收明细：[phase2-checks.json](phase2-checks.json)（每项检查绑定提交、工作区摘要、profile、命令、退出码、时间、日志与产物）。运行与解读验收：[../acceptance-phase2.md](../acceptance-phase2.md)；本地安装与运维：[../local-development.md](../local-development.md)；任务书与逐项证据：[../execution/phase-2.md](../execution/phase-2.md)；决策 D-015 … D-024：[../execution/decisions.md](../execution/decisions.md)。阶段一交接原样保留：[phase1.md](phase1.md)、[phase1.manifest.json](phase1.manifest.json)。

## 1. 新增能力与本地入口

| 能力 | 入口 |
|---|---|
| 契约 v2 与冻结的 v1 并存：新内核对象、`SEMANTIC_DRIVER` / `PROBE` 接口、v1→v2 适配、TS 类型 | `contracts/v2/`、[docs/contracts/v2.md](../contracts/v2.md)、`make contracts-check` |
| 语义驱动接缝与第二语义 profile（仓储分配），同一内核、API 与回放 | `examples/warehouse-allocation/`；种子项目“仓储分配示例” |
| Z3 成本最优（区间与已证下界）、未知补全与鲁棒序列、查询包与见证重放、可复现的独立上下文 | 模型工作台“目标与发布”；`POST /model-versions/{id}/checks`（`OPTIMIZE_OBJECTIVE`、`ROBUST_SEQUENCE`）；`fal query …` |
| 多参与者内核：轮次策略、各自观测 / 目标 / 预算 / 用量、联合终止、冲突重验证、无进展上限 | 场景编辑器“参与者 / 轮次 / 终止”；运行台参与者视角 |
| 任务计划策略：版本化计划、修订触发、检查点在新进程 / Worker 重启后精确恢复；观测请求 | 策略 `task-rule` / `task-symbolic` / `task-model`（及替身 `task-model-stub`）；运行台“计划”面板；`fal replay plans` |
| 持久业务服务环境：本地订单服务、幂等操作、条件更新、会话标记快照、按 id 对账、人工复核、独立探针 | `make orders-up`、`make orders-e2e`；运行台“环境操作”；`fal ops list/review` |
| 规则集与模型发布：类型检查、暂停 / 重规划 / 复核、发布检查、回归案例、差异到修订建议 | 模型工作台“目标与发布”；`fal rules …`、`fal release …`、`fal regression …`、`fal run suggestions` |
| 评测 v2：Temporal 矩阵队列（恢复 / 重跑失败 / 合并 / 复用）、划分、聚类统计、配对比较与消融、探针来源 | 基准页 v2；`fal matrix create/cells/resume/rerun-failed/merge/report --format json|csv|md` |
| 回放按轮次 / 计划 / 操作 / 模型版本定位；离线逐模型包报告 | 证据页导航；`fal replay turns|plans|operations|model`、`fal-report` |
| Web：路由分块、虚拟表格、schema 表单字段级错误与示例、六个区域的阶段二面板 | http://127.0.0.1:5173（开发）/ :8080（Compose） |
| 公共 SDK / CLI 覆盖新增操作；插件合同工具；包外任务计划插件 | `formal_lab_sdk.Client`、`fal`、`formal_lab_sdk.plugin_testing`、`examples/external-plugin`（0.2.0） |
| 本地 profile、doctor、实测并发、备份 / 恢复、Chart 0.2.0 安装与升级 / 回滚（kind）、发行清单与许可证、去重离线包、磁盘余量保护 | `make doctor`、`scripts/local_data.py`、`scripts/helm-upgrade-check.sh`、`make release`、`make offline-bundle`、`make disk-guard` |
| 深化轨道（SELECTED）：PRISM-games 随机博弈概率查询、策略导出与模型内核对、类型化扩展与 UI | `make prism-games-check`；模型工作台“概率扩展”；`/api/v1/extensions/prism-games` |

## 2. 真实命令

```bash
bash scripts/bootstrap-dev-vm.sh && make bootstrap   # 工具链与锁定依赖（虚拟机内）
make doctor                                           # 三个 profile 的可用性、资源与端口
make services-up && make dev-up                       # 开发栈：web :5173 / api :8000 / worker
make orders-up                                        # 本地订单服务 :8765
make phase2-check                                     # 全部验收 → docs/handoff/phase2-checks.json
make handoff-phase2                                   # 重新生成 phase2.manifest.json 与本文件的两张表
fal export <run_id> -o run.zip && fal replay turns run.zip --actor b
make release && make offline-bundle                   # 发行清单、去重离线包（均受磁盘余量保护）
```

## 3. 验收结果

全量运行中 `matrix-v2-platform`（测试依赖全新的集成数据库）与 `kind-install-upgrade` 的升级半程（磁盘余量检查拒绝：宿主机 7.3 GiB，需要 10 GiB）首次失败；在同一提交、同一工作区摘要上重置测试库并清理本项目构建缓存后以 `--only` 重跑通过，下表为重跑结果（manifest `known_issues` 第一条）。并发测量在验收运行中几乎没有加速（94.9 s / 91.2 s），同日空闲时为 57.6 s / 31.8 s（第二条）。

<!-- checks:begin -->
状态：**complete**

`make phase2-check` 于 2026-09-28T16:30:50Z 在提交 `4e1f959e81f2`（工作区摘要 `e3b0c44298fc`，干净）上运行，Ubuntu 24.04.4 LTS，aarch64，Python 3.12.3，Docker 29.5.2，z3 5.1.0，temporalio 1.33.0，kind kind v0.33.0 go1.26.7 linux/arm64，helm v4.3.0+gbec5b06；耗时 779.1 s。

检查组：compatibility **PASS**，semantic-driver **PASS**，planning-objectives **PASS**，multi-actor-recovery **PASS**，service-operations **PASS**，model-release **PASS**，evaluation-replay **PASS**，product-path **PASS**，local-release **PASS**，resource-profile **PASS**。计数：{'PASS': 28, 'FAIL': 0, 'NOT_RUN': 0, 'NOT_SELECTED': 0, 'BLOCKED': 0}。

| 组 | 检查 | 任务 | 结果 | 退出码 | 耗时 s | 日志 |
|---|---|---|---|---|---|---|
| compatibility | 契约 v1 冻结、v2 生成一致、v1→v2 升级，TS 类型与样例 (`contracts-v1-v2`) | P2-110, P2-010, P2-011 | **PASS** | 0 | 4.9 | [log](../../docs/execution/evidence/phase2/checks/contracts-v1-v2.log) |
| compatibility | 阶段一单参与者调度轨迹、哨兵与旧回放包 (`phase1-parity`) | P2-110, P2-001, P2-002 | **PASS** | 0 | 60.6 | [log](../../docs/execution/evidence/phase2/checks/phase1-parity.log) |
| compatibility | 全部单元 / 架构 / 示例测试（无外部服务） (`unit-all`) | P2-110 | **PASS** | 0 | 543.6 | [log](../../docs/execution/evidence/phase2/checks/unit-all.log) |
| compatibility | API / CLI / SDK 与阶段一回放包读取（平台） (`api-cli-sdk-old-bundles`) | P2-110, P2-093 | **PASS** | 0 | 502.9 | [log](../../docs/execution/evidence/phase2/checks/api-cli-sdk-old-bundles.log) |
| semantic-driver | 语义驱动替换、第二语义 profile（仓储）、插件合同工具与包外插件 (`driver-and-second-profile`) | P2-111, P2-012, P2-013, P2-018 | **PASS** | 0 | 91.7 | [log](../../docs/execution/evidence/phase2/checks/driver-and-second-profile.log) |
| semantic-driver | 第二 profile 经平台持久路径运行 (`second-profile-platform`) | P2-111, P2-012 | **PASS** | 0 | 33.4 | [log](../../docs/execution/evidence/phase2/checks/second-profile-platform.log) |
| planning-objectives | 成本优化、未知补全与稳健序列、见证重放、缓存边界与 Z3 可复现 (`objectives-unknowns-cache`) | P2-111, P2-020, P2-021, P2-022 … | **PASS** | 0 | 275.4 | [log](../../docs/execution/evidence/phase2/checks/objectives-unknowns-cache.log) |
| multi-actor-recovery | 两种确定性策略的轮次运行、任务计划检查点与新进程恢复、无进展处理 (`task-plans-and-turns`) | P2-112, P2-030, P2-040, P2-041 … | **PASS** | 0 | 862.3 | [log](../../docs/execution/evidence/phase2/checks/task-plans-and-turns.log) |
| multi-actor-recovery | 暂停 / 继续 / 取消 / Worker 重启后的轮次、计数与计划进度 (`multi-actor-platform-recovery`) | P2-112, P2-037 | **PASS** | 0 | 35.0 | [log](../../docs/execution/evidence/phase2/checks/multi-actor-platform-recovery.log) |
| service-operations | 订单服务：业务动作、独立探针、响应丢失对账、重复提交、重置与清理、五种案例、纯数据对照 (`order-service`) | P2-113, P2-050, P2-051, P2-052 … | **PASS** | 0 | 36.1 | [log](../../docs/execution/evidence/phase2/checks/order-service.log) |
| service-operations | 订单服务经持久路径：Worker 被杀、取消交错、本地与 Temporal 一致、人工复核 (`order-service-platform`) | P2-113, P2-054, P2-055, P2-057 … | **PASS** | 0 | 58.5 | [log](../../docs/execution/evidence/phase2/checks/order-service-platform.log) |
| service-operations | 空目录创建环境 → 实验 → 导出 → 重置 → 重跑 → 清理（进程模式，真实日志） (`order-service-e2e`) | P2-113, P2-069, P2-062 | **PASS** | 0 | 137.8 | [log](../../docs/execution/evidence/phase2/checks/order-service-e2e.log) |
| model-release | 规则类型检查、发布记录、回归案例、效果证据等级 (`rules-releases`) | P2-070, P2-071, P2-072, P2-073 … | **PASS** | 0 | 4.4 | [log](../../docs/execution/evidence/phase2/checks/rules-releases.log) |
| model-release | 差异 → 定位 → 新版本 → 检查 → 新实验（API / CLI）与规则暂停 (`difference-to-revision`) | P2-075, P2-077 | **PASS** | 0 | 12.3 | [log](../../docs/execution/evidence/phase2/checks/difference-to-revision.log) |
| evaluation-replay | 配对比较与消融、划分、聚类统计、探针来源、空目录离线报告 (`reports-offline`) | P2-115, P2-082, P2-083, P2-084 … | **PASS** | 0 | 12.5 | [log](../../docs/execution/evidence/phase2/checks/reports-offline.log) |
| evaluation-replay | 矩阵队列：中断恢复、失败重跑、增量合并、复用；回放定位与重新执行 (`matrix-v2-platform`) | P2-115, P2-080, P2-081, P2-086 | **PASS** | 0 | 201.3 | [log](../../docs/execution/evidence/phase2/checks/matrix-v2-platform.log) |
| product-path | Web：新项目 → 两参与者成本对比 → 离线回放；界面状态与测量；六个区域 (`web-product`) | P2-114, P2-090, P2-091, P2-092 … | **PASS** | 0 | 463.2 | [log](../../docs/execution/evidence/phase2/checks/web-product.log) |
| product-path | 公共客户端完成与 Web 等价的纵向路径 (`sdk-vertical`) | P2-114, P2-097 | **PASS** | 0 | 53.7 | [log](../../docs/execution/evidence/phase2/checks/sdk-vertical.log) |
| local-release | 原生本地 Compose 整栈：实验、矩阵、订单服务、两参与者、SSE、S3 产物 (`compose-smoke`) | P2-116, P2-101, P2-103 | **PASS** | 0 | 419.8 | [log](../../docs/execution/evidence/phase2/checks/compose-smoke.log) |
| local-release | 订单服务 Compose 生命周期（项目标签、清理） (`orders-compose`) | P2-116, P2-062, P2-069 | **PASS** | 0 | 144.2 | [log](../../docs/execution/evidence/phase2/checks/orders-compose.log) |
| local-release | 离线包：镜像去重、空目录无包仓库安装、规则 / 符号演示、整栈实验 (`offline-install`) | P2-116, P2-106, P2-107 | **PASS** | 0 | 134.7 | [log](../../docs/execution/evidence/phase2/checks/offline-install.log) |
| local-release | 发行 manifest：wheel / Web / 镜像摘要、异架构构建状态、许可证清单、资源读数 (`release-manifest`) | P2-105, P2-109, P2-006 | **PASS** | 0 | 207.3 | [log](../../docs/execution/evidence/phase2/checks/release-manifest.log) |
| local-release | kind：Chart 安装、从阶段一版本升级（迁移）与回滚（仅单节点开发集群） (`kind-install-upgrade`) | P2-116, P2-101, P2-104 | **PASS** | 0 | 577.6 | [log](../../docs/execution/evidence/phase2/checks/kind-install-upgrade.log) |
| local-release | 备份 → 重置 → 恢复，用一次实际实验验证 (`backup-restore`) | P2-108 | **PASS** | 0 | 17.7 | [log](../../docs/execution/evidence/phase2/checks/backup-restore.log) |
| resource-profile | 三个 profile 的可用性、资源估计与端口冲突 (`doctor`) | P2-100, P2-004 | **PASS** | 0 | 3.4 | [log](../../docs/execution/evidence/phase2/checks/doctor.log) |
| resource-profile | 按实测资源设置并发：1 并发基线与 2 并发测量 (`concurrency`) | P2-102 | **PASS** | 0 | 186.1 | [log](../../docs/execution/evidence/phase2/checks/concurrency.log) |
| conditional | 真实模型端点：请求可复现与证据完整 (`model-real`) | P2-039, P2-045, P2-046 | **PASS** | 0 | 344.7 | [log](../../docs/execution/evidence/phase2/checks/model-real.log) |
| extension | 深化轨道：PRISM-games 随机博弈概率查询、策略导出与模型内核对、类型化扩展与 UI (`prism-games`) | P2-X01, P2-X02, P2-X03, P2-X04 | **PASS** | 0 | 25.3 | [log](../../docs/execution/evidence/phase2/checks/prism-games.log) |
<!-- checks:end -->

## 4. 内核类型（P2-123）

实际类型、定义位置、契约版本（均为 `formal-lab-contracts/v2`）、JSON Schema、例子与实现；由 `scripts/handoff_phase2.py` 导入代码生成，manifest 的 `types` 字段含完整路径与行号。

<!-- types:begin -->
| 类型 | 种类 | 定义 | 记录 / schema / 例子 | 实现 |
|---|---|---|---|---|
| **SemanticDriver** | Protocol | `packages/contracts/src/formal_lab_contracts/interfaces.py:216` | `PluginDescriptor` · [schema](../../contracts/v2/schemas/PluginDescriptor.schema.json) · [例子](../../tests/contracts/fixtures/v2/valid/PluginDescriptor.driver.json) | `formal_lab_model.driver.IRFiniteDriver` ([src](../../packages/model-core/src/formal_lab_model/driver.py))<br>`formal_lab_example_warehouse.driver.WarehouseDriver` ([src](../../examples/warehouse-allocation/src/formal_lab_example_warehouse/driver.py)) |
| **TurnScheduler** | Protocol | `packages/contracts/src/formal_lab_contracts/interfaces.py:230` | `TurnState` · [schema](../../contracts/v2/schemas/TurnState.schema.json) · [例子](../../tests/contracts/fixtures/v2/valid/TurnState.json) | `formal_lab_runtime.turns.CycleScheduler` ([src](../../packages/runtime/src/formal_lab_runtime/turns.py)) |
| **PlannerCheckpoint** | contract object | `packages/contracts/src/formal_lab_contracts/execution.py:172`<br>协议 `formal_lab_contracts.interfaces.CheckpointingPlanner` | `PlannerCheckpoint` · [schema](../../contracts/v2/schemas/PlannerCheckpoint.schema.json) · [例子](../../tests/contracts/fixtures/v2/valid/PlannerCheckpoint.json) | `formal_lab_example_scheduling.task_planner.TaskPlanner` ([src](../../examples/neutral-scheduling/src/formal_lab_example_scheduling/task_planner.py))<br>`fal_example_external_plugin.checklist.ChecklistPlanner` ([src](../../examples/external-plugin/src/fal_example_external_plugin/checklist.py)) |
| **EnvironmentSession** | contract object | `packages/contracts/src/formal_lab_contracts/execution.py:258`<br>协议 `formal_lab_contracts.interfaces.SessionEnvironment` | `EnvironmentSession` · [schema](../../contracts/v2/schemas/EnvironmentSession.schema.json) · [例子](../../tests/contracts/fixtures/v2/valid/EnvironmentSession.json) | `formal_lab_example_orders.env.OrderServiceEnvironment` ([src](../../examples/local-order-service/src/formal_lab_example_orders/env.py)) |
| **ExecutionStage** | StrEnum | `packages/contracts/src/formal_lab_contracts/kernel.py:245` | `StageRecord` · [schema](../../contracts/v2/schemas/StageRecord.schema.json) · [例子](../../tests/contracts/fixtures/v2/valid/StageRecord.json) | `formal_lab_runtime.engine.plan_step` ([src](../../packages/runtime/src/formal_lab_runtime/engine.py)) |
| **ProbeResult** | contract object | `packages/contracts/src/formal_lab_contracts/execution.py:284`<br>协议 `formal_lab_contracts.interfaces.Probe` | `ProbeResult` · [schema](../../contracts/v2/schemas/ProbeResult.schema.json) · [例子](../../tests/contracts/fixtures/v2/valid/ProbeResult.json) | `formal_lab_example_orders.plugins.OrderProbe` ([src](../../examples/local-order-service/src/formal_lab_example_orders/plugins.py)) |
| **ModelReleaseRecord** | contract object | `packages/contracts/src/formal_lab_contracts/governance.py:150` | `ModelReleaseRecord` · [schema](../../contracts/v2/schemas/ModelReleaseRecord.schema.json) · [例子](../../tests/contracts/fixtures/v2/valid/ModelReleaseRecord.json) | `formal_lab_runtime.release.check_release` ([src](../../packages/runtime/src/formal_lab_runtime/release.py))<br>`formal_lab_api.services.governance.create_release` ([src](../../packages/platform-api/src/formal_lab_api/services/governance.py)) |
<!-- types:end -->

## 5. 目录地图（阶段二新增与变化）

```
contracts/v2/                         v2 schema 与摘要（生成，勿手改）；contracts/v1/ 冻结
packages/contracts/                   + execution.py（轮次、任务计划、检查点、会话、操作、探针、阶段记录）、governance.py（规则、发布、回归）、kernel.py、compat.py（v1→v2）
packages/model-core/                  + driver.py（IR 语义驱动）、objectives.py、rules.py
packages/solver-adapters/z3/          + optimize.py（成本最优、鲁棒序列）
packages/solver-adapters/prism-games/ 新：可选 PRISM-games 扩展（博弈载荷、进程适配器、独立求解器）
packages/runtime/                     engine.py 改为轮次内核；+ turns.py、coordination.py、release.py、query.py
packages/platform-api/                迁移 0002；+ services/operations.py、governance.py、matrices.py（v2）、probabilistic.py
packages/orchestrator/                + MatrixWorkflow、matrix_claim / matrix_settle 活动
packages/evaluation/                  + experiments.py（报告 v2）、offline.py（fal-report）
packages/sdk/                         + plugin_testing.py；plugins.py 导出阶段二接口；CLI 新命令
web/src/                              路由分块；components/RunKernel、ReleasePanel、MatrixV2、ProbabilisticPanel
examples/warehouse-allocation/        第二语义 profile
examples/local-order-service/         本地业务服务、环境适配器、探针、生命周期、端到端
examples/external-plugin/             0.2.0：+ checklist.py（任务计划 + 检查点）
scripts/                              phase2_check.py、handoff_phase2.py、disk_guard.py、local_data.py、backup_restore_check.py、concurrency_bench.py、helm-upgrade-check.sh、kind-load-public.sh、license_inventory.py、prism_games_check.py、orders_report.py、state_delay_report.py、offline_report_evidence.py、model_evidence.py
docs/execution/evidence/phase2/       阶段二证据（checks/ 为验收日志）
```

## 6. 兼容决策

- 契约：v1 冻结（摘要与阶段一相同），新数据只以 v2 写出；读取 v1 数据与阶段一回放包经 `formal_lab_contracts.compat` 升级（D-015、D-019）。`tests/compat/fixtures/phase1/` 是在阶段一代码上捕获、不再重新生成的基线。
- 数据库：迁移 0002 只增加列与表，旧行保留写入时的契约版本；阶段一应用可在 0002 上运行（kind 回滚检查）。
- 单参与者运行与阶段一轨迹相同（`phase1-parity`）；Z3 结果以单独 / 批量一致的新基线为准（D-017）。
- 多参与者中陈旧依据的效果差异不生成修订建议与回归案例（D-022）；业务服务的保证在服务端事务中（D-021）。

## 7. 已知问题、条件项与后续事项

- 已知问题与复现方法见 manifest `known_issues`；条件检查（真实模型）与扩展检查（PRISM-games）的结果单独列在 `conditional_checks` / `extension_checks`，不影响必做结论。
- 后续部署事项（认证、多用户、生产部署、多节点升级、镜像仓库发布、amd64 原生、真实外部系统、概率 profile、真实模型规模化）及各自的触发条件与依赖见 manifest `deferred_work`。
- 发行产物：`out/release/`（wheel、Web 包、manifest）与 `out/offline/`（离线包）不入库，由 `make release`、`make offline-bundle` 重建；入库的清单副本在 `docs/execution/evidence/phase2/release-manifest.json`、`offline-manifest.json`；许可证清单 [../licenses.md](../licenses.md)。

## 8. 接续入口（阶段三）

- 引用本交接的实际版本：`phase2.manifest.json` 的 `source_revision.checked_commit` 与 `contract_digests`；阶段三开始时先跑 `make phase2-check`，结果全部 PASS 再改动。
- 新语义 profile：实现 `SemanticDriver`（参考 `formal_lab_model.driver.IRFiniteDriver` 与 `formal_lab_example_warehouse.driver.WarehouseDriver`）并以插件包注册，内核与平台无需改动（架构测试守护）。
- 新规划器：实现 `Planner`；需要跨暂停保持状态时实现 `CheckpointingPlanner` 并用 `formal_lab_sdk.plugin_testing.check_planner` 验证（参考包外 `org.example.checklist-planner`）。
- 新业务系统：实现 `SessionEnvironment`（`query_operation` 是结果未知时对账的前提）与 `Probe`；参考 `examples/local-order-service`。
- 概率结论：扩展载荷与结果类型在 `formal_lab_solver_prism`；若要成为正式 profile，需要概率语义驱动（见 `deferred_work`）。
