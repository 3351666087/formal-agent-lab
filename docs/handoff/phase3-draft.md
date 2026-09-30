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

## G2 · 执行扩展点与操作一致性

- **接口**（契约 v2 增量，摘要 `4539dd9b…`，v1 `0cbd6256…` 不变）：插件接口 `EXECUTION_GATE` 与协议 `interfaces.ExecutionGate`（`paths(action)`、`decide(GateRequest) -> GateResult`）；数据对象 `GateRequest`、`GateResult`、`ConditionCheck`；记录 `ExecutionDecision`；枚举 `ExecutionPhase`（FIRST_SEND / RESEND / REEXECUTE）、`GateVerdict`、`OperationEffect`（SEND / QUERY / REUSE / NONE）；`OperationRecord.request_digest`、`.decisions`，`OperationTransition.effect`；`ScenarioManifest.execution_gates`；事件 `EXECUTION_DECIDED`；能力 `gate.pre_execution`、`gate.fresh_values`；`PluginUi.condition_labels`。
- **实现**：`packages/runtime/src/formal_lab_runtime/coordination.py`（请求摘要、冲突、复用、只有 `env.idempotent_step` 才重发、每次发送前询问门控、转换效果）；`engine.py`（`_gate_hook` / `_gate_values`：发送前读取门控所需位置，能按请求观测时取新鲜值；决定事件；被拒动作按“世界不变”比较）；`manifest.py`（`gate:<i>` 固定版本与协商）；API 场景服务保存 / 校验 `execution_gates`，操作 API 返回 `request_digest` 与 `decisions`。示例门控：`examples/local-order-service/.../gates.py`（库存安全线）、`examples/warehouse-allocation/.../gates.py`（库区装载率）；订单服务同 id 异参返回 409 → 适配器 `Conflict`；两个示例规则规划器在门控拒绝后的下一回合不再提出同一动作；场景构造参数 `safety_stock` / `max_fill`。决策 D-025。
- **证据**：`scripts/operation_consistency_evidence.py` → `docs/execution/evidence/phase3/g2-operations.json`（真实订单服务进程，逐项统计服务自身的操作表）：成功一次 1 行；门控拒绝 0 行且服务查无此操作；重复投递（同账本复用、另一 Worker 由服务按 id 去重）1 行；同 id 异参被协调器与服务（409）各拒绝一次；发送后丢响应 → 查询对账 1 行；预检查后修订变化（修订 3 允许 → 竞争者先预约 → 修订 4 服务拒绝 `PRECONDITION_FALSE`）；两个无共享账本的 Worker 同时发送 1 行；服务提交后进程退出并被重启 → 查询对账 1 行；本地运行器门控场景（安全库存 2）26 次发送、2 次拒绝，被拒操作不在服务中。持久路径：`tests/integration/test_operation_consistency_platform.py`（Temporal + PostgreSQL + 真实服务，中途杀 Worker）通过：决定持久化、被拒操作从未发送、服务无重复、与本地运行器的拒绝逐条一致。单元：`packages/runtime/tests/test_operation_consistency.py`（6）、`examples/warehouse-allocation/tests/test_capacity_gate.py`（2）。
- **兼容**：未声明门控的场景与阶段二轨迹相同（单元 441 通过，含阶段一哨兵；订单服务 / 多参与者 / 平台运行集成 17 通过）；阶段二测试中不带执行者的“重复投递”改为发送同一请求（新规则下缺执行者即不同请求）。

## G3 · 语义驱动、规则与发布能力

