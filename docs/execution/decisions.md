# 决策记录（Phase 1）

每条记录：决策、理由、被放弃的替代方案、对后续扩展的影响。新决策追加到末尾，编号不复用。

## D-001 仓库组织：uv workspace + pnpm workspace 的单仓

- **决策**：Python 模块按职责拆为独立 workspace 包（`packages/*`、`examples/*`），用 uv 统一锁定（`uv.lock`）；Web 与生成的 TypeScript 契约用 pnpm 锁定（`pnpm-lock.yaml`）。
- **理由**：模块边界（contracts / model-core / solver-adapters / neutral-environment / strategies / evaluation / orchestrator / platform-api / sdk）在包层面强制依赖方向；单一锁文件保证 API、Worker、CLI 使用同一依赖闭包。
- **替代方案**：单个 Python 包 + 子模块（边界靠约定，易被跨层导入破坏）；Poetry / Hatch 多项目（无跨包统一锁）。
- **扩展影响**：后续阶段新增领域能力 = 新增 workspace 包或包外插件，不修改核心包。

## D-002 单一契约来源：Pydantic v2 模型 → JSON Schema → TypeScript

- **决策**：`packages/contracts` 中的 Pydantic 模型是 formal-lab-contracts/v1 的唯一来源；`contracts/v1/*.schema.json` 与 `packages/contracts-ts` 的 TypeScript 类型均由 `make contracts` 生成，CI 与 `make phase1-check` 通过重新生成 + `git diff --exit-code` 检查漂移。
- **理由**：后端主语言为 Python，运行时校验与契约定义同源；JSON Schema 是跨语言交换格式。
- **替代方案**：手写 JSON Schema 为源（Python 侧失去类型与校验便利）；Protobuf / TypeSpec（引入额外工具链，且 JSON 负载为主）。
- **扩展影响**：扩展字段只能通过带命名空间、版本与 schema 标识的 `extensions` 槽追加，核心对象保持强类型。

## D-003 开发运行环境：Colima Ubuntu 24.04 arm64 虚拟机

- **决策**：所有构建、测试、服务运行在 Colima（Lima vz）Ubuntu 24.04 aarch64 虚拟机内执行；源码位于宿主机 home 目录并通过 virtiofs 共享；工具链由 `scripts/bootstrap-dev-vm.sh` 固定版本安装；Python 虚拟环境放在虚拟机本地磁盘（`UV_PROJECT_ENVIRONMENT`），避免宿主机与虚拟机二进制混用。
- **理由**：交付目标是 Linux；arm64 原生虚拟化性能接近宿主机，Rosetta 可运行 amd64 镜像。
- **替代方案**：直接在 macOS 开发（与 Linux 目标不一致）；x86_64 QEMU 虚拟机（实测慢约 35 倍，已弃用）。
- **扩展影响**：实际验证的 OS/架构以 `docs/execution/evidence/P1-001-environment.md` 为准；amd64 镜像构建留作发行阶段扩展。

## D-004 LLM 接入：OpenAI 兼容 Chat Completions 适配器

- **决策**：LLM 策略通过平台自有 `ModelClient` 接口调用模型；首个实现为 OpenAI 兼容 Chat Completions（`FAL_LLM_BASE_URL` / `FAL_LLM_API_KEY` / `FAL_LLM_MODEL`，当前指向用户提供的中转站，默认模型 `gpt-5.6-sol`），使用 JSON Schema 结构化输出；另有确定性替身 `StubModelClient`，其结果标注来源 `LLM_STUB` 并与真实模型结果分开统计。
- **理由**：用户指定 OpenAI 兼容中转站；自有接口让策略与具体供应商解耦。
- **替代方案**：直接依赖某家 SDK（策略代码与供应商耦合）。
- **扩展影响**：新增供应商 = 新增 `ModelClient` 实现；密钥只存在于未纳入版本控制的 `.env`。

## D-005 IR 语义细则：后写覆盖 + 后状态域守卫

