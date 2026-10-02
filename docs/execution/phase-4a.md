<!-- 任务书原文：~/Downloads/04A_opus5_5_platform_closure.md（编制 2026-10-02）；复选框编号改为 P4A-A1…A5 以便 scripts/tick.py 记录证据。交接记录：docs/handoff/phase4.md。 -->

# Phase 4A：平台修复与可验证交接（Opus 5.5）

项目：https://github.com/3351666087/formal-agent-lab
编制日期：2026-10-02
核对基线：`bccda301e58905ee0b0f37b2be9ed2938064d726`
顺序：先执行本文件 A1—A5，再交接 `04B_opus4_8_domain_closure.md` 的 B1—B3。

## 交付目标

Phase 4 是对现有产品的修复与验收收口，共 **8 个交付包**：本文件 5 个通用包（A1—A5），后续文件 3 个领域包（B1—B3）。沿用 Phase 3 的功能范围、六个功能区、插件体系、数据库、Temporal 和设计系统。本文件用订单、仓储和生产调度场景独立完成：检查结果可信、执行依据与当前状态一致、模型调用确实发生、参与者输入遵循已配置视图、联合轮次和配对统计正确、产品入口真实可用。最终产品目标是本地研究 Beta；4A 完成只表示通用接口与场景达到交接条件，整体结论由 B3 汇总。开发执行者（Opus 5.5）与实验里调用的模型（provider 配置决定）分别记录。

每包采用“复现缺口 → 固定预期 → 最小兼容修复 → 受影响验证”；最终稳定修订再做一次全量验收；保留失败与重试记录；完成报告由机器结果生成。契约保持 v1 冻结、v2 数据可读，增量字段走已有生成/兼容流程。

## A1 · 检查器与验收状态

- [x] **P4A-A1** 修复检查器、证据脚本接口和验收汇总，使未完成的必做项无法产生整体通过。
  - 证据：检查器状态协议：结构化结果+nonce、证据存在/新鲜/格式/记录状态、pytest 全跳过=BLOCKED、条件项固定触发、只采纳本次调用、complete 需完整运行、--strict；严格总验收按 nonce 裁决（REPORT_MISSING/STALE_REPORT/PARTIAL/…）且非 complete 退出 1；phase4 套件 a1—a5/b1—b3 与 B 登记点；tests/tools 35 项通过，真实引擎故障注入 8/8；真实 D5 脚本退出 0 记 BLOCKED 现判 BLOCKED。详见 docs/handoff/phase4.md#a1
  - 实现：`scripts/check_runner.py`、`scripts/check_result.py`、`scripts/acceptance_local.py`、`scripts/phase4_check.py`、`scripts/phase4_domain_checks.py`、`scripts/a1_status_evidence.py`、`tests/tools/test_check_status.py`、`tests/tools/test_acceptance_local.py`、`docs/execution/check-protocol.md`

复用 `scripts/check_runner.py`、`scripts/phase3_check.py`、`scripts/acceptance_local.py`、`tests/tools/test_check_runner.py`；新增 `scripts/phase4_check.py`（组 `a1`—`a5`、`b1`—`b3`）。由结构化证据、命令结果和声明的验收条件共同决定 PASS / FAIL / BLOCKED / NOT_RUN（含条件项不适用规则），每个结果带原因、检查 ID、attempt、日志与证据位置。必做项失败、缺失、阻塞、未执行、格式错误或过期证据时严格总验收返回非零、`complete=false`；部分运行与整体通过分开；条件项及触发条件执行前固定；环境依赖缺失属执行阻塞。汇总只采纳本次实际产生并验证过的结果；记录 commit、工作区摘要、配置摘要、工具版本与证据摘要，代码或配置改变后旧 PASS 失效。

**必须复现**：脚本退出 0 但报告 BLOCKED；必需断言为 false；报告丢失；子进程失败但磁盘留旧 PASS；只选一组；代码变化后复用旧证据；完整必做全部通过——前六种均不能汇总成整体通过。

## A2 · 当前状态、执行绑定与参与者输入

