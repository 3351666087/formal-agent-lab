# 阶段三交接草稿（Phase 3A：通用平台与视觉交付）

任务书：[docs/execution/phase-3a.md](../execution/phase-3a.md)（原文 `03A_opus5_5_platform_and_design.md`，修订 2026-09-29）。本文件是阶段三唯一的交接记录：每个交付包完成时追加一段证据（接口、代码路径、命令、结果），跨会话从这里接续。阶段二的验收（提交 `4e1f959`，28/28 PASS，[phase2.md](phase2.md)）是**历史证据**；本轮结果单独记录，完整产品验收在全部集成完成后统一收口。

## 接手核对（2026-09-29）

| 项 | 结果 |
|---|---|
| 基线 | HEAD = `0ae45712f6f7287acebec66836d0e1d70ca4fc1d`（阶段二交接），工作区干净，与 origin/main 一致 |
| doctor | Ubuntu 24.04.4 aarch64，4 vCPU，5910 MiB；宿主机盘 15.1 GiB 空闲，Docker 盘 22.7 GiB；local-lite / local-services / local-kind 均 AVAILABLE；HTTP 代理已排除回环（`docs/execution/evidence/phase3/doctor-takeover.json`） |
| 核心回归 | 单元 / 契约 / 架构 / 示例：428 passed（`-m "not integration and not llm and not ui"`，459.8 s） |
| Figma | MCP 连接可用：账户 Rui，Pro 团队 full seat（G5 使用） |

## G1 · 契约与插件兼容

- **阶段二 v2 历史样本**：`tests/compat/capture_phase2.py` 在 `0ae4571` 上捕获三个 v2 回放包（两名调度员轮流 + 任务计划 / 检查点；仓储第二 profile；订单服务延迟响应 + 对账操作 + 探针）与 `CAPTURE.json`，存于 `tests/compat/fixtures/phase2/`，不再重新生成。`tests/compat/test_phase2_fixtures.py` 检查它们按当前代码原样可读（事件数、操作数、参与者、指标、因果链、轮次 / 计划 / 对账 / 命名空间载荷）。阶段一 v1 样本继续由 `packages/runtime/tests/test_kernel.py` 与 `tests/integration/test_sdk_cli_replay.py` 读取。
- **兼容策略**：阶段三对 v2 只做增量（新对象、带默认值的可选字段），契约版本保持 `formal-lab-contracts/v2`，摘要变化记入本文件；破坏性变化发布 v3 并提供 v2 读取。新增对象由 `tests/contracts/test_contracts.py::test_every_v2_object_has_a_sample` 强制要求样例、Pydantic / JSON Schema 往返与 TypeScript 生成（`make contracts`）。
- **接口分类**（写入 [plugin-integration.md](../architecture/plugin-integration.md) 第 2 节）：`SemanticDriver`、`LoadedModel`、`CheckpointingPlanner`、`SessionEnvironment`、`Probe`（以及 `Planner`、`Environment`、`Verifier`、`TurnScheduler` 等）是**协议**；`EnvironmentSession`、`PlannerCheckpoint`、`ProbeResult`、`TaskPlan`、`TurnState` 是**数据对象**；`ExecutionStage` 是**枚举**，`StageRecord` / `StepRecord` / `OperationRecord` 是内核写入的**记录**。
- **插件指南**：`docs/architecture/plugin-integration.md` 按 v2 实际实现重写（原文仍是阶段一：语义 profile 写成 IR feature、缺驱动 / 会话环境 / 探针 / 检查点 / 轮次 / 阶段记录 / 合同检查）。`formal_lab_sdk.plugins` 另导出 `LoadedModel`、`Prediction`、`ExecutionStage`、`StageRecord`。
- **任务书记录**：`scripts/tick.py` 支持 `P3A-G1` 形式的编号（→ `docs/execution/phase-3a.md`）。
- 验证：`tests/compat`、`examples/external-plugin`（插件合同检查）、`packages/sdk`、`tests/architecture` 54 passed；ruff 通过。
