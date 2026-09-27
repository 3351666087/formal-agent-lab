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