- **决策**：deterministic_finite_v1 中一个动作的所有表达式在前状态求值；效果按声明顺序收集，同一位置后写覆盖先写；动作适用 ⇔ 前提成立且所有被写整数位置的后状态值在声明范围内（隐式域守卫）。枚举/实体在 Z3 中编码为 0..n−1 的 Int。
- **理由**：给出无歧义、可在解释器与 Z3 中独立实现并逐步比对的语义；域守卫让“有界整数”成为可检查的约束而非运行时错误。
- **替代方案**：写冲突即报错（需要静态冲突分析，Z3 编码复杂）；越界饱和截断（隐藏建模错误）。
- **扩展影响**：新语义（并发、概率、稠密时间）以新 profile 引入，现 profile 对其返回 UNSUPPORTED（docs/architecture/capability-matrix.md）。

## D-006 环境 = 通用 IR 世界模拟器 + 场景配置

- **决策**：主线环境 `formal-lab.env.ir-world` 以固定模型（可带 truth_constant_overrides）为真值，按场景配置施加初值覆盖、按种子扰动实例数据、延迟/隐藏观测。策略只拿到 Observation 与候选集；预期效果由平台用固定（信念）模型计算后与观测比较。
- **理由**：一个纯数据引擎覆盖四个必做场景；模型工作台编辑的就是驱动环境的模型；“预期 vs 模拟”差异来源清晰（真值覆盖）。
- **替代方案**：为调度单独手写模拟器（两套语义需要同步维护）。
- **扩展影响**：领域环境可作为新 ENVIRONMENT 插件接入；实例数据（加工时间、资源容量）建模为只读状态变量，由观测传递给策略。

## D-007 插件发现：`formal_lab.plugins` entry points + PluginRegistration

- **决策**：内置与包外插件一律通过 entry point 注册（返回 `PluginRegistration(descriptor, factory)` 列表），工厂签名 `factory(config, services)`；registry 校验契约版本与接口版本，记录描述符摘要；运行时通过 RunManifest 固定插件版本与摘要。
- **理由**：核心包不导入任何插件（P1-012）；包外插件只需依赖公开契约/SDK。
- **替代方案**：配置文件列出导入路径（易漂移，无打包元数据）。

## D-008 Z3 规划目标：有界最短计划 + 滚动时域

- **决策**：Z3 规划策略求信念状态到目标的最短动作序列（≤ horizon），执行首个动作，按信念状态摘要缓存计划后缀；无计划时按声明顺序回退并在 rationale 中说明。
- **理由**：最短步数在调度中近似最小化完工时间，求解稳定（实测 ~1 s/新计划）。
- **替代方案**：Optimize 最小化加权延误（需要“域上 max”聚合，IR 暂不提供）。实测该策略在部分场景延误成本高于规则策略，属于真实对比结果，保留。

## D-009 Z3 线程安全：每个编译模型独占一个 z3.Context，按线程缓存

- **决策**：`Z3Model` 持有私有 `z3.Context`，所有 Z3 对象显式绑定该上下文；`compile_package` 以 (模型摘要, 线程 id) 缓存。
- **理由**：Z3 上下文非线程安全。Inspect 并发样本与 Worker 线程池（最多 8 个并发活动）曾触发 Z3 断言崩溃；有并发回归测试。
- **替代方案**：全局锁（串行化所有求解，吞吐受限）；进程池（心跳与共享状态复杂）。

## D-010 TypeScript 类型取自序列化视图

- **决策**：`contracts/v1/bundle.schema.json`（校验视图）供 ajv/jsonschema 校验输入；`bundle.serialization.schema.json`（带默认值字段均为必填）生成 TS 类型，二者同源于 Pydantic。
- **理由**：Web/SDK 读取的是平台输出，默认值字段总是存在；用校验视图生成会把它们变成可选，削弱类型检查。

## D-011 S3 兼容对象存储选 SeaweedFS

- **决策**：开发与 Compose 使用 `chrislusf/seaweedfs:4.47`（`weed mini`，Apache-2.0）；平台只依赖 S3 API（boto3），Helm 指向任意外部 S3 兼容服务。
- **理由**：多架构镜像、许可宽松、单容器即可提供 S3。
- **替代方案**：MinIO（社区版发行与许可变化）；仅本地文件（不满足 S3 适配要求）。

## D-012 编排服务的部署边界

