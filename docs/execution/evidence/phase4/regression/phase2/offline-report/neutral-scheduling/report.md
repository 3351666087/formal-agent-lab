# Offline report: scheduling strategies and the observation-delay ablation — neutral-scheduling

## Conclusions

- 68 of 68 bundle(s) verified (format, contract, digests, causality, required parts); 0 rejected and excluded
- [acceptance] 51 cell(s): 51 finished, 0 failed or cancelled, 0 not run; goal reached in 48 of 51; missing metrics: makespan 3
- [acceptance] success 48/51 = 94% (denominator: every planned cell); timed out 0, reused 0, new runs 51
- [acceptance] 10 comparison(s) have no complete pairs (the metric is missing on one side or the dimension varies only where the other does not) — no conclusion from them
- [acceptance] method: 成本优化（Z3） is better on makespan (mean paired difference -1.33, 95% CI [-2.56, -0.111], 9 pairs, 0 unpaired)
- [acceptance] method: 最短路径（Z3） is better on makespan (mean paired difference -1.33, 95% CI [-2.56, -0.111], 9 pairs, 6 unpaired)
- [acceptance] mechanism: no-observation-delay is better on steps_used (mean paired difference -21.8, 95% CI [-29.3, -14.1], 15 pairs, 15 unpaired)
- [acceptance] mechanism: no-observation-delay is better on effect_mismatches (mean paired difference -2.4, 95% CI [-3.13, -1.67], 15 pairs, 15 unpaired)
- [acceptance] mechanism: no-observation-delay is better on delay_cost (mean paired difference -24.7, 95% CI [-46.4, -4], 15 pairs, 15 unpaired)
- [acceptance] mechanism: no-observation-delay is better on mean_tardiness (mean paired difference -4.2, 95% CI [-7.71, -0.911], 15 pairs, 15 unpaired)
- [acceptance] mechanism: no-observation-delay is better on makespan (mean paired difference -2.75, 95% CI [-3.75, -1.75], 12 pairs, 18 unpaired)
- [dev] 17 cell(s): 17 finished, 0 failed or cancelled, 0 not run; goal reached in 16 of 17; missing metrics: makespan 1
- [dev] success 16/17 = 94% (denominator: every planned cell); timed out 0, reused 0, new runs 17
- [dev] 10 comparison(s) have no complete pairs (the metric is missing on one side or the dimension varies only where the other does not) — no conclusion from them
- [dev] mechanism: no-observation-delay is better on steps_used (mean paired difference -23, 95% CI [-36, -10.2], 5 pairs, 5 unpaired) — engineering reading (small sample)
- [dev] mechanism: no-observation-delay is better on effect_mismatches (mean paired difference -3, 95% CI [-4.4, -1.4], 5 pairs, 5 unpaired) — engineering reading (small sample)
- [dev] mechanism: no-observation-delay is better on delay_cost (mean paired difference -23.6, 95% CI [-66.8, -1.2], 5 pairs, 5 unpaired) — engineering reading (small sample)
- [dev] mechanism: no-observation-delay is better on mean_tardiness (mean paired difference -4, 95% CI [-11.1, -0.2], 5 pairs, 5 unpaired) — engineering reading (small sample)
- [dev] mechanism: no-observation-delay is better on makespan (mean paired difference -1.5, 95% CI [-3.25, -0.25], 4 pairs, 6 unpaired) — engineering reading (small sample)

## Split `acceptance`

Denominator: 51 cells — run status {'SUCCEEDED': 48, 'BUDGET_EXHAUSTED': 3}; goal not reached: 3; missing metrics {'goal_reached': 0, 'steps_used': 0, 'rejected_actions': 0, 'effect_mismatches': 0, 'wall_seconds': 0, 'model_calls': 0, 'tokens': 0, 'orders_completed': 0, 'delay_cost': 0, 'mean_tardiness': 0, 'makespan': 3}.

Success: 48/51 (goal reached / every planned cell of this split (fixed before the runs; failed, cancelled, timed-out and not-run cells count as not reached)); finished only 48/51. Timed out: 0. Reused: 0 (—); new runs 51; sampling {'UNKNOWN': 51}.

### Per scenario (unit: one seed of one scenario)

| scenario | participants | backend | rules | model | ablation | budget | metric | value | 95% CI | n | missing | source |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 1 | [1, 1] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 15.67 | [14, 17] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 0.215 | [0.188, 0.233] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | [3, 3] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 1 | [0, 2] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 0.3333 | [0, 0.667] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 8.667 | [7, 10] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 1 | [1, 1] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 13.33 | [13, 14] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 1.733 | [1.42, 2.28] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | [3, 3] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 6.333 | [6, 7] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | goal_reached | 1 | [1, 1] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | steps_used | 13.33 | [13, 14] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | rejected_actions | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | effect_mismatches | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | wall_seconds | 4.28 | [3.91, 4.68] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | orders_completed | 3 | [3, 3] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | delay_cost | 1 | [0, 3] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | mean_tardiness | 0.1111 | [0, 0.333] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | makespan | 6.333 | [6, 7] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 1 | [1, 1] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 13.33 | [13, 14] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 1.705 | [1.38, 2.28] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | [3, 3] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 6.333 | [6, 7] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 1 | [1, 1] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 15.67 | [14, 17] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 0.1947 | [0.167, 0.211] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | 15.67 | [14, 17] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | [3, 3] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 1 | [0, 2] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 0.3333 | [0, 0.667] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 8.667 | [7, 10] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 1 | [1, 1] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 15.67 | [14, 17] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 0.1923 | [0.171, 0.212] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | [3, 3] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 1 | [0, 2] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 0.3333 | [0, 0.667] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 8.667 | [7, 10] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | goal_reached | 1 | [1, 1] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | steps_used | 15.67 | [14, 17] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | rejected_actions | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | effect_mismatches | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | wall_seconds | 0.206 | [0.177, 0.225] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | orders_completed | 3 | [3, 3] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | delay_cost | 1 | [0, 2] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | mean_tardiness | 0.3333 | [0, 0.667] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | makespan | 8.667 | [7, 10] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 1 | [1, 1] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 15.67 | [14, 17] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 2.333 | [2, 3] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 3.731 | [3.3, 4.06] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | [3, 3] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 1 | [0, 2] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 0.3333 | [0, 0.667] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 8.667 | [7, 10] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | goal_reached | 1 | [1, 1] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | steps_used | 13.33 | [13, 14] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | rejected_actions | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | effect_mismatches | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | wall_seconds | 0.1803 | [0.173, 0.191] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | orders_completed | 3 | [3, 3] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | delay_cost | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | mean_tardiness | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | makespan | 6.333 | [6, 7] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 1 | [1, 1] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 32.33 | [32, 33] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 16 | [15, 17] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 2.667 | [2, 3] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 11.69 | [10.6, 13] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | [3, 3] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 3.667 | [1, 6] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 0.6667 | [0.333, 1] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 9.333 | [9, 10] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | goal_reached | 1 | [1, 1] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | steps_used | 13.33 | [13, 14] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | rejected_actions | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | effect_mismatches | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | wall_seconds | 0.167 | [0.16, 0.179] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | orders_completed | 3 | [3, 3] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | delay_cost | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | mean_tardiness | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | makespan | 6.333 | [6, 7] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | goal_reached | 1 | [1, 1] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | steps_used | 32.67 | [32, 33] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | rejected_actions | 16.67 | [16, 17] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | effect_mismatches | 3 | [2, 4] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | wall_seconds | 19 | [16.7, 20.5] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | orders_completed | 3 | [3, 3] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | delay_cost | 3 | [1, 4] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | mean_tardiness | 0.5556 | [0.333, 0.667] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | makespan | 9 | [9, 9] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 1 | [1, 1] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 32.33 | [32, 33] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 16 | [15, 17] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 2.667 | [2, 3] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 11.89 | [10.7, 13.3] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | [3, 3] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 3.667 | [1, 6] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 0.6667 | [0.333, 1] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 9.333 | [9, 10] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | goal_reached | 1 | [1, 1] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | steps_used | 15.67 | [14, 17] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | rejected_actions | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | effect_mismatches | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | wall_seconds | 0.2113 | [0.189, 0.229] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | model_calls | 15.67 | [14, 17] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | tokens | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | orders_completed | 3 | [3, 3] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | delay_cost | 1 | [0, 2] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | mean_tardiness | 0.3333 | [0, 0.667] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | makespan | 8.667 | [7, 10] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 60 | [60, 60] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 59 | [59, 59] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 15.05 | [15, 15.2] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | 60 | [60, 60] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 110 | [110, 110] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 18 | [18, 18] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | — | — | 0 | 3 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | goal_reached | 1 | [1, 1] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | steps_used | 15.67 | [14, 17] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | rejected_actions | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | effect_mismatches | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | wall_seconds | 0.2063 | [0.183, 0.221] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | orders_completed | 3 | [3, 3] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | delay_cost | 1 | [0, 2] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | mean_tardiness | 0.3333 | [0, 0.667] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | makespan | 8.667 | [7, 10] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 1 | [1, 1] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 42.33 | [25, 53] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 21.67 | [7, 30] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 4.333 | [3, 5] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 10.67 | [6.26, 13.4] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | [3, 3] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 8.333 | [5, 14] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 2.333 | [1.33, 3.67] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 13.67 | [11, 16] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |

