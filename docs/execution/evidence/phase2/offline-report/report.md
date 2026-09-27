# Offline report: scheduling strategies and the observation-delay ablation

## Conclusions

- 36 of 37 bundle(s) verified (format, contract, digests, causality, required parts); 1 rejected and excluded
- [acceptance] 27 cell(s): 27 finished, 0 failed or cancelled, 0 not run; goal reached in 27 of 27; missing metrics: none
- [acceptance] method: Z3 有界规划 is better on delay_cost (mean paired difference -2.22, 95% CI [-4.44, -0.667], 9 pairs, 0 unpaired)
- [acceptance] method: Z3 有界规划 is better on mean_tardiness (mean paired difference -0.778, 95% CI [-1.41, -0.296], 9 pairs, 0 unpaired)
- [acceptance] method: Z3 有界规划 is better on makespan (mean paired difference -3, 95% CI [-4.22, -1.89], 9 pairs, 0 unpaired)
- [acceptance] mechanism: no-observation-delay is better on steps_used (mean paired difference +15.2, 95% CI [+7.44, +23.9], 9 pairs, 9 unpaired)
- [acceptance] mechanism: no-observation-delay is better on effect_mismatches (mean paired difference +3.11, 95% CI [+2.44, +3.89], 9 pairs, 9 unpaired)
- [acceptance] mechanism: no-observation-delay is better on delay_cost (mean paired difference +3.67, 95% CI [+1.44, +6.33], 9 pairs, 9 unpaired)
- [acceptance] mechanism: no-observation-delay is better on mean_tardiness (mean paired difference +0.889, 95% CI [+0.333, +1.59], 9 pairs, 9 unpaired)
- [acceptance] mechanism: no-observation-delay is better on makespan (mean paired difference +2.67, 95% CI [+1.33, +4.11], 9 pairs, 9 unpaired)
- [dev] 9 cell(s): 9 finished, 0 failed or cancelled, 0 not run; goal reached in 9 of 9; missing metrics: none
- [dev] method: Z3 有界规划 is better on steps_used (mean paired difference -5.33, 95% CI [-14, -1], 3 pairs, 0 unpaired)
- [dev] method: Z3 有界规划 is better on makespan (mean paired difference -2, 95% CI [-4, -1], 3 pairs, 0 unpaired)
- [dev] mechanism: no-observation-delay is better on effect_mismatches (mean paired difference +3.67, 95% CI [+2, +5], 3 pairs, 3 unpaired)

## Split `acceptance`

Denominator: 27 cells — run status {'SUCCEEDED': 27}; goal not reached: 0; missing metrics {'goal_reached': 0, 'steps_used': 0, 'rejected_actions': 0, 'effect_mismatches': 0, 'wall_seconds': 0, 'model_calls': 0, 'tokens': 0, 'orders_completed': 0, 'delay_cost': 0, 'mean_tardiness': 0, 'makespan': 0}.

### Per scenario (unit: one seed of one scenario)

