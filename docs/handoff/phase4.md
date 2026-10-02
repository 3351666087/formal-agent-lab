# 阶段四交接（Phase 4：平台修复与可验证交接 + 领域收口）

任务书：[docs/execution/phase-4a.md](../execution/phase-4a.md)（原文 `04A_opus5_5_platform_closure.md`，2026-10-02，A1—A5，开发执行者 Opus 5.5）；B1—B3 由 `04B_opus4_8_domain_closure.md` 交接。本文件是阶段四唯一的交接记录：每个交付包完成时追加证据，最终补齐 [phase4.manifest.json](phase4.manifest.json) 与 [phase4-checks.json](phase4-checks.json)。整体 Phase 4 的完成标记留给 B3。阶段二（`4e1f959`）、阶段三（`67e1b82`，0.3.0 发布 `9203691`）的交接是历史证据。

## 接手核对（2026-10-02）

| 项 | 结果 |
|---|---|
| 基线 | HEAD = `bccda301e58905ee0b0f37b2be9ed2938064d726` = 核对基线，工作区干净，与 origin/main 一致；仓库无 AGENTS.md |
| doctor | Ubuntu 24.04.4 aarch64，4 vCPU，5910 MiB；Postgres / Temporal / S3 已起，API / Web 开发栈未起；LLM 已配置；java 缺失（PRISM 不涉及）（`docs/execution/evidence/phase4/doctor-takeover.json`） |
| 磁盘 | 接手时宿主盘仅 8.5 GiB（0.3.0 镜像构建撑大了 VM 稀疏盘）。经用户授权清理垃圾：VM 内 BuildKit 缓存 4.3 GB、未被引用的阶段二 `formal-agent-lab/*:4e1f959e81f2` 镜像、pip/uv 缓存，随后在 VM 内 fstrim 归还 13.7 GiB；宿主 uv 缓存 954 MB、npm 缓存、brew 旧版本、一个过期的 Codex 临时安装目录。宿主盘 8.5 → 18 GiB。保留：开发栈卷与服务镜像、当前项目镜像、kindest/node、VM 内 Playwright 浏览器、其它应用的活动运行时；废纸篓未动（本就为空）；未做任何宽泛 prune |

## 4A 交接总览

STATUS_TABLE

**命令**

```bash
make phase4-check ARGS="--group a1,a2,a3,a4,a5"   # 4A 平台包（VM 内：scripts/in-vm.sh 'make …'）
make phase4-check                                 # 全部组；b1—b3 未登记前整体保持未完成
make acceptance-local                             # 严格总验收（阶段二必做回归 + 阶段三适用回归 + 阶段四），B3 最终汇总
uv run --frozen python scripts/handoff_phase4.py  # 由本次检查结果生成 phase4.manifest.json / phase4-checks.json / openapi
```

**真实模型与测试服务**：`p4-a3-real-endpoint` 使用已配置的 OpenAI 兼容中转（`https://api.uheapi.com/v1`，`gpt-5.6-sol`；凭据只在 git 忽略的 `.env`，证据中不含），结果标 `LLM`（应答端点 PROVIDER）。`formal_lab_strategies.protocol_server` 是回环上的协议测试服务，**不是模型**，结果标 `LLM_PROTOCOL_TEST`；确定性替身标 `LLM_STUB`。A2 的参与者投影与 A3 的协议测试均使用协议测试服务；只有 `a3-real-endpoint.json` 是真实提供方运行。开发执行者是 Opus 5.5，与实验中被调用的模型无关。

**接口位置（供 B1—B3 接入）**

| 主题 | 位置 |
|---|---|
| 执行依据 / 绑定 / 原子性边界 | `formal_lab_contracts.ExecutionContext`、`execution_binding()`；内核 `engine._send_hook` + `execution_context.py`；条件写 = `env.current_revision` + `env.conditional_step`（订单服务在写入事务内核对）；门控读 `GateRequest.execution`；签发 `ReceiptIssuerGate`、准入 `admit_execution`；范围见 [assurance-scope.md §6](../assurance-scope.md) |
| 参与者投影与凭据分配 | `formal_lab_runtime.participants`（`Projection`、`participant_bundle`、`ParticipantServices.get_setting` 拒绝凭据类键）；参与者 API `/participant/whoami`、`/participant/export`，令牌由 `POST /runs/{id}/participants/{actor}/access` 签发；环境写凭据只在 0600 文件中由适配器读取 |
| 模型客户端与计划接口 | `formal_lab_strategies.decision`（`DecisionRequest` / `ModelDecider` / `Decision`，内置 `choose_request` / `order_request`）、`client_from_settings`；来源由应答端点决定，`ProposalSource.decided_by`、`PlanGenerator.model_call_ids`；预算 `max_model_calls` / `max_model_attempts` |
| 联合轮次 / 环境适配入口 | 轮次结局（PASSED / 退场 / 运行结束）、`WORLD_STEPPED`、`BatchRecord.world_step` / `automatic`、`env.world_step_report`；子进程环境范例 `examples/subprocess-env`；SDK 合同检查 `formal_lab_sdk.plugin_testing.check_environment` |
| 矩阵复用键与评分接口 | 复用键 v3（`services/matrices.py expand_v2`：划分、内核版本、模型端点；版本未知 → RERUN）；报告 `formal_lab_eval.experiments.build_report`（固定分母成功率、不完整配对原因、工程读数）；指标 `MetricDefinition.observable` / `window` |
| 产品与发行入口 | Web / API / CLI `fal` / SDK `formal_lab_sdk.Client`；发行 `scripts/release.py`（wheel、Web、本地运行配置、清单）、`scripts/offline_bundle.py`（镜像离线包，磁盘允许时）；`scripts/a5_release_evidence.py` |
| 阻塞 | 镜像离线包（宿主磁盘：需 8 GiB + 15 GiB 保留量）；参与者多用户登录属部署范围；订单服务读接口回环不鉴权（部署条件）。真实端点与 Figma 本次可用、已实际使用 |
| B1—B3 待注册位置 | `scripts/phase4_domain_checks.py`（只允许 b1—b3 组；未登记时为 `NO_CHECKS`，整体保持未完成）；证据脚本用 `scripts/check_result.py` 上报 |