### Pooled across scenarios (unit: scenario; cluster bootstrap)

| participants | backend | rules | model | ablation | budget | metric | value | 95% CI | scenarios | n |
|---|---|---|---|---|---|---|---|---|---|---|
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | goal_reached | 1 | — | 1 | 3 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | steps_used | 15.67 | — | 1 | 3 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | rejected_actions | 0 | — | 1 | 3 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | effect_mismatches | 0 | — | 1 | 3 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | wall_seconds | 0.206 | — | 1 | 3 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | model_calls | — | — | 0 | 0 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | tokens | — | — | 0 | 0 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | orders_completed | 3 | — | 1 | 3 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | delay_cost | 1 | — | 1 | 3 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | mean_tardiness | 0.3333 | — | 1 | 3 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | makespan | 8.667 | — | 1 | 3 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 1 | [1, 1] | 2 | 6 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 15.67 | [15.7, 15.7] | 2 | 6 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 0 | [0, 0] | 2 | 6 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 1.167 | [0, 2.33] | 2 | 6 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 1.973 | [0.215, 3.73] | 2 | 6 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | [3, 3] | 2 | 6 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 1 | [1, 1] | 2 | 6 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 0.3333 | [0.333, 0.333] | 2 | 6 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 8.667 | [8.67, 8.67] | 2 | 6 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | goal_reached | 1 | — | 1 | 3 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | steps_used | 13.33 | — | 1 | 3 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | rejected_actions | 0 | — | 1 | 3 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | effect_mismatches | 0 | — | 1 | 3 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | wall_seconds | 0.1803 | — | 1 | 3 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | model_calls | — | — | 0 | 0 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | tokens | — | — | 0 | 0 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | orders_completed | 3 | — | 1 | 3 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | delay_cost | 0 | — | 1 | 3 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | mean_tardiness | 0 | — | 1 | 3 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | makespan | 6.333 | — | 1 | 3 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 1 | [1, 1] | 2 | 6 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 22.83 | [13.3, 32.3] | 2 | 6 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 8 | [0, 16] | 2 | 6 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 1.333 | [0, 2.67] | 2 | 6 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 6.713 | [1.73, 11.7] | 2 | 6 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | [3, 3] | 2 | 6 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 1.833 | [0, 3.67] | 2 | 6 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 0.3333 | [0, 0.667] | 2 | 6 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 7.833 | [6.33, 9.33] | 2 | 6 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | goal_reached | 1 | — | 1 | 3 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | steps_used | 13.33 | — | 1 | 3 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | rejected_actions | 0 | — | 1 | 3 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | effect_mismatches | 0 | — | 1 | 3 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | wall_seconds | 0.167 | — | 1 | 3 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | model_calls | — | — | 0 | 0 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | tokens | — | — | 0 | 0 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | orders_completed | 3 | — | 1 | 3 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | delay_cost | 0 | — | 1 | 3 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | mean_tardiness | 0 | — | 1 | 3 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | makespan | 6.333 | — | 1 | 3 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | goal_reached | 1 | [1, 1] | 2 | 6 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | steps_used | 23 | [13.3, 32.7] | 2 | 6 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | rejected_actions | 8.333 | [0, 16.7] | 2 | 6 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | effect_mismatches | 1.5 | [0, 3] | 2 | 6 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | wall_seconds | 11.64 | [4.28, 19] | 2 | 6 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | model_calls | — | — | 0 | 0 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | tokens | — | — | 0 | 0 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | orders_completed | 3 | [3, 3] | 2 | 6 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | delay_cost | 2 | [1, 3] | 2 | 6 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | mean_tardiness | 0.3333 | [0.111, 0.556] | 2 | 6 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | makespan | 7.667 | [6.33, 9] | 2 | 6 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 1 | [1, 1] | 2 | 6 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 22.83 | [13.3, 32.3] | 2 | 6 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 8 | [0, 16] | 2 | 6 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 1.333 | [0, 2.67] | 2 | 6 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 6.797 | [1.71, 11.9] | 2 | 6 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | [3, 3] | 2 | 6 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 1.833 | [0, 3.67] | 2 | 6 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 0.3333 | [0, 0.667] | 2 | 6 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 7.833 | [6.33, 9.33] | 2 | 6 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | goal_reached | 1 | — | 1 | 3 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | steps_used | 15.67 | — | 1 | 3 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | rejected_actions | 0 | — | 1 | 3 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | effect_mismatches | 0 | — | 1 | 3 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | wall_seconds | 0.2113 | — | 1 | 3 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | model_calls | 15.67 | — | 1 | 3 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | tokens | 0 | — | 1 | 3 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | orders_completed | 3 | — | 1 | 3 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | delay_cost | 1 | — | 1 | 3 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | mean_tardiness | 0.3333 | — | 1 | 3 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | makespan | 8.667 | — | 1 | 3 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 0.5 | [0, 1] | 2 | 6 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 37.83 | [15.7, 60] | 2 | 6 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 29.5 | [0, 59] | 2 | 6 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 0 | [0, 0] | 2 | 6 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 7.622 | [0.195, 15.1] | 2 | 6 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | 37.83 | [15.7, 60] | 2 | 6 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | 0 | [0, 0] | 2 | 6 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 1.5 | [0, 3] | 2 | 6 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 55.5 | [1, 110] | 2 | 6 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 9.167 | [0.333, 18] | 2 | 6 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 8.667 | — | 1 | 3 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | goal_reached | 1 | — | 1 | 3 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | steps_used | 15.67 | — | 1 | 3 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | rejected_actions | 0 | — | 1 | 3 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | effect_mismatches | 0 | — | 1 | 3 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | wall_seconds | 0.2063 | — | 1 | 3 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | model_calls | — | — | 0 | 0 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | tokens | — | — | 0 | 0 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | orders_completed | 3 | — | 1 | 3 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | delay_cost | 1 | — | 1 | 3 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | mean_tardiness | 0.3333 | — | 1 | 3 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | makespan | 8.667 | — | 1 | 3 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 1 | [1, 1] | 2 | 6 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 29 | [15.7, 42.3] | 2 | 6 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 10.83 | [0, 21.7] | 2 | 6 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 2.167 | [0, 4.33] | 2 | 6 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 5.431 | [0.192, 10.7] | 2 | 6 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | [3, 3] | 2 | 6 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 4.667 | [1, 8.33] | 2 | 6 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 1.333 | [0.333, 2.33] | 2 | 6 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 11.17 | [8.67, 13.7] | 2 | 6 |

