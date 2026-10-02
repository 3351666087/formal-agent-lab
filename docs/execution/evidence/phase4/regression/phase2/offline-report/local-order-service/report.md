# Offline report: scheduling strategies and the observation-delay ablation — local-order-service

## Conclusions

- 16 of 17 bundle(s) verified (format, contract, digests, causality, required parts); 1 rejected and excluded
- [acceptance] 12 cell(s): 12 finished, 0 failed or cancelled, 0 not run; goal reached in 12 of 12; missing metrics: none
- [acceptance] success 12/12 = 100% (denominator: every planned cell); timed out 0, reused 0, new runs 12
- [acceptance] method: 订单规则 is better on steps_used (mean paired difference -2.17, 95% CI [-3.5, -1], 6 pairs, 0 unpaired) — engineering reading (small sample)
- [dev] 4 cell(s): 4 finished, 0 failed or cancelled, 0 not run; goal reached in 4 of 4; missing metrics: none
- [dev] success 4/4 = 100% (denominator: every planned cell); timed out 0, reused 0, new runs 4

## Split `acceptance`

Denominator: 12 cells — run status {'SUCCEEDED': 12}; goal not reached: 0; missing metrics {'goal_reached': 0, 'steps_used': 0, 'rejected_actions': 0, 'effect_mismatches': 0, 'wall_seconds': 0, 'model_calls': 0, 'tokens': 0, 'orders_completed': 0, 'late_orders': 0, 'mean_latency': 0, 'probe.throughput': 0, 'probe.completion_rate': 0, 'probe.queue_length': 0, 'probe.backlog': 0, 'probe.latency_ticks': 0, 'probe.op_latency_ms': 0, 'probe.recovery_seconds': 0}.

Success: 12/12 (goal reached / every planned cell of this split (fixed before the runs; failed, cancelled, timed-out and not-run cells count as not reached)); finished only 12/12. Timed out: 0. Reused: 0 (—); new runs 12; sampling {'UNKNOWN': 12}.

### Per scenario (unit: one seed of one scenario)