| scenario | participants | backend | rules | model | ablation | budget | metric | value | 95% CI | n | missing | source |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 正常调度 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 1 | [1, 1] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 15.67 | [14, 17] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 0.2833 | [0.26, 0.306] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | [3, 3] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 1 | [0, 2] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 0.3333 | [0, 0.667] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 8.667 | [7, 10] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 1 | [1, 1] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 13.33 | [13, 14] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 2.655 | [2.08, 3.48] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | [3, 3] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 6.333 | [6, 7] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 1 | [1, 1] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 15.67 | [14, 17] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 0.3133 | [0.274, 0.345] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | [3, 3] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 1 | [0, 2] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 0.3333 | [0, 0.667] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 8.667 | [7, 10] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | goal_reached | 1 | [1, 1] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | steps_used | 15.67 | [14, 17] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | rejected_actions | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | effect_mismatches | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | wall_seconds | 0.231 | [0.198, 0.266] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | orders_completed | 3 | [3, 3] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | delay_cost | 1 | [0, 2] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | mean_tardiness | 0.3333 | [0, 0.667] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | makespan | 8.667 | [7, 10] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 1 | [1, 1] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 42.33 | [25, 53] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 21.67 | [7, 30] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 4.333 | [3, 5] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 14.23 | [7.42, 18.6] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | [3, 3] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 8.333 | [5, 14] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 2.333 | [1.33, 3.67] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 13.67 | [11, 16] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | goal_reached | 1 | [1, 1] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | steps_used | 13.33 | [13, 14] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | rejected_actions | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | effect_mismatches | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | wall_seconds | 0.2367 | [0.227, 0.252] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | orders_completed | 3 | [3, 3] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | delay_cost | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | mean_tardiness | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | makespan | 6.333 | [6, 7] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 1 | [1, 1] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 32.33 | [32, 33] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 16 | [15, 17] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 2.667 | [2, 3] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 16.67 | [15.4, 17.7] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | [3, 3] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 3.667 | [1, 6] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 0.6667 | [0.333, 1] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 9.333 | [9, 10] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | goal_reached | 1 | [1, 1] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | steps_used | 15.67 | [14, 17] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | rejected_actions | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | effect_mismatches | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | wall_seconds | 0.2907 | [0.256, 0.316] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
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
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 4.902 | [4.61, 5.32] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | [3, 3] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 1 | [0, 2] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 0.3333 | [0, 0.667] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 8.667 | [7, 10] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |

### Pooled across scenarios (unit: scenario; cluster bootstrap)

| participants | backend | rules | model | ablation | budget | metric | value | 95% CI | scenarios | n |
|---|---|---|---|---|---|---|---|---|---|---|
| EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | goal_reached | 1 | — | 1 | 3 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | steps_used | 15.67 | — | 1 | 3 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | rejected_actions | 0 | — | 1 | 3 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | effect_mismatches | 0 | — | 1 | 3 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | wall_seconds | 0.231 | — | 1 | 3 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | model_calls | — | — | 0 | 0 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | tokens | — | — | 0 | 0 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | orders_completed | 3 | — | 1 | 3 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | delay_cost | 1 | — | 1 | 3 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | mean_tardiness | 0.3333 | — | 1 | 3 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | makespan | 8.667 | — | 1 | 3 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 1 | [1, 1] | 2 | 6 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 29 | [15.7, 42.3] | 2 | 6 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 10.83 | [0, 21.7] | 2 | 6 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 2.167 | [0, 4.33] | 2 | 6 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 7.258 | [0.283, 14.2] | 2 | 6 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | [3, 3] | 2 | 6 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 4.667 | [1, 8.33] | 2 | 6 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 1.333 | [0.333, 2.33] | 2 | 6 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 11.17 | [8.67, 13.7] | 2 | 6 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | goal_reached | 1 | — | 1 | 3 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | steps_used | 13.33 | — | 1 | 3 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | rejected_actions | 0 | — | 1 | 3 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | effect_mismatches | 0 | — | 1 | 3 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | wall_seconds | 0.2367 | — | 1 | 3 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | model_calls | — | — | 0 | 0 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | tokens | — | — | 0 | 0 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | orders_completed | 3 | — | 1 | 3 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | delay_cost | 0 | — | 1 | 3 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | mean_tardiness | 0 | — | 1 | 3 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | makespan | 6.333 | — | 1 | 3 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 1 | [1, 1] | 2 | 6 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 22.83 | [13.3, 32.3] | 2 | 6 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 8 | [0, 16] | 2 | 6 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 1.333 | [0, 2.67] | 2 | 6 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 9.665 | [2.66, 16.7] | 2 | 6 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | [3, 3] | 2 | 6 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 1.833 | [0, 3.67] | 2 | 6 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 0.3333 | [0, 0.667] | 2 | 6 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 7.833 | [6.33, 9.33] | 2 | 6 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | goal_reached | 1 | — | 1 | 3 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | steps_used | 15.67 | — | 1 | 3 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | rejected_actions | 0 | — | 1 | 3 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | effect_mismatches | 0 | — | 1 | 3 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | wall_seconds | 0.2907 | — | 1 | 3 |
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
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 2.608 | [0.313, 4.9] | 2 | 6 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | [3, 3] | 2 | 6 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 1 | [1, 1] | 2 | 6 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 0.3333 | [0.333, 0.333] | 2 | 6 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 8.667 | [8.67, 8.67] | 2 | 6 |