### Paired comparisons (one dimension at a time)

| kind | A | B | metric | mean B−A | 95% CI | pairs | unpaired | better | test |
|---|---|---|---|---|---|---|---|---|---|
| method | 任务计划（规则生成） | 成本优化（Z3） | goal_reached | 0 | [0, 0] | 9 | 0 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 成本优化（Z3） | steps_used | 4 | [-1.67, 10.1] | 9 | 0 | 任务计划（规则生成） | p=0.891 (statistical) |
| method | 任务计划（规则生成） | 成本优化（Z3） | rejected_actions | 5.333 | [0, 10.7] | 9 | 0 | — | significance not reported: 3 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 成本优化（Z3） | effect_mismatches | 0.1111 | [-0.222, 0.444] | 9 | 0 | 任务计划（规则生成） | significance not reported: 3 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 成本优化（Z3） | wall_seconds | 3.151 | [1.02, 5.54] | 9 | 0 | — | p=0.0391 (statistical) |
| method | 任务计划（规则生成） | 成本优化（Z3） | model_calls | — | — | 0 | 9 | — | no complete pairs (engineering) |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 2] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 3] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 4] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-observation-delay', 'scenario-default', 2] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-observation-delay', 'scenario-default', 3] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-observation-delay', 'scenario-default', 4] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 2] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 3] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 4] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
| method | 任务计划（规则生成） | 成本优化（Z3） | tokens | — | — | 0 | 9 | — | no complete pairs (engineering) |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 2] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 3] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 4] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-observation-delay', 'scenario-default', 2] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-observation-delay', 'scenario-default', 3] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-observation-delay', 'scenario-default', 4] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 2] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 3] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 4] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
| method | 任务计划（规则生成） | 成本优化（Z3） | orders_completed | 0 | [0, 0] | 9 | 0 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 成本优化（Z3） | delay_cost | 0.2222 | [-1, 1.67] | 9 | 0 | 任务计划（规则生成） | p=1 (statistical) |
| method | 任务计划（规则生成） | 成本优化（Z3） | mean_tardiness | -0.1111 | [-0.37, 0.148] | 9 | 0 | 成本优化（Z3） | p=0.625 (statistical) |
| method | 任务计划（规则生成） | 成本优化（Z3） | makespan | -1.333 | [-2.56, -0.111] | 9 | 0 | 成本优化（Z3） | p=0.125 (statistical) |
| method | 任务计划（规则生成） | 最短路径（Z3） | goal_reached | 0 | [0, 0] | 9 | 6 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 2] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 3] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 4] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 2] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 3] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 4] | missing a | a: no cell with this key on this side | b: present | | | | | |
| method | 任务计划（规则生成） | 最短路径（Z3） | steps_used | 4 | [-1.67, 10.1] | 9 | 6 | 任务计划（规则生成） | p=0.891 (statistical) |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 2] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 3] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 4] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 2] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 3] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 4] | missing a | a: no cell with this key on this side | b: present | | | | | |
| method | 任务计划（规则生成） | 最短路径（Z3） | rejected_actions | 5.333 | [0, 10.7] | 9 | 6 | — | significance not reported: 3 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 2] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 3] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 4] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 2] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 3] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 4] | missing a | a: no cell with this key on this side | b: present | | | | | |
| method | 任务计划（规则生成） | 最短路径（Z3） | effect_mismatches | 0.1111 | [-0.222, 0.444] | 9 | 6 | 任务计划（规则生成） | significance not reported: 3 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 2] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 3] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 4] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 2] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 3] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 4] | missing a | a: no cell with this key on this side | b: present | | | | | |
| method | 任务计划（规则生成） | 最短路径（Z3） | wall_seconds | 3.203 | [1.02, 5.67] | 9 | 6 | — | p=0.0547 (statistical) |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 2] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 3] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 4] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 2] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 3] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 4] | missing a | a: no cell with this key on this side | b: present | | | | | |
| method | 任务计划（规则生成） | 最短路径（Z3） | model_calls | — | — | 0 | 15 | — | no complete pairs (engineering) |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 2] | missing both | a: no cell with this key on this side | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 3] | missing both | a: no cell with this key on this side | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 4] | missing both | a: no cell with this key on this side | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 2] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 3] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 4] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-observation-delay', 'scenario-default', 2] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-observation-delay', 'scenario-default', 3] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-observation-delay', 'scenario-default', 4] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 2] | missing both | a: no cell with this key on this side | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
| method | 任务计划（规则生成） | 最短路径（Z3） | tokens | — | — | 0 | 15 | — | no complete pairs (engineering) |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 2] | missing both | a: no cell with this key on this side | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 3] | missing both | a: no cell with this key on this side | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 4] | missing both | a: no cell with this key on this side | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 2] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 3] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 4] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-observation-delay', 'scenario-default', 2] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-observation-delay', 'scenario-default', 3] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-observation-delay', 'scenario-default', 4] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 2] | missing both | a: no cell with this key on this side | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
| method | 任务计划（规则生成） | 最短路径（Z3） | orders_completed | 0 | [0, 0] | 9 | 6 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 2] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 3] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 4] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 2] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 3] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 4] | missing a | a: no cell with this key on this side | b: present | | | | | |
| method | 任务计划（规则生成） | 最短路径（Z3） | delay_cost | 0.2222 | [-1, 1.67] | 9 | 6 | 任务计划（规则生成） | p=1 (statistical) |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 2] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 3] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 4] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 2] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 3] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 4] | missing a | a: no cell with this key on this side | b: present | | | | | |
| method | 任务计划（规则生成） | 最短路径（Z3） | mean_tardiness | -0.1111 | [-0.37, 0.148] | 9 | 6 | 最短路径（Z3） | p=0.625 (statistical) |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 2] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 3] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 4] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 2] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 3] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 4] | missing a | a: no cell with this key on this side | b: present | | | | | |
| method | 任务计划（规则生成） | 最短路径（Z3） | makespan | -1.333 | [-2.56, -0.111] | 9 | 6 | 最短路径（Z3） | p=0.125 (statistical) |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 2] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 3] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 4] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 2] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 3] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 4] | missing a | a: no cell with this key on this side | b: present | | | | | |
| method | 任务计划（规则生成） | 模型辅助（替身） | goal_reached | -0.3333 | [-0.667, 0] | 9 | 0 | 任务计划（规则生成） | significance not reported: 3 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 模型辅助（替身） | steps_used | 14.78 | [0, 29.4] | 9 | 0 | 任务计划（规则生成） | significance not reported: 3 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 模型辅助（替身） | rejected_actions | 19.67 | [0, 39.3] | 9 | 0 | — | significance not reported: 3 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 模型辅助（替身） | effect_mismatches | -0.7778 | [-1.56, 0] | 9 | 0 | 模型辅助（替身） | significance not reported: 3 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 模型辅助（替身） | wall_seconds | 3.768 | [-0.00111, 7.54] | 9 | 0 | — | p=0.461 (statistical) |
| method | 任务计划（规则生成） | 模型辅助（替身） | model_calls | — | — | 0 | 9 | — | no complete pairs (engineering) |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 2] | missing a | a: NOT_APPLICABLE: strategy makes no model calls | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 3] | missing a | a: NOT_APPLICABLE: strategy makes no model calls | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 4] | missing a | a: NOT_APPLICABLE: strategy makes no model calls | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-observation-delay', 'scenario-default', 2] | missing a | a: NOT_APPLICABLE: strategy makes no model calls | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-observation-delay', 'scenario-default', 3] | missing a | a: NOT_APPLICABLE: strategy makes no model calls | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-observation-delay', 'scenario-default', 4] | missing a | a: NOT_APPLICABLE: strategy makes no model calls | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 2] | missing a | a: NOT_APPLICABLE: strategy makes no model calls | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 3] | missing a | a: NOT_APPLICABLE: strategy makes no model calls | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 4] | missing a | a: NOT_APPLICABLE: strategy makes no model calls | b: present | | | | | |
| method | 任务计划（规则生成） | 模型辅助（替身） | tokens | — | — | 0 | 9 | — | no complete pairs (engineering) |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 2] | missing a | a: NOT_APPLICABLE: strategy makes no model calls | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 3] | missing a | a: NOT_APPLICABLE: strategy makes no model calls | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 4] | missing a | a: NOT_APPLICABLE: strategy makes no model calls | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-observation-delay', 'scenario-default', 2] | missing a | a: NOT_APPLICABLE: strategy makes no model calls | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-observation-delay', 'scenario-default', 3] | missing a | a: NOT_APPLICABLE: strategy makes no model calls | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-observation-delay', 'scenario-default', 4] | missing a | a: NOT_APPLICABLE: strategy makes no model calls | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 2] | missing a | a: NOT_APPLICABLE: strategy makes no model calls | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 3] | missing a | a: NOT_APPLICABLE: strategy makes no model calls | b: present | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 4] | missing a | a: NOT_APPLICABLE: strategy makes no model calls | b: present | | | | | |
| method | 任务计划（规则生成） | 模型辅助（替身） | orders_completed | -1 | [-2, 0] | 9 | 0 | 任务计划（规则生成） | significance not reported: 3 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 模型辅助（替身） | delay_cost | 36.33 | [0, 72.7] | 9 | 0 | 任务计划（规则生成） | significance not reported: 3 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 模型辅助（替身） | mean_tardiness | 5.889 | [0, 11.8] | 9 | 0 | 任务计划（规则生成） | significance not reported: 3 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 模型辅助（替身） | makespan | 0 | [0, 0] | 6 | 3 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 2] | missing b | a: present | b: MISSING: not all operations finished | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 3] | missing b | a: present | b: MISSING: not all operations finished | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 4] | missing b | a: present | b: MISSING: not all operations finished | | | | | |
| method | 任务计划（规则生成） | 规则（EDD） | goal_reached | 0 | [0, 0] | 9 | 0 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 规则（EDD） | steps_used | 8.889 | [0, 19] | 9 | 0 | 任务计划（规则生成） | significance not reported: 3 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 规则（EDD） | rejected_actions | 7.222 | [0, 16] | 9 | 0 | — | significance not reported: 3 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 规则（EDD） | effect_mismatches | 0.6667 | [0, 1.44] | 9 | 0 | 任务计划（规则生成） | significance not reported: 3 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 规则（EDD） | wall_seconds | 2.305 | [-0.00444, 4.91] | 9 | 0 | — | p=0.652 (statistical) |
| method | 任务计划（规则生成） | 规则（EDD） | model_calls | — | — | 0 | 9 | — | no complete pairs (engineering) |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 2] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 3] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 4] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-observation-delay', 'scenario-default', 2] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-observation-delay', 'scenario-default', 3] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-observation-delay', 'scenario-default', 4] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 2] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 3] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 4] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
| method | 任务计划（规则生成） | 规则（EDD） | tokens | — | — | 0 | 9 | — | no complete pairs (engineering) |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 2] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 3] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 4] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-observation-delay', 'scenario-default', 2] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-observation-delay', 'scenario-default', 3] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-observation-delay', 'scenario-default', 4] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 2] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 3] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 4] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
| method | 任务计划（规则生成） | 规则（EDD） | orders_completed | 0 | [0, 0] | 9 | 0 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 规则（EDD） | delay_cost | 2.444 | [0, 5.11] | 9 | 0 | 任务计划（规则生成） | significance not reported: 3 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 规则（EDD） | mean_tardiness | 0.6667 | [0, 1.37] | 9 | 0 | 任务计划（规则生成） | significance not reported: 3 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 规则（EDD） | makespan | 1.667 | [0, 3.33] | 9 | 0 | 任务计划（规则生成） | significance not reported: 3 non-zero paired differences < 6 (engineering) |
| mechanism | none | no-observation-delay | goal_reached | 0.2 | [0, 0.4] | 15 | 15 | no-observation-delay | significance not reported: 3 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
| mechanism | none | no-observation-delay | steps_used | -21.8 | [-29.3, -14.1] | 15 | 15 | no-observation-delay | p=0.000488 (statistical) |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
| mechanism | none | no-observation-delay | rejected_actions | -22.53 | [-33.1, -12.8] | 15 | 15 | — | p=0.000488 (statistical) |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
| mechanism | none | no-observation-delay | effect_mismatches | -2.4 | [-3.13, -1.67] | 15 | 15 | no-observation-delay | p=0.000488 (statistical) |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
| mechanism | none | no-observation-delay | wall_seconds | -10.41 | [-12.4, -8.26] | 15 | 15 | — | p=6.1e-05 (statistical) |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
| mechanism | none | no-observation-delay | model_calls | -44.33 | [-46, -43] | 3 | 27 | — | significance not reported: 3 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
| mechanism | none | no-observation-delay | tokens | 0 | [0, 0] | 3 | 27 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
| mechanism | none | no-observation-delay | orders_completed | 0.6 | [0, 1.2] | 15 | 15 | no-observation-delay | significance not reported: 3 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
| mechanism | none | no-observation-delay | delay_cost | -24.73 | [-46.4, -4] | 15 | 15 | no-observation-delay | p=0.000488 (statistical) |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
| mechanism | none | no-observation-delay | mean_tardiness | -4.2 | [-7.71, -0.911] | 15 | 15 | no-observation-delay | p=0.000488 (statistical) |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
| mechanism | none | no-observation-delay | makespan | -2.75 | [-3.75, -1.75] | 12 | 18 | no-observation-delay | p=0.00391 (statistical) |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
| mechanism | none | no-plan-memory | goal_reached | 0 | [0, 0] | 6 | 24 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
| mechanism | none | no-plan-memory | steps_used | 0.1667 | [0, 0.5] | 6 | 24 | none | significance not reported: 1 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
| mechanism | none | no-plan-memory | rejected_actions | 0.3333 | [0, 1] | 6 | 24 | — | significance not reported: 1 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
| mechanism | none | no-plan-memory | effect_mismatches | 0.1667 | [0, 0.5] | 6 | 24 | none | significance not reported: 1 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
| mechanism | none | no-plan-memory | wall_seconds | 4.844 | [3.02, 6.83] | 6 | 24 | — | p=0.0312 (statistical) |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
| mechanism | none | no-plan-memory | model_calls | — | — | 0 | 30 | — | no complete pairs (engineering) |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
| mechanism | none | no-plan-memory | tokens | — | — | 0 | 30 | — | no complete pairs (engineering) |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
| mechanism | none | no-plan-memory | orders_completed | 0 | [0, 0] | 6 | 24 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
| mechanism | none | no-plan-memory | delay_cost | 0.1667 | [-1, 1.5] | 6 | 24 | none | significance not reported: 2 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
| mechanism | none | no-plan-memory | mean_tardiness | -9.252e-18 | [-0.167, 0.167] | 6 | 24 | no-plan-memory | significance not reported: 2 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
| mechanism | none | no-plan-memory | makespan | -0.1667 | [-0.5, 0] | 6 | 24 | no-plan-memory | significance not reported: 1 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 3] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 4] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['acceptance', 'sched-normal', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 2] | missing b | a: present | b: no cell with this key on this side | | | | | |

