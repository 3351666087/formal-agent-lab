#!/usr/bin/env python3
"""Build the phase-8 defensive attack-graph analysis study (cyber-attackgraph): many formal AND/OR attack-graph
models, and for each a set of hard analysis questions whose answers are computed and cross-checked by the Z3 verifier
— shortest attack-path cost, target reachability under a deployed defence set, the minimum number of defences that
cut every path, and whether a derived step is enabled. Each question is a genuine piece of security-analyst reasoning
over a formal model, with an objective machine-checked ground truth.

Writes research/studies/cyber-attackgraph/ (study.json, graphs/, inputs/, reference/, ground-truth.json).

    uv run --frozen python scripts/cyber_attackgraph_study.py [--graphs 42] [--reps 3]
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "research" / "studies" / "cyber-attackgraph"
SIZES = [(4, 3), (5, 3), (5, 4), (6, 3)]  # cycled by seed → a spread of difficulty


def _schema(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required, "additionalProperties": False}


SCHEMAS = {
    "shortest_cost": _schema({"cost": {"type": "integer"}, "rationale": {"type": "string"}}, ["cost"]),
    "reachability": _schema({"reachable": {"type": "boolean"}, "rationale": {"type": "string"}}, ["reachable"]),
    "min_defense": _schema({"count": {"type": "integer"}, "rationale": {"type": "string"}}, ["count"]),
    "step_enabled": _schema({"enabled": {"type": "boolean"}, "rationale": {"type": "string"}}, ["enabled"]),
}


def _graph_md(ag) -> str:  # a structured, readable rendering of the formal model
    nodes = ag.by_name()
    lines = ["# Attack graph (formal AND/OR dependency model)", "",
             "An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its "
             "parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The "
             "target is the crown objective.", "",
             f"- Entry footholds (always reachable to start): {', '.join(ag.entry)}",
             f"- Target: {ag.goal}", "", "| step | type | parents |", "|---|---|---|"]
    for fn in sorted(nodes):
        n = nodes[fn]
        ps = ", ".join(n["parents"]) if n["parents"] else "— (entry)"
        lines.append(f"| {fn} | {n['type'].upper()} | {ps} |")
    return "\n".join(lines) + "\n"


def build(n_graphs: int, reps: int) -> None:
    from formal_lab_domain_mal.analysis import generate, ground_truth, reachable, step_enabled

    for sub in ("graphs", "inputs", "reference"):
        (STUDY / sub).mkdir(parents=True, exist_ok=True)
    tasks, gts = [], {}
    rng = random.Random(20260012)

    for i in range(n_graphs):
        seed = 1000 + i
        layers, width = SIZES[i % len(SIZES)]
        ag = generate(seed, layers=layers, width=width)
        gt = ground_truth(ag, verify_z3=True)
        gts[ag.graph_id] = gt
        (STUDY / "graphs" / f"{ag.graph_id}.json").write_text(
            json.dumps({"graph": ag.graph_dict(), "entry": ag.entry, "goal": ag.goal,
                        "hardenable": ag.hardenable}, indent=1) + "\n")
        base_md = _graph_md(ag)
        nodes = ag.by_name()

        def add(kind: str, extra_md: str, answer, question: str, note: str, *, ag=ag, gt=gt, base_md=base_md) -> None:
            tid = f"{ag.graph_id}-{kind}"
            (STUDY / "inputs" / f"{tid}.md").write_text(base_md + extra_md)
            # the answer is wrapped so its JSON needle cannot collide with a bare digit/boolean in the graph text
            ref = {"graph_id": ag.graph_id, "graph_digest": ag.digest(), "question_kind": kind,
                   "answer": {"value": answer}, "note": note}
            (STUDY / "reference" / f"{tid}.json").write_text(json.dumps(ref, indent=1) + "\n")
            tasks.append({"task_id": tid, "track": "formal_model_analysis", "representation_id": "steplist",
                          "purpose": f"{kind} over a {gt['nodes']}-node attack graph", "inputs": [f"inputs/{tid}.md"],
                          "question": question, "answer_format": "json", "answer_schema": SCHEMAS[kind],
                          "reference": f"reference/{tid}.json", "scorer_id": "attackgraph.analysis",
                          "scorer_version": "1", "bound": {"nodes": gt["nodes"]}})

        if gt["reachable_target"] and gt["shortest_cost"] is not None:
            add("shortest_cost", "\n## Question\nWhat is the minimum number of attack steps the attacker must take to "
                "reach the target? Count every step the attacker performs, **including the final step that "
                "compromises the target itself**.\n", gt["shortest_cost"],
                "Give the minimum number of attack steps to reach the target, including the final target step.",
                "Z3 OPTIMIZE_OBJECTIVE (attack_cost)")

        # reachability under a deployed defence set: half the time deploy the min-cut (target blocked), else a random
        # non-cut subset (target still reachable) — so the answer is genuinely either way and must be reasoned out
        cut = gt["min_cut"].get("cut") or []
        if cut and rng.random() < 0.5:
            deployed, exp = cut, False
        else:
            k = min(len(ag.hardenable), max(1, len(cut) or 2))
            deployed = sorted(rng.sample(ag.hardenable, k))
            exp = ag.goal in reachable(nodes, ag.entry, frozenset(deployed))
        add("reachability", f"\n## Deployed defences\nThe defender has blocked these steps (they can no longer be "
            f"used): {', '.join(deployed) or 'none'}.\n\n## Question\nWith those defences in place, is the target "
            "still reachable?\n", exp, "Answer whether the target is still reachable with those defences deployed.",
            "native reachability oracle, Z3-confirmed")

        if gt["min_cut"].get("size") is not None:
            add("min_defense", "\n## Question\nA defender may block steps to stop the attacker. What is the smallest "
                "number of steps they must block so the target becomes unreachable? (Footholds and the target itself "
                "cannot be blocked.)\n", gt["min_cut"]["size"],
                "Give the smallest number of steps to block so the target is unreachable.",
                "AND/OR min-cut search, Z3-confirmed")

        # step-enabled: pick an AND step if any (harder), build a partial compromised set missing 0 or 1 parent
        cands = [fn for fn, n in nodes.items() if n["parents"] and n["type"] == "and"] or \
                [fn for fn, n in nodes.items() if n["parents"]]
        if cands:
            target = rng.choice(cands)
            ps = nodes[target]["parents"]
            comp = sorted(ps if rng.random() < 0.5 or len(ps) == 1 else rng.sample(ps, len(ps) - 1))
            ans = step_enabled(ag, comp, target)
            add("step_enabled", f"\n## Current state\nThe attacker has already compromised: {', '.join(comp) or 'nothing'}.\n\n"
                f"## Question\nIs the step `{target}` (type {nodes[target]['type'].upper()}) enabled to be taken "
                "next?\n", ans, f"Answer whether `{target}` is enabled next.", "AND/OR semantics")

    providers = [
        {"provider_config_id": "gpt-6-astra-relay", "provider": "openai", "api": "openai.chat.completions",
         "api_version": "v1", "route": "COMPATIBLE_RELAY", "base_url_setting": "FAL_RESEARCH_RELAY_BASE_URL",
         "api_key_setting": "FAL_RESEARCH_GPT_API_KEY", "model": "gpt-6-astra",
         "params": {"max_completion_tokens": 3000}, "comparability_note": "relay route; identity is relay-reported"},
        {"provider_config_id": "claude-opus-5-5-relay", "provider": "anthropic", "api": "anthropic.messages",
         "api_version": "2023-06-01", "route": "COMPATIBLE_RELAY", "base_url_setting": "FAL_RESEARCH_RELAY_BASE_URL",
         "api_key_setting": "FAL_RESEARCH_CLAUDE_API_KEY", "model": "claude-opus-5-5",
         "params": {"max_tokens": 3000}, "comparability_note": "relay route; identity is relay-reported"}]
    planned = len(tasks) * len(providers) * reps
    study = {
        "study_id": "cyber-attackgraph",
        "title": "Defensive attack-graph analysis (verifier-grounded)",
        "purpose": "hard, machine-checked security-analyst questions over formal AND/OR attack-graph models — shortest "
                   "attack path, reachability under deployed defences, minimum defence cut, step enablement. Ground "
                   "truth is the Z3 verifier / model semantics, so answers are objectively right or wrong and the "
                   "tasks discriminate rather than everyone scoring 100%.",
        "tasks": tasks, "providers": providers, "assistance_modes": ["STATIC_UNASSISTED"], "replicates": reps,
        "rubric_id": "fal-research-rubric", "rubric_version": "1", "primary_metric": "correct",
        "secondary_metrics": ["format_valid", "refused", "responded", "program_corresponds", "output_tokens"],
        "limits": {"max_calls": planned + 40, "max_http_attempts": 2 * planned + 80,
                   "max_output_tokens_per_call": 3000, "max_total_output_tokens": 3000 * (planned + 40),
                   "network_retries": 2},
        "comparisons": [{"vary": "provider", "a": "gpt-6-astra-relay", "b": "claude-opus-5-5-relay",
                         "note": "both via the same relay; an engineering reading, not a verified provider ranking"}],
        "missing_policy": "the denominator is the planned units; a unit with no model-produced response is MISSING; a "
                          "refusal is not retried; the frozen call cap covers the planned requests plus bounded "
                          "resamples and the denominator never changes"}
    (STUDY / "study.json").write_text(json.dumps(study, indent=1, ensure_ascii=False) + "\n")
    (STUDY / "ground-truth.json").write_text(json.dumps(gts, indent=1) + "\n")
    kinds: dict[str, int] = {}
    for t in tasks:
        kinds[t["task_id"].rsplit("-", 1)[1]] = kinds.get(t["task_id"].rsplit("-", 1)[1], 0) + 1
    print(f"cyber-attackgraph: {n_graphs} graphs, {len(tasks)} tasks {kinds}, {len(providers)} models × {reps} reps "
          f"= {planned} planned units")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--graphs", type=int, default=42)
    ap.add_argument("--reps", type=int, default=3)
    args = ap.parse_args()
    build(args.graphs, args.reps)
