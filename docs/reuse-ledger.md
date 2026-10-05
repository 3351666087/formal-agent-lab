# 复用记录（Reuse Ledger）

原则：优先使用正式发布的包与稳定 API；**阶段一、二均没有复制或 fork 任何上游源码**，下列组件均以未修改的官方发行物（PyPI wheel / npm 包 / 官方镜像 / 官方二进制）使用，版本由 `uv.lock`、`pnpm-lock.yaml`、Dockerfile/Compose 与 `scripts/bootstrap-dev-vm.sh` 固定。许可信息取自安装包元数据与上游仓库（2026-09-27 核对）。

## 1. 三个核心复用项

### 1.1 Z3 — 有限模型规划与性质检查

| 项 | 内容 |
|---|---|
| 来源 | https://github.com/Z3Prover/z3 ，PyPI `z3-solver` |
| 版本 / commit | `z3-solver==5.1.0.0`（uv.lock）；上游标签 `z3-5.1.0` → `0b6cdcdbc65da25ef0f73ac9da210574d0f66cf8`；Linux arm64 使用官方 `manylinux_2_38_aarch64` wheel（因此镜像基于 glibc 2.41 的 `python:3.12-slim-trixie`） |
| 许可 | MIT |
| 采用模块 | `packages/solver-adapters/z3`（`formal_lab_solver_z3`） |
| 复用方式 | 官方 Python 绑定原样使用；平台自写 IR→Z3 编译器（有界展开）、查询与规划适配层；不改求解器 |
| 修改文件 | 上游：无。本仓库：`compiler.py`、`verifier.py`、`planner.py`、`__init__.py` |
| 实际导入/调用路径 | `import z3`（`compiler.py`、`verifier.py`）；`z3.Context()`（每个模型独立上下文）、`z3.Int/Bool/IntVal/BoolVal(…, ctx)`、`z3.If/And/Or/Not/Implies/Sum`、`z3.Solver(ctx=…)`、`solver.set("timeout", ms)`、`solver.push/pop/add/check/model/reason_unknown`、`model.eval(…, model_completion=True)`、`z3.get_version_string()` |
| 验证证据 | `packages/solver-adapters/z3/tests/test_z3_engine.py`（88 项：三类查询、UNKNOWN(timeout)、UNSUPPORTED、60 个随机模型与解释器的差分对照、见证重放、多线程并发）；`docs/execution/evidence/M2-core-tests.log` |
| 升级边界 | 固定精确版本；升级需重跑差分测试与并发测试；依赖“每线程独立 Context”的线程安全前提（Z3 上下文非线程安全，见 decisions D-008 之后的并发修复） |

### 1.2 Temporal — 持久实验编排

| 项 | 内容 |
|---|---|
| 来源 | https://github.com/temporalio/sdk-python （PyPI `temporalio`）；https://github.com/temporalio/cli ；https://github.com/temporalio/temporal |
| 版本 / commit | `temporalio==1.33.0` → `ab52fdde33ee8ed193402625bfdba25d240a762d`；Temporal CLI `v1.9.1` → `1de87a9f26991bf4f5c0a5ff96f2cea8d7a3cbde`（`temporal server start-dev`，内含 Server `v1.32.0` → `d94e34a1ebba5410a2e7d07119a76896909591aa`）；镜像 `temporalio/temporal:1.9.1` |
| 许可 | MIT（SDK、CLI、Server） |
| 采用模块 | `packages/orchestrator`（工作流、活动、Worker）、`packages/platform-api/…/orchestration.py`（客户端） |
| 复用方式 | 官方 SDK 与官方服务原样使用；编排能力（持久历史、重试、取消、信号、查询、心跳、continue-as-new）全部来自 Temporal |
| 修改文件 | 上游：无。本仓库：`workflow.py`、`activities.py`、`worker.py`、`orchestration.py` |
| 实际导入/调用路径 | `from temporalio import workflow, activity`；`@workflow.defn/run/signal/query`、`workflow.execute_activity(…, retry_policy, heartbeat_timeout, cancellation_type=ActivityCancellationType.WAIT_CANCELLATION_COMPLETED)`、`workflow.wait_condition`、`workflow.continue_as_new`、`workflow.info().is_continue_as_new_suggested()`；`@activity.defn`、`activity.heartbeat()`；`temporalio.exceptions.ActivityError/ApplicationError/CancelledError`；`temporalio.common.RetryPolicy/WorkflowIDReusePolicy/WorkflowIDConflictPolicy`；`temporalio.client.Client.connect/start_workflow/get_workflow_handle().signal/cancel/describe/query`、`service_client.check_health`；`temporalio.worker.Worker(…, activity_executor=ThreadPoolExecutor)` |
| 验证证据 | `tests/integration/test_platform_runs.py`（持久化、暂停/继续、取消、SIGKILL Worker 恢复、重复提交、失败路径）；`docs/execution/evidence/M5-platform-integration.log`、`P1-123-worker-crash-recovery.md`（服务端 HEARTBEAT 超时后第 2 次尝试成功） |
| 升级边界 | SDK 与 CLI 固定版本；工作流代码只调用活动名字符串，升级需保持确定性重放；若升级 Server，Compose/Helm 需同步镜像版本并重跑集成测试 |

