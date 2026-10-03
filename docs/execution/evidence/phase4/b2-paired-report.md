# Matrix CAGE 4 蓝方方法配对比较

## Conclusions

- [acceptance] 18 cell(s): 18 finished, 0 failed or cancelled, 0 not run; goal reached in 18 of 18; missing metrics: recovery_time 13
- [acceptance] success 18/18 = 100% (denominator: every planned cell); timed out 0, reused 0, new runs 18
- [acceptance] 2 comparison(s) have no complete pairs (the metric is missing on one side or the dimension varies only where the other does not) — no conclusion from them
- [acceptance] method: *=A 官方基线 · SleepAgent 映射 (×5) is better on rejected_actions (mean paired difference +75.7, 95% CI [+58.7, +90.8], 6 pairs, 0 unpaired)
- [acceptance] method: *=C 平台规则 · 告警响应 (×5) is better on red_footholds_final (mean paired difference -3, 95% CI [-5.5, -0.333], 6 pairs, 0 unpaired) — engineering reading (small sample)
- [acceptance] method: *=C 平台规则 · 告警响应 (×5) is better on red_foothold_host_steps (mean paired difference -84.8, 95% CI [-140, -33.2], 6 pairs, 0 unpaired) — engineering reading (small sample)
- [acceptance] method: *=C 平台规则 · 告警响应 (×5) is better on unrecovered_hosts (mean paired difference -3, 95% CI [-5.5, -0.333], 6 pairs, 0 unpaired) — engineering reading (small sample)
- [acceptance] method: *=A 官方基线 · SleepAgent 映射 (×5) is better on blue_actions_not_started (mean paired difference +75.7, 95% CI [+58.7, +90.8], 6 pairs, 0 unpaired)

## Split `acceptance`

Denominator: 18 cells — run status {'SUCCEEDED': 18}; goal not reached: 0; missing metrics {'goal_reached': 0, 'steps_used': 0, 'rejected_actions': 0, 'effect_mismatches': 0, 'model_calls': 0, 'tokens': 0, 'wall_seconds': 0, 'native_blue_reward': 0, 'green_success_rate': 0, 'green_failed_actions': 0, 'red_footholds_final': 0, 'red_foothold_host_steps': 0, 'recovery_time': 13, 'unrecovered_hosts': 0, 'blue_actions_not_started': 0, 'blue_agent_count': 0}.

Success: 18/18 (goal reached / every planned cell of this split (fixed before the runs; failed, cancelled, timed-out and not-run cells count as not reached)); finished only 18/18. Timed out: 0. Reused: 0 (—); new runs 18; sampling {'DETERMINISTIC': 18}.

### Per scenario (unit: one seed of one scenario)