- **接口**（契约 v2 增量，摘要 `db180892…`）：`CapabilityReport`、`FeatureSupport`、`SupportStatus`、`ReleaseConfig`（`required_checks`、`required_holds`、`horizon`、`timeout_ms`）；`ReleaseCheck` 新增 `required`、`executed`、`backend`、`scope`、`property_holds`、`claim`；`ModelReleaseRecord` 新增 `config`、`process_completed`、`capabilities`；能力 `driver.stats`（`LoadedModel.stats()` 可选）。
- **实现**：`packages/runtime/src/formal_lab_runtime/release.py`（`capability_report()`；`check_release(..., config=)` 按报告执行，缺能力记 UNSUPPORTED，必需检查无结论 → `process_completed = false`，性质成立与否单独记录；规模统计用协议方法 + 可选 `stats()`，去掉对 `ground_actions()` 的未声明依赖）；`manifest.py` / `engine.py`（场景规则集需要 `driver.ir`，否则协商阶段拒绝运行）；`IRFiniteDriver`、`WarehouseDriver` 声明 `driver.stats`；API `GET /model-versions/{id}/capabilities`（订单版本带 PRISM-games 载荷时附扩展行），`POST /model-versions/{id}/releases` 接受 `required_checks` / `required_holds`；SDK `Client.capabilities()`、`release(required_checks=, required_holds=)`；CLI `fal release capabilities <id>`、`fal release check --require … --require-holds …`。最小只实现公开协议的驱动：`examples/external-plugin/.../counter_driver.py`（profile `counter_v1`，只依赖 SDK；SDK 另导出驱动所需数据对象）。决策 D-026。
- **证据**：`scripts/model_revision_evidence.py` → `docs/execution/evidence/phase3/g3-release.json`，8/8：订单 IR 模型发布 RELEASED、流程完成；最小驱动的规则 / 查询 / 统计为 UNSUPPORTED（原因写明“没有已安装的验证器为 counter_v1 声明 query.goal_reachability”），默认配置发布通过，要求 GOAL_REACHABILITY 时 REJECTED 且流程未完成；**真实修订**：真实订单服务的 deviation 案例（p2 半速）产生 4 个 `tick` 效果差异、建议指向常量 `slow`、4 个回归案例 → 旧版本被回归案例拒绝（4/4 FAIL），修订版（`slow[p2]=true`）RELEASED（4/4 PASS），修订版对同一服务的新运行 0 差异；**陈旧依据**：两名处理员轮初观测，4 个差异全部归为陈旧依据（“planned at revision 8, executed at revision 9”），0 条建议、0 个回归案例。测试：`packages/runtime/tests/test_release.py`（6，含流程完成与性质不成立分开）、`tests/integration/test_governance_platform.py`（API 能力报告与必需检查）；PRISM-games 扩展单元 5 通过，其能力声明与回归入口（`make prism-games-check`）不变。

## G4 · 联合批次与按参与者的规划输入