- **决策**：开发与 Compose 使用 `temporal server start-dev`（SQLite 持久卷，单节点）；Helm Chart 不部署 PostgreSQL/Temporal/对象存储，而通过现有 Secret 与地址接入外部服务。
- **理由**：本阶段交付单用户本地配置；生产级 Temporal/数据库有各自成熟的部署方式，平台不重复。
- **扩展影响**：部署能力等级在 `/api/v1/meta` 的 `capability_level` 与 docs/deployment.md 中标注。

## D-013 Web：Vite 构建的 SPA，由 Caddy 提供并反向代理 /api

- **决策**：React + React Router + TanStack Query（无 Next.js，仓库为空起步）；生产镜像 `caddy:2.11-alpine`，`/api/*` 以 `flush_interval -1` 代理以支持 SSE。开发时 Vite 在虚拟机内以轮询方式监听 virtiofs 共享的源码。
- **理由**：所有交互走同一 REST/SSE API，与 CLI/SDK 共享服务层；静态托管简单可缓存。

## D-014 本仓库许可证：Apache-2.0

- **决策**：仓库代码以 Apache License 2.0 发布（仓库所有者将选择权交给执行者）。根目录 `LICENSE`（Apache 官方全文）与 `NOTICE`；每个 Python 发行包、Helm Chart 目录各带一份相同的 `LICENSE`（PEP 639 `license = "Apache-2.0"`，文本随 wheel/sdist 分发；`tests/architecture/test_license.py` 保证副本一致）；插件描述、npm 元数据、镜像标签 `org.opencontainers.image.licenses` 与发行/离线包清单统一为 `Apache-2.0`，镜像内附 `/usr/share/doc/formal-agent-lab/{LICENSE,NOTICE}`。
- **理由**：平台以插件扩展为核心，宽松许可便于第三方插件与后续领域阶段以任意许可接入，不受 copyleft 传染；相比 MIT 多了明确的专利授权与贡献条款，适合规划/验证类技术；与全部依赖兼容（MIT、BSD-3、Apache-2.0、PostgreSQL License；psycopg 为 LGPL-3.0-only，仅以未修改的库动态使用，不影响本仓库代码的许可）。
- **扩展影响**：新包复制根 `LICENSE` 并在 pyproject 声明 `license = "Apache-2.0"`、`license-files = ["LICENSE"]`（架构测试会检查）；包外插件可自选许可，在 `PluginDescriptor.license` 中声明。

## D-015 并行发布契约 v2，冻结 v1 并提供适配器（阶段二）

- **决策**：`formal-lab-contracts/v2` 成为平台现行契约；v1 源码原样冻结在 `formal_lab_contracts.v1`，`contracts/v1/` 与 `docs/contracts/v1.md` 逐字节不变（摘要 `0cbd6256…`）。`formal_lab_contracts.compat.upgrade(kind, json)` 先按 v1 校验再映射到 v2；数据库行记录写入时的 `contract_version`，读取时升级；回放包写 `@2`、读 `@1`。
- **理由**：第二个语义驱动需要非 IR 模型载荷，新插件接口需要扩展 `PluginInterface`。v1 的 `ModelPackage.ir` 为必填、枚举封闭，v1 消费者会拒绝这些数据，无法在 v1 内兼容扩展（P2-013）。v2 保留所有 v1 对象名、字段名与语义，只新增可选字段并把 `ir` 移入类型化 `payload`（`ir` 保留为只读访问器）。v2 新增的 IR 字段在默认值时不进入规范形式，阶段一模型摘要不变。
- **替代方案**：在 v1 的 `extensions` 中塞入非 IR 载荷（语义不透明、无法校验，驱动选择无法在契约层表达）；原地修改 v1（破坏阶段一回放包与既有消费者）。
- **扩展影响**：v1 插件（interface_version 1）继续注册并收到 v2 对象；`SEMANTIC_DRIVER`、`PROBE` 仅限 v2；注册表按 semver 兼容版本解析插件，manifest 固定实际解析到的版本。

## D-016 运行内核只经语义驱动读取模型语义

- **决策**：步骤引擎不再构造 `CheckedModel`/`Interpreter`，而是按模型 profile 从注册表选择 `SEMANTIC_DRIVER`，只通过 `LoadedModel` 获取候选、预测、性质、带来源的信念与展示结构。IR 驱动在 model-core；部分状态的前提由运行的验证器在全部补全上判定（与阶段一语义一致）。
- **理由**：去掉 runtime 与 IR 的硬耦合（P2-010），第二种语义以插件接入，runtime 无需识别场景或 profile 名称（P2-012）。改造后阶段一生产调度哨兵逐格复现（规则策略所有指标一致）。

