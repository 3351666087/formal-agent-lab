"""Cost optimisation and robustness queries on the Z3 encoding (P2-021 … P2-027).

OPTIMIZE_OBJECTIVE — the path semantics of `formal_lab_model.objectives`, encoded over a fixed unrolling of
`horizon` steps with a *done* flag: done_t ⇔ the goal held at some s_i, i ≤ t. While not done, step t is an
ordinary transition and pays its step costs; once done the state stutters and pays nothing; the goal must hold at
s_H. Each lexicographic level (then the plan length) is minimised by incremental bound tightening on one solver:
after any solution with value v, ask for value ≤ v − d with d doubling until unsat, then binary-search the gap.
An unsat answer for value ≤ x proves that no plan within the horizon is cheaper than x + 1 (`proven_lower`);
a timeout keeps the best plan found as FEASIBLE with the interval [proven_lower, value]. The optimum found on a
level is fixed before the next level is optimised. The witness is replayed by the reference interpreter and its
values are recomputed independently (`formal_lab_model.objectives.path_values`).

ROBUST_SEQUENCE — a fixed action sequence from a partial state: known locations fixed, unknown ones free within
their domains. ROBUST iff every completion lets every action apply in turn (and, if a goal is given, reach it);
otherwise the solver's completion is the counterexample. Open-loop only — it never branches on later observations.
"""

from __future__ import annotations

import time
from typing import Any

import z3
from formal_lab_contracts import GroundAction as CGroundAction
from formal_lab_contracts import (
    ObjectiveBound,
    ObjectiveSpec,
    OptimizationResult,
    OptimizationStatus,
    RobustnessResult,
    RobustnessVerdict,
    StateScalar,
    Witness,
    WitnessStep,
)
from formal_lab_model.interpreter import Interpreter
from formal_lab_model.objectives import Level, path_values, resolve_levels

from .compiler import Z3Model, _ite_num, _sum


def _to_contract(ga) -> CGroundAction:
    return CGroundAction(action_type=ga.action, params=dict(ga.params))


class _Deadline:
    def __init__(self, timeout_ms: int):
        self.end = time.perf_counter() + timeout_ms / 1000

    def remaining_ms(self) -> int:
        return int((self.end - time.perf_counter()) * 1000)


