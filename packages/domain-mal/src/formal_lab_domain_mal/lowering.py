"""Lower a MAL attack graph to the neutral deterministic finite IR (phase 3B, D1).

The first closed loop uses the subset of MAL that maps onto the platform's `deterministic_finite_v1` IR: attack-step
compromise. The lowering models the goal's `or`/`and` ancestors as boolean `compromised[step]` state and reproduces
the native attack graph's reachability of the goal, using the native simulator's reachable set as the fold oracle for
the conditions the IR does not model directly (existence steps and disabled defenses). The platform then runs the IR
with its own reference interpreter and the Z3 bounded verifier — three independent engines that must agree on whether
the target is reachable. What the abstraction leaves out is recorded in `scope`.

Modeled as IR:
- entity set `steps`: the goal and its native-reachable `or`/`and` ancestors;
- state `compromised[steps]` (bool), initial true for the entry points;
- constants `is_and[steps]`, `edge[parent, child]` (only among modeled steps), `seed[steps]` (a step the native run
  reached without any modeled parent — an entry point, or one first reached through folded conditions / pruned
  ancestors that are outside the goal cone);
- action `compromise(n)`: an OR step fires on `seed[n]` or any compromised modeled parent; an AND step fires when
  every modeled parent is compromised (its non-modeled prerequisites were satisfied natively, so they fold to true);
- property `target_reached` (the TargetSecurity goal) and objective `attack_cost` (one per step).

Only the goal's ancestors are modeled, since they alone decide the goal's reachability — keeping the IR small enough
for the bounded verifier.
"""

from __future__ import annotations

import re
from typing import Any

from formal_lab_contracts import ModelIR

STEP_TYPES = ("or", "and")


def _mid(full_name: str) -> str:
    """A MAL full name (`asset:step`) as an IR-safe entity member id."""
    return re.sub(r"[^0-9A-Za-z_]", "__", full_name)


def ancestors(nodes: dict[str, dict[str, Any]], goal: str) -> set[str]:
    """The goal and every step it (transitively) depends on, via parent edges."""
    seen: set[str] = set()
    stack = [goal]
    while stack:
        fn = stack.pop()
        if fn in seen or fn not in nodes:
            continue
        seen.add(fn)
        stack.extend(nodes[fn]["parents"])
    return seen


