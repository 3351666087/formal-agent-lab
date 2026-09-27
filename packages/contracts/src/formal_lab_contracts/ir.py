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

Additions in formal-lab-contracts/v2 (same profile, backward compatible — a v1 model is a valid v2 model with the
same canonical form and digest, because fields introduced in v2 are left out of the canonical form while they hold
their default):
- quantifiers `max_over` / `min_over`: largest / smallest int `body` over the members that satisfy `where`;
  `default` is the value when no member qualifies (required whenever `where` is given).
- `ModelIR.objectives`: named cost objectives (see `ObjectiveDecl`) that scenarios and planners refer to by id.
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
QuantOp = Literal["forall", "exists", "count", "sum", "max_over", "min_over"]
V2_QUANT_OPS = ("max_over", "min_over")


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
    """forall/exists → bool, count → number of satisfying members, sum → sum of an int body,
    max_over/min_over → largest/smallest int body over the satisfying members (`default` when there is none)."""

    op: QuantOp
    var: Name
    domain: Name = Field(description="entity set or enum to range over")
    where: Expr | None = None
    body: Expr
    default: Expr | None = Field(default=None, description="max_over/min_over only: value when no member qualifies")

    @model_validator(mode="after")
    def _default_only_for_extrema(self) -> QuantExpr:
        if self.default is not None and self.op not in V2_QUANT_OPS:
            raise ValueError(f"`default` is only meaningful for {V2_QUANT_OPS}, not {self.op!r}")
        if self.op in V2_QUANT_OPS and self.where is not None and self.default is None:
            raise ValueError(f"{self.op} with `where` needs a `default` for the empty case")
        return self


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


class CostTerm(ContractModel):
    """One additive cost term of an objective level.

    - action_cost: `weight` × the declared `cost` of every action taken on the path.
    - state_rate: `weight` × `expr` (int) evaluated on every post-state s_1..s_k of the path.
    - terminal: `weight` × `expr` (int) evaluated on the final state s_k of the path.
    """

    kind: Literal["action_cost", "state_rate", "terminal"]
    expr: Expr | None = None
    weight: int = 1
    label: str | None = None

    @model_validator(mode="after")
    def _expr_shape(self) -> CostTerm:
        if self.kind == "action_cost" and self.expr is not None:
            raise ValueError("action_cost terms take no expr (they use ActionDecl.cost)")
        if self.kind != "action_cost" and self.expr is None:
            raise ValueError(f"{self.kind} terms need an int expr")
        return self


class ObjectiveDecl(ContractModel):
    """A named cost objective declared by the model: the sum of its terms over a path."""

    id: Name
    label: str | None = None
    unit: str = "cost"
    direction: Literal["minimize", "maximize"] = "minimize"
    terms: list[CostTerm] = Field(min_length=1)
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
    objectives: list[ObjectiveDecl] = Field(default_factory=list, description="named cost objectives (v2)")


# fields introduced by formal-lab-contracts/v2 inside the IR: omitted from the canonical form at their default
V2_IR_DEFAULTS = {"ModelIR.objectives": [], "QuantExpr.default": None}


for _model in (VarExpr, ApplyExpr, QuantExpr, AssignTarget, AssignEffect, WhenEffect, ForallEffect, CostTerm,
               ObjectiveDecl):
    _model.model_rebuild()


_QUANT_OPS = ("forall", "exists", "count", "sum", "max_over", "min_over")


def canonical_ir_dump(ir: ModelIR) -> dict:
    """Canonical JSON form of a model (the input of its digest).

    Every v1 field is explicit (defaults filled); list order is semantic and preserved; key order is irrelevant
    because digests use sorted-key canonical JSON. Fields introduced in v2 (`V2_IR_DEFAULTS`) are left out while
    they hold their default, so a phase-1 model keeps its phase-1 digest.
    """
    data = ir.model_dump(mode="json")
    if data.get("objectives") == []:
        data.pop("objectives")

    def strip(node):
        if isinstance(node, dict):
            if node.get("op") in _QUANT_OPS and "body" in node and node.get("default", 0) is None:
                node.pop("default")
            for value in node.values():
                strip(value)
        elif isinstance(node, list):
            for value in node:
                strip(value)

    strip(data)
    return data
