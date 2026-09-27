# 阶段一执行任务书：通用实验平台与有限状态建模引擎

执行模型标签：Opus 5.5  
交付顺序：先执行本文件，再由后续扩展阶段接入领域能力。  
任务类型：直接开发、集成、运行、检查和交接，以可运行产物和验收结果为最终输出。  
编制日期：2026-09-26

## 0. 任务与交付目标

本阶段直接建设一个可独立运行的通用实验平台，并以生产调度这一离散决策场景验证平台能力。任务重点是：数据契约、有限状态模型、规划与检查、实验编排、策略运行、事件流、评测、回放、Web、CLI、SDK、构建与发行。

项目所有者具有大型 SaaS 开发经验，目标是终局可扩展架构。本阶段按完整产品标准推进，交付可运行功能、真实集成、自动检查、可追溯证据和完整用户路径。

完成后，用户应可以创建项目，编辑有限状态模型，配置生产调度实验，选择策略，运行实验，看到实时事件、规划结果与有限边界内的检查结论，比较策略，导出并回放实验。后续扩展通过正式注册表、版本化契约和插件接口接入。

本阶段尽量完成所有具有独立价值且可直接验证的通用能力；具体完成量以实际实现和验收证据为准。

### 0.1 本阶段产品轮廓

本阶段形成以下完整闭环：

- 通用项目、模型版本、场景、策略、运行、事件、产物和指标数据模型。
- 有限离散状态 IR、参考解释器、Z3 编译器和有界查询。
- 纯数据 Environment 接口与生产调度示例环境。
- Temporal 驱动的持久实验编排、预算、暂停/继续/取消和恢复。
- Web 六个功能区、CLI、Python SDK、导入导出与回放。
- Inspect 适配、矩阵评测、指标聚合与可追溯证据。
- OCI、Compose、Helm、离线包和阶段交接产物。
- 插件注册、能力声明、版本化 schema 和后续扩展入口。

### 0.2 运行配置

默认交付单用户本地开发配置，服务入口绑定本机回环地址。项目分组、数据视图和检查结果分别承担组织、展示和模型结论表达职责。文档与 UI 明确标注该配置的实际能力等级，并为后续部署配置保留正式扩展点。

## 1. 执行规则与任务状态

- [x] **P1-001** 检查当前仓库、说明、开发命令、未提交修改及运行环境；以已有代码为起点。空目录执行初始化，已有目录保留用户工作并在其上增量开发。
  - 证据：空仓库初始化；环境与工具链记录见 docs/execution/evidence/P1-001-environment.md（Ubuntu 24.04.4 aarch64 / Docker 29.5.2 / uv 0.12.19 / node 24.21.0 / helm 4.3.0 / temporal CLI 1.9.1）
- [x] **P1-002** 将本任务书登记为仓库内的 **docs/execution/phase-1.md**，持续更新勾选状态。
  - 证据：本文件即 docs/execution/phase-1.md，由 scripts/tick.py 维护勾选与证据
- [x] **P1-003** 建立 **docs/execution/decisions.md**，记录影响后续扩展的选择、理由与替代方案。
  - 证据：docs/execution/decisions.md（D-001 起持续追加）
- [x] **P1-004** 先实现数据契约和纵向闭环，再扩展 UI、批量实验和部署；推进到验收完成。
  - 证据：提交顺序即推进顺序：契约 8b49f9b → 引擎与示例 54a8efe → 平台纵向闭环（持久化/API/SSE/Temporal）0cb1b12、dc02277 → 评测/回放/SDK/CLI 9fe6188 → Web 1e35650、74df1f2 → 部署 2908dc6 → 发行 00f1d3f → 验收 5f0af4a（make phase1-check 20/20 PASS）与交接
- [x] **P1-005** 实际实现并取得证据后才能勾选。阻塞项保留未勾选，追加 **BLOCKED：原因 / 已完成部分 / 解除条件**。
  - 证据：每个已勾选项均附证据行（scripts/tick.py 要求证据文本）；阻塞项规则由 tick.py --block 支持，本阶段结束时无残留阻塞项：条件式检查的前提（用户提供的 OpenAI 兼容中转站、本地 kind 集群）均具备，llm-real / helm-install 实测 PASS
- [x] **P1-006** 常规可逆实现选择自行决策。缺少外部服务配置、基础设施或出现真实语义冲突时，精确说明，同时继续完成其余独立任务。
  - 证据：常规可逆选择自行决策并记录于 docs/execution/decisions.md（D-001..D-013）；外部依赖如实说明：模型名 gpt 6 sol 不存在，改用中转站上的 gpt-5.6-sol 并告知用户；不上云，Helm 安装在本地 kind 临时集群验证；许可证起初未擅自指定（元数据标 UNLICENSED），所有者随后将选择交给执行者，选定 Apache-2.0 并记录理由与兼容性（D-014，tests/architecture/test_license.py）
