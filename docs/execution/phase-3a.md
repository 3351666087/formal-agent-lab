<!-- 任务书原文：~/Downloads/03A_opus5_5_platform_and_design.md（修订 2026-09-29）；复选框编号改为 P3A-G1…G6 以便 scripts/tick.py 记录证据。交接记录：docs/handoff/phase3-draft.md。 -->

# Phase 3A：通用平台与视觉交付（Opus 5.5）

项目：https://github.com/3351666087/formal-agent-lab  
修订日期：2026-09-29  
执行顺序：先完成本文件，再交接后续领域集成文件。整个 Phase 3 共 12 个交付包，本文件占 6 个。

## 交付目标与工作量约束

在现有订单、仓储和生产调度示例上，把插件接口、操作一致性、多参与者调度、界面扩展和发行工具补齐，并统一完成前端、Figma 与 GitHub 展示。所有本文件要求都能使用这些普通业务示例独立实现、验收。

基线是上次复核的 main `0ae45712f6f7287acebec66836d0e1d70ca4fc1d`。阶段二产品验收提交为 `4e1f959e81f282fd0b3d05103b5734437d357644`，交接报告 26 项必做、1 项模型条件检查、1 项概率扩展检查通过；这些是历史证据。本轮开始核对实际 HEAD 与工作区差异。

本文件归并原计划中的接口缺口，并将用户追加的视觉改造统一放入 G5。每个交付包先找现有实现：已满足的部分引用代码与证据即可，实际存在的缺口再增量修改。完成条件写在交付包内，测试、文档和接口声明随实现一起完成。以本文件的 6 个复选框记录进度，保持一个交接记录。

阶段二已有的数据库、Temporal、模型客户端、任务计划、探针、矩阵、六页 Web、SDK/CLI、Compose、Chart 和发行脚本继续复用。优先通过现有 schema、元数据和扩展字段接入；新的抽象只解决下列明确列出的缺口。

## G1 · 契约与插件兼容

- [x] **P3A-G1** 完成一次接手核对及必要的契约/插件兼容增量。
  - 证据：接手核对（HEAD=0ae4571 干净、doctor、428 单元回归通过）；阶段二 v2 回放样本 tests/compat/fixtures/phase2（capture_phase2.py @0ae4571）与可读性测试；v2 增量兼容策略；协议 / 数据对象 / 枚举与记录分类；插件指南按 v2 重写；SDK 导出补齐。详见 docs/handoff/phase3-draft.md#g1
  - 实现：`tests/compat/capture_phase2.py`、`tests/compat/test_phase2_fixtures.py`、`docs/architecture/plugin-integration.md`、`packages/sdk/src/formal_lab_sdk/plugins.py`、`scripts/tick.py`

读取阶段二交接、known-issues、决策 D-015 至 D-024 和实际接口。保持 v1 冻结、新数据 v2、旧数据通过兼容层读取；保存一份阶段二 v2 回放作为历史样本。新增对象同步 Python 类型、schema、TypeScript 类型、摘要及兼容策略，破坏性变化显式升版。

明确 `SemanticDriver`、`LoadedModel`、`CheckpointingPlanner`、`SessionEnvironment`、`Probe` 是协议；`EnvironmentSession`、`PlannerCheckpoint`、`ProbeResult` 是数据对象；`ExecutionStage/StageRecord` 是枚举与记录。更新与当前实现不符的插件指南。

**复用位置：** `packages/contracts/src/formal_lab_contracts/{interfaces,compat,execution,kernel}.py`、`contracts/v2/`、`packages/contracts-ts/`、`packages/sdk/src/formal_lab_sdk/plugin_testing.py`、`examples/external-plugin/`。

**完成证据：** 旧 v1/v2 回放可读，原有示例可运行，新对象往返与插件合同检查通过。接手运行 doctor 与核心回归；后续按代码影响范围增量验证。

## G2 · 执行扩展点与操作一致性