| scenario | participants | backend | rules | model | ablation | budget | metric | value | 95% CI | n | missing | source |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 订单：预测效果偏差（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | goal_reached | 1 | [1, 1] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：预测效果偏差（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | steps_used | 30.67 | [28, 34] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：预测效果偏差（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | rejected_actions | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：预测效果偏差（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | effect_mismatches | 5.333 | [4, 7] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：预测效果偏差（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | wall_seconds | 10.99 | [7.88, 14.3] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：预测效果偏差（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：预测效果偏差（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：预测效果偏差（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | orders_completed | 6 | [6, 6] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：预测效果偏差（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | late_orders | 0.3333 | [0, 1] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：预测效果偏差（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | mean_latency | 4 | [2.83, 5.33] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：预测效果偏差（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.throughput | 0.4167 | [0.25, 0.5] | 3 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：预测效果偏差（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.completion_rate | 1 | [1, 1] | 3 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：预测效果偏差（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.queue_length | 0 | [0, 0] | 3 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：预测效果偏差（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.backlog | 0 | [0, 0] | 3 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：预测效果偏差（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.latency_ticks | 6.5 | [4, 10] | 3 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：预测效果偏差（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.op_latency_ms | 0.325 | [0.324, 0.327] | 3 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：预测效果偏差（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.recovery_seconds | — | — | 0 | 3 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：预测效果偏差（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | goal_reached | 1 | [1, 1] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：预测效果偏差（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | steps_used | 28.33 | [28, 29] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：预测效果偏差（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | rejected_actions | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：预测效果偏差（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | effect_mismatches | 4.667 | [4, 5] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：预测效果偏差（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | wall_seconds | 0.791 | [0.777, 0.803] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：预测效果偏差（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：预测效果偏差（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：预测效果偏差（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | orders_completed | 6 | [6, 6] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：预测效果偏差（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | late_orders | 0.3333 | [0, 1] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：预测效果偏差（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | mean_latency | 3.833 | [3, 4.67] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：预测效果偏差（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.throughput | 0.5 | [0.25, 0.75] | 3 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：预测效果偏差（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.completion_rate | 1 | [1, 1] | 3 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：预测效果偏差（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.queue_length | 0 | [0, 0] | 3 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：预测效果偏差（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.backlog | 0 | [0, 0] | 3 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：预测效果偏差（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.latency_ticks | 6.056 | [5.5, 6.67] | 3 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：预测效果偏差（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.op_latency_ms | 0.3115 | [0.308, 0.315] | 3 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：预测效果偏差（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.recovery_seconds | — | — | 0 | 3 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：正常处理（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | goal_reached | 1 | [1, 1] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：正常处理（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | steps_used | 27.33 | [27, 28] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：正常处理（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | rejected_actions | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：正常处理（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | effect_mismatches | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：正常处理（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | wall_seconds | 16.95 | [14.3, 18.9] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：正常处理（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：正常处理（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：正常处理（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | orders_completed | 6 | [6, 6] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：正常处理（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | late_orders | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：正常处理（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | mean_latency | 2.778 | [2.17, 3.5] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：正常处理（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.throughput | 0.75 | [0.75, 0.75] | 3 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：正常处理（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.completion_rate | 1 | [1, 1] | 3 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：正常处理（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.queue_length | 0 | [0, 0] | 3 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：正常处理（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.backlog | 0 | [0, 0] | 3 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：正常处理（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.latency_ticks | 3.333 | [2.67, 4] | 3 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：正常处理（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.op_latency_ms | 0.3242 | [0.307, 0.347] | 3 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：正常处理（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.recovery_seconds | — | — | 0 | 3 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：正常处理（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | goal_reached | 1 | [1, 1] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：正常处理（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | steps_used | 25.33 | [25, 26] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：正常处理（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | rejected_actions | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：正常处理（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | effect_mismatches | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：正常处理（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | wall_seconds | 0.6803 | [0.663, 0.7] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：正常处理（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：正常处理（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：正常处理（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | orders_completed | 6 | [6, 6] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：正常处理（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | late_orders | 0 | [0, 0] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：正常处理（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | mean_latency | 2.611 | [2, 3.33] | 3 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：正常处理（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.throughput | 0.75 | [0.75, 0.75] | 3 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：正常处理（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.completion_rate | 1 | [1, 1] | 3 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：正常处理（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.queue_length | 0 | [0, 0] | 3 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：正常处理（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.backlog | 0 | [0, 0] | 3 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：正常处理（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.latency_ticks | 3 | [2.33, 3.67] | 3 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：正常处理（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.op_latency_ms | 0.31 | [0.297, 0.32] | 3 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：正常处理（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.recovery_seconds | — | — | 0 | 3 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |

### Pooled across scenarios (unit: scenario; cluster bootstrap)