### Paired comparisons (one dimension at a time)

| kind | A | B | metric | mean B−A | 95% CI | pairs | unpaired | better | test |
|---|---|---|---|---|---|---|---|---|---|
| method | EDD 规则 | Z3 有界规划 | goal_reached | 0 | [0, 0] | 9 | 0 | — | significance not reported: 0 non-zero paired differences < 6 |
| method | EDD 规则 | Z3 有界规划 | steps_used | -4.889 | [-10.4, 0.111] | 9 | 0 | Z3 有界规划 | p=0.0781 |
| method | EDD 规则 | Z3 有界规划 | rejected_actions | -1.889 | [-6.22, 2.22] | 9 | 0 | — | significance not reported: 3 non-zero paired differences < 6 |
| method | EDD 规则 | Z3 有界规划 | effect_mismatches | -0.5556 | [-1.33, 0] | 9 | 0 | Z3 有界规划 | significance not reported: 2 non-zero paired differences < 6 |
| method | EDD 规则 | Z3 有界规划 | wall_seconds | 1.607 | [-0.0761, 3.88] | 9 | 0 | — | p=0.25 |
| method | EDD 规则 | Z3 有界规划 | orders_completed | 0 | [0, 0] | 9 | 0 | — | significance not reported: 0 non-zero paired differences < 6 |
| method | EDD 规则 | Z3 有界规划 | delay_cost | -2.222 | [-4.44, -0.667] | 9 | 0 | Z3 有界规划 | p=0.0312 |
| method | EDD 规则 | Z3 有界规划 | mean_tardiness | -0.7778 | [-1.41, -0.296] | 9 | 0 | Z3 有界规划 | p=0.0156 |
| method | EDD 规则 | Z3 有界规划 | makespan | -3 | [-4.22, -1.89] | 9 | 0 | Z3 有界规划 | p=0.00391 |
| method | EDD 规则 | 任务计划（规则生成） | goal_reached | 0 | [0, 0] | 9 | 0 | — | significance not reported: 0 non-zero paired differences < 6 |
| method | EDD 规则 | 任务计划（规则生成） | steps_used | -8.889 | [-19, 0] | 9 | 0 | 任务计划（规则生成） | significance not reported: 3 non-zero paired differences < 6 |
| method | EDD 规则 | 任务计划（规则生成） | rejected_actions | -7.222 | [-16, 0] | 9 | 0 | — | significance not reported: 3 non-zero paired differences < 6 |
| method | EDD 规则 | 任务计划（规则生成） | effect_mismatches | -0.6667 | [-1.44, 0] | 9 | 0 | 任务计划（规则生成） | significance not reported: 3 non-zero paired differences < 6 |
| method | EDD 规则 | 任务计划（规则生成） | wall_seconds | -3.08 | [-6.87, 0.0368] | 9 | 0 | — | p=0.91 |
| method | EDD 规则 | 任务计划（规则生成） | orders_completed | 0 | [0, 0] | 9 | 0 | — | significance not reported: 0 non-zero paired differences < 6 |
| method | EDD 规则 | 任务计划（规则生成） | delay_cost | -2.444 | [-5.11, 0] | 9 | 0 | 任务计划（规则生成） | significance not reported: 3 non-zero paired differences < 6 |
| method | EDD 规则 | 任务计划（规则生成） | mean_tardiness | -0.6667 | [-1.37, 0] | 9 | 0 | 任务计划（规则生成） | significance not reported: 3 non-zero paired differences < 6 |
| method | EDD 规则 | 任务计划（规则生成） | makespan | -1.667 | [-3.33, 0] | 9 | 0 | 任务计划（规则生成） | significance not reported: 3 non-zero paired differences < 6 |
| mechanism | no-observation-delay | none | goal_reached | 0 | [0, 0] | 9 | 9 | — | significance not reported: 0 non-zero paired differences < 6 |
| mechanism | no-observation-delay | none | steps_used | 15.22 | [7.44, 23.9] | 9 | 9 | no-observation-delay | p=0.0312 |
| mechanism | no-observation-delay | none | rejected_actions | 12.56 | [5.89, 19.9] | 9 | 9 | — | p=0.0312 |
| mechanism | no-observation-delay | none | effect_mismatches | 3.111 | [2.44, 3.89] | 9 | 9 | no-observation-delay | p=0.00391 |
| mechanism | no-observation-delay | none | wall_seconds | 11.68 | [7.94, 15.5] | 9 | 9 | — | p=0.00391 |
| mechanism | no-observation-delay | none | orders_completed | 0 | [0, 0] | 9 | 9 | — | significance not reported: 0 non-zero paired differences < 6 |
| mechanism | no-observation-delay | none | delay_cost | 3.667 | [1.44, 6.33] | 9 | 9 | no-observation-delay | p=0.0312 |
| mechanism | no-observation-delay | none | mean_tardiness | 0.8889 | [0.333, 1.59] | 9 | 9 | no-observation-delay | p=0.0312 |
| mechanism | no-observation-delay | none | makespan | 2.667 | [1.33, 4.11] | 9 | 9 | no-observation-delay | p=0.0312 |