### 1.3 Inspect — 中性任务评测与日志

| 项 | 内容 |
|---|---|
| 来源 | https://github.com/UKGovernmentBEIS/inspect_ai ，https://inspect.aisi.org.uk/ ，PyPI `inspect-ai` |
| 版本 / commit | `inspect-ai==0.3.269` → `019e31bd6820a0eff823073b2a8bf10406827a39` |
| 许可 | MIT |
| 采用模块 | `packages/evaluation`（`inspect_adapter.py`、`inspect_import.py`）；`examples/neutral-scheduling/…/inspect_task.py` |
| 复用方式 | 复用 Task/Sample 数据集、solver + scorer 管线、指标归约（mean/stderr）、`eval` 运行器与 `.eval` 日志格式、模型提供方（`get_model`）；平台契约 RunManifest/MetricResult 保持独立，通过适配层互转 |
| 修改文件 | 上游：无。本仓库：`inspect_adapter.py`、`inspect_import.py`、`inspect_task.py` |
| 实际导入/调用路径 | `from inspect_ai import Task, task, eval`；`inspect_ai.dataset.Sample`；`inspect_ai.solver.solver, TaskState, Generate`；`inspect_ai.scorer.scorer, Score, Target, mean, stderr`；`inspect_ai.model.ModelOutput.from_content, get_model, ChatMessageSystem, ChatMessageUser, GenerateConfig, ResponseSchema`；`inspect_ai.util.JSONSchema`；`inspect_ai.log.read_eval_log, EvalLog`；CLI `inspect eval <task.py> -T … --model mockllm/model` |
| 验证证据 | `packages/evaluation/tests/test_inspect_adapter.py`（真实 inspect eval，Score↔MetricResult 逐样本对照回放包）；`tests/integration/test_sdk_cli_replay.py::test_inspect_evaluation_is_imported_and_reported`；`docs/execution/evidence/M6-eval-replay-sdk.log` |
| 升级边界 | 固定精确版本；`mockllm/model` 只是占位（规则/Z3 策略不调用模型）；升级需重跑两个 Inspect 测试，关注 Score.metadata 与样本 metadata 字段 |

## 2. 其它直接依赖

