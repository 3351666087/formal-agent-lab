# Phase 2 执行任务书：本地通用实验平台深化

建议执行模型：Opus 5.5  
项目：https://github.com/3351666087/formal-agent-lab  
编制日期：2026-09-27  
任务性质：在阶段一代码上直接开发、集成、运行和交接。  
本文件是新的阶段二任务书；阶段一已完成，后续扩展接续新的阶段三任务书。

## 0. 本阶段最终交付

把当前平台推进为可独立使用的本地实验产品：支持多个参与者轮流决策、成本优化、明确的不完备观测语义、持久任务计划、纯数据环境与本地业务服务环境、完整实验矩阵、可解释证据、交互式工作台和本地发行。

用生产调度、仓储资源分配和订单处理服务验证所有通用能力。实际开发对象就是这些应用及其共用平台组件。每项能力应有自身可运行示例、接口、测试和使用价值。

优先完成接口与算法设计中需要较强推理的部分，再完成产品交互、异常恢复与完整本地验收。复用现有实现，围绕真实缺口推进，最终交付可运行代码和证据。

### 0.1 已核查的基线

规划时读取的 main：**46400ad8d3c882bcf62dc9fffded3152fc5c35b0**。  
仓库中阶段一验收记录对应的产品提交：**f3afa5cb20804e764bab545f6ba67eed139af7f0**。  
阶段一记录为 **20 PASS / 0 FAIL / 0 NOT_RUN**；本次任务拆分检查了源码和既有证据，未重新执行整套验收。执行本文件时再次核对最新 HEAD。

| 已有实现或实际缺口 | 源码/证据入口 | 本阶段处理 |
|---|---|---|
| Web、API、PostgreSQL、Temporal、SDK、CLI、Inspect 已有运行记录 | docs/handoff/phase1.md | 在原有产品上扩展 |
| 注册表已有多种插件接口，但步骤引擎直接构造 CheckedModel / Interpreter | packages/runtime/src/formal_lab_runtime/engine.py | 提取可替换的语义驱动接口 |
| RunComponents 使用 participants[0]，实际步骤只驱动第一个参与者 | 同上 | 实现真正的多参与者轮次调度 |
| 每步 restore(snapshot)，apply 后才将操作完成记录持久化 | runtime/engine.py、platform-api/services/execution.py | 分开纯模拟器恢复与持久服务会话恢复 |
| Z3 规划以最短动作路径为主 | solver-adapters/z3/.../planner.py | 实现显式成本目标与优化结果 |
| 规划缓存键包含模型、目标、信念值，尚需覆盖查询边界等条件 | 同上 | 补齐缓存语义与资源上限 |
| 观测有未知项，规划会使用 last-known 值；前提检查已有未知补全 | model-core/.../belief.py、observation-semantics.md | 分清假设规划与对全部补全成立的结论 |
| Compose、离线安装、kind 安装已有本地通过记录 | docs/deployment.md | 沿用并扩展本地验证 |
| 验收脚本的 --skip/--only 会合并旧报告 | scripts/phase1_check.py | 新报告按源码修订绑定证据 |
| 离线包共享镜像层重复存放、Web 路由静态导入 | offline_bundle.py、web/src/main.tsx | 优化实际产物与交互性能 |

### 0.2 本地环境与预算

仓库 **docs/execution/evidence/P1-001-environment.md** 记录的是：Apple M4 主机上的 Colima/Lima vz，Ubuntu 24.04.4 aarch64，4 CPU、5910 MiB 内存；当时根盘剩余 17G、Docker 数据盘剩余 28G；配置了 Rosetta binfmt。当前容量与工具状态以重新执行的 doctor 报告为准。

本任务作者的审阅容器与开发者的 Mac/Colima 是两个环境；审阅容器的硬件读数不作为开发机规格。

默认本地资源策略：