## Split `dev`

Denominator: 9 cells — run status {'SUCCEEDED': 9}; goal not reached: 0; missing metrics {'goal_reached': 0, 'steps_used': 0, 'rejected_actions': 0, 'effect_mismatches': 0, 'wall_seconds': 0, 'model_calls': 0, 'tokens': 0, 'orders_completed': 0, 'delay_cost': 0, 'mean_tardiness': 0, 'makespan': 0}.

### Per scenario (unit: one seed of one scenario)

| scenario | participants | backend | rules | model | ablation | budget | metric | value | 95% CI | n | missing | source |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 正常调度 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 1 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 15 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 0.286 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 8 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 1 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 14 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 5.635 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 7 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 1 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 15 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 0.28 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 正常调度 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 8 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | goal_reached | 1 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | steps_used | 15 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | rejected_actions | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | effect_mismatches | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | wall_seconds | 0.211 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | orders_completed | 3 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | delay_cost | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | mean_tardiness | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | makespan | 8 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 1 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 47 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 28 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 5 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 17.68 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 4 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 1.333 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 12 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | goal_reached | 1 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | steps_used | 14 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | rejected_actions | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | effect_mismatches | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | wall_seconds | 0.275 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | orders_completed | 3 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | delay_cost | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | mean_tardiness | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | makespan | 7 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 1 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 33 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 18 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 4 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 18.96 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 2 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 0.3333 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 8 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | goal_reached | 1 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | steps_used | 15 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | rejected_actions | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | effect_mismatches | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | wall_seconds | 0.288 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
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
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 4.255 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 状态延迟 | 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 8 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |

### Pooled across scenarios (unit: scenario; cluster bootstrap)

