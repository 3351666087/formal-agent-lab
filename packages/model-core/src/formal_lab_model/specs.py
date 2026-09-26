"""Derive contract ActionSpecs from a checked model."""

from __future__ import annotations

from typing import Any

from formal_lab_contracts import ActionSpec

from .checker import CheckedModel, TBool, TInt, TSym
from .pretty import effect_lines, expr_text


def _param_schema(model: CheckedModel, ty) -> dict[str, Any]:
    if isinstance(ty, TBool):
        return {"type": "boolean"}
    if isinstance(ty, TInt):
        return {"type": "integer", "minimum": ty.lo, "maximum": ty.hi}
    assert isinstance(ty, TSym)
    return {"type": "string", "enum": list(model.domains[ty.domain]), "x-domain": ty.domain}


def action_specs(model: CheckedModel) -> list[ActionSpec]:
    from .checker import _Checker  # local: reuse type resolution without re-checking

    resolver = _Checker(model.ir)
    resolver.domains, resolver.domain_kind = model.domains, model.domain_kind
    specs = []
    for act in model.ir.actions:
        props = {p.name: _param_schema(model, resolver.resolve_type(p.type, "")) for p in act.params}
        specs.append(
            ActionSpec(
                action_type=act.name,
                label=act.label,
                description=act.description,
                params_schema={"type": "object", "properties": props, "required": list(props),
                               "additionalProperties": False},
                preconditions=[expr_text(act.precondition)],
                precondition_expr=act.precondition,
                expected_effects=effect_lines(act.effects),
                effects=act.effects,
                cost=float(act.cost),
                timeout_seconds=act.timeout_seconds,
                retry=act.retry,
            )
        )
    return specs
