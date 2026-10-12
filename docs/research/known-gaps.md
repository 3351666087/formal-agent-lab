# Known gaps and research-goal coverage

Carried forward and extended by each phase. An unverified capability is marked *planned* or *not run*, never implied to
work.

## Carried from phase 4 (recorded)

| id | gap | where it bites | status after 7 |
|---|---|---|---|
| **K01** | 目标性质与凭据错配 — a target property and the issued credential can disagree | phase-4B MAL issuer / target reachability | **CLOSED (phase 7)** — a receipt's check basis now binds the concrete target identity (`CheckBasis.target_digest` + `model_digest`, from `TargetSecurity.target_digest()` = sha256 of property_id + reach_forbidden + kind), and `admission._target_security_covered` requires that digest to match the scenario target — a `property_id` label alone, or a receipt with no target digest, cannot authorise the step. Proof: `test_k01_same_name_different_target_cannot_reuse_credential` (same label, different `reach_forbidden` → reuse denied, correct target admits) and `test_k01_a_receipt_without_a_target_digest_is_not_enough` |
| **K02** | `LabPolicy.max_attack_steps` 未执行 — the policy field is declared but not enforced in the loop | phase-4B lab-controlled operating conditions | **CLOSED (phase 7)** — `gate.AttackBudget` enforces it at the admit point: one admitted governed action = one unit, the ledger is one file per run (shared across actors, durable across pause/resume), a retry of an already-admitted operation is not re-charged, and an over-budget governed action is DENIED with zero side effects. `max_attack_steps=1` admits exactly one. Proof: `test_k02_attack_budget_unit` and `test_k02_budget_of_one_admits_one_governed_action` (budget 1 → one compromise admitted, goal not reached; the ledger records one consumed unit) |
| **K03** | 门控详情未显示 `detail` — a gate decision's `detail` is not surfaced in the UI | phase-4B gate display | **CLOSED (phase 7)** — `web/src/components/Steps.tsx` `ConditionLine` shows the `detail` and keeps observed/required, and distinguishes holds true (✓) / false (✕) / unknown (?, 未知 — a null `holds` is no longer shown as ✕) and a missing observation. Type-checked; the three-state data is real (`test_k03_gate_conditions_carry_the_three_states_with_detail`) |

K01–K03 are closed in their original locations (domain-mal gate/admission/config, the broker CheckBasis, and the
Steps.tsx component). The attack-step budget is a runtime constraint (a durable ledger), not a UI number or an
actor-prompt instruction.

## Opened in 5A

| id | gap | effect | plan |
|---|---|---|---|
| **K04** | the bounded model conclusion for the ordinary case is `UNKNOWN` (Z3 times out at the case bound) while the recorded run does complete | the model-internal layer is inconclusive at that bound; the correspondence layer carries the decisive comparison | *expected and instructive* — it is exactly why independent program observation is kept as its own layer; a decisive verdict needs a smaller bound or a stronger checker, recorded as-is, not forced |
| **K05** | the platform validates an imported case **offline** (digests, identities, separation) but does not recompute software **tree digests** (it has no checkout) | a case imported to the platform is trusted for its tree digests; those are verified by `fal research validate --repo` and the research check on a checkout | acceptable for 5A; 5B/7 may add a server-side revision check if a checkout is provisioned |

## Opened in 5B

| id | gap | effect | plan |
|---|---|---|---|
| **K06** | the base order service has no per-tenant authentication; tenant isolation is only enforced by the phase-5B research fixture, not by the default service | the default service is not a secure multi-tenant product; isolation is a *research fixture* property, clearly separated from the default startup path | by design — 5B studies the authorization component, not a claim that the shipped service isolates tenants; a production isolation layer is out of scope |
| **K07** | the isolation abstraction covers read/write as one `access(subject, tenant)` action over a fixed 2×2 grant; concurrency, token strength/transport, and partial-read leakage not visible in stored state are not modelled | the correspondence covers the recorded attempts only; a cross-tenant request whose effect is not observable in the tenant's state stays UNKNOWN (demonstrated) | the uncovered semantics are declared in the case (`uncovered_semantics`); phase 7 may widen the model if a case needs it |

