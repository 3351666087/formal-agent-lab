# Phase 6B dual-model evaluation: program-grounded analysis and representation sensitivity

Study `p6b-eval` · primary metric `correct` · rubric fal-research-rubric@1 · 2 replicate(s) per condition

Ledger: 24 response record(s), 24 call(s), 25 HTTP attempt(s), 0 possibly billed unconfirmed attempt(s).

## Track `implementation_conformance` — 8 planned unit(s)

| condition | planned | call outcomes | behaviour | correct | format valid | refused | program corresponds | out tokens | identity |
|---|---|---|---|---|---|---|---|---|---|
| claude-opus-5-5-relay · STATIC_UNASSISTED · transcript | 4 | ANSWERED 4 | CORRECT 4 | 1.00 (n=4, missing 0) | 1.00 (n=4, missing 0) | 0.00 (n=4, missing 0) | 1.00 (n=4, missing 0) | 2001.00 (n=4, missing 0) | COMPATIBLE_RELAY/RELAY_REPORTED: requested claude-opus-5-5, returned claude-opus-5-5 |
| gpt-6-astra-relay · STATIC_UNASSISTED · transcript | 4 | ANSWERED 4 | CORRECT 4 | 1.00 (n=4, missing 0) | 1.00 (n=4, missing 0) | 0.00 (n=4, missing 0) | 1.00 (n=4, missing 0) | 150.00 (n=4, missing 0) | COMPATIBLE_RELAY/RELAY_REPORTED: requested gpt-6-astra, returned gpt-6-astra |

Rubric signals (heuristic, recorded only — not adjudicated, no human review):
- claude-opus-5-5-relay · STATIC_UNASSISTED · transcript: names_isolation_risk 4/4, no_false_violation 2/2, states_scope 4/4, violation_identified 2/2
- gpt-6-astra-relay · STATIC_UNASSISTED · transcript: names_isolation_risk 4/4, no_false_violation 2/2, states_scope 4/4, violation_identified 2/2

**Paired (provider): gpt-6-astra-relay vs claude-opus-5-5-relay** — 4 pair(s), 0 unpaired; mean difference (b − a) 0.00; engineering reading: fewer than 6 complete pairs or non-zero differences — a direction, not a significance claim
> parameters are recorded, not equated: equal names (e.g. two 'high' settings) do not mean equal compute, and a fixed seed on a real API does not reproduce an answer

**Paired (representation): garage vs library** — not applicable: this track plans no unit with representation = garage

**Paired (representation): courier vs approval** — not applicable: this track plans no unit with representation = courier

## Track `synthetic_representation` — 16 planned unit(s)