- [x] **P3A-G2** 交付真实执行边界上的类型化扩展点，以及可靠的操作去重和未知结果恢复。
  - 证据：ExecutionGate 插件接口（首次发送 / 重发 / 重执行前询问，决定写入操作记录与事件）；操作 id 绑定请求摘要（同 id 复用、异参冲突）；未知结果先查询、仅 env.idempotent_step 才重发否则 NEEDS_REVIEW；订单库存 / 仓储容量门控示例；真实订单服务证据 9/9 与持久路径（杀 Worker）测试通过。详见 docs/handoff/phase3-draft.md#g2
  - 实现：`packages/runtime/src/formal_lab_runtime/coordination.py`、`packages/runtime/src/formal_lab_runtime/engine.py`、`packages/contracts/src/formal_lab_contracts/execution.py`、`examples/local-order-service/src/formal_lab_example_orders/gates.py`、`examples/warehouse-allocation/src/formal_lab_example_warehouse/gates.py`、`scripts/operation_consistency_evidence.py`、`tests/integration/test_operation_consistency_platform.py`

当前 `apply_step` 记录检查结果后直接进入协调器。提供一个通用、可注入的执行前决策接口，以订单库存条件/仓储资源条件作为实现示例；决策与原因形成类型化记录，并在 local runner 和 Temporal 路径实际生效。现有默认行为与历史轨迹保持兼容，显式启用新决策的例子按新配置运行。

复用 `Coordinator` 和 ledger：operation_id 绑定规范化请求内容，同 id 同请求复用结果，同 id 异参返回冲突；响应未知先查询记录，只有后端明确声明相同 id 幂等去重时才能重发，缺少条件则进入 NEEDS_REVIEW。扩展点覆盖首次发送、重发与重执行，并区分查询历史结果和产生新副作用。

保留业务服务的条件更新和事务；验证预检查后修订变化、两个 Worker 竞争、发送后响应丢失及重启。决策记录、operation record 和服务端实际副作用相互可追溯。

**复用位置：** `packages/runtime/src/formal_lab_runtime/{engine,coordination,local_runner}.py`、`packages/platform-api/src/formal_lab_api/services/execution.py`、`examples/local-order-service/`。

**完成证据：** 使用订单服务的真实进程，展示成功一次、未满足业务条件时零次、重复交付一次、同 id 异参冲突，以及丢响应后恢复仍只产生一次副作用；local runner 与持久路径均有记录。

## G3 · 语义驱动、规则与发布能力

- [x] **P3A-G3** 完成公开驱动协议到规则/查询/模型发布的能力协商和结果记录。
  - 证据：能力报告（只依据驱动 driver.* 与验证器 query.* 声明）决定规则 / 查询 / 发布；ReleaseConfig 必需检查与必需性质，缺能力或无结论 → 流程未完成、REJECTED；process_completed 与 property_holds 分开；去掉 ground_actions() 未声明依赖；规则集需 driver.ir 否则协商拒绝；最小协议驱动 counter_v1；订单服务真实修订（旧版 REJECTED、修订版 RELEASED、新运行 0 差异）与陈旧依据分类（4 个差异、0 建议）。详见 docs/handoff/phase3-draft.md#g3
  - 实现：`packages/runtime/src/formal_lab_runtime/release.py`、`packages/contracts/src/formal_lab_contracts/governance.py`、`examples/external-plugin/src/fal_example_external_plugin/counter_driver.py`、`packages/platform-api/src/formal_lab_api/services/governance.py`、`scripts/model_revision_evidence.py`

修正 `release.py::check_release` 对 `loaded.ground_actions()` 的未声明依赖，采用正式兼容接口或可选统计能力。使用只实现公开协议的最小驱动验证这一点。

现有规则运行时依赖 IR 的 `checked/interp`，发布也有 IR 条件分支。为驱动、规则和查询建立明确的支持声明：已实现的能力继续复用；未实现的返回 UNSUPPORTED；发布配置列出必需检查，缺少其能力或结果时给出明确未通过状态。发布记录列出实际执行内容、模型/规则版本、后端、范围和结果。由检查性质决定结论含义，保持“发布流程完成”和“某性质成立”两个字段的含义清楚。

