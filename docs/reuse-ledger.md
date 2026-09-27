# 复用记录（Reuse Ledger）

原则：优先使用正式发布的包与稳定 API；**本阶段没有复制或 fork 任何上游源码**，下列组件均以未修改的官方发行物（PyPI wheel / npm 包 / 官方镜像 / 官方二进制）使用，版本由 `uv.lock`、`pnpm-lock.yaml`、Dockerfile/Compose 与 `scripts/bootstrap-dev-vm.sh` 固定。许可信息取自安装包元数据与上游仓库（2026-09-27 核对）。

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

## 3. 本仓库许可与兼容性

本仓库代码以 [Apache-2.0](../LICENSE) 发布（决策 D-014）。上表依赖的许可均与之兼容：MIT、BSD-3、Apache-2.0、PostgreSQL License 为宽松许可；psycopg（LGPL-3.0-only）以未修改的官方 wheel 作为库动态导入，镜像中随包保留其许可文件，本仓库不分发其修改版。发行的 wheel、sdist、镜像（`/usr/share/doc/formal-agent-lab/`）、发行目录与离线包均附带 `LICENSE` 与 `NOTICE`。