| participants | backend | rules | model | ablation | budget | metric | value | 95% CI | scenarios | n |
|---|---|---|---|---|---|---|---|---|---|---|
| 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | goal_reached | 1 | [1, 1] | 2 | 6 |
| 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | steps_used | 29 | [27.3, 30.7] | 2 | 6 |
| 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | rejected_actions | 0 | [0, 0] | 2 | 6 |
| 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | effect_mismatches | 2.667 | [0, 5.33] | 2 | 6 |
| 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | wall_seconds | 13.97 | [11, 16.9] | 2 | 6 |
| 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | model_calls | — | — | 0 | 0 |
| 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | tokens | — | — | 0 | 0 |
| 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | orders_completed | 6 | [6, 6] | 2 | 6 |
| 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | late_orders | 0.1667 | [0, 0.333] | 2 | 6 |
| 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | mean_latency | 3.389 | [2.78, 4] | 2 | 6 |
| 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.throughput | 0.5833 | [0.417, 0.75] | 2 | 6 |
| 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.completion_rate | 1 | [1, 1] | 2 | 6 |
| 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.queue_length | 0 | [0, 0] | 2 | 6 |
| 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.backlog | 0 | [0, 0] | 2 | 6 |
| 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.latency_ticks | 4.917 | [3.33, 6.5] | 2 | 6 |
| 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.op_latency_ms | 0.3246 | [0.324, 0.325] | 2 | 6 |
| 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.recovery_seconds | — | — | 0 | 0 |
| 订单规则 | order service | none | local-order-service@1 | none | scenario-default | goal_reached | 1 | [1, 1] | 2 | 6 |
| 订单规则 | order service | none | local-order-service@1 | none | scenario-default | steps_used | 26.83 | [25.3, 28.3] | 2 | 6 |
| 订单规则 | order service | none | local-order-service@1 | none | scenario-default | rejected_actions | 0 | [0, 0] | 2 | 6 |
| 订单规则 | order service | none | local-order-service@1 | none | scenario-default | effect_mismatches | 2.333 | [0, 4.67] | 2 | 6 |
| 订单规则 | order service | none | local-order-service@1 | none | scenario-default | wall_seconds | 0.7357 | [0.68, 0.791] | 2 | 6 |
| 订单规则 | order service | none | local-order-service@1 | none | scenario-default | model_calls | — | — | 0 | 0 |
| 订单规则 | order service | none | local-order-service@1 | none | scenario-default | tokens | — | — | 0 | 0 |
| 订单规则 | order service | none | local-order-service@1 | none | scenario-default | orders_completed | 6 | [6, 6] | 2 | 6 |
| 订单规则 | order service | none | local-order-service@1 | none | scenario-default | late_orders | 0.1667 | [0, 0.333] | 2 | 6 |
| 订单规则 | order service | none | local-order-service@1 | none | scenario-default | mean_latency | 3.222 | [2.61, 3.83] | 2 | 6 |
| 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.throughput | 0.625 | [0.5, 0.75] | 2 | 6 |
| 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.completion_rate | 1 | [1, 1] | 2 | 6 |
| 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.queue_length | 0 | [0, 0] | 2 | 6 |
| 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.backlog | 0 | [0, 0] | 2 | 6 |
| 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.latency_ticks | 4.528 | [3, 6.06] | 2 | 6 |
| 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.op_latency_ms | 0.3107 | [0.31, 0.311] | 2 | 6 |
| 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.recovery_seconds | — | — | 0 | 0 |

### Paired comparisons (one dimension at a time)

| kind | A | B | metric | mean B−A | 95% CI | pairs | unpaired | better | test |
|---|---|---|---|---|---|---|---|---|---|
| method | 最短路径（Z3） | 订单规则 | goal_reached | 0 | [0, 0] | 6 | 0 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
| method | 最短路径（Z3） | 订单规则 | steps_used | -2.167 | [-3.5, -1] | 6 | 0 | 订单规则 | significance not reported: 5 non-zero paired differences < 6 (engineering) |
| method | 最短路径（Z3） | 订单规则 | rejected_actions | 0 | [0, 0] | 6 | 0 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
| method | 最短路径（Z3） | 订单规则 | effect_mismatches | -0.3333 | [-1.5, 0.5] | 6 | 0 | 订单规则 | significance not reported: 2 non-zero paired differences < 6 (engineering) |
| method | 最短路径（Z3） | 订单规则 | wall_seconds | -13.23 | [-16.2, -10.2] | 6 | 0 | — | p=0.0312 (statistical) |
| method | 最短路径（Z3） | 订单规则 | orders_completed | 0 | [0, 0] | 6 | 0 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
| method | 最短路径（Z3） | 订单规则 | late_orders | 0 | [0, 0] | 6 | 0 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
| method | 最短路径（Z3） | 订单规则 | mean_latency | -0.1667 | [-0.389, 0.0278] | 6 | 0 | 订单规则 | significance not reported: 5 non-zero paired differences < 6 (engineering) |
| method | 最短路径（Z3） | 订单规则 | probe.throughput | 0.04167 | [-0.125, 0.25] | 6 | 0 | — | significance not reported: 2 non-zero paired differences < 6 (engineering) |
| method | 最短路径（Z3） | 订单规则 | probe.completion_rate | 0 | [0, 0] | 6 | 0 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
| method | 最短路径（Z3） | 订单规则 | probe.queue_length | 0 | [0, 0] | 6 | 0 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
| method | 最短路径（Z3） | 订单规则 | probe.backlog | 0 | [0, 0] | 6 | 0 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
| method | 最短路径（Z3） | 订单规则 | probe.latency_ticks | -0.3889 | [-1.78, 0.833] | 6 | 0 | — | significance not reported: 5 non-zero paired differences < 6 (engineering) |
| method | 最短路径（Z3） | 订单规则 | probe.op_latency_ms | -0.01389 | [-0.0301, 0.000278] | 6 | 0 | — | p=0.156 (statistical) |

