<!-- 任务书原文：~/Downloads/06B_opus4_8_domain_evaluation.md（编制 2026-10-06，核对基线 a05c1d2）；复选框编号 P6B-01 / P6B-02，scripts/tick.py 记录证据。开发执行者：Opus 4.8（开发身份，与被测模型分开记录）。前置 phase-5b.md、phase-6a.md；交接 docs/handoff/phase6.md。 -->

# Phase 6B：领域判据、双模型实验与结果解释

用 Phase 5 的真实程序案例与 6A 的评测入口，回答：大模型能否理解并正确分析这些有程序依据的形式模型；哪些结论在独立验证下成立；不同业务表述对无害合成任务有什么影响。两条轨道分别进行：`implementation_conformance`（真实订单服务隔离案例，用途明确、以 5B 记录核查）与 `synthetic_representation`（独立无害合成任务，研究表示敏感性）。不把真实攻击隐藏为业务诱导规避，也不把两轨结果拼接成该能力的证据。被测模型固定为 Opus 5.5 与 GPT-6 Astra，身份按 6A 记录（本轮经中转，身份为中转方报告）。

## B1 · 判据、任务和实验定义

- [x] **P6B-01** 冻结可核查的参考判据和双模型实验定义，并证明待测输入没有参考答案泄漏。
  - 证据：rubric.json frozen (version+self-digest, 6 dimensions); orders.isolation-judgment@1 program-grounded scorer (truth from the 5B recorded run, not the reference); frozen study p6b-eval 6 conditions×2 models×2 reps=24, two tracks apart; load_study ANSWER_LEAK guard rejects reference-answer-in-input; p6b-unit 6 tests
  - 实现：`research/rubric/fal-research-rubric-1.json`、`packages/evaluation/src/formal_lab_eval/research_scorers.py`、`scripts/p6b_studies.py`

冻结 rubric（`research/rubric/fal-research-rubric-1.json`，版本 + 自摘要）区分六个判据：形式化正确性、程序对应、假设与范围表达、可观察的安全判断、拒绝及适当性、有用性与成本。优先确定性验证器；无真人复核，不标注“专家已复核”；LLM judge 未使用。真实案例任务为隔离性质判断（before/after = 缺陷/修复两个任务条件），由模型内判断 + 5B 程序裁判独立核查，没有自由文本到程序操作的执行通路。合成表示任务用人工审定的固定题面，在两个无害业务语境中表达同一个核验相等的有限问题（相同动作/目标/答案，只换业务叙述）。冻结工程批次：1 个真实案例 2 个任务条件 + 2 个合成基题各 2 个表示 = 6 条件，2 模型 × 2 重复 = 24 个初始请求。参考答案与补丁解释不进入待测输入（load_study 的 ANSWER_LEAK 校验）；案例级 split 保持同组。

## B2 · 执行、独立评分与解释

- [x] **P6B-02** 在冻结条件下运行已授权批次，产出完整分母、可追溯评分和两条轨道分别呈现的结果。
  - 证据：protocol dry-run (24 units scripted, all classes) + real batch within quota; denominator=24 planned units, MISSING for no-model-answer; two-track report with rubric digest+signals, representation & provider comparisons; real result: 24/24 answered, both models CORRECT on both tracks, no representation sensitivity at this difficulty, provider comparison engineering-only (relay, K08/K15); p6b-eval 18 assertions
  - 实现：`scripts/p6b_evidence.py`、`packages/evaluation/src/formal_lab_eval/research.py`、`scripts/research_checks.py`

先用协议测试服务确认字段、评分和成本上限，再真实在线调用。协议服务/缓存回放有独立标签；真实提供方缺失时 BLOCKED/NOT_RUN。按 study.json 执行，记录每个计划单元、每次调用尝试、模型 requested/returned、响应、失败/拒绝、验证与评分。分母始终是 24 个计划单元；无模型回答的单元在模型指标中为 MISSING（非 0 非 1），按调用结果计数。重复采样不是独立案例；样本不足以支持区间/显著性时省略。主要指标（correct）看结果前固定；工程检查通过与模型表现分开。拒绝可保存并人工核查，不靠连续改写或换模型争取接受。两轨分别呈现，不合并成一个总体成功率。

## 交接

研究定义 `research/studies/p6b-eval/`，结果 `research/results/p6b-eval/`，证据 `docs/execution/evidence/research/p6b/`；注册 `p6b`，更新 protocol、known-gaps、handoff/phase6。真实调用经中转完成，身份为中转方报告，不作已核实的提供方比较（官方路由未配置 → K08）。

```bash
make research-check ARGS="--group p6b"
```
