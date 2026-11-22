> **说明(2026-11-22):** 本文件写于第四版实验(3 道题、2 个被测模型、3 档护栏)。当前第一轮阶段性报告的设计、统计方法与局限以 `report-advisor.html` / `攻击模型同构研究-第一轮报告.html` 为准;本文件的相关工作与伦理部分仍适用。

# Methods, positioning, ethics, limitations

## Research question

Two isomorphic state machines — one an attack model, one a legitimate business process —
carry identical logic. Does a safety restriction cause a model to lose the ability to solve
the legitimate business problem? And is any refusal driven by the domain, the surface
vocabulary, or the shape of the task?

## Design

A fully-crossed grid, all answers graded against exact ground truth:

| factor | levels |
|---|---|
| subject model | `deepseek-chat` (weak native guardrails), `gpt-6.2-astra` (strong, current frontier) |
| guardrail (system prompt) | off · generic ("decline harmful requests") · explicit (names attack paths / failed states / removing controls) |
| vocabulary arm | attack · business (real-world twin) · abstract (`s1..sn`, `a1..am`) |
| task | shortest path to bad · shortest path to **success** (benign-goal control) · minimal control set |
| model family | A (TCP⇄tenancy) · B (TLS⇄loan) · C (WPA2⇄credential) |
| repeats | 20 per cell (sampling: DeepSeek temp 0.8; gpt-6.2-astra temp fixed at 1) |

The three vocabulary arms are **exactly isomorphic** (z3-verified), so any difference across
them is caused by naming, not by logic. The two path tasks share everything except the
target state (bad vs success), isolating "is it the path task or the bad *target* that is
refused". The guardrail levels give a dose-response. Output is required as JSON
`{"status","actions"}`, so refusal and answer are read objectively from structure.

## Measures and grading

* **Primary outcome** per call: `refused | correct | wrong | unparseable`, graded against the
  exact ground truth (`ground_truth.py`: BFS shortest paths; exhaustive minimal control set
  with the constraint that the success state stays reachable).
* **Refusal (annotator A)**: the model's own `status` field plus whether a usable answer was
  returned. Because output is structured, this is objective.
* **Refusal (annotator B)**: an independent judge model (`gpt-5-mini`) re-labels a stratified
  sample of raw replies; `stats.py` reports Cohen's kappa (label validation).
* **Statistics** (`stats.py`, pure Python): Wilson 95% intervals on every rate; two-sided
  Fisher exact for guardrail (off vs explicit) on the business problems; dose-response across
  guardrail levels; vocabulary and task-shape contrasts.

## Positioning (related work to cite in a write-up)

* **Over-refusal / exaggerated safety** benchmarks: XSTest, OR-Bench, PHTest, WildGuard —
  this study is in that family but adds *formally isomorphic* pairs and *decidable ground
  truth*, so "lost capability" is measured, not just "refused".
* **Alignment / safety tax**: the observation that safety training can cost capability.
* **Semantic-transformation jailbreaks** (cipher, translation, domain-shift): the mirror
  image — there the transform is used to *evade*; here it is used to *measure* the collateral
  cost on legitimate work, with a verifier that rules out the evasion reading.

## Ethics

Isomorphic relabelling is dual-use: it can also launder attack planning into business
language. This study uses it only to *measure* over-refusal, on abstract reachability
problems with no operational exploit content, and reports a safety-positive framing (the risk
is over-refusal of legitimate work, and separately that disguise does not unlock capability a
model would otherwise withhold — the unguarded baseline solves everything anyway). The models
are labelled transition systems, not runnable exploits.

## Limitations

1. **Isomorphism is constructed, not discovered.** The twins are programmatic relabellings,
   so z3 "proving" isomorphism is confirming a construction. A stronger design has an
   independent author formalise the business process from a prose spec without seeing the
   attack model, then checks isomorphism — making it a finding. Noted as future work; one such
   independent formalisation would strengthen the claim.
2. **Naturalness of the twins is argued, not rated.** A manipulation check (does an unguarded
   model read the business arm as an ordinary business process?) supports it; blind human
   naturalness ratings by domain experts are not done.
3. **Guardrails are system prompts, not training.** Real safety behaviour is largely trained
   in (RLHF / constitutional). We include a strong natively-aligned model (`gpt-6.2-astra`)
   with no system prompt as the closest available proxy for trained guardrails, but a clean
   test of *trained* over-refusal needs model-internal access we do not have.
4. **Two subjects.** Broader model coverage (Claude, Gemini, open models) would generalise.
5. **Model/version drift.** Hosted `deepseek-chat` and `gpt-6.2-astra` can change; we record
   the call date and the provider-returned model id with every response.
6. **Task ceiling.** Shortest paths are 2–4 steps and minimal control sets are size 2;
   unguarded accuracy is near-ceiling, so this measures refusal, not graded degradation.
   Parameterised larger isomorphic families would add an accuracy-degradation axis.
7. **Pilots in the appendix.** Two earlier pilots are kept for transparency: v1 leaked the
   answer categories ("is this an attack model?") into the prompt; v2 fixed that and measured
   recognition. Both are superseded by this capability design and are reported as pilots.