## Split `dev`

Denominator: 4 cells — run status {'SUCCEEDED': 4}; goal not reached: 0; missing metrics {'goal_reached': 0, 'steps_used': 0, 'rejected_actions': 0, 'effect_mismatches': 0, 'wall_seconds': 0, 'model_calls': 0, 'tokens': 0, 'orders_completed': 0, 'late_orders': 0, 'mean_latency': 0, 'probe.throughput': 0, 'probe.completion_rate': 0, 'probe.queue_length': 0, 'probe.backlog': 0, 'probe.latency_ticks': 0, 'probe.op_latency_ms': 0, 'probe.recovery_seconds': 0}.

Success: 4/4 (goal reached / every planned cell of this split (fixed before the runs; failed, cancelled, timed-out and not-run cells count as not reached)); finished only 4/4. Timed out: 0. Reused: 0 (—); new runs 4; sampling {'UNKNOWN': 4}.

### Per scenario (unit: one seed of one scenario)

| scenario | participants | backend | rules | model | ablation | budget | metric | value | 95% CI | n | missing | source |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 订单：预测效果偏差（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | goal_reached | 1 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：预测效果偏差（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | steps_used | 30 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：预测效果偏差（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | rejected_actions | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：预测效果偏差（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | effect_mismatches | 4 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：预测效果偏差（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | wall_seconds | 13 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：预测效果偏差（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：预测效果偏差（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：预测效果偏差（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | orders_completed | 6 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：预测效果偏差（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | late_orders | 1 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：预测效果偏差（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | mean_latency | 4 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：预测效果偏差（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.throughput | 0.75 | — | 1 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：预测效果偏差（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.completion_rate | 1 | — | 1 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：预测效果偏差（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.queue_length | 0 | — | 1 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：预测效果偏差（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.backlog | 0 | — | 1 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：预测效果偏差（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.latency_ticks | 6.333 | — | 1 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：预测效果偏差（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.op_latency_ms | 0.3208 | — | 1 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：预测效果偏差（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.recovery_seconds | — | — | 0 | 1 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：预测效果偏差（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | goal_reached | 1 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：预测效果偏差（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | steps_used | 26 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：预测效果偏差（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | rejected_actions | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：预测效果偏差（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | effect_mismatches | 4 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：预测效果偏差（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | wall_seconds | 0.721 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：预测效果偏差（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：预测效果偏差（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：预测效果偏差（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | orders_completed | 6 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：预测效果偏差（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | late_orders | 1 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：预测效果偏差（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | mean_latency | 3.333 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：预测效果偏差（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.throughput | 0.75 | — | 1 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：预测效果偏差（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.completion_rate | 1 | — | 1 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：预测效果偏差（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.queue_length | 0 | — | 1 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：预测效果偏差（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.backlog | 0 | — | 1 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：预测效果偏差（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.latency_ticks | 5 | — | 1 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：预测效果偏差（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.op_latency_ms | 0.299 | — | 1 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：预测效果偏差（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.recovery_seconds | — | — | 0 | 1 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：正常处理（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | goal_reached | 1 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：正常处理（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | steps_used | 26 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：正常处理（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | rejected_actions | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：正常处理（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | effect_mismatches | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：正常处理（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | wall_seconds | 20.47 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：正常处理（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：正常处理（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：正常处理（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | orders_completed | 6 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：正常处理（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | late_orders | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：正常处理（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | mean_latency | 2.333 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：正常处理（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.throughput | 1 | — | 1 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：正常处理（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.completion_rate | 1 | — | 1 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：正常处理（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.queue_length | 0 | — | 1 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：正常处理（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.backlog | 0 | — | 1 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：正常处理（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.latency_ticks | 2.75 | — | 1 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：正常处理（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.op_latency_ms | 0.3172 | — | 1 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：正常处理（业务服务） | 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.recovery_seconds | — | — | 0 | 1 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：正常处理（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | goal_reached | 1 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：正常处理（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | steps_used | 24 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：正常处理（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | rejected_actions | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：正常处理（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | effect_mismatches | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：正常处理（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | wall_seconds | 0.663 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：正常处理（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | model_calls | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：正常处理（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | tokens | — | — | 0 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：正常处理（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | orders_completed | 6 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：正常处理（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | late_orders | 0 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：正常处理（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | mean_latency | 2.333 | — | 1 | 0 | evaluator (formal-lab.eval.generic) as recorded in the bundle |
| 订单：正常处理（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.throughput | 1 | — | 1 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：正常处理（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.completion_rate | 1 | — | 1 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：正常处理（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.queue_length | 0 | — | 1 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：正常处理（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.backlog | 0 | — | 1 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：正常处理（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.latency_ticks | 2.75 | — | 1 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：正常处理（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.op_latency_ms | 0.3117 | — | 1 | 0 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |
| 订单：正常处理（业务服务） | 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.recovery_seconds | — | — | 0 | 1 | probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics) |

