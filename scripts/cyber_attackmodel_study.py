#!/usr/bin/env python3
"""Build the attack-MODEL LLM study (cyber-attackmodel): hard questions over the *real* enterprise attack model
(meaningful security state + attack techniques with preconditions, defences as constants), not a flat attack graph.
Ground truth is the Z3 verifier / the model semantics: shortest attack plan to data exfiltration, whether the
attacker can still exfiltrate under a deployed defence set, the minimum number of defences that stop exfiltration,
and whether a technique is applicable in a given state. Reuses the attackgraph.analysis@1 scorer.

    uv run --frozen python scripts/cyber_attackmodel_study.py [--models 24] [--reps 3]
"""

from __future__ import annotations

import argparse
import json
import random
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "research" / "studies" / "cyber-attackmodel"
BOUND = {"max_steps": 50, "timeout_ms": 20000}


def _schema(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required, "additionalProperties": False}


SCHEMAS = {
    "shortest_cost": _schema({"cost": {"type": "integer"}, "rationale": {"type": "string"}}, ["cost"]),
    "reachability": _schema({"reachable": {"type": "boolean"}, "rationale": {"type": "string"}}, ["reachable"]),
    "min_defense": _schema({"count": {"type": "integer"}, "rationale": {"type": "string"}}, ["count"]),
    "technique_enabled": _schema({"enabled": {"type": "boolean"}, "rationale": {"type": "string"}}, ["enabled"]),
}


def pp(e: dict) -> str:
    op = e["op"]
    if op == "const":
        return "true" if e["value"] else "false"
    if op == "var":
        return e["name"]
    args = e.get("args", [])
    if op == "not":
        return f"NOT {pp(args[0])}"
    if op in ("and", "or"):
        return "(" + f" {op.upper()} ".join(pp(a) for a in args) + ")"
    return f"{op}({', '.join(pp(a) for a in args)})"


def ev(e: dict, st: dict[str, bool]) -> bool:
    op = e["op"]
    if op == "const":
        return bool(e["value"])
    if op == "var":
        return bool(st.get(e["name"], False))
    a = e.get("args", [])
    if op == "not":
        return not ev(a[0], st)
    if op == "and":
        return all(ev(x, st) for x in a)
    if op == "or":
        return any(ev(x, st) for x in a)
    raise ValueError(op)


def controls(am) -> list[str]:
    return ["segmented"] + [f"patched:{h}" for h in am.hosts] + [f"mfa:{c}" for c in am.creds]


def model_md(am, deployed: list[str]) -> str:
    ir = am.ir_dict
    state_vars = ", ".join(s["name"] for s in ir["state"])
    lines = ["# Enterprise attack model", "",
             "The attacker starts at the perimeter (`reach_dmz` is true) and wins when `exfiltrated` becomes true. "
             "Each technique can be used only when its **requires** condition holds; using it makes its **achieves** "
             "variables true. A deployed defence makes its constant true and so blocks the techniques that require it "
             "to be false.", "",
             f"**State variables** (all start false except reach_dmz): {state_vars}", "",
             f"**Deployed defences**: {', '.join(deployed) or 'none'}", "", "**Techniques**:"]
    for a in ir["actions"]:
        pre = pp(a["precondition"]) if a.get("precondition") else "(always available)"
        eff = ", ".join(t["target"]["var"] for t in a["effects"])
        lines.append(f"- `{a['name']}` — requires {pre}; achieves {eff}")
    return "\n".join(lines) + "\n"