## D-017 Z3 规划可复现：每次查询新建上下文，计划记忆放入检查点

- **决策**：每次 Z3 查询使用新的 `z3.Context`；Z3 规划器的“当前计划”以 `TaskPlan` 保存在 `PlannerCheckpoint` 中，每步先从检查点恢复；进程级求解缓存只存完整查询键（模型、驱动、模式、目标/目标函数摘要、受预算约束的 horizon、信念摘要、假设集合）的确定性答案，有容量上限（LRU）。
- **理由**：实测阶段一 Z3 结果依赖同一进程内之前的运行（全局后缀缓存与复用的上下文），同一格单独运行与批量运行在 12 格中有 8 格不同（`docs/execution/evidence/phase2/z3-reproducibility.json`）。新做法下 12 格单独与批量结果完全一致，保证“同种子新进程中途恢复 = 不中断运行”（P2-046）。
- **影响**：阶段一哨兵中 Z3 策略的批量数字不可复现；阶段二以单独/批量一致的新结果为基线，规则策略全部指标与阶段一逐格相同。每次查询多出上下文创建开销（毫秒级）。

## D-018 操作协调状态机与账本

- **决策**：环境操作经 `Coordinator` 执行，状态为 `PREPARED → DISPATCHED → COMPLETED | FAILED | OUTCOME_UNKNOWN → RECONCILED`。每次状态转换先写账本，再调用环境：本地运行用内存账本，平台用 `operation_records` 表，每次提交独立事务。恢复方式由环境能力决定：`env.pure_replayable` 从步前快照精确重放；`env.query_operation` 按操作 id 向服务查询后对账，不重发；两者都没有时标记 NEEDS_REVIEW，以 `OPERATION_UNRESOLVED` 可解释地结束运行。
- **理由**：阶段一“恢复快照再 apply”只适用于纯数据模拟器；外部服务的业务状态不会随快照回滚（P2-050 … P2-054）。本地运行器与 Temporal 路径共享同一协调逻辑（P2-057）。

## D-019 数据库存原始 JSON 与写入版本，读取时升级

- **决策**：迁移 0002 为模型版本、场景、运行增加 `contract_version` 列（既有行标为 v1），不批量改写历史 JSON；所有读取经 `compat` 升级。运行新增 `carry`（轮次游标、规划器检查点、按参与者用量、规则标志），事件新增 `turn`/`stage`。同一迁移建好规则集、发布记录、查询包、回归案例、环境会话、矩阵单元与操作记录表。
- **理由**：历史运行按写入时的契约解释（P2-093 “历史运行按当时 schema 展示”）；升级在读路径集中实现、可测（`tests/compat/`），迁移可回滚。

## D-020 任务计划器维护自己的工作状态；无进展由终止策略结束

- **决策**：任务计划策略在检查点中保存“工作状态”：每个位置最新观测值（按 `observed_at_step`）叠加自己已应用动作的模型预测效果（排在应用步之后，更新的观测覆盖）。只派发在工作状态上前提成立的候选；被拒动作按其前提读取位置的最新值记忆，只有这些位置出现新观测值才重试。引擎对“同一位置、世界修订号未变”的重复观测请求拒绝服务并记录（`served: false`）；场景可设 `no_progress_limit`，连续无状态变化的轮次达到上限以 `NO_PROGRESS` 结束并写明停滞长度。
- **理由**：state-delay 下信念落后于世界，按整份观测摘要记忆拒绝会每步清空、在机器间来回试探（实测 5 个种子中规则/任务计划最长停滞 18–59 轮，`docs/execution/evidence/phase2/state-delay/report.md`）；工作状态使任务计划在延迟观测下零拒绝完成。无进展上限取在仍能成功的策略的最长停滞之上（20），只截停无望的运行。
- **影响**：检查点变大（工作状态约为状态位置数）；上限是场景配置，默认不启用，阶段一场景与结果不变。

## D-021 持久业务服务作为环境：适配器声明能力，服务端保证幂等与条件更新

