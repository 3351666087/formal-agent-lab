# A4 paired report (known inputs)

## Conclusions

- [acceptance] 10 cell(s): 10 finished, 1 failed or cancelled, 0 not run; goal reached in 9 of 10; missing metrics: delay_cost 1
- [acceptance] success 9/10 = 90% (denominator: every planned cell); timed out 0, reused 2, new runs 8
- [acceptance] method: z3 is better on delay_cost (mean paired difference -2.5, 95% CI [-3.75, -0.75], 4 pairs, 1 unpaired) — engineering reading (small sample)

## Split `acceptance`

Denominator: 10 cells — run status {'SUCCEEDED': 9, 'FAILED': 1}; goal not reached: 1; missing metrics {'delay_cost': 1}.

Success: 9/10 (goal reached / every planned cell of this split (fixed before the runs; failed, cancelled, timed-out and not-run cells count as not reached)); finished only 9/10. Timed out: 0. Reused: 2 (same full configuration completed in mx_a); new runs 8; sampling {'DETERMINISTIC': 10}.

### Per scenario (unit: one seed of one scenario)

| scenario | participants | backend | rules | model | ablation | budget | metric | value | 95% CI | n | missing | source |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sc | rule | scenario | scenario | m@1 | none | scenario-default | delay_cost | 10 | [8.8, 11.2] | 5 | 0 | evaluator (known inputs) |
| sc | z3 | scenario | scenario | m@1 | none | scenario-default | delay_cost | 7.25 | [5.75, 8.5] | 4 | 1 | evaluator (known inputs) |

### Pooled across scenarios (unit: scenario; cluster bootstrap)

| participants | backend | rules | model | ablation | budget | metric | value | 95% CI | scenarios | n |
|---|---|---|---|---|---|---|---|---|---|---|
| rule | scenario | scenario | m@1 | none | scenario-default | delay_cost | 10 | — | 1 | 5 |
| z3 | scenario | scenario | m@1 | none | scenario-default | delay_cost | 7.25 | — | 1 | 4 |

### Paired comparisons (one dimension at a time)

| kind | A | B | metric | mean B−A | 95% CI | pairs | unpaired | better | test |
|---|---|---|---|---|---|---|---|---|---|
| method | rule | z3 | delay_cost | -2.5 | [-3.75, -0.75] | 4 | 1 | z3 | significance not reported: 3 non-zero paired differences < 6 (engineering) |
|  | incomplete pair ['acceptance', 'sc', 'scenario', 'scenario', 'm@1', 'none', 'scenario-default', 3] | missing b | a: present | b: MISSING: run FAILED: worker error: solver crashed | | | | | |

## Metric sources

- `delay_cost`: evaluator (known inputs)
