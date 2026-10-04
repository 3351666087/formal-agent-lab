"""Red and blue strategies for the MAL domain (phase 3B, D3).

Red (attacker), turn-taking planners that emit an `ActionProposal`. "Attack steps" here are abstract boolean nodes of
a MAL / coreLang attack graph lowered to the deterministic IR and run in the `ir-world` simulator — reachability over
a modelled graph, not any real system:
  * `MalRedRule`   — a deterministic rule: compromise the applicable step closest to the goal (greedy shortest path);
  * `MalRedHybrid` — model-assisted, reusing A3's reusable decision path (`formal_lab_strategies.decision`): the rule
                     computes the applicable candidate steps (verification) and the model chooses among them; the
                     choice is thus always rule-verified. Provenance is taken from the answer — LLM (a real provider),
                     LLM_PROTOCOL_TEST (the loopback test service) or LLM_STUB (the deterministic stand-in, which
                     defers to the rule's order) — and when the model returns nothing usable it falls back to the
                     rule, labelled RULE, keeping the failed call ids. No real endpoint configured ⇒ a labelled stub,
                     never an LLM label without a real answer;
  * the symbolic red baseline reuses the platform's `formal-lab.planner.z3-bounded` (cost-optimal / bounded search).

Blue (defender) is a configuration strategy chosen before the episode, not a turn: `min_cost_cut` picks a fewest-steps
set whose hardening disconnects the goal from the attacker's entry points (a minimum vertex cut, by max-flow), within a
business-cost budget; `harden_package` returns the package with those steps pre-hardened. This models blue choosing a
defence configuration under a business cost, and keeps the referee (env state + probes) the judge of success.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from formal_lab_contracts import ActionProposal, PlanningContext, PluginDescriptor, ProposalSource
from formal_lab_contracts import capabilities as caps
from formal_lab_contracts.errors import NonRetryableFailure

from .frontend import attack_graph_of

# --------------------------------------------------------------------------- blue: minimum-cost cut


def _distances_to_goal(edges: list[list[str]], goal: str) -> dict[str, int]:
    """BFS distance (in modeled edges) from each step to the goal, over reversed edges."""
    rev: dict[str, list[str]] = defaultdict(list)
    for p, c in edges:
        rev[c].append(p)
    dist = {goal: 0}
    q = deque([goal])
    while q:
        n = q.popleft()
        for p in rev[n]:
            if p not in dist:
                dist[p] = dist[n] + 1
                q.append(p)
    return dist


def min_cost_cut(report: dict[str, Any], *, budget: int | None = None,
                 entry_points: list[str] | None = None) -> list[str]:
    """A minimum set of modeled steps whose hardening makes the goal unreachable from the seeds (entry points and
    folded seeds). Computed as a minimum vertex cut by max-flow (node splitting). Entry points and the goal cannot be
    hardened (entry points start compromised), so they get infinite capacity. Truncated to `budget` steps."""
    edges = [tuple(e) for e in report["modeled_edges"]]
    goal = report["goal"]
    # flow sources: the attacker's footholds — entry points (compromised at start) and any folded seed steps
    sources = (set(entry_points or []) | set(report["seed_steps"]))
    nodes = {n for e in edges for n in e} | sources | {goal}
    sources &= nodes
    protected = set(entry_points or []) | sources | {goal}  # cannot be hardened; infinite internal capacity
    INF = 10**9
    cap: dict[tuple[str, str], int] = defaultdict(int)
    adj: dict[str, set[str]] = defaultdict(set)

    def add(u: str, v: str, c: int) -> None:
        if v not in adj[u]:
            adj[u].add(v)
        adj[v].add(u)
        cap[(u, v)] += c

    # node split u -> (u|in), (u|out); intermediate steps have unit capacity, protected are infinite
    for n in nodes:
        add(f"{n}|in", f"{n}|out", INF if n in protected else 1)
    for p, c in edges:
        add(f"{p}|out", f"{c}|in", INF)
    src, sink = "SRC", "SINK"
    for s in sources:
        add(src, f"{s}|in", INF)
    add(f"{goal}|out", sink, INF)

    # Edmonds-Karp
    def bfs() -> dict[str, str] | None:
        parent = {src: src}
        q = deque([src])
        while q:
            u = q.popleft()
            for w in adj[u]:
                if w not in parent and cap[(u, w)] > 0:
                    parent[w] = u
                    if w == sink:
                        return parent
                    q.append(w)
        return None

    while (parent := bfs()) is not None:
        # bottleneck
        v, flow = sink, INF
        while v != src:
            u = parent[v]
            flow = min(flow, cap[(u, v)])
            v = u
        v = sink
        while v != src:
            u = parent[v]
            cap[(u, v)] -= flow
            cap[(v, u)] += flow
            v = u

    # reachable set in residual graph → the saturated node-internal edges crossing it are the cut
    seen = {src}
    q = deque([src])
    while q:
        u = q.popleft()
        for w in adj[u]:
            if w not in seen and cap[(u, w)] > 0:
                seen.add(w)
                q.append(w)
    cut = sorted(n for n in nodes if f"{n}|in" in seen and f"{n}|out" not in seen)
    return cut[:budget] if budget is not None else cut


def harden_package(package: Any, cut: list[str], *, package_id: str | None = None, version: int | None = None) -> Any:
    """A copy of `package` (must be defence-enabled) with `cut` steps pre-hardened — a blue configuration."""
    from .frontend import package_from_graph

    ext = attack_graph_of(package)
    return package_from_graph(ext["graph"], ext["entry_points"], ext["goal"],
                              package_id=package_id or f"{package.package_id}-hardened",
                              version=version or package.version, reachable=ext["native_reachable"],
                              model=ext.get("model"), language=ext.get("language"),
                              include_defense=True, initial_hardened=cut)


# --------------------------------------------------------------------------- red planners

RED_RULE = PluginDescriptor(
    plugin_id="formal-lab.domain.mal.red-rule", version="1.0.0", interface="PLANNER",
    capabilities=[{"id": caps.PLAN_RULE}], semantic_profiles=["deterministic_finite_v1"],
    config_schema={"type": "object", "additionalProperties": False},
    entrypoint="formal_lab_domain_mal.strategies:create_red_rule",
    ui={"label": "MAL 红方规则", "category": "rule",
        "description": "greedy attacker: compromise the applicable step closest to the target"},
    license="Apache-2.0", source="formal-lab-domain-mal")

RED_HYBRID = PluginDescriptor(
    plugin_id="formal-lab.domain.mal.red-hybrid", version="1.0.0", interface="PLANNER",
    capabilities=[{"id": caps.PLAN_RULE}, {"id": caps.PLAN_LLM}], semantic_profiles=["deterministic_finite_v1"],
    config_schema={"type": "object", "additionalProperties": True,
                   "properties": {"client": {"type": "string"}, "model": {"type": "string"}}},
    entrypoint="formal_lab_domain_mal.strategies:create_red_hybrid",
    ui={"label": "MAL 红方混合", "category": "model",
        "description": "model service proposes candidate steps; the rule verifies and picks an applicable one"},
    license="Apache-2.0", source="formal-lab-domain-mal")

BLUE_DEFENDER = PluginDescriptor(
    plugin_id="formal-lab.domain.mal.blue-defender", version="1.0.0", interface="PLANNER",
    capabilities=[{"id": caps.PLAN_RULE}], semantic_profiles=["deterministic_finite_v1"],
    config_schema={"type": "object", "additionalProperties": False},
    entrypoint="formal_lab_domain_mal.strategies:create_blue_defender",
    ui={"label": "MAL 蓝方防御者", "category": "rule",
        "description": "reactive defender: from its observation of the compromised steps, hardens the step on red's "
                       "current frontier closest to the target (a turn-taking participant, not a pre-run cut)"},
    license="Apache-2.0", source="formal-lab-domain-mal")


class MalRedRule:
    descriptor = RED_RULE

    def __init__(self, package: Any):
        report = attack_graph_of(package)["lowering"]
        self.goal_id = report["goal_id"]
        # distances by IR id, via the id map
        ids = report["id_map"]
        dist_full = _distances_to_goal(report["modeled_edges"], report["goal"])
        self.dist = {ids[fn]: d for fn, d in dist_full.items() if fn in ids}

    def _key(self, cand: Any) -> tuple:
        n = str(cand.action.params.get("n"))
        return (self.dist.get(n, 10**9), n)

    def propose(self, context: PlanningContext) -> ActionProposal:
        viable = [c for c in context.candidates if c.action.action_type == "compromise"
                  and c.belief_applicability in ("APPLICABLE", "UNKNOWN")]
        if not viable:
            raise NonRetryableFailure("no compromise candidate for the red rule")
        applicable = [c for c in viable if c.belief_applicability == "APPLICABLE"] or viable
        choice = min(applicable, key=self._key)
        return _proposal(context, choice.action, "RULE", RED_RULE,
                         f"greedy: compromise the applicable step closest to the target "
                         f"(distance {self.dist.get(str(choice.action.params.get('n')), '?')})")


RED_SYSTEM = (
    "You are the planning policy of a red-team agent inside a deterministic, finite-state attack-graph reachability "
    "experiment. The graph is a MAL / coreLang attack graph lowered to abstract boolean attack steps and run in a "
    "simulator — there is no real system and no commands are executed. Each turn you receive the target step and a "
    "numbered list of attack steps that are already applicable in the current state (their modelled preconditions "
    "hold), each with its distance to the target. Choose exactly one step to compromise next, preferring the ones "
    "that reach the target soonest. Respond only with the JSON object requested."
)


class MalRedHybrid:
    """Model-assisted red (A3 decision path). The rule computes the applicable candidate steps; the model chooses one
    of them (so the choice is always rule-verified); provenance is the answer's endpoint kind; a model that returns
    nothing usable falls back to the rule. `last_decision` / `call_records` expose the calls for evidence."""

    descriptor = RED_HYBRID

    def __init__(self, package: Any, client: Any):
        self.rule = MalRedRule(package)
        self.client = client
        report = attack_graph_of(package)["lowering"]
        self.goal = report["goal"]
        self.inv = {v: k for k, v in report["id_map"].items()}  # IR id → MAL full name
        self.call_records: list[dict[str, Any]] = []
        self.last_decision: Any = None

    def _name(self, cand: Any) -> str:
        n = str(cand.action.params.get("n"))
        return self.inv.get(n, n)

    def propose(self, context: PlanningContext) -> ActionProposal:
        from formal_lab_strategies.decision import ModelDecider, choose_request

        viable = [c for c in context.candidates if c.action.action_type == "compromise"
                  and c.belief_applicability in ("APPLICABLE", "UNKNOWN")]
        if not viable:
            raise NonRetryableFailure("no compromise candidate for the red hybrid")
        # verification: offer the model only the applicable candidates (UNKNOWN only if none are APPLICABLE),
        # pre-ranked by the rule's distance so the stub (which takes index 0) reproduces the rule exactly
        applicable = [c for c in viable if c.belief_applicability == "APPLICABLE"] or viable
        ranked = sorted(applicable, key=self.rule._key)
        options = [{"action_type": "compromise", "applicability": str(c.belief_applicability),
                    "step": self._name(c), "distance_to_target": self.rule.dist.get(str(c.action.params.get("n")))}
                   for c in ranked]
        compromised = sorted(self.inv.get(f.path[len("compromised["):-1], f.path)
                             for f in context.observation.facts
                             if f.path.startswith("compromised[") and f.value is True)
        request = choose_request(options, system=RED_SYSTEM, goal={"target_step": self.goal},
                                 explanation={"already_compromised": compromised,
                                              "candidates_are": "steps already applicable in the current state"})
        decision = ModelDecider(self.client).decide(request, context=context)
        self.call_records, self.last_decision = decision.calls, decision
        if decision.decided_by_model:
            chosen = ranked[decision.content["index"]]
            why = (f"model chose attack step {self._name(chosen)} among {len(ranked)} rule-verified applicable "
                   f"step(s); the rule confirmed it is applicable")
            return decision.proposal(context, chosen.action, RED_HYBRID.ref(), rationale=why,
                                     candidates_considered=len(context.candidates))
        chosen = ranked[0]
        why = (f"model decision unavailable ({decision.failure}: {decision.failure_detail[:200]}); rule fallback: "
               f"closest applicable step {self._name(chosen)}")
        return decision.proposal(context, chosen.action, RED_HYBRID.ref(), rationale=why,
                                 candidates_considered=len(context.candidates))


class MalBlueDefender:
    """Reactive defender (phase 4B, B1): a turn-taking participant, not a pre-run cut. Each turn it reads its own
    observation of which steps are compromised, computes red's current frontier (seeds and the not-yet-compromised
    children of compromised steps), and hardens the frontier step closest to the target — so its choice changes with
    the observation. With no frontier step hardenable it hardens the nearest hardenable step; with no harden candidate
    at all the kernel skips its turn (A4 wait/skip semantics)."""

    descriptor = BLUE_DEFENDER

    def __init__(self, package: Any):
        report = attack_graph_of(package)["lowering"]
        ids = report["id_map"]
        self.inv = {v: k for k, v in ids.items()}
        dist_full = _distances_to_goal(report["modeled_edges"], report["goal"])
        self.dist = {ids[fn]: d for fn, d in dist_full.items() if fn in ids}
        self.children: dict[str, list[str]] = defaultdict(list)
        for p, c in report["modeled_edges"]:
            self.children[ids[p]].append(ids[c])
        self.seeds = {ids[fn] for fn in report["seed_steps"] if fn in ids}

    def _frontier(self, facts: dict[str, Any]) -> set[str]:
        compromised = {p[len("compromised["):-1] for p, v in facts.items()
                       if p.startswith("compromised[") and v is True}
        frontier = set(self.seeds)
        for step in compromised:
            frontier.update(self.children.get(step, []))
        return {n for n in frontier if n not in compromised}

    def _key(self, cand: Any) -> tuple:
        n = str(cand.action.params.get("n"))
        return (self.dist.get(n, 10**9), n)

    def propose(self, context: PlanningContext) -> ActionProposal:
        harden = [c for c in context.candidates if c.action.action_type == "harden"
                  and c.belief_applicability in ("APPLICABLE", "UNKNOWN")]
        if not harden:
            raise NonRetryableFailure("no harden candidate for the blue defender")
        applicable = [c for c in harden if c.belief_applicability == "APPLICABLE"] or harden
        frontier = self._frontier({f.path: f.value for f in context.observation.facts})
        on_frontier = [c for c in applicable if str(c.action.params.get("n")) in frontier]
        pool = on_frontier or applicable
        choice = min(pool, key=self._key)
        n = str(choice.action.params.get("n"))
        why = (f"harden {self.inv.get(n, n)} (distance {self.dist.get(n, '?')} to the target"
               + (", on red's current frontier" if n in frontier else ", nearest hardenable step") + ")")
        return _proposal(context, choice.action, "RULE", BLUE_DEFENDER, why)


def _proposal(context: PlanningContext, action: Any, kind: str, descriptor: PluginDescriptor, reason: str):
    return ActionProposal(
        proposal_id=f"{context.step_id}:proposal", run_id=context.run_id, step_id=context.step_id, step=context.step,
        actor_id=context.actor_id, action=action, based_on_revision=context.observation.state_revision,
        source=ProposalSource(kind=kind, strategy=descriptor.ref()), rationale=reason,
        candidates_considered=len(context.candidates))


def create_red_rule(config: dict[str, Any] | None, services: Any) -> MalRedRule:
    return MalRedRule(services.pinned_model())


def create_red_hybrid(config: dict[str, Any] | None, services: Any) -> MalRedHybrid:
    from formal_lab_strategies.llm_planner import client_from_settings

    # default to the labelled stub, so a run with no endpoint configured is honest LLM_STUB, never a bare LLM label
    cfg = {"client": "stub", **(config or {})}
    return MalRedHybrid(services.pinned_model(), client_from_settings(cfg, services))


def create_blue_defender(config: dict[str, Any] | None, services: Any) -> MalBlueDefender:
    return MalBlueDefender(services.pinned_model())