整体 Phase 4 的完成标记留给 B3。

## A1 · 检查器与验收状态

**复现的缺口**（基线 `bccda301`）：
- `run_attempt` 只以退出码判定 PASS——D5 证据脚本在 CAGE 缺失时写 `status: BLOCKED` 却退出 0，被记为 PASS；
- 声明的证据文件从不检查存在、新鲜或内容：磁盘上的旧文件可以“替”失败的运行作证；
- 组状态混入早先调用的结果（同一工作树上只重跑一个检查，其它组仍按旧 PASS 计入 `mandatory_passed`）；
- 条件项没有固定触发条件；
- `acceptance_local.py` 在 `complete=false` 时仍返回 0，且直接读取磁盘上的报告（子进程崩溃时会采纳旧报告）。

**修复**（状态协议见 [check-protocol.md](../execution/check-protocol.md)）：
- `scripts/check_runner.py`（报告 `checks@3`，兼容 `checks@2` 的键）：每次 attempt 一次性 nonce 与 `FAL_CHECK_RESULT`；`decide()` 按“超时 → 带 nonce 的 BLOCKED/NOT_RUN → 退出码 → 结构化结果（过期/格式/缺失/必需断言）→ `produces` 证据（缺失/旧文件/格式/记录的状态/`assertions_from` 布尔）→ pytest 0 通过（跳过 = BLOCKED）”判定；只在 FAIL 时重试；条件项按 `trigger` 探针在执行前定适用性（`NOT_APPLICABLE` 或按必做计）；组状态与汇总只计本次调用；`complete`（= `mandatory_passed`）需完整运行且每个必需组 PASS，部分运行只给 `selection_status`；必需组无检查为 `NO_CHECKS`；`--strict`；拒绝把可执行代码排除出工作树摘要（退出 2）；每个结果带原因、attempt、日志、结构化结果位置、证据摘要。
- `scripts/check_result.py`：证据脚本上报接口（`fal-check-result@1`，仅标准库；PASS 0 / FAIL 1 / BLOCKED 3）。
- `scripts/acceptance_local.py`（`acceptance@2`）：依次运行 phase2 / phase3 / phase4，每个套件带一次性 `FAL_ACCEPTANCE_NONCE` 写入 `out/acceptance/<suite>/`；裁决 COMPLETE / INCOMPLETE / PARTIAL / REPORT_MISSING / STALE_REPORT / MALFORMED_REPORT / RUNNER_CRASHED；严格模式非 complete 退出 1；复跑的阶段二 / 三证据写入 `docs/execution/evidence/phase4/regression/<suite>/`，历史记录不被覆盖（`scripts/phase3_check.py` 的 EV 随 `FAL_EVIDENCE_DIR`）。
- `scripts/phase4_check.py`：组固定 `a1`—`a5`、`b1`—`b3`；`scripts/phase4_domain_checks.py` 是 B1—B3 的登记点（只允许 b 组，未登记时为 `NO_CHECKS`，整体保持未完成）。`make phase4-check`。
- 阶段三 D1—D6 证据检查改为 `produces` + `assertions_from="conclusion"`：在临时证据目录复跑 11 项全部 PASS；把 `FAL_CAGE_HOME` 指向不存在的路径时，真实 D5 脚本（退出 0、记 BLOCKED）现在被判为 **BLOCKED**（原先为 PASS）。

**验证**：`tests/tools` 35 项（新增 `test_check_status.py` 27、`test_acceptance_local.py` 6，原 `test_check_runner.py` 2 项不变）；`make phase4-check ARGS="--group a1"`：`p4-a1-engine`、`p4-a1-fault-injection`（对真实引擎注入八种情形，8/8 必需断言成立，证据 `docs/execution/evidence/phase4/a1-status-protocol.json`）PASS，部分运行 `complete=false`；`acceptance_local.py --suites phase4 --group a1` 退出 1，裁决 PARTIAL，`unmet` 列出 a2—a5、b1—b3 的 `NO_CHECKS`。