- 同时运行 1 个实验；初始求解并发 1，矩阵任务进入队列。
- 开发栈、完整 Compose 栈、kind 验收按步骤切换，重型验收串行进行。
- 原生 linux/arm64 作为首要验收平台；amd64 仿真构建单独记录架构与执行方式。
- 模型推理使用现有配置的 API；规则与符号策略始终可独立运行。
- 镜像、日志、数据包都有空间预检和按项目归属的清理入口。
- 云资源采购、公网服务发布、托管服务接入和多节点可用性验证登记为后续部署事项。

## 1. 接手、证据与工作方式

- [x] **P2-001** 读取 README、阶段一三份 handoff、插件指南、能力矩阵、复用记录和现有开发命令；检查 HEAD 与工作区修改。
  - 证据：接手检查于 46400ad（= 任务书基线，工作区干净）：读取 README、docs/handoff/phase1.{md,manifest.json}、phase1-checks.json、plugin-integration.md、capability-matrix.md、reuse-ledger.md、Makefile 目标与 scripts/dev.sh；按任务书定位的缺口逐一核对源码（engine.py participants[0]、execution.py 快照恢复、z3 planner 最短路径与缓存键、belief.py last-known、main.tsx 静态导入）
- [ ] **P2-002** 将本文件登记为 docs/execution/phase-2.md；在 docs/execution/decisions.md 追加实际架构决策。
- [x] **P2-003** 保存阶段一交接与契约摘要基线；新的测试输出写入阶段二目录，保留历史报告的源码与时间含义。
  - 证据：docs/execution/evidence/phase2/baseline/phase1-baseline.json 固定阶段一交接（checked_commit f3afa5c、20 PASS、契约摘要 0cbd6256…、交接文件 sha256）；v1 兼容样例 tests/compat/fixtures/phase1/（46400ad 上由 capture_phase1.py 生成的 2 个 v1 回放包与 v1 对象）；阶段二输出统一写入 docs/execution/evidence/phase2/，phase1 报告不再被覆盖
  - 实现：`tests/compat/capture_phase1.py`、`docs/execution/evidence/phase2/baseline/phase1-baseline.json`
- [x] **P2-004** 实现 make doctor：记录当前 OS/架构、VM/cgroup 可用 CPU/内存、磁盘、Docker daemon、Compose、端口、工具链和本地依赖状态。
  - 证据：make doctor（scripts/doctor.py，仅标准库）：OS/架构/虚拟化与 binfmt、cgroup 优先的可用 CPU/内存、仓库与 Docker 数据盘空间、Docker/Compose/buildx、端口占用者（容器名/dev.sh 会话/ss）、工具链、锁同步与依赖、后端服务、三个 profile 可用性与资源估计、并发默认值；实测记录 docs/execution/evidence/phase2/doctor.json（Ubuntu 24.04.4 aarch64，4 CPU，5910 MiB，三个 profile 均 AVAILABLE）
  - 实现：`scripts/doctor.py`、`Makefile`
- [x] **P2-005** 先运行已有独立示例和针对本次改动的基线检查；完整回归安排在里程碑与最终验收，记录准确命令与退出码。
  - 证据：改动前基线（46400ad）：独立示例 compare rule,z3 × 4 场景 × 种子 1-3 退出码 0，单元套件 228 passed 退出码 0；命令、退出码、时间与日志见 docs/execution/evidence/phase2/baseline/baseline-checks.json；完整回归安排在里程碑与 make phase2-check
- [ ] **P2-006** 增量扩展已有包；新包只在职责或运行生命周期确有差异时建立，更新 workspace、锁文件、依赖方向与许可证清单。
- [ ] **P2-007** 每次勾选绑定实现文件及真实证据；状态区分 PASS、FAIL、BLOCKED、NOT_RUN、NOT_SELECTED，注明前提和解除条件。
- [ ] **P2-008** 常规可逆工程选择自行推进；某一外部依赖缺失时继续完成独立任务，并保留精确阻塞记录。

## 2. 固定接口与可扩展运行内核

当前核心能够加载插件，但并不意味着所有执行语义已经插件化。本节首先消除已定位的实际耦合。

