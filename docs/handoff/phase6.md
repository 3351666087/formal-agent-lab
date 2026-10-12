# Phase 6 handoff

Machine-readable companion: [`phase6.manifest.json`](phase6.manifest.json) (`phase-handoff/v1`). Protocols, types,
functions and the scoring interface: [`../research/protocol.md`](../research/protocol.md#phase-6a-provider-calls-raw-answers-and-evaluation).
Gaps: [`../research/known-gaps.md`](../research/known-gaps.md). Task book: [`../execution/phase-6a.md`](../execution/phase-6a.md).

Developer (coding) models: Claude Opus 5.5 (6A), Claude Opus 4.8 (6B). The models under test are recorded per
experiment unit (provider, route, requested and returned model); no result is attributed to the developer model.
**Phase 6 is complete** (6A + 6B), with one documented limitation: the real dual-model calls ran through a relay, so
the provider comparison is engineering-only and no verified Claude-vs-GPT conclusion is drawn (K08/K15).

## 6A — provider calls, raw answers and evaluation (complete)

### P6A-01 · provider adapters and the raw response record

- **Adapters** in `formal_lab_strategies.model_clients`: `OpenAIChatAdapter` (Chat Completions) and
  `AnthropicMessagesAdapter` (native Messages API), built by `research_adapter(ProviderConfig)`; `research_call` sends
  one request with a fixed number of network retries and **no** JSON forcing, re-asking or rule fallback. Existing
  planners keep their structured-decision path (`complete_json`, `RULE_FALLBACK`) unchanged.
- **Routes** are classified from the endpoint host — `OFFICIAL_NATIVE`, `COMPATIBLE_RELAY`, `LOOPBACK_TEST` — and a
  study that declares another route is refused, so a relay is never recorded as an official endpoint.
- **`fal-research-response/v1`** keeps, per call: experiment identity, call identity (provider, api + version, endpoint
  without credentials, route, requested / returned model, model switch, identity status, response and request ids,
  parameters as sent), the raw body as returned, visible text, finish reason as written, the explicit refusal field,
  truncation, tool calls, reasoning availability (`NOT_EXPOSED` / `SUMMARY_ONLY` — never claimed as raw reasoning),
  every HTTP attempt, and cost (usage as reported incl. thinking and cache tokens, latency, possibly-billed unconfirmed
  attempts). It is written **before** anything parses it.
- **How refusals and errors are told apart**: the call axis (`CallOutcome`) has a stable class for every case —
  a refusal *inside an HTTP success* is `CONTENT_REFUSAL`; 401 / 403 are `AUTH_ERROR`; 429 `RATE_LIMITED`; 5xx
  `PROVIDER_ERROR`; an unknown model `MODEL_UNAVAILABLE`; a lost response `UNCERTAIN` (possibly billed); not sent:
  `BUDGET_EXHAUSTED`, `CANCELLED`, `BLOCKED_NO_CREDENTIAL`. The answer axis (`AnswerStatus`) is separate.
- **How the actual model is confirmed**: `model_identity` is `CONFIRMED_BY_PROVIDER` only on an official route that
  names the model; on a relay it is `RELAY_REPORTED`; unnamed is `UNKNOWN`; `model_switched` marks a different model.
- **Credentials**: read only by the adapter layer via `read_setting` (`FAL_*` names, environment then the git-ignored
  `.env`); a provider's own variable (e.g. `ANTHROPIC_API_KEY`) is never read; no written file holds a key (redaction
  of echoed credentials; every check scans the files it wrote).

### P6A-02 · studies, independent scoring, two-track reports

- **`fal-research-study/v1`** (`research/studies/<study_id>/study.json`): tasks with their real purpose, input files
  vs a scorer-only reference, `STATIC_UNASSISTED` / `ASSISTED` (a mode a task does not define is NOT_RUN), providers,
  replicates, rubric, primary metric, limits, missing policy, pre-registered comparisons. `scripts/p6a_studies.py`
  builds the 6A studies from recorded data — every number in the ordinary task is quoted from case `orders-p2-speed`.
- **Runner** `formal_lab_eval.research`: raw response first, then `fal-research-evaluation/v1`; resume reuses a
  response only if the provider made it, otherwise calls again as a new sample (history kept, budget not regained);
  rescoring reuses responses and never calls a model.
- **Scorers** (registrable; 6B registers here — `register_scorer` or the `formal_lab.research_scorers` entry point):
  `orders.deviation-diagnosis@1` replays the *recorded program run* on the model revised by the answer;
  `synthetic.shortest-plan@1` replays the plan on the reference interpreter (program correspondence N/A).
- **Reports** per track, never pooled: call outcomes and behaviour labels over the planned denominator, metric
  aggregates with n / missing / not-applicable, cost, identity; paired comparisons along one dimension at a time with
  the parameter-comparability caveat.