| 组件 | 版本 | 许可 | 用途 | 位置 |
|---|---|---|---|---|
| Pydantic | 2.13.5 | MIT | 契约唯一来源、JSON Schema 生成 | packages/contracts |
| FastAPI / Uvicorn | 0.141.1 / 0.54.0 | MIT / BSD-3 | REST + SSE | packages/platform-api |
| SQLAlchemy / Alembic | 2.1.1 / 1.20.0 | MIT | 持久化与迁移 | packages/platform-api |
| psycopg (binary) | 3.3.6 | LGPL-3.0-only | PostgreSQL 驱动（以未修改的库动态使用，不分发修改版） | packages/platform-api |
| httpx | 0.28.1 | BSD-3 | OpenAI 兼容模型客户端、SDK | strategies, sdk |
| boto3 | 1.43.x | Apache-2.0 | S3 兼容产物存储 | runtime |
| typer | 0.27.2 | MIT | `fal` CLI | sdk |
| jsonschema | 4.26.0 | MIT | 插件配置校验、契约测试 | platform-api, tests |
| React / React Router / TanStack Query | 19.3.0 / 8.4.0 / 5.104.0 | MIT | Web | web |
| Vite / TypeScript | 8.3.1 / 7.0.2 | MIT / Apache-2.0 | Web 构建与类型检查 | web, contracts-ts |
| json-schema-to-typescript / ajv | 16.0.0 / 8.20.0 | MIT | TS 契约生成与校验 | packages/contracts-ts |
| Playwright | 1.63.0 | Apache-2.0 | UI 浏览器测试（开发依赖） | tests/integration/test_web_ui.py |
| PostgreSQL 镜像 | postgres:16-alpine | PostgreSQL License | 数据库 | deploy/compose |
| SeaweedFS 镜像 | chrislusf/seaweedfs:4.47（`c5073360…`） | Apache-2.0 | S3 兼容对象存储（Compose / 开发） | deploy/compose |
| Caddy 镜像 | caddy:2.11-alpine | Apache-2.0 | Web 静态服务 + /api 反向代理 | deploy/docker/web.Dockerfile |
| Helm / kubeconform | 4.3.0 / 0.8.0 | Apache-2.0 | Chart lint/渲染/清单校验 | scripts/bootstrap-dev-vm.sh |
| uv / pnpm / Node | 0.12.19 / 12.6.0 / 24.21.0 | MIT/Apache-2.0 / MIT / MIT | 构建工具链 | scripts/bootstrap-dev-vm.sh |

## 2a. 阶段二新增与变化（2026-09-28 核对）

阶段二仍未复制或 fork 任何上游源码；新增用法如下，版本固定方式不变（`uv.lock`、`pnpm-lock.yaml`、Dockerfile / Compose、脚本常量）。第三方依赖的逐包许可清单由 `scripts/license_inventory.py` 生成：[licenses.md](licenses.md)。

### Z3 — 成本优化、鲁棒序列、查询包

| 项 | 内容 |
|---|---|
| 版本 | 不变：`z3-solver==5.1.0.0`，MIT |
| 新增调用位置 | `packages/solver-adapters/z3/src/formal_lab_solver_z3/optimize.py`：同一 `z3.Solver(ctx=…)` 上逐级收紧界（`solver.push()` / `solver.add(expr <= target)` / `solver.check()` / `solver.pop()`，倍增后二分），`solver.set("timeout", …)`、`solver.reason_unknown()`、`model.eval(…, model_completion=True)`；鲁棒序列在部分状态上把未知位置留为自由变量求反例。未使用 `z3.Optimize`：逐级收紧能在超时时保留已证下界 `proven_lower` 与可行解区间 |
| 修改 | 上游无；本仓库新增 `optimize.py`，`compiler.py` 每次查询新建 `z3.Context()`（决策 D-017，保证单独 / 批量运行结果一致） |
| 证据 | `packages/solver-adapters/z3/tests/test_optimize.py`（11 项：最优值与区间、超时保留可行解、见证由参考解释器重放并独立重算成本、鲁棒 / 反例）；`docs/execution/evidence/phase2/z3-reproducibility.json` |

### Temporal — 矩阵队列

| 项 | 内容 |
|---|---|
| 版本 | 不变：`temporalio==1.33.0`、CLI `v1.9.1`，MIT |
| 新增调用位置 | `packages/orchestrator/src/formal_lab_orchestrator/workflow.py` 的 `MatrixWorkflow`（`workflow.execute_activity` 调用 `matrix_claim` / `matrix_settle`，`workflow.wait_condition`、`continue_as_new`）；`packages/platform-api/src/formal_lab_api/orchestration.py::start_matrix` |
| 证据 | `tests/integration/test_matrix_v2_platform.py`（中断恢复、失败重跑、增量合并、跨矩阵复用） |

### FastAPI / Uvicorn / SQLite — 本地订单服务（业务服务样例）