沿用 D-022：陈旧依据造成的差异保留在轨迹中；只有在可比较状态上成立的模型偏差进入修订建议与回归案例。

**复用位置：** `packages/model-core/src/formal_lab_model/{driver,rules}.py`、`packages/runtime/src/formal_lab_runtime/release.py`、API `services/governance.py`、`examples/warehouse-allocation/`。

**完成证据：** 现有 IR 模型正常发布；最小非 IR 驱动可加载并得到准确能力报告；缺失必需能力时明确未通过；订单例子完成一次真实模型修订与一次陈旧依据分类。已有 PRISM-games 扩展保持现有能力声明和回归入口。

## G4 · 轮次与参与者输入接口

- [ ] **P3A-G4** 提供可恢复的联合批次接口，以及可按参与者构造的 Planner 输入服务。

保持现有 ROUND_ROBIN、FIXED_TABLE、SIMULTANEOUS_SNAPSHOT 行为；后者含义仍为轮初共同观测、随后顺序执行。新增显式声明的批次能力：保存轮初观测和参与者提案，集齐后向支持批次的环境提交一次，再记录各参与者结果；中途重启可以继续。global_step、actor_step、round、environment step 的关系清楚，缺失成员、超时和取消有确定结果。批次运行能力与形式化模型对并发性质的支持分别声明。

将 Planner 工厂的服务构造与环境/求解器使用的完整服务解耦，提供按参与者配置的模型视图、设置读取和输入构造接口；`last_outcome`、候选解释、观测请求和检查点恢复均经过相同输入构造流程。实现的是通用依赖注入和数据视图机制。

**复用位置：** `runtime/turns.py`、`runtime/engine.py::open_components` 与 CarryState、`interfaces.py`、既有仓储示例；这里的 `runtime/` 指 `packages/runtime/src/formal_lab_runtime/`。

**完成证据：** 两名仓储参与者共同提交一轮、环境仅推进一次；中途重启继续该轮；甲仓/乙仓按配置收到各自数据字段，恢复前后一致；原有顺序场景轨迹保持一致。

## G5 · 前端、Figma、GitHub 与 SVG 动画统一交付

- [ ] **P3A-G5** 完成产品视觉定稿与真实功能接入，交付前端、Figma 设计文件、GitHub 展示和可编辑的 SVG 动画素材。

**设计与实现。** 先看现有前端与 README，选定一个完整方向并落实：专业研究工作台，强调清楚的模型结构、运行过程和证据，兼顾信息密度和可读性。建立字体、间距、颜色、状态、图表、圆角和动效 tokens，以及导航、表格、表单、侧栏、状态标签、空态/错误态等复用组件。品牌色和参与者/状态颜色分离。沿现有六个区域完成统一改造，保留真实 API、路由和用户流程；桌面优先，窄屏可用，支持键盘操作和减少动效的偏好。