- **Where answers live**: `research/results/<study_id>/responses/` (raw), `prompts/` (exactly what was sent),
  `evaluations/`, `ledger.jsonl` (every sample), `report.md`; `fal research study show …`; and in the Web UI under
  基准对比 → 研究评测 after `fal research study import` (read-only import that re-checks each response's digest).

### Validation

- `make research-check ARGS="--group p6a"`: **p6a-unit** (55 tests: the adapters against the protocol test service
  over real HTTP for every class, plus the study layer), **p6a-protocol** (23 assertions: all 24 units of
  `p6a-protocol` scripted through every call and answer class, budget before sending and not regained on resume, cancel
  before sending, resume reuse / new samples, rescoring without calls, no credential in any file), **p6a-real**
  (7 assertions).
- `tests/integration/test_research_platform.py`: study import → two tracks / 24 units → a unit's raw refusal readable
  → re-import replaces → a response edited after recording is rejected.

### Real endpoints (within the authorized test quota)

| Provider config | Route | Units | Result |
|---|---|---|---|
| `gpt-6-astra-relay` (`FAL_RESEARCH_GPT_API_KEY`) | COMPATIBLE_RELAY | STATIC, ASSISTED | both answered `slow[p2]=true`; the recorded run replayed on that revision CORRESPONDS (109/109 fields) → CORRECT; returned model `gpt-6-astra` (relay-reported); 66 / 83 output tokens |
| `claude-opus-5-5-relay` (`FAL_RESEARCH_CLAUDE_API_KEY`, native Messages protocol) | COMPATIBLE_RELAY | STATIC, ASSISTED | the relay first answered 503 "no available accounts", then 404 "not supported … in this group", then the model answered (all kept in the ledger). STATIC: `slow[p2]=true` → CORRESPONDS → CORRECT; ASSISTED: **two** fenced JSON blocks where one object was required → INVALID_FORMAT under the pre-registered rule; thinking present (SUMMARY_ONLY); 960 / 797 output tokens (456 / 477 thinking) |
| `claude-opus-5-5-native` (`FAL_ANTHROPIC_API_KEY`) | OFFICIAL_NATIVE | STATIC, ASSISTED | **BLOCKED** — no credential configured; nothing sent |

Ledger of `p6a-real`: 10 calls, 12 HTTP attempts, 0 possibly-billed unconfirmed attempts; 6 model-produced answers
(the first two GPT samples were made with the previously configured relay key and are kept as history). The paired
provider comparison (2 pairs, mean difference −0.50) is an **engineering reading** through one relay: identities are
relay-reported, so it is not a verified comparison of Anthropic's and OpenAI's models (K08).

### Blocked and next

- Official routes are blocked: no `FAL_ANTHROPIC_API_KEY` and no official OpenAI credential. Add them to the
  git-ignored `.env` and re-run `fal research study run research/studies/p6a-real` — answered units are reused, the
  blocked ones are called.
## 6B — domain criteria, the dual-model experiment and its reading (complete)

Developer model of 6B: Claude Opus 4.8 (coding identity; the models under test are recorded per unit). The two tracks
stay apart and are never pooled.

### P6B-01 · frozen criteria and experiment definition, no answer leakage

- **Rubric** `research/rubric/fal-research-rubric-1.json` — six dimensions with a fixed version and self-digest
  (`load_rubric` recomputes and checks it; the digest is in every report). Deterministic verifiers are primary; no LLM
  judge and no human review were used, so no dimension is marked expert-reviewed.
- **Program-grounded scorer** `orders.isolation-judgment@1`: judges tenant isolation on a recorded 5B run from the
  recorded observation + the 5B conformance verdict, not from the reference answer.
- **Frozen study** `research/studies/p6b-eval/` — 6 conditions × 2 models × 2 replicates = **24** requests, all
  `STATIC_UNASSISTED`: the real case `orders-tenant-isolation` before/after (defect / fix, judged from a factual
  transcript — grant table given, verdict not), and two synthetic base problems each in two harmless business framings
  that share one reference (verified-equal: same sample IR digest and shortest answer).
- **No answer leakage**: `load_study` rejects a reference answer that appears in any task input (`ANSWER_LEAK`), and
  the case-level split keeps a case and its derived tasks in one group.

### P6B-02 · the authorized batch, independent scoring, two-track results

- **Dry run first**: the whole study scripted against the loopback protocol test service (not a model) — every call
  and answer class, the scorers, the rubric digest and signals, the cost cap. Then the real batch.
- **Denominator = the 24 planned units**; a unit without a model answer is MISSING in the model metrics (never 0/1);
  refusals are never retried; repeat samples are not independent cases (clustered by case/problem); the primary metric
  `correct` was fixed before the run.
- **Result** (24/24 answered on both tracks): both models answered every unit and were **correct on every unit** — the
  program-grounded isolation judgments and the small synthetic plans. No representation sensitivity at this difficulty
  (the two framings gave the same answers). The per-track provider comparison is 0.00 mean difference, an **engineering
  reading** only (relay-reported identity, tiny sample). GPT-6 Astra used far fewer output tokens than Claude Opus 5.5
  (which emits thinking tokens); cost recorded, not equated. A pipeline-and-phenomenon batch, not a superiority claim.

### Validation

`make research-check ARGS="--group p6b"`: **p6b-unit** (6 tests: the isolation scorer grounded in the recorded run,
the frozen rubric, the answer-leak guard, the verified-equal framings) and **p6b-eval** (18 assertions: the scripted
dry run of all 24 units through every class, program-grounded scoring, synthetic N/A, the rubric digest and signals,
the cost cap, no credential written, then the real batch within quota).

### Phase 6 status

Phase 6 is **complete** (6A + 6B delivered and validated; the real dual-model batch ran and was scored). The provider
comparison is **engineering-only**: both 6B models answered through a relay (relay-reported identity, K08), and the
official routes are not configured, so no verified Claude-vs-GPT conclusion is drawn. Open gaps K13–K15 (easy tasks →
no discrimination; conservative framing → no representation sensitivity observed; relay-only identity) are in
[known-gaps.md](../research/known-gaps.md).

### Materials Phase 7 can freeze for reproduction

The studies `research/studies/p6a-protocol|p6a-real|p6b-eval`, the rubric, and `research/results/` (ledgers + raw
responses + evaluations + reports); the 5A/5B cases the real tasks draw on. None of these is a fresh held-out set for
Phase 7 — the cases were seen during Phase 6 and their derived tasks stay in the same split group. No conclusion is
drawn about the real-attack-disguise / regulation-evasion experiments, which were not run.
