"""Human-readable rendering of IR expressions and effects (for UI, ActionSpec and explanations)."""

from __future__ import annotations

from typing import Any

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

_INFIX = {
    "and": " ∧ ", "or": " ∨ ", "implies": " → ",
    "eq": " = ", "ne": " ≠ ", "lt": " < ", "le": " ≤ ", "gt": " > ", "ge": " ≥ ",
    "add": " + ", "sub": " − ", "mul": " × ",
}  # fmt: skip


def expr_text(expr: Any) -> str:
    if isinstance(expr, ConstExpr):
        v = expr.value
        return ("true" if v else "false") if isinstance(v, bool) else str(v)
    if isinstance(expr, RefExpr):
        return expr.name
    if isinstance(expr, VarExpr):
        return f"{expr.name}[{', '.join(expr_text(i) for i in expr.index)}]" if expr.index else expr.name
    if isinstance(expr, QuantExpr):
        sym = {"forall": "∀", "exists": "∃", "count": "#", "sum": "Σ"}[expr.op]
        where = f" | {expr_text(expr.where)}" if expr.where is not None else ""
        return f"{sym}{expr.var} ∈ {expr.domain}{where}: {expr_text(expr.body)}"
    if isinstance(expr, ApplyExpr):
        args = [expr_text(a) for a in expr.args]
        if expr.op == "not":
            return f"¬({args[0]})"
        if expr.op == "neg":
            return f"−({args[0]})"
        if expr.op in ("min", "max"):
            return f"{expr.op}({', '.join(args)})"
        if expr.op == "ite":
            return f"(if {args[0]} then {args[1]} else {args[2]})"
        if len(args) == 1:
            return args[0]
        return "(" + _INFIX[expr.op].join(args) + ")"
    return repr(expr)


def effect_lines(effects: list[Any], indent: str = "") -> list[str]:
    out: list[str] = []
    for eff in effects:
        if isinstance(eff, AssignEffect):
            target = eff.target.var
            if eff.target.index:
                target += f"[{', '.join(expr_text(i) for i in eff.target.index)}]"
            out.append(f"{indent}{target} := {expr_text(eff.value)}")
        elif isinstance(eff, WhenEffect):
            out.append(f"{indent}when {expr_text(eff.condition)}:")
            out.extend(effect_lines(eff.then, indent + "  "))
            if eff.otherwise:
                out.append(f"{indent}otherwise:")
                out.extend(effect_lines(eff.otherwise, indent + "  "))
        elif isinstance(eff, ForallEffect):
            where = f" | {expr_text(eff.where)}" if eff.where is not None else ""
            out.append(f"{indent}for each {eff.var} ∈ {eff.domain}{where}:")
            out.extend(effect_lines(eff.effects, indent + "  "))
    return out
