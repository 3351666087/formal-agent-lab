"""formal-lab-contracts/v2 — the single source of truth for platform contracts.

The frozen v1 contract lives in `formal_lab_contracts.v1`; `formal_lab_contracts.compat` upgrades v1 JSON to v2.
"""

from . import capabilities, compat, errors, execution, governance, interfaces, ir, kernel
from . import objects as _objects
from .common import (
    CONTRACT_VERSION,
    CONTRACT_VERSION_V1,
    SUPPORTED_CONTRACT_VERSIONS,
    ArtifactRef,
    ContractModel,
    Digest,
    EvidenceRef,
    Extension,
    PluginRef,
    StateScalar,
    canonical_json,
    digest_of,
    parse_state_path,
    state_path,
    utcnow,
)
from .errors import ErrorCode, ErrorInfo, FormalLabError
from .execution import *  # noqa: F403
from .governance import *  # noqa: F403
from .governance import RULE_CONTEXT_PARAMS
from .ir import DETERMINISTIC_FINITE_V1, CostTerm, ModelIR, ObjectiveDecl, canonical_ir_dump
from .kernel import *  # noqa: F403
from .kernel import OPERATION_TRANSITIONS
from .objects import *  # noqa: F403
from .objects import (
    INTERFACE_VERSION,
    QUERY_SEMANTICS,
    SUPPORTED_INTERFACE_VERSIONS,
    TERMINAL_RUN_STATUSES,
    VERDICTS_BY_KIND,
)


def _public(module) -> list[str]:
    return [name for name, value in vars(module).items()
            if isinstance(value, type) and getattr(value, "__module__", "") == module.__name__]


__all__ = [
    "CONTRACT_VERSION",
    "CONTRACT_VERSION_V1",
    "DETERMINISTIC_FINITE_V1",
    "SUPPORTED_CONTRACT_VERSIONS",
    "ArtifactRef",
    "ContractModel",
    "CostTerm",
    "Digest",
    "ErrorCode",
    "ErrorInfo",
    "EvidenceRef",
    "Extension",
    "FormalLabError",
    "ModelIR",
    "ObjectiveDecl",
    "PluginRef",
    "StateScalar",
    "canonical_ir_dump",
    "canonical_json",
    "capabilities",
    "compat",
    "digest_of",
    "errors",
    "execution",
    "governance",
    "interfaces",
    "ir",
    "kernel",
    "parse_state_path",
    "state_path",
    "utcnow",
    "QUERY_SEMANTICS",
    "VERDICTS_BY_KIND",
    "TERMINAL_RUN_STATUSES",
    "INTERFACE_VERSION",
    "SUPPORTED_INTERFACE_VERSIONS",
    "OPERATION_TRANSITIONS",
    "RULE_CONTEXT_PARAMS",
    *_public(_objects), *_public(kernel), *_public(execution), *_public(governance),
]
