# Enterprise attack-surface analysis (verifier-grounded)

Study `cyber-enterprise` · primary metric `correct` · rubric fal-research-rubric@1 · 3 replicate(s) per condition

Ledger: 720 response record(s), 720 call(s), 724 HTTP attempt(s), 2 possibly billed unconfirmed attempt(s).

## Track `formal_model_analysis` — 720 planned unit(s)

| condition | planned | call outcomes | behaviour | correct | format valid | refused | program corresponds | out tokens | identity |
|---|---|---|---|---|---|---|---|---|---|
| claude-opus-5-5-relay · STATIC_UNASSISTED · steplist | 360 | ANSWERED 340, CONTENT_REFUSAL 19, TRUNCATED 1 | CORRECT 336, INCORRECT 4, INVALID_FORMAT 1, REFUSED 19 | 0.93 (n=360, missing 0) | 1.00 (n=341, missing 19) | 0.05 (n=360, missing 0) | 0.99 (n=340, missing 20) | 602.64 (n=360, missing 0) | COMPATIBLE_RELAY/RELAY_REPORTED: requested claude-opus-5-5, returned claude-opus-5-5 |
| gpt-6-astra-relay · STATIC_UNASSISTED · steplist | 360 | ANSWERED 360 | CORRECT 349, INCORRECT 11 | 0.97 (n=360, missing 0) | 1.00 (n=360, missing 0) | 0.00 (n=360, missing 0) | 0.97 (n=360, missing 0) | 245.43 (n=360, missing 0) | COMPATIBLE_RELAY/RELAY_REPORTED: requested gpt-6-astra, returned gpt-6-astra |

Rubric signals (heuristic, recorded only — not adjudicated, no human review):
- claude-opus-5-5-relay · STATIC_UNASSISTED · steplist: answered_field 340/340, cites_structure 340/340, explains 340/340
- gpt-6-astra-relay · STATIC_UNASSISTED · steplist: answered_field 360/360, cites_structure 360/360, explains 360/360

**Paired (provider): gpt-6-astra-relay vs claude-opus-5-5-relay** — 360 pair(s), 0 unpaired; mean difference (b − a) -0.04; enough paired differences for the reported test
> parameters are recorded, not equated: equal names (e.g. two 'high' settings) do not mean equal compute, and a fixed seed on a real API does not reproduce an answer


## Notes

- the two experiment lines are reported apart and never pooled into one success rate
- model scores count only responses the model produced; transport / auth / limit / budget / cancel / blocked units are MISSING (never 0, never 1); refusals and invalid answers count as not correct
- a relay route reports a model name it cannot prove; conclusions about a provider's model need a route whose identity is verifiable
- tasks: ent-1000-chokepoints, ent-1000-min_defense, ent-1000-reach_from_entry, ent-1000-reachability, ent-1000-shortest_cost, ent-1000-step_enabled, ent-1001-chokepoints, ent-1001-min_defense, ent-1001-reach_from_entry, ent-1001-reachability, ent-1001-shortest_cost, ent-1001-step_enabled, ent-1002-chokepoints, ent-1002-min_defense, ent-1002-reach_from_entry, ent-1002-reachability, ent-1002-shortest_cost, ent-1002-step_enabled, ent-1003-chokepoints, ent-1003-min_defense, ent-1003-reach_from_entry, ent-1003-reachability, ent-1003-shortest_cost, ent-1003-step_enabled, ent-1004-chokepoints, ent-1004-min_defense, ent-1004-reach_from_entry, ent-1004-reachability, ent-1004-shortest_cost, ent-1004-step_enabled, ent-1005-chokepoints, ent-1005-min_defense, ent-1005-reach_from_entry, ent-1005-reachability, ent-1005-shortest_cost, ent-1005-step_enabled, ent-1006-chokepoints, ent-1006-min_defense, ent-1006-reach_from_entry, ent-1006-reachability, ent-1006-shortest_cost, ent-1006-step_enabled, ent-1007-chokepoints, ent-1007-min_defense, ent-1007-reach_from_entry, ent-1007-reachability, ent-1007-shortest_cost, ent-1007-step_enabled, ent-1008-chokepoints, ent-1008-min_defense, ent-1008-reach_from_entry, ent-1008-reachability, ent-1008-shortest_cost, ent-1008-step_enabled, ent-1009-chokepoints, ent-1009-min_defense, ent-1009-reach_from_entry, ent-1009-reachability, ent-1009-shortest_cost, ent-1009-step_enabled, ent-1010-chokepoints, ent-1010-min_defense, ent-1010-reach_from_entry, ent-1010-reachability, ent-1010-shortest_cost, ent-1010-step_enabled, ent-1011-chokepoints, ent-1011-min_defense, ent-1011-reach_from_entry, ent-1011-reachability, ent-1011-shortest_cost, ent-1011-step_enabled, ent-1012-chokepoints, ent-1012-min_defense, ent-1012-reach_from_entry, ent-1012-reachability, ent-1012-shortest_cost, ent-1012-step_enabled, ent-1013-chokepoints, ent-1013-min_defense, ent-1013-reach_from_entry, ent-1013-reachability, ent-1013-shortest_cost, ent-1013-step_enabled, ent-1014-chokepoints, ent-1014-min_defense, ent-1014-reach_from_entry, ent-1014-reachability, ent-1014-shortest_cost, ent-1014-step_enabled, ent-1015-chokepoints, ent-1015-min_defense, ent-1015-reach_from_entry, ent-1015-reachability, ent-1015-shortest_cost, ent-1015-step_enabled, ent-1016-chokepoints, ent-1016-min_defense, ent-1016-reach_from_entry, ent-1016-reachability, ent-1016-shortest_cost, ent-1016-step_enabled, ent-1017-chokepoints, ent-1017-min_defense, ent-1017-reach_from_entry, ent-1017-reachability, ent-1017-shortest_cost, ent-1017-step_enabled, ent-1018-chokepoints, ent-1018-min_defense, ent-1018-reach_from_entry, ent-1018-reachability, ent-1018-shortest_cost, ent-1018-step_enabled, ent-1019-chokepoints, ent-1019-min_defense, ent-1019-reach_from_entry, ent-1019-reachability, ent-1019-shortest_cost, ent-1019-step_enabled