| participants | backend | rules | model | ablation | budget | metric | value | 95% CI | scenarios | n |
|---|---|---|---|---|---|---|---|---|---|---|
| EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | goal_reached | 1 | — | 1 | 1 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | steps_used | 15 | — | 1 | 1 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | rejected_actions | 0 | — | 1 | 1 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | effect_mismatches | 0 | — | 1 | 1 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | wall_seconds | 0.211 | — | 1 | 1 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | model_calls | — | — | 0 | 0 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | tokens | — | — | 0 | 0 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | orders_completed | 3 | — | 1 | 1 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | delay_cost | 0 | — | 1 | 1 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | mean_tardiness | 0 | — | 1 | 1 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | makespan | 8 | — | 1 | 1 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 1 | [1, 1] | 2 | 2 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 31 | [15, 47] | 2 | 2 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 14 | [0, 28] | 2 | 2 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 2.5 | [0, 5] | 2 | 2 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 8.984 | [0.286, 17.7] | 2 | 2 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | [3, 3] | 2 | 2 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 2 | [0, 4] | 2 | 2 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 0.6667 | [0, 1.33] | 2 | 2 |
| EDD 规则 | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 10 | [8, 12] | 2 | 2 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | goal_reached | 1 | — | 1 | 1 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | steps_used | 14 | — | 1 | 1 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | rejected_actions | 0 | — | 1 | 1 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | effect_mismatches | 0 | — | 1 | 1 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | wall_seconds | 0.275 | — | 1 | 1 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | model_calls | — | — | 0 | 0 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | tokens | — | — | 0 | 0 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | orders_completed | 3 | — | 1 | 1 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | delay_cost | 0 | — | 1 | 1 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | mean_tardiness | 0 | — | 1 | 1 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | makespan | 7 | — | 1 | 1 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | goal_reached | 1 | [1, 1] | 2 | 2 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | steps_used | 23.5 | [14, 33] | 2 | 2 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | rejected_actions | 9 | [0, 18] | 2 | 2 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | effect_mismatches | 2 | [0, 4] | 2 | 2 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 12.3 | [5.63, 19] | 2 | 2 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | [3, 3] | 2 | 2 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 1 | [0, 2] | 2 | 2 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 0.1667 | [0, 0.333] | 2 | 2 |
| Z3 有界规划 | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 7.5 | [7, 8] | 2 | 2 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | goal_reached | 1 | — | 1 | 1 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | steps_used | 15 | — | 1 | 1 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | rejected_actions | 0 | — | 1 | 1 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | effect_mismatches | 0 | — | 1 | 1 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | no-observation-delay | scenario-default | wall_seconds | 0.288 | — | 1 | 1 |
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
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | wall_seconds | 2.268 | [0.28, 4.25] | 2 | 2 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | model_calls | — | — | 0 | 0 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | tokens | — | — | 0 | 0 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | orders_completed | 3 | [3, 3] | 2 | 2 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | delay_cost | 0 | [0, 0] | 2 | 2 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | mean_tardiness | 0 | [0, 0] | 2 | 2 |
| 任务计划（规则生成） | ir-world | none | neutral-scheduling@1 | none | scenario-default | makespan | 8 | [8, 8] | 2 | 2 |

### Paired comparisons (one dimension at a time)

