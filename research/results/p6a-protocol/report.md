# Phase 6A protocol validation (loopback test service, not a model)

Study `p6a-protocol` · primary metric `correct` · rubric fal-research-rubric@1 · 2 replicate(s) per condition

Ledger: 24 response record(s), 24 call(s), 28 HTTP attempt(s), 1 possibly billed unconfirmed attempt(s).

## Track `implementation_conformance` — 8 planned unit(s)

| condition | planned | call outcomes | behaviour | correct | format valid | refused | program corresponds | out tokens | identity |
|---|---|---|---|---|---|---|---|---|---|
| ptest-anthropic · ASSISTED · brief-md | 2 | ANSWERED 1, PROVIDER_ERROR 1 | CORRECT 1, NO_MODEL_ANSWER 1 | 1.00 (n=1, missing 1) | 1.00 (n=1, missing 1) | 0.00 (n=1, missing 1) | 1.00 (n=1, missing 1) | 13.00 (n=1, missing 1) | LOOPBACK_TEST/TEST_SERVICE: requested protocol-test-v1, returned protocol-test-v1; LOOPBACK_TEST/UNKNOWN: requested protocol-test-v1, returned None |
| ptest-anthropic · STATIC_UNASSISTED · brief-md | 2 | ANSWERED 1, CONTENT_REFUSAL 1 | CORRECT 1, REFUSED 1 | 0.50 (n=2, missing 0) | 1.00 (n=1, missing 1) | 0.50 (n=2, missing 0) | 1.00 (n=1, missing 1) | 6.50 (n=2, missing 0) | LOOPBACK_TEST/TEST_SERVICE: requested protocol-test-v1, returned protocol-test-v1 |
| ptest-openai · ASSISTED · brief-md | 2 | ANSWERED 2 | CORRECT 1, INVALID_FORMAT 1 | 0.50 (n=2, missing 0) | 0.50 (n=2, missing 0) | 0.00 (n=2, missing 0) | 1.00 (n=1, missing 1) | 12.00 (n=2, missing 0) | LOOPBACK_TEST/TEST_SERVICE: requested protocol-test-v1, returned protocol-test-v1 |
| ptest-openai · STATIC_UNASSISTED · brief-md | 2 | ANSWERED 2 | CORRECT 1, INCORRECT 1 | 0.50 (n=2, missing 0) | 1.00 (n=2, missing 0) | 0.00 (n=2, missing 0) | 0.50 (n=2, missing 0) | 13.00 (n=2, missing 0) | LOOPBACK_TEST/TEST_SERVICE: requested protocol-test-v1, returned protocol-test-v1 |

**Paired (provider): ptest-openai vs ptest-anthropic** — 3 pair(s), 1 unpaired; mean difference (b − a) 0.00; engineering reading: fewer than 6 complete pairs or non-zero differences — a direction, not a significance claim
> parameters are recorded, not equated: equal names (e.g. two 'high' settings) do not mean equal compute, and a fixed seed on a real API does not reproduce an answer

**Paired (representation): ir-json vs prose** — not applicable: this track plans no unit with representation = ir-json

**Paired (assistance): STATIC_UNASSISTED vs ASSISTED** — 3 pair(s), 1 unpaired; mean difference (b − a) 0.33; engineering reading: fewer than 6 complete pairs or non-zero differences — a direction, not a significance claim

## Track `synthetic_representation` — 16 planned unit(s)

| condition | planned | call outcomes | behaviour | correct | format valid | refused | program corresponds | out tokens | identity |
|---|---|---|---|---|---|---|---|---|---|
| ptest-anthropic · STATIC_UNASSISTED · ir-json | 4 | ANSWERED 1, EMPTY_CONTENT 1, MODEL_UNAVAILABLE 1, TRUNCATED 1 | EMPTY 1, INVALID_FORMAT 2, NO_MODEL_ANSWER 1 | 0.00 (n=3, missing 1) | 0.00 (n=2, missing 2) | 0.00 (n=3, missing 1) | MISSING (n=0, missing 0, n/a 4) | 9.67 (n=3, missing 1) | LOOPBACK_TEST/TEST_SERVICE: requested protocol-test-v1, returned protocol-test-v1; LOOPBACK_TEST/UNKNOWN: requested protocol-test-v1, returned None |
| ptest-anthropic · STATIC_UNASSISTED · prose | 4 | ANSWERED 2, AUTH_ERROR 1, MALFORMED_RESPONSE 1 | CORRECT 1, INCORRECT 1, NO_MODEL_ANSWER 2 | 0.50 (n=2, missing 2) | 1.00 (n=2, missing 2) | 0.00 (n=2, missing 2) | MISSING (n=0, missing 0, n/a 4) | 9.00 (n=2, missing 2) | LOOPBACK_TEST/UNKNOWN: requested protocol-test-v1, returned None; LOOPBACK_TEST/TEST_SERVICE: requested protocol-test-v1, returned protocol-test-v1 |
| ptest-openai · STATIC_UNASSISTED · ir-json | 4 | ANSWERED 4 | CORRECT 2, INVALID_FORMAT 1, PARTIAL 1 | 0.50 (n=4, missing 0) | 0.75 (n=4, missing 0) | 0.00 (n=4, missing 0) | MISSING (n=0, missing 0, n/a 4) | 13.25 (n=4, missing 0) | LOOPBACK_TEST/TEST_SERVICE: requested protocol-test-v1, returned protocol-test-v1 |
| ptest-openai · STATIC_UNASSISTED · prose | 4 | ANSWERED 3, CONTENT_REFUSAL 1 | CORRECT 1, INCORRECT 1, INVALID_FORMAT 1, REFUSED 1 | 0.25 (n=4, missing 0) | 0.67 (n=3, missing 1) | 0.25 (n=4, missing 0) | MISSING (n=0, missing 0, n/a 4) | 8.25 (n=4, missing 0) | LOOPBACK_TEST/TEST_SERVICE: requested protocol-test-v1, returned protocol-test-v1; LOOPBACK_TEST/TEST_SERVICE: requested protocol-test-v1, returned protocol-test-other |

**Paired (provider): ptest-openai vs ptest-anthropic** — 5 pair(s), 3 unpaired; mean difference (b − a) -0.20; engineering reading: fewer than 6 complete pairs or non-zero differences — a direction, not a significance claim
> parameters are recorded, not equated: equal names (e.g. two 'high' settings) do not mean equal compute, and a fixed seed on a real API does not reproduce an answer

**Paired (representation): ir-json vs prose** — 5 pair(s), 3 unpaired; mean difference (b − a) -0.20; engineering reading: fewer than 6 complete pairs or non-zero differences — a direction, not a significance claim

**Paired (assistance): STATIC_UNASSISTED vs ASSISTED** — not applicable: this track plans no unit with assistance = ASSISTED

## Not run

- lamp-ir-json · ASSISTED: the task defines no assistance material
- lamp-prose · ASSISTED: the task defines no assistance material
- shortcut-ir-json · ASSISTED: the task defines no assistance material
- shortcut-prose · ASSISTED: the task defines no assistance material

## Notes

- the two experiment lines are reported apart and never pooled into one success rate
- model scores count only responses the model produced; transport / auth / limit / budget / cancel / blocked units are MISSING (never 0, never 1); refusals and invalid answers count as not correct
- a relay route reports a model name it cannot prove; conclusions about a provider's model need a route whose identity is verifiable
- tasks: lamp-ir-json, lamp-prose, orders-deviation, shortcut-ir-json, shortcut-prose
