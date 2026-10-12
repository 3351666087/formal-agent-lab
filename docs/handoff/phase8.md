# Phase 8 handoff — defensive attack-graph analysis, at scale

A self-initiated expansion, asked for by the user: the cyber domain was too thin (a 3-node "attack graph"), the tasks
too easy to be worthy of a frontier model, and the real-call count too small. Phase 8 answers all three.

Machine-readable companion: [`phase8.manifest.json`](phase8.manifest.json). Task book:
[`../execution/phase-8.md`](../execution/phase-8.md). Earlier closeout: [`phase7.md`](phase7.md).

## What it is

A real formal **attack-graph analysis** domain for defence. An attack graph is an abstract AND/OR dependency model
(entry footholds → intermediate steps → a target) — the standard object of threat-model / attack-graph analysis. The
steps are abstract graph nodes (`reach`, `pivot`, `escalate`, `access`), not operational exploitation instructions.
Each task is a hard question a security analyst would ask, and every answer is computed and **cross-checked by the Z3
verifier / the model semantics**, so the ground truth is objective, not a human opinion
(`packages/domain-mal/src/formal_lab_domain_mal/analysis.py`).

Four question kinds (`research/studies/cyber-attackgraph`, 48 graphs, 12–20 nodes, 183 tasks):

| kind | question | ground truth |
|---|---|---|
| `shortest_cost` | minimum attack-path cost to the target (incl. the final step) | Z3 `OPTIMIZE_OBJECTIVE` |
| `reachability` | is the target reachable with a given defence set deployed | Z3 `GOAL_REACHABILITY` |
| `min_defense` | smallest number of defences that cut **every** path (AND/OR min-cut) | min-cut search, Z3-confirmed |
| `step_enabled` | is a derived step enabled in a given partial state | AND/OR semantics |

## The real batch (P8-02)

**1098 real dual-model calls** (183 tasks × 2 models × 3 replicates), ~2.2 h, every unit model-produced. Not volume
for its own sake — the tasks discriminate, and the result is nuanced.

| model | correct | answered-only | wrong | refused | notes |
|---|---|---|---|---|---|
| GPT-6 Astra (relay) | **0.96** | 0.96 | 21 | 0 | answered everything |
| Claude Opus 5.5 (relay) | **0.94** | **0.977** | 12 | **22** | declined 22 security-framed tasks (`stop_reason: refusal`) |

Per question kind (correct rate):

| kind | GPT-6 | Opus-5.5 | hardest? |
|---|---|---|---|
| `min_defense` (min-cut) | 1.00 | 1.00 | both perfect — the combinatorial one did not trip them |
| `shortest_cost` | 0.99 | 1.00 | near-perfect |
| `reachability` | 1.00 | 0.89 | Opus refused 16 here; 0 wrong when it answered |
| `step_enabled` | 0.86 | 0.88 | **the discriminator** — both make real AND/OR semantic errors |

Findings, stated plainly:

1. **The tasks discriminate.** `step_enabled` (is this AND/OR step enabled in this state?) is where both models make
   genuine errors (~86–88%), despite looking the simplest — precise AND-vs-OR reasoning on a specific step is harder
   for them than the optimisation questions. The min-cut, which looks hardest, both solve perfectly.
2. **Claude's safety layer refused 22/549 (4%)** of the defensive attack-graph tasks (`stop_reason: refusal`, empty
   content), concentrated on `reachability` and `step_enabled`; GPT-6 never refused. This is a safety-vs-analysis
   tension on security-framed formal tasks, not a quality gap — on the tasks Claude did answer it was near-perfect
   (97.7%). Reported as a refusal, counted as not-correct, never hidden.
3. **No ranking claim.** The paired difference is ~0.02 and both answer through a relay (identity relay-reported), so
   this is a hard, discriminating, verifier-grounded experiment — not a verified GPT-vs-Claude ranking.

## Checks and reproduction

- `make research-check ARGS="--group p8"` — `cyber-attackgraph` check: the study validates and is data-separated
  (answers wrapped `{value:…}` so no bare integer leaks into the task), a sample of the committed ground truths
  **re-derive and are Z3-confirmed** (the answers are machine-checked, not asserted), and the scorer labels a scripted
  loopback run correctly. No model call.
- `uv run --frozen python scripts/cyber_run.py` — the real batch; resumable (saved answers reused).
- Results: `research/results/cyber-attackgraph/report.md`; raw answers + evaluations per unit; evidence
  `docs/execution/evidence/research/cyber/{check,run}.json`. Imported into the order project's research studies, so
  the Web UI **基准对比** shows every unit and its raw answer.

## Caveats (unchanged, stated up front)

- The attack graphs are abstract formal models for defensive analysis, **not scans of a real network**;
  `program_correspondence` here means the answer agrees with the Z3 verifier, not a program observation.
- Relay identity is reported, not verified. A verified provider comparison needs official routes (`FAL_*` official
  credentials).

```bash
make research-check ARGS="--group p8"
uv run --frozen python scripts/cyber_run.py        # resumable real batch
uv run --frozen python scripts/handoff_phase8.py   # regenerate the manifest from the committed report
```