**留给后续执行者**：阶段三其余 G 组证据脚本仍以退出码 + 引用文件为准，未改为结构化上报；B1—B3 负责把所属领域脚本的真实业务断言接到 `CheckResult`。

## A2 · 当前状态、执行绑定与参与者输入

**复现的缺口**（按基线 `bccda301` 的代码路径逐条核对；新的证据脚本依赖本包新增的接口，不能在基线上原样运行）：
- 门控从 `GateRequest` 的 `values_revision` / `based_on_revision` 取版本——没有声明观测路径的门控（D2 Broker）实际拿到的是**提案**版本：订单服务已到 7 时，按 5 签发的凭据照样放行；
- 凭据绑定由各门控自行拼装（策略给的字符串、`service_identity` 配置值），签发与校验没有共同定义；session、turn、环境版本、视图/规则版本都不在绑定内；
- 检查与写入之间没有任何保护：检查通过后另一写入者落地，写入照常生效；读不到当前版本时照样发送；
- 订单服务的写接口不鉴权，回环上任何进程都能写；
- 参与者视图只过滤观测与 `last_outcome` 的字段差异：`last_outcome` 的结果、冲突路径、错误文本照原样给规划器；平台没有参与者下载通道（只有运营方导出）；`get_setting` 会把环境写凭据路径交给规划器；
- 模型调用记录不标参与者，无法按参与者检查投影。

**修复**：
- 契约（v2，增量可选字段，v1 不变）：`ExecutionContext`、`execution_binding()` / `execution_binding_digest()`（唯一规范化定义）、`params_digest()`；`GateRequest.execution`、`ExecutionDecision.execution`；能力 `env.current_revision`、`env.conditional_step`。v2 摘要 `b0a5836e913a`，生成物与 TS 类型已同步。
- 内核（`execution_context.py`、`engine._send_hook`、`coordination._send`）：每次首发 / 重发 / 纯数据重放前构造执行依据——身份取自内核 turn，当前版本来自环境权威读取（FRESH / SERIALIZED / UNKNOWN），提案版本另存；提案身份不符 `IDENTITY_MISMATCH`，条件写环境读不到版本 `BASIS_UNKNOWN`，均为内核自身的 `ExecutionDecision`（`formal-lab.kernel.execution-basis`），不发送；条件写环境随发送带 `expected_revision`。模型调用记录带 `actor_id` / `step`。
- Broker：`admit_execution()` 按 `BINDING_FIELDS` 逐字段比对、当前版本必须等于凭据检查时版本、必需绑定缺失即拒绝；新增 `ReceiptIssuerGate`（`formal-lab.broker.receipt-issuer`）在发送前按当时的执行依据签发；MAL 门控同样走 `admit_execution`；D2 演示改为发送时签发。
- 订单服务：`--write-token-file`（`ORDERS_WRITE_TOKEN_FILE`）后所有写路由需 `Authorization: Bearer`，否则 401 且不记录；`expected_revision` 在写入事务内核对（`version_policy` EXACT / LOCATIONS），不符记 REJECTED、零业务写入；生命周期 `secure_writes=True` 生成 0600 凭据文件，清单只含路径；适配器声明两项新能力。
- 参与者边界：`Projection` 一条规则作用于任意载荷（位置键、带 `path` 的条目、路径列表、自由文本中的位置及其值）；`last_outcome` 整体投影；`get_setting` 拒绝凭据类键并记录；`participant_bundle()` 生成参与者下载（本人与运行级事件、重新编号并只保留可见的因果父事件、环境/门控配置及地址与路径清除、其他参与者配置与视图清除、不含指标与制品），仍是同一离线读取器可读的合法包。平台 API：`POST /api/v1/runs/{run_id}/participants/{actor_id}/access`（运营方签发 HMAC 令牌，绑定 run + actor，可设有效期）、`GET /api/v1/participant/whoami`、`GET /api/v1/participant/export`（身份只取自令牌，`actor` 参数越权 403；无 / 伪造 / 过期令牌 401）。
- 协议测试服务 `formal_lab_strategies.protocol_server`：回环上的 OpenAI 兼容 Chat Completions 端点，记录每个请求体（Authorization 只记是否存在与摘要），按载荷返回合法选择，模型名 `protocol-test-v1`，**不是模型**；可脚本化 429 / 500 / 非 JSON / 违反 schema / 越界 / 无 usage / 挂起。A3 复用。
- 保证范围写入 [assurance-scope.md §6](../assurance-scope.md)：进程内插件受信但不是沙箱；写边界由服务进程强制；订单服务读接口在回环上不鉴权，“对同机进程保密”是部署条件。

**必须复现**（`scripts/a2_execution_evidence.py` → `docs/execution/evidence/phase4/a2-execution-basis.json`，真实订单服务进程、真实内核发送路径，写计数取自服务 `/admin/export`）：