- **接口**（契约 v2 增量，摘要 `adbe8269…`）：轮次模式 `TurnMode.JOINT_BATCH`（要求 `ROUND_START`）与 `TurnPolicy.batch_timeout_s`；`TurnRef.batch_id`、`.env_step`；记录 `BatchRecord`（OPEN / SUBMITTED / CANCELLED，成员、打开 / 提交步、环境步、操作 id、批次语义、是否联合预测）、`BatchMember`、枚举 `BatchMemberStatus`（PROPOSED / PASSED / ABSENT / TIMED_OUT / CANCELLED）；数据对象 `ParticipantView`（`include` / `exclude` / `settings` / `label`）与 `Participant.view`；事件 `BATCH_OPENED` / `BATCH_SUBMITTED` / `BATCH_CANCELLED`；`OperationRecord.kind = "batch"`、`.batch_id`、`.batch_outcomes`；能力 `env.batch_step`、`driver.joint_predict`（`params.semantics`，常量 `START_STATE_DISJOINT_WRITES`）；协议 `BatchEnvironment.step_batch(proposals, *, operation_id)`。
- **实现**：`packages/runtime/src/formal_lab_runtime/engine.py`（`plan_step` 在轮初打开批次、按参与者过滤规划输入；`_apply_joint` / `_submit_batch`：成员照常 CHECK，提案存入携带状态中的开放批次，本轮最后一个成员或超过期限的第一个成员提交；逐成员执行门控；逐成员在自己的提案步记录结果与比较；驱动与环境语义一致时按联合预测比较；`finish_run` 取消未提交的批次）；`coordination.py`（`Coordinator.execute_batch`：同一身份 / 复用 / 冲突规则，纯数据重执行须得到相同结果，丢失应答只在 `env.idempotent_step` 时重发）；`participants.py`（`ParticipantInput`：观测、补观测请求、`last_outcome` 过滤与输入摘要；`ParticipantServices`：参与者设置优先）；`turns.py`（`advance(progressed=None)`、`close_round`）；`manifest.py`（`JOINT_BATCH` 需要 `env.batch_step`，协商说明是否联合预测）；`formal-lab.env.driver-world` 的 `step_batch`；仓储驱动声明 `driver.joint_predict`；场景构造 `receiver_and_picker(turns=JOINT, views=VIEWS)` 与种子场景“仓储：收货员 + 拣货员同步批次”；API 保存场景时校验视图位置；持久路径的步骤记录取成员结果中的 `TurnRef`。编号关系（`global_step` / `actor_step` / `round` / `env_step`）与成员状态写入 [plugin-integration.md](../architecture/plugin-integration.md) 3.7。决策 D-027。
- **证据**：`scripts/joint_batch_evidence.py` → `docs/execution/evidence/phase3/g4-batch.json`，9/9：收货员与拣货员 20 个全局步、10 个批次、环境 10 步（每个批次 `env_step = round`），每个成员结果在自己的提案步，联合预测与环境全部 MATCH（拣货员与收货员写同一库存格时被拒，原因 “batch write conflict”，联合预测已预见）；**轮中重启**：在第 3 轮收货员提案后停止（批次 OPEN、环境仍在第 2 步），状态经 JSON 交给新建插件后继续，轨迹与每个规划器的输入摘要和不间断运行完全相同；**视图**：收货员的规划器只收到 clock / dock / stock，拣货员收到除 dock 外全部，`last_outcome` 中的比较字段同样过滤，设置 `style` 只对收货员生效；**成员状态**：自身预算用完 → 之后各批次 ABSENT；规划 0.4 s 超过期限 0.2 s → TIMED_OUT，提案未提交；运行预算在轮中耗尽 → BATCH_CANCELLED，没有操作 id；门控拒绝的成员不在已发送的批次结果中；**顺序运行不变**：仓储轮流运行与 `0ae4571` 捕获的阶段二回放逐动作一致，没有批次事件，携带状态无 `batch` 键。**持久路径**：`tests/integration/test_joint_batch_platform.py`（Temporal + PostgreSQL）在轮中暂停（奇数步、批次 OPEN）后恢复并杀掉 Worker，运行成功：无重复事件、每个批次 `env_step = round`、每个全局步一个结果，轨迹与每个规划器的输入摘要与本地运行器一致；轮中取消 → `BATCH_CANCELLED`、成员全部 CANCELLED、无操作 id；保存场景时视图写了不存在的位置族 → 422 与字段路径。测试：`examples/warehouse-allocation/tests/test_joint_batch.py`（7）、`packages/runtime/tests/test_participants.py`（4）；单元 / 契约 / 架构 / 示例 459 通过（含阶段一哨兵），契约 Python 133、TypeScript 97，Web 类型检查通过；集成（联合批次 3、多参与者 2、操作一致性 1、平台运行 / 治理 / 矩阵 / SDK 垂直）全部通过。

## G5 · 前端、Figma、GitHub 与 SVG 动画