## Split `dev`

Denominator: 17 cells — run status {'SUCCEEDED': 16, 'BUDGET_EXHAUSTED': 1}; goal not reached: 1; missing metrics {'goal_reached': 0, 'steps_used': 0, 'rejected_actions': 0, 'effect_mismatches': 0, 'wall_seconds': 0, 'model_calls': 0, 'tokens': 0, 'orders_completed': 0, 'delay_cost': 0, 'mean_tardiness': 0, 'makespan': 1}.

Success: 16/17 (goal reached / every planned cell of this split (fixed before the runs; failed, cancelled, timed-out and not-run cells count as not reached)); finished only 16/17. Timed out: 0. Reused: 0 (—); new runs 17; sampling {'UNKNOWN': 17}.

### Per scenario (unit: one seed of one scenario)

| scenario | participants | backend | rules | model | ablation | budget | metric | value | 95% CI | n | missing | source |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 1 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 15 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 0.194 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 8 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 1 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 14 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 3.096 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 7 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | goal_reached | 1 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | steps_used | 14 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | rejected_actions | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | effect_mismatches | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | wall_seconds | 5.695 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | orders_completed | 3 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | delay_cost | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | mean_tardiness | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | makespan | 7 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 1 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 14 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 3.072 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 7 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 1 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 15 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 0.283 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | 15 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 8 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 1 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 15 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 0.198 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 8 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | goal_reached | 1 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | steps_used | 15 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | rejected_actions | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | effect_mismatches | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | wall_seconds | 0.191 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | orders_completed | 3 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | delay_cost | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | mean_tardiness | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | makespan | 8 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 1 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 15 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 2 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 3.557 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 8 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | goal_reached | 1 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | steps_used | 14 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | rejected_actions | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | effect_mismatches | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | wall_seconds | 0.181 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | orders_completed | 3 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | delay_cost | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | mean_tardiness | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | makespan | 7 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 1 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 33 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 18 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 4 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 13.34 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 2 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 0.3333 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 8 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | goal_reached | 1 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | steps_used | 14 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | rejected_actions | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | effect_mismatches | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | wall_seconds | 0.18 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | orders_completed | 3 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | delay_cost | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | mean_tardiness | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | makespan | 7 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | goal_reached | 1 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | steps_used | 33 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | rejected_actions | 18 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | effect_mismatches | 4 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | wall_seconds | 20.2 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | orders_completed | 3 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | delay_cost | 2 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | mean_tardiness | 0.3333 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | makespan | 8 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 1 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 33 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 18 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 4 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 13.77 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 2 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 0.3333 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 8 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | goal_reached | 1 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | steps_used | 15 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | rejected_actions | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | effect_mismatches | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | wall_seconds | 0.187 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | model_calls | 15 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | tokens | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | orders_completed | 3 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | delay_cost | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | mean_tardiness | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | makespan | 8 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 60 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 59 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 14.76 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | 60 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 110 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 18 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | — | — | 0 | 1 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | goal_reached | 1 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | steps_used | 15 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | rejected_actions | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | effect_mismatches | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | wall_seconds | 0.202 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | orders_completed | 3 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | delay_cost | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | mean_tardiness | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | makespan | 8 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 1 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 47 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 28 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 5 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 11.94 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 4 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 1.333 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 12 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |

