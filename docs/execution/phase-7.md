<!-- 任务书原文：~/Downloads/07_reproduction_and_closeout.md（编制 2026-10-06，核对基线 a05c1d2）；复选框编号 P7-01 / P7-02，scripts/tick.py 记录证据。开发执行者：Opus 5.5（通用工程/复现/报告）+ Opus 4.8（领域机制/判据/K01-K02）——分工，不代表能力豁免。前置 phase-5/6；交接 docs/handoff/phase7.md。 -->

# Phase 7：保留案例、独立复现与研究结题

把案例、验证器、双模型实验和证据整理成可本地重建、检查、解释的研究交付物；以一个新机制的保留案例检查方法是否只适用于首个样例；关闭 K01-K03；向导师准确说明完成了什么、哪些结论仍不成立。两条轨道分别统计；真实攻击伪装/监管规避实验未纳入，不写成负结果。

## 7.1 · 小规模保留案例与冻结评测

- [x] **P7-01** 增加一个真实软件保留案例，在冻结条件下完成双模型评测，并交付逐案例的可信度与局限说明。
  - 证据：new held-out case research/cases/ratelimit-token-bucket (token bucket — different mechanism; own_test_variant, honestly labelled; upstream case NOT_RUN, blocker+entry in phase7 handoff); frozen study p7-holdout (before/after × 2 models × 2 reps = 8), reference fixed before any model saw it, ANSWER_LEAK guard; real result 8/8 answered, both models CORRECT, program CORRESPONDS; p7-holdout 12 assertions + p7-case 6
  - 实现：`examples/local-order-service/src/formal_lab_example_orders/research_ratelimit.py`、`scripts/p7_holdout_case.py`、`scripts/p7_evidence.py`

规模：Phase 5 的一个真实案例（orders-tenant-isolation）+ 本阶段一个新案例（令牌桶容量限制器，机制不同于订单服务，own_test_variant，诚实标注；上游案例未完成，阻塞与入口记入 handoff）；Phase 6 的两个合成基题继续使用。新案例机制、程序—模型对应、性质与裁判由领域职责说明；通用职责接入已有 schema、来源校验与展示。研究计划在看到保留案例的模型结果前冻结（参考答案由程序运行确定，再供模型求解）。before/after × 2 模型 × 2 重复 = 8 个新增初始请求，授权额度内；参考答案不入待测输入（ANSWER_LEAK 校验）；案例级 split 同组。

## 7.2 · 缺口关闭、复现包与导师验收

- [x] **P7-02** 关闭 K01—K03，完成本地总验收与干净环境复现，交付研究包和导师可核查的结题说明。
  - 证据：K01-K03 closed in place (commit 6fdcd5d; domain-mal gate/admission/config, broker CheckBasis, Steps.tsx) with tests; p7 registered; make research-check --strict complete=True (p5a,p5b,p6a,p6b,p7 = 12 checks PASS); offline clean-room reproduction scripts/p7_reproduce.py (no model call/network); offline_bundle manifest references research_data; final status fields in phase7.manifest (engineering_ready=true, experiment_execution_complete=true, findings=descriptive, independent_human_reproduction=PENDING, original_adviser_scope_complete=false); acceptance-local = baseline command (dev stack + 15GiB)
  - 实现：`scripts/p7_reproduce.py`、`scripts/handoff_phase7.py`、`scripts/offline_bundle.py`、`docs/handoff/phase7.md`

K01/K02/K03 在原位置修复（domain-mal gate/admission/config、broker CheckBasis、Steps.tsx），见 known-gaps 的关闭判据与证据。注册 `p7` 并完成五组总检查；研究检查用 nonce、实际断言与来源摘要；缺检查/BLOCKED/NOT_RUN/缺证据/过期证据都不产生 overall_complete。复用 release.py/offline_bundle.py，确认产物引用研究数据；提供只用已有结果的离线复核路径（scripts/p7_reproduce.py）与需用户凭据的重新采样路径。离线复核不冒充在线实验。最终状态分别给出 engineering_ready / experiment_execution_complete / findings_supported / independent_human_reproduction / original_adviser_scope_complete，定义在 protocol。若导师原始验收仍含“隐藏真实攻击以测监管规避”，`original_adviser_scope_complete` 保持 false。

```bash
make research-check ARGS="--group p7"
make research-check ARGS="--strict"
make acceptance-local
```