| 情形 | 结果 |
|---|---|
| 服务 7、提案与凭据 5 | Broker DENY（“receipt checked at revision 5, the environment is at 7 (FRESH)”），该参与者在服务上的操作 0 条，版本仍为 7 |
| 检查通过后另一写入者落地 | 两个门控 ALLOW；服务在写入事务内拒绝（`STALE_REVISION: verified at revision 0, the service is at 1`），记录 REJECTED，前后版本相同，业务写入 0 |
| 合法同版本动作 | 签发 → 准入 → 写入 1 次，服务记录的 `revision_before` = 检查时版本 |
| 同 ID 同请求 / 异参 | 服务返回既有结果（`replayed`）；异参 409 → `Conflict`；内核同 ID 异请求 → 冲突不发送 |
| 环境 / session / turn / 版本 / 服务身份 / 版本号错配 | 6 种全部拒绝，各自的原因指名该字段；提案冒充 actor → `IDENTITY_MISMATCH`；版本读取失败（注入）→ `BASIS_UNKNOWN`；服务上该参与者写入 0 |
| 恢复与重发 | 首发在提交前丢失、期间状态 0→2：旧凭据重发 DENY、写入 0；发送时重新签发 → 在版本 2 写入 1 次；第二个 worker 共用账本 → 复用、不再写；停止于第 3 步再以新组件续跑，25 次发送全部 FRESH 且等于服务记录的 `revision_before` |
| 真实策略工厂 + 实际序列化 / 下载 | 两名 LLM 参与者经真实工厂、真实 OpenAI 兼容客户端与协议测试服务运行（订单服务，`stock` 对 A 隐藏）：A 的 13 个请求体、调用记录、检查点中无 `stock[…]`，B（未过滤，对照）的请求中有；写凭据与测试模型密钥不在任何请求体、调用记录、运营方导出、参与者下载中；A 的下载无 `stock[…]`、无服务地址与凭据路径、无 B 的事件与配置，`fal replay verify` 离线读取 OK；`ORDERS_WRITE_TOKEN_FILE` 等对参与者返回空 |
| 凭据分发 / 端口 / 写拒绝 | 凭据文件 0600，服务 argv 只有路径；无凭据或错凭据写入 401、admin/reset 401，且服务不记录；服务只监听 127.0.0.1，从 VM 的非回环地址连接被拒 |
| 仓储（纯数据，收货员 + 拣货员带视图，容量门控） | 轮流与联合批次两种：每次发送的依据均为 SERIALIZED 且带当前版本；拣货员下载无 `dock[…]`、无收货员事件（运营方导出有） |

**验证**：`p4-a2-kernel`（运行时执行依据 13、投影 4、原参与者 / 一致性测试、Broker 含新增执行准入 18、契约）、`p4-a2-order-service`（真实服务进程 5 + 原订单服务测试）、`p4-a2-evidence`（22/22 必需断言）、`p4-a2-participant-api`（真实 API + worker：签发、whoami、401 / 403、投影下载离线可读）。受影响套件：运行时 / 领域 / 策略 / 评测 / 契约 / 兼容 / 架构 / 工具 / 示例 456 项通过；集成（订单服务、一致性、治理、多参与者、参与者通道、SDK/CLI/回放，真实 PostgreSQL + Temporal + API / worker 子进程）18 项通过。

**留给后续执行者**：订单服务之外的实时环境若要关闭检查—写入窗口，需实现 `env.current_revision` + `env.conditional_step`；其它门控若需要版本，应读 `GateRequest.execution` 并在 UNKNOWN 时拒绝。多用户登录（SSO）仍属部署范围，参与者令牌是本地单用户运营方签发的读取凭据。

## A3 · 模型调用与可恢复决策

**复现的缺口**（按基线代码路径核对）：
- 来源由配置字符串决定：任务规划器 `kind = "LLM_STUB" if client == "stub" else "LLM"`——模型不可达、采用规则顺序时计划仍标 LLM；协议测试服务、真实提供方无从区分；
- 继承已生成计划的后续步 `model_call_ids` 为空，无法追溯到生成计划的调用；
- 预算只计可用应答（`model_calls`）：端点不可达时每一步都会再发请求并回退，预算永远不耗尽；重试次数不受预算约束；
- 4xx 拒绝记为传输错误；未报告用量的调用记 0 token（看起来免费）；调用记录无提示/配置摘要、无应答端点类型；
- 每个策略各写一套客户端调用、失败处理与记账，没有复用点；替身调用 ID 随机，带调用 ID 的计划检查点在续跑后不一致。

