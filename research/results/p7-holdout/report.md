# Phase 7 held-out case: token-bucket capacity judgment

Study `p7-holdout` · primary metric `correct` · rubric fal-research-rubric@1 · 2 replicate(s) per condition

Ledger: 8 response record(s), 8 call(s), 8 HTTP attempt(s), 0 possibly billed unconfirmed attempt(s).

## Track `implementation_conformance` — 8 planned unit(s)

| condition | planned | call outcomes | behaviour | correct | format valid | refused | program corresponds | out tokens | identity |
|---|---|---|---|---|---|---|---|---|---|
| claude-opus-5-5-relay · STATIC_UNASSISTED · transcript | 4 | ANSWERED 4 | CORRECT 4 | 1.00 (n=4, missing 0) | 1.00 (n=4, missing 0) | 0.00 (n=4, missing 0) | 1.00 (n=4, missing 0) | 264.50 (n=4, missing 0) | COMPATIBLE_RELAY/RELAY_REPORTED: requested claude-opus-5-5, returned claude-opus-5-5 |
| gpt-6-astra-relay · STATIC_UNASSISTED · transcript | 4 | ANSWERED 4 | CORRECT 4 | 1.00 (n=4, missing 0) | 1.00 (n=4, missing 0) | 0.00 (n=4, missing 0) | 1.00 (n=4, missing 0) | 40.25 (n=4, missing 0) | COMPATIBLE_RELAY/RELAY_REPORTED: requested gpt-6-astra, returned gpt-6-astra |

Rubric signals (heuristic, recorded only — not adjudicated, no human review):
- claude-opus-5-5-relay · STATIC_UNASSISTED · transcript: identifies_overflow_step 2/2, states_capacity 4/4
- gpt-6-astra-relay · STATIC_UNASSISTED · transcript: identifies_overflow_step 2/2, states_capacity 4/4

**Paired (provider): gpt-6-astra-relay vs claude-opus-5-5-relay** — 4 pair(s), 0 unpaired; mean difference (b − a) 0.00; engineering reading: fewer than 6 complete pairs or non-zero differences — a direction, not a significance claim
> parameters are recorded, not equated: equal names (e.g. two 'high' settings) do not mean equal compute, and a fixed seed on a real API does not reproduce an answer


## Notes

- the two experiment lines are reported apart and never pooled into one success rate
- model scores count only responses the model produced; transport / auth / limit / budget / cancel / blocked units are MISSING (never 0, never 1); refusals and invalid answers count as not correct
- a relay route reports a model name it cannot prove; conclusions about a provider's model need a route whose identity is verifiable
- tasks: capacity-defect, capacity-fix