def lower(graph: dict[str, Any], entry_points: list[str], goal: str, reachable: list[str], *,
          name: str | None = None) -> tuple[ModelIR, dict[str, Any]]:
    """Return (IR, lowering report). `reachable` is the native simulator's compromised set from these entry points;
    it is the oracle for which ancestors are modeled and which steps seed without a modeled parent."""
    nodes = {n["full_name"]: n for n in graph["nodes"]}
    if goal not in nodes:
        raise ValueError(f"goal {goal!r} is not a step of this model")
    R = set(reachable)
    anc = ancestors(nodes, goal)
    # modeled = the goal plus its or/and ancestors the native run actually reached (they decide the goal)
    modeled = {fn for fn in anc if nodes[fn]["type"] in STEP_TYPES and fn in R}
    if nodes[goal]["type"] in STEP_TYPES:
        modeled.add(goal)  # always model the goal, even when it is unreachable (then it stays isolated)
    entry = [e for e in entry_points if e in nodes]

    members = sorted(modeled)
    ids = {fn: _mid(fn) for fn in members}
    member_ids = [ids[fn] for fn in members]
    edges = [(p, c) for c in members for p in nodes[c]["parents"] if p in modeled]
    parents_in_modeled = {c: [p for p in nodes[c]["parents"] if p in modeled] for c in members}
    is_and = {fn for fn in members if nodes[fn]["type"] == "and"}
    # a step seeds (fires with no modeled parent) when the native run reached it but none of its modeled parents did
    seed = {fn for fn in members if fn in R and not any(p in R for p in parents_in_modeled[fn])}

    def table(true_ids: set[str]) -> dict[str, Any]:
        return {"default": False, "cells": [{"index": [ids[fn]], "value": True} for fn in sorted(true_ids)]}

    edge_cells = [{"index": [ids[p], ids[c]], "value": True} for p, c in edges]
    v = lambda n, *ix: {"op": "var", "name": n, "index": list(ix)}  # noqa: E731
    ref = lambda n: {"op": "ref", "name": n}  # noqa: E731
    ap = lambda op, *a: {"op": op, "args": list(a)}  # noqa: E731
    q = lambda op, var, dom, body: {"op": op, "var": var, "domain": dom, "body": body}  # noqa: E731

    parent_compromised = q("exists", "p", "steps", ap("and", v("edge", ref("p"), ref("n")), v("compromised", ref("p"))))
    all_parents = q("forall", "p", "steps", ap("or", ap("not", v("edge", ref("p"), ref("n"))),
                                               v("compromised", ref("p"))))
    precond = ap("and", ap("not", v("compromised", ref("n"))),
                 ap("or",
                    ap("and", ap("not", v("is_and", ref("n"))), ap("or", v("seed", ref("n")), parent_compromised)),
                    ap("and", v("is_and", ref("n")), all_parents)))
    ir_dict = {
        "semantic_profile": "deterministic_finite_v1",
        "name": name or f"mal-{graph.get('model_name', 'model')}",
        "description": f"Deterministic lowering of a MAL attack graph: reachability of {goal}.",
        "entity_sets": [{"name": "steps", "members": member_ids, "label": "攻击步骤"}],
        "constants": [
            {"name": "is_and", "type": {"kind": "bool"}, "index": ["steps"], "value": table(is_and),
             "description": "AND step (needs all parents); else OR (needs any)"},
            {"name": "seed", "type": {"kind": "bool"}, "index": ["steps"], "value": table(seed),
             "description": "reachable with no modeled parent: entry points and steps first reached via folded "
                            "conditions or pruned out-of-cone ancestors"},
            {"name": "edge", "type": {"kind": "bool"}, "index": ["steps", "steps"],
             "value": {"default": False, "cells": edge_cells}, "description": "parent → child among modeled steps"},
        ],
        "state": [
            {"name": "compromised", "type": {"kind": "bool"}, "index": ["steps"],
             "initial": table(set(entry) & modeled), "label": "已攻陷", "observable": True},
        ],
        "actions": [
            {"name": "compromise", "label": "攻陷步骤", "cost": 1,
             "params": [{"name": "n", "type": {"kind": "entity", "set": "steps"}}],
             "precondition": precond,
             "effects": [{"kind": "assign", "target": {"var": "compromised", "index": [ref("n")]},
                          "value": {"op": "const", "value": True}}]},
        ],
        "properties": [
            {"id": "target_reached", "kind": "goal", "expr": v("compromised", {"op": "const", "value": ids[goal]}),
             "label": f"到达 {goal}", "description": "TargetSecurity: the attacker compromises the target step"},
        ],
        "objectives": [
            {"id": "attack_cost", "label": "攻击代价", "unit": "steps", "terms": [{"kind": "action_cost"}]},
        ],
    }
    report = {
        "goal": goal, "goal_id": ids[goal], "entry_points": entry,
        "modeled_steps": len(members), "edges": len(edges),
        "and_steps": len(is_and), "or_steps": len(members) - len(is_and), "seed_steps": sorted(seed),
        "ancestors_total": len(anc), "native_reachable_total": len(R),
        "excluded_unreached_ancestors": sorted(fn for fn in anc
                                               if nodes[fn]["type"] in STEP_TYPES and fn not in R),
        "folded_non_step_parents": sorted({p for c in members for p in nodes[c]["parents"]
                                           if nodes[p]["type"] not in STEP_TYPES}),
        "goal_native_reachable": goal in R,
        "scope": {
            "kind": "deterministic reachability of one target step over the or/and attack graph",
            "oracle": "native mal-simulator reachable set (ttc disabled, no Bernoulli draws)",
            "in_scope": ["or/and attack-step compromise", "entry points", "existence steps and disabled defenses "
                         "folded to their native truth", "per-step unit cost"],
            "out_of_scope": ["time-to-compromise (TTC) and any randomness", "partial observation of the graph",
                             "asset/association changes during the attack", "quantitative rewards"],
            "cross_check": "the IR reproduces the native goal reachability; the reference interpreter and the Z3 "
                           "bounded verifier confirm it independently",
        },
        "id_map": ids,
    }
    return ModelIR.model_validate(ir_dict), report
