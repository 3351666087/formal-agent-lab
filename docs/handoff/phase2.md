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

<!-- checks:begin -->
（由 `make handoff-phase2` 生成）
<!-- checks:end -->

## 4. 内核类型（P2-123）

实际类型、定义位置、契约版本（均为 `formal-lab-contracts/v2`）、JSON Schema、例子与实现；由 `scripts/handoff_phase2.py` 导入代码生成，manifest 的 `types` 字段含完整路径与行号。

<!-- types:begin -->
（由 `make handoff-phase2` 生成）
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
