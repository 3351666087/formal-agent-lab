"""Neutral finite-state IR, semantic profile `deterministic_finite_v1`.

A model is a finite set of typed state locations (optionally indexed by finite entity sets),
immutable constants, parameterised actions with a pure precondition and deterministic effects,
and named properties (goals / invariants). Expressions are a pure JSON AST.

Normative semantics (implemented independently by the reference interpreter and the Z3 compiler):
- One grounded action per logical step; actions are grounded over their finite parameter domains.
- All expressions of an action are evaluated in the pre-state. Effects are collected in declaration
  order; a later write to the same location overrides an earlier one.
- An action is applicable iff its precondition holds AND every written integer value lies in the
  declared range of its location (implicit domain guard).
- Integer arithmetic is unbounded inside expressions; only stored values are range-checked.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .common import ContractModel, Name, StateScalar

DETERMINISTIC_FINITE_V1 = "deterministic_finite_v1"

# --------------------------------------------------------------------------- types


class BoolType(ContractModel):
    kind: Literal["bool"] = "bool"


class IntType(ContractModel):
    kind: Literal["int"] = "int"
    min: int
    max: int

    @model_validator(mode="after")
    def _range(self) -> IntType:
        if self.min > self.max:
            raise ValueError(f"empty integer range [{self.min}, {self.max}]")
        return self


class EnumType(ContractModel):
    kind: Literal["enum"] = "enum"
    name: Name = Field(description="name of a declared enum")


class EntityType(ContractModel):
    kind: Literal["entity"] = "entity"
    set: Name = Field(description="name of a declared entity set")


TypeRef = Annotated[BoolType | IntType | EnumType | EntityType, Field(discriminator="kind")]

# --------------------------------------------------------------------------- expressions

APPLY_OPS = (
    "not", "and", "or", "implies",
    "eq", "ne", "lt", "le", "gt", "ge",
    "add", "sub", "mul", "neg", "min", "max",
    "ite",
)  # fmt: skip
ApplyOp = Literal[
    "not", "and", "or", "implies",
    "eq", "ne", "lt", "le", "gt", "ge",
    "add", "sub", "mul", "neg", "min", "max",
    "ite",
]  # fmt: skip
QuantOp = Literal["forall", "exists", "count", "sum"]


class ConstExpr(ContractModel):
    op: Literal["const"] = "const"
    value: StateScalar
    domain: Name | None = Field(
        default=None, description="enum or entity set of a symbolic value; required when ambiguous"
    )


class VarExpr(ContractModel):
    """Reads a state variable or a constant table at the given index."""

    op: Literal["var"] = "var"
    name: Name
    index: list[Expr] = Field(default_factory=list)


class RefExpr(ContractModel):
    """Reads an action parameter or a quantifier-bound variable."""

    op: Literal["ref"] = "ref"
    name: Name


class ApplyExpr(ContractModel):
    op: ApplyOp
    args: list[Expr] = Field(min_length=1)


class QuantExpr(ContractModel):
    """forall/exists → bool, count → number of satisfying members, sum → sum of an int body."""

    op: QuantOp
    var: Name
    domain: Name = Field(description="entity set or enum to range over")
    where: Expr | None = None
    body: Expr


Expr = Annotated[ConstExpr | VarExpr | RefExpr | ApplyExpr | QuantExpr, Field(discriminator="op")]

# --------------------------------------------------------------------------- effects


class AssignTarget(ContractModel):
    var: Name
    index: list[Expr] = Field(default_factory=list)


class AssignEffect(ContractModel):
    kind: Literal["assign"] = "assign"
    target: AssignTarget
    value: Expr


class WhenEffect(ContractModel):
    kind: Literal["when"] = "when"
    condition: Expr
    then: list[Effect] = Field(default_factory=list)
    otherwise: list[Effect] = Field(default_factory=list)


class ForallEffect(ContractModel):
    kind: Literal["forall"] = "forall"
    var: Name
    domain: Name
    where: Expr | None = None
    effects: list[Effect] = Field(min_length=1)


Effect = Annotated[AssignEffect | WhenEffect | ForallEffect, Field(discriminator="kind")]

# --------------------------------------------------------------------------- declarations


class EnumDecl(ContractModel):
    name: Name
    values: list[Name] = Field(min_length=1)
    description: str | None = None


class EntitySetDecl(ContractModel):
    name: Name
    members: list[Name] = Field(min_length=1)
    label: str | None = None
    description: str | None = None


class CellValue(ContractModel):
    index: list[Name]
    value: StateScalar


class ValueTable(ContractModel):
    """Values of an indexed location family: `default` everywhere, overridden by `cells`."""

    default: StateScalar | None = None
    cells: list[CellValue] = Field(default_factory=list)


class ConstantDecl(ContractModel):
    name: Name
    type: TypeRef
    index: list[Name] = Field(default_factory=list, description="entity sets / enums indexing the table")
    value: ValueTable
    description: str | None = None


class StateVarDecl(ContractModel):
    name: Name
    type: TypeRef
    index: list[Name] = Field(default_factory=list)
    initial: ValueTable
    label: str | None = None
    description: str | None = None
    observable: bool = Field(default=True, description="false: never revealed to agents directly")


class ParamDecl(ContractModel):
    name: Name
    type: TypeRef


class ActionDecl(ContractModel):
    name: Name
    params: list[ParamDecl] = Field(default_factory=list)
    precondition: Expr = Field(default_factory=lambda: ConstExpr(value=True))
    effects: list[Effect] = Field(default_factory=list)
    cost: int = Field(default=1, ge=0)
    label: str | None = None
    description: str | None = None
    timeout_seconds: float = Field(default=30.0, gt=0)
    retry: Literal["IDEMPOTENT", "RECONCILE_THEN_RETRY", "NOT_RETRYABLE"] = "RECONCILE_THEN_RETRY"


class PropertyDecl(ContractModel):
    id: Name
    kind: Literal["goal", "invariant"]
    expr: Expr
    label: str | None = None
    description: str | None = None


class ModelIR(ContractModel):
    semantic_profile: str = Field(default=DETERMINISTIC_FINITE_V1)
    name: str = Field(min_length=1)
    description: str | None = None
    enums: list[EnumDecl] = Field(default_factory=list)
    entity_sets: list[EntitySetDecl] = Field(default_factory=list)
    constants: list[ConstantDecl] = Field(default_factory=list)
    state: list[StateVarDecl] = Field(min_length=1)
    actions: list[ActionDecl] = Field(min_length=1)
    properties: list[PropertyDecl] = Field(default_factory=list)
    features: list[str] = Field(
        default_factory=list,
        description="semantic features the model relies on beyond the profile (e.g. 'probabilistic_effects');"
        " unsupported features make engines answer UNSUPPORTED",
    )


for _model in (VarExpr, ApplyExpr, QuantExpr, AssignTarget, AssignEffect, WhenEffect, ForallEffect):
    _model.model_rebuild()