- **决策**：`examples/local-order-service` 以独立进程（FastAPI + SQLite，每个会话一个租户文件）实现业务，平台只经环境适配插件访问。适配器声明持久会话、快照（会话标记）、按 id 查询、幂等步进、多参与者、服务端重置与状态导入，不声明纯重放/恢复。服务每个操作一个 `BEGIN IMMEDIATE` 事务，操作 id 为主键并在事务内检查；`REJECT_STALE` 映射为按字段变更日志的条件更新。无应答（超时、连接中断、502–504）一律作为结果未知，由协调器按 id 查询；连查询也失败时标记 NEEDS_REVIEW 并以 `OPERATION_UNRESOLVED` 结束，不猜测。运行开始时环境协商结果写明恢复路径。
- **理由**：只有服务自己能回答“这个操作是否已生效”；把保证放在服务事务里，Worker 重启、重复 Activity、进程缓存丢失和取消交错都归结为同一个按 id 对账过程（P2-050 … P2-058）。租户文件隔离使同一服务进程可同时承载多个运行。
- **影响**：服务不保证多个进程通过网络文件系统共享同一文件；恢复时间由服务启动时根据上次提交时间计算，包含停机前的空闲时间，在探针说明中写明。

## D-022 多参与者的效果差异按计划依据归因；发布按模型版本内容寻址

- **决策**：效果比较照常记录，但动作执行时的世界修订号晚于其提案所依据的修订号（另一参与者先改变了世界，常见于轮开始统一观测）时，`expected_by` 写明“计划于修订 X、执行于修订 Y”，这类差异不生成模型修订建议、回归案例，也不计入规则上下文的 `ev_different_count`。发布记录的 id 由检查内容与模型版本行共同决定。
- **理由**：陈旧依据下的差异是观测时点造成的，归咎模型会产生永远无法通过的回归案例（实测两名调度员场景产生 8 个此类案例，使任何版本都无法发布）。只按内容寻址时，另一项目中相同 IR 的发布会被错当成本版本的发布（Web 验收中复现）。
- **影响**：单参与者运行不受影响（计划与执行修订号总是相同）；阶段一哨兵结果不变。

## D-023 PRISM-games 作为可选扩展：独立进程、类型化载荷、结果与 Z3 分开

- **决策**：深化轨道选择 SELECTED，固定 PRISM-games 3.2.4（官方 linux64-arm 二进制，sha256 `366f5fed…`，GPL-2.0），配 Java 21 运行时，均由用户安装在 `~/.local/opt`（`FAL_PRISM_GAMES_HOME`）。新包 `packages/solver-adapters/prism-games`（`formal_lab_solver_prism`，只依赖 pydantic）提供：类型化模型载荷 `org.formal-lab.prism-games/allocation-game@1`（有限、轮流、完全观测、随机只在加工步）、由载荷生成的 PRISM 模型、以子进程调用二进制的适配器、以及不依赖 PRISM 的独立求解器（逐轮倒推、状态计数、策略评估）。每次查询的数值、状态数与导出策略的值都由独立求解器在模型内核对，结果类型为 `…/result@1`，在平台中以 `PROBABILISTIC` 检查单独存取、单独列出，Web 在“概率扩展”页与 Z3 结论分开呈现。
- **理由**：扩展只需要少量、可核对的概率结论，不值得把 JVM 和 GPL 代码带进平台；进程边界让许可与分发清楚（不链接、不随镜像/wheel/离线包分发，架构测试守护），也让“后端未安装”成为明确的 UNSUPPORTED 而非替代答案。用独立求解器核对，避免把一个外部数值直接当作结论。
- **影响**：概率查询只在安装了 PRISM-games 的本地环境可用；容器与 Helm 部署报告不可用及原因。适配器只生成并核对可达性查询（鲁棒与合作两种联盟）；奖励、多目标、并发博弈等 PRISM-games 支持的能力在能力表中标为本适配器 UNSUPPORTED。

## D-024 重型步骤先检查宿主机磁盘余量