### Pooled across scenarios (unit: scenario; cluster bootstrap)

| participants | backend | rules | model | ablation | budget | metric | value | 95% CI | scenarios | n |
|---|---|---|---|---|---|---|---|---|---|---|
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | goal_reached | 1 | — | 1 | 1 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | steps_used | 15 | — | 1 | 1 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | rejected_actions | 0 | — | 1 | 1 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | effect_mismatches | 0 | — | 1 | 1 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | wall_seconds | 0.191 | — | 1 | 1 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | model_calls | — | — | 0 | 0 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | tokens | — | — | 0 | 0 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | orders_completed | 3 | — | 1 | 1 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | delay_cost | 0 | — | 1 | 1 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | mean_tardiness | 0 | — | 1 | 1 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | makespan | 8 | — | 1 | 1 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 1 | [1, 1] | 2 | 2 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 15 | [15, 15] | 2 | 2 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 0 | [0, 0] | 2 | 2 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 1 | [0, 2] | 2 | 2 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 1.875 | [0.194, 3.56] | 2 | 2 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | [3, 3] | 2 | 2 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 0 | [0, 0] | 2 | 2 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 0 | [0, 0] | 2 | 2 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 8 | [8, 8] | 2 | 2 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | goal_reached | 1 | — | 1 | 1 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | steps_used | 14 | — | 1 | 1 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | rejected_actions | 0 | — | 1 | 1 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | effect_mismatches | 0 | — | 1 | 1 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | wall_seconds | 0.181 | — | 1 | 1 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | model_calls | — | — | 0 | 0 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | tokens | — | — | 0 | 0 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | orders_completed | 3 | — | 1 | 1 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | delay_cost | 0 | — | 1 | 1 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | mean_tardiness | 0 | — | 1 | 1 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | makespan | 7 | — | 1 | 1 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 1 | [1, 1] | 2 | 2 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 23.5 | [14, 33] | 2 | 2 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 9 | [0, 18] | 2 | 2 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 2 | [0, 4] | 2 | 2 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 8.22 | [3.1, 13.3] | 2 | 2 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | [3, 3] | 2 | 2 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 1 | [0, 2] | 2 | 2 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 0.1667 | [0, 0.333] | 2 | 2 |
| 成本优化（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 7.5 | [7, 8] | 2 | 2 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | goal_reached | 1 | — | 1 | 1 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | steps_used | 14 | — | 1 | 1 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | rejected_actions | 0 | — | 1 | 1 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | effect_mismatches | 0 | — | 1 | 1 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | wall_seconds | 0.18 | — | 1 | 1 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | model_calls | — | — | 0 | 0 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | tokens | — | — | 0 | 0 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | orders_completed | 3 | — | 1 | 1 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | delay_cost | 0 | — | 1 | 1 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | mean_tardiness | 0 | — | 1 | 1 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | makespan | 7 | — | 1 | 1 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | goal_reached | 1 | [1, 1] | 2 | 2 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | steps_used | 23.5 | [14, 33] | 2 | 2 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | rejected_actions | 9 | [0, 18] | 2 | 2 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | effect_mismatches | 2 | [0, 4] | 2 | 2 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | wall_seconds | 12.95 | [5.7, 20.2] | 2 | 2 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | model_calls | — | — | 0 | 0 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | tokens | — | — | 0 | 0 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | orders_completed | 3 | [3, 3] | 2 | 2 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | delay_cost | 1 | [0, 2] | 2 | 2 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | mean_tardiness | 0.1667 | [0, 0.333] | 2 | 2 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | no-plan-memory | scenario-default | makespan | 7.5 | [7, 8] | 2 | 2 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 1 | [1, 1] | 2 | 2 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 23.5 | [14, 33] | 2 | 2 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 9 | [0, 18] | 2 | 2 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 2 | [0, 4] | 2 | 2 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 8.421 | [3.07, 13.8] | 2 | 2 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | [3, 3] | 2 | 2 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 1 | [0, 2] | 2 | 2 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 0.1667 | [0, 0.333] | 2 | 2 |
| 最短路径（Z3） | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 7.5 | [7, 8] | 2 | 2 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | goal_reached | 1 | — | 1 | 1 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | steps_used | 15 | — | 1 | 1 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | rejected_actions | 0 | — | 1 | 1 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | effect_mismatches | 0 | — | 1 | 1 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | wall_seconds | 0.187 | — | 1 | 1 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | model_calls | 15 | — | 1 | 1 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | tokens | 0 | — | 1 | 1 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | orders_completed | 3 | — | 1 | 1 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | delay_cost | 0 | — | 1 | 1 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | mean_tardiness | 0 | — | 1 | 1 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | makespan | 8 | — | 1 | 1 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 0.5 | [0, 1] | 2 | 2 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 37.5 | [15, 60] | 2 | 2 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 29.5 | [0, 59] | 2 | 2 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 0 | [0, 0] | 2 | 2 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 7.523 | [0.283, 14.8] | 2 | 2 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | 37.5 | [15, 60] | 2 | 2 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | 0 | [0, 0] | 2 | 2 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 1.5 | [0, 3] | 2 | 2 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 55 | [0, 110] | 2 | 2 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 9 | [0, 18] | 2 | 2 |
| 模型辅助（替身） | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 8 | — | 1 | 1 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | goal_reached | 1 | — | 1 | 1 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | steps_used | 15 | — | 1 | 1 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | rejected_actions | 0 | — | 1 | 1 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | effect_mismatches | 0 | — | 1 | 1 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | wall_seconds | 0.202 | — | 1 | 1 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | model_calls | — | — | 0 | 0 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | tokens | — | — | 0 | 0 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | orders_completed | 3 | — | 1 | 1 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | delay_cost | 0 | — | 1 | 1 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | mean_tardiness | 0 | — | 1 | 1 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | makespan | 8 | — | 1 | 1 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 1 | [1, 1] | 2 | 2 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 31 | [15, 47] | 2 | 2 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 14 | [0, 28] | 2 | 2 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 2.5 | [0, 5] | 2 | 2 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 6.071 | [0.198, 11.9] | 2 | 2 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | [3, 3] | 2 | 2 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 2 | [0, 4] | 2 | 2 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 0.6667 | [0, 1.33] | 2 | 2 |
| 规则（EDD） | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 10 | [8, 12] | 2 | 2 |

