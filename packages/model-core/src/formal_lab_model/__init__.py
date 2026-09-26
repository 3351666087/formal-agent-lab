"""Finite-state IR engine: static checking, canonical form, digests and the reference interpreter."""

from .checker import CheckedModel, GroundAction, ModelCheckError, ModelIssue, check_model, check_or_raise
from .compare import compare_effects
from .diff import ModelChange, diff_models
from .explore import SearchOutcome, bfs, reachable_states
from .frontend import IRJsonFrontend, build_package, canonical_ir, canonical_text, ir_digest, parse_ir
from .interpreter import Interpreter, State, StepResult
from .pretty import effect_lines, expr_text
from .specs import action_specs

__all__ = [
    "CheckedModel",
    "GroundAction",
    "IRJsonFrontend",
    "Interpreter",
    "ModelChange",
    "ModelCheckError",
    "ModelIssue",
    "SearchOutcome",
    "State",
    "StepResult",
    "action_specs",
    "bfs",
    "build_package",
    "canonical_ir",
    "canonical_text",
    "check_model",
    "check_or_raise",
    "compare_effects",
    "diff_models",
    "effect_lines",
    "expr_text",
    "ir_digest",
    "parse_ir",
    "reachable_states",
]