### Pooled across scenarios (unit: scenario; cluster bootstrap)

| participants | backend | rules | model | ablation | budget | metric | value | 95% CI | scenarios | n |
|---|---|---|---|---|---|---|---|---|---|---|
| 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | goal_reached | 1 | [1, 1] | 2 | 2 |
| 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | steps_used | 28 | [26, 30] | 2 | 2 |
| 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | rejected_actions | 0 | [0, 0] | 2 | 2 |
| 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | effect_mismatches | 2 | [0, 4] | 2 | 2 |
| 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | wall_seconds | 16.74 | [13, 20.5] | 2 | 2 |
| 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | model_calls | — | — | 0 | 0 |
| 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | tokens | — | — | 0 | 0 |
| 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | orders_completed | 6 | [6, 6] | 2 | 2 |
| 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | late_orders | 0.5 | [0, 1] | 2 | 2 |
| 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | mean_latency | 3.167 | [2.33, 4] | 2 | 2 |
| 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.throughput | 0.875 | [0.75, 1] | 2 | 2 |
| 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.completion_rate | 1 | [1, 1] | 2 | 2 |
| 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.queue_length | 0 | [0, 0] | 2 | 2 |
| 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.backlog | 0 | [0, 0] | 2 | 2 |
| 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.latency_ticks | 4.542 | [2.75, 6.33] | 2 | 2 |
| 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.op_latency_ms | 0.319 | [0.317, 0.321] | 2 | 2 |
| 最短路径（Z3） | order service | none | local-order-service@1 | none | scenario-default | probe.recovery_seconds | — | — | 0 | 0 |
| 订单规则 | order service | none | local-order-service@1 | none | scenario-default | goal_reached | 1 | [1, 1] | 2 | 2 |
| 订单规则 | order service | none | local-order-service@1 | none | scenario-default | steps_used | 25 | [24, 26] | 2 | 2 |
| 订单规则 | order service | none | local-order-service@1 | none | scenario-default | rejected_actions | 0 | [0, 0] | 2 | 2 |
| 订单规则 | order service | none | local-order-service@1 | none | scenario-default | effect_mismatches | 2 | [0, 4] | 2 | 2 |
| 订单规则 | order service | none | local-order-service@1 | none | scenario-default | wall_seconds | 0.692 | [0.663, 0.721] | 2 | 2 |
| 订单规则 | order service | none | local-order-service@1 | none | scenario-default | model_calls | — | — | 0 | 0 |
| 订单规则 | order service | none | local-order-service@1 | none | scenario-default | tokens | — | — | 0 | 0 |
| 订单规则 | order service | none | local-order-service@1 | none | scenario-default | orders_completed | 6 | [6, 6] | 2 | 2 |
| 订单规则 | order service | none | local-order-service@1 | none | scenario-default | late_orders | 0.5 | [0, 1] | 2 | 2 |
| 订单规则 | order service | none | local-order-service@1 | none | scenario-default | mean_latency | 2.833 | [2.33, 3.33] | 2 | 2 |
| 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.throughput | 0.875 | [0.75, 1] | 2 | 2 |
| 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.completion_rate | 1 | [1, 1] | 2 | 2 |
| 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.queue_length | 0 | [0, 0] | 2 | 2 |
| 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.backlog | 0 | [0, 0] | 2 | 2 |
| 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.latency_ticks | 3.875 | [2.75, 5] | 2 | 2 |
| 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.op_latency_ms | 0.3054 | [0.299, 0.312] | 2 | 2 |
| 订单规则 | order service | none | local-order-service@1 | none | scenario-default | probe.recovery_seconds | — | — | 0 | 0 |