def optimize(zm: Z3Model, interp: Interpreter, objective: ObjectiveSpec, start: dict[str, StateScalar],
             timeout_ms: int) -> tuple[OptimizationResult, Witness | None, dict[str, Any]]:
    levels = resolve_levels(objective, zm.m)
    H = objective.horizon
    deadline = _Deadline(timeout_ms)
    solver = zm.solver()
    S = [zm.state_vars(0)]
    solver.add(*zm.domain_constraints(S[0]))
    solver.add(*zm.fix_state(S[0], start))
    done = [zm.prop(objective.goal_property, S[0])]
    acts = []
    step_costs: dict[str, list[Any]] = {lv.id: [] for lv in levels}
    lengths = []
    action_cost = {i: zm.m.actions[ga.action].cost for i, ga in enumerate(zm.actions)}
    for t in range(H):
        S.append(zm.state_vars(t + 1))
        act, cons = zm.transition(t, S[t], S[t + 1])
        acts.append(act)
        running = z3.Not(done[t])
        range_cons, rest = cons[:2], cons[2:]  # `transition` starts with the act@t range constraints
        solver.add(*range_cons)
        solver.add(z3.Implies(running, z3.And(*[zm.as_bool(c) for c in rest])))
        solver.add(z3.Implies(done[t], z3.And(*[S[t + 1][p] == S[t][p] for p in zm.state_paths])))
        for lv in levels:
            step = _level_step(zm, lv, act, S[t + 1], action_cost)
            step_costs[lv.id].append(_ite_num(running, step, 0))
        lengths.append(z3.If(running, z3.IntVal(1, zm.ctx), z3.IntVal(0, zm.ctx)))
        done.append(z3.Or(done[t], zm.prop(objective.goal_property, S[t + 1])))
    solver.add(done[H])
    values = {}
    for lv in levels:
        terminal = [term.weight * zm.expr(term.expr, S[H], {}) for term in lv.terms if term.kind == "terminal"]
        total = _sum(step_costs[lv.id] + terminal)
        values[lv.id] = total if not isinstance(total, int) else z3.IntVal(total, zm.ctx)
    length = z3.Sum(*lengths) if lengths else z3.IntVal(0, zm.ctx)
    order = [(lv.id, values[lv.id] if lv.direction == "minimize" else -values[lv.id]) for lv in levels]
    order.append(("__length", length))

    calls = 0
    bounds: dict[str, dict[str, Any]] = {}
    model = None
    status = OptimizationStatus.OPTIMAL
    for name, expr in order:
        # first feasible solution under the levels fixed so far
        rem = deadline.remaining_ms()
        if rem <= 0:
            status = OptimizationStatus.FEASIBLE if model is not None else OptimizationStatus.UNKNOWN
            break
        solver.set("timeout", rem)
        res = solver.check()
        calls += 1
        if res == z3.unsat:
            if model is None:
                return (OptimizationResult(objective_id=objective.objective_id,
                                           status=OptimizationStatus.NO_PLAN_WITHIN_HORIZON, horizon=H,
                                           solver_calls=calls), None, {"reason": "no goal path within the horizon"})
            break
        if res == z3.unknown:
            status = OptimizationStatus.FEASIBLE if model is not None else OptimizationStatus.UNKNOWN
            reason = solver.reason_unknown()
            bounds.setdefault(name, {"value": None, "proven_lower": None, "optimal": False})
            if model is None:
                return (OptimizationResult(objective_id=objective.objective_id, status=status, horizon=H,
                                           solver_calls=calls), None, {"reason": reason})
            break
        model = solver.model()
        best = model.eval(expr, model_completion=True).as_long()
        lower = None  # all values < lower are proven impossible
        step = 1
        proven = False
        # gallop downwards, then binary search between the last unsat bound and the best found
        while True:
            if lower is not None and lower >= best:
                proven = True
                break
            target = best - step if lower is None else (lower + best - 1) // 2
            if lower is not None:
                target = max(target, lower)
            rem = deadline.remaining_ms()
            if rem <= 0:
                break
            solver.push()
            solver.add(expr <= target)
            solver.set("timeout", rem)
            r = solver.check()
            calls += 1
            if r == z3.sat:
                model = solver.model()
                best = model.eval(expr, model_completion=True).as_long()
                solver.pop()
                step *= 2
            elif r == z3.unsat:
                solver.pop()
                lower = target + 1
            else:
                solver.pop()
                break
        if not proven:
            status = OptimizationStatus.FEASIBLE
        bounds[name] = {"value": best, "proven_lower": lower, "optimal": proven}
        solver.add(expr == best if proven else expr <= best)
        if not proven:
            break
    if model is None:
        return (OptimizationResult(objective_id=objective.objective_id, status=OptimizationStatus.UNKNOWN, horizon=H,
                                   solver_calls=calls), None, {"reason": "timeout before any plan"})

    # witness: states until the goal first holds
    states, actions = [], []
    k = model.eval(length, model_completion=True).as_long()
    for t in range(k + 1):
        states.append({p: zm.decode_value(p, model.eval(S[t][p], model_completion=True)) for p in zm.state_paths})
        if t > 0:
            actions.append(zm.actions[model.eval(acts[t - 1], model_completion=True).as_long()])
    steps = [WitnessStep(step=t, action=_to_contract(actions[t - 1]) if t else None, state=states[t])
             for t in range(k + 1)]
    replay = path_values(interp, levels, states[0], actions, objective.goal_property)
    level_values = {lv.id: model.eval(values[lv.id], model_completion=True).as_long() for lv in levels}
    ok = (replay["applicable"] and replay["goal_first_reached_at"] == k
          and all(replay["values"][lv.id] == level_values[lv.id] for lv in levels)
          and replay["final_state"] == states[-1])
    witness = Witness(steps=steps, replay="CONFIRMED" if ok else "REFUTED",
                      replay_note="replayed and re-costed by the reference interpreter" if ok else
                      f"interpreter replay disagrees: {replay['values']} vs {level_values}")
    out_levels = []
    for lv in levels:
        b = bounds.get(lv.id, {})
        value = level_values[lv.id]
        lower = b.get("proven_lower")
        if lv.direction == "maximize":  # bounds were computed on the negated value
            out_levels.append(ObjectiveBound(level=lv.id, value=value, proven_lower=None,
                                             proven_upper=-lower if lower is not None else None,
                                             optimal=b.get("optimal", False)))
        else:
            out_levels.append(ObjectiveBound(level=lv.id, value=value, proven_lower=lower, proven_upper=value,
                                             optimal=b.get("optimal", False)))
    result = OptimizationResult(objective_id=objective.objective_id, status=status, horizon=H, plan_length=k,
                                levels=out_levels, solver_calls=calls)
    return result, witness, {"length_optimal": bounds.get("__length", {}).get("optimal", False)}