| 项 | 内容 |
|---|---|
| 来源 / 版本 / 许可 | FastAPI 0.141.1（MIT）、Uvicorn 0.54.0（BSD-3）、Python 标准库 `sqlite3`（SQLite：公有领域）、httpx 0.28.1（BSD-3，适配器客户端） |
| 位置 | `examples/local-order-service/src/formal_lab_example_orders/service.py`（独立进程，不导入平台任何包——架构测试守护）、`env.py`（环境适配器，经 HTTP 访问）、`lifecycle.py`（进程 / Compose 生命周期） |
| 复用方式 | 原样使用；`BEGIN IMMEDIATE` 事务内按操作 id 主键去重、按字段变更日志做条件更新（决策 D-021） |
| 证据 | `examples/local-order-service/tests/test_order_service.py`、`tests/integration/test_order_service_platform.py`、`docs/execution/evidence/phase2/orders/` |

### PRISM-games — 可选深化轨道（SELECTED）

| 项 | 内容 |
|---|---|
| 来源 | https://github.com/prismmodelchecker/prism-games ，https://www.prismmodelchecker.org/games/ |
| 版本 | 3.2.4 官方二进制 `prism-games-3.2.4-linux64-arm.tar.gz`（sha256 `366f5fedf6d8be8b089372f64714edebda3fab26001bf38323905b8fcb62ce52`）；Java 运行时 Eclipse Temurin JRE 21.0.12+1（aarch64，`jre21-aarch64.tar.gz` sha256 `14be1f35…`） |
| 许可 | PRISM-games：GPL-2.0；Temurin：GPL-2.0 with Classpath Exception |
| 分发安排 | **不分发**：不进入 wheel、镜像、离线包；用户自行安装到 `~/.local/opt`，适配器以独立进程调用二进制，只写输入文件、读输出文件，不链接、不导入（`tests/architecture/test_boundaries.py::test_prism_games_runs_only_as_a_separate_process`） |
| 采用模块 | `packages/solver-adapters/prism-games`（`formal_lab_solver_prism`，Apache-2.0，只依赖 pydantic）；`packages/platform-api/src/formal_lab_api/services/probabilistic.py`；`web/src/components/ProbabilisticPanel.tsx` |
| 实际调用 | `bin/prism model.prism props.props -prop 1 -exportstrat strat.txt -exportmodel model.all`、`-prop 2`、`bin/prism -version`；解析 `Result:`、`States/Transitions/Choices`、`model.sta` 与 `strat.txt` |
| 修改 | 上游无（官方 `install.sh` 只改写启动脚本中的安装路径） |
| 证据 | `docs/execution/evidence/phase2/prism-games/`（原始模型、性质、两次调用日志、导出策略与显式模型、`result.json`、`summary.json`）；`packages/solver-adapters/prism-games/tests/test_prism_games.py`；`tests/integration/test_probabilistic_platform.py` |
| 升级边界 | 固定版本与校验和；升级需重跑 `make prism-games-check`（数值与独立求解器一致、状态数一致、导出策略的值一致） |

### 其它阶段二用法

| 组件 | 版本 | 许可 | 用途 | 位置 |
|---|---|---|---|---|
| React `lazy` / `Suspense` | 19.3.0 | MIT | 路由分块 | web/src/main.tsx |
| kind / kindest/node | v0.33.0 / v1.37.0（`a1ed56cf…`） | Apache-2.0 | 单节点 Chart 安装、升级与回滚检查 | scripts/helm-install-check.sh、helm-upgrade-check.sh |
| Helm | 4.3.0 | Apache-2.0 | Chart 0.2.0 安装 / 升级 / 回滚 | 同上 |
| PostgreSQL 客户端工具 | 16（fal-dev 容器内 `pg_dump` / `psql`） | PostgreSQL License | 本地备份 / 恢复 / 重置 | scripts/local_data.py |

## 3. 本仓库许可与兼容性

本仓库代码以 [Apache-2.0](../LICENSE) 发布（决策 D-014）。上表依赖的许可均与之兼容：MIT、BSD-3、Apache-2.0、PostgreSQL License 为宽松许可；psycopg（LGPL-3.0-only）以未修改的官方 wheel 作为库动态导入，镜像中随包保留其许可文件，本仓库不分发其修改版。发行的 wheel、sdist、镜像（`/usr/share/doc/formal-agent-lab/`）、发行目录与离线包均附带 `LICENSE` 与 `NOTICE`。

## 4. 阶段三（Phase 3B）领域集成复用

