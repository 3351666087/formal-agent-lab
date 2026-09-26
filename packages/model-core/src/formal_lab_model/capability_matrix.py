"""Capability matrix of the deterministic_finite_v1 profile across engine components.

Single source for docs/architecture/capability-matrix.md and the /api/v1/capabilities endpoint.
Statuses describe what is implemented AND covered by tests in this phase.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Status = Literal["SUPPORTED", "UNSUPPORTED", "PARTIAL"]
COMPONENTS = ("interpreter", "z3_compiler", "ir_world_env", "z3_planner")


class MatrixRow(BaseModel):
    feature: str
    description: str
    status: dict[str, Status]
    unsupported_answer: str | None = None
    extension_point: str | None = None


MATRIX: list[MatrixRow] = [
    MatrixRow(feature="finite_entities", description="finite entity sets and enums as index domains",
              status=dict.fromkeys(COMPONENTS, "SUPPORTED")),
    MatrixRow(feature="bool_enum_bounded_int", description="bool, enum/entity symbols, bounded integers",
              status=dict.fromkeys(COMPONENTS, "SUPPORTED")),
    MatrixRow(feature="pure_expression_ast", description="pure expression AST incl. ∀/∃/count/sum over finite domains",
              status=dict.fromkeys(COMPONENTS, "SUPPORTED")),
    MatrixRow(feature="discrete_logical_steps", description="one grounded action per logical step, explicit order",
              status=dict.fromkeys(COMPONENTS, "SUPPORTED")),
    MatrixRow(feature="deterministic_effects", description="assign / when / forall effects, later write wins, domain guard",
              status=dict.fromkeys(COMPONENTS, "SUPPORTED")),
    MatrixRow(feature="partial_observation",
              description="observations with delayed/unknown facts (environment layer, not model semantics)",
              status={"interpreter": "PARTIAL", "z3_compiler": "PARTIAL", "ir_world_env": "SUPPORTED",
                      "z3_planner": "PARTIAL"},
              unsupported_answer="precondition checks over unknown facts answer UNKNOWN when completions disagree",
              extension_point="Environment.observe + Verifier state/unknown_paths arguments"),
    MatrixRow(feature="dense_time", description="real-valued clocks / continuous time",
              status=dict.fromkeys(COMPONENTS, "UNSUPPORTED"), unsupported_answer="UNSUPPORTED",
              extension_point="new semantic profile + ModelFrontend/Verifier plugins"),
    MatrixRow(feature="concurrent_actions", description="several actions in one logical step",
              status=dict.fromkeys(COMPONENTS, "UNSUPPORTED"), unsupported_answer="UNSUPPORTED",
              extension_point="new semantic profile (e.g. concurrent_finite_v1)"),
    MatrixRow(feature="probabilistic_effects", description="stochastic transitions / probabilities",
              status=dict.fromkeys(COMPONENTS, "UNSUPPORTED"), unsupported_answer="UNSUPPORTED",
              extension_point="new semantic profile + probabilistic Verifier plugin"),
    MatrixRow(feature="unbounded_integers", description="integer state without declared bounds",
              status=dict.fromkeys(COMPONENTS, "UNSUPPORTED"), unsupported_answer="UNSUPPORTED",
              extension_point="new semantic profile"),
]


def matrix_markdown() -> str:
    head = "| feature | " + " | ".join(COMPONENTS) + " | unsupported answer | extension point |"
    sep = "|" + "---|" * (len(COMPONENTS) + 3)
    rows = [
        f"| {r.feature} — {r.description} | " + " | ".join(r.status[c] for c in COMPONENTS)
        + f" | {r.unsupported_answer or ''} | {r.extension_point or ''} |"
        for r in MATRIX
    ]
    return "\n".join([head, sep, *rows]) + "\n"


def main() -> None:
    print("# 能力矩阵：deterministic_finite_v1\n")
    print("由 `python -m formal_lab_model.capability_matrix` 从 formal_lab_model/capability_matrix.py 生成，勿手工编辑。")
    print("状态含义：SUPPORTED = 已实现且有测试；PARTIAL = 在所述范围内实现；UNSUPPORTED = 引擎显式返回 UNSUPPORTED。\n")
    print(matrix_markdown())


if __name__ == "__main__":
    main()