- **决策**：镜像构建、kind、离线包与 Compose 冒烟在开始前调用 `scripts/disk_guard.py --need N`：经共享仓库目录（virtiofs）读取宿主机剩余空间，同时读取 VM 内 `/var/lib/docker`，不足即拒绝启动；结束后 `fstrim` 把 VM 内释放的块还给宿主机。`make phase2-check` 在每个 Docker 检查后执行同样的回收。
- **理由**：Colima 的 VM 磁盘是宿主机上的稀疏文件，只增不减。2026-09-28 宿主机磁盘写满，VM 的 Docker 数据盘写入失败、ext4 日志中止、正在构建的镜像层丢失（`e2fsck` 修复，PostgreSQL 经崩溃恢复、`pg_amcheck` 无错）。
- **影响**：余量不足时检查记录为 FAIL 并写明读数，而不是冒险运行；各步骤的需求按实测峰值加 3 GiB 余量设定。

## D-025 执行前决策作为可注入插件；操作 id 绑定请求内容；重发以后端声明为条件

- **决策**（阶段三 G2）：新增插件接口 `EXECUTION_GATE`（v2 增量）。场景声明 `execution_gates` 后，协调器在每次发送前（首次发送、结果未知且后端无记录时的重发、纯数据环境的重执行）按顺序询问门控；门控声明需要读取的位置，内核在发送前读取（能按请求观测的环境取新鲜值），门控回答 ALLOW / DENY 与条件。决定写成 `ExecutionDecision`，挂在操作记录上并发事件；DENY 时什么都不发送，操作 FAILED、动作 REJECTED。复用已记录结果与查询历史不询问门控。操作记录新增 `request_digest`（执行者、种类、动作的规范化摘要）：同 id 同请求复用结果，同 id 异参为冲突、不发送；订单服务同样以 409 拒绝。结果未知且后端查无记录时，只有环境声明 `env.idempotent_step` 才重发，否则 NEEDS_REVIEW（阶段二代码在此情形下无条件重发）。每个转换标注 `effect`（SEND / QUERY / REUSE / NONE）。
- **理由**：阶段二在检查后直接进入协调器，业务条件只能由服务在事务内拒绝，无法在执行边界按策略阻止、也不留类型化原因；按 id 复用而不比对请求内容，会把另一请求错当成已完成；无幂等声明的重发可能产生第二次副作用。放在协调器内使本地运行器与 Temporal 路径共用同一规则。
- **影响**：不声明门控的场景行为与阶段二相同（轨迹不变，单元回归与阶段一哨兵通过）；持久环境的已完成操作被再次投递时，记录多一条 `REUSE` 转换。规划器通过 `last_outcome` 看到 `EXECUTION_GATE` 拒绝，两个示例规则规划器在下一回合不再提出同一动作。证据：`scripts/operation_consistency_evidence.py`（真实订单服务进程）、`tests/integration/test_operation_consistency_platform.py`（持久路径 + Worker 被杀）。

## D-026 能力报告决定规则 / 查询 / 发布能做什么；“流程完成”与“性质成立”分开

- **决策**（阶段三 G3）：`capability_report(package, registry)` 只从驱动声明的 `driver.*` 能力与验证器对该 profile 声明的 `query.*` 能力推导每项功能（类型检查、候选 / 预测、回归重放、规则、成本目标、规模统计、五种查询）的 SUPPORTED / UNSUPPORTED、提供者与原因；发布按报告执行，缺能力的检查记为 UNSUPPORTED（executed = false）。`ReleaseConfig` 列出必需检查（默认 TYPE_CHECK；带规则集时加 RULE_CHECK，带回归案例时加 REGRESSION）与必需成立的性质；必需检查缺能力或无结论性结果 → `process_completed = false`、REJECTED；性质是否成立记在每项检查的 `property_holds` 与 `claim`（由查询种类与结论决定措辞），只有 `required_holds` 中的性质阻止发布。规模统计改用协议方法与可选的 `stats()`（`driver.stats`），不再调用未声明的 `ground_actions()`。场景带规则集而驱动未声明 `driver.ir` 时，运行在协商阶段被拒绝（阶段二会静默不执行规则）。
- **理由**：阶段二的发布依赖 IR 分支与未声明的方法，非 IR 驱动的行为只能靠猜；`ReleaseCheck.passed` 同时表示“检查未报错”和“不阻止发布”，读者容易把“发现不变量可被违反”理解为发布失败或反之。
- **影响**：已有 IR 模型的发布结论不变（新增字段带默认值，旧记录可读）；发布 id 的内容摘要包含配置。证据：`scripts/model_revision_evidence.py`（订单服务真实修订与陈旧依据分类）、`packages/runtime/tests/test_release.py`、`tests/integration/test_governance_platform.py`。

