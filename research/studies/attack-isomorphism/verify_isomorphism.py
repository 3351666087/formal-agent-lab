"""Prove each attack model and its real-world twin are the SAME state machine.

Two independent checks per twin, so the "100% identical logic" claim does not rest on a
single tool:

  1. Z3 (SMT) search — ask the solver to FIND a bijection sigma on states (actions paired
     by the declared action_map) such that the attack LTS's labelled transition relation
     maps exactly onto the twin's, initial->initial and bad->bad. We then also prove the
     bijection is UNIQUE (no second distinct sigma exists). Finding it with the solver —
     rather than merely checking the map we wrote down — is what makes this a proof of
     isomorphism and not an assertion.

  2. Exhaustive constructive check (pure Python, no solver) — apply the declared bijection
     and confirm the edge sets, initial states and bad states correspond both ways. An
     independent witness that agrees with Z3.

Also reported: a structural isomorphism search with the action labels ALSO left free
(pure digraph-with-edge-colours isomorphism), confirming the machines are identical even
before you trust the action pairing; and reachability of `bad`, confirming the attack
state and the failure state sit at the same place in both diagrams.

Run:  uv run --frozen python research/studies/attack-isomorphism/verify_isomorphism.py
"""

from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

from z3 import And, Distinct, Not, Or, Solver, sat, unsat, Int, Function, IntSort, BoolSort, ForAll

sys.path.insert(0, str(Path(__file__).resolve().parent))
from models import LTS, TWINS, Twin  # noqa: E402


def reachable_from(lts: LTS, start: str) -> set[str]:
    seen, stack = {start}, [start]
    while stack:
        s = stack.pop()
        for a, b, d in [(x, y, z) for (x, y, z) in lts.transitions]:
            if a == s and d not in seen:
                seen.add(d)
                stack.append(d)
    return seen


def constructive_check(t: Twin) -> dict:
    """Independent, solver-free: apply the declared bijection and compare edge sets."""
    sm, am = t.state_map, t.action_map
    att, real = t.attack, t.real
    errs: list[str] = []

    if sorted(sm.keys()) != sorted(att.states):
        errs.append("state_map domain != attack states")
    if sorted(sm.values()) != sorted(real.states):
        errs.append("state_map image != real states (not a bijection)")
    if len(set(sm.values())) != len(sm):
        errs.append("state_map not injective")
    if sorted(am.keys()) != sorted(att.actions):
        errs.append("action_map domain != attack actions")
    if sorted(am.values()) != sorted(real.actions):
        errs.append("action_map image != real actions (not a bijection)")
    if len(set(am.values())) != len(am):
        errs.append("action_map not injective")

    mapped = {(sm[s], am[a], sm[d]) for (s, a, d) in att.transitions}
    real_edges = set(real.transitions)
    if mapped != real_edges:
        errs.append(f"edge sets differ: only-in-image={mapped - real_edges}, "
                    f"only-in-real={real_edges - mapped}")
    if sm.get(att.initial) != real.initial:
        errs.append("initial state not preserved")
    if sorted(sm[b] for b in att.bad) != sorted(real.bad):
        errs.append("bad state(s) not preserved")

    # reachability parity: the bad state sits identically in both diagrams
    att_bad_reach = all(b in reachable_from(att, att.initial) for b in att.bad)
    real_bad_reach = all(b in reachable_from(real, real.initial) for b in real.bad)

    return {
        "ok": not errs,
        "errors": errs,
        "edges_compared": len(real_edges),
        "attack_bad_reachable": att_bad_reach,
        "real_bad_reachable": real_bad_reach,
    }


