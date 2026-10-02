# 阶段四交接（Phase 4：平台修复与可验证交接 + 领域收口）

任务书：[docs/execution/phase-4a.md](../execution/phase-4a.md)（原文 `04A_opus5_5_platform_closure.md`，2026-10-02，A1—A5，开发执行者 Opus 5.5）；B1—B3 由 `04B_opus4_8_domain_closure.md` 交接。本文件是阶段四唯一的交接记录：每个交付包完成时追加证据，最终补齐 [phase4.manifest.json](phase4.manifest.json) 与 [phase4-checks.json](phase4-checks.json)。整体 Phase 4 的完成标记留给 B3。阶段二（`4e1f959`）、阶段三（`67e1b82`，0.3.0 发布 `9203691`）的交接是历史证据。

## 接手核对（2026-10-02）

| 项 | 结果 |
|---|---|
| 基线 | HEAD = `bccda301e58905ee0b0f37b2be9ed2938064d726` = 核对基线，工作区干净，与 origin/main 一致；仓库无 AGENTS.md |
| doctor | Ubuntu 24.04.4 aarch64，4 vCPU，5910 MiB；Postgres / Temporal / S3 已起，API / Web 开发栈未起；LLM 已配置；java 缺失（PRISM 不涉及）（`docs/execution/evidence/phase4/doctor-takeover.json`） |
| 磁盘 | 接手时宿主盘仅 8.5 GiB（0.3.0 镜像构建撑大了 VM 稀疏盘）。经用户授权清理垃圾：VM 内 BuildKit 缓存 4.3 GB、未被引用的阶段二 `formal-agent-lab/*:4e1f959e81f2` 镜像、pip/uv 缓存，随后在 VM 内 fstrim 归还 13.7 GiB；宿主 uv 缓存 954 MB、npm 缓存、brew 旧版本、一个过期的 Codex 临时安装目录。宿主盘 8.5 → 18 GiB。保留：开发栈卷与服务镜像、当前项目镜像、kindest/node、VM 内 Playwright 浏览器、其它应用的活动运行时；废纸篓未动（本就为空）；未做任何宽泛 prune |

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