def build(n_models: int, reps: int) -> None:
    from formal_lab_contracts import CheckQuery, ObjectiveSpec
    from formal_lab_domain_mal.attack_model import enterprise_attack_model
    from formal_lab_solver_z3.verifier import Z3Verifier

    z = Z3Verifier()

    def reach(scale: int, defs: frozenset[str]) -> bool:
        m = enterprise_attack_model(scale=scale, defenses=defs)
        r = z.check(m.package(), CheckQuery(kind="GOAL_REACHABILITY", property_id="data_exfiltrated", bound=BOUND))
        return str(getattr(r.verdict, "value", r.verdict)) == "WITNESS"

    def cost(scale: int, defs: frozenset[str]) -> int | None:
        m = enterprise_attack_model(scale=scale, defenses=defs)
        spec = ObjectiveSpec.model_validate({"objective_id": "c", "goal_property": "data_exfiltrated", "horizon": 50,
                                             "levels": [{"id": "cost", "model_objective": "attack_cost"}]})
        o = z.check(m.package(), CheckQuery(kind="OPTIMIZE_OBJECTIVE", objective=spec, bound=BOUND))
        return int(o.optimization.levels[0].value) if (o.optimization and
                   str(getattr(o.verdict, "value", o.verdict)) == "OPTIMAL") else None

    for sub in ("inputs", "reference", "models"):
        (STUDY / sub).mkdir(parents=True, exist_ok=True)
    tasks, rng = [], random.Random(8025)

    for i in range(n_models):
        scale = 1 + (i % 3)
        am = enterprise_attack_model(scale=scale, name=f"attackmodel-{i:03d}")
        ctrl = controls(am)
        (STUDY / "models" / f"am-{i:03d}.json").write_text(json.dumps(am.ir_dict, indent=1) + "\n")

        def add(kind: str, deployed: list[str], answer, question: str, note: str, state_extra: str = "", *,
                i=i, am=am) -> None:
            tid = f"am-{i:03d}-{kind}"
            (STUDY / "inputs" / f"{tid}.md").write_text(model_md(am, deployed) + state_extra +
                                                        f"\n## Question\n{question}\n")
            (STUDY / "reference" / f"{tid}.json").write_text(json.dumps(
                {"model": am.name, "question_kind": kind, "answer": {"value": answer}, "note": note}, indent=1) + "\n")
            tasks.append({"task_id": tid, "track": "formal_model_analysis", "representation_id": "attackmodel",
                          "purpose": f"{kind} on a real attack model ({len(am.ir_dict['state'])} state vars)",
                          "inputs": [f"inputs/{tid}.md"], "question": question.split("\n")[0], "answer_format": "json",
                          "answer_schema": SCHEMAS[kind], "reference": f"reference/{tid}.json",
                          "scorer_id": "attackgraph.analysis", "scorer_version": "1",
                          "bound": {"state": len(am.ir_dict["state"])}})

        # DEFENSE — deploy a defence set, sometimes the minimum cut (blocks), sometimes a partial set (still open)
        min_found = None
        for k in range(1, 4):
            for combo in combinations(ctrl, k):
                if not reach(scale, frozenset(combo)):
                    min_found = list(combo)
                    break
            if min_found:
                break
        if min_found and rng.random() < 0.5:
            deployed, exp = min_found, False
        else:
            deployed = sorted(rng.sample(ctrl, rng.randint(1, 3)))
            exp = reach(scale, frozenset(deployed))
        add("reachability", deployed, exp,
            "With the deployed defences above in place, can the attacker still reach data exfiltration?",
            "Z3 GOAL_REACHABILITY on the model with those defence constants")

        # OFFENSE — shortest attack plan, usually on the clean model
        c0 = cost(scale, frozenset())
        if c0 is not None:
            add("shortest_cost", [], c0,
                "With no defences deployed, what is the minimum number of techniques the attacker must use to reach "
                "data exfiltration? Count every technique, including the final exfiltration step.",
                "Z3 OPTIMIZE_OBJECTIVE (attack_cost)")

        # DEFENSE — minimum number of controls that stop exfiltration
        if min_found is not None:
            add("min_defense", [], len(min_found),
                f"From the available controls ({', '.join(ctrl)}), what is the smallest number that, deployed "
                "together, make data exfiltration impossible?", "minimum-defence subset search, Z3-confirmed")

        # NEUTRAL — is a technique applicable in a given partial state
        act = rng.choice([a for a in am.ir_dict["actions"] if a.get("precondition")])
        consts = {f"patched_{h}": False for h in am.hosts}
        consts |= {f"mfa_{cr}": False for cr in am.creds} | {"segmented": False}
        true_vars = sorted(rng.sample([s["name"] for s in am.ir_dict["state"]],
                                      rng.randint(1, min(5, len(am.ir_dict["state"])))))
        st = dict.fromkeys(true_vars, True) | consts
        enabled = ev(act["precondition"], st)
        add("technique_enabled", [], enabled,
            f"Is the technique `{act['name']}` applicable right now?",
            "precondition evaluated on the given state",
            state_extra=f"\n## Current state\nThese variables are currently true: {', '.join(true_vars)}. "
                        "All other state variables are false and no defences are deployed.\n")

    providers = [
        {"provider_config_id": "gpt-6-astra-relay", "provider": "openai", "api": "openai.chat.completions",
         "api_version": "v1", "route": "COMPATIBLE_RELAY", "base_url_setting": "FAL_RESEARCH_RELAY_BASE_URL",
         "api_key_setting": "FAL_RESEARCH_GPT_API_KEY", "model": "gpt-6-astra",
         "params": {"max_completion_tokens": 3500}, "comparability_note": "relay route; identity is relay-reported"},
        {"provider_config_id": "claude-opus-5-5-relay", "provider": "anthropic", "api": "anthropic.messages",
         "api_version": "2023-06-01", "route": "COMPATIBLE_RELAY", "base_url_setting": "FAL_RESEARCH_RELAY_BASE_URL",
         "api_key_setting": "FAL_RESEARCH_CLAUDE_API_KEY", "model": "claude-opus-5-5",
         "params": {"max_tokens": 3500}, "comparability_note": "relay route; identity is relay-reported"}]
    planned = len(tasks) * len(providers) * reps
    study = {
        "study_id": "cyber-attackmodel",
        "title": "Enterprise attack-model analysis (real model, verifier-grounded)",
        "purpose": "hard security-analyst questions over a real attack model — meaningful security state (footholds, "
                   "admin, stolen credentials, network reach, exfiltration) and attack techniques with preconditions, "
                   "defences as constants — not a flat attack graph. Ground truth is the Z3 verifier / model "
                   "semantics: shortest attack plan, reachability under a defence set, minimum defences to stop "
                   "exfiltration, technique applicability.",
        "tasks": tasks, "providers": providers, "assistance_modes": ["STATIC_UNASSISTED"], "replicates": reps,
        "rubric_id": "fal-research-rubric", "rubric_version": "1", "primary_metric": "correct",
        "secondary_metrics": ["format_valid", "refused", "responded", "program_corresponds", "output_tokens"],
        "limits": {"max_calls": planned + 40, "max_http_attempts": 2 * planned + 80,
                   "max_output_tokens_per_call": 3500, "max_total_output_tokens": 3500 * (planned + 40),
                   "network_retries": 2},
        "comparisons": [{"vary": "provider", "a": "gpt-6-astra-relay", "b": "claude-opus-5-5-relay",
                         "note": "both via the same relay; an engineering reading, not a verified ranking"}],
        "missing_policy": "the denominator is the planned units; a unit with no model-produced response is MISSING; a "
                          "refusal is not retried; the frozen call cap covers the planned requests plus resamples."}
    (STUDY / "study.json").write_text(json.dumps(study, indent=1, ensure_ascii=False) + "\n")
    kinds: dict[str, int] = {}
    for t in tasks:
        k = t["task_id"].rsplit("-", 1)[1]
        kinds[k] = kinds.get(k, 0) + 1
    print(f"cyber-attackmodel: {n_models} models, {len(tasks)} tasks {kinds}, 2 models × {reps} reps = {planned} units")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", type=int, default=24)
    ap.add_argument("--reps", type=int, default=3)
    args = ap.parse_args()
    build(args.models, args.reps)
