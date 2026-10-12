"""Defensive attack-graph analysis (phase 8): generate formal attack-graph models and compute, with the Z3 verifier
and the model semantics, the ground-truth answers to hard analysis questions a security analyst would ask of a threat
model — shortest attack path length, reachability of a target under a set of deployed defences, the smallest set of
defences that cuts every path to the target, and whether a derived step is enabled in a given state.

This is formal threat modelling for defence. An attack graph is an abstract AND/OR dependency model (entry footholds,
intermediate steps, a target), the standard object of attack-graph / MAL analysis; the steps are abstract graph nodes
(`reach`, `pivot`, `escalate`, `access`), not operational exploitation instructions. Every answer here is produced by
the deterministic model semantics and cross-checked by the Z3 bounded verifier, so the LLM tasks built on top have an
objective, machine-checked ground truth rather than a human opinion.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any

from formal_lab_contracts import CheckQuery, ObjectiveSpec

STEP_VERBS = ("reach", "pivot", "escalate", "access", "obtain", "traverse")
BOUND = {"max_steps": 60, "timeout_ms": 30000}


@dataclass
class AttackGraph:
    """An abstract AND/OR attack graph: entry footholds with no parents, intermediate steps that fire on any parent
    (OR) or all parents (AND), and one target. `hardenable` steps are the ones a defender can block (deploy a
    defence / patch)."""

    graph_id: str
    nodes: list[dict[str, Any]]
    entry: list[str]
    goal: str
    hardenable: list[str]
    seed: int
    meta: dict[str, Any] = field(default_factory=dict)

    def by_name(self) -> dict[str, dict[str, Any]]:
        return {n["full_name"]: n for n in self.nodes}

    def graph_dict(self) -> dict[str, Any]:
        return {"nodes": self.nodes, "assets": [], "associations": [], "counts": self.meta,
                "defenses_enabled": True, "model_name": self.graph_id}

    def digest(self) -> str:
        key = [(n["full_name"], n["type"], tuple(sorted(n["parents"]))) for n in self.nodes]
        return hashlib.sha256(repr((sorted(key), sorted(self.entry), self.goal)).encode()).hexdigest()


def reachable(nodes: dict[str, dict[str, Any]], entry: list[str], blocked: frozenset[str] = frozenset()) -> set[str]:
    """The native oracle: which steps an attacker can reach from the footholds, given a set of blocked (hardened)
    steps. A blocked step never fires; an OR step fires on any reached parent, an AND step when all parents are
    reached; an entry step with no reached parent seeds."""
    reached: set[str] = set()
    frontier = True
    while frontier:
        frontier = False
        for fn, n in nodes.items():
            if fn in reached or fn in blocked:
                continue
            ps = n["parents"]
            fires = (fn in entry) if not ps else (all(p in reached for p in ps) if n["type"] == "and"
                                                  else any(p in reached for p in ps))
            if not ps and fn in entry:
                fires = True
            if fires:
                reached.add(fn)
                frontier = True
    return reached


def generate(seed: int, *, layers: int = 4, width: int = 3, p_and: float = 0.35) -> AttackGraph:
    """A deterministic, layered AND/OR attack graph. Entry footholds feed intermediate layers (each step draws 1–3
    parents from the two preceding layers, AND with probability `p_and`), ending at a single target. Difficulty
    scales with `layers`×`width`."""
    rng = random.Random(seed)
    layer_steps: list[list[str]] = []
    nodes: dict[str, dict[str, Any]] = {}

    def add(fn: str, typ: str, parents: list[str]) -> None:
        nodes[fn] = {"full_name": fn, "asset": fn.split(":")[0], "step": fn.split(":")[1], "type": typ,
                     "existence_status": False, "parents": parents, "children": [], "ttc": None, "auto": False,
                     "blocked": False}

    n_entry = max(2, width - 1)
    entries = [f"edge{i}:reach" for i in range(n_entry)]
    for e in entries:
        add(e, "or", [])
    layer_steps.append(entries)

    for li in range(1, layers):
        this: list[str] = []
        pool = [s for prev in layer_steps[max(0, li - 2):] for s in prev]
        for wi in range(width):
            fn = f"h{li}_{wi}:{rng.choice(STEP_VERBS)}"
            k = min(len(pool), rng.randint(1, 3))
            parents = rng.sample(pool, k)
            typ = "and" if (len(parents) > 1 and rng.random() < p_and) else "or"
            add(fn, typ, parents)
            this.append(fn)
        layer_steps.append(this)

    goal = "crown:obtain"
    gk = min(len(layer_steps[-1]), rng.randint(2, 3))
    add(goal, "or", rng.sample(layer_steps[-1], gk))

    for fn, n in nodes.items():  # wire children
        for p in n["parents"]:
            nodes[p]["children"].append(fn)

    entry = entries
    R = reachable(nodes, entry)
    if goal not in R:  # guarantee a reachable target: attach the goal to a reached frontier step as OR
        frontier = sorted(R & {s for layer in layer_steps[1:] for s in layer}) or entry
        nodes[goal]["parents"] = [frontier[-1]]
        nodes[goal]["type"] = "or"
        nodes[frontier[-1]]["children"].append(goal)
        R = reachable(nodes, entry)
    hardenable = sorted((R - set(entry)) - {goal})
    meta = {"layers": layers, "width": width, "nodes": len(nodes), "reachable": len(R),
            "and_steps": sum(1 for n in nodes.values() if n["type"] == "and")}
    return AttackGraph(graph_id=f"ag-{seed:04d}", nodes=list(nodes.values()), entry=entry, goal=goal,
                       hardenable=hardenable, seed=seed, meta=meta)


# a realistic enterprise attack surface: named tiers with MITRE-ATT&CK-style tactic labels, used purely as abstract
# graph nodes for defensive analysis (no operational detail). AND-joins model real conjunctive controls (MFA needs a
# password AND a token; privileged access needs credentials AND a network path).
_TIERS = [
    ("perimeter", ["internet", "phishing", "supplychain", "vpnGateway", "wifiGuest", "exposedApi"],
     ("initialAccess",), "or"),
    ("foothold", ["dmzWeb", "mailClient", "workstation", "ciRunner", "containerHost", "iotDevice"],
     ("execution", "exploitPublicApp"), "or"),
    ("credential", ["browserStore", "memoryDump", "kerberoast", "configSecret", "sshKey", "tokenCache"],
     ("credentialAccess",), "or"),
    ("auth", ["ssoLogin", "rdpLogin", "apiToken", "vpnSession", "dbLogin"], ("authenticate",), "and"),
    ("lateral", ["appServer", "fileServer", "jumpHost", "backupHost", "monitoringHost", "printServer"],
     ("lateralMovement",), "or"),
    ("escalation", ["localAdmin", "domainAdmin", "serviceAccount", "hypervisor", "secretsManager"],
     ("privilegeEscalation",), "and"),
    ("collection", ["dbReplica", "shareMount", "vaultRead", "mailArchive", "codeRepo"], ("collection",), "or"),
]


def generate_enterprise(seed: int, *, scale: int = 2) -> AttackGraph:
    """A larger, realistic multi-tier enterprise attack graph (perimeter → foothold → credential → auth → lateral →
    privilege escalation → collection → the crown-jewel data store), with conjunctive controls as AND-joins and a
    broad attack surface (several hosts per tier, multiple paths). `scale` multiplies the hosts per tier. The step
    labels are ATT&CK-style tactic names used only as abstract graph nodes for defensive analysis."""
    rng = random.Random(seed * 131 + 7)
    nodes: dict[str, dict[str, Any]] = {}

    def add(fn: str, typ: str, parents: list[str]) -> None:
        nodes[fn] = {"full_name": fn, "asset": fn.split(":")[0], "step": fn.split(":")[1], "type": typ,
                     "existence_status": False, "parents": parents, "children": [], "ttc": None, "auto": False,
                     "blocked": False}

    tier_steps: list[list[str]] = []
    for ti, (_tier, hosts, verbs, join) in enumerate(_TIERS):
        picks = hosts if ti == 0 else rng.sample(hosts, min(len(hosts), 2 + scale))
        this: list[str] = []
        pool = [s for prev in tier_steps[max(0, ti - 2):] for s in prev]
        for h in picks:
            fn = f"{h}:{rng.choice(verbs)}"
            if ti == 0:
                add(fn, "or", [])
            else:
                k = min(len(pool), (2 if join == "and" else rng.randint(1, 3)))
                parents = rng.sample(pool, max(1, k))
                typ = "and" if (join == "and" and len(parents) >= 2) else "or"
                add(fn, typ, parents)
            this.append(fn)
        tier_steps.append(this)

    goal = "crownData:exfiltrate"
    gk = min(len(tier_steps[-1]), 1 + scale)
    add(goal, "or", rng.sample(tier_steps[-1], max(1, gk)))
    for fn, n in nodes.items():
        for p in n["parents"]:
            nodes[p]["children"].append(fn)

    entry = tier_steps[0]
    R = reachable(nodes, entry)
    if goal not in R:
        frontier = sorted(R - set(entry)) or entry
        nodes[goal]["parents"] = [frontier[-1]]
        nodes[frontier[-1]]["children"].append(goal)
        R = reachable(nodes, entry)
    hardenable = sorted((R - set(entry)) - {goal})
    meta = {"scale": scale, "tiers": len(_TIERS), "nodes": len(nodes), "reachable": len(R),
            "and_steps": sum(1 for n in nodes.values() if n["type"] == "and"), "realistic": True}
    return AttackGraph(graph_id=f"ent-{seed:04d}", nodes=list(nodes.values()), entry=entry, goal=goal,
                       hardenable=hardenable, seed=seed, meta=meta)


def package(ag: AttackGraph, *, initial_hardened: list[str] | None = None) -> Any:
    from .frontend import package_from_graph

    blocked = frozenset(initial_hardened or [])
    R = reachable(ag.by_name(), ag.entry, blocked)
    return package_from_graph(ag.graph_dict(), ag.entry, ag.goal, package_id=ag.graph_id, version=1,
                              reachable=sorted(R), language={"name": "coreLang", "version": "1.0.0"},
                              include_defense=True, initial_hardened=sorted(blocked))


def z3_reachable(ag: AttackGraph, initial_hardened: list[str] | None = None) -> bool:
    from formal_lab_solver_z3.verifier import Z3Verifier

    pkg = package(ag, initial_hardened=initial_hardened)
    v = Z3Verifier().check(pkg, CheckQuery(kind="GOAL_REACHABILITY", property_id="target_reached", bound=BOUND))
    return str(getattr(v.verdict, "value", v.verdict)) == "WITNESS"


def z3_shortest_cost(ag: AttackGraph, initial_hardened: list[str] | None = None) -> int | None:
    from formal_lab_solver_z3.verifier import Z3Verifier

    pkg = package(ag, initial_hardened=initial_hardened)
    spec = ObjectiveSpec.model_validate({"objective_id": "cheap", "goal_property": "target_reached", "horizon": 60,
                                         "levels": [{"id": "cost", "model_objective": "attack_cost"}]})
    r = Z3Verifier().check(pkg, CheckQuery(kind="OPTIMIZE_OBJECTIVE", objective=spec, bound=BOUND))
    if str(getattr(r.verdict, "value", r.verdict)) != "OPTIMAL" or r.optimization is None:
        return None
    return int(r.optimization.levels[0].value)


def min_defense_cut(ag: AttackGraph, *, max_k: int = 4) -> dict[str, Any]:
    """The smallest set of hardenable steps whose removal makes the target unreachable (an AND/OR min-cut). Searched
    by increasing size and checked with the native reachability oracle; the chosen cut is independently confirmed by
    Z3 (target unreachable with it, reachable without one of its members)."""
    nodes = ag.by_name()
    if ag.goal not in reachable(nodes, ag.entry):
        return {"size": 0, "cut": [], "note": "target already unreachable"}
    for k in range(1, max_k + 1):
        for combo in combinations(ag.hardenable, k):
            if ag.goal not in reachable(nodes, ag.entry, frozenset(combo)):
                return {"size": k, "cut": list(combo), "searched_up_to": k}
    return {"size": None, "cut": [], "note": f"no cut of size ≤ {max_k}", "searched_up_to": max_k}


def step_enabled(ag: AttackGraph, compromised: list[str], step: str) -> bool:
    """Pure AND/OR semantics: given a set of already-compromised steps, is `step` enabled next (all parents for AND,
    any parent for OR; an entry step is always enabled)?"""
    n = ag.by_name()[step]
    cset = set(compromised)
    ps = n["parents"]
    if not ps:
        return step in ag.entry
    return all(p in cset for p in ps) if n["type"] == "and" else any(p in cset for p in ps)


def ground_truth(ag: AttackGraph, *, verify_z3: bool = True) -> dict[str, Any]:
    """Every analysis answer for one graph, with Z3 cross-checks. Raises if a native answer and Z3 disagree."""
    nodes = ag.by_name()
    base_reach = ag.goal in reachable(nodes, ag.entry)
    cost = z3_shortest_cost(ag) if base_reach else None
    cut = min_defense_cut(ag)
    # a reachability-under-defence probe: harden roughly half the min-cut (so the target usually stays reachable)
    probe = sorted(ag.hardenable)[: max(1, len(ag.hardenable) // 3)]
    probe_reach_native = ag.goal in reachable(nodes, ag.entry, frozenset(probe))
    gt = {"graph_id": ag.graph_id, "digest": ag.digest(), "nodes": len(nodes), "reachable_target": base_reach,
          "shortest_cost": cost, "min_cut": cut, "defense_probe": {"hardened": probe, "reachable": probe_reach_native}}
    if verify_z3:
        assert z3_reachable(ag) == base_reach, f"{ag.graph_id}: Z3/native reachability disagree"
        assert z3_reachable(ag, probe) == probe_reach_native, f"{ag.graph_id}: Z3/native disagree under defence"
        if cut.get("cut"):
            assert not z3_reachable(ag, cut["cut"]), f"{ag.graph_id}: Z3 says target reachable despite the cut"
            if cut["size"] and cut["size"] > 0:
                partial = cut["cut"][:-1]
                assert z3_reachable(ag, partial), f"{ag.graph_id}: cut not minimal (Z3)"
        gt["z3_confirmed"] = True
    return gt