**修复**：
- 复用接口 `formal_lab_strategies.decision`：`DecisionRequest`（任务、系统提示、载荷、响应 schema、业务校验、提示版本）→ `ModelDecider.decide(request, context=PlanningContext)` → `Decision`（内容、来源、模型、调用记录、用量、失败分类）→ `decision.proposal(...)` / `decision.source_of(...)`；内置 `choose_request`（选一个候选）与 `order_request`（依赖一致的任务排列）。LLM 策略与调度任务规划器都改走它。
- 来源取自应答：客户端记录应答端点类型 PROVIDER / PROTOCOL_TEST（协议测试服务以 `x-formal-lab-endpoint: protocol-test` 自报）/ STUB，对应来源 `LLM` / `LLM_PROTOCOL_TEST` / `LLM_STUB`；`ProposalSource.decided_by` = MODEL_RESPONSE（本步应答）/ INHERITED_PLAN（引用生成计划的调用）/ RULE_FALLBACK（失败调用 ID 保留）；`PlanGenerator.model_call_ids` 记录生成该计划版本的调用。契约 v2 增量：`ProposalSourceKind.LLM_PROTOCOL_TEST`、`ProposalSource.decided_by`、`PlanGenerator.model_call_ids`、`Budget.max_model_attempts`（v1 不变）。
- 调用记录：call ID、请求 / 返回模型、`model_switched`、尝试次数、`sent`、状态、端点类型、去凭据端点（无 user-info / query）、提示摘要、配置摘要、业务校验结果、用量是否提供（未提供 → token 为 null）、耗时、HTTP 状态。失败分类 TRANSPORT_ERROR / FORMAT_ERROR / BUSINESS_INVALID / PROVIDER_REJECTED / CANCELLED / BUDGET_EXHAUSTED 分开。
- 预算：每次调用前按运行与参与者两级的 `max_model_calls` 与 `max_model_attempts`（含重试、失败与回退前的尝试）检查，耗尽则不发送、记 BUDGET_EXHAUSTED；单次调用的重试数截到剩余尝试数；内核在 `model_attempts` 达上限时结束运行。替身调用 ID 由提示摘要决定（确定性）。
- 评测：发生过模型尝试（即使全部失败回退）的运行，`model_calls` / `tokens` 指标不再标“不调用模型”。Web 来源徽标与基准页提示加入“协议测试服务”。

**领域策略需要传入的字段及其来源**：

| 字段 | 来源 |
|---|---|
| `options`（候选 / 任务） | 内核给出的 `PlanningContext.candidates`（已在参与者投影后的信念上计算），或策略自己的任务分解；只提供允许的项 |
| `goal` / 目标说明 | `PlanningContext.goal`、`objective`，由策略渲染 |
| `explanation`（需要模型考虑的事实） | `PlanningContext.observation`（已按视图投影）中策略选取的部分 |
| 响应 schema 与 `validate` | 策略：`choose` / `order` 内置，其它任务自带 JSON Schema 与业务校验 |
| 提示版本 | 策略版本（进入 `prompt_digest`） |
| 客户端 | `client_from_settings(config, services)`：`FAL_LLM_BASE_URL` / `FAL_LLM_API_KEY` / `FAL_LLM_MODEL`（参与者设置优先，再平台设置 / `.env`）；`client: stub` 为替身 |
| 预算 | 内核：`PlanningContext.budget` / `usage`、`actor_budget` / `actor_usage` |

**必须复现**（`scripts/a3_model_decision_evidence.py` → `a3-model-decision.json`；真实提供方单独 `--real` → `a3-real-endpoint.json`）：

| 情形 | 结果 |
|---|---|
| 测试服务返回不同合法候选 | 同一场景 `pick:0` → `assign(o1_cut, m1)`，`pick:1` → `assign(o1_cut, m2)`；来源 LLM_PROTOCOL_TEST / MODEL_RESPONSE，引用的调用 ID 都是服务实际应答 |
| 无效选择 | 越界两次 → 规则回退（RULE / RULE_FALLBACK，保留 2 个失败调用 ID）；`on_model_failure: fail` → 运行 FAILED，原因 `BUSINESS_INVALID: index 10000 out of range 0..36` |
| 不可达端点 | 关闭端口：TRANSPORT_ERROR 记录（2 次尝试、“Connection refused”、token 为 null），`model_calls` 0、`model_attempts` > 0，所有步骤 RULE_FALLBACK，无一标为模型决策 |
| 替身 | 所有步骤 LLM_STUB，端点类型 STUB |
| 暂停 / 恢复 | 本地：第 4 步停、经 JSON 在新组件中续跑，12 个请求 = 12 个已提交调用 ID，无重复；平台（Temporal + PostgreSQL）：暂停期间无请求，恢复后 SIGKILL worker，已提交调用 ID 无重复且都是服务实际应答，在途丢失 ≤ 1（`tests/integration/test_llm_decision_platform.py`） |
| 预算 | `max_model_calls=3` → 服务恰好收到 3 个请求，运行 BUDGET_EXHAUSTED；全部 500 且 `max_model_attempts=4` → 恰好 4 个请求 |
| 复用 | 调度任务规划器（generator=model）走同一决策：15 步只需 1 次调用，继承步骤引用生成计划的调用 ID（INHERITED_PLAN） |
| 真实端点最小例子 | 已配置的 OpenAI 兼容中转（`https://api.uheapi.com/v1`，`gpt-5.6-sol`）：正常调度场景任务规划器 SUCCEEDED，15 步、1 次真实调用（PROVIDER，返回模型 `gpt-5.6-sol`，提供方报告 429 / 528 token，约 38 s），来源 LLM（MODEL_RESPONSE + INHERITED_PLAN）；订单正常场景 LLM 策略 6 次真实调用（逐调用 OK / VALID，HTTP 200，用量已报告）后按 6 次预算 BUDGET_EXHAUSTED。同日较早一次运行中订单场景有 1 次调用未得到可用应答，当时证据未记录其分类，此后证据逐调用记录结果。证据文件不含任何凭据（已逐文件核对） |