先确认当前执行环境的 Figma 连接可读写，再建立一个实际设计文件：设计变量/组件、关键页面、图表/模型图规范和动效分镜；提供真实文件链接与关键节点对应的代码组件。可参考既有 [产品结构图](https://www.figma.com/board/aCNXHt4o1Q7SRUBiyHpa2h)，它作为信息结构依据。设计稿与实际代码一致，页面上的领域无关样例使用订单、仓储和调度数据。若 Figma 连接暂不可用，继续完成代码、SVG 源素材及 tokens，将 Figma 同步状态准确记入交接，不能声称已有设计文件。

**GitHub 展示。** 改造 README 的首屏、产品定位、真实界面截图、功能地图、快速开始、架构/运行流程和演示入口；统一封面、图标、图示与前端视觉。保留项目用途和能力的准确含义，演示数据与真实结果明确标记，徽章取自实际存在的状态。展示素材放在仓库可追踪目录，文档、截图和动画共用一套视觉素材。

**SVG 动画。** 制作一个约 15—25 秒的产品演示：模型 → 计划 → 运行 → 偏差/结果 → 证据回放，使用已跑通的普通业务示例。交付可编辑 SVG、时间线/生成脚本，以及静态封面、网页预览和视频导出；根据实际 GitHub 渲染选择静态封面加视频链接或兼容的短循环预览。SVG 是可编辑源素材，视频是导出物，分别保存。Figma 视频工具若只支持 MP4，就用它导出 MP4；其他格式由实际可用的本地工具生成并检查。动画叙事以真实能力和已验证流程为准。

**功能接入。** 按插件元数据呈现模型、参与者、批次、执行决策、发布检查与能力说明。接口输出保留 observed、verified-within-scope、predicted、unknown 的含义；结果的后端和范围可追溯。具体插件提供语义、标签和指标，平台提供渲染与查询接口。

复用现有矩阵、配对统计和回放。实验复用键纳入模型、插件、规则、视图配置、场景、种子、预算及声明的扩展配置摘要；这些内容改变后产生新格。记录回放与重新执行继续使用不同入口。

**复用位置：** `web/src/`、API `services/{modeling,governance,matrices,bundles}.py`、`packages/sdk/`、`packages/evaluation/`。优先补足新对象的字段和元数据，已有通路直接引用。

**完成证据：** 一个仓储批次和一个订单恢复场景经 Web 与 SDK/CLI 完成运行、查询、导出、离线读取；更改相关配置使矩阵复用失效，同配置复用有明确标记。提供真实前端截图、Figma 链接/同步状态、实际渲染的 README 预览、SVG 源文件与可播放导出，检查实际页面而非只看设计稿。

**视觉交接。** 将 tokens、组件用法、图表配色、页面布局、媒体生成命令和基准截图写入一份 `docs/design-system.md`，与代码中的样式源对应。后续集成主要增加插件数据、字段、标签和必要组件状态；全局品牌、字体、导航结构、间距体系及动效语言以本次定稿为基线。确需补充的组件沿用现有规范，视觉微调在基准截图上说明原因。

## G6 · 本地检查与发行工具收口

- [ ] **P3A-G6** 将本轮通用增量交接为可直接接入后续插件的代码、检查命令和本地发行入口。

复用 `scripts/phase2_check.py` 和既有发行工具，支持独立输出目录、分组/单项选择、每次 attempt 独立日志、源码提交/工作区摘要/配置摘要。首次失败、重试和最终结果均保留；完整执行耗时与单项重跑耗时分别统计。矩阵测试在保留数据库上连续通过两次。

继续使用本地 Colima、原生架构、已有 Compose/Chart、去重离线包、wheel、依赖锁和许可证清单。为新增包保留配置/打包接入位置；本文件用现有业务示例验证工具，最终含具体插件的完整发行由后续集成统一完成。

运行前重新探测资源。沿用 disk_guard，检查宿主共享盘及 VM/Docker 盘；默认并发 1，重型任务串行。普通本地 HTTP 客户端沿用回环地址代理处理，真实模型端点保留其代理配置。历史环境为 4 CPU、约 5.9 GiB 内存；磁盘读数以本次 doctor 为准。

**复用位置：** `scripts/{phase2_check,handoff_phase2,disk_guard,local_data,offline_bundle,release}.py`、`deploy/compose/`、`deploy/helm/`、订单示例 `net.py`。

**完成证据：** 本轮受影响检查通过；现有命令可加载新增检查并保留尝试记录；交接列出实际接口/类型、代码位置、运行命令、兼容策略、已完成/阻塞内容和下一步。把结果写入同一阶段三交接草稿，后续执行者接续补齐。历史验收与本轮结果明确区分，完整产品验收在所有集成完成后统一收口。

## 执行与交接方式

依次完成 G1—G6；已存在且满足条件的实现直接复用。每包完成时提交一段简短证据到同一交接记录，完成下一包所需的信息包含接口、代码路径、命令和结果。跨会话时从该记录继续。

G1—G6 的产物是后续集成的依赖。后续执行者使用公开接口补充具体插件与配置，通用模块的整套实现由本文件一次负责。新增产品能力、额外后端和远程基础设施保持在当前执行范围之外。