| kind | A | B | metric | mean B−A | 95% CI | pairs | unpaired | better | test |
|---|---|---|---|---|---|---|---|---|---|
| method | EDD 规则 | Z3 有界规划 | goal_reached | 0 | [0, 0] | 3 | 0 | — | significance not reported: 0 non-zero paired differences < 6 |
| method | EDD 规则 | Z3 有界规划 | steps_used | -5.333 | [-14, -1] | 3 | 0 | Z3 有界规划 | significance not reported: 3 non-zero paired differences < 6 |
| method | EDD 规则 | Z3 有界规划 | rejected_actions | -3.333 | [-10, 0] | 3 | 0 | — | significance not reported: 1 non-zero paired differences < 6 |
| method | EDD 规则 | Z3 有界规划 | effect_mismatches | -0.3333 | [-1, 0] | 3 | 0 | Z3 有界规划 | significance not reported: 1 non-zero paired differences < 6 |
| method | EDD 规则 | Z3 有界规划 | wall_seconds | 2.232 | [0.064, 5.35] | 3 | 0 | — | significance not reported: 3 non-zero paired differences < 6 |
| method | EDD 规则 | Z3 有界规划 | orders_completed | 0 | [0, 0] | 3 | 0 | — | significance not reported: 0 non-zero paired differences < 6 |
| method | EDD 规则 | Z3 有界规划 | delay_cost | -0.6667 | [-2, 0] | 3 | 0 | Z3 有界规划 | significance not reported: 1 non-zero paired differences < 6 |
| method | EDD 规则 | Z3 有界规划 | mean_tardiness | -0.3333 | [-1, 0] | 3 | 0 | Z3 有界规划 | significance not reported: 1 non-zero paired differences < 6 |
| method | EDD 规则 | Z3 有界规划 | makespan | -2 | [-4, -1] | 3 | 0 | Z3 有界规划 | significance not reported: 3 non-zero paired differences < 6 |
| method | EDD 规则 | 任务计划（规则生成） | goal_reached | 0 | [0, 0] | 3 | 0 | — | significance not reported: 0 non-zero paired differences < 6 |
| method | EDD 规则 | 任务计划（规则生成） | steps_used | -10.67 | [-32, 0] | 3 | 0 | 任务计划（规则生成） | significance not reported: 1 non-zero paired differences < 6 |
| method | EDD 规则 | 任务计划（规则生成） | rejected_actions | -9.333 | [-28, 0] | 3 | 0 | — | significance not reported: 1 non-zero paired differences < 6 |
| method | EDD 规则 | 任务计划（规则生成） | effect_mismatches | -1 | [-3, 0] | 3 | 0 | 任务计划（规则生成） | significance not reported: 1 non-zero paired differences < 6 |
| method | EDD 规则 | 任务计划（规则生成） | wall_seconds | -4.452 | [-13.4, 0.077] | 3 | 0 | — | significance not reported: 3 non-zero paired differences < 6 |
| method | EDD 规则 | 任务计划（规则生成） | orders_completed | 0 | [0, 0] | 3 | 0 | — | significance not reported: 0 non-zero paired differences < 6 |
| method | EDD 规则 | 任务计划（规则生成） | delay_cost | -1.333 | [-4, 0] | 3 | 0 | 任务计划（规则生成） | significance not reported: 1 non-zero paired differences < 6 |
| method | EDD 规则 | 任务计划（规则生成） | mean_tardiness | -0.4444 | [-1.33, 0] | 3 | 0 | 任务计划（规则生成） | significance not reported: 1 non-zero paired differences < 6 |
| method | EDD 规则 | 任务计划（规则生成） | makespan | -1.333 | [-4, 0] | 3 | 0 | 任务计划（规则生成） | significance not reported: 1 non-zero paired differences < 6 |
| mechanism | no-observation-delay | none | goal_reached | 0 | [0, 0] | 3 | 3 | — | significance not reported: 0 non-zero paired differences < 6 |
| mechanism | no-observation-delay | none | steps_used | 17 | [0, 32] | 3 | 3 | no-observation-delay | significance not reported: 2 non-zero paired differences < 6 |
| mechanism | no-observation-delay | none | rejected_actions | 15.33 | [0, 28] | 3 | 3 | — | significance not reported: 2 non-zero paired differences < 6 |
| mechanism | no-observation-delay | none | effect_mismatches | 3.667 | [2, 5] | 3 | 3 | no-observation-delay | significance not reported: 3 non-zero paired differences < 6 |
| mechanism | no-observation-delay | none | wall_seconds | 13.38 | [3.97, 18.7] | 3 | 3 | — | significance not reported: 3 non-zero paired differences < 6 |
| mechanism | no-observation-delay | none | orders_completed | 0 | [0, 0] | 3 | 3 | — | significance not reported: 0 non-zero paired differences < 6 |
| mechanism | no-observation-delay | none | delay_cost | 2 | [0, 4] | 3 | 3 | no-observation-delay | significance not reported: 2 non-zero paired differences < 6 |
| mechanism | no-observation-delay | none | mean_tardiness | 0.5556 | [0, 1.33] | 3 | 3 | no-observation-delay | significance not reported: 2 non-zero paired differences < 6 |
| mechanism | no-observation-delay | none | makespan | 1.667 | [0, 4] | 3 | 3 | no-observation-delay | significance not reported: 2 non-zero paired differences < 6 |

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

## Rejected bundles

- `run_off_corrupted.replay.zip`: unreadable: error: Error -3 while decompressing data: invalid distance too far back