**真实调用状态**：本环境端点可用，`p4-a3-real-endpoint` 为真实提供方运行；端点不可用时该检查记 BLOCKED，协议测试服务不充当真实模型。研究比较是否可完成由 B3 依据真实模型运行证据判断。

**验证**：`p4-a3-unit`（策略 / 决策 / 调度任务规划器 / 评测 37 项）、`p4-a3-decision`（9/9 必需断言）、`p4-a3-platform`（Temporal + PostgreSQL 暂停 / 恢复 / SIGKILL worker）、`p4-a3-real-endpoint`（真实提供方 3/3）全部 PASS；受影响套件 403 项、集成（平台运行、矩阵 v2、模型决策）15 项通过；web `tsc --noEmit` 通过。

## A4 · 联合轮次与配对评测

**复现的缺口**（按基线代码路径核对，并用仓储场景实测）：
- 现有仓储场景两角色都能 `tick`，任何一轮都不会出现“某参与者暂时无动作”，空闲跳过从未被真实覆盖；
- 联合批次只记录 `env_step`（快照步数），环境自己的世界步编号与环境内部自动参与者的动作没有记录位置；
- 没有子进程环境的适配范例；SDK 环境合同检查不核对会话身份、同 ID 重发、批次 = 一个世界步、清理，也不区分声明与未声明的能力；
- 报告的成功率分母为“已结束的单元”，失败 / 未运行单元被排除；失败的单元在配对比较中直接消失（不计为不完整配对）；复用、超时没有数量与原因；配对只给未配对数量；小样本没有“工程读数”标记；两侧若是同一策略（不同名称）仍会被当作方法比较；
- 指标定义只有单位，没有观察量与时间窗；
- 复用键不含数据划分、内核版本、实际调用的模型端点 / 模型名；真实模型单元与确定性单元一样会被复用，没有“关键版本未知则保守重跑”。

**修复**：
- 轮次：内核原有的三种结局保持并被实测区分——参与者无可行动作 = 本轮 PASSED / `TURN_SKIPPED(retired=false)`，其他参与者继续；参与者预算用尽 = 退场 `TURN_SKIPPED(retired=true)`，其他参与者继续；整个实验结束 = 终止原因（全部退场 `ACTOR_BUDGETS_EXHAUSTED`，FAIL 策略下无动作 `NO_APPLICABLE_ACTION`，联合目标达成等）。
- 世界步单独记录：新事件 `WORLD_STEPPED`（批次 id、轮次、世界步、来源、本世界步中环境自动参与者的动作、实际发送的成员），`BatchRecord.world_step` / `automatic`；新能力 `env.world_step_report`（环境报告自己的世界步编号与自动参与者动作，未声明时世界步取快照步数并注明来源）。成员提案、自动参与者、批次提交、世界步四者分开。
- 子进程环境适配范例 `formal-lab.example.subprocess-world`（示例包 `examples/subprocess-env`：`formal_lab_example_subprocess.adapter` + 子进程 `formal_lab_example_subprocess.world`，JSON lines 协议 `formal-lab/subprocess-env@1`，子进程中承载通用 driver world）：会话身份（`subproc-<pid>-<nonce>`，重启即新会话）、请求身份（回显 id，不符即协议错误）、超时（不应答即杀死子进程，步骤抛 `ResultUnknown`、其它抛 `Timeout`）、清理（close、终结器、stdin EOF 三重保证）、版本（描述符 / 协议 / 后端）与能力：只声明可核验的（FULL_STATE 快照、恢复后重执行、按 id 幂等与查询、批次 = 一个世界步、世界步报告），持久会话 / 按需观测 / 观测延迟 / 种子变异不声明；按后端能力选择恢复（加载快照）或重建（新子进程 reset + 按原 id 重放已记录操作，摘要必须一致否则失败）。子进程可按世界步写日志 `world_log`，并支持配置环境自动参与者。
- SDK 合同检查 `check_environment` 增加：同 ID 重发只生效一次、一个批次 = 一个世界步且同批次 id 不重复生效、世界步报告与快照一致、会话身份稳定并指名插件、close 后无残留进程；未声明的能力只报告“未声明”，不去调用。
- 报告（`formal_lab_eval`）：成功率按预先固定的实验定义计算——分母为本划分的全部计划单元（失败 / 取消 / 超时 / 未运行均计为未达成），另附仅已结束单元的参考值；超时、复用（含来源与原因）、新执行、未复用原因、采样类型（DETERMINISTIC / RECORDED / RESAMPLED）、按指标的缺失原因分别计数；配对比较中失败或未运行的单元以“run FAILED: 原因”出现在不完整配对里，`unpaired_detail` 逐条给出缺失的一侧与原因；`reading` = ENGINEERING（非零配对差 < 6）/ STATISTICAL；两侧有效策略相同则拒绝比较并说明。`MetricDefinition.observable` / `window`，内置与示例的全部业务指标已补齐观察量与时间窗。
- 矩阵复用键 v3：在原有模型、插件（含描述符摘要）、规则、参与者视图、场景、种子、预算、扩展配置之外加入数据划分、内核 / 契约版本、每个参与者实际调用的模型端点与模型名（凭据不入键）。真实模型单元（模型名背后的版本未固定）与 live 服务环境（版本不由描述符固定）为“关键版本未知”，从不复用、保守重跑，原因写入单元；每个单元记录复用决策 REUSED / NEW / RERUN 及原因，创建响应增加 `rerun_conservative` 计数。