推荐新增接口的名称可按现有风格调整，职责必须明确：

| 接口/对象 | 职责 |
|---|---|
| SemanticDriver | 校验模型载荷、生成候选、构造推断状态、预测效果、解释性质与展示结构 |
| TurnScheduler | 选择下一参与者、保存轮次游标、区分全局步与参与者步 |
| PlannerCheckpoint | 计划、任务进度、摘要、随机状态与剩余预算的可恢复快照 |
| EnvironmentSession | 持久服务环境的会话引用、修订号、操作查询与生命周期 |
| ExecutionStage | 观测、提案、检查、执行、协调、探针、比较的明确阶段 |
| ModelReleaseRecord | 固定模型版本、编译产物、查询配置、回归结果和适用范围 |
| ProbeResult | 独立业务观测的来源、时间、值、缺失原因和证据 |

- [ ] **P2-010** 从 RunComponents.__post_init__、compute_candidates、plan_step、apply_step 提取 SemanticDriver；runtime 根据注册表和运行版本选取驱动。
- [ ] **P2-011** 为现有 deterministic_finite_v1 提供驱动，原生产调度样例保持相同语义与可读历史结果。
- [ ] **P2-012** 用第二个独立实现的仓储资源分配插件验证候选、预测和性质计算来自驱动；通用 runtime 无须识别具体场景名称。
- [ ] **P2-013** 审查 ModelPackage.ir 的强制 ModelIR 类型及 PluginInterface 枚举。兼容扩展使用有 schema 的命名空间载荷；确需非 ModelIR 载荷时交付真实的并行 v2 契约与 v1 适配器。
- [ ] **P2-014** 契约升级覆盖 Pydantic、JSON Schema、TypeScript、数据库读取、API、CLI、SDK、事件与回放；保留 v1 固定样例和原始解释。
- [ ] **P2-015** 新 profile 真实描述自己的载荷；能力协商在运行前产生可解释结果，模型类型、驱动、环境和验证器不匹配时返回 UNSUPPORTED。
- [ ] **P2-016** 将步骤生命周期表达为可替换的类型化阶段；每段输入输出、重试语义、错误和证据均有合同。
- [ ] **P2-017** 插件 descriptor 与配置 schema 在 API 和 Worker 启动时一致校验，运行 manifest 固定实际插件版本与摘要。
- [ ] **P2-018** 新建插件合同测试工具，覆盖初始化、能力协商、观察、提案、状态推进、恢复与结束；通过公共 SDK 验证包外插件。
- [ ] **P2-019** 更新依赖方向检查，使纯算法包、运行核心、业务服务适配包各有明确职责；保持原纯数据示例的独立运行路径。

## 3. 形式化引擎：成本、假设与可解释结果

