"""One rendered explanation of a check result, shared by the Web UI, the CLI and exported query bundles (P2-029).

The lines say what was asked, what the verdict means and — equally important — what it does not claim: the
bound, the scope (model-internal), the assumptions, and for optimisation how much of the optimum is proven.
"""

from __future__ import annotations

from formal_lab_contracts import BoundedCheckResult

SEMANTICS = {
    "EXISTS_PATH": "is there a path of at most {k} step(s) from the start state to a state where {p!r} holds?",
    "ALL_PATHS": "do all paths of at most {k} step(s) keep {p!r}? (answered by searching a violating path)",
    "SINGLE_STEP": "is {a} applicable in the given state (unknown locations range over their domains)?",
    "OPTIMAL_PATH": "which path of at most {k} step(s) to {p!r} is cheapest, level by level?",
    "ALL_COMPLETIONS": "does the fixed sequence {seq} work for every completion of the unknown locations?",
}

MEANING = {
    "WITNESS": "a path exists; it was replayed by the reference interpreter ({replay})",
    "NO_WITNESS_WITHIN_BOUND": "no such path of at most {k} step(s) exists — a bounded conclusion; nothing is claimed "
                               "for longer paths",
    "APPLICABLE": "applicable in every allowed completion",
    "INAPPLICABLE": "inapplicable in every allowed completion",
    "UNKNOWN": "not decided: {why}",
    "UNSUPPORTED": "not checked: {why}",
    "OPTIMAL": "the returned plan is optimal on every level within the horizon (proven)",
    "FEASIBLE": "a plan was found but optimality is not proven (solver stopped); the interval states what is proven",
    "NO_PLAN_WITHIN_HORIZON": "no path of at most {k} step(s) reaches the goal — bounded conclusion",
    "ROBUST": "every completion lets the whole sequence apply",
    "NOT_ROBUST": "a completion of the unknowns breaks the sequence (counterexample below)",
}


def explain_check(result: BoundedCheckResult) -> list[str]:
    q = result.query
    k = q.bound.max_steps if q.objective is None else q.objective.horizon
    prop = q.property_id or (q.objective.goal_property if q.objective else None)
    action = f"{q.action.action_type}({', '.join(f'{a}={b}' for a, b in q.action.params.items())})" if q.action else ""
    seq = " → ".join(s.action_type for s in q.sequence) if q.sequence else ""
    lines = [f"question ({result.semantics}): " + SEMANTICS[str(result.semantics)].format(k=k, p=prop, a=action,
                                                                                            seq=seq)]
    verdict = str(result.verdict)
    why = result.stats.reason_unknown or (result.unsupported.reason if result.unsupported else "") or \
        (result.explanation or "")
    replay = result.witness.replay if result.witness else "no witness"
    lines.append(f"answer: {verdict} — " + MEANING.get(verdict, verdict).format(k=k, why=why, replay=replay))
    if result.explanation and verdict not in ("UNKNOWN", "UNSUPPORTED"):
        lines.append(f"detail: {result.explanation}")
    if result.witness is not None:
        acts = [s.action.action_type for s in result.witness.steps[1:] if s.action]
        lines.append(f"witness: {len(acts)} step(s): " + (" → ".join(acts[:12]) + (" …" if len(acts) > 12 else "")
                                                        if acts else "(start state)"))
    if result.optimization is not None:
        for lv in result.optimization.levels:
            proven = "optimal (proven)" if lv.optimal else (
                f"proven range [{lv.proven_lower if lv.proven_lower is not None else '?'}, "
                f"{lv.proven_upper if lv.proven_upper is not None else lv.value}]")
            lines.append(f"objective level {lv.level}: value {lv.value}, {proven}")
        lines.append(f"optimisation: {result.optimization.solver_calls} solver call(s), plan length "
                     f"{result.optimization.plan_length}, method: {result.optimization.method}")
    if result.robustness is not None and result.robustness.counterexample is not None:
        rob = result.robustness
        at = f"action {rob.failing_index + 1} ({rob.sequence[rob.failing_index]}) fails" \
            if rob.failing_index is not None else "the goal does not hold at the end"
        lines.append(f"counterexample completion {rob.counterexample}: {at}")
    if result.observation_request is not None:
        req = result.observation_request
        lines.append(f"to settle it, observe {req.paths} (applicable with {req.applicable_completion}, "
                     f"inapplicable with {req.inapplicable_completion})")
    if result.assumption_set is not None and result.assumption_set.items:
        lines.append(f"assumptions: {len(result.assumption_set.items)} location(s) not freshly observed "
                     f"({result.assumption_set.counts})")
    for a in result.assumptions:
        lines.append(f"assumed: {a}")
    lines.append(f"scope: {result.scope} (a conclusion about the model, not the real system); bound "
                 f"{q.bound.max_steps} step(s)" + (f", timeout {q.bound.timeout_ms} ms" if q.bound.timeout_ms else ""))
    lines.append(f"backend: {result.backend.name} {result.backend.version}, {result.stats.elapsed_ms:.0f} ms, "
                 f"status {result.stats.solver_status}")
    return lines