**完成证据**（`scripts/a4_rounds_evidence.py` → `a4-rounds.json`、`a4-paired-report.md`；平台 `tests/integration/test_rounds_reuse_platform.py`）：

| 情形 | 结果 |
|---|---|
| 轮流，收货员只能上架 | SUCCEEDED（JOINT_GOAL_REACHED），16 个全局步：收货员行动 3、空闲跳过 5，拣货员行动 8 |
| 联合批次，收货员只能上架 | SUCCEEDED，10 个批次 = 10 个世界步：收货员 PROPOSED 3 / PASSED 7，拣货员 PROPOSED 10 |
| 收货员预算 2 步 | 收货员行动 2 后退场（`TURN_SKIPPED retired=true` 1 次），拣货员继续并完成（SUCCEEDED） |
| 整个实验结束 | 两人都退场 → BUDGET_EXHAUSTED / ACTOR_BUDGETS_EXHAUSTED；FAIL 策略下收货员无动作 → FAILED / NO_APPLICABLE_ACTION |
| 轮中恢复（本地） | 第 5 步（第 3 轮收货员提案后、批次 OPEN）停止，经 JSON 在新组件中续跑：轨迹与批次与不中断运行完全一致 |
| 子进程环境 | 合同检查全部阶段通过；10 个批次与子进程自己的世界步日志逐轮相同；环境自动参与者 `clock` 的动作只出现在 WORLD_STEPPED，不是批次成员；加载恢复（SNAPSHOT）与重建恢复（RESEED）都得到同一状态与摘要；0.5 s 超时：抛 Timeout、旧子进程被杀 |
| 可手算配对报告 | 已知输入 rule = {10, 12, 8, 11, 9}、z3 = {7, 9, 8, 失败, 5}：4 对差值 [−3, −3, 0, −4]，均值 −2.5，1 个不完整配对（种子 3：z3 侧 “run FAILED: worker error”），成功 9/10，z3 更优、工程读数（4 对 < 6） |
| 平台（Temporal + PostgreSQL） | 子进程环境上的联合批次（收货员只能上架）：轮中暂停 + SIGKILL worker 后 SUCCEEDED，无重复事件；每个已提交批次的 (world_step, operation) 与子进程自己的世界步日志逐轮相同，世界步 1..n 连续（重启后的重执行只重复已记录的对，不形成新世界步）；收货员 PASSED 次数 = 其非退场 `TURN_SKIPPED` 次数 = 运行的 turn 状态计数，拣货员每轮 PROPOSED。矩阵：同配置的确定性单元 REUSED（同一 run，原因“the same full configuration … completed in matrix …”），LLM 单元（协议测试服务）配置摘要相同但 RERUN（“model … is not pinned”）并产生新请求；改预算后两单元都是新执行（NEW / RERUN）；报告 reused 1、new_runs 1、sampling DETERMINISTIC 1 / RESAMPLED 1，成功率分母 2 |

**验证**：`p4-a4-unit`（子进程环境 5、neutral-env、仓储、评测含可手算报告、多参与者，40 项）、`p4-a4-rounds`（9/9 必需断言）、`p4-a4-platform`（新增 2 + 原矩阵 v2 / 联合批次平台测试，7 项）全部 PASS；架构边界测试新增“只有子进程适配器控制进程”规则——最初把适配器放进 `formal_lab_env` 时被边界测试拦下（环境包不得启动进程、不得依赖 runtime；API 不得引用策略插件包），已移到示例包并改为 API 内部的去凭据 URL 函数；受影响单元套件 392 项通过（另 4 项即上述边界问题，修复后架构测试 58 项通过），web `tsc --noEmit` 通过。

## A5 · 产品入口、视觉修复与交接

