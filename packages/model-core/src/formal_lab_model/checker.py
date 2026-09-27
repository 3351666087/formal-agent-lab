"""Static checking of deterministic_finite_v1 models.

`check_model` resolves names, checks types and value tables, grounds actions and returns a
`CheckedModel` (symbol tables only — evaluation semantics live in the interpreter and, independently,
in the Z3 compiler). All problems are collected as `ModelIssue`s with a JSON-pointer-like location.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Any

from formal_lab_contracts import DETERMINISTIC_FINITE_V1, ModelIR, StateScalar, state_path
from formal_lab_contracts.capabilities import UNSUPPORTED_FEATURES_V1
from formal_lab_contracts.ir import (
    ActionDecl,
    ApplyExpr,
    AssignEffect,
    BoolType,
    ConstExpr,
    EnumType,
    ForallEffect,
    IntType,
    QuantExpr,
    RefExpr,
    TypeRef,
    ValueTable,
    VarExpr,
    WhenEffect,
)
from pydantic import BaseModel, Field

MAX_GROUND_ACTIONS = 20_000
MAX_LOCATIONS = 200_000

# ------------------------------------------------------------------ internal types


@dataclass(frozen=True)
class TBool:
    def __str__(self) -> str:
        return "bool"


@dataclass(frozen=True)
class TInt:
    lo: int | None = None  # None = unbounded (intermediate arithmetic)
    hi: int | None = None

    def __str__(self) -> str:
        return "int" if self.lo is None else f"int[{self.lo}..{self.hi}]"


@dataclass(frozen=True)
class TSym:
    domain: str

    def __str__(self) -> str:
        return self.domain


Ty = TBool | TInt | TSym


def same_kind(a: Ty, b: Ty) -> bool:
    if isinstance(a, TInt) and isinstance(b, TInt):
        return True
    return a == b


class ModelIssue(BaseModel):
    path: str
    code: str
    message: str
    severity: str = Field(default="error")


# ------------------------------------------------------------------ checked model


@dataclass
class LocationFamily:
    name: str
    ty: Ty
    index: tuple[str, ...]  # domain names
    is_state: bool
    table: dict[str, StateScalar]  # path -> value (initial for state, value for constants)
    observable: bool = True

    def paths(self) -> list[str]:
        return list(self.table)


@dataclass(frozen=True)
class GroundAction:
    action: str
    params: tuple[tuple[str, StateScalar], ...]

    @property
    def key(self) -> str:
        inner = ",".join(f"{k}={v}" for k, v in self.params)
        return f"{self.action}({inner})"

    def params_dict(self) -> dict[str, StateScalar]:
        return dict(self.params)


@dataclass
class CheckedModel:
    ir: ModelIR
    domains: dict[str, list[str]]  # enum / entity set name -> members
    domain_kind: dict[str, str]  # name -> "enum" | "entity"
    families: dict[str, LocationFamily]  # constants and state variables
    actions: dict[str, ActionDecl]
    ground_actions: list[GroundAction]
    properties: dict[str, Any]
    issues: list[ModelIssue] = field(default_factory=list)
    objectives: dict[str, Any] = field(default_factory=dict)  # id → ObjectiveDecl (v2)

    @property
    def state_families(self) -> list[LocationFamily]:
        return [f for f in self.families.values() if f.is_state]

    def initial_state(self) -> dict[str, StateScalar]:
        state: dict[str, StateScalar] = {}
        for fam in self.state_families:
            state.update(fam.table)
        return state

    def location_type(self, path: str) -> Ty:
        name = path.split("[", 1)[0]
        return self.families[name].ty

    def state_paths(self) -> list[str]:
        return [p for fam in self.state_families for p in fam.table]

    def param_domain(self, ty: Ty) -> list[StateScalar]:
        if isinstance(ty, TBool):
            return [False, True]
        if isinstance(ty, TInt):
            assert ty.lo is not None and ty.hi is not None
            return list(range(ty.lo, ty.hi + 1))
        return list(self.domains[ty.domain])


class ModelCheckError(Exception):
    def __init__(self, issues: list[ModelIssue]):
        super().__init__("; ".join(f"{i.path}: {i.message}" for i in issues[:5]))
        self.issues = issues


# ------------------------------------------------------------------ checker


class _Checker:
    def __init__(self, ir: ModelIR):
        self.ir = ir
        self.issues: list[ModelIssue] = []
        self.domains: dict[str, list[str]] = {}
        self.domain_kind: dict[str, str] = {}
        self.symbol_domains: dict[str, list[str]] = {}
        self.families: dict[str, LocationFamily] = {}

    def err(self, path: str, code: str, message: str) -> None:
        self.issues.append(ModelIssue(path=path, code=code, message=message))

    # -------------------------------------------------------------- declarations
    def run(self) -> CheckedModel:
        ir = self.ir
        if ir.semantic_profile != DETERMINISTIC_FINITE_V1:
            self.err("/semantic_profile", "UNSUPPORTED_PROFILE",
                     f"semantic profile {ir.semantic_profile!r} is not supported (only {DETERMINISTIC_FINITE_V1})")
        for feat in ir.features:
            code = "UNSUPPORTED_FEATURE" if feat in UNSUPPORTED_FEATURES_V1 else "UNKNOWN_FEATURE"
            self.err("/features", code, f"feature {feat!r} is outside {DETERMINISTIC_FINITE_V1}")

        top_names: dict[str, str] = {}

        def claim(name: str, where: str) -> None:
            if name in top_names:
                self.err(where, "DUPLICATE_NAME", f"name {name!r} already declared at {top_names[name]}")
            else:
                top_names[name] = where

        for i, enum in enumerate(ir.enums):
            claim(enum.name, f"/enums/{i}")
            self._domain(enum.name, enum.values, "enum", f"/enums/{i}")
        for i, es in enumerate(ir.entity_sets):
            claim(es.name, f"/entity_sets/{i}")
            self._domain(es.name, es.members, "entity", f"/entity_sets/{i}")

        for i, const in enumerate(ir.constants):
            where = f"/constants/{i}"
            claim(const.name, where)
            ty = self.resolve_type(const.type, f"{where}/type")
            idx = self._index(const.index, f"{where}/index")
            table = self._table(const.name, ty, idx, const.value, f"{where}/value") if ty and idx is not None else {}
            if ty is not None:
                self.families[const.name] = LocationFamily(const.name, ty, tuple(const.index), False, table)
        for i, var in enumerate(ir.state):
            where = f"/state/{i}"
            claim(var.name, where)
            ty = self.resolve_type(var.type, f"{where}/type")
            idx = self._index(var.index, f"{where}/index")
            table = self._table(var.name, ty, idx, var.initial, f"{where}/initial") if ty and idx is not None else {}
            if ty is not None:
                self.families[var.name] = LocationFamily(var.name, ty, tuple(var.index), True, table, var.observable)

        n_locations = sum(len(f.table) for f in self.families.values())
        if n_locations > MAX_LOCATIONS:
            self.err("/state", "TOO_LARGE", f"{n_locations} locations exceed the limit {MAX_LOCATIONS}")

        actions: dict[str, ActionDecl] = {}
        ground: list[GroundAction] = []
        for i, act in enumerate(ir.actions):
            where = f"/actions/{i}"
            claim(act.name, where)
            actions[act.name] = act
            scope: dict[str, Ty] = {}
            domains: list[tuple[str, list[StateScalar]]] = []
            for j, p in enumerate(act.params):
                pty = self.resolve_type(p.type, f"{where}/params/{j}/type")
                if p.name in scope:
                    self.err(f"{where}/params/{j}", "DUPLICATE_PARAM", f"parameter {p.name!r} repeated")
                if pty is not None:
                    scope[p.name] = pty
                    domains.append((p.name, self._param_values(pty)))
            self.expect(act.precondition, TBool(), scope, f"{where}/precondition")
            self.check_effects(act.effects, scope, f"{where}/effects")
            for combo in itertools.product(*[vals for _, vals in domains]):
                ground.append(GroundAction(act.name, tuple(zip([n for n, _ in domains], combo, strict=True))))
        if len(ground) > MAX_GROUND_ACTIONS:
            self.err("/actions", "TOO_LARGE", f"{len(ground)} ground actions exceed the limit {MAX_GROUND_ACTIONS}")

        props: dict[str, Any] = {}
        for i, prop in enumerate(ir.properties):
            where = f"/properties/{i}"
            if prop.id in props:
                self.err(where, "DUPLICATE_PROPERTY", f"property {prop.id!r} repeated")
            props[prop.id] = prop
            self.expect(prop.expr, TBool(), {}, f"{where}/expr")

        objectives: dict[str, Any] = {}
        for i, obj in enumerate(ir.objectives):
            where = f"/objectives/{i}"
            if obj.id in objectives:
                self.err(where, "DUPLICATE_OBJECTIVE", f"objective {obj.id!r} repeated")
            objectives[obj.id] = obj
            for j, term in enumerate(obj.terms):
                if term.expr is not None:
                    self.expect(term.expr, TInt(), {}, f"{where}/terms/{j}/expr")

        return CheckedModel(ir=ir, domains=self.domains, domain_kind=self.domain_kind, families=self.families,
                            actions=actions, ground_actions=ground, properties=props, issues=self.issues,
                            objectives=objectives)

    def _domain(self, name: str, members: list[str], kind: str, where: str) -> None:
        if len(set(members)) != len(members):
            self.err(where, "DUPLICATE_MEMBER", f"{kind} {name!r} lists a member twice")
        self.domains[name] = list(members)
        self.domain_kind[name] = kind
        for m in members:
            self.symbol_domains.setdefault(m, []).append(name)

    def resolve_type(self, t: TypeRef, where: str) -> Ty | None:
        if isinstance(t, BoolType):
            return TBool()
        if isinstance(t, IntType):
            return TInt(t.min, t.max)
        name = t.name if isinstance(t, EnumType) else t.set
        want = "enum" if isinstance(t, EnumType) else "entity"
        if self.domain_kind.get(name) != want:
            self.err(where, "UNKNOWN_TYPE", f"{want} {name!r} is not declared")
            return None
        return TSym(name)

    def _index(self, index: list[str], where: str) -> list[list[str]] | None:
        out = []
        for k, name in enumerate(index):
            if name not in self.domains:
                self.err(f"{where}/{k}", "UNKNOWN_DOMAIN", f"index domain {name!r} is not declared")
                return None
            out.append(self.domains[name])
        return out

    def _value_ok(self, ty: Ty, value: StateScalar) -> bool:
        if isinstance(ty, TBool):
            return isinstance(value, bool)
        if isinstance(ty, TInt):
            return isinstance(value, int) and not isinstance(value, bool) and ty.lo <= value <= ty.hi  # type: ignore[operator]
        return isinstance(value, str) and value in self.domains[ty.domain]

    def _table(self, name: str, ty: Ty, idx: list[list[str]], vt: ValueTable, where: str) -> dict[str, StateScalar]:
        table: dict[str, StateScalar] = {}
        cells = {tuple(c.index): (k, c.value) for k, c in enumerate(vt.cells)}
        if len(cells) != len(vt.cells):
            self.err(f"{where}/cells", "DUPLICATE_CELL", "a cell index is listed twice")
        valid_keys = set(itertools.product(*idx))
        for key, (k, value) in cells.items():
            if key not in valid_keys:
                self.err(f"{where}/cells/{k}", "BAD_INDEX", f"cell index {list(key)} is not in the index domains")
            elif not self._value_ok(ty, value):
                self.err(f"{where}/cells/{k}", "BAD_VALUE", f"value {value!r} is not a {ty}")
        if vt.default is not None and not self._value_ok(ty, vt.default):
            self.err(f"{where}/default", "BAD_VALUE", f"default {vt.default!r} is not a {ty}")
        for key in itertools.product(*idx):
            if key in cells:
                table[state_path(name, key)] = cells[key][1]
            elif vt.default is not None:
                table[state_path(name, key)] = vt.default
            else:
                self.err(where, "INCOMPLETE_TABLE", f"no value for {state_path(name, key)} and no default")
                return table
        return table

    def _param_values(self, ty: Ty) -> list[StateScalar]:
        if isinstance(ty, TBool):
            return [False, True]
        if isinstance(ty, TInt):
            return list(range(ty.lo, ty.hi + 1))  # type: ignore[arg-type]
        return list(self.domains[ty.domain])

    # -------------------------------------------------------------- expressions
    def expect(self, expr: Any, want: Ty, scope: dict[str, Ty], where: str) -> None:
        got = self.infer(expr, scope, where, hint=want)
        if got is not None and not same_kind(got, want):
            self.err(where, "TYPE_MISMATCH", f"expected {want}, got {got}")

    def infer(self, expr: Any, scope: dict[str, Ty], where: str, hint: Ty | None = None) -> Ty | None:
        if isinstance(expr, ConstExpr):
            v = expr.value
            if isinstance(v, bool):
                return TBool()
            if isinstance(v, int):
                return TInt()
            if expr.domain:
                if v not in self.domains.get(expr.domain, []):
                    self.err(where, "UNKNOWN_SYMBOL", f"{v!r} is not a member of {expr.domain!r}")
                    return None
                return TSym(expr.domain)
            if isinstance(hint, TSym) and v in self.domains[hint.domain]:
                return hint
            owners = self.symbol_domains.get(v, [])
            if len(owners) == 1:
                return TSym(owners[0])
            self.err(where, "AMBIGUOUS_SYMBOL" if owners else "UNKNOWN_SYMBOL",
                     f"symbol {v!r} " + (f"belongs to {owners}; set `domain`" if owners else "is not declared"))
            return None
        if isinstance(expr, RefExpr):
            if expr.name not in scope:
                self.err(where, "UNBOUND", f"{expr.name!r} is not a parameter or bound variable here")
                return None
            return scope[expr.name]
        if isinstance(expr, VarExpr):
            fam = self.families.get(expr.name)
            if fam is None:
                self.err(where, "UNKNOWN_VARIABLE", f"{expr.name!r} is not a state variable or constant")
                return None
            if len(expr.index) != len(fam.index):
                self.err(where, "BAD_ARITY", f"{expr.name} takes {len(fam.index)} index argument(s), got {len(expr.index)}")
                return fam.ty
            for k, (sub, dom) in enumerate(zip(expr.index, fam.index, strict=True)):
                self.expect(sub, TSym(dom), scope, f"{where}/index/{k}")
            return fam.ty
        if isinstance(expr, QuantExpr):
            if expr.domain not in self.domains:
                self.err(where, "UNKNOWN_DOMAIN", f"quantifier domain {expr.domain!r} is not declared")
                return None
            inner = {**scope, expr.var: TSym(expr.domain)}
            if expr.where is not None:
                self.expect(expr.where, TBool(), inner, f"{where}/where")
            numeric_body = expr.op in ("sum", "max_over", "min_over")
            self.expect(expr.body, TInt() if numeric_body else TBool(), inner, f"{where}/body")
            if expr.default is not None:
                self.expect(expr.default, TInt(), scope, f"{where}/default")
            return TInt() if expr.op in ("count", "sum", "max_over", "min_over") else TBool()
        if isinstance(expr, ApplyExpr):
            return self._apply(expr, scope, where)
        self.err(where, "BAD_EXPR", f"unrecognised expression {expr!r}")
        return None

    def _apply(self, e: ApplyExpr, scope: dict[str, Ty], where: str) -> Ty | None:
        op, args = e.op, e.args

        def arity(n: int | None = None, at_least: int | None = None) -> bool:
            if (n is not None and len(args) != n) or (at_least is not None and len(args) < at_least):
                self.err(where, "BAD_ARITY", f"{op} expects {n if n is not None else f'>= {at_least}'} args, got {len(args)}")
                return False
            return True

        if op in ("not",):
            if arity(1):
                self.expect(args[0], TBool(), scope, f"{where}/args/0")
            return TBool()
        if op in ("and", "or"):
            if arity(at_least=1):
                for k, a in enumerate(args):
                    self.expect(a, TBool(), scope, f"{where}/args/{k}")
            return TBool()
        if op == "implies":
            if arity(2):
                for k, a in enumerate(args):
                    self.expect(a, TBool(), scope, f"{where}/args/{k}")
            return TBool()
        if op in ("eq", "ne"):
            if arity(2):
                left = self.infer(args[0], scope, f"{where}/args/0")
                right = self.infer(args[1], scope, f"{where}/args/1", hint=left)
                if left is None and right is not None:
                    left = self.infer(args[0], scope, f"{where}/args/0", hint=right)
                if left is not None and right is not None and not same_kind(left, right):
                    self.err(where, "TYPE_MISMATCH", f"cannot compare {left} with {right}")
            return TBool()
        if op in ("lt", "le", "gt", "ge"):
            if arity(2):
                for k, a in enumerate(args):
                    self.expect(a, TInt(), scope, f"{where}/args/{k}")
            return TBool()
        if op in ("add", "mul", "min", "max", "sub"):
            if arity(at_least=1):
                for k, a in enumerate(args):
                    self.expect(a, TInt(), scope, f"{where}/args/{k}")
            return TInt()
        if op == "neg":
            if arity(1):
                self.expect(args[0], TInt(), scope, f"{where}/args/0")
            return TInt()
        if op == "ite":
            if not arity(3):
                return None
            self.expect(args[0], TBool(), scope, f"{where}/args/0")
            t1 = self.infer(args[1], scope, f"{where}/args/1")
            t2 = self.infer(args[2], scope, f"{where}/args/2", hint=t1)
            if t1 is not None and t2 is not None and not same_kind(t1, t2):
                self.err(where, "TYPE_MISMATCH", f"ite branches differ: {t1} vs {t2}")
            return t1 if not isinstance(t1, TInt) else TInt()
        self.err(where, "UNKNOWN_OP", f"unknown operator {op!r}")
        return None

    # -------------------------------------------------------------- effects
    def check_effects(self, effects: list[Any], scope: dict[str, Ty], where: str) -> None:
        for k, eff in enumerate(effects):
            here = f"{where}/{k}"
            if isinstance(eff, AssignEffect):
                fam = self.families.get(eff.target.var)
                if fam is None:
                    self.err(f"{here}/target", "UNKNOWN_VARIABLE", f"{eff.target.var!r} is not declared")
                    continue
                if not fam.is_state:
                    self.err(f"{here}/target", "ASSIGN_TO_CONSTANT", f"{eff.target.var!r} is a constant")
                if len(eff.target.index) != len(fam.index):
                    self.err(f"{here}/target", "BAD_ARITY", f"{fam.name} takes {len(fam.index)} index argument(s)")
                else:
                    for j, (sub, dom) in enumerate(zip(eff.target.index, fam.index, strict=True)):
                        self.expect(sub, TSym(dom), scope, f"{here}/target/index/{j}")
                self.expect(eff.value, fam.ty, scope, f"{here}/value")
            elif isinstance(eff, WhenEffect):
                self.expect(eff.condition, TBool(), scope, f"{here}/condition")
                self.check_effects(eff.then, scope, f"{here}/then")
                self.check_effects(eff.otherwise, scope, f"{here}/otherwise")
            elif isinstance(eff, ForallEffect):
                if eff.domain not in self.domains:
                    self.err(here, "UNKNOWN_DOMAIN", f"domain {eff.domain!r} is not declared")
                    continue
                inner = {**scope, eff.var: TSym(eff.domain)}
                if eff.where is not None:
                    self.expect(eff.where, TBool(), inner, f"{here}/where")
                self.check_effects(eff.effects, inner, f"{here}/effects")


def check_model(ir: ModelIR) -> CheckedModel:
    """Check a model; the result carries `issues` (empty when the model is well-formed)."""
    return _Checker(ir).run()


def check_or_raise(ir: ModelIR) -> CheckedModel:
    checked = check_model(ir)
    if checked.issues:
        raise ModelCheckError(checked.issues)
    return checked


def check_expression(model: CheckedModel, expr: Any, *, expected: str = "bool", params: dict[str, Any] | None = None,
                     extra_domains: dict[str, list[str]] | None = None, where: str = "") -> list[ModelIssue]:
    """Type-check an expression against a checked model (used for rule conditions and objective terms).

    `params` maps a ref name to "bool" | "int" | a domain name (possibly one of `extra_domains`, symbolic values
    that exist only in the evaluation context, e.g. comparison verdicts)."""
    checker = _Checker(model.ir)
    checker.domains = {**model.domains, **(extra_domains or {})}
    checker.domain_kind = {**model.domain_kind, **{d: "enum" for d in (extra_domains or {})}}
    checker.families = model.families
    checker.symbol_domains = {}
    for d, members in checker.domains.items():
        for m in members:
            checker.symbol_domains.setdefault(m, []).append(d)
    scope: dict[str, Ty] = {}
    for name, ty in (params or {}).items():
        scope[name] = TBool() if ty == "bool" else TInt() if ty == "int" else TSym(ty)
    want = TBool() if expected == "bool" else TInt()
    checker.expect(expr, want, scope, where)
    return checker.issues
