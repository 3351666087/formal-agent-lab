"""Reference interpreter for deterministic_finite_v1 (pure Python, explicit AST evaluation).

This is the normative executable semantics. The Z3 compiler implements the same semantics
independently; tests compare both on small models and replay solver witnesses here.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

from formal_lab_contracts import StateScalar, state_path
from formal_lab_contracts.ir import (
    ApplyExpr,
    AssignEffect,
    ConstExpr,
    ForallEffect,
    QuantExpr,
    RefExpr,
    VarExpr,
    WhenEffect,
)

from .checker import CheckedModel, GroundAction, TInt

State = dict[str, StateScalar]
Env = dict[str, StateScalar]
Evaluator = Callable[[State, Env], Any]
EffectFn = Callable[[State, Env, list[tuple[str, StateScalar]]], None]


class EvaluationError(Exception):
    pass


@dataclass
class StepResult:
    action: GroundAction
    applicable: bool
    reason: str | None
    next_state: State | None
    writes: list[tuple[str, StateScalar]]


class Interpreter:
    def __init__(self, model: CheckedModel):
        if model.issues:
            raise EvaluationError("cannot interpret a model with issues")
        self.model = model
        self.consts: dict[str, StateScalar] = {}
        for fam in model.families.values():
            if not fam.is_state:
                self.consts.update(fam.table)
        self._state_names = {f.name for f in model.state_families}
        self._pre: dict[str, Evaluator] = {}
        self._eff: dict[str, EffectFn] = {}
        for name, act in model.actions.items():
            self._pre[name] = self.compile_expr(act.precondition)
            self._eff[name] = self._compile_effects(act.effects)
        self._props = {pid: self.compile_expr(p.expr) for pid, p in model.properties.items()}
        self._int_ranges = {
            fam.name: (fam.ty.lo, fam.ty.hi) for fam in model.state_families if isinstance(fam.ty, TInt)
        }

    # ------------------------------------------------------------------ expressions
    def compile_expr(self, expr: Any) -> Evaluator:
        if isinstance(expr, ConstExpr):
            value = expr.value
            return lambda s, e: value
        if isinstance(expr, RefExpr):
            name = expr.name
            return lambda s, e: e[name]
        if isinstance(expr, VarExpr):
            return self._compile_read(expr.name, [self.compile_expr(i) for i in expr.index])
        if isinstance(expr, QuantExpr):
            members = self.model.domains[expr.domain]
            var = expr.var
            body = self.compile_expr(expr.body)
            where = self.compile_expr(expr.where) if expr.where is not None else None

            def envs(s: State, e: Env) -> Iterator[Env]:
                for m in members:
                    inner = {**e, var: m}
                    if where is None or where(s, inner):
                        yield inner

            if expr.op == "forall":
                return lambda s, e: all(body(s, i) for i in envs(s, e))
            if expr.op == "exists":
                return lambda s, e: any(body(s, i) for i in envs(s, e))
            if expr.op == "count":
                return lambda s, e: sum(1 for i in envs(s, e) if body(s, i))
            if expr.op in ("max_over", "min_over"):
                pick = max if expr.op == "max_over" else min
                default = self.compile_expr(expr.default) if expr.default is not None else None

                def extremum(s: State, e: Env, pick=pick, default=default) -> Any:
                    values = [body(s, i) for i in envs(s, e)]
                    if values:
                        return pick(values)
                    if default is None:
                        raise EvaluationError(f"{expr.op} over an empty set without a default")
                    return default(s, e)

                return extremum
            return lambda s, e: sum(body(s, i) for i in envs(s, e))
        if isinstance(expr, ApplyExpr):
            args = [self.compile_expr(a) for a in expr.args]
            return _APPLY[expr.op](args)
        raise EvaluationError(f"cannot evaluate {expr!r}")

    def _compile_read(self, name: str, index: list[Evaluator]) -> Evaluator:
        is_state = name in self._state_names
        consts = self.consts
        if not index:
            if is_state:
                return lambda s, e: s[name]
            value = consts[name]
            return lambda s, e: value
        if is_state:
            return lambda s, e: s[f"{name}[{','.join(str(f(s, e)) for f in index)}]"]
        return lambda s, e: consts[f"{name}[{','.join(str(f(s, e)) for f in index)}]"]

    def _compile_effects(self, effects: list[Any]) -> EffectFn:
        parts: list[EffectFn] = []
        for eff in effects:
            if isinstance(eff, AssignEffect):
                name = eff.target.var
                idx = [self.compile_expr(i) for i in eff.target.index]
                value = self.compile_expr(eff.value)

                def assign(s: State, e: Env, w: list, name=name, idx=idx, value=value) -> None:
                    path = f"{name}[{','.join(str(f(s, e)) for f in idx)}]" if idx else name
                    w.append((path, value(s, e)))

                parts.append(assign)
            elif isinstance(eff, WhenEffect):
                cond = self.compile_expr(eff.condition)
                then = self._compile_effects(eff.then)
                other = self._compile_effects(eff.otherwise)

                def when(s: State, e: Env, w: list, cond=cond, then=then, other=other) -> None:
                    (then if cond(s, e) else other)(s, e, w)

                parts.append(when)
            elif isinstance(eff, ForallEffect):
                members = self.model.domains[eff.domain]
                var = eff.var
                where = self.compile_expr(eff.where) if eff.where is not None else None
                inner = self._compile_effects(eff.effects)

                def forall(s: State, e: Env, w: list, members=members, var=var, where=where, inner=inner) -> None:
                    for m in members:
                        env = {**e, var: m}
                        if where is None or where(s, env):
                            inner(s, env, w)

                parts.append(forall)

        def run(s: State, e: Env, w: list) -> None:
            for part in parts:
                part(s, e, w)

        return run

    # ------------------------------------------------------------------ semantics
    def initial_state(self) -> State:
        return self.model.initial_state()

    def evaluate(self, expr: Any, state: State, env: Env | None = None) -> Any:
        return self.compile_expr(expr)(state, env or {})

    def holds(self, property_id: str, state: State) -> bool:
        return bool(self._props[property_id](state, {}))

    def precondition(self, action: GroundAction, state: State) -> bool:
        return bool(self._pre[action.action](state, action.params_dict()))

    def step(self, action: GroundAction, state: State) -> StepResult:
        env = action.params_dict()
        if not self._pre[action.action](state, env):
            return StepResult(action, False, "PRECONDITION_FALSE", None, [])
        writes: list[tuple[str, StateScalar]] = []
        self._eff[action.action](state, env, writes)
        nxt = dict(state)
        for path, value in writes:  # later writes override earlier ones
            nxt[path] = value
        for path in {p for p, _ in writes}:
            rng = self._int_ranges.get(path.split("[", 1)[0])
            if rng is not None and not rng[0] <= nxt[path] <= rng[1]:  # type: ignore[operator]
                return StepResult(action, False, f"DOMAIN_GUARD: {path}={nxt[path]} outside [{rng[0]}, {rng[1]}]",
                                  None, writes)
        return StepResult(action, True, None, nxt, writes)

    def apply(self, action: GroundAction, state: State) -> State | None:
        return self.step(action, state).next_state

    def successors(self, state: State) -> Iterator[tuple[GroundAction, State]]:
        for ga in self.model.ground_actions:
            nxt = self.apply(ga, state)
            if nxt is not None:
                yield ga, nxt

    def applicable_actions(self, state: State) -> list[GroundAction]:
        return [ga for ga, _ in self.successors(state)]

    def ground(self, action: str, params: dict[str, StateScalar]) -> GroundAction:
        decl = self.model.actions.get(action)
        if decl is None:
            raise KeyError(f"unknown action {action!r}")
        names = [p.name for p in decl.params]
        if set(params) != set(names):
            raise KeyError(f"action {action} expects params {names}, got {sorted(params)}")
        ga = GroundAction(action, tuple((n, params[n]) for n in names))
        if ga not in set(self.model.ground_actions):
            raise KeyError(f"parameter value outside its domain: {ga.key}")
        return ga

    # ------------------------------------------------------------------ partial states
    def applicability_with_unknowns(
        self, action: GroundAction, known: State, unknown_paths: list[str], max_completions: int = 50_000
    ) -> tuple[str, int]:
        """Reference answer for SINGLE_STEP queries over a partial state.

        Enumerates all completions of the unknown locations: APPLICABLE if applicable in every
        completion, INAPPLICABLE if in none, UNKNOWN otherwise (evidence is insufficient).
        """
        domains = [self.model.param_domain(self.model.location_type(p)) for p in unknown_paths]
        total = 1
        for d in domains:
            total *= len(d)
        if total > max_completions:
            return "UNKNOWN", 0
        seen_true = seen_false = False
        count = 0
        for combo in itertools.product(*domains):
            state = dict(known)
            state.update(zip(unknown_paths, combo, strict=True))
            ok = self.step(action, state).applicable
            seen_true |= ok
            seen_false |= not ok
            count += 1
            if seen_true and seen_false:
                return "UNKNOWN", count
        return ("APPLICABLE" if seen_true else "INAPPLICABLE"), count

    def replay(self, start: State, actions: list[GroundAction]) -> tuple[list[State], int | None]:
        """Replay actions; returns (states, index of first inapplicable action or None)."""
        states = [start]
        cur = start
        for i, ga in enumerate(actions):
            nxt = self.apply(ga, cur)
            if nxt is None:
                return states, i
            states.append(nxt)
            cur = nxt
        return states, None


def _all(args):
    return lambda s, e: all(a(s, e) for a in args)


def _any(args):
    return lambda s, e: any(a(s, e) for a in args)


def _sub(args):
    first, rest = args[0], args[1:]
    return lambda s, e: first(s, e) - sum(a(s, e) for a in rest)


def _mul(args):
    def run(s, e):
        out = 1
        for a in args:
            out *= a(s, e)
        return out

    return run


_APPLY: dict[str, Callable[[list[Evaluator]], Evaluator]] = {
    "not": lambda a: lambda s, e: not a[0](s, e),
    "and": _all,
    "or": _any,
    "implies": lambda a: lambda s, e: (not a[0](s, e)) or bool(a[1](s, e)),
    "eq": lambda a: lambda s, e: a[0](s, e) == a[1](s, e),
    "ne": lambda a: lambda s, e: a[0](s, e) != a[1](s, e),
    "lt": lambda a: lambda s, e: a[0](s, e) < a[1](s, e),
    "le": lambda a: lambda s, e: a[0](s, e) <= a[1](s, e),
    "gt": lambda a: lambda s, e: a[0](s, e) > a[1](s, e),
    "ge": lambda a: lambda s, e: a[0](s, e) >= a[1](s, e),
    "add": lambda a: lambda s, e: sum(x(s, e) for x in a),
    "sub": _sub,
    "mul": _mul,
    "neg": lambda a: lambda s, e: -a[0](s, e),
    "min": lambda a: lambda s, e: min(x(s, e) for x in a),
    "max": lambda a: lambda s, e: max(x(s, e) for x in a),
    "ite": lambda a: lambda s, e: a[1](s, e) if a[0](s, e) else a[2](s, e),
}


def location(name: str, *index: str) -> str:
    return state_path(name, index)