| scenario | participants | backend | rules | model | ablation | budget | metric | value | 95% CI | n | missing | source |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CAGE 4 · holdout · 687a | *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | goal_reached | 1 | [0.439, 1] | 3 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · holdout · 687a | *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | steps_used | 495 | [495, 495] | 3 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · holdout · 687a | *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | rejected_actions | 0 | [0, 0] | 3 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · holdout · 687a | *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | effect_mismatches | 0 | [0, 0] | 3 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · holdout · 687a | *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | model_calls | — | — | 0 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · holdout · 687a | *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | tokens | — | — | 0 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · holdout · 687a | *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | wall_seconds | 50.17 | [49.2, 51] | 3 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · holdout · 687a | *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | native_blue_reward | 0 | [0, 0] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · holdout · 687a | *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | green_success_rate | 0.9996 | [0.999, 1] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · holdout · 687a | *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | green_failed_actions | 1.333 | [0, 4] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · holdout · 687a | *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | red_footholds_final | 42.67 | [39, 47] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · holdout · 687a | *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | red_foothold_host_steps | 2184 | [2.17e+03, 2.22e+03] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · holdout · 687a | *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | recovery_time | — | — | 0 | 3 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · holdout · 687a | *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | unrecovered_hosts | 42.67 | [39, 47] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · holdout · 687a | *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | blue_actions_not_started | 0 | [0, 0] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · holdout · 687a | *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | blue_agent_count | 5 | [5, 5] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · holdout · 687a | *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | goal_reached | 1 | [0.439, 1] | 3 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · holdout · 687a | *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | steps_used | 495 | [495, 495] | 3 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · holdout · 687a | *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | rejected_actions | 0 | [0, 0] | 3 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · holdout · 687a | *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | effect_mismatches | 0 | [0, 0] | 3 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · holdout · 687a | *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | model_calls | — | — | 0 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · holdout · 687a | *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | tokens | — | — | 0 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · holdout · 687a | *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | wall_seconds | 53.36 | [52.5, 54.8] | 3 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · holdout · 687a | *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | native_blue_reward | 0 | [0, 0] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · holdout · 687a | *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | green_success_rate | 0.9996 | [0.999, 1] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · holdout · 687a | *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | green_failed_actions | 1.333 | [0, 4] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · holdout · 687a | *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | red_footholds_final | 42.67 | [39, 47] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · holdout · 687a | *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | red_foothold_host_steps | 2184 | [2.17e+03, 2.22e+03] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · holdout · 687a | *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | recovery_time | — | — | 0 | 3 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · holdout · 687a | *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | unrecovered_hosts | 42.67 | [39, 47] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · holdout · 687a | *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | blue_actions_not_started | 0 | [0, 0] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · holdout · 687a | *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | blue_agent_count | 5 | [5, 5] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · holdout · 687a | *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | goal_reached | 1 | [0.439, 1] | 3 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · holdout · 687a | *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | steps_used | 495 | [495, 495] | 3 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · holdout · 687a | *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | rejected_actions | 93 | [86, 102] | 3 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · holdout · 687a | *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | effect_mismatches | 0 | [0, 0] | 3 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · holdout · 687a | *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | model_calls | — | — | 0 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · holdout · 687a | *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | tokens | — | — | 0 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · holdout · 687a | *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | wall_seconds | 51.75 | [50.8, 53.3] | 3 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · holdout · 687a | *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | native_blue_reward | -7.667 | [-10, -6] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · holdout · 687a | *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | green_success_rate | 1 | [1, 1] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · holdout · 687a | *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | green_failed_actions | 0 | [0, 0] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · holdout · 687a | *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | red_footholds_final | 38 | [35, 40] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · holdout · 687a | *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | red_foothold_host_steps | 2079 | [2.05e+03, 2.1e+03] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · holdout · 687a | *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | recovery_time | 28.79 | [26.7, 32.2] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · holdout · 687a | *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | unrecovered_hosts | 38 | [35, 40] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · holdout · 687a | *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | blue_actions_not_started | 93 | [86, 102] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · holdout · 687a | *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | blue_agent_count | 5 | [5, 5] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · dev · 8f9b | *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | goal_reached | 1 | [0.439, 1] | 3 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · dev · 8f9b | *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | steps_used | 495 | [495, 495] | 3 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · dev · 8f9b | *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | rejected_actions | 0 | [0, 0] | 3 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · dev · 8f9b | *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | effect_mismatches | 0 | [0, 0] | 3 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · dev · 8f9b | *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | model_calls | — | — | 0 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · dev · 8f9b | *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | tokens | — | — | 0 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · dev · 8f9b | *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | wall_seconds | 50.37 | [49, 51.6] | 3 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · dev · 8f9b | *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | native_blue_reward | -66 | [-90, -21] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · dev · 8f9b | *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | green_success_rate | 0.9947 | [0.992, 0.998] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · dev · 8f9b | *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | green_failed_actions | 19 | [6, 30] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · dev · 8f9b | *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | red_footholds_final | 33.33 | [26, 38] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · dev · 8f9b | *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | red_foothold_host_steps | 1512 | [1.24e+03, 1.8e+03] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · dev · 8f9b | *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | recovery_time | — | — | 0 | 3 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · dev · 8f9b | *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | unrecovered_hosts | 33.33 | [26, 38] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · dev · 8f9b | *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | blue_actions_not_started | 0 | [0, 0] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · dev · 8f9b | *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | blue_agent_count | 5 | [5, 5] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · dev · 8f9b | *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | goal_reached | 1 | [0.439, 1] | 3 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · dev · 8f9b | *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | steps_used | 495 | [495, 495] | 3 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · dev · 8f9b | *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | rejected_actions | 0 | [0, 0] | 3 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · dev · 8f9b | *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | effect_mismatches | 0 | [0, 0] | 3 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · dev · 8f9b | *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | model_calls | — | — | 0 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · dev · 8f9b | *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | tokens | — | — | 0 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · dev · 8f9b | *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | wall_seconds | 50.69 | [49.8, 51.7] | 3 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · dev · 8f9b | *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | native_blue_reward | -66 | [-90, -21] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · dev · 8f9b | *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | green_success_rate | 0.9947 | [0.992, 0.998] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · dev · 8f9b | *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | green_failed_actions | 19 | [6, 30] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · dev · 8f9b | *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | red_footholds_final | 33.33 | [26, 38] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · dev · 8f9b | *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | red_foothold_host_steps | 1512 | [1.24e+03, 1.8e+03] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · dev · 8f9b | *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | recovery_time | — | — | 0 | 3 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · dev · 8f9b | *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | unrecovered_hosts | 33.33 | [26, 38] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · dev · 8f9b | *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | blue_actions_not_started | 0 | [0, 0] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · dev · 8f9b | *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | blue_agent_count | 5 | [5, 5] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · dev · 8f9b | *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | goal_reached | 1 | [0.439, 1] | 3 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · dev · 8f9b | *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | steps_used | 495 | [495, 495] | 3 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · dev · 8f9b | *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | rejected_actions | 58.33 | [40, 73] | 3 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · dev · 8f9b | *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | effect_mismatches | 0 | [0, 0] | 3 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · dev · 8f9b | *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | model_calls | — | — | 0 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · dev · 8f9b | *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | tokens | — | — | 0 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · dev · 8f9b | *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | wall_seconds | 49.97 | [48.9, 51.3] | 3 | 0 | evaluator formal-lab.eval.generic |
| CAGE 4 · dev · 8f9b | *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | native_blue_reward | -69 | [-120, -21] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · dev · 8f9b | *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | green_success_rate | 0.9943 | [0.992, 0.997] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · dev · 8f9b | *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | green_failed_actions | 20.33 | [11, 30] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · dev · 8f9b | *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | red_footholds_final | 32 | [26, 38] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · dev · 8f9b | *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | red_foothold_host_steps | 1447 | [1.24e+03, 1.63e+03] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · dev · 8f9b | *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | recovery_time | 23.75 | — | 2 | 1 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · dev · 8f9b | *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | unrecovered_hosts | 32 | [26, 38] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · dev · 8f9b | *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | blue_actions_not_started | 58.33 | [40, 73] | 3 | 0 | evaluator formal-lab.cage4.metrics |
| CAGE 4 · dev · 8f9b | *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | blue_agent_count | 5 | [5, 5] | 3 | 0 | evaluator formal-lab.cage4.metrics |