- [x] **P1-007** 截图、指标、测试、镜像构建与部署状态均以真实执行证据记录；测试代码与测试通过状态分别记录。
  - 证据：截图为 Playwright 真实运行产物（docs/execution/evidence/ui/，20 张）；指标来自真实运行（examples/neutral-scheduling/results/comparison.json、compose-smoke.json、helm/install.json）；测试代码（tests/、各包 tests/）与通过状态（docs/handoff/phase1-checks.json + evidence/checks/*.log）分开记录；镜像构建与部署状态见 release-manifest.json、offline-manifest.json、compose-smoke.json、helm/install.json

必做任务全部取得验收证据后阶段状态才为 complete。上下文切换后读取任务清单继续工作。

## 2. 终局边界与工程组织

保留已有项目合理的技术选择。空仓库默认：

| 层 | 默认选择 | 要求 |
|---|---|---|
| Web | TypeScript + React；已有 Next.js 可保留 | 全部交互连接真实 API 与持久化数据 |
| API / 契约 | Python + FastAPI + Pydantic / JSON Schema | Python 与 TypeScript 使用单一契约来源 |
| 持久化 | PostgreSQL + 迁移工具 | 运行、事件和模型版本持久化 |
| 大对象 | 本地文件与 S3 兼容对象存储接口 | 日志与导出包通过 ArtifactRef 引用 |
| 长任务 | Temporal + 官方 Python SDK | 编排可恢复、可取消 |
| 求解器 | Z3 Python 绑定 | 仅编译受支持的有限离散语义 |
| 评测 | 自有 Run/Metric 契约 + Inspect 适配器 | 通过适配层保持平台契约独立 |
| 发布 | OCI、Compose、Helm、Python SDK、CLI | 开发与最终扩展部署共用构建基础 |

- [x] **P1-010** 建立 contracts、model-core、solver-adapters、orchestrator、platform-api、web、sdk、evaluation、neutral-environment 等模块边界。
  - 证据：模块边界即 workspace 包：packages/{contracts,contracts-ts,model-core,solver-adapters/z3,neutral-environment,strategies,runtime,evaluation,platform-api,orchestrator,sdk}、web、examples/{neutral-scheduling,external-plugin}；依赖方向由 tests/architecture/test_boundaries.py 按真实 import 检查
- [x] **P1-011** API、Worker、Web 按运行职责部署；内部包保持模块化接口，并由实际部署职责决定服务边界。
  - 证据：部署职责：API（fal-api，python.Dockerfile target api）、Worker（fal-worker，target worker）、Web（web.Dockerfile/Caddy）分别部署（Compose 与 Helm 各为独立服务/Deployment）；内部包通过 runtime 引擎与服务层模块化接口复用（docs/execution/evidence/compose-smoke.json）
- [x] **P1-012** 扩展模块通过注册表与能力声明接入。核心包保持插件无关，扩展差异集中在正式接口与元数据中。
  - 证据：插件经 formal_lab.plugins entry point + PluginDescriptor 能力声明接入；核心包不 import 插件包、不含示例插件 id（test_core_is_plugin_agnostic）；评分器按 eval.applies_to 能力选择
- [x] **P1-013** Environment 主线使用项目自带纯数据模拟器；所有已声明能力都对应真实实现与可验证结果。
  - 证据：主线环境为 formal-lab.env.ir-world（packages/neutral-environment，纯数据 IR 模拟器）；声明能力 env.snapshot_restore/observation_delay/truth_overrides/seeded_variation 均有测试（packages/neutral-environment/tests/test_ir_world.py，docs/execution/evidence/M2-core-tests.log）

## 3. 直接复用的仓库及改造落点

优先使用正式包和稳定 API。确需修改内部机制时采用最小范围复制或 fork，并保留适用许可证、来源和差异记录。

### 3.1 Z3：有限模型规划与性质检查

来源：[Z3Prover/z3](https://github.com/Z3Prover/z3)，调研时主许可证为 MIT。

- [x] **P1-020** 核对版本、许可证、Python API 与项目兼容性，固定实际版本。
  - 证据：z3-solver==5.1.0.0（MIT），uv.lock 固定；Python API 经 import z3 使用，差分测试通过（docs/execution/evidence/M2-core-tests.log）
- [x] **P1-021** 复用 Python 绑定与官方有限约束示例；在 **solver-adapters/z3** 实现 IR 编译器，通过官方绑定复用求解器能力。
  - 证据：packages/solver-adapters/z3/src/formal_lab_solver_z3/compiler.py：IR→Z3 编译器，复用官方 Python 绑定（Solver/If/Int/Bool），不修改求解器
- [x] **P1-022** 实现有界目标可达性、单步前置条件检查、有界不变量反例搜索；分别声明量词、边界与结果语义。
  - 证据：verifier.py 实现 GOAL_REACHABILITY(EXISTS_PATH) / INVARIANT_VIOLATION(ALL_PATHS) / ACTION_PRECONDITION(SINGLE_STEP)，语义与边界写在模块文档与 BoundedCheckResult.semantics/bound/assumptions；test_z3_engine.py
- [x] **P1-023** 保存求解状态、步数、耗时、超时原因、变量映射与可解释见证；unknown、超时、未支持分别使用独立结果状态保存。
  - 证据：BoundedCheckResult 保存 solver_status/steps_explored/elapsed_ms/timeout_ms/reason_unknown/variable_mapping/witness(含解释器重放)；UNKNOWN(timeout) 与 UNSUPPORTED 分别测试（test_timeout_yields_unknown_with_reason / test_unsupported_profile_feature）

### 3.2 Temporal：持久实验编排

来源：[temporalio/temporal](https://github.com/temporalio/temporal)、[temporalio/sdk-python](https://github.com/temporalio/sdk-python)。集成时逐项核对所用版本许可。

- [x] **P1-024** 使用官方服务与 Python SDK 实现 **ExperimentWorkflow**，编排能力直接建立在 Temporal 之上。
  - 证据：packages/orchestrator/src/formal_lab_orchestrator/workflow.py ExperimentWorkflow（temporalio==1.33.0 官方 SDK + temporal CLI 1.9.1 dev server/Server 1.32.0）；集成测试 docs/execution/evidence/M5-platform-integration.log
- [x] **P1-025** 数据库、对象存储、模型调用、求解与模拟器操作放入 Activities；工作流聚焦可重放编排。
  - 证据：数据库/对象存储/模型调用/求解/模拟器全部在 activities（activities.py → formal_lab_api.services.execution）；工作流仅编排、信号与查询
- [x] **P1-026** 实现启动、暂停、继续、取消、预算耗尽及 Worker 重启恢复；暂停在声明的逻辑步边界生效。
  - 证据：启动/暂停（逻辑步边界）/继续/取消/预算耗尽/Worker SIGKILL 重启恢复均有集成测试（test_pause_takes_effect_at_step_boundary_and_resume, test_cancel_keeps_evidence, test_budget_override_exhausts, test_worker_crash_is_recovered_without_duplicates；docs/execution/evidence/M5-platform-integration.log；docs/execution/evidence/P1-123-worker-crash-recovery.md）
- [x] **P1-027** 使用稳定 run_id、step_id、operation_id；重试采用幂等键保持事件、计数和模拟器推进的一致性。
  - 证据：确定性 id：step_id=<run>:s<n>，operation_id=<run>:s<n>:propose|apply，事件 idempotency_key 唯一约束；重试后无重复事件/计数（assert_consistent）
- [x] **P1-028** 已发起但结果未知的步骤先读操作记录协调；仅对声明为可幂等重试的步骤重试。
  - 证据：operations 账本：propose 结果（含模型调用）先持久化，重试复用；apply 与快照/事件/计数同事务提交，未知结果按记录协调；Temporal 心跳超时重试证据见 P1-123-worker-crash-recovery.md

### 3.3 Inspect：中性任务评测与日志

来源：[UKGovernmentBEIS/inspect_ai](https://github.com/UKGovernmentBEIS/inspect_ai)、[官方文档](https://inspect.aisi.org.uk/)。调研时主许可证为 MIT。

- [x] **P1-029** 复用通用任务、模型适配和日志接口，将生产调度实验接入 Inspect，并保持评测对象为本阶段的纯数据实验。
  - 证据：inspect-ai==0.3.269（MIT）：Task/Sample 数据集/@solver/@scorer/mean+stderr/eval 与 .eval 日志；examples/neutral-scheduling/.../inspect_task.py 把纯数据调度实验接入 Inspect；InspectModelClient 复用 Inspect 模型适配（docs/execution/evidence/M6-eval-replay-sdk.log）
- [x] **P1-030** 平台保持独立 RunManifest 与 MetricResult，并通过适配层与 Inspect 对象互转。
  - 证据：formal_lab_eval.inspect_adapter：result_to_score（MetricResult→Score，缺失值只进 metadata）与 metric_results_from_log（EvalLog→MetricResult）互转，test_inspect_eval_round_trip 逐样本对照 bundle 指标
- [x] **P1-031** 关键结果由模拟器状态和确定性评分函数给出；LLM 描述仅作辅助说明。
  - 证据：关键指标由模拟器真值状态与确定性评分函数（GenericEvaluator、SchedulingScorer）给出；LLM rationale 仅作为提案说明保存
- [x] **P1-032** 用真实中性任务验证导入、运行、评分、日志归档与平台展示。
  - 证据：真实 inspect eval（CLI，mockllm 占位模型不参与决策）→ formal_lab_eval.inspect_import 导入 4 个样本 run、归档 .eval 日志为项目产物、生成 source=inspect 矩阵并出报告（test_inspect_evaluation_is_imported_and_reported）

### 3.4 复用记录

- [x] **P1-033** 建立 **docs/reuse-ledger.md**：URL、版本/commit、许可、采用模块、复用方式、修改文件、验证证据、升级边界。
  - 证据：docs/reuse-ledger.md：Z3/Temporal/Inspect 的 URL、版本与上游 commit、许可、采用模块、复用方式（均未修改的官方发行物）、修改文件、验证证据、升级边界；其余依赖许可表
- [x] **P1-034** 记录 Z3、Temporal SDK、Inspect 的实际导入或调用路径；复用记录同时包含真实导入或调用路径、版本与验证证据。
  - 证据：reuse-ledger 逐项列出真实导入/调用路径（import z3 / temporalio.workflow|activity|client|worker / inspect_ai.Task|solver|scorer|log），并附版本（uv.lock）与测试证据

## 4. 冻结阶段间契约：formal-lab-contracts/v1

必须交付真实类型、JSON Schema、Python/TypeScript 类型和合同测试。以下名称与语义固定；扩展字段通过版本化方式补充。

| 对象 | 必须表达的内容 |
|---|---|
| PluginDescriptor | 插件 ID/版本、接口版本、能力、配置与输入输出 schema |
| ModelPackage | 插件类别/语义 profile、版本与摘要、类型化状态、动作、性质、来源及编译产物 |
| ScenarioManifest | 模型引用、环境配置、参与者、策略版本、目标、预算、种子、停止条件 |
| Observation | 参与者、逻辑步、状态修订号、已知事实、未知项、证据引用 |
| ActionSpec | 动作类型、参数 schema、前提、预期效果、成本、超时、重试语义 |
| ActionProposal | run/step/actor、动作参数、所依据观测修订号、提议来源 |
| ActionOutcome | operation ID、状态、是否已施加效果、前后修订号、结果与证据 |
| BoundedCheckResult | 查询种类、结论、边界、假设、模型/状态/动作摘要、见证与后端 |
| TraceEvent | event/run ID、单调序号、因果父事件、逻辑/墙钟时间、负载 schema |
| ArtifactRef | 对象位置、媒体类型、字节数、内容摘要、格式版本 |
| MetricDefinition / MetricResult | 指标 ID/版本、单位、方向、聚合方式、数值与证据 |
| RunManifest | 实际固定的模型/插件/环境版本、配置、预算、种子、状态与产物 |

- [x] **P1-040** 从单一契约来源生成其余语言类型；提交生成命令，并在 CI 检查漂移。
  - 证据：Pydantic 为唯一来源，make contracts 生成 schemas/TS/文档；CI 在 GitHub ubuntu-24.04 x86_64 上执行 make contracts-check（重新生成后 git diff --exit-code）并通过（docs/execution/evidence/ci-run.json，run 36283566183）
- [x] **P1-041** 实现稳定接口：ModelFrontend.compile、Planner.propose、Verifier.check、Environment.reset/observe/step/snapshot/restore/close、Evaluator.score、ArtifactStore.put/get。
  - 证据：接口定义 packages/contracts/src/formal_lab_contracts/interfaces.py；实现：IRJsonFrontend.compile、Z3BoundedPlanner/EddDispatchPlanner/LLMPlanner.propose、Z3Verifier.check、IRWorldEnvironment.reset/observe/step/snapshot/restore/close、GenericEvaluator/SchedulingScorer.score、Local/S3ArtifactStore.put/get
- [x] **P1-042** 每个接口给出可运行示例；Environment 示例仅调用纯数据模拟器。
  - 证据：examples/interfaces/{model_frontend,verifier,environment,planner,evaluator,artifact_store}.py，全部由 tests/examples/test_interface_examples.py 运行通过；Environment 示例只调用纯数据 IR 模拟器
- [x] **P1-043** 定义统一错误：输入无效、版本不匹配、不支持、超时、结果未知、取消、可/不可重试失败。
  - 证据：formal_lab_contracts.errors：INVALID_INPUT/VERSION_MISMATCH/UNSUPPORTED/TIMEOUT/RESULT_UNKNOWN/CANCELLED/RETRYABLE_FAILURE/NON_RETRYABLE_FAILURE(+NOT_FOUND/CONFLICT)，异常↔ErrorInfo 往返测试 test_error_model_round_trip_and_retryability
- [x] **P1-044** 扩展字段须有命名空间、版本与 schema；核心对象持续保持强类型结构。
  - 证据：ExtensibleModel.extensions：反向 DNS 命名空间 + version + schema_id，JSON Schema propertyNames 约束，保留 formal-lab.core.*；核心对象 extra=forbid（fixtures invalid/unknown-core-field, bad-extension-namespace）
- [x] **P1-045** 实现 capabilities 协商；未支持语义返回显式 UNSUPPORTED 结果。
  - 证据：capabilities.negotiate + PluginRegistry.negotiate；test_capability_negotiation；Verifier 对未支持 profile/feature 返回 verdict=UNSUPPORTED（非异常）
- [x] **P1-046** 编辑模型产生新版本；运行固定引用版本；旧实验持续引用其原始版本与解释。
  - 证据：编辑=新增不可变 ModelVersion（内容不变不建新版本）；场景与运行固定 (package_id, version, digest)，旧实验继续引用原版本（test_model_versions_are_immutable_and_runs_keep_their_version；UI test_model_workbench_edit_check_and_persist）
- [x] **P1-047** 导出 **contracts/v1/**、**docs/contracts/v1.md**，固定契约摘要并写入交接。
  - 证据：contracts/v1/（28 个 schema 文件 + DIGEST.json）与 docs/contracts/v1.md 已导出；契约摘要 sha256 0cbd6256c21eead867cdd3bcf8ea7f1011207d4dacd6d09996b543575e21312b 写入 docs/handoff/phase1.manifest.json 的 contract_digest；漂移检查 make contracts-check 在 CI 与验收中通过

### 4.1 精确结果语义

- [x] **P1-048** query_kind 至少区分 GOAL_REACHABILITY、INVARIANT_VIOLATION、ACTION_PRECONDITION，并分别表达“存在路径”与“所有路径满足性质”的查询语义。
  - 证据：QueryKind 三类 + QuerySemantics EXISTS_PATH/ALL_PATHS/SINGLE_STEP，模型校验器强制一致（semantic-invalid/semantics-mismatch）
- [x] **P1-049** 搜索结果使用 WITNESS、NO_WITNESS_WITHIN_BOUND、UNKNOWN、UNSUPPORTED；NO_WITNESS_WITHIN_BOUND 始终携带查询边界并按有界结论展示。
  - 证据：SearchVerdict WITNESS/NO_WITNESS_WITHIN_BOUND/UNKNOWN/UNSUPPORTED；NO_WITNESS 结果总带 bound 与“有界结论”解释（test_goal_not_reachable_within_bound_is_bounded_conclusion）
- [x] **P1-050** 单步前提结果区分 APPLICABLE、INAPPLICABLE、UNKNOWN、UNSUPPORTED；证据不足保持未知。
  - 证据：PreconditionVerdict APPLICABLE/INAPPLICABLE/UNKNOWN/UNSUPPORTED；未知项作为自由变量，结论不一致时 UNKNOWN（test_precondition_with_unknowns_matches_interpreter）
- [x] **P1-051** 普通检查结果表示模型内结论，并预留类型化扩展槽供后续能力追加。
  - 证据：BoundedCheckResult.scope=MODEL_INTERNAL + extensions 类型化扩展槽

## 5. 中性有限状态 IR 与可用引擎

必做语义 profile 为 **deterministic_finite_v1**：有限实体集合；布尔、枚举、有界整数；纯表达式 AST；离散逻辑步；显式动作顺序；确定性效果。用能力矩阵说明时间、并发、概率与部分观测支持范围。

- [x] **P1-060** 实现解析、类型与引用检查、规范化序列化和版本摘要；表达式采用纯 AST 与显式解释器执行。
  - 证据：formal_lab_model.checker（解析/类型/引用检查，ModelIssue 带路径）、frontend.canonical_ir/ir_digest（规范化 + sha256）；纯 AST + 显式解释器；test_model_core.py
- [x] **P1-061** 实现纯 Python 参考解释器，与 Z3 编译器独立实现同一语义。
  - 证据：formal_lab_model.interpreter（纯 Python，闭包编译 AST）；Z3 编译器独立实现同一语义，仅共享静态符号表
- [x] **P1-062** 实现初始状态、动作适用性、状态转移、目标条件与有限步轨迹。
  - 证据：Interpreter.initial_state/precondition/step/apply/successors/holds/replay；test_lamp_semantics_and_domain_guard / test_two_jobs_*
- [x] **P1-063** 小状态空间比较解释器穷举与 Z3 查询；求解见证必须能被解释器重放。
  - 证据：60 个随机模型 + 合成目标：解释器 BFS 与 Z3 在判定与最短见证长度一致，见证经解释器重放 CONFIRMED；反空洞守卫要求 ≥40 个深度≥2 见证（test_differential_*，docs/execution/evidence/M2-core-tests.log）
- [x] **P1-064** 概率、并发等当前 profile 之外的语义返回 UNSUPPORTED，并记录对应扩展接口与能力矩阵。
  - 证据：profile 外语义（features / semantic_profile）→ 前端 Unsupported、Verifier verdict=UNSUPPORTED 并给出 extension_point；能力矩阵见 docs/architecture/capability-matrix.md（由代码生成）
- [x] **P1-065** truth state 与 Observation 为不同对象；用延迟产线状态演示未知，并在 UI 与文档中将其解释为实验语义。
  - 证据：真值状态只在环境与证据中，Observation 为独立对象；状态延迟场景演示未知；UI 以“已观测/过期/未知(上次已知)”标注并在回放中并列真值快照（参与者不可见）；文档 docs/architecture/observation-semantics.md；UI 测试 docs/execution/evidence/M7-web-ui.log
- [x] **P1-066** 实现通用效果比较：符合、存在差异、信息不足；保存字段级差异与证据。
  - 证据：formal_lab_model.compare.compare_effects：MATCH/DIFFERENT/INSUFFICIENT_INFORMATION + 字段级 FieldDiff；每步 EFFECT_COMPARED 事件；expectation-mismatch 场景 effect_mismatches>0

## 6. 必做样例：生产调度实验

建立 **examples/neutral-scheduling/**。实体为订单、工序、机器、工位和有限资源。动作是分配工序、推进逻辑时间、暂停/恢复模拟机器、重排队列。条件包括资源容量、工序依赖与机器容量。目标是完成订单并降低模拟延期成本。环境完全由项目内纯数据模型驱动。

- [x] **P1-070** 提供正常调度、资源不足、状态延迟、预期与模拟结果不一致四个场景。
  - 证据：examples/neutral-scheduling：normal / resource-shortage / state-delay / expectation-mismatch（scenarios.py），规则与 Z3 策略全部 SUCCEEDED（test_scenarios_complete_with_non_stub_strategies）
- [x] **P1-071** 实现确定性规则策略和 Z3 规划策略，共用 Planner 接口。
  - 证据：EddDispatchPlanner（RULE）与 Z3BoundedPlanner（SYMBOLIC）共用 Planner 接口
- [x] **P1-072** 实现通用 LLM 策略适配：结构化观测与候选 schema 输入，ActionProposal 输出；当前示例策略只作用于生产调度环境。
  - 证据：formal_lab_strategies.llm_planner：结构化观测 + 候选 JSON Schema 输入，ActionProposal 输出；HTTP 级 mock 测试 test_llm_planner.py
- [x] **P1-073** 无模型 API 配置时，规则和符号策略仍可完整运行；模型替身单独标注并与真实模型实验结果分开。
  - 证据：无 FAL_LLM_API_KEY 时 LLM 策略显式报错，规则/符号策略完整运行；StubModelClient 结果标注 LLM_STUB（test_llm_stub_results_are_labelled, test_unconfigured_llm_is_explicit）
- [x] **P1-074** 有可用配置时做一次真实模型集成检查；无配置留下入口及未测记录，继续其余工作。
  - 证据：用户提供的 OpenAI 兼容中转站 + gpt-5.6-sol：normal 场景 14 步 SUCCEEDED，14 次调用 / 104,039 tokens，全部来源 LLM（docs/execution/evidence/P1-074-llm-integration.json，tests/integration/test_llm_real.py）
- [x] **P1-075** 使用同一模拟器、预算与评分函数比较策略，保存实际结果。
  - 证据：同一模拟器/预算/评分函数：4 场景 × {EDD 规则, Z3, LLM 替身} × 种子 1–5 = 60 run，结果保存于 examples/neutral-scheduling/results/comparison.json（Z3 相对规则步数更少 p=0.00214，延期成本差异不显著 p=0.706；替身单独标注 LLM_STUB）

## 7. 平台后端与运行时

- [x] **P1-080** 实现项目、模型版本、场景、策略配置、运行、产物及指标的持久 CRUD 和数据库迁移。
  - 证据：PostgreSQL + Alembic（formal_lab_api/migrations/versions/0001_initial_schema.py）：projects/models/model_versions/scenarios/strategy_configs/runs/run_events/operations/env_snapshots/artifacts/metrics/checks/plugin_catalog；REST CRUD 见 formal_lab_api/app.py；docs/execution/evidence/M5-platform-integration.log
- [x] **P1-081** 状态机区分已创建、排队、运行、暂停中、已暂停、取消中、已取消、成功、失败和预算结束。
  - 证据：RunStatus 十态 + services/events.py ALLOWED 转移表；集成测试覆盖 QUEUED/RUNNING/PAUSING/PAUSED/CANCELLING/CANCELLED/SUCCEEDED/FAILED/BUDGET_EXHAUSTED（docs/execution/evidence/M5-platform-integration.log）
- [x] **P1-082** 启动时固定模型、配置、策略与环境版本，创建真实 RunManifest。
  - 证据：formal_lab_runtime.manifest.make_manifest 固定模型摘要/版本、场景快照+摘要、各角色插件版本与描述符摘要、预算、种子、平台版本与源码修订（test_run_is_persisted_with_pinned_manifest）
- [x] **P1-083** 实现有序事件、序号查询、SSE 与断线续传；去重和恢复后保持顺序。
  - 证据：gap-free seq（行锁分配）、idempotency_key 去重、GET /runs/{id}/events?after_seq=、SSE /events/stream + Last-Event-ID 续传（test_sse_live_stream_and_reconnect）
- [x] **P1-084** 实现步数、墙钟时间、模型调用及 tokens 预算；每类运行记录其适用预算维度。
  - 证据：步数/墙钟（扣除暂停时长）/模型调用/tokens 预算；manifest.config.budget_dimensions 按策略能力记录适用维度（test_budget_dimensions, test_budget_override_exhausts）
- [x] **P1-085** 实现 ArtifactStore 本地与 S3 兼容适配，大对象通过 ArtifactRef 存储，数据库事件保存引用与摘要。
  - 证据：LocalArtifactStore + S3ArtifactStore（SeaweedFS 4.47 实测 test_s3_artifact_store_roundtrip）；快照/模型调用记录以 ArtifactRef 存储，事件只含引用与摘要
- [x] **P1-086** 失败/取消保留现场与证据，环境按生命周期关闭。
  - 证据：取消/失败保留快照、事件与部分指标（test_cancel_keeps_evidence, test_non_retryable_failure_finalizes_as_failed_with_evidence）；finish_run 关闭环境
- [x] **P1-087** 提供普通日志、错误、健康检查和运行诊断。
  - 证据：结构化日志（var/log/*.log）、统一 ErrorInfo 错误、/health、/api/v1/health/ready（DB/Temporal/对象存储）、/runs/{id}/diagnostics（工作流描述+操作记录）
- [x] **P1-088** 插件系统加载启动时已安装并登记的模块，注册、版本和能力信息进入统一目录。
  - 证据：entry point 注册表 + plugin_catalog 表（API/Worker 启动时同步），GET /api/v1/plugins 返回版本/能力/描述符摘要/来源

## 8. Web：六个真实功能区

| 区域 | 必须完成的行为 |
|---|---|
| 模型工作台 | 结构图/表单编辑、类型错误、版本差异、编译与检查 |
| 场景管理 | 模型版本、参与者、策略、环境、预算配置及复制 |
| 策略注册表 | 能力、配置 schema、版本、兼容性及运行配置 |
| 实验运行台 | 状态、事件、候选、检查、效果、暂停/继续/取消 |
| 证据与回放 | 因果时间线、产物预览、差异报告、按步回放 |
| 基准对比 | 同场景/预算/种子比较、指标、缺失值与统计范围 |

- [x] **P1-090** 六个区域均接真实 API，提供加载、空数据、错误、禁用与完成状态。
  - 证据：六个区域（模型工作台/场景管理/策略注册表/实验运行台/证据与回放/基准对比）均调用真实 API，含加载、空数据、错误（NOT_FOUND）、禁用（终态暂停按钮）与完成状态；Playwright 测试 docs/execution/evidence/M7-web-ui.log，截图 docs/execution/evidence/ui
- [x] **P1-091** 模型/场景编辑可保存、刷新恢复并实际启动实验。
  - 证据：模型表单编辑→刷新恢复草稿→保存为新版本→刷新后仍在；场景种子修改保存为新修订→刷新保持→“运行实验”启动（test_model_workbench_edit_check_and_persist, test_scenario_edit_persists_and_starts_run）；该测试发现并修复了场景草稿被覆盖的缺陷
- [x] **P1-092** 长实验通过 SSE 更新；刷新重连后继续查看。
  - 证据：运行台用 EventSource(SSE) 实时更新，运行中途刷新页面后先分页加载历史再按最后 seq 续传，最终事件数与 API event_seq 一致（test_run_console_live_sse_resume_after_reload）
- [x] **P1-093** 图、表、事件互相定位；动作详情显示输入、前提、判断及效果。
  - 证据：时间线/状态图表/事件表/步骤表点击互相定位到步骤，←/→ 键切换；步骤详情展示观测输入、候选、前提检查、决策依据与效果（字段级预测 vs 观测）
- [x] **P1-094** 检查范围可见，区分已观测、有界结论、预测和未知。
  - 证据：图例与徽标区分 已观测/过期/未知/预测/有界结论/模型内结论；检查结果显示边界、假设与语义（EXISTS_PATH/ALL_PATHS/SINGLE_STEP）
- [x] **P1-095** 标签、状态字段、动作显示与指标由插件元数据扩展；核心 UI 通过 schema 和注册表渲染生产调度样例。
  - 证据：标签/状态字段/动作显示/指标名全部来自模型 IR 标签与插件 PluginDescriptor.ui（web/src/labels.ts），核心 UI 无调度专用代码；插件配置表单由 config_schema 渲染（SchemaForm）
- [x] **P1-096** 完成基本响应式和键盘操作，检查实际截图，并将遮挡、溢出和图表可读性纳入 UI 验收。
  - 证据：桌面 1440 与手机 375 下 7 个页面无横向溢出（自动断言），手机抽屉导航、Tab 方向键、Esc 关闭对话框；人工检查截图后修复了结构图第四列被裁切、图表标签重叠、窄屏表格逐字换行、侧栏背景截断（docs/execution/evidence/ui）

## 9. 评测、回放、CLI 与 SDK

- [x] **P1-100** 实现场景 × 策略 × 种子 × 预算矩阵，保存每个组合的真实状态。
  - 证据：formal_lab_eval.matrix.expand + POST /projects/{id}/matrices；每个组合一个真实 run，报告 cells 列出 run_id 与真实状态（CLI 18 格矩阵测试）
- [x] **P1-101** 指标支持单位、方向、缺失值、样本数、聚合与配对比较。
  - 证据：MetricDefinition 单位/方向/聚合；aggregate 输出 sample_size/missing_count；paired_compare 按 (场景, 种子, 预算) 配对（test_stats.py, test_cli_matrix_compares_two_non_stub_strategies）
- [x] **P1-102** 置信区间注明方法和样本；显著性仅在统计条件满足时报告，缺失值使用独立缺失语义参与聚合。
  - 证据：区间注明方法与 n（Wilson / percentile bootstrap，n≥3）；精确 Wilcoxon 仅在 ≥6 个非零配对差时报告，否则给出不报告原因；MISSING/NOT_APPLICABLE 独立语义（test_stats.py 含独立穷举对照）
- [x] **P1-103** 分开实现事件回放和重新运行：前者查看原轨迹，后者产生新 run 并保留来源。
  - 证据：回放：GET /runs/{id}/events、/steps/{n}、fal replay view/step（只读原轨迹）；重新运行：POST /runs/{id}/rerun 产生新 run，source_run_id 与 lineage.reruns 记录来源（test_rerun_creates_new_run_with_lineage）
- [x] **P1-104** 导出自包含 replay 包，包含契约、manifest、事件、模型快照与必需产物；在空工作目录验证导入。
  - 证据：formal-lab/replay-bundle@1：契约 schemas+DIGEST、manifest、events、模型快照、指标、快照/模型调用产物，全部带 sha256；空工作目录离线 verify/view/step（服务地址指向不可达端口），删除后导入新项目事件逐条一致（docs/execution/evidence/M6-eval-replay-sdk.log）
- [x] **P1-105** CLI 支持模型校验、运行/查看/取消实验、矩阵、导入导出和回放。
  - 证据：fal CLI：model validate/push、run start/show/events/step/cancel/pause/resume/rerun、matrix run/report、export/import、replay verify/view/step（test_sdk_cli_replay.py）
- [x] **P1-106** Python SDK 和包外插件样例仅使用公开接口完成注册。
  - 证据：formal_lab_sdk.Client + formal_lab_sdk.plugins 公开接口；examples/external-plugin（仅依赖 formal-lab-sdk，entry point 注册）被目录发现并完成实验，提案来源 EXTERNAL（test_external_plugin_registered_through_public_interfaces）
- [x] **P1-107** Web、CLI、SDK 共用服务与契约，三种入口共用同一服务与契约实现。
  - 证据：Web（fetch /api/v1）、CLI（formal_lab_sdk.Client）、SDK 共用同一 FastAPI 服务层与 formal-lab-contracts/v1（TS 类型由同一 Pydantic 源生成）

## 10. 构建、部署与发行基础

- [x] **P1-110** 提供锁依赖的构建、启动、迁移、测试命令和仅含示例配置项的 .env.example。
  - 证据：uv.lock + pnpm-lock.yaml 锁定；make bootstrap/build/dev-up/migrate/seed/test-unit/test-integration/test-ui/images/compose-up/release/phase1-check 等（make help）；.env.example 仅含示例值
- [x] **P1-111** 提供 Web/API/Worker OCI 构建定义，记录实际镜像引用与摘要。
  - 证据：deploy/docker/python.Dockerfile（api/worker）与 web.Dockerfile；实际镜像 ID、架构、大小与 revision 标签记录于 docs/execution/evidence/compose-smoke.json 与 release-manifest.json
- [x] **P1-112** Compose 启动 Web/API/Worker/PostgreSQL/Temporal 及选定对象存储配置，实际跑通中性实验。
  - 证据：deploy/compose/docker-compose.yaml 启动 web/api/worker/postgres/temporal/s3(SeaweedFS)+迁移；scripts/compose-smoke.sh 实测经 :8080 运行实验（SSE 经代理完整）、8 格矩阵全部成功、18 个产物位于 S3、导出回放包（docs/execution/evidence/compose-smoke.json）
- [x] **P1-113** Helm 覆盖配置、服务、Worker 和外部存储连接；完成 lint/模板检查。有集群再验证安装，分开记录状态。
  - 证据：Chart 覆盖配置/Service/API/Worker/Web/迁移 Hook/外部 PostgreSQL、Temporal、S3 与 LLM Secret；helm lint --strict、helm template、kubeconform 通过（evidence/helm/{lint,kubeconform}.log）；安装状态单独记录：kind v0.33.0 / Kubernetes v1.37.0 安装并跑通实验（evidence/helm/install.json）
- [x] **P1-114** Helm 交付通用开发部署模板，并在文档中准确标注已验证的部署范围。
  - 证据：docs/deployment.md 按方式列出已验证范围与未验证项（多节点、Ingress 控制器、外部 HA 数据库/Temporal、升级回滚未验证），能力等级为单用户本地开发配置
- [x] **P1-115** 构建 SDK wheel、CLI 和平台基础发行包；manifest 记录源码、依赖、镜像、场景及文档。
  - 证据：make release：12 个 wheel（含 formal-lab-sdk 与 fal CLI）、Web 包、3 个镜像标签；manifest 记录源码 revision、uv.lock/pnpm-lock 摘要、契约摘要、wheel sha256、镜像 ID、场景与文档；SDK/CLI 在全新 venv 中无服务运行（docs/execution/evidence/release-manifest.json）
- [x] **P1-116** 基础离线打包脚本区分已装入内容与外部前提；manifest 准确列出实际包含的权重、镜像与依赖。
  - 证据：scripts/offline_bundle.py：区分 included（6 个镜像、30 个 wheel、Web、compose(pull_policy never)、install.sh、model_weights=[]）与 not_included/external_prerequisites；--verify 解包到空目录、pip --no-index 安装 CLI、启动并跑通实验（docs/execution/evidence/offline-manifest.json）
- [x] **P1-117** 文档给出空环境开始的路径，记录实际验证的 OS、架构和资源，资源要求以实际验证记录为准。
  - 证据：docs/getting-started.md：从空 Ubuntu 24.04 到运行与验收的完整路径；实测环境 Ubuntu 24.04.4 aarch64 / 4 vCPU / 5.9 GiB，另有 CI x86_64；资源表来自实测（内存、磁盘、镜像、耗时）

## 11. 阶段一必做验收

提供统一命令 **make phase1-check**；已有任务工具可以用等价命令，但必须写入交接。

- [x] **P1-120** 契约：Python/TypeScript/schema 一致；错误输入、未知和未支持语义正确处理。
  - 证据：验收 contracts PASS（make contracts-check 无漂移；tests/contracts 39 passed；TS ajv/tsc 契约测试 27/27）+ contract-semantics PASS（前端错误、UNSUPPORTED、含未知项的前提、超时 UNKNOWN、错误模型往返、能力协商：6 passed）；phase1-checks.json（提交 5f0af4a，2026-09-27）；日志 docs/execution/evidence/checks/contracts.log、contract-semantics.log
- [x] **P1-121** 引擎：可达、不可达、不变量反例、超时/未知均有真实验证。
  - 证据：验收 engine PASS：可达见证、界内无见证、不变量反例、超时 → UNKNOWN（附原因）等 27 passed；phase1-checks.json（提交 5f0af4a，2026-09-27）；日志 docs/execution/evidence/checks/engine.log
- [x] **P1-122** 语义：解释器与 Z3 小模型对照，见证可回放。
  - 证据：验收 semantics-differential PASS：随机小模型上参考解释器（穷举 BFS）与独立 Z3 编译器判定逐一对照，Z3 见证经解释器回放，另有防空转守卫测试，81 passed；phase1-checks.json（提交 5f0af4a，2026-09-27）；日志 docs/execution/evidence/checks/semantics-differential.log
- [x] **P1-123** 运行：持久化、Worker 恢复、取消、重复提交、断线续传正确。
  - 证据：验收 runtime-integration PASS（真实 PostgreSQL + Temporal）：持久化、SIGKILL Worker 后恢复、逻辑步边界暂停/继续、取消、预算、幂等重复提交、SSE Last-Event-ID 断线续传，12 passed；phase1-checks.json（提交 5f0af4a，2026-09-27）；日志 docs/execution/evidence/checks/runtime-integration.log
- [x] **P1-124** 产品：UI 创建运行并查看结果，CLI 导出，SDK 读取。
  - 证据：UI 创建并完成实验（Playwright：场景页“运行实验”与运行台“启动”），CLI 导出回放包（fal export），SDK 读取 manifest/事件/步骤（test_sdk_builds_project_from_scratch_and_reads_results）
- [x] **P1-125** 评测：至少两种非替身策略在多个固定种子/场景下产生可比结果。
  - 证据：CLI 矩阵：3 场景 × EDD 规则/Z3 规划 × 种子 1,2,3，18 run 全部 SUCCEEDED，delay_cost 等 9 对配对比较；来源 RULE/SYMBOLIC（非替身）
- [x] **P1-126** 回放：离线查看原事件；重新运行产生新 ID，并保留原结果及来源关系。
  - 证据：离线查看导出包（无服务）；重新运行产生新 ID，原 run 保留并记录 lineage（test_cli_export_offline_replay_import_and_rerun, test_import_into_fresh_database_keeps_events_and_allows_rerun）
- [x] **P1-127** 部署：Compose 完整路径实测；Helm 渲染与安装验证状态分开记录。
  - 证据：Compose 与 Helm 分开记录：compose-e2e PASS（整栈镜像启动，经 Caddy 跑完一次实验 SUCCEEDED、110 条事件经 SSE 全部收到、18 个产物写入 S3，docs/execution/evidence/compose-smoke.json）；helm-render PASS（lint/template/kubeconform：6 个资源全部有效）；helm-install PASS（kind v0.33.0 / Kubernetes v1.37.0 临时集群安装 Chart 并跑完实验 SUCCEEDED，194 条事件，docs/execution/evidence/helm/install.json）；phase1-checks.json（提交 5f0af4a，2026-09-27）
- [x] **P1-128** 边界：主路径仅调用中性模拟器，没有扩展动作、外部目标执行器或伪装的自由命令工具。
  - 证据：主路径仅调用 IR 纯数据模拟器：环境/策略/引擎无 subprocess/shell/socket 执行器，网络只在模型客户端；环境拒绝非模型声明的动作（test_main_path_has_no_external_executors, test_actions_are_limited_to_model_declared_types）
- [x] **P1-129** 为关键行为写有意义的测试，避免大量镜像实现的单元测试掩盖端到端未接通。
  - 证据：关键行为以端到端测试覆盖，而非镜像实现：真实服务集成（运行 12、Web UI Playwright 12、SDK/CLI/回放/矩阵 6）、解释器 ↔ 独立 Z3 编译器差分（81，含非空转守卫）、真实模型检查；unit-suite 211 passed，lint PASS；测试代码见 tests/ 与各包 tests/，通过状态见 phase1-checks.json（提交 5f0af4a，2026-09-27）

每个验收项保存命令、退出码、时间、日志和版本。勾选状态以真实执行证据为准。条件式检查（例如缺少外部模型配置时的真实调用、缺少集群时的 Helm 安装）单独记录 NOT_RUN 与原因，并让能力表只展示实际完成和实测的范围。

## 12. 强制交接：phase-handoff/v1

- [x] **P1-130** 生成 **docs/handoff/phase1.md**：已完成能力、真实命令、目录地图、问题、未验证项、扩展入口及本地开发限制。
  - 证据：docs/handoff/phase1.md：已完成能力与入口、真实命令、验收结果表（make handoff 从 phase1-checks.json 生成，状态 complete）、目录地图、问题与未验证项、本地开发限制、扩展入口与接续条件
- [x] **P1-131** 生成 **docs/handoff/phase1.manifest.json**，使用下表固定字段。
  - 证据：docs/handoff/phase1.manifest.json（scripts/handoff.py / make handoff 生成）：表中全部字段齐备，status=complete（无失败检查、无未运行的必做检查、除交接自身与流程项外无未勾选项），source_revision 记录受检提交 5f0af4a 与工作区状态，contract_digest sha256 0cbd6256…
- [x] **P1-132** 生成 **docs/handoff/phase1-checks.json**：任务 ID、命令、结果、退出码、日志/产物、实际执行时间。
  - 证据：docs/handoff/phase1-checks.json（make phase1-check 生成）：20 项检查，每项含任务 ID、命令、结果、退出码、开始/结束时间与耗时、日志（docs/execution/evidence/checks/*.log）与产物路径；提交 5f0af4a 干净工作区上 20 PASS / 0 FAIL / 0 NOT_RUN
- [x] **P1-133** 生成 **docs/architecture/plugin-integration.md**：如何新增前端、语义 profile、规划器、验证器、环境和评分器，并提供生产调度示例。
  - 证据：docs/architecture/plugin-integration.md：注册机制（entry point、PluginDescriptor、PluginServices、能力协商、UI 元数据）与前端/语义 profile/规划器/验证器/环境/评分器/产物存储的接口约定，附生产调度示例走查与包外插件示例
- [x] **P1-134** 在 **tests/contracts/** 保留后续扩展阶段可复用的合同测试与兼容样例。
  - 证据：tests/contracts/：build_fixtures.py + fixtures/{valid,invalid,semantic-invalid}（15/11/7 个兼容样例）+ test_contracts.py；TS 侧 packages/contracts-ts/test 复用同一组样例
- [x] **P1-135** **examples/neutral-scheduling/** 独立可运行，作为后续回归哨兵。
  - 证据：python -m formal_lab_example_scheduling run|compare|check|export-model 无需服务独立运行；回归哨兵 examples/neutral-scheduling/tests/test_sentinel.py
- [x] **P1-136** 输出真实变更与交接状态，并在 phase-handoff/v1 产物生成后结束本阶段执行。
  - 证据：真实变更与交接状态：manifest source_revision.agent_changes（全部提交以用户身份 3351666087 完成）与 status=complete；交接产物提交并推送后向用户输出最终报告，本阶段执行结束

| manifest 字段 | 要求 |
|---|---|
| handoff_version | phase-handoff/v1 |
| phase | 1 |
| status | complete 或 blocked；全部必做项通过才能 complete |
| source_revision | 实际 commit、工作区是否修改；无 Git 用源码快照摘要 |
| contract_version | formal-lab-contracts/v1 |
| contract_digest | 固定排序契约文件的摘要与计算方法 |
| paths | 契约、API、示例、部署、日志、报告和发行产物的真实相对路径 |
| commands | bootstrap、dev、demo、phase1_check、export、replay、build 实际命令 |
| implemented_capabilities | 已实现且验证的能力 |
| unsupported_capabilities | 未支持的语义与功能 |
| deferred_work | 后续扩展事项与依赖 |
| checks | 检查 ID、结果和证据路径 |
| reuse_ledger | 复用记录路径 |
| known_issues | 缺陷、影响和复现条件 |

commit、digest、路径和测试结果均从实际仓库与执行产物生成；自身修改与用户原有未提交修改分别记录。

## 13. 最终回复

提供：实际功能及本地入口；准确启动/验收命令；通过/失败/阻塞汇总；交接文件位置；后续扩展接续条件及缺失前提。

现在检查仓库并直接执行任务，持续推进到真实实现、检查、验收与交接产物完成。
