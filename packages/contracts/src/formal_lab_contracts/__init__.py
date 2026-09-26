"""formal-lab-contracts/v1 — the single source of truth for platform contracts."""

from . import capabilities, errors, interfaces, ir
from .common import (
    CONTRACT_VERSION,
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
from .ir import DETERMINISTIC_FINITE_V1, ModelIR
from . import objects as _objects
from .objects import *  # noqa: F403

__all__ = [
    "CONTRACT_VERSION",
    "DETERMINISTIC_FINITE_V1",
    "ArtifactRef",
    "ContractModel",
    "Digest",
    "ErrorCode",
    "ErrorInfo",
    "EvidenceRef",
    "Extension",
    "FormalLabError",
    "ModelIR",
    "PluginRef",
    "StateScalar",
    "canonical_json",
    "capabilities",
    "digest_of",
    "errors",
    "interfaces",
    "ir",
    "parse_state_path",
    "state_path",
    "utcnow",
] + [
    name
    for name, value in vars(_objects).items()
    if isinstance(value, type) and getattr(value, "__module__", "") == _objects.__name__
]