def z3_isomorphism(att: LTS, real: LTS, action_map: dict, *, free_actions: bool) -> dict:
    """Search with Z3 for a state bijection realising the isomorphism; prove uniqueness."""
    aS, rS = list(att.states), list(real.states)
    aA, rA = list(att.actions), list(real.actions)
    if len(aS) != len(rS) or len(aA) != len(rA) or len(att.transitions) != len(real.transitions):
        return {"exists": False, "unique": None, "reason": "size mismatch"}

    rS_idx = {s: i for i, s in enumerate(rS)}
    rA_idx = {a: i for i, a in enumerate(rA)}

    s = Solver()
    # sigma[i] = index in rS that attack-state aS[i] maps to; a permutation.
    sigma = [Int(f"sig_{i}") for i in range(len(aS))]
    for v in sigma:
        s.add(v >= 0, v < len(rS))
    s.add(Distinct(*sigma))

    # alpha: action correspondence. Fixed by declared map, or free (a permutation) if asked.
    if free_actions:
        alpha = [Int(f"alp_{i}") for i in range(len(aA))]
        for v in alpha:
            s.add(v >= 0, v < len(rA))
        s.add(Distinct(*alpha))
    else:
        alpha = [rA_idx[action_map[a]] for a in aA]  # constants

    aS_idx = {st: i for i, st in enumerate(aS)}
    aA_idx = {ac: i for i, ac in enumerate(aA)}
    real_edge_set = {(rS_idx[x], rA_idx[y], rS_idx[z]) for (x, y, z) in real.transitions}

    # forward inclusion: every mapped attack edge is a real edge.
    def is_real_edge(si, ai, di):
        return Or(*[And(si == x, ai == y, di == z) for (x, y, z) in real_edge_set])

    for (x, y, z) in att.transitions:
        si, ai, di = sigma[aS_idx[x]], alpha[aA_idx[y]], sigma[aS_idx[z]]
        s.add(is_real_edge(si, ai, di))
    # with equal edge cardinality + sigma/alpha injective, forward inclusion ⇒ bijection on edges.

    s.add(sigma[aS_idx[att.initial]] == rS_idx[real.initial])
    for b in att.bad:
        s.add(Or(*[sigma[aS_idx[b]] == rS_idx[rb] for rb in real.bad]))

    if s.check() != sat:
        return {"exists": False, "unique": None, "reason": "no bijection satisfies constraints"}
    m = s.model()
    found = {aS[i]: rS[m[sigma[i]].as_long()] for i in range(len(aS))}

    # uniqueness: forbid this solution, re-check.
    s.add(Or(*[sigma[i] != m[sigma[i]] for i in range(len(aS))]))
    second = s.check()
    unique = second == unsat

    return {"exists": True, "unique": unique, "witness_state_map": found,
            "free_actions": free_actions}


def main() -> int:
    report = {"schema": "attack-isomorphism/v1", "twins": []}
    all_ok = True
    for t in TWINS:
        cons = constructive_check(t)
        z3_paired = z3_isomorphism(t.attack, t.real, t.action_map, free_actions=False)
        z3_struct = z3_isomorphism(t.attack, t.real, t.action_map, free_actions=True)

        witness_matches = (z3_paired.get("witness_state_map") == t.state_map)
        ok = (cons["ok"] and z3_paired.get("exists") and z3_paired.get("unique")
              and z3_struct.get("exists") and witness_matches
              and cons["attack_bad_reachable"] and cons["real_bad_reachable"])
        all_ok = all_ok and ok

        report["twins"].append({
            "key": t.key,
            "attack_model": t.attack.name, "attack_domain": t.attack.domain,
            "attack_source": t.attack.source,
            "real_model": t.real.name, "real_domain": t.real.domain,
            "states": len(t.attack.states), "transitions": len(t.attack.transitions),
            "constructive_check": cons,
            "z3_paired_actions": z3_paired,
            "z3_free_actions_structural": z3_struct,
            "z3_witness_equals_declared_map": witness_matches,
            "verdict": "ISOMORPHIC" if ok else "FAILED",
        })

        print(f"\n=== {t.key} :: {t.attack.name}  ⇄  {t.real.name} ===")
        print(f"  states={len(t.attack.states)} transitions={len(t.attack.transitions)}")
        print(f"  constructive edge-set identity : {'PASS' if cons['ok'] else 'FAIL ' + str(cons['errors'])}")
        print(f"  Z3 isomorphism (actions paired) : exists={z3_paired.get('exists')} unique={z3_paired.get('unique')}")
        print(f"  Z3 structural (actions free)    : exists={z3_struct.get('exists')}")
        print(f"  Z3 witness == declared bijection: {witness_matches}")
        print(f"  bad-state reachable both sides  : attack={cons['attack_bad_reachable']} real={cons['real_bad_reachable']}")
        print(f"  VERDICT: {'ISOMORPHIC (100% identical logic)' if ok else 'FAILED'}")

    out = Path(__file__).resolve().parent / "isomorphism-report.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"\nWrote {out}")
    print(f"\nALL TWINS ISOMORPHIC: {all_ok}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