### Pooled across scenarios (unit: scenario; cluster bootstrap)

| participants | backend | rules | model | ablation | budget | metric | value | 95% CI | scenarios | n |
|---|---|---|---|---|---|---|---|---|---|---|
| *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | goal_reached | 1 | [1, 1] | 2 | 6 |
| *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | steps_used | 495 | [495, 495] | 2 | 6 |
| *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | rejected_actions | 0 | [0, 0] | 2 | 6 |
| *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | effect_mismatches | 0 | [0, 0] | 2 | 6 |
| *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | model_calls | — | — | 0 | 0 |
| *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | tokens | — | — | 0 | 0 |
| *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | wall_seconds | 50.27 | [50.2, 50.4] | 2 | 6 |
| *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | native_blue_reward | -33 | [-66, 0] | 2 | 6 |
| *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | green_success_rate | 0.9971 | [0.995, 1] | 2 | 6 |
| *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | green_failed_actions | 10.17 | [1.33, 19] | 2 | 6 |
| *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | red_footholds_final | 38 | [33.3, 42.7] | 2 | 6 |
| *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | red_foothold_host_steps | 1848 | [1.51e+03, 2.18e+03] | 2 | 6 |
| *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | recovery_time | — | — | 0 | 0 |
| *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | unrecovered_hosts | 38 | [33.3, 42.7] | 2 | 6 |
| *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | blue_actions_not_started | 0 | [0, 0] | 2 | 6 |
| *=A 官方基线 · SleepAgent 映射 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | blue_agent_count | 5 | [5, 5] | 2 | 6 |
| *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | goal_reached | 1 | [1, 1] | 2 | 6 |
| *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | steps_used | 495 | [495, 495] | 2 | 6 |
| *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | rejected_actions | 0 | [0, 0] | 2 | 6 |
| *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | effect_mismatches | 0 | [0, 0] | 2 | 6 |
| *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | model_calls | — | — | 0 | 0 |
| *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | tokens | — | — | 0 | 0 |
| *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | wall_seconds | 52.02 | [50.7, 53.4] | 2 | 6 |
| *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | native_blue_reward | -33 | [-66, 0] | 2 | 6 |
| *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | green_success_rate | 0.9971 | [0.995, 1] | 2 | 6 |
| *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | green_failed_actions | 10.17 | [1.33, 19] | 2 | 6 |
| *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | red_footholds_final | 38 | [33.3, 42.7] | 2 | 6 |
| *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | red_foothold_host_steps | 1848 | [1.51e+03, 2.18e+03] | 2 | 6 |
| *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | recovery_time | — | — | 0 | 0 |
| *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | unrecovered_hosts | 38 | [33.3, 42.7] | 2 | 6 |
| *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | blue_actions_not_started | 0 | [0, 0] | 2 | 6 |
| *=B 原生映射 · MonitorAgent (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | blue_agent_count | 5 | [5, 5] | 2 | 6 |
| *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | goal_reached | 1 | [1, 1] | 2 | 6 |
| *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | steps_used | 495 | [495, 495] | 2 | 6 |
| *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | rejected_actions | 75.67 | [58.3, 93] | 2 | 6 |
| *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | effect_mismatches | 0 | [0, 0] | 2 | 6 |
| *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | model_calls | — | — | 0 | 0 |
| *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | tokens | — | — | 0 | 0 |
| *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | wall_seconds | 50.86 | [50, 51.7] | 2 | 6 |
| *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | native_blue_reward | -38.33 | [-69, -7.67] | 2 | 6 |
| *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | green_success_rate | 0.9971 | [0.994, 1] | 2 | 6 |
| *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | green_failed_actions | 10.17 | [0, 20.3] | 2 | 6 |
| *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | red_footholds_final | 35 | [32, 38] | 2 | 6 |
| *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | red_foothold_host_steps | 1763 | [1.45e+03, 2.08e+03] | 2 | 6 |
| *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | recovery_time | 26.27 | [23.8, 28.8] | 2 | 5 |
| *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | unrecovered_hosts | 35 | [32, 38] | 2 | 6 |
| *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | blue_actions_not_started | 75.67 | [58.3, 93] | 2 | 6 |
| *=C 平台规则 · 告警响应 (×5) | scenario | scenario | cage4-blue@1 | none | max_steps=510 | blue_agent_count | 5 | [5, 5] | 2 | 6 |

### Paired comparisons (one dimension at a time)

| kind | A | B | metric | mean B−A | 95% CI | pairs | unpaired | better | test |
|---|---|---|---|---|---|---|---|---|---|
| method | *=A 官方基线 · SleepAgent 映射 (×5) | *=B 原生映射 · MonitorAgent (×5) | goal_reached | 0 | [0, 0] | 6 | 0 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
| method | *=A 官方基线 · SleepAgent 映射 (×5) | *=B 原生映射 · MonitorAgent (×5) | steps_used | 0 | [0, 0] | 6 | 0 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
| method | *=A 官方基线 · SleepAgent 映射 (×5) | *=B 原生映射 · MonitorAgent (×5) | rejected_actions | 0 | [0, 0] | 6 | 0 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
| method | *=A 官方基线 · SleepAgent 映射 (×5) | *=B 原生映射 · MonitorAgent (×5) | effect_mismatches | 0 | [0, 0] | 6 | 0 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
| method | *=A 官方基线 · SleepAgent 映射 (×5) | *=B 原生映射 · MonitorAgent (×5) | wall_seconds | 1.752 | [-0.0145, 3.66] | 6 | 0 | *=A 官方基线 · SleepAgent 映射 (×5) | p=0.219 (statistical) |
| method | *=A 官方基线 · SleepAgent 映射 (×5) | *=B 原生映射 · MonitorAgent (×5) | native_blue_reward | 0 | [0, 0] | 6 | 0 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
| method | *=A 官方基线 · SleepAgent 映射 (×5) | *=B 原生映射 · MonitorAgent (×5) | green_success_rate | 0 | [0, 0] | 6 | 0 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
| method | *=A 官方基线 · SleepAgent 映射 (×5) | *=B 原生映射 · MonitorAgent (×5) | green_failed_actions | 0 | [0, 0] | 6 | 0 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
| method | *=A 官方基线 · SleepAgent 映射 (×5) | *=B 原生映射 · MonitorAgent (×5) | red_footholds_final | 0 | [0, 0] | 6 | 0 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
| method | *=A 官方基线 · SleepAgent 映射 (×5) | *=B 原生映射 · MonitorAgent (×5) | red_foothold_host_steps | 0 | [0, 0] | 6 | 0 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
| method | *=A 官方基线 · SleepAgent 映射 (×5) | *=B 原生映射 · MonitorAgent (×5) | recovery_time | — | — | 0 | 6 | — | no complete pairs (engineering) |
|  | incomplete pair ['acceptance', 'scn_204adcc8a4ce4add8bee', 'scenario', 'scenario', 'cage4-blue@1', 'none', 'max_steps=510', 1] | missing both | a: MISSING: no host left the red foothold set before the end | b: MISSING: no host left the red foothold set before the end | | | | | |
|  | incomplete pair ['acceptance', 'scn_204adcc8a4ce4add8bee', 'scenario', 'scenario', 'cage4-blue@1', 'none', 'max_steps=510', 2] | missing both | a: MISSING: no host left the red foothold set before the end | b: MISSING: no host left the red foothold set before the end | | | | | |
|  | incomplete pair ['acceptance', 'scn_204adcc8a4ce4add8bee', 'scenario', 'scenario', 'cage4-blue@1', 'none', 'max_steps=510', 3] | missing both | a: MISSING: no host left the red foothold set before the end | b: MISSING: no host left the red foothold set before the end | | | | | |
|  | incomplete pair ['acceptance', 'scn_794d1a33039142df8415', 'scenario', 'scenario', 'cage4-blue@1', 'none', 'max_steps=510', 1] | missing both | a: MISSING: no host left the red foothold set before the end | b: MISSING: no host left the red foothold set before the end | | | | | |
|  | incomplete pair ['acceptance', 'scn_794d1a33039142df8415', 'scenario', 'scenario', 'cage4-blue@1', 'none', 'max_steps=510', 2] | missing both | a: MISSING: no host left the red foothold set before the end | b: MISSING: no host left the red foothold set before the end | | | | | |
|  | incomplete pair ['acceptance', 'scn_794d1a33039142df8415', 'scenario', 'scenario', 'cage4-blue@1', 'none', 'max_steps=510', 3] | missing both | a: MISSING: no host left the red foothold set before the end | b: MISSING: no host left the red foothold set before the end | | | | | |
| method | *=A 官方基线 · SleepAgent 映射 (×5) | *=B 原生映射 · MonitorAgent (×5) | unrecovered_hosts | 0 | [0, 0] | 6 | 0 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
| method | *=A 官方基线 · SleepAgent 映射 (×5) | *=B 原生映射 · MonitorAgent (×5) | blue_actions_not_started | 0 | [0, 0] | 6 | 0 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
| method | *=A 官方基线 · SleepAgent 映射 (×5) | *=B 原生映射 · MonitorAgent (×5) | blue_agent_count | 0 | [0, 0] | 6 | 0 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
| method | *=A 官方基线 · SleepAgent 映射 (×5) | *=C 平台规则 · 告警响应 (×5) | goal_reached | 0 | [0, 0] | 6 | 0 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
| method | *=A 官方基线 · SleepAgent 映射 (×5) | *=C 平台规则 · 告警响应 (×5) | steps_used | 0 | [0, 0] | 6 | 0 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
| method | *=A 官方基线 · SleepAgent 映射 (×5) | *=C 平台规则 · 告警响应 (×5) | rejected_actions | 75.67 | [58.7, 90.8] | 6 | 0 | *=A 官方基线 · SleepAgent 映射 (×5) | p=0.0312 (statistical) |
| method | *=A 官方基线 · SleepAgent 映射 (×5) | *=C 平台规则 · 告警响应 (×5) | effect_mismatches | 0 | [0, 0] | 6 | 0 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
| method | *=A 官方基线 · SleepAgent 映射 (×5) | *=C 平台规则 · 告警响应 (×5) | wall_seconds | 0.5908 | [-0.294, 1.5] | 6 | 0 | *=A 官方基线 · SleepAgent 映射 (×5) | p=0.562 (statistical) |
| method | *=A 官方基线 · SleepAgent 映射 (×5) | *=C 平台规则 · 告警响应 (×5) | native_blue_reward | -5.333 | [-17.7, 7.33] | 6 | 0 | *=A 官方基线 · SleepAgent 映射 (×5) | significance not reported: 5 non-zero paired differences < 6 (engineering) |
| method | *=A 官方基线 · SleepAgent 映射 (×5) | *=C 平台规则 · 告警响应 (×5) | green_success_rate | -1.158e-06 | [-0.000634, 0.000547] | 6 | 0 | *=A 官方基线 · SleepAgent 映射 (×5) | significance not reported: 3 non-zero paired differences < 6 (engineering) |
| method | *=A 官方基线 · SleepAgent 映射 (×5) | *=C 平台规则 · 告警响应 (×5) | green_failed_actions | 0 | [-2, 2.33] | 6 | 0 | — | significance not reported: 3 non-zero paired differences < 6 (engineering) |
| method | *=A 官方基线 · SleepAgent 映射 (×5) | *=C 平台规则 · 告警响应 (×5) | red_footholds_final | -3 | [-5.5, -0.333] | 6 | 0 | *=C 平台规则 · 告警响应 (×5) | significance not reported: 5 non-zero paired differences < 6 (engineering) |
| method | *=A 官方基线 · SleepAgent 映射 (×5) | *=C 平台规则 · 告警响应 (×5) | red_foothold_host_steps | -84.83 | [-140, -33.2] | 6 | 0 | *=C 平台规则 · 告警响应 (×5) | significance not reported: 5 non-zero paired differences < 6 (engineering) |
| method | *=A 官方基线 · SleepAgent 映射 (×5) | *=C 平台规则 · 告警响应 (×5) | recovery_time | — | — | 0 | 6 | — | no complete pairs (engineering) |
|  | incomplete pair ['acceptance', 'scn_204adcc8a4ce4add8bee', 'scenario', 'scenario', 'cage4-blue@1', 'none', 'max_steps=510', 1] | missing a | a: MISSING: no host left the red foothold set before the end | b: present | | | | | |
|  | incomplete pair ['acceptance', 'scn_204adcc8a4ce4add8bee', 'scenario', 'scenario', 'cage4-blue@1', 'none', 'max_steps=510', 2] | missing a | a: MISSING: no host left the red foothold set before the end | b: present | | | | | |
|  | incomplete pair ['acceptance', 'scn_204adcc8a4ce4add8bee', 'scenario', 'scenario', 'cage4-blue@1', 'none', 'max_steps=510', 3] | missing a | a: MISSING: no host left the red foothold set before the end | b: present | | | | | |
|  | incomplete pair ['acceptance', 'scn_794d1a33039142df8415', 'scenario', 'scenario', 'cage4-blue@1', 'none', 'max_steps=510', 1] | missing both | a: MISSING: no host left the red foothold set before the end | b: MISSING: no host left the red foothold set before the end | | | | | |
|  | incomplete pair ['acceptance', 'scn_794d1a33039142df8415', 'scenario', 'scenario', 'cage4-blue@1', 'none', 'max_steps=510', 2] | missing a | a: MISSING: no host left the red foothold set before the end | b: present | | | | | |
|  | incomplete pair ['acceptance', 'scn_794d1a33039142df8415', 'scenario', 'scenario', 'cage4-blue@1', 'none', 'max_steps=510', 3] | missing a | a: MISSING: no host left the red foothold set before the end | b: present | | | | | |
| method | *=A 官方基线 · SleepAgent 映射 (×5) | *=C 平台规则 · 告警响应 (×5) | unrecovered_hosts | -3 | [-5.5, -0.333] | 6 | 0 | *=C 平台规则 · 告警响应 (×5) | significance not reported: 5 non-zero paired differences < 6 (engineering) |
| method | *=A 官方基线 · SleepAgent 映射 (×5) | *=C 平台规则 · 告警响应 (×5) | blue_actions_not_started | 75.67 | [58.7, 90.8] | 6 | 0 | *=A 官方基线 · SleepAgent 映射 (×5) | p=0.0312 (statistical) |
| method | *=A 官方基线 · SleepAgent 映射 (×5) | *=C 平台规则 · 告警响应 (×5) | blue_agent_count | 0 | [0, 0] | 6 | 0 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |

## Metric sources

- `blue_actions_not_started`: evaluator formal-lab.cage4.metrics
- `blue_agent_count`: evaluator formal-lab.cage4.metrics
- `effect_mismatches`: evaluator formal-lab.eval.generic
- `goal_reached`: evaluator formal-lab.eval.generic
- `green_failed_actions`: evaluator formal-lab.cage4.metrics
- `green_success_rate`: evaluator formal-lab.cage4.metrics
- `model_calls`: evaluator formal-lab.eval.generic
- `native_blue_reward`: evaluator formal-lab.cage4.metrics
- `recovery_time`: evaluator formal-lab.cage4.metrics
- `red_foothold_host_steps`: evaluator formal-lab.cage4.metrics
- `red_footholds_final`: evaluator formal-lab.cage4.metrics
- `rejected_actions`: evaluator formal-lab.eval.generic
- `steps_used`: evaluator formal-lab.eval.generic
- `tokens`: evaluator formal-lab.eval.generic
- `unrecovered_hosts`: evaluator formal-lab.cage4.metrics
- `wall_seconds`: evaluator formal-lab.eval.generic