| condition | planned | call outcomes | behaviour | correct | format valid | refused | program corresponds | out tokens | identity |
|---|---|---|---|---|---|---|---|---|---|
| claude-opus-5-5-relay · STATIC_UNASSISTED · approval | 2 | ANSWERED 2 | CORRECT 2 | 1.00 (n=2, missing 0) | 1.00 (n=2, missing 0) | 0.00 (n=2, missing 0) | MISSING (n=0, missing 0, n/a 2) | 215.50 (n=2, missing 0) | COMPATIBLE_RELAY/RELAY_REPORTED: requested claude-opus-5-5, returned claude-opus-5-5 |
| claude-opus-5-5-relay · STATIC_UNASSISTED · courier | 2 | ANSWERED 2 | CORRECT 2 | 1.00 (n=2, missing 0) | 1.00 (n=2, missing 0) | 0.00 (n=2, missing 0) | MISSING (n=0, missing 0, n/a 2) | 224.50 (n=2, missing 0) | COMPATIBLE_RELAY/RELAY_REPORTED: requested claude-opus-5-5, returned claude-opus-5-5 |
| claude-opus-5-5-relay · STATIC_UNASSISTED · garage | 2 | ANSWERED 2 | CORRECT 2 | 1.00 (n=2, missing 0) | 1.00 (n=2, missing 0) | 0.00 (n=2, missing 0) | MISSING (n=0, missing 0, n/a 2) | 237.50 (n=2, missing 0) | COMPATIBLE_RELAY/RELAY_REPORTED: requested claude-opus-5-5, returned claude-opus-5-5 |
| claude-opus-5-5-relay · STATIC_UNASSISTED · library | 2 | ANSWERED 2 | CORRECT 2 | 1.00 (n=2, missing 0) | 1.00 (n=2, missing 0) | 0.00 (n=2, missing 0) | MISSING (n=0, missing 0, n/a 2) | 292.00 (n=2, missing 0) | COMPATIBLE_RELAY/RELAY_REPORTED: requested claude-opus-5-5, returned claude-opus-5-5 |
| gpt-6-astra-relay · STATIC_UNASSISTED · approval | 2 | ANSWERED 2 | CORRECT 2 | 1.00 (n=2, missing 0) | 1.00 (n=2, missing 0) | 0.00 (n=2, missing 0) | MISSING (n=0, missing 0, n/a 2) | 55.50 (n=2, missing 0) | COMPATIBLE_RELAY/RELAY_REPORTED: requested gpt-6-astra, returned gpt-6-astra |
| gpt-6-astra-relay · STATIC_UNASSISTED · courier | 2 | ANSWERED 2 | CORRECT 2 | 1.00 (n=2, missing 0) | 1.00 (n=2, missing 0) | 0.00 (n=2, missing 0) | MISSING (n=0, missing 0, n/a 2) | 55.50 (n=2, missing 0) | COMPATIBLE_RELAY/RELAY_REPORTED: requested gpt-6-astra, returned gpt-6-astra |
| gpt-6-astra-relay · STATIC_UNASSISTED · garage | 2 | ANSWERED 2 | CORRECT 2 | 1.00 (n=2, missing 0) | 1.00 (n=2, missing 0) | 0.00 (n=2, missing 0) | MISSING (n=0, missing 0, n/a 2) | 101.00 (n=2, missing 0) | COMPATIBLE_RELAY/RELAY_REPORTED: requested gpt-6-astra, returned gpt-6-astra |
| gpt-6-astra-relay · STATIC_UNASSISTED · library | 2 | ANSWERED 2 | CORRECT 2 | 1.00 (n=2, missing 0) | 1.00 (n=2, missing 0) | 0.00 (n=2, missing 0) | MISSING (n=0, missing 0, n/a 2) | 89.00 (n=2, missing 0) | COMPATIBLE_RELAY/RELAY_REPORTED: requested gpt-6-astra, returned gpt-6-astra |

**Paired (provider): gpt-6-astra-relay vs claude-opus-5-5-relay** — 8 pair(s), 0 unpaired; mean difference (b − a) 0.00; engineering reading: fewer than 6 complete pairs or non-zero differences — a direction, not a significance claim
> parameters are recorded, not equated: equal names (e.g. two 'high' settings) do not mean equal compute, and a fixed seed on a real API does not reproduce an answer

**Paired (representation): garage vs library** — 4 pair(s), 0 unpaired; mean difference (b − a) 0.00; engineering reading: fewer than 6 complete pairs or non-zero differences — a direction, not a significance claim

**Paired (representation): courier vs approval** — 4 pair(s), 0 unpaired; mean difference (b − a) 0.00; engineering reading: fewer than 6 complete pairs or non-zero differences — a direction, not a significance claim


## Notes

- the two experiment lines are reported apart and never pooled into one success rate
- model scores count only responses the model produced; transport / auth / limit / budget / cancel / blocked units are MISSING (never 0, never 1); refusals and invalid answers count as not correct
- a relay route reports a model name it cannot prove; conclusions about a provider's model need a route whose identity is verifiable
- tasks: approval, courier, garage, isolation-defect, isolation-fix, library