## D-027 联合批次沿用“一个成员一步”，环境每批次一步；参与者视图只约束规划器

- **决策**（阶段三 G4）：新增轮次模式 `JOINT_BATCH`（要求 `ROUND_START`）。每个成员的提案仍占一个全局步（TURN → OBSERVE → PROPOSE → CHECK），提案存入运行携带状态中的开放 `BatchRecord`；本轮最后一个成员的那一步通过 `env.batch_step`（`step_batch`）一次提交，环境只前进一步；每个成员的结果与比较记在它自己的提案步（`TurnRef.batch_id`、`env_step`）。缺席、超时、取消与门控拒绝都有确定的成员状态。批次执行（环境能力）与联合语义（驱动能力 `driver.joint_predict`）分开声明，语义一致时才按联合预测比较。参与者视图（`Participant.view`）与 `ParticipantServices` 决定规划器收到什么：视图外位置从观测中移除（信念视为从未观测），补观测请求与 `last_outcome` 的比较字段同样过滤，设置先读参与者自己的；内核的检查、预测与比较仍用完整观测。
- **理由**：保留“一个全局步 = 一个参与者回合”使阶段二的持久化、恢复、预算与事件模型不必改变——批次只是跨步的携带状态，恢复时从数据库或 JSON 状态原样继续；把批次提交放在最后一个成员的步里，环境不会看到半个批次。批次执行与联合语义分开，是因为环境能同时应用动作不代表模型给出了同时动作的含义；混为一谈会把其他成员的写入误报为模型错误。视图若只在规划器内部自觉遵守就无法验证；在内核统一过滤并记录输入摘要，恢复前后可逐步比对。
- **影响**：顺序模式的轨迹、事件与携带状态不变（仓储顺序运行与 `0ae4571` 捕获逐动作一致，单元与阶段一哨兵通过）；`CycleScheduler.advance` 接受 `progressed=None`。证据：`scripts/joint_batch_evidence.py`、`examples/warehouse-allocation/tests/test_joint_batch.py`、`packages/runtime/tests/test_participants.py`、`tests/integration/test_joint_batch_platform.py`。

## D-028 MAL 领域用隔离 venv + 类型化子进程接入；首个闭环把子集降低到确定性 IR，原生可达集为 fold 预言；三类意图分开

- **决策**（阶段三 D1）：mal-toolbox 2.11.0 / mal-simulator 3.2.1 / coreLang v1.0.0 装在独立虚拟环境（默认 `~/.venvs/fal-mal`，`FAL_MAL_HOME`/`FAL_MAL_MAR` 可覆盖），平台侧只通过类型化子进程（`packages/environment-mal/.../_worker.py`，一次 JSON 请求 / 一次响应）调用，绝不导入到冻结的平台锁里——与 PRISM 同一模式（D-023）。领域包分两个：`domain-mal`（纯：前端 `frontend.py`、降低 `lowering.py`、配置 `config.py`、平台运行 `run.py`），`environment-mal`（桥 `bridge.py`、worker、导入便捷 `importer.py`）。前端注册为 `MODEL_FRONTEND` 插件（`formal-lab.domain.mal.frontend`，源格式 `mal-attack-graph/v1`，profile `deterministic_finite_v1`），经 entry-point 组 `formal_lab.plugins` 被 registry 发现。首个闭环只取“攻击步骤攻陷”的确定性子集降低到 `deterministic_finite_v1` IR，复用 IRFiniteDriver、Z3、G3 发布检查；**原生模拟器（TTC 禁用、无 Bernoulli 抽样）的可达集是 fold 预言**——只建模目标的 or/and 祖先中原生实际到达的步骤，存在步与已禁用防御按其原生真值折叠，使 IR 闭包精确复现原生对目标的可达性。三类意图分开：LabPolicy（实验边界）、TargetSecurity（目标系统性质）、BusinessSLO（业务目标）；红方到达 TargetSecurity 的禁止步是找反例（实验成功），**不是**违反 LabPolicy。
- **理由**：MAL 的依赖（antlr、tree-sitter、pettingzoo）与平台锁冲突，隔离是为解决冲突而非许可（三个包都是 Apache-2.0）。结构化不动点会因 mal-simulator 剪枝“不必要”步骤而过近似（曾得 77 vs 原生 64），所以改以原生可达集为预言让 IR 闭包与原生一致，再由参考解释器与 Z3 独立复核（三引擎必须一致）。把 TargetSecurity 与 LabPolicy 混同会把红方的正常工作误判为违规，是 D1 明确要避免的错误。
- **影响**：新增 `packages/domain-mal`、`packages/environment-mal`（workspace 成员、根依赖、`mal` pytest 标记）。离线可运行——降低、参考解释器、Z3、ir-world 平台运行只用平台环境与提交夹具；证据脚本 `scripts/d1_mal_evidence.py` 在原生工具链缺失时回退 `import.source="fixture"`（与夹具摘要一致）。其他 MAL 语义（TTC / 随机 / 部分观测 / 数量奖励）超出该 profile，声明 UNSUPPORTED。证据：`docs/execution/evidence/phase3/d1-mal.json`、`packages/domain-mal/tests`、`packages/environment-mal/tests`；检查组 `d1-mal`。