**复现的缺口**：
- 390 px 下同步批次一轮的两个成员并排挤在 76 px 轮次列与 90 px 环境列之间：实测每个成员单元格只有 **70 px**，参与者名（“receive…”）、状态徽标（PROPOSED / APPLIED）与动作（“上架 i…”）全部被截断；平板 / 桌面宽度正常（259 / 461 px）。原有窄屏检查只看整页是否横向滚动，因此没有发现（修复前：同一测试在基线代码上的测量与截图 `docs/execution/evidence/phase4/a5-before/`；修复后：`a5-narrow.json` 与 `screens/`）；
- 动作文本省略时没有全文可读入口（无 `title`），可滚动的轮次列表没有显式 `tabindex`；
- Figma 的“运行台（390 px 窄屏）”画面就是这个被挤压的版本；
- 截图链 `scripts/capture_screens.py` 只在开发库没有任何矩阵时才建示例矩阵，开发库已有其他矩阵时直接中断，且证据只能写入阶段三目录。

**修复**：
- `web/src/styles.css`：`@media (max-width: 640px)` 时批次逐轮堆叠（轮次 → 每名成员整宽一格 → 世界步），轮次之间分隔线；单元格内的芯片 / 徽标换行；轮次列表的键盘焦点样式；桌面布局不变。
- `RunKernel.tsx` BatchPanel：动作全文在 `title`，轮次列表 `tabIndex=0`（键盘可聚焦并用 PageDown 滚动），右侧显示 A4 的世界步与环境自动参与者，说明文字改为“一个世界步；环境自身的自动参与者另行列出”。
- 截图链：`--out` 指定证据位置（默认仍是阶段三记录，历史不覆盖），开发库已有其他矩阵时也会建自己的示例矩阵。四张事实变化的基线截图（`run-batch` / `run-batch-dark` / `run-narrow` / `run-batch-step`）由这条链重新生成后替换，其余基线截图未动；README 与设计系统文档同步“世界步”与窄屏规则。
- 发行：`scripts/release.py` 把本地运行配置（`docker-compose.yaml`、`services.dev.yaml`、`.env.example`）连同摘要放入发行目录与清单；`scripts/a5_release_evidence.py` 分别记录在线安装与完全离线安装。

**完成证据**：

| 项 | 结果 |
|---|---|
| 产品流程（普通业务场景：订单处理，纯数据后端） | CLI `fal model push` 导入模型 → SDK 建场景与策略 → CLI `fal run start --wait`：SUCCEEDED，25 步 → API `/runs/{id}/steps/1` 与 CLI `fal run step` 给出同一解释（`reserve(o1)`，理由 “reserve stock for the submitted order due first”，前提 APPLICABLE，效果 MATCH）→ Web 运行台步骤详情（截图 `screens/a5-flow-step-explanation.png`）→ Web 下载与 CLI `fal export` 两份导出（事件数一致）→ **停止 API 进程**后在空目录 `fal replay verify / view / step` 全部成功（`a5-product-flow.json`） |
| 窄屏修复 | 390 px 明暗：成员单元格 70 → 328 px，无截断，动作全文 `title`；平板 259 px、桌面 461 px 不变；明 / 暗文字对比度 17.44 / 14.31；轮次列表 `tabindex=0`、聚焦后 PageDown 滚动；减少动态时过渡与动画为 0s；无整页横向滚动（截图 `screens/a5-batch-{phone-390,tablet-768,desktop-1440}-{light,dark}.png`，`a5-narrow.json`） |
| 截图链 | `capture_screens.py` 8 项检查全部为真（仓储批次 10 轮、订单恢复 6 个已对账操作、复用标记、窄屏无横向滚动、跳转链接、减少动态、无页面错误、无错误画面；`a5-web-capture.json`） |
| Figma（`uuV6JeilZQkhnIQcJYEUET`） | 只同步事实变化的节点：`6:106`（运行台 · 仓储批次）、`6:112`（运行台 · 深色）、`6:114`（运行台 · 390 px，画框 390×293 → 390×565，换为批次面板的新截图）、`7:61`（390 px 画面的代码说明加入 640 px 规则）；其余画面、组件、变量、故事板未动；记录在 `design/figma.json` 的 `syncs` |
| 发行 | `release.py --skip-images`：20 个 wheel（全部工作区成员，含新示例 `formal-lab-example-subprocess`）、Web 包、3 个本地运行配置（含摘要）、清单与许可清单；**在线安装**：干净 venv 从刚构建的 wheel 安装项目包、第三方依赖取自索引 / uv 缓存，无服务器下 `fal --help / replay verify / view / batches` 全部 0；**完全离线安装**：38 个 wheel 的离线目录，空目录新 venv `pip --no-index`（代理指向关闭端口）安装 `formal-lab-sdk[offline]`，对订单场景导出包 `fal replay verify / view / step` 全部 0（`a5-release.json`、`release-manifest.json`） |
| 镜像离线包 | **BLOCKED**：`offline_bundle.py` 构建并保存四个 OCI 镜像需 8 GiB，另需保持 15 GiB 宿主保留量，宿主仅 18.7 GiB 可用（磁盘守卫拒绝）；未构建，不写成已完成 |

**验证**：A5_FINAL
