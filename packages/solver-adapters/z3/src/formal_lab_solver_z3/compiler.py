"""Compile deterministic_finite_v1 models to Z3 (bounded unrolling).

Independent of the reference interpreter: it shares only the static symbol tables produced by
`formal_lab_model.check_model` (domains, location families, ground actions) and re-implements the
evaluation semantics symbolically. Encoding:

- bool locations → Bool, int locations → Int with range constraints, enum/entity locations → Int
  codes 0..n-1 in declaration order.
- state copy t has constants  `<path>@<t>`; the action taken between t and t+1 is `act@<t>` (Int index
  into the ground-action list).
- For every location p: p@(t+1) = ite(act@t = a1, next_a1(p), ite(act@t = a2, …, p@t)) over the
  actions that write p; next_a(p) folds a's writes in declaration order (later write wins).
- act@t = a  ⇒  pre_a(S_t) ∧ post-state of every written int location within its declared range.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Any

import z3
from formal_lab_contracts import StateScalar
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
from formal_lab_model.checker import CheckedModel, GroundAction, LocationFamily, TBool, TInt, TSym


class CompileError(Exception):
    pass


@dataclass(frozen=True)
class ZSym:
    """A symbolic enum/entity value: `term` is a member name (concrete) or a Z3 Int code."""

    domain: str | None
    term: Any


@dataclass(frozen=True)
class _Choice:
    """ite over symbols whose domain is not known yet (resolved when an encoding is needed)."""

    cond: Any
    then: ZSym
    other: ZSym


class Z3Model:
    """Z3 encoding of one checked model. Owns a private z3.Context: Z3 contexts are not thread-safe, so a
    Z3Model must only be used by one thread at a time (callers cache one per thread)."""

    def __init__(self, model: CheckedModel, ctx: z3.Context | None = None):
        if model.issues:
            raise CompileError("model has issues")
        self.ctx = ctx or z3.Context()
        self.m = model
        self.codes = {d: {name: i for i, name in enumerate(members)} for d, members in model.domains.items()}
        self.consts: dict[str, StateScalar] = {}
        self.family_of: dict[str, LocationFamily] = {}
        for fam in model.families.values():
            for path in fam.table:
                self.family_of[path] = fam
            if not fam.is_state:
                self.consts.update(fam.table)
        self.owners: dict[str, list[str]] = {}
        for d, members in model.domains.items():
            for name in members:
                self.owners.setdefault(name, []).append(d)
        self.state_paths = model.state_paths()
        self.actions = model.ground_actions
        self._writes_cache: dict[int, list[tuple[str, Any, Any]]] = {}

    # ------------------------------------------------------------------ state copies
    def state_vars(self, t: int) -> dict[str, z3.ExprRef]:
        out = {}
        for path in self.state_paths:
            ty = self.family_of[path].ty
            name = f"{path}@{t}"
            out[path] = z3.Bool(name, self.ctx) if isinstance(ty, TBool) else z3.Int(name, self.ctx)
        return out

    def domain_constraints(self, S: dict[str, z3.ExprRef]) -> list[z3.BoolRef]:
        cons = []
        for path, var in S.items():
            ty = self.family_of[path].ty
            if isinstance(ty, TInt):
                cons.append(z3.And(var >= ty.lo, var <= ty.hi))
            elif isinstance(ty, TSym):
                cons.append(z3.And(var >= 0, var < len(self.m.domains[ty.domain])))
        return cons

    def encode_value(self, path: str, value: StateScalar) -> Any:
        ty = self.family_of[path].ty
        if isinstance(ty, TSym):
            return z3.IntVal(self.codes[ty.domain][value], self.ctx)  # type: ignore[index]
        if isinstance(ty, TBool):
            return z3.BoolVal(bool(value), self.ctx)
        return z3.IntVal(int(value), self.ctx)

    def decode_value(self, path: str, value: z3.ExprRef) -> StateScalar:
        ty = self.family_of[path].ty
        if isinstance(ty, TBool):
            return z3.is_true(value)
        n = value.as_long()  # type: ignore[attr-defined]
        if isinstance(ty, TSym):
            return self.m.domains[ty.domain][n]
        return n

    def fix_state(self, S: dict[str, z3.ExprRef], state: dict[str, StateScalar]) -> list[z3.BoolRef]:
        return [S[p] == self.encode_value(p, val) for p, val in state.items() if p in S]

    # ------------------------------------------------------------------ expressions
    def _sym_code(self, x: ZSym, domain: str) -> Any:
        if isinstance(x.term, str):
            return z3.IntVal(self.codes[domain][x.term], self.ctx)
        if isinstance(x.term, _Choice):
            ch = x.term
            return z3.If(ch.cond, self._sym_code(ch.then, domain), self._sym_code(ch.other, domain))
        return x.term

    def _domain_of(self, *xs: ZSym) -> str:
        for x in xs:
            if x.domain is not None:
                return x.domain
        for x in xs:
            if isinstance(x.term, _Choice):
                return self._domain_of(x.term.then, x.term.other)
            if isinstance(x.term, str):
                owners = self.owners.get(x.term, [])
                if len(owners) == 1:
                    return owners[0]
        raise CompileError(f"cannot determine the domain of symbolic value(s) {xs!r}")

    def _eq(self, a: Any, b: Any) -> Any:
        if isinstance(a, ZSym) or isinstance(b, ZSym):
            assert isinstance(a, ZSym) and isinstance(b, ZSym)
            if isinstance(a.term, str) and isinstance(b.term, str):
                return a.term == b.term
            domain = self._domain_of(a, b)
            return self._sym_code(a, domain) == self._sym_code(b, domain)
        return a == b

    def _read(self, name: str, index: list[Any], S: dict[str, z3.ExprRef]) -> Any:
        fam = self.m.families[name]
        if all(isinstance(i, ZSym) and isinstance(i.term, str) for i in index):
            path = f"{name}[{','.join(i.term for i in index)}]" if index else name
            return self._location(path, fam, S)
        # symbolic index: case split over the finite index product
        result = None
        for combo in itertools.product(*[self.m.domains[d] for d in fam.index]):
            path = f"{name}[{','.join(combo)}]"
            cond = _and([(i.term == member) if isinstance(i.term, str) else (i.term == self.codes[d][member])
                         for i, member, d in zip(index, combo, fam.index, strict=True)])
            val = self._location(path, fam, S)
            result = val if result is None else self._ite(cond, val, result)
        return result

    def _location(self, path: str, fam: LocationFamily, S: dict[str, z3.ExprRef]) -> Any:
        if fam.is_state:
            raw = S[path]
        else:
            raw = self.consts[path]
        if isinstance(fam.ty, TSym):
            return ZSym(fam.ty.domain, raw)
        return raw

    def _ite(self, c: Any, a: Any, b: Any) -> Any:
        if isinstance(c, bool):
            return a if c else b
        if isinstance(a, ZSym) or isinstance(b, ZSym):
            domain = a.domain or b.domain
            if domain is None:
                return ZSym(None, _Choice(c, a, b))
            return ZSym(domain, z3.If(c, self._sym_code(a, domain), self._sym_code(b, domain)))
        return z3.If(c, a, b)

    def expr(self, e: Any, S: dict[str, z3.ExprRef], env: dict[str, Any]) -> Any:
        if isinstance(e, ConstExpr):
            val = e.value
            if isinstance(val, str):
                return ZSym(e.domain, val)
            return val
        if isinstance(e, RefExpr):
            return env[e.name]
        if isinstance(e, VarExpr):
            return self._read(e.name, [self.expr(i, S, env) for i in e.index], S)
        if isinstance(e, QuantExpr):
            members = self.m.domains[e.domain]
            parts = []
            for member in members:
                inner = {**env, e.var: ZSym(e.domain, member)}
                cond = self.expr(e.where, S, inner) if e.where is not None else True
                body = self.expr(e.body, S, inner)
                parts.append((cond, body))
            if e.op == "forall":
                return _and([_implies(c, b) for c, b in parts])
            if e.op == "exists":
                return _or([_and([c, b]) for c, b in parts])
            if e.op == "count":
                return _sum([_ite_num(_and([c, b]), 1, 0) for c, b in parts])
            if e.op in ("max_over", "min_over"):
                # fold from the default (value when no member qualifies): best = ite(c_i ∧ (none yet ∨ b_i beats
                # best), b_i, best), tracking "some member qualified" separately so the default never competes
                default = self.expr(e.default, S, env) if e.default is not None else 0
                best: Any = default
                seen: Any = False
                for c, b in parts:
                    beats = _cmp(b, best, e.op)
                    take = _and([c, _or([_not(seen), beats])])
                    best = _ite_num(take, b, best)
                    seen = _or([seen, c])
                return best
            return _sum([_ite_num(c, b, 0) for c, b in parts])
        if isinstance(e, ApplyExpr):
            args = [self.expr(a, S, env) for a in e.args]
            op = e.op
            if op == "not":
                return _not(args[0])
            if op == "and":
                return _and(args)
            if op == "or":
                return _or(args)
            if op == "implies":
                return _implies(args[0], args[1])
            if op == "eq":
                return self._eq(args[0], args[1])
            if op == "ne":
                return _not(self._eq(args[0], args[1]))
            if op in ("lt", "le", "gt", "ge"):
                a, b = args
                return {"lt": a < b, "le": a <= b, "gt": a > b, "ge": a >= b}[op]
            if op == "add":
                return _sum(args)
            if op == "sub":
                out = args[0]
                for a in args[1:]:
                    out = out - a
                return out
            if op == "mul":
                out = args[0]
                for a in args[1:]:
                    out = out * a
                return out
            if op == "neg":
                return -args[0]
            if op in ("min", "max"):
                out = args[0]
                for a in args[1:]:
                    pick = (a < out) if op == "min" else (a > out)
                    out = a if isinstance(pick, bool) and pick else (out if isinstance(pick, bool) else z3.If(pick, a, out))
                return out
            if op == "ite":
                return self._ite(args[0], args[1], args[2])
        raise CompileError(f"cannot compile expression {e!r}")

    # ------------------------------------------------------------------ actions
    def action_env(self, ga: GroundAction) -> dict[str, Any]:
        decl = self.m.actions[ga.action]
        env: dict[str, Any] = {}
        for p in decl.params:
            val = dict(ga.params)[p.name]
            env[p.name] = ZSym(p.type.name if p.type.kind == "enum" else p.type.set, val) if isinstance(val, str) \
                else val
        return env

    def writes(self, idx: int, S: dict[str, z3.ExprRef]) -> list[tuple[str, Any, Any]]:
        """(path, guard, value) in declaration order."""
        ga = self.actions[idx]
        env = self.action_env(ga)
        out: list[tuple[str, Any, Any]] = []
        self._collect(self.m.actions[ga.action].effects, S, env, True, out)
        return out

    def _collect(self, effects: list[Any], S, env, guard, out) -> None:
        for eff in effects:
            if isinstance(eff, AssignEffect):
                fam = self.m.families[eff.target.var]
                index = [self.expr(i, S, env) for i in eff.target.index]
                value = self.expr(eff.value, S, env)
                if isinstance(fam.ty, TSym):
                    value = self._sym_code(value, fam.ty.domain)
                if all(isinstance(i.term, str) for i in index):
                    path = f"{fam.name}[{','.join(i.term for i in index)}]" if index else fam.name
                    out.append((path, guard, value))
                else:
                    for combo in itertools.product(*[self.m.domains[d] for d in fam.index]):
                        cond = _and([(i.term == m) if isinstance(i.term, str) else (i.term == self.codes[d][m])
                                     for i, m, d in zip(index, combo, fam.index, strict=True)])
                        out.append((f"{fam.name}[{','.join(combo)}]", _and([guard, cond]), value))
            elif isinstance(eff, WhenEffect):
                cond = self.expr(eff.condition, S, env)
                self._collect(eff.then, S, env, _and([guard, cond]), out)
                self._collect(eff.otherwise, S, env, _and([guard, _not(cond)]), out)
            elif isinstance(eff, ForallEffect):
                for member in self.m.domains[eff.domain]:
                    inner = {**env, eff.var: ZSym(eff.domain, member)}
                    cond = self.expr(eff.where, S, inner) if eff.where is not None else True
                    self._collect(eff.effects, S, inner, _and([guard, cond]), out)

    def next_values(self, idx: int, S: dict[str, z3.ExprRef]) -> dict[str, Any]:
        nxt: dict[str, Any] = {}
        for path, guard, value in self.writes(idx, S):
            prev = nxt.get(path, S[path])
            nxt[path] = value if guard is True else (prev if guard is False else z3.If(guard, value, prev))
        return nxt

    def enabled(self, idx: int, S: dict[str, z3.ExprRef], nxt: dict[str, Any] | None = None) -> Any:
        ga = self.actions[idx]
        pre = self.expr(self.m.actions[ga.action].precondition, S, self.action_env(ga))
        nxt = self.next_values(idx, S) if nxt is None else nxt
        guards = []
        for path, val in nxt.items():
            ty = self.family_of[path].ty
            if isinstance(ty, TInt):
                guards.append(_and([val >= ty.lo, val <= ty.hi]))  # may be python bools: keep ctx-safe
        return _and([pre, *guards])

    def transition(self, t: int, S: dict[str, z3.ExprRef], S2: dict[str, z3.ExprRef]) -> tuple[z3.ArithRef, list]:
        act = z3.Int(f"act@{t}", self.ctx)
        cons: list[Any] = [act >= 0, act < len(self.actions)]
        per_path: dict[str, list[tuple[int, Any]]] = {}
        for i in range(len(self.actions)):
            nxt = self.next_values(i, S)
            en = self.enabled(i, S, nxt)
            cons.append(z3.Implies(act == i, self.as_bool(en)))
            for path, val in nxt.items():
                per_path.setdefault(path, []).append((i, val))
        for path in self.state_paths:
            val: Any = S[path]
            for i, v in reversed(per_path.get(path, [])):
                val = z3.If(act == i, v, val)
            cons.append(S2[path] == val)
        return act, cons

    def prop(self, property_id: str, S: dict[str, z3.ExprRef]) -> Any:
        return self.as_bool(self.expr(self.m.properties[property_id].expr, S, {}))

    def as_bool(self, x: Any) -> z3.BoolRef:
        return z3.BoolVal(x, self.ctx) if isinstance(x, bool) else x

    def solver(self) -> z3.Solver:
        return z3.Solver(ctx=self.ctx)


# ---------------------------------------------------------------------- helpers over mixed python/z3 values


def _not(x: Any) -> Any:
    return (not x) if isinstance(x, bool) else z3.Not(x)


def _and(xs: list[Any]) -> Any:
    if any(x is False for x in xs):
        return False
    rest = [x for x in xs if x is not True]
    return True if not rest else (rest[0] if len(rest) == 1 else z3.And(*rest))


def _or(xs: list[Any]) -> Any:
    if any(x is True for x in xs):
        return True
    rest = [x for x in xs if x is not False]
    return False if not rest else (rest[0] if len(rest) == 1 else z3.Or(*rest))


def _implies(a: Any, b: Any) -> Any:
    return _or([_not(a), b])


def _ite_num(c: Any, a: Any, b: Any) -> Any:
    if isinstance(c, bool):
        return a if c else b
    return z3.If(c, a, b)


def _cmp(a: Any, b: Any, op: str) -> Any:
    """a strictly better than b for max_over (>) / min_over (<), on mixed python/z3 ints."""
    if isinstance(a, int) and isinstance(b, int) and not isinstance(a, bool) and not isinstance(b, bool):
        return a > b if op == "max_over" else a < b
    return (a > b) if op == "max_over" else (a < b)


def _sum(xs: list[Any]) -> Any:
    const = sum(x for x in xs if isinstance(x, int) and not isinstance(x, bool))
    terms = [x for x in xs if not (isinstance(x, int) and not isinstance(x, bool))]
    if not terms:
        return const
    total = z3.Sum(*terms) if len(terms) > 1 else terms[0]
    return total + const if const else total