直接复用 [Z3Prover/z3](https://github.com/Z3Prover/z3) 官方 Python 绑定；优化功能参考 [Z3 Optimization](https://microsoft.github.io/z3guide/docs/optimization/intro/)。保留当前锁定版本作为起点，按兼容性决定是否升级。

- [ ] **P2-020** 定义 ObjectiveSpec：目标表达式、单位、优化方向、字典序优先级、终止目标、有限 horizon 与成本累计方式。
- [ ] **P2-021** 在已有编译器旁实现成本优化；支持生产延期成本与动作成本，并保留现有最短路径策略作为独立基线。
- [ ] **P2-022** 优先用现有 sum、min/max、ite 组合表达成本；只有实际表达不足时扩展 IR，补齐解释器与编译器的同语义实现。
- [ ] **P2-023** 保存可行见证、目标值、求解状态及已证实的最优性范围。超时得到的可行方案与已证明最优方案分别展示。
- [ ] **P2-024** 用可穷举小模型对照最优成本、目标达成与见证重放；构造一个“更短但更贵”的案例确认优化实际生效。
- [ ] **P2-025** 显式表示已知、过期、未知及初值假设。使用 last-known 的规划标记为基于假设的计划，保存假设集合。
- [ ] **P2-026** 为有限不完备状态实现“所有允许补全均满足单步条件”的检查；多步先支持给定动作序列的稳健性检查，明确与可随观测分支的策略综合之区别。
- [ ] **P2-027** 当未知补全产生不同结果时保存 UNKNOWN 或反例补全；将额外观测需求作为类型化结果供生产调度策略使用。
- [ ] **P2-028** 补齐规划缓存键：模型/驱动版本、目标、优化配置、horizon、未知与假设集合、相关预算配置；缓存有容量上限，区别见证和有界无见证结果。
- [ ] **P2-029** 为每次检查输出可回放查询包：输入版本、假设、范围、结果、见证/反例、耗时与后端；UI 和导出共享同一解释。

## 4. 真正的多参与者与轮次调度

先实现每个逻辑步一个参与者动作的显式交错语义。以两名生产调度员协调机器、仓储工位分配为验收场景。

- [ ] **P2-030** 替换固定 participants[0] 的调度方式，实现 round-robin 与场景声明的固定轮次表。
- [ ] **P2-031** 持久化当前 actor、全局 step、actor_step、round 与调度游标；默认单参与者配置保持兼容。
- [ ] **P2-032** 每个参与者获得自己的 Observation、目标、候选集合、策略实例与用量，展示层可切换参与者视角。
- [ ] **P2-033** 明确轮次动作的观测时点、世界修订号与共享资源冲突裁决；为两位调度员同时希望分配同一机器的情形写确定性验收。
- [ ] **P2-034** 事件键、operation_id、proposal_id 和因果关系包含必要的 actor/turn 信息；同轮次重放产生一致业务结果。
- [ ] **P2-035** 将默认终止条件抽象为明确的运行配置，区分单参与者目标完成、联合完成、无可选动作和预算结束。
- [ ] **P2-036** 全局与参与者预算分别计数；记录模型尝试、成功调用、已知 token 用量和未报告用量。
- [ ] **P2-037** 多参与者暂停、继续、取消、Worker 重启后恢复到正确轮次，并保留各自计划进度。
- [ ] **P2-038** 更新 StepRecord、EpisodeRecord、矩阵维度、评分器输入和回放器对多参与者的支持；旧单参与者包继续可读。
- [ ] **P2-039** 交付规则+规则、规则+符号、可配置模型+符号三个运行配置；实测模型配置可用时运行第三种，其余两种始终可验收。

## 5. 持久任务计划与通用策略能力

保留当前 Planner.propose 的兼容入口。在其周围建设可恢复计划，而不是建立另一套编排系统。长任务直接复用 [temporalio/sdk-python](https://github.com/temporalio/sdk-python)；消息处理参考 [Temporal Signals / Queries / Updates](https://docs.temporal.io/encyclopedia/workflow-message-passing)。

- [ ] **P2-040** 实现 TaskPlan、TaskNode、依赖、完成判据、计划版本与当前游标；用订单分解和工序依赖验证。
- [ ] **P2-041** 为策略提供显式 checkpoint/restore 能力，保存结构化任务进度、必要摘要、随机状态和缓存引用。
- [ ] **P2-042** 计划失效由新观测、资源变化、预算或效果差异触发；保存修订前后计划和原因。
- [ ] **P2-043** 提供规则、符号、模型辅助三种计划生成方式，统一产出类型化对象并走相同运行通路。
- [ ] **P2-044** 扩展现有模型客户端的结构化输出校验、超时、限流退避和取消；将传输失败、格式失败与模型返回的业务结果分别记录。
- [ ] **P2-045** 模型配置与开发模型标签分离；调用记录保存实际返回的型号、请求配置和用量。使用现有配置，凭据缺失时报告对应检查未运行。
- [ ] **P2-046** 用同种子的新进程对照不中断运行与中途恢复：比较动作轨迹、轮次、任务游标和规则/符号结果；真实模型重跑只声称请求与证据可复现。
- [ ] **P2-047** 处理重复无进展、重复观测和无候选状态，交付有停止理由的结果；对现有 state-delay 案例给出策略行为差异报告。

## 6. 操作协调与持久服务环境

当前“恢复快照后重新 apply”只适用于声明了这一能力的环境。订单服务是独立进程，数据库中的订单不会因为 Worker 恢复旧快照而自动回滚。

- [ ] **P2-050** 为环境定义显式能力：pure_replayable、persistent_session、snapshot、restore、query_operation、idempotent_step，并在运行启动时协商。
- [ ] **P2-051** 设计并持久化操作状态：prepared、dispatched、completed、failed、outcome_unknown、reconciled；保存阶段转换和原因。
- [ ] **P2-052** 本地业务服务接收稳定 operation_id 并返回已有结果；协调器在调用前登记意图，在响应后记录结果。
- [ ] **P2-053** 模拟“服务已完成业务操作但响应丢失”：先查询 operation_id 与业务状态，再决定后续处理，验证一次订单只产生一次业务效果。
- [ ] **P2-054** 处理重复 Activity、Worker 退出、进程缓存丢失及取消与执行交错；使用服务侧幂等和数据库事务表达已实现的保证范围。
- [ ] **P2-055** 把 planner checkpoint、轮次状态与已持久化提案一起恢复；计费响应丢失时保留未确认用量，分别统计逻辑提案与实际调用尝试。
- [ ] **P2-056** 将共享资源的修订号检查与业务服务条件更新对应起来，给出旧观测提交和更新冲突的真实案例。
- [ ] **P2-057** 本地运行器和 Temporal 路径共享执行阶段与协调逻辑，通过同一套合同样例比较结果。
- [ ] **P2-058** 为异常操作提供查询、人工标记复核和可解释终止入口；所有恢复动作在事件中可追踪。

## 7. 完整本地业务样例与环境管理

建立 **examples/local-order-service/**：订单提交、资源预约、处理队列、库存与完成状态。提供纯数据模型和独立业务服务两种后端，以同一动作合同进行比较。业务操作只包含这些真实的订单处理功能。

- [ ] **P2-060** 实现本地订单服务及其持久化，提供固定的业务 API 和健康状态；使用合成订单数据。
- [ ] **P2-061** 实现独立环境适配包，使用正式 EnvironmentSession 与操作协调接口，不在通用引擎写入业务客户端。
- [ ] **P2-062** 实现 create/start/ready/reset/close 状态和项目归属标记；开发脚本根据项目自带 Compose 定义管理生命周期。
- [ ] **P2-063** 以本机端口或 Compose 内部服务名连接环境；沿用单用户回环地址配置，并在能力页注明部署 profile。
- [ ] **P2-064** 实现后台正常订单流与独立 Probe：吞吐、完成率、队列长度、延迟和恢复时间，固定采样窗口与逻辑/墙钟含义。
- [ ] **P2-065** 提供正常处理、资源短缺、延迟响应、进程重启和预测效果偏差五种可重复案例。
- [ ] **P2-066** 对照纯数据环境与业务服务的动作前提、结果和证据；差异保存为可定位到具体字段与操作的报告。
- [ ] **P2-067** 声明每个环境实际支持的恢复方式：重新播种、服务侧重置、状态导入或快照；恢复结果用探针验证。
- [ ] **P2-068** 加入 CPU/内存/磁盘预检、运行时超时、资源统计和失败后项目资源清理；保留用户其他项目的资源。
- [ ] **P2-069** 从空的项目工作目录完成创建环境、运行实验、导出、重置、重跑与清理，保存真实验收日志。

## 8. 规则、版本发布与效果证据

本节实现通用业务规则与模型发布流程。样例为机器容量、订单依赖、库存约束和计划一致性。

- [ ] **P2-070** 实现带类型的事件—条件—处理规则：触发事件、表达式、版本、优先级以及继续、补充观测、重规划、暂停等结果。
- [ ] **P2-071** 规则条件复用纯表达式 AST；未知、超时、冲突与不支持都有显式结果和优先级解释。
- [ ] **P2-072** 规则编辑产生新版本；编译、类型检查、小模型查询和回归在发布前完成，运行固定引用已发布产物。
- [ ] **P2-073** ModelReleaseRecord 保存检查对象、版本摘要、边界、假设和日志；它表达编译与检查事实。
- [ ] **P2-074** 效果证据区分 observed、verified-within-scope、predicted、unknown，明确可比较字段的新鲜度和缺失状态。
- [ ] **P2-075** 效果差异触发受影响计划暂停与模型修订建议；修订版本经检查后用于新运行，旧运行继续解释原版本。
- [ ] **P2-076** 将反例或效果差异转成最小可回归案例，保留模型、场景、种子、输入、预期与实测输出。
- [ ] **P2-077** 交付一条“发现差异—定位模型—编辑新版本—重新检查—新实验比较”的完整 UI/CLI 路径。

## 9. 评测、回放与研究数据

直接扩展当前 packages/evaluation，保留 [Inspect AI](https://github.com/UKGovernmentBEIS/inspect_ai) 适配。将方法改变的效果与底层环境差异分别记录。

- [ ] **P2-080** 矩阵支持参与者策略组合、环境后端、规则设置、模型版本、种子和预算，生成稳定 cell_id 与来源配置摘要。
- [ ] **P2-081** 矩阵队列支持中断恢复、失败单元重跑和增量合并；已完成单元以完整配置摘要去重。
- [ ] **P2-082** 实现规则、最短路径、成本优化、模型辅助策略的配对比较，并提供观测延迟与计划记忆等机制的配置消融。
- [ ] **P2-083** 预先固定开发/验收场景划分与种子；报告所有失败、缺失、未配对样本和实际分母。
- [ ] **P2-084** 对多场景重复种子的统计标明独立单位；逐场景汇总或采用按场景分组的重采样，避免把相关记录当独立样本。
- [ ] **P2-085** 独立探针与环境评分进入同一报告但保留来源；实验状态失败、目标未达成与指标缺失分开表达。
- [ ] **P2-086** 回放支持轮次、任务计划、操作协调和模型版本定位；记录式回放与重新执行继续使用不同入口。
- [ ] **P2-087** 在空目录离线读包，校验版本、摘要、事件因果和必需产物；生成 JSON/CSV/Markdown 对比报告及明确的工程结论。

## 10. Web、CLI 与 SDK 产品收尾

沿用现有六个区域，通过插件元数据扩展；所有页面连接真实持久化对象。

- [ ] **P2-090** 模型工作台增加成本目标、发布记录、查询包、假设说明和版本差异入口。
- [ ] **P2-091** 场景编辑器支持多参与者配置、轮次顺序、联合终止条件、环境后端及独立预算。
- [ ] **P2-092** 运行台显示当前参与者、计划进度、操作状态、资源使用、探针和恢复事件，暂停/继续/取消有明确反馈。
- [ ] **P2-093** 证据页实现图、事件、计划、模型版本与业务指标相互定位；历史运行按当时 schema 展示。
- [ ] **P2-094** 基准页支持配置筛选、配对样本数、失败/未知分布、成本与任务效果同时比较，并导出当前视图的数据依据。
- [ ] **P2-095** 将 web/src/main.tsx 的页面静态导入改为路由分块；大事件列表按实际记录规模采用分页或虚拟列表。
- [ ] **P2-096** 测量首屏产物体积与大轨迹交互响应；为 UI 空态、等待、失败、重连和窄屏保存真实截图。
- [ ] **P2-097** 为新增操作补齐 fal 命令与 Python SDK，并从公共客户端完成与 Web 等价的纵向路径。
- [ ] **P2-098** 用户配置通过 schema 表单创建和保存，错误定位到字段，示例参数可直接启动实际实验。
- [ ] **P2-099** 完成一次从“新项目”到“两个参与者的成本对比及离线回放”的完整产品验收。

## 11. 本地运行、发行与性能

复用 [Docker Compose](https://github.com/docker/compose)、现有 Helm Chart、[kind](https://github.com/kubernetes-sigs/kind)。镜像可通过 [Buildx OCI exporter](https://docs.docker.com/build/exporters/oci-docker/) 输出到本地文件；本地构建与远程 registry 发布是独立事项。

- [ ] **P2-100** 提供 local-lite、local-services、local-kind 三个明确 profile，并统一由 doctor 报告可用性、预计资源和端口冲突。
- [ ] **P2-101** local-lite 使用已有纯数据样例；local-services 验收平台及订单服务；local-kind 用于 Chart 安装/升级/回滚测试。
- [ ] **P2-102** 先读取实际 VM 资源，再设置实验和求解并发；保存 1 并发基线与资源许可下的 2 并发测量，明确峰值内存、耗时和失败原因。
- [ ] **P2-103** 扩展现有 Compose 冒烟测试，重型运行串行安排；确保清理本次临时项目后再开启下一套完整栈。
- [ ] **P2-104** 对已有 kind 安装脚本增加本地升级/回滚检查，选择已支持的前后版本并验证数据库迁移兼容性；结果明确限于单节点开发集群。
- [ ] **P2-105** 构建本机原生 arm64 wheel/Web/镜像，保存来源版本和摘要；amd64 本地构建采用可用 builder，分别报告构建、仿真运行和原生运行状态。
- [ ] **P2-106** 离线包将 api/worker 等镜像合并导出或采用可验证的内容寻址去重；比较包体积并验证 docker load 与实际安装。
- [ ] **P2-107** 为所发布 OS/架构收集兼容 wheels 和镜像；在空目录完成无包仓库下载的安装与规则/符号演示，模型 API 前提单独列明。
- [ ] **P2-108** 提供本地数据备份/恢复、升级、卸载、重置和磁盘整理文档；备份恢复用一次实际实验验证。
- [ ] **P2-109** 生成发行 manifest、依赖与许可证清单、真实资源读数和本地使用指南；后续部署事项登记触发条件和依赖。

## 12. 深化轨道：有限概率模型

本轨道继承旧任务书的 PRISM-games 选配，不属于默认必做门槛。先完成主线；本地资源和依赖具备时可完成一个小型研究验证，明确记录 SELECTED / NOT_SELECTED / BLOCKED。

来源：[prismmodelchecker/prism-games](https://github.com/prismmodelchecker/prism-games)、[官方能力说明与论文入口](https://www.prismmodelchecker.org/games/)。采用有限、轮流行动、完全观测的小型资源分配模型；具体性质取决于已验证的后端支持。

- [ ] **P2-X01** 固定实际版本、许可与 arm64/amd64 运行方式；给独立模型载荷和 profile，声明随机转移及观测假设。
- [ ] **P2-X02** 通过独立适配器调用 PRISM-games，完成一个公开小例或资源分配例的概率查询，保存原始模型、性质、结果与求解日志。
- [ ] **P2-X03** 若后端支持相应性质的策略导出，展示策略并验证模型内结果；状态规模、误差和支持范围进入能力表。
- [ ] **P2-X04** 将数值结果接入类型化扩展与 UI；概率结论与确定性 Z3 结论分别呈现，记录实际分发许可安排。

## 13. 阶段二验收

交付 **make phase2-check**。这是本地验收入口，不以远程 CI 或 registry 发布为通过条件。沿用阶段一有意义的测试，扩展关键行为测试。

- [ ] **P2-110** 兼容性：旧模型、v1 合同样例、单参与者调度、API/CLI/SDK 与旧回放读取通过。
- [ ] **P2-111** 引擎：第二语义驱动、成本优化、未知补全、见证重放和缓存边界通过。
- [ ] **P2-112** 多参与者：两种确定性策略完成轮次运行；中断恢复后的任务进度、结果和计数正确。
- [ ] **P2-113** 服务环境：空环境创建、业务动作、独立探针、响应丢失协调、重复提交、重置与清理均有真实记录。
- [ ] **P2-114** 产品：Web 创建和运行多参与者场景，CLI 导出，SDK 读取，空目录离线回放通过。
- [ ] **P2-115** 评测：配对矩阵及消融产生包含失败、未知、样本、成本和业务效果的实际报告。
- [ ] **P2-116** 发行：原生本地 Compose、离线安装、kind 适用检查与资源测量有证据；模型实测和异架构状态独立列出。
- [ ] **P2-117** 验收报告逐项绑定 checked_commit、工作区摘要、profile、命令、退出码、时间、日志和产物；跨修订继承的旧 PASS 仅作历史证据。

建议至少包含以下 machine-readable 检查组：

| check_id | 对应能力 |
|---|---|
| compatibility | v1 与阶段一样例 |
| semantic-driver | 驱动替换与第二样例 |
| planning-objectives | 成本及未知假设 |
| multi-actor-recovery | 轮次与计划恢复 |
| service-operations | 持久业务服务协调 |
| model-release | 规则发布与差异修订 |
| evaluation-replay | 矩阵、证据及离线回放 |
| product-path | Web/CLI/SDK |
| local-release | Compose、离线、kind |
| resource-profile | 实际本地资源 |

## 14. 阶段交接

阶段二完成标准是本地必做能力均有证据。深化轨道、真实模型前提和后续部署状态独立记录，不混入已完成能力。

- [ ] **P2-120** 生成 docs/handoff/phase2.md：新增能力、实际命令、目录地图、兼容决策、已知问题与接续入口。
- [ ] **P2-121** 生成 docs/handoff/phase2.manifest.json 和 phase2-checks.json，沿用 phase-handoff/v1；phase=2，completion_scope=local-platform。保留 contract_version、contract_digest、checks 等原有必填字段，多版本与检查分类以新增字段表达。
- [ ] **P2-122** manifest 的 status 使用 complete 或 blocked，并列出 mandatory_checks、conditional_checks、extension_checks、deferred_work；全部必做 PASS 才为 complete。
- [ ] **P2-123** 将 SemanticDriver、TurnScheduler、PlannerCheckpoint、EnvironmentSession、ExecutionStage、ProbeResult、ModelReleaseRecord 的实际类型、版本、路径及例子写入交接。
- [ ] **P2-124** 交付 examples/external-plugin 的增强版或第二个包外样例，证明新扩展通过公共接口接入。
- [ ] **P2-125** 更新 docs/reuse-ledger.md，逐项记录上游 URL、固定版本、许可、实际调用位置、修改与证据。
- [ ] **P2-126** 提供 docs/acceptance-phase2.md 与 docs/local-development.md，写清真实安装、启动、测试、恢复、清理和结果解释方法。
- [ ] **P2-127** 总结必做完成情况、条件项、剩余问题及发行产物位置，以实际验收和交接文件结束本阶段。

### 14.1 交接必填字段

~~~json
{
  "handoff_version": "phase-handoff/v1",
  "phase": 2,
  "completion_scope": "local-platform",
  "status": "blocked",
  "source_revision": {},
  "phase1_baseline": {},
  "contract_version": "formal-lab-contracts/v1",
  "contract_digest": {},
  "contract_versions": [],
  "contract_digests": {},
  "paths": {},
  "commands": {},
  "implemented_capabilities": [],
  "unsupported_capabilities": [],
  "checks": [],
  "mandatory_checks": [],
  "conditional_checks": [],
  "extension_checks": [],
  "deferred_work": [],
  "known_issues": [],
  "reuse_ledger": "docs/reuse-ledger.md"
}
~~~

上面是字段示例，初始状态为 blocked；实际完成后才写 complete。默认契约版本按实际实现填写，完整支持的版本同时列入 contract_versions。提交号、摘要、路径、测试数和命令从真实环境生成。保留 phase1 原始记录，并让阶段三明确引用阶段二的实际交接版本。

现在从接手检查开始，完成主线中的真实实现与本地验收；将复杂但可独立完成的通用工作在本阶段做完整。