## D-029 领域准入 Broker 作为执行门控；验证凭据只保证已检查的范围；红蓝边界在内核过滤 + 独立泄漏检查

- **决策**（阶段三 D2）：新增可复用包 `packages/domain-broker`（`VerificationReceipt` 签名凭据、类型化事件—条件—处理规则、红蓝角色边界、`Broker`），MAL 领域在 `packages/domain-mal` 绑定具体规则与签发器。**Broker 实现为 G2 的 `EXECUTION_GATE`**：只有当一份凭据签名有效、绑定到本次请求（run/step/actor/operation/动作参数摘要/session/服务身份）、检查时的状态修订等于当前修订、未过期、检查基础可授权该动作、且通过发布的领域规则时，动作才被放行；任一失败即 DENY，而门控 DENY 永不发送——**拒绝零副作用**（沿用 G2 在 local runner / Temporal / 重发 / 纯数据重执行上的保证）。签名用 stdlib `hmac`（HMAC-SHA256，FIPS-198）经 `Signer`/`Verifier` 抽象，可换非对称后端；**签名只提供来源与完整性，数学保证等于凭据记录的 check_basis / scope**，对弱检查签名不会使其变强，模型 RELEASED 标签本身不构成准入。LabPolicy、动作前提、角色规则、TargetSecurity 四类判定各自解释；未知/超时/不支持条件保留三值（None），与判定为假（False）区分，都停止动作但只有 None 触发重新观测/重规划。规则先 REVIEWED（保留自然语言 source）再 `released()` 冻结版本与内容摘要，只有 RELEASED 规则集在执行时被查询。红蓝边界用平台 `ParticipantView`（G4）过滤，另加独立 `leaks()` 检查真实交付给规划器的载荷不含标记的真值或凭据字段。
- **理由**：把准入做成执行门控而不是新拦截层，直接复用 G2 已验证的“拒绝零副作用”路径与协调、去重、恢复，不必改内核。凭据的价值在于把“检查了什么、针对哪个世界”固定下来供 Broker 核对；因此签名与保证分离，过期不阻碍查看历史来源，但新发送必须按当前修订重新出具。三值条件让“未知”可与“违规”区分，满足 D2 对未知/超时/不支持要停止并重规划的要求。签名密钥存放在与环境/服务凭据分离的 KeyStore；进程内 Python 对象**不**声称是代码沙箱，真正的进程/容器/网络隔离留给 D4。
- **影响**：新增 `packages/domain-broker`（workspace 成员、根依赖、entry-point 注册 `formal-lab.broker.receipt-gate`）；`domain-mal` 增加 `admission.py`（规则集 + 签发器 + LabPolicy/TargetSecurity 条件）、`gate.py`（`formal-lab.domain.mal.broker-gate`）、`demo.py`。签名用 stdlib，未给冻结锁新增编译依赖。证据：`docs/execution/evidence/phase3/d2-broker.json`、`packages/domain-broker/tests`、`packages/domain-mal/tests/test_admission.py`；检查组 `d2-broker`。
