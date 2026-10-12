<!-- 自建扩展阶段（非下发任务书）：应用户要求——案例太少、MAL 攻击图太玩具、cyber 领域不足、希望看到上千次真实模型调用且每一步对得起模型智能。目标：以“可被验证器判定”的难题重建 cyber 领域，并做一次上千单元的真实双模型批次。复选框 P8-01 / P8-02，scripts/tick.py 记录证据。开发模型 Claude Opus 4.8 / Opus 5.5，trailer 见提交。 -->

# Phase 8：防御性攻击图分析与大规模真实评测

把 cyber 领域从“三节点思维导图”升级为真正的形式攻击图分析：抽象 AND/OR 攻击图（入口立足点、中间步骤、目标），回答安全分析师真正会问的难题——最短攻击路径代价、部署一组防御后目标是否仍可达、使目标不可达的最小防御割、某派生步骤在给定状态下是否使能。每个问题的基准答案由 Z3 验证器 / 模型语义计算并交叉确认，所以答案客观对错、题目有区分度，而不是两模型都满分。

## 8.1 · 攻击图分析研究体（验证器判定）

- [x] **P8-01** 构建防御性攻击图分析研究体：形式 AND/OR 模型族、四类验证器判定的难题、评分器与数据隔离，并以 Z3 复核基准答案。
  - 证据：defensive attack-graph analysis study built and checked: packages/domain-mal/analysis.py (AND/OR generator + native oracle + Z3 ground truth for shortest cost / reachability-under-defense / min-cut / step-enabled, cross-checked), scorer attackgraph.analysis@1, research/studies/cyber-attackgraph (48 graphs, 183 tasks, 1098 planned units, answers wrapped to prevent ANSWER_LEAK). cyber-attackgraph check PASS (6 assertions: validates+separated, single track, ground truth re-derived+Z3-confirmed on sampled graphs, scorer labels scripted loopback, no key leak). FORMAL_MODEL_ANALYSIS track added (contracts regen, web label). Targeted regression 334 passed.
  - 实现：`packages/domain-mal/src/formal_lab_domain_mal/analysis.py`、`scripts/cyber_attackgraph_study.py`、`scripts/cyber_attackgraph_check.py`

机制：`packages/domain-mal/analysis.py`（生成器、原生可达性预言、Z3 最短代价/可达性、AND/OR 最小割、步骤使能），评分器 `attackgraph.analysis@1`（按验证器基准判对错，`program_correspondence` 记录是否与验证器一致），研究体 `research/studies/cyber-attackgraph`。答案以 `{"value": …}` 包裹，杜绝裸整数泄漏进题面（ANSWER_LEAK）。检查 `scripts/cyber_attackgraph_check.py`：研究体校验+数据隔离、抽样图基准从零重算并经 Z3 确认、评分器在协议回放上按脚本正确标注、密钥不落盘。注册 `p8`。

## 8.2 · 大规模真实双模型批次

- [ ] **P8-02** 在授权额度内运行一次上千单元的真实 GPT+Claude 批次，每一步都是验证器判定的难题，分模型/分题型报告正确率与一致性，并导入平台可视化。

~48 图 × 4 题型 × 2 模型 × 3 重复 ≈ 1100+ 真实调用（`scripts/cyber_run.py`，可续跑：已保存答案复用）。报告分题型（最短代价/可达性/最小割/步骤使能）与分模型正确率、程序对应（与验证器一致率）、输出 token；中转身份不可核验，不做已核验的厂商对比。导入订单项目的研究评测，网页 `基准对比` 可见每个单元的原始回答与评分依据。

```bash
make research-check ARGS="--group p8"
uv run --frozen python scripts/cyber_run.py        # 真实上千次批次（需 .env 中转凭据；可续跑）
```
