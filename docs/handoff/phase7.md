# Phase 7 handoff — reproduction and closeout

Machine-readable companion: [`phase7.manifest.json`](phase7.manifest.json). Protocols, status-field definitions and
method: [`../research/protocol.md`](../research/protocol.md). Gaps: [`../research/known-gaps.md`](../research/known-gaps.md).
Task book: [`../execution/phase-7.md`](../execution/phase-7.md).

Developer (coding) models: Claude Opus 5.5 (general engineering, reproduction, report) and Claude Opus 4.8 (domain
mechanism, criteria, K01/K02) — a division of labour, run by one session, recorded apart from the models under test
(no result is attributed to a developer model, and the split implies no capability claim).

## P7-01 — a new held-out case and a frozen dual-model evaluation (complete, with one blocker)

- **The two real cases.** `orders-tenant-isolation` (reused from 5B) and a **new** held-out case
  `research/cases/ratelimit-token-bucket` — a token-bucket capacity limiter, a *different* mechanism from the order
  service and tenant isolation, built to check the method generalises beyond the first sample. It is a project-owned
  finite program (`research_ratelimit.py`), honestly labelled `own_test_variant`; its defect/fix is one line of the
  refill (uncapped vs capped), its secure-spec model has the `within_capacity` invariant (Z3 `NO_WITNESS_WITHIN_BOUND`),
  and its oracle reads the real token count. Against the recorded runs the uncapped variant **DEVIATES** and the capped
  variant **CORRESPONDS**; its own tests pass.
- **Upstream case — NOT_RUN (blocker).** The preferred second case was a public upstream mechanism. Installing or
  vendoring an external project with its maintainer regression and pinning revision/license is a reproducibility risk
  in this sandboxed VM (frozen `uv.lock`, tight disk), so the new case is an own fixture instead: the method-generality
  check is met, but the intended **upstream↔own contrast is not**. Unblock: vendor a small permissively-licensed
  upstream mechanism with its tests at a pinned revision (entry point in `phase7.manifest.json → blocked`).
- **Frozen evaluation.** `research/studies/p7-holdout`: before/after (defect/fix) × 2 models × 2 replicates = **8**
  requests, `STATIC_UNASSISTED`, scorer `ratelimit.capacity-judgment@1`, reference answers fixed from the program runs
  before any model saw the task (no leakage: `ANSWER_LEAK` guard). Result: 8/8 answered, both models **correct on every
  unit**, program-correspondence `CORRESPONDS`, overflow step identified. An engineering/generality batch, not a
  ranking: the provider comparison is relay-only (identity relay-reported), the sample is tiny, the metric was fixed
  first. Phase 6's two synthetic bases are unchanged (not re-added to pad the count).

## P7-02 — K01–K03 closed, total check, reproduction, closeout (complete; acceptance-local is the baseline command)

- **K01 / K02 / K03 closed in place** (committed earlier this phase; details and tests in
  [`../research/known-gaps.md`](../research/known-gaps.md)): the receipt binds the concrete target (not a label); the
  attack-step budget is enforced at the admit point with a durable, retry-idempotent, pause/resume-safe ledger; the
  gate `detail` and the three condition states (true/false/unknown + missing) are shown.
- **Research total check.** `make research-check ARGS="--strict"` → **complete=True** (p5a, p5b, p6a, p6b, p7 all PASS;
  12 checks). `p7-unit` (K01/K02/K03 + the new fixture), `p7-case` (the held-out case validates and re-derives
  offline), `p7-holdout` (the dual-model batch).
- **Local total acceptance** (`make acceptance-local`) is the **baseline command**: phases 1–4 were complete=true at
  their revisions (a05c1d2 / b993dc9), and the phase-7 domain changes are covered by `p7-unit` and the re-run `d2`
  broker evidence. A full re-run needs the dev stack and ≥15 GiB free disk (currently less); the user runs it when
  that headroom is available.
- **Reproduction.** `scripts/p7_reproduce.py` does an automated clean-room **offline** recheck — it validates every
  committed case and reads the committed results with no model call and no network — and `scripts/offline_bundle.py`'s
  manifest now carries a `research_data` reference (cases/studies/results/rubric digests + source revision). A
  re-sampling path (`fal research study run`) makes new online calls and needs the user's own credentials and quota.
  Independent **human** reproduction is **PENDING** (an agent re-running is only automated reproduction).

## Final status (defined in `../research/protocol.md`)

| field | value | why |
|---|---|---|
| `engineering_ready` | **true** | the local pipeline builds, validates cases offline, runs the dual-model studies and reports; `research-check --strict` is complete. Engineering readiness is not support for any hypothesis |
| `experiment_execution_complete` | **true** | the dual-model batches (6B's 24 + the held-out 8) were requested, answered and scored with complete denominators |
| `findings_supported` | **descriptive only** | supported: the method + independent checks work on a second, different mechanism; both models were correct on every unit at this difficulty, no representation sensitivity observed. Not supported: any ranking / superiority, any verified provider comparison (relay identity), general attack-modelling capability |
| `independent_human_reproduction` | **PENDING** | automated clean-room offline recheck passes; no person has reproduced it yet |
| `original_adviser_scope_complete` | **false** | the original adviser scope included hiding a real attack purpose to test regulation evasion; that experiment was **not run** and these materials do not support that conclusion. Only the adviser can accept an adjusted scope |

## What the adviser asked

| question | answer the evidence supports |
|---|---|
| Is this a model with a software basis? | Yes — each case points to real source, subject capabilities, operations, a property and an independent program observation, and declares its abstraction limits and uncovered semantics (`research/cases/*`, `MECHANISM.md`). |
| Do the model's findings hold in the program? | Given separately: the model-internal verdict, the concrete regression/observation, and whether they correspond — `fal-conformance-result/v1`, with UNKNOWN kept when evidence is insufficient. |
| Does a fix change the corresponding behaviour? | Yes — comparable before/after (defect/fix) on tenant isolation and the token bucket, with the ordinary legal behaviour still holding (the capped bucket and the authorised accesses still work). |
| Can frontier models analyse these formal models? | On the models actually called, under a fixed setup, per case: both were correct on all 24 + 8 units at this difficulty; refusals/errors/failures counted apart; **not** extrapolated to all software (and these tasks were easy — K13). |
| Does a different business framing change the reasoning? | Only for the harmless synthetic problems with reviewed, verified-equal framings: no sensitivity was observed; **not** extrapolated to disguised real-attack use. |
| Was the original disguised-attack / regulation-evasion experiment done? | **No.** It was not run and the current materials do not support that conclusion — this difference is stated plainly for the adviser. |

In one paragraph: what exists now is a **local research system that can check software models and model answers** —
cases tied to real program observations, independent program/formal verification, dual-model studies with raw answers
and traceable scoring, strict checks, and an offline reproduction path. Paper-level novelty, broad applicability, and
full coverage of the original adviser goal each still need their own evidence; none is claimed here.

## Reproduce

```bash
make research-check ARGS="--strict"                        # offline case/protocol checks + the recorded studies
uv run --frozen python scripts/p7_reproduce.py             # automated clean-room offline recheck (no model call)
uv run --frozen python scripts/p7_holdout_case.py          # rebuild the held-out case + study from the program runs
uv run --frozen fal research study run research/studies/p7-holdout   # re-sample (needs your API credentials + quota)
make acceptance-local                                      # phases 1-4 local total acceptance (dev stack + disk)
```
