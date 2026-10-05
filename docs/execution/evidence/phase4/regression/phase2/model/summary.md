# Model-assisted strategies: evidence against the configured endpoint

Generated 2026-10-05T10:41:15Z by `scripts/model_evidence.py`; model label `gpt-5.6-sol`. Real-model reruns claim only request and evidence reproducibility.

| check | status | claim |
|---|---|---|
| requests | PASS | the first request (before any model answer) is identical for the same model, scenario and seed |
| resume | PASS | a fresh process restores the planner checkpoint at the boundary and every call keeps its evidence |
| per_step | PASS | every call records the configured label, the model the provider returned, request config, attempts, outcome and usage as reported |
| mixed | PASS | a real-model participant and a Z3 participant take turns on one run; per-actor usage is kept apart |

Details (digests, per-call records, run summaries) are in `evidence.json`.
