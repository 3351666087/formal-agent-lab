# Offline report: scheduling strategies and the observation-delay ablation

Bundles are verified first (format, contract version, digests, event causality, required parts, pinned model); one report per model package.

## local-order-service

[report.md](local-order-service/report.md) · [report.csv](local-order-service/report.csv) · [report.json](local-order-service/report.json)

- 16 of 17 bundle(s) verified (format, contract, digests, causality, required parts); 1 rejected and excluded
- [acceptance] 12 cell(s): 12 finished, 0 failed or cancelled, 0 not run; goal reached in 12 of 12; missing metrics: none
- [acceptance] method: 订单规则 is better on steps_used (mean paired difference -2.17, 95% CI [-3.5, -1], 6 pairs, 0 unpaired)
- [dev] 4 cell(s): 4 finished, 0 failed or cancelled, 0 not run; goal reached in 4 of 4; missing metrics: none

## neutral-scheduling

[report.md](neutral-scheduling/report.md) · [report.csv](neutral-scheduling/report.csv) · [report.json](neutral-scheduling/report.json)

- 68 of 68 bundle(s) verified (format, contract, digests, causality, required parts); 0 rejected and excluded
- [acceptance] 51 cell(s): 51 finished, 0 failed or cancelled, 0 not run; goal reached in 48 of 51; missing metrics: makespan 3
- [acceptance] 10 comparison(s) have no complete pairs (the metric is missing on one side or the dimension varies only where the other does not) — no conclusion from them
- [acceptance] method: 成本优化（Z3） is better on makespan (mean paired difference -1.33, 95% CI [-2.56, -0.111], 9 pairs, 0 unpaired)
- [acceptance] method: 最短路径（Z3） is better on makespan (mean paired difference -1.33, 95% CI [-2.56, -0.111], 9 pairs, 6 unpaired)
- [acceptance] mechanism: no-observation-delay is better on steps_used (mean paired difference -21.8, 95% CI [-29.3, -14.1], 15 pairs, 15 unpaired)
- [acceptance] mechanism: no-observation-delay is better on effect_mismatches (mean paired difference -2.4, 95% CI [-3.13, -1.67], 15 pairs, 15 unpaired)
- [acceptance] mechanism: no-observation-delay is better on delay_cost (mean paired difference -24.7, 95% CI [-46.4, -4], 15 pairs, 15 unpaired)
- [acceptance] mechanism: no-observation-delay is better on mean_tardiness (mean paired difference -4.2, 95% CI [-7.71, -0.911], 15 pairs, 15 unpaired)
- [acceptance] mechanism: no-observation-delay is better on makespan (mean paired difference -2.75, 95% CI [-3.75, -1.75], 12 pairs, 18 unpaired)
- [dev] 17 cell(s): 17 finished, 0 failed or cancelled, 0 not run; goal reached in 16 of 17; missing metrics: makespan 1
- [dev] 10 comparison(s) have no complete pairs (the metric is missing on one side or the dimension varies only where the other does not) — no conclusion from them
- [dev] mechanism: no-observation-delay is better on steps_used (mean paired difference -23, 95% CI [-36, -10.2], 5 pairs, 5 unpaired)
- [dev] mechanism: no-observation-delay is better on effect_mismatches (mean paired difference -3, 95% CI [-4.4, -1.4], 5 pairs, 5 unpaired)
- [dev] mechanism: no-observation-delay is better on delay_cost (mean paired difference -23.6, 95% CI [-66.8, -1.2], 5 pairs, 5 unpaired)
- [dev] mechanism: no-observation-delay is better on mean_tardiness (mean paired difference -4, 95% CI [-11.1, -0.2], 5 pairs, 5 unpaired)
- [dev] mechanism: no-observation-delay is better on makespan (mean paired difference -1.5, 95% CI [-3.25, -0.25], 4 pairs, 6 unpaired)

