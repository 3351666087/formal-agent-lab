# Known gaps and research-goal coverage

Carried forward and extended by each phase. An unverified capability is marked *planned* or *not run*, never implied to
work.

## Carried from phase 4 (recorded, not reopened in 5A)

| id | gap | where it bites | status in 5A |
|---|---|---|---|
| **K01** | 目标性质与凭据错配 — a target property and the issued credential can disagree | phase-4B MAL issuer / target reachability | recorded; **5B** judges whether K01 affects its real path |
| **K02** | `LabPolicy.max_attack_steps` 未执行 — the policy field is declared but not enforced in the loop | phase-4B lab-controlled operating conditions | recorded; **5B** judges whether K02 affects its real path |
| **K03** | 门控详情未显示 `detail` — a gate decision's `detail` is not surfaced in the UI | phase-4B gate display | recorded; UI-only, no effect on 5A correspondence |

Phase 7 confirms closure of K01–K03 across the track.

## Opened in 5A

| id | gap | effect | plan |
|---|---|---|---|
| **K04** | the bounded model conclusion for the ordinary case is `UNKNOWN` (Z3 times out at the case bound) while the recorded run does complete | the model-internal layer is inconclusive at that bound; the correspondence layer carries the decisive comparison | *expected and instructive* — it is exactly why independent program observation is kept as its own layer; a decisive verdict needs a smaller bound or a stronger checker, recorded as-is, not forced |
| **K05** | the platform validates an imported case **offline** (digests, identities, separation) but does not recompute software **tree digests** (it has no checkout) | a case imported to the platform is trusted for its tree digests; those are verified by `fal research validate --repo` and the research check on a checkout | acceptable for 5A; 5B/7 may add a server-side revision check if a checkout is provisioned |

## Original research-goal coverage (5A)

| goal | 5A coverage |
|---|---|
| tie software revision ↔ model ↔ validation ↔ provider model as separate identities | **done** for the first three (`SoftwareSource`, `ModelRef`, artifacts by sha); the provider-model identity is a phase-6 task input, reserved not implemented |
| reject failed references / property mismatch / before-after mix-up / changed-but-unsealed content on import | **done** — `validate_case` + platform import reject all of these (see protocol.md; `test_research_validate.py`) |
| keep model conclusion, program regression and correspondence apart; `UNKNOWN`/`UNCONFIRMED`/`SPURIOUS` distinct | **done** — `fal-conformance-result/v1` + `decide_correspondence` |
| one ordinary business case end-to-end, a conclusion traceable to model/program/observation/test | **done** — `research/cases/orders-p2-speed` (belief DEVIATES, revised CORRESPONDS) |
| case evidence views reusing ModelWorkbench / Evidence | **done** — ModelWorkbench 研究案例 tab, Evidence 对应验证 tab |
| shared research-check entry for phases 5–7 | **done** — `make research-check` (groups p5a–p7; p5b–p7 NO_CHECKS until registered) |
| domain properties (attack-graph etc.) | **5B** — out of 5A scope; 5A validates the generic protocol only |
| synthetic_representation track | **not opened in 5A**; fixed, reviewed synthetic problems, studied later |
| formal abstraction-preservation proof | **not claimed** — 5A does empirical conformance only (see method, protocol.md) |
