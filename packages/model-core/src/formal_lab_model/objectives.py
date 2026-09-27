"""Cost objectives over paths (P2-020 … P2-024): the reference semantics.

A plan for an `ObjectiveSpec` is a path s_0 → … → s_k (k ≤ horizon) whose last state is the *first* state where the
goal holds (costs stop accumulating once the goal holds). On every lexicographic level the path's value is

    Σ_{t=1..k} [ Σ action_cost terms  w · cost(a_t)  +  Σ state_rate terms  w · expr(s_t) ]  +  Σ terminal terms  w · expr(s_k)

Levels are compared in order (minimize; maximize levels are negated); an implicit last level prefers fewer steps.

`path_values` evaluates a given path with the interpreter; `optimal_by_search` finds the optimum by exhaustive
dynamic programming over (state, remaining steps) — the ground truth the Z3 optimiser is checked against on small
models.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from typing import Any

from formal_lab_contracts import ObjectiveSpec
from formal_lab_contracts.ir import CostTerm

from .checker import CheckedModel, GroundAction
from .interpreter import Interpreter, State


@dataclass(frozen=True)
class Level:
    id: str
    direction: str  # minimize | maximize
    terms: tuple[CostTerm, ...]
    unit: str = "cost"


class ObjectiveError(ValueError):
    pass


def resolve_levels(objective: ObjectiveSpec, model: CheckedModel) -> list[Level]:
    """Levels with their terms (model objectives are looked up by id)."""
    out = []
    for level in objective.levels:
        if level.model_objective:
            decl = model.objectives.get(level.model_objective)
            if decl is None:
                raise ObjectiveError(f"the model declares no objective {level.model_objective!r}")
            out.append(Level(level.id, level.direction, tuple(decl.terms), decl.unit))
        else:
            out.append(Level(level.id, level.direction, tuple(level.terms), level.unit))
    if objective.goal_property not in model.properties:
        raise ObjectiveError(f"unknown goal property {objective.goal_property!r}")
    return out


def _step_value(interp: Interpreter, level: Level, action: GroundAction, post: State) -> int:
    total = 0
    for term in level.terms:
        if term.kind == "action_cost":
            total += term.weight * interp.model.actions[action.action].cost
        elif term.kind == "state_rate":
            total += term.weight * int(interp.evaluate(term.expr, post))
    return total


def _terminal_value(interp: Interpreter, level: Level, final: State) -> int:
    return sum(term.weight * int(interp.evaluate(term.expr, final)) for term in level.terms if term.kind == "terminal")


def path_values(interp: Interpreter, levels: list[Level], start: State, actions: list[GroundAction],
                goal: str) -> dict[str, Any]:
    """Replay `actions` from `start` and evaluate every level (independent of any solver).

    Returns {"applicable": bool, "goal_first_reached_at": int | None, "values": {level: int}, "length": k}."""
    state = start
    values = {lv.id: 0 for lv in levels}
    first_goal = 0 if interp.holds(goal, state) else None
    for i, ga in enumerate(actions):
        if first_goal is not None:
            break
        nxt = interp.apply(ga, state)
        if nxt is None:
            return {"applicable": False, "failed_at": i, "values": values, "length": i, "goal_first_reached_at": None}
        for lv in levels:
            values[lv.id] += _step_value(interp, lv, ga, nxt)
        state = nxt
        if interp.holds(goal, state):
            first_goal = i + 1
    for lv in levels:
        values[lv.id] += _terminal_value(interp, lv, state)
    return {"applicable": True, "values": values, "length": first_goal if first_goal is not None else len(actions),
            "goal_first_reached_at": first_goal, "final_state": state}


def _key(values: dict[str, int], levels: list[Level], length: int) -> tuple:
    return (*(values[lv.id] if lv.direction == "minimize" else -values[lv.id] for lv in levels), length)


def optimal_by_search(interp: Interpreter, levels: list[Level], start: State, goal: str, horizon: int,
                      max_states: int = 300_000) -> dict[str, Any] | None:
    """Exhaustive optimum (lexicographic, then fewest steps). None when no goal path exists within the horizon."""
    order = sorted(start)
    seen = {"n": 0}
    INF = None

    def key(s: State) -> tuple:
        return tuple(s[p] for p in order)

    states: dict[tuple, State] = {}

    @cache
    def best(sk: tuple, h: int):
        seen["n"] += 1
        if seen["n"] > max_states:
            raise ObjectiveError("state space too large for the exhaustive reference")
        s = states[sk]
        if interp.holds(goal, s):
            term = tuple(_terminal_value(interp, lv, s) for lv in levels)
            return ((*(t if lv.direction == "minimize" else -t for t, lv in zip(term, levels, strict=True)), 0), ())
        if h == 0:
            return INF
        choice = INF
        for ga, nxt in interp.successors(s):
            nk = key(nxt)
            states.setdefault(nk, nxt)
            sub = best(nk, h - 1)
            if sub is INF:
                continue
            step = tuple(_step_value(interp, lv, ga, nxt) * (1 if lv.direction == "minimize" else -1)
                         for lv in levels)
            total = (*(a + b for a, b in zip(step, sub[0][:-1], strict=True)), sub[0][-1] + 1)
            if choice is INF or total < choice[0]:
                choice = (total, (ga, *sub[1]))
        return choice

    sk = key(start)
    states[sk] = start
    res = best(sk, horizon)
    if res is INF:
        return None
    values = {lv.id: (v if lv.direction == "minimize" else -v) for lv, v in zip(levels, res[0][:-1], strict=True)}
    return {"values": values, "length": res[0][-1], "actions": list(res[1]), "states_explored": seen["n"]}