### Paired comparisons (one dimension at a time)

| kind | A | B | metric | mean B−A | 95% CI | pairs | unpaired | better | test |
|---|---|---|---|---|---|---|---|---|---|
| method | 最短路径（Z3） | 订单规则 | goal_reached | 0 | — | 2 | 0 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
| method | 最短路径（Z3） | 订单规则 | steps_used | -3 | — | 2 | 0 | 订单规则 | significance not reported: 2 non-zero paired differences < 6 (engineering) |
| method | 最短路径（Z3） | 订单规则 | rejected_actions | 0 | — | 2 | 0 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
| method | 最短路径（Z3） | 订单规则 | effect_mismatches | 0 | — | 2 | 0 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
| method | 最短路径（Z3） | 订单规则 | wall_seconds | -16.04 | — | 2 | 0 | — | significance not reported: 2 non-zero paired differences < 6 (engineering) |
| method | 最短路径（Z3） | 订单规则 | orders_completed | 0 | — | 2 | 0 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
| method | 最短路径（Z3） | 订单规则 | late_orders | 0 | — | 2 | 0 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
| method | 最短路径（Z3） | 订单规则 | mean_latency | -0.3333 | — | 2 | 0 | 订单规则 | significance not reported: 1 non-zero paired differences < 6 (engineering) |
| method | 最短路径（Z3） | 订单规则 | probe.throughput | 0 | — | 2 | 0 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
| method | 最短路径（Z3） | 订单规则 | probe.completion_rate | 0 | — | 2 | 0 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
| method | 最短路径（Z3） | 订单规则 | probe.queue_length | 0 | — | 2 | 0 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
| method | 最短路径（Z3） | 订单规则 | probe.backlog | 0 | — | 2 | 0 | — | significance not reported: 0 non-zero paired differences < 6 (engineering) |
| method | 最短路径（Z3） | 订单规则 | probe.latency_ticks | -0.6667 | — | 2 | 0 | — | significance not reported: 1 non-zero paired differences < 6 (engineering) |
| method | 最短路径（Z3） | 订单规则 | probe.op_latency_ms | -0.01365 | — | 2 | 0 | — | significance not reported: 2 non-zero paired differences < 6 (engineering) |

## Metric sources

- `effect_mismatches`: evaluator (formal-lab.eval.generic) as recorded in the bundle
- `goal_reached`: evaluator (formal-lab.eval.generic) as recorded in the bundle
- `late_orders`: evaluator (formal-lab.eval.generic) as recorded in the bundle
- `mean_latency`: evaluator (formal-lab.eval.generic) as recorded in the bundle
- `model_calls`: evaluator (formal-lab.eval.generic) as recorded in the bundle
- `orders_completed`: evaluator (formal-lab.eval.generic) as recorded in the bundle
- `probe.backlog`: probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics)
- `probe.completion_rate`: probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics)
- `probe.latency_ticks`: probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics)
- `probe.op_latency_ms`: probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics)
- `probe.queue_length`: probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics)
- `probe.recovery_seconds`: probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics)
- `probe.throughput`: probe formal-lab.example.orders.probe (GET http://127.0.0.1:41595/t/deviation-rule-1/metrics)
- `rejected_actions`: evaluator (formal-lab.eval.generic) as recorded in the bundle
- `steps_used`: evaluator (formal-lab.eval.generic) as recorded in the bundle
- `tokens`: evaluator (formal-lab.eval.generic) as recorded in the bundle
- `wall_seconds`: evaluator (formal-lab.eval.generic) as recorded in the bundle

## Rejected bundles

- `run_off_corrupted.replay.zip`: unreadable: BadZipFile: Bad CRC-32 for file 'contracts/v2/schemas/ModelPackage.schema.json'