领域集成引入的上游与方法。沿用 D-023 的原则：有依赖冲突或非宽松分发的第三方运行时**不进入** wheel / 镜像 / 离线包，而是作为外部前提装在独立虚拟环境，经类型化子进程调用（只写输入、读输出，不链接、不导入冻结平台环境）。

### 直接接入的上游工具（外部前提，不分发）

| 组件 | 版本 / 固定点 | 许可 | 用途 | 隔离与位置 |
|---|---|---|---|---|
| coreLang | v1.0.0 | Apache-2.0 | MAL 攻击语言，编译为 `corelang-1.0.0.mar`（sha256 `9aabc828…`，19 资产） | 独立 venv `~/.venvs/fal-mal`；经 `packages/environment-mal` 子进程调用（D-028） |
| mal-toolbox | 2.11.0 | Apache-2.0 | 加载模型、构建攻击图 | 同上 |
| mal-simulator | 3.2.1 | Apache-2.0 | 原生攻击步骤模拟（TTC 禁用、无 Bernoulli）作为降低的 fold 预言 | 同上 |
| CAGE Challenge 4 / CybORG | 4.0（git `8c3c50ca`） | MIT（Commonwealth of Australia 2019；未修改、不分发） | 官方 Scenario4 脚本基线（蓝/绿/红） | 独立 venv `~/.venvs/fal-cage`，仅装核心依赖（无 torch/ray）；经 `packages/environment-cage` 子进程调用（D-032） |

### 方法参考（仅概念，未采用其代码）

下列工作在任务书中列为方法复用来源；本轮**只借鉴其概念并自行实现**，未 vendoring 或链接其代码，因此不涉及其许可分发。实现位置见各决策。

| 方法 | 概念 | 本轮自实现位置 |
|---|---|---|
| Shielding（AAAI'18） | 执行前筛选（动作在生效前被屏蔽器裁决） | Broker 作为 G2 `EXECUTION_GATE`（D-029） |
| AgentSpec | 事件—条件—处理规则 | `formal_lab_domain_broker.rules`（类型化 ECA，审查→发布）（D-029） |
| Progent | 动作参数约束 | 凭据绑定动作参数摘要 + 角色/LabPolicy 条件（D-029） |
| VeriGuard | 发布检查与在线监测分离 | G3 发布能力（RELEASED）与 Broker 在线准入分离；凭据只保证已检查范围（D-029） |
| ARTEMIS | 任务监督与独立复核 | 裁判以环境状态/探针判定，Agent 自述仅解释（D-030/D-031） |
| Dynamic Cyber Ranges | 动态对手、持续业务、恢复指标 | D4 探针（成功率/恢复）、D5 成对评测与 LabPolicy 消融保留（D-031/D-032） |

### 平台内部复用

领域包只经 G1—G6 的公开接口接入：`MODEL_FRONTEND`（MAL 攻击图→确定性 IR）、`SEMANTIC_DRIVER`/`PLANNER`/`VERIFIER`（复用 IRFiniteDriver、z3-bounded、z3-bmc）、`EXECUTION_GATE`（Broker）、`PROBE`、`SessionEnvironment`（订单服务生命周期）、`ScenarioManifest`/`run_local`/`QueryBundle`。签名用 stdlib `hmac`（HMAC-SHA256，FIPS-198），未给冻结锁新增编译依赖。

## 5. 阶段四（Phase 4B）复用

- **无新增第三方代码或依赖**：`uv.lock` 的变化只有工作区内部依赖（`formal-lab-domain-mal` 依赖 `formal-lab-strategies`、`formal-lab-solver-z3`）与 0.4.0 版本号。
- **CybORG 4.0**（git `8c3c50ca`，MIT，未修改、不分发）：从 D5 的脚本基线扩展为平台环境 `formal-lab.env.cage4`，仍经独立 venv `~/.venvs/fal-cage` 的类型化子进程调用（`packages/environment-cage/src/formal_lab_env_cage/_worker.py`）。
- **模型端点**：沿用 A3 的 `formal_lab_strategies.decision` 与 OpenAI 兼容客户端；端点地址与密钥只在 git 忽略的 `.env`。
- **平台内部复用**：B3 的发行检查沿用 `scripts/release.py` 与 A5 的安装 / 回放流程；本地交付名映射到 `scripts/doctor.py` 已有配置（`DELIVERY`）。
