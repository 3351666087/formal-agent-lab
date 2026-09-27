"""formal-lab-contracts/v1 error data model (frozen copy; exceptions live in formal_lab_contracts.errors)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field

from .common import ContractModel


class ErrorCode(StrEnum):
    INVALID_INPUT = "INVALID_INPUT"
    VERSION_MISMATCH = "VERSION_MISMATCH"
    UNSUPPORTED = "UNSUPPORTED"
    TIMEOUT = "TIMEOUT"
    RESULT_UNKNOWN = "RESULT_UNKNOWN"
    CANCELLED = "CANCELLED"
    RETRYABLE_FAILURE = "RETRYABLE_FAILURE"
    NON_RETRYABLE_FAILURE = "NON_RETRYABLE_FAILURE"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"


RETRYABLE_CODES = frozenset({ErrorCode.TIMEOUT, ErrorCode.RETRYABLE_FAILURE})

HTTP_STATUS = {
    ErrorCode.INVALID_INPUT: 422,
    ErrorCode.VERSION_MISMATCH: 409,
    ErrorCode.UNSUPPORTED: 422,
    ErrorCode.TIMEOUT: 504,
    ErrorCode.RESULT_UNKNOWN: 502,
    ErrorCode.CANCELLED: 409,
    ErrorCode.RETRYABLE_FAILURE: 503,
    ErrorCode.NON_RETRYABLE_FAILURE: 500,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.CONFLICT: 409,
}


class FieldError(ContractModel):
    path: str
    message: str


class ErrorInfo(ContractModel):
    code: ErrorCode
    message: str
    retryable: bool
    details: dict[str, Any] = Field(default_factory=dict)
    field_errors: list[FieldError] = Field(default_factory=list)