def _level_step(zm: Z3Model, lv: Level, act: Any, post: dict[str, Any], action_cost: dict[int, int]) -> Any:
    parts = []
    for term in lv.terms:
        if term.kind == "action_cost":
            chain: Any = z3.IntVal(0, zm.ctx)
            for i, cost in action_cost.items():
                if cost:
                    chain = z3.If(act == i, z3.IntVal(cost, zm.ctx), chain)
            parts.append(term.weight * chain)
        elif term.kind == "state_rate":
            val = zm.expr(term.expr, post, {})
            parts.append(term.weight * (val if not isinstance(val, int) else z3.IntVal(val, zm.ctx)))
    return _sum(parts) if parts else 0


def robust_sequence(zm: Z3Model, interp: Interpreter, sequence: list, known: dict[str, StateScalar],
                    unknown_paths: list[str], goal: str | None, timeout_ms: int) -> RobustnessResult:
    keys = [ga.key for ga in sequence]
    S = [zm.state_vars(0)]
    solver = zm.solver()
    solver.set("timeout", timeout_ms)
    solver.add(*zm.domain_constraints(S[0]))
    solver.add(*zm.fix_state(S[0], {p: v for p, v in known.items() if p not in set(unknown_paths)}))
    enabled = []
    for t, ga in enumerate(sequence):
        idx = zm.actions.index(ga)
        nxt = zm.next_values(idx, S[t])
        enabled.append(zm.as_bool(zm.enabled(idx, S[t], nxt)))
        S.append(zm.state_vars(t + 1))
        for p in zm.state_paths:
            solver.add(S[t + 1][p] == nxt.get(p, S[t][p]))
    ok = [*enabled] + ([zm.prop(goal, S[-1])] if goal else [])
    solver.add(z3.Not(z3.And(*ok)))
    res = solver.check()
    if res == z3.unsat:
        return RobustnessResult(verdict=RobustnessVerdict.ROBUST, sequence=keys, require_goal=goal,
                                unknown_paths=sorted(unknown_paths))
    if res == z3.unknown:
        return RobustnessResult(verdict=RobustnessVerdict.UNKNOWN, sequence=keys, require_goal=goal,
                                unknown_paths=sorted(unknown_paths))
    m = solver.model()
    completion = {p: zm.decode_value(p, m.eval(S[0][p], model_completion=True)) for p in sorted(unknown_paths)}
    start = dict(known)
    start.update(completion)
    states, failed = interp.replay(start, sequence)  # independent confirmation of the counterexample
    goal_fails = failed is None and goal is not None and not interp.holds(goal, states[-1])
    return RobustnessResult(verdict=RobustnessVerdict.NOT_ROBUST, sequence=keys, require_goal=goal,
                            counterexample=completion, failing_index=failed, goal_fails=goal_fails,
                            unknown_paths=sorted(unknown_paths))