## Opened in 6A

| id | gap | effect | plan |
|---|---|---|---|
| **K08** | both real models were reached only through a third-party relay (`COMPATIBLE_RELAY`, api.uheapi.com): the returned model names are the relay's report; the official Anthropic route is BLOCKED (no `FAL_ANTHROPIC_API_KEY`), and there is no official OpenAI credential | the real results verify the adapters end to end and give an engineering reading, but support **no** formal provider comparison (`provider_comparison_supported: false` in the evidence) | add official credentials (git-ignored `.env`) and re-run `p6a-real` / the 6B studies on `OFFICIAL_NATIVE` routes |
| **K09** | the relay route for Claude Opus 5.5 changed during the session: 503 "no available accounts", then 404 "not supported by any configured account in this group", then answered — all kept in the ledger history | route instability is a result, not hidden: earlier samples of those units remain recorded; the pre-registered call cap was raised once (8 → 12) with the reason written into the study | none needed beyond recording; a stable official route removes it |
| **K10** | an unflagged refusal written as prose is not detected heuristically | it is scored `INVALID_FORMAT` with the visible text kept, never `REFUSED` | 6B scorers may classify it explicitly |
| **K11** | token accounting differs by provider: Anthropic `input_tokens` excludes prompt-cache reads / writes (the relay applied caching once: 2 input + 1293 cache-write tokens), OpenAI `prompt_tokens` includes cached tokens; the relay reported no reasoning tokens for GPT-6 Astra; the first two Claude records predate the cache-write / thinking-token mapping (their raw bodies hold the full usage) | cost figures are recorded as reported, not equated across providers | keep comparing from the raw usage when it matters |
| **K12** | studies run locally (a sequential runner with a durable ledger); the platform imports results read-only — Temporal does not schedule studies | no platform-side pause / resume of a study; resume is the local runner's (ledger-based, budget not regained) | phase 7 may move study execution behind the platform if long studies need it |

## Opened in 6B

| id | gap | effect | plan |
|---|---|---|---|
| **K13** | the frozen 6B tasks are easy enough that both models scored 100% on all 24 units | the batch verifies the pipeline and shows no deviation, but does not discriminate the models or stress program-grounded analysis | Phase 7 (or a later study) can add harder cases built on the 5A/5B machinery; the scorers and study schema already support it |
| **K14** | no representation sensitivity was observed because the two business framings share identical actions/goal/answer (only the narrative differs) | the representation comparison is conservative by construction; a framing that also changes surface information would be a *different* task, not an equivalence test | a graded set of framings (with verified-equal cores) is a Phase 7 option |
| **K15** | both 6B models answered only through the relay; the per-track provider comparison is engineering-only (identity relay-reported) | no verified Claude-vs-GPT conclusion is drawn (same as K08) | configure the official routes and re-run |

## Original research-goal coverage (5A + 5B)

| goal | coverage |
|---|---|
| an implementation-level software **safety** property observable on the real local service, with clear subject capabilities and action semantics | **done (5B)** — `orders-tenant-isolation`: subject/resource/capability/trust-boundary/action/property/oracle in `MECHANISM.md`; observed on the running fixture over real SQLite |
| defect/fix independent regression + model↔program correspondence, three result classes | **done (5B)** — defect **DEVIATES**, fix **CORRESPONDS**, rejected-write **UNKNOWN**; model conclusion, program regression and correspondence kept apart |
| oracle reads real state, never a self-reported success | **done (5B)** — each outcome read back through the tenant's own authorized principal; unobservable → UNKNOWN |
| phase-6 task material vs reference-answer boundary | **done (5A+5B)** — `task_input` (model + property + fixture/mechanism) vs `reference` (expected verdicts), separation enforced on import |

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