### Paired comparisons (one dimension at a time)

| kind | A | B | metric | mean B−A | 95% CI | pairs | unpaired | better | test |
|---|---|---|---|---|---|---|---|---|---|
| method | 任务计划（规则生成） | 成本优化（Z3） | goal_reached | 0 | [0, 0] | 3 | 0 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 成本优化（Z3） | steps_used | 5.333 | [-1, 18] | 3 | 0 | 任务计划（规则生成） | significance not reported: 3 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 成本优化（Z3） | rejected_actions | 6 | [0, 18] | 3 | 0 | — | significance not reported: 1 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 成本优化（Z3） | effect_mismatches | 0.6667 | [0, 2] | 3 | 0 | 任务计划（规则生成） | significance not reported: 1 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 成本优化（Z3） | wall_seconds | 4.226 | [-0.01, 9.79] | 3 | 0 | — | significance not reported: 3 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 成本优化（Z3） | model_calls | — | — | 0 | 3 | — | no complete pairs (engineering) |
|  | incomplete pair ['dev', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-observation-delay', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
| method | 任务计划（规则生成） | 成本优化（Z3） | tokens | — | — | 0 | 3 | — | no complete pairs (engineering) |
|  | incomplete pair ['dev', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-observation-delay', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
| method | 任务计划（规则生成） | 成本优化（Z3） | orders_completed | 0 | [0, 0] | 3 | 0 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 成本优化（Z3） | delay_cost | 0.6667 | [0, 2] | 3 | 0 | 任务计划（规则生成） | significance not reported: 1 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 成本优化（Z3） | mean_tardiness | 0.1111 | [0, 0.333] | 3 | 0 | 任务计划（规则生成） | significance not reported: 1 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 成本优化（Z3） | makespan | -0.6667 | [-1, 0] | 3 | 0 | 成本优化（Z3） | significance not reported: 2 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 最短路径（Z3） | goal_reached | 0 | [0, 0] | 3 | 2 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['dev', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 1] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 1] | missing a | a: no cell with this key on this side | b: present | | | | | |
| method | 任务计划（规则生成） | 最短路径（Z3） | steps_used | 5.333 | [-1, 18] | 3 | 2 | 任务计划（规则生成） | significance not reported: 3 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['dev', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 1] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 1] | missing a | a: no cell with this key on this side | b: present | | | | | |
| method | 任务计划（规则生成） | 最短路径（Z3） | rejected_actions | 6 | [0, 18] | 3 | 2 | — | significance not reported: 1 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['dev', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 1] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 1] | missing a | a: no cell with this key on this side | b: present | | | | | |
| method | 任务计划（规则生成） | 最短路径（Z3） | effect_mismatches | 0.6667 | [0, 2] | 3 | 2 | 任务计划（规则生成） | significance not reported: 1 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['dev', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 1] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 1] | missing a | a: no cell with this key on this side | b: present | | | | | |
| method | 任务计划（规则生成） | 最短路径（Z3） | wall_seconds | 4.36 | [-0.011, 10.2] | 3 | 2 | — | significance not reported: 3 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['dev', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 1] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 1] | missing a | a: no cell with this key on this side | b: present | | | | | |
| method | 任务计划（规则生成） | 最短路径（Z3） | model_calls | — | — | 0 | 5 | — | no complete pairs (engineering) |
|  | incomplete pair ['dev', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 1] | missing both | a: no cell with this key on this side | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['dev', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-observation-delay', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 1] | missing both | a: no cell with this key on this side | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
| method | 任务计划（规则生成） | 最短路径（Z3） | tokens | — | — | 0 | 5 | — | no complete pairs (engineering) |
|  | incomplete pair ['dev', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 1] | missing both | a: no cell with this key on this side | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['dev', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-observation-delay', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 1] | missing both | a: no cell with this key on this side | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
| method | 任务计划（规则生成） | 最短路径（Z3） | orders_completed | 0 | [0, 0] | 3 | 2 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['dev', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 1] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 1] | missing a | a: no cell with this key on this side | b: present | | | | | |
| method | 任务计划（规则生成） | 最短路径（Z3） | delay_cost | 0.6667 | [0, 2] | 3 | 2 | 任务计划（规则生成） | significance not reported: 1 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['dev', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 1] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 1] | missing a | a: no cell with this key on this side | b: present | | | | | |
| method | 任务计划（规则生成） | 最短路径（Z3） | mean_tardiness | 0.1111 | [0, 0.333] | 3 | 2 | 任务计划（规则生成） | significance not reported: 1 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['dev', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 1] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 1] | missing a | a: no cell with this key on this side | b: present | | | | | |
| method | 任务计划（规则生成） | 最短路径（Z3） | makespan | -0.6667 | [-1, 0] | 3 | 2 | 最短路径（Z3） | significance not reported: 2 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['dev', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 1] | missing a | a: no cell with this key on this side | b: present | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-plan-memory', 'scenario-default', 1] | missing a | a: no cell with this key on this side | b: present | | | | | |
| method | 任务计划（规则生成） | 模型辅助（替身） | goal_reached | -0.3333 | [-1, 0] | 3 | 0 | 任务计划（规则生成） | significance not reported: 1 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 模型辅助（替身） | steps_used | 15 | [0, 45] | 3 | 0 | 任务计划（规则生成） | significance not reported: 1 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 模型辅助（替身） | rejected_actions | 19.67 | [0, 59] | 3 | 0 | — | significance not reported: 1 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 模型辅助（替身） | effect_mismatches | -0.6667 | [-2, 0] | 3 | 0 | 模型辅助（替身） | significance not reported: 1 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 模型辅助（替身） | wall_seconds | 3.764 | [-0.004, 11.2] | 3 | 0 | — | significance not reported: 3 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 模型辅助（替身） | model_calls | — | — | 0 | 3 | — | no complete pairs (engineering) |
|  | incomplete pair ['dev', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 1] | missing a | a: NOT_APPLICABLE: strategy makes no model calls | b: present | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-observation-delay', 'scenario-default', 1] | missing a | a: NOT_APPLICABLE: strategy makes no model calls | b: present | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 1] | missing a | a: NOT_APPLICABLE: strategy makes no model calls | b: present | | | | | |
| method | 任务计划（规则生成） | 模型辅助（替身） | tokens | — | — | 0 | 3 | — | no complete pairs (engineering) |
|  | incomplete pair ['dev', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 1] | missing a | a: NOT_APPLICABLE: strategy makes no model calls | b: present | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-observation-delay', 'scenario-default', 1] | missing a | a: NOT_APPLICABLE: strategy makes no model calls | b: present | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 1] | missing a | a: NOT_APPLICABLE: strategy makes no model calls | b: present | | | | | |
| method | 任务计划（规则生成） | 模型辅助（替身） | orders_completed | -1 | [-3, 0] | 3 | 0 | 任务计划（规则生成） | significance not reported: 1 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 模型辅助（替身） | delay_cost | 36.67 | [0, 110] | 3 | 0 | 任务计划（规则生成） | significance not reported: 1 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 模型辅助（替身） | mean_tardiness | 6 | [0, 18] | 3 | 0 | 任务计划（规则生成） | significance not reported: 1 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 模型辅助（替身） | makespan | 0 | — | 2 | 1 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['dev', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 1] | missing b | a: present | b: MISSING: not all operations finished | | | | | |
| method | 任务计划（规则生成） | 规则（EDD） | goal_reached | 0 | [0, 0] | 3 | 0 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 规则（EDD） | steps_used | 10.67 | [0, 32] | 3 | 0 | 任务计划（规则生成） | significance not reported: 1 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 规则（EDD） | rejected_actions | 9.333 | [0, 28] | 3 | 0 | — | significance not reported: 1 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 规则（EDD） | effect_mismatches | 1 | [0, 3] | 3 | 0 | 任务计划（规则生成） | significance not reported: 1 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 规则（EDD） | wall_seconds | 2.8 | [0.004, 8.39] | 3 | 0 | — | significance not reported: 3 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 规则（EDD） | model_calls | — | — | 0 | 3 | — | no complete pairs (engineering) |
|  | incomplete pair ['dev', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-observation-delay', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
| method | 任务计划（规则生成） | 规则（EDD） | tokens | — | — | 0 | 3 | — | no complete pairs (engineering) |
|  | incomplete pair ['dev', 'sched-normal', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'no-observation-delay', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', 'ir-world', 'none', 'neutral-scheduling@1', 'none', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
| method | 任务计划（规则生成） | 规则（EDD） | orders_completed | 0 | [0, 0] | 3 | 0 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 规则（EDD） | delay_cost | 1.333 | [0, 4] | 3 | 0 | 任务计划（规则生成） | significance not reported: 1 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 规则（EDD） | mean_tardiness | 0.4444 | [0, 1.33] | 3 | 0 | 任务计划（规则生成） | significance not reported: 1 non-zero paired differences < 6 (engineering) |
| method | 任务计划（规则生成） | 规则（EDD） | makespan | 1.333 | [0, 4] | 3 | 0 | 任务计划（规则生成） | significance not reported: 1 non-zero paired differences < 6 (engineering) |
| mechanism | none | no-observation-delay | goal_reached | 0.2 | [0, 0.6] | 5 | 5 | no-observation-delay | significance not reported: 1 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['dev', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
| mechanism | none | no-observation-delay | steps_used | -23 | [-36, -10.2] | 5 | 5 | no-observation-delay | significance not reported: 4 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['dev', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
| mechanism | none | no-observation-delay | rejected_actions | -24.6 | [-42.6, -9.2] | 5 | 5 | — | significance not reported: 4 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['dev', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
| mechanism | none | no-observation-delay | effect_mismatches | -3 | [-4.4, -1.4] | 5 | 5 | no-observation-delay | significance not reported: 4 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['dev', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
| mechanism | none | no-observation-delay | wall_seconds | -11.29 | [-13.9, -7.28] | 5 | 5 | — | significance not reported: 5 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['dev', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
| mechanism | none | no-observation-delay | model_calls | -45 | — | 1 | 9 | — | significance not reported: 1 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['dev', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
| mechanism | none | no-observation-delay | tokens | 0 | — | 1 | 9 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['dev', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
| mechanism | none | no-observation-delay | orders_completed | 0.6 | [0, 1.8] | 5 | 5 | no-observation-delay | significance not reported: 1 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['dev', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
| mechanism | none | no-observation-delay | delay_cost | -23.6 | [-66.8, -1.2] | 5 | 5 | no-observation-delay | significance not reported: 4 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['dev', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
| mechanism | none | no-observation-delay | mean_tardiness | -4 | [-11.1, -0.2] | 5 | 5 | no-observation-delay | significance not reported: 4 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['dev', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
| mechanism | none | no-observation-delay | makespan | -1.5 | [-3.25, -0.25] | 4 | 6 | no-observation-delay | significance not reported: 3 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['dev', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing a | a: MISSING: not all operations finished | b: present | | | | | |
| mechanism | none | no-plan-memory | goal_reached | 0 | — | 2 | 8 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['dev', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
| mechanism | none | no-plan-memory | steps_used | 0 | — | 2 | 8 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['dev', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
| mechanism | none | no-plan-memory | rejected_actions | 0 | — | 2 | 8 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['dev', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
| mechanism | none | no-plan-memory | effect_mismatches | 0 | — | 2 | 8 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['dev', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
| mechanism | none | no-plan-memory | wall_seconds | 4.525 | — | 2 | 8 | — | significance not reported: 2 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['dev', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
| mechanism | none | no-plan-memory | model_calls | — | — | 0 | 10 | — | no complete pairs (engineering) |
|  | incomplete pair ['dev', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
| mechanism | none | no-plan-memory | tokens | — | — | 0 | 10 | — | no complete pairs (engineering) |
|  | incomplete pair ['dev', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '最短路径（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: NOT_APPLICABLE: strategy makes no model calls | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing both | a: NOT_APPLICABLE: strategy makes no model calls | b: no cell with this key on this side | | | | | |
| mechanism | none | no-plan-memory | orders_completed | 0 | — | 2 | 8 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['dev', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
| mechanism | none | no-plan-memory | delay_cost | 0 | — | 2 | 8 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['dev', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
| mechanism | none | no-plan-memory | mean_tardiness | 0 | — | 2 | 8 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['dev', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
| mechanism | none | no-plan-memory | makespan | 0 | — | 2 | 8 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['dev', 'sched-normal', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-normal', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '任务计划（规则生成）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '成本优化（Z3）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '模型辅助（替身）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing both | a: MISSING: not all operations finished | b: no cell with this key on this side | | | | | |
|  | incomplete pair ['dev', 'sched-state-delay', '规则（EDD）', 'ir-world', 'none', 'neutral-scheduling@1', 'scenario-default', 1] | missing b | a: present | b: no cell with this key on this side | | | | | |

## Metric sources

- `delay_cost`: evaluator (formal-lab.eval.generic) as recorded in the bundle
- `effect_mismatches`: evaluator (formal-lab.eval.generic) as recorded in the bundle
- `goal_reached`: evaluator (formal-lab.eval.generic) as recorded in the bundle
- `makespan`: evaluator (formal-lab.eval.generic) as recorded in the bundle
- `mean_tardiness`: evaluator (formal-lab.eval.generic) as recorded in the bundle
- `model_calls`: evaluator (formal-lab.eval.generic) as recorded in the bundle
- `orders_completed`: evaluator (formal-lab.eval.generic) as recorded in the bundle
- `rejected_actions`: evaluator (formal-lab.eval.generic) as recorded in the bundle
- `steps_used`: evaluator (formal-lab.eval.generic) as recorded in the bundle
- `tokens`: evaluator (formal-lab.eval.generic) as recorded in the bundle
- `wall_seconds`: evaluator (formal-lab.eval.generic) as recorded in the bundle
