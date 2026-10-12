# Phase 6A minimal real calls (ordinary business task)

Study `p6a-real` · primary metric `correct` · rubric fal-research-rubric@1 · 1 replicate(s) per condition

Ledger: 22 response record(s), 10 call(s), 12 HTTP attempt(s), 0 possibly billed unconfirmed attempt(s).

## Track `implementation_conformance` — 6 planned unit(s)

| condition | planned | call outcomes | behaviour | correct | format valid | refused | program corresponds | out tokens | identity |
|---|---|---|---|---|---|---|---|---|---|
| claude-opus-5-5-native · ASSISTED · brief-md | 1 | BLOCKED_NO_CREDENTIAL 1 | NOT_RUN 1 | MISSING (n=0, missing 1, n/a 0) | MISSING (n=0, missing 1, n/a 0) | MISSING (n=0, missing 1, n/a 0) | MISSING (n=0, missing 1, n/a 0) | MISSING (n=0, missing 1, n/a 0) | OFFICIAL_NATIVE/UNKNOWN: requested claude-opus-5-5, returned None |
| claude-opus-5-5-native · STATIC_UNASSISTED · brief-md | 1 | BLOCKED_NO_CREDENTIAL 1 | NOT_RUN 1 | MISSING (n=0, missing 1, n/a 0) | MISSING (n=0, missing 1, n/a 0) | MISSING (n=0, missing 1, n/a 0) | MISSING (n=0, missing 1, n/a 0) | MISSING (n=0, missing 1, n/a 0) | OFFICIAL_NATIVE/UNKNOWN: requested claude-opus-5-5, returned None |
| claude-opus-5-5-relay · ASSISTED · brief-md | 1 | ANSWERED 1 | INVALID_FORMAT 1 | 0.00 (n=1, missing 0) | 0.00 (n=1, missing 0) | 0.00 (n=1, missing 0) | MISSING (n=0, missing 1, n/a 0) | 797.00 (n=1, missing 0) | COMPATIBLE_RELAY/RELAY_REPORTED: requested claude-opus-5-5, returned claude-opus-5-5 |
| claude-opus-5-5-relay · STATIC_UNASSISTED · brief-md | 1 | ANSWERED 1 | CORRECT 1 | 1.00 (n=1, missing 0) | 1.00 (n=1, missing 0) | 0.00 (n=1, missing 0) | 1.00 (n=1, missing 0) | 960.00 (n=1, missing 0) | COMPATIBLE_RELAY/RELAY_REPORTED: requested claude-opus-5-5, returned claude-opus-5-5 |
| gpt-6-astra-relay · ASSISTED · brief-md | 1 | ANSWERED 1 | CORRECT 1 | 1.00 (n=1, missing 0) | 1.00 (n=1, missing 0) | 0.00 (n=1, missing 0) | 1.00 (n=1, missing 0) | 83.00 (n=1, missing 0) | COMPATIBLE_RELAY/RELAY_REPORTED: requested gpt-6-astra, returned gpt-6-astra |
| gpt-6-astra-relay · STATIC_UNASSISTED · brief-md | 1 | ANSWERED 1 | CORRECT 1 | 1.00 (n=1, missing 0) | 1.00 (n=1, missing 0) | 0.00 (n=1, missing 0) | 1.00 (n=1, missing 0) | 66.00 (n=1, missing 0) | COMPATIBLE_RELAY/RELAY_REPORTED: requested gpt-6-astra, returned gpt-6-astra |

**Paired (provider): gpt-6-astra-relay vs claude-opus-5-5-relay** — 2 pair(s), 0 unpaired; mean difference (b − a) -0.50; engineering reading: fewer than 6 complete pairs or non-zero differences — a direction, not a significance claim
> parameters are recorded, not equated: equal names (e.g. two 'high' settings) do not mean equal compute, and a fixed seed on a real API does not reproduce an answer

**Paired (assistance): STATIC_UNASSISTED vs ASSISTED** — 2 pair(s), 1 unpaired; mean difference (b − a) -0.50; engineering reading: fewer than 6 complete pairs or non-zero differences — a direction, not a significance claim


## Notes

- the two experiment lines are reported apart and never pooled into one success rate
- model scores count only responses the model produced; transport / auth / limit / budget / cancel / blocked units are MISSING (never 0, never 1); refusals and invalid answers count as not correct
- a relay route reports a model name it cannot prove; conclusions about a provider's model need a route whose identity is verifiable
- tasks: orders-deviation