- **方向与样式源**：专业研究工作台（Evidence Workbench）。唯一样式源 `design/tokens.json`（1.0.1）→ `scripts/design_tokens.py`（`--check` 检查漂移）→ `web/src/tokens.css`：颜色（Light / Dark，`data-theme` 覆盖）、参与者 / 系列分类色 `--p1…p8`、证据等级 `--ev-*`、字体、字号、间距、圆角、阴影、动效（`prefers-reduced-motion` 时全部为 0）、布局；品牌色、状态色、分类色分离。对比度复核后下调了浅色 `text-muted`、`ev-unknown` 与 p2 / p6，参与者首字母改用 `text-inverse`（全部 ≥ 4.6:1）。组件与用法、图表规则、页面布局、可访问性、媒体命令与基准截图：[docs/design-system.md](../design-system.md)。
- **Web**（`web/src/`）：`styles.css` 重写为组件层（保留全部原类名并映射旧变量）；`icons.tsx`（20 个图标 + 标志，替代 Unicode 字形；按钮可访问名称不再含字形）；`ui.tsx` 新增 `PageHead`、`Stat`、`EvidenceTag` / `EvidenceLegend`、`ParticipantChip`、带符号的 `StatusBadge`；外壳加跳到主要内容、外观切换、路由级错误界面；六个区域统一页头。**功能接入**：运行台同步批次面板（`GET /runs/{id}/batches`）、执行前决策、规划器输入（参与者视图隐藏的位置与输入摘要）、成员结果的批次与环境步；步骤详情的字段比较按四个证据等级显示；模型工作台能力报告（`/model-versions/{id}/capabilities`）；场景编辑同步批次（含期限）与参与者视图；矩阵单元格复用标记与复用键各部分摘要；证据页同步批次页签；柱状图系列改用分类色。
- **接口**：`GET /api/v1/runs/{id}/batches`（`formal_lab_contracts.bundle.summarize_batches`，`ReplayBundle.batches()` 离线同义）；SDK `Client.batches`；CLI `fal run batches`、`fal replay batches`；操作 API 增加 `kind`、`batch_id`、`batch_outcomes`；矩阵复用键 v2（`key_version: 2`）：解析后的插件（策略、环境、驱动、验证器、门控、评分器，含描述符摘要）、参与者视图、场景清单摘要、声明的扩展配置（场景与模型包），复用单元格带 `reused_from` 与 `key_parts`。旧矩阵的单元格摘要是 v1 键：合并进旧矩阵的新单元格按 v2 键计算，不会与旧单元格误配（可能重复运行一次，不会误复用）。
- **修复**（本包发现）：证据页对持久会话环境（订单服务）的会话标记快照崩溃——改为说明会话快照并显示标记内容；持久路径上 Worker 在发送前被杀时，已写入操作记录的门控决定缺少 `EXECUTION_DECIDED` 事件（CI 集成失败的原因）——提交步骤时为记录上的全部决定发事件（按决定 id 幂等）；`fal replay operations` 遇到批次操作（无单一动作）报错；截图检查增加“错误界面”判定。
- **Figma**：[formal-agent-lab · Evidence Workbench (Phase 3A)](https://www.figma.com/design/uuV6JeilZQkhnIQcJYEUET)（Pro 团队，账户 Rui），节点与代码对应见 `design/figma.json`：Cover（同步状态）· Foundations（58 个变量：Color Light/Dark + Dimension，Web 代码语法即 CSS 变量；8 个文字样式、3 个阴影；浅 / 深两帧）· Components（Icon/* 20、Button、StatusBadge、EvidenceTag、ParticipantChip、NavItem，变体绑定变量，描述写明代码组件）· Screens（14 张真实截图，标注路由与组件）· Charts & model graph（模型结构图、时间线、柱状图、批次行、比较中的证据等级）· Motion storyboard（5 个场景的真实帧与时序、封面）。同步方向代码 → Figma；视频不经 Figma 导出（其视频工具只渲染 Figma 时间线），由同一 SVG 在本地导出，二者不会分叉。
- **SVG 动画与媒体**：`scripts/render_demo.py`：`svg`（标准库）→ `docs/assets/demo.svg`（可编辑源，134 KB，CSS keyframes 共用 20 s 时间线，减少动态时显示静态总结）、`demo-cover.svg`、`demo.html`（可暂停 / 拖动）、`architecture.svg`；`frames`（VM，Chromium 按 Web Animations API 逐帧定位 600 帧）→ `encode`（宿主 ffmpeg / rsvg-convert）→ `demo.mp4`（h264 1920×1080 30 fps 20.0 s，1.3 MB）、`demo-cover.png`。叙事：模型 → 计划 → 运行 → 偏差 → 证据，数值全部来自订单服务 deviation 案例的真实运行与 `g3-release.json`（`design/animation/demo-data.json` 记录来源与采集提交）。
- **GitHub README**：首屏动画 SVG（GitHub 中实测播放）、实际 CI 徽章与许可证徽章、定位（是什么 / 不是什么）、真实界面截图 6 张、功能地图、快速开始（含 CLI 批次流程）、架构与运行流程图、文档索引；写明截图与动画的数据来源。渲染检查见下方证据。
- **证据**：SDK / CLI：`scripts/product_flow_evidence.py` → `docs/execution/evidence/phase3/g5-flows.json` 6/6（仓储同步批次：`fal run start --wait` 成功、10 轮每轮一个环境步、导出回放包离线读取的轮次与在线一致；订单延迟响应：6 个结果未知的操作全部按 id 查询对账，离线回放包保留相同的对账）。Web：`scripts/capture_screens.py` → `g5-web.json` 8/8（在场景页点“运行实验”完成仓储批次与订单恢复两次运行、批次面板轮次与导出包一致、异常操作可见、矩阵复用标记、390 px 无横向滚动、跳转链接、减少动态、无页面错误与错误界面），同时生成 `docs/assets/screens/` 的 15 张基准截图。README 实际渲染：推送后用 Chromium 打开 github.com 仓库首页（未登录）截取 `docs/execution/evidence/phase3/g5-readme-rendered.png`，README 中 10 张图（动画、CI 与许可证徽章、6 张截图、架构图）全部加载，动画在 GitHub 的 `<img>` 中播放（内置浏览器中逐场景核对）。复用键：`tests/integration/test_matrix_v2_platform.py::test_reuse_key_covers_views_gates_and_extensions`（同配置复用并标来源；改视图 / 门控 / 扩展配置各产生新单元格）。回归：Playwright UI 14/14（`test_web_ui.py`、`test_web_product.py`，选择器随按钮去字形更新）；矩阵、SDK/CLI 回放、联合批次、操作一致性集成通过；单元 459。

## G6 · 本地检查与发行工具

- **检查引擎** `scripts/check_runner.py`（结果格式 `checks@2`）：套件是导出 `SUITE` 的模块（`--suite phase3` → `scripts/phase3_check.py`；`--suite phase2` 加载 `phase2_check.py` 的历史检查；也可给 .py 路径）；`--out` 独立输出目录，`--group` / `--only` / `--skip` 分组与单项，`--retries`，`--list`。每次尝试单独写日志 `logs/<id>/<时间>-attempt-<n>.log`；保留首次失败（`first_failure`）、重试后才通过的标记（`flaky`）、最终结果与每项的历史（最近 20 次调用）；记录源码提交、工作区摘要（检查自身输出除外）、配置摘要（检查定义 + `uv.lock` + `pnpm-lock.yaml` + Compose 文件）、工具版本与运行前后的资源读数（CPU、内存、宿主盘与 Docker 盘）；另一提交 / 工作区 / 配置上的结果标 `inherited`，不算当前通过。耗时分开：本次调用、每项总耗时与每次尝试、最近一次完整执行（`timing.last_full_run_s`）与单项重跑（`timing.partial_runs`，含选择条件）。检查逐个执行（并发 1）；`heavy_gib` 检查先经 `disk_guard`，须在写入量之外保留 `FAL_DISK_RESERVE_GIB`（默认 15）GiB，否则 BLOCKED 并写明读数；Docker / 服务检查后 `fstrim` 归还空间；回环地址不走代理（NO_PROXY），代理变量本身保留给真实模型端点。测试：`tests/tools/test_check_runner.py`。
- **阶段三检查集** `scripts/phase3_check.py`：g1-contracts、g2-operations、g3-release、g4-batch、g5-product、g6-release、regression 共 25 项（`make phase3-check [ARGS=…]`，`make checks SUITE=phase2`，`make design-check`）；包括“矩阵测试在保留的数据库上连续两次通过”（`p3-matrix-kept-db`：同一进程先后两个独立 pytest 会话）。
- **发行工具**：`release.py --skip-images --out --evidence`（不建镜像的发行：全部 wheel、Web 包、干净 venv 中的 SDK/CLI（含 `fal replay batches`）、许可证清单）；带镜像的发行与去重离线包作为扩展检查，按磁盘保留量自动 BLOCKED。新增包的接入位置：uv 工作区成员自动进入 `uv build --all-packages` 与 manifest，插件经 `formal_lab.plugins` entry point 注册，镜像来自 `deploy/compose/docker-compose.yaml`，Chart 在 `deploy/helm/formal-agent-lab`。
- **历史证据保护**（本包发现并修复）：本轮的 UI 测试、概率扩展平台测试与许可证清单曾写入 `docs/execution/evidence/phase2/`（G3、G5 的提交中带入了改写后的阶段二截图与测量）。已把该目录恢复为阶段二交接 `0ae4571` 的内容，并让所有写证据的测试与工具使用同一个 `FAL_EVIDENCE_DIR`：默认本轮目录 `docs/execution/evidence/phase3`，只有 `phase2_check.py` 设为阶段二目录。
- **磁盘事件**（记录在案）：第一次完整执行时，带镜像的发行检查在 `fstrim` 之后读到宿主可用 16 GiB（门槛为写入量 16 GiB，未计保留量）而开始构建；宿主降到 12 GiB 时我中止了异架构构建，删除了本次新建的项目镜像标签（`formal-agent-lab/*:{0.2.0,4e5fbb159ed5,local}`，保留阶段二的 `4e1f959e81f2` 镜像）并执行 `docker builder prune` 与 `fstrim`，宿主回到 16 GiB；随后在引擎中加入保留量。另删除了可重建的 `out/offline`（阶段二离线包输出，685 MB，`make offline-bundle` 重建）与 `var/it-artifacts`、`var/demo-frames`。未做任何宽泛的 prune。
- **结果**（本轮最终执行，`docs/execution/evidence/phase3/checks/results.json`）：提交 `962bd37`、工作区干净、配置摘要 `21b564b0…`；7 组全部 PASS——22 PASS、0 FAIL、2 BLOCKED（扩展检查：带镜像的发行需 8 + 15 GiB、去重离线包需 12 + 15 GiB，宿主当时 16.2 GiB、Docker 盘 22.3 GiB），无一项需要重试；完整执行 2183.8 s（36.4 min），其后单项重跑 `p3-batch-evidence` 1.4 s 单独记在 `timing.partial_runs`，该项历史保留上一次结果。主要项：单元 462 通过（含阶段一哨兵）、平台集成 37 通过（与 CI 相同的集合）、Playwright 14 通过、矩阵测试在保留数据库上两个会话各通过、SDK/CLI 与 Web 流程证据 6/6、8/8、轻量发行 15 个 wheel + Web 包 + 干净 venv 中的 `fal`。阶段二证据目录执行前后 `git status` 为空。
- **第一次完整执行**（提交 `4e5fbb1`，已被上面的结果取代；其日志在重新执行前删除）暴露并促成了本包的修复：`capture_screens.py --shots` 的 `global` 位置错误（FAIL）、新的持久批次测试在轮中暂停上有时间偏差（首次失败、重试通过被标为 flaky；集成全集两次均失败）、带镜像的发行检查未计保留量（见磁盘事件）。首次失败 / 重试 / 最终结果的保留由 `tests/tools/test_check_runner.py` 覆盖。
- **CI**：`4e5fbb1` 的 GitHub Actions 全绿（G2 门控事件修复后集成通过）；本包的提交推送后再核对。

## 阶段三 A 汇总（交给后续集成）

### 接口与类型（契约 `formal-lab-contracts/v2`，摘要 `bc24e5e9…` → G2 `4539dd9b…` → G3 `db180892…` → G4 `adbe8269…`；v1 `0cbd6256…` 冻结）

| 包 | 类型 / 接口 | 代码 |
|---|---|---|
| G1 | 协议 / 数据对象 / 枚举 / 记录的分类；`formal_lab_sdk.plugins` 导出驱动所需对象；阶段二 v2 回放样本 | `packages/contracts/src/formal_lab_contracts/interfaces.py`、`packages/sdk/src/formal_lab_sdk/plugins.py`、`tests/compat/` |
| G2 | 插件接口 `EXECUTION_GATE` / 协议 `ExecutionGate`；`GateRequest` `GateResult` `ConditionCheck` `ExecutionDecision`；`ExecutionPhase` `GateVerdict` `OperationEffect`；`OperationRecord.request_digest` `.decisions`；`ScenarioManifest.execution_gates`；事件 `EXECUTION_DECIDED`；能力 `gate.pre_execution` `gate.fresh_values` | `formal_lab_runtime/coordination.py`、`engine.py`（`_gate_hook`）、`manifest.py` |
| G3 | `CapabilityReport` `FeatureSupport` `SupportStatus` `ReleaseConfig`；`ReleaseCheck` / `ModelReleaseRecord` 新字段；能力 `driver.stats`；`capability_report()` `check_release(config=)` | `formal_lab_runtime/release.py`、API `GET /model-versions/{id}/capabilities`、`fal release capabilities` |
| G4 | `TurnMode.JOINT_BATCH` `TurnPolicy.batch_timeout_s` `TurnRef.batch_id` `.env_step`；`BatchRecord` `BatchMember` `BatchMemberStatus`；`ParticipantView` / `Participant.view`；事件 `BATCH_OPENED` `BATCH_SUBMITTED` `BATCH_CANCELLED`；`OperationRecord.kind="batch"` `.batch_id` `.batch_outcomes`；能力 `env.batch_step` `driver.joint_predict`；协议 `BatchEnvironment.step_batch`；`ParticipantServices` `ParticipantInput` | `formal_lab_runtime/engine.py`（`_apply_joint` / `_submit_batch`）、`participants.py`、`turns.py`、`formal_lab_env/driver_world.py` |
| G5 | `GET /runs/{id}/batches`（`bundle.summarize_batches`、`ReplayBundle.batches()`）；`Client.batches`；`fal run batches` / `fal replay batches`；操作 API `kind` `batch_id` `batch_outcomes`；矩阵复用键 v2（`key_parts`、`reused_from`）；设计 tokens 与组件 | `packages/platform-api/…/app.py`、`services/matrices.py`、`web/src/`、`design/` |
| G6 | 检查引擎 `Check` / `Suite` / `checks@2` 结果；阶段三检查集；`release.py --skip-images --out --evidence`；`capture_screens.py --shots` | `scripts/check_runner.py`、`scripts/phase3_check.py` |

### 命令

```bash
make phase3-check [ARGS="--group g4-batch | --only id | --out dir | --list"]   # 本轮全部检查
make checks SUITE=phase2 ARGS="--list"                                          # 阶段二检查（同一引擎）
make contracts && make contracts-check                                          # 契约生成与漂移
python3 scripts/design_tokens.py [--check] ; make design-check                  # 样式源
python3 scripts/render_demo.py svg ; scripts/in-vm.sh 'uv run --frozen python scripts/render_demo.py frames' ; python3 scripts/render_demo.py encode
scripts/in-vm.sh 'uv run --frozen python scripts/capture_screens.py'            # 基准截图 + Web 流程证据（需开发栈）
scripts/in-vm.sh 'uv run --frozen python scripts/{operation_consistency,model_revision,joint_batch}_evidence.py'
```

### 兼容策略

- 契约只做增量：新对象与带默认值的可选字段，版本保持 v2，摘要变化记在各包；破坏性变化另发 v3 并提供 v2 读取。阶段二 v2 回放样本（`tests/compat/fixtures/phase2/`）与阶段一 v1 样本按当前代码原样可读。
- 行为兼容：未声明门控、批次、视图的场景与阶段二轨迹一致（仓储轮流运行与 `0ae4571` 捕获逐动作一致；阶段一哨兵）；两处有意的行为改变写在决策里——结果未知且后端无记录时只有 `env.idempotent_step` 才重发（D-025），规则集需要 `driver.ir`（D-026）。
- 矩阵复用键 v2 与 v1 摘要不同：旧矩阵中合并新单元格时按 v2 计算，不会误复用（最多重复运行一次）。
- 阶段二验收（`docs/handoff/phase2-checks.json`，提交 `4e1f959`）是历史证据；本轮结果在 `docs/execution/evidence/phase3/`，完整产品验收在全部集成完成后统一收口。

### 已完成 / 阻塞 / 下一步

- **已完成**：P3A-G1 … G6（本文件各节）；证据 `docs/execution/evidence/phase3/`（doctor、g2-operations、g3-release、g4-batch、g5-flows、g5-web、g5-readme-rendered、release-manifest、licenses、checks/）；Figma 文件与 `design/figma.json`；README 与设计系统文档。
- **阻塞 / 未执行**（原因明确，均非代码缺陷）：带 OCI 镜像的发行与去重离线包——本机宿主盘 16 GiB，低于写入量 + 15 GiB 保留量，检查记为 BLOCKED（在更空的磁盘上 `make phase3-check ARGS="--only p3-release-images,p3-offline-bundle"`）；真实 LLM 端点与 PRISM-games 不在阶段三检查集中（阶段二的条件 / 扩展检查结论保持，`make checks SUITE=phase2 ARGS="--only model-real,prism-games"` 可重跑）；Figma 视频导出未使用（视频由同一 SVG 在本地导出，理由见 G5）。
- **下一步（后续领域集成文件）**：新插件用公开接口接入——语义驱动（`driver.*` 能力决定能力报告，联合语义用 `driver.joint_predict`）、环境（`env.batch_step`、会话 / 对账能力）、执行门控（`EXECUTION_GATE`）、评分器；标签与值写在描述符 `ui` 中，不改核心 UI；新增检查加入 `scripts/phase3_check.py` 或新套件模块（同一引擎），写证据的工具读取 `FAL_EVIDENCE_DIR`；视觉以 `docs/design-system.md` 与基准截图为基线；完整产品验收在全部集成完成后统一收口。
