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