- [x] **P4A-A2** 用真实订单服务和仓储场景补齐执行前验证、状态竞争处理及参与者数据边界。
  - 证据：执行依据：内核按 turn 取身份、环境权威读取当前版本（FRESH/SERIALIZED/UNKNOWN）、提案版本另存，IDENTITY_MISMATCH / BASIS_UNKNOWN 不发送；统一 execution_binding 签发与校验、逐字段拒绝原因、发送时签发；订单服务写凭据（401）与事务内 expected_revision（EXACT/LOCATIONS）；参与者投影覆盖规划器输入/模型请求/调用记录/检查点/下载，令牌绑定的参与者通道（401/403），下载可离线读取。真实服务进程复现：凭据 5/服务 7 写入 0、检查后变化被条件更新拒绝、合法同版本写 1 次、ID 复用/冲突、6 种绑定错配、重发与续跑同规则、真实工厂+实际序列化/下载无标记字段与凭据（22/22）；phase4 a2 组 4/4 PASS；集成 18 项通过。详见 docs/handoff/phase4.md#a2
  - 实现：`packages/runtime/src/formal_lab_runtime/execution_context.py`、`packages/domain-broker/src/formal_lab_domain_broker/broker.py`、`examples/local-order-service/src/formal_lab_example_orders/service.py`、`packages/runtime/src/formal_lab_runtime/participants.py`、`packages/platform-api/src/formal_lab_api/services/participant_access.py`、`scripts/a2_execution_evidence.py`、`docs/assurance-scope.md`

执行依据（提案版本与执行时权威版本分开；门控不借无关字段取版本；读不到当前状态则未知并阻止写入）、完整绑定（由内核/已登记 session/实际服务身份构造，签发与校验同一规范化定义，策略字符串不作权威身份）、检查与写入间的竞争（真实服务用条件更新在副作用边界核对预期版本；纯数据运行串行化区间）、参与者数据（同一投影覆盖工厂初始化、PluginServices、模型载荷、观测、候选、查询、last_outcome、计划/检查点、调用记录、异常与下载/回放）。

**必须复现**：服务版本 7、提案与凭据版本 5 时写入计数 0；检查后状态变化时条件更新拒绝；合法同版本动作成功；同 ID 同请求查既有结果、异参冲突；环境/session/turn/版本错配拒绝；恢复与重发同规则；用真实策略工厂与实际序列化/下载路径检查标记字段与测试凭据。

## A3 · 模型调用与可恢复决策

- [ ] **P4A-A3** 完成可供其他策略复用的真实模型决策路径，覆盖调用记录、预算、来源与计划恢复。

最小复用接口（领域策略只给允许的任务/候选、响应约束、目标与解释即得标准 ActionProposal / TaskPlan）；真实提供方、协议测试服务与确定性替身分开标记，`client` 字符串不能单独决定来源；调用记录（call ID、请求/返回模型 ID、尝试次数、状态、用量是否提供、耗时、配置/提示摘要，凭据移除）；失败分类；预算覆盖恢复/重试/回退。

**必须复现**：测试服务返回不同合法候选时决策随之改变；无效选择按声明路径拒绝或回退；不可达真实端点产生实际失败记录；替身保持替身标签；暂停恢复不重复已提交调用；预算阻止继续请求；已配置真实端点的最小例子。

## A4 · 联合轮次与配对评测

- [ ] **P4A-A4** 补齐会被后续环境复用的轮次、恢复、实验矩阵和指标真实性。

区分单个参与者无动作 / 跳过退场 / 整个实验结束；联合批次一次提交推进一次世界步；子进程环境适配范例与合同检查；配对键、失败/超时/缺失/不适用计数、成功率分母、指标观察量/单位/时间窗；复用键与真实复用验证。

**完成证据**：两参与者完整运行/跳过/轮中恢复真实计数；平台与测试环境世界步逐轮对应；可手算核对的配对报告（含失败与不完整配对）；矩阵两次运行准确区分复用与新执行。

## A5 · 产品入口、视觉修复与交接

- [ ] **P4A-A5** 完成普通业务场景的真实产品流程、窄屏修复和可供 B1—B3 复用的本地交付。

Web/API/CLI/SDK 实际调用完成导入、配置、运行、解释、导出与离线回放（回放在服务停止时读取导出包）；修复 390px `.batch-row/.members/.batch-cell` 挤压与标签溢出（390px / 平板 / 桌面、明暗、键盘、减少动态）；Figma 只同步实际变化的节点，连接不可用则记待办；发行工具输出 wheel、Web 包、本地运行配置与清单，干净目录安装与离线回放（在线 / 完全离线分别记录）。

**完成证据**：实际产品入口调用、回放结果、窄屏截图与检查记录、发行安装结果、A1—A5 当前修订检查报告。

## 交接协议

```bash
make phase4-check ARGS="--group a1,a2,a3,a4,a5"
make acceptance-local
```

交接：`docs/handoff/phase4.md`、`phase4.manifest.json`、`phase4-checks.json`；证据 `docs/execution/evidence/phase4/`。整体 Phase 4 的完成标记留给 B3。
