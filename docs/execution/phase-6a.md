<!-- 任务书原文：~/Downloads/06A_opus5_5_evaluation_foundation.md（编制 2026-10-06，核对基线 a05c1d2）；复选框编号 P6A-01 / P6A-02 与原文一致，scripts/tick.py 记录证据。开发执行者：Opus 5.5（开发身份，与被测模型分开记录）。前置 phase-5a.md、phase-5b.md；交接 docs/handoff/phase6.md。 -->

# Phase 6A：双模型调用、原始回答与评测基础

让同一份已审定任务可以调用 Claude Opus 5.5 与 GPT-6 Astra，完整记录提供方返回，并把答案交给独立评分器。平台、验证器、证据与程序实例在本地，模型推理在线。本文件负责通用接口，用普通业务与无害合成任务验收；实际软件案例保留用途说明，表示对照只用独立的无害合成案例。开发执行者与被测模型是两种身份，每个实验单元记录实际提供方与返回模型。

## A1 · 提供方适配与原始响应

- [x] **P6A-01** 交付两个提供方的可靠调用适配，以及不丢失拒绝和非结构化回答的研究响应记录。
  - 证据：OpenAIChatAdapter + AnthropicMessagesAdapter + research_call (raw first, call axis, fixed retries, budget/cancel before sending, possibly-billed counting, FAL_* credentials only, route checked against host); fal-research-response/v1; p6a-unit 55 + p6a-protocol 23 assertions; real: GPT-6 Astra + Claude Opus 5.5 answered via relay (COMPATIBLE_RELAY), Anthropic official route BLOCKED
  - 实现：`packages/strategies/src/formal_lab_strategies/model_clients.py`、`packages/strategies/src/formal_lab_strategies/protocol_server.py`、`packages/contracts/src/formal_lab_contracts/research.py`

沿用 `formal_lab_strategies.model_clients`，增加 OpenAI Chat Completions 与 Anthropic Messages 的最小研究适配和 `research_call`；研究静态调用输出持久化的回答产物，不伪装成 ActionProposal，既有策略的结构化决策接口不变。保持用户指定模型；拒绝、不可用或路由变化作为结果，不自动换型号或改写任务。原生接口与兼容中转分开登记（`route`）。研究响应协议 `fal-research-response/v1` 保存实验身份、调用身份、原始回答、执行状态、成本与来源；HTTP 401/403、限流、服务错误不算内容拒绝；空内容、截断、JSON 解析错误、类型错误与返回模型未知均有稳定分类；未暴露的内部推理保持不可用。调用轴与回答轴分开，原始回答先保存；取消与预算在请求前检查，模型调用、HTTP 尝试与未知计费请求分别计数，网络层有限重试固定，拒绝不重试；请求已发出但响应丢失记为不确定。

## A2 · 研究任务、分项评分与配对矩阵

- [x] **P6A-02** 交付研究任务入口、独立评分接口、两条实验线分开的矩阵与报告，并用普通任务和合成样例完成验证。
  - 证据：fal-research-study/v1 + fal-research-evaluation/v1; formal_lab_eval.research runner (reuse/scoring keys, resume, rescoring) + research_scorers (registrable; program-grounded and reference-interpreter scorers); two-track report with paired comparisons; studies p6a-protocol (24 units) and p6a-real; platform import + Web 研究评测 view; make research-check ARGS=--group p6a → PASS
  - 实现：`packages/evaluation/src/formal_lab_eval/research.py`、`packages/evaluation/src/formal_lab_eval/research_scorers.py`、`scripts/p6a_studies.py`、`web/src/components/StudyView.tsx`

研究定义协议 `fal-research-study/v1`（`research/studies/<study_id>/study.json`），任务输入与裁判材料分开；`STATIC_UNASSISTED` 与 `ASSISTED` 两种辅助模式，未实现的组合标为未运行。以现有 MetricDefinition / MetricResult 与 stats 为基础的薄评分适配和小型评测记录 `fal-research-evaluation/v1`，不制造步骤、世界状态或执行成功；每个单元有格式有效性、模型内正确性、程序对应（合成样例 N/A）、行为标签、拒绝状态、成本与原因。配对键只让一个比较维度变化；提供方参数不完全可比时明确记录。响应复用键与评分复用键分开。验收用协议服务覆盖合法回答、可见拒绝、空内容、截断、格式无效、模型变化、401/429/5xx、预算、取消和恢复；真实端点只作已授权额度内的普通业务最小调用，缺凭据时 BLOCKED。

## 交接

登记 `p6a`，沿用 `fal-check-result@1`；交付 `docs/handoff/phase6.md`、`phase6.manifest.json` 与 `docs/execution/evidence/research/p6a/`，并更新 protocol 的实际类型、函数、配置和评分接口。Phase 6 总状态等待 6B。

```bash
make research-check ARGS="--group p6a"
```
