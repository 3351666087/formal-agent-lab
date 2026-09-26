"""Unified error model shared by API responses, activities, plugins and the SDK."""

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


class FormalLabError(Exception):
    code: ErrorCode = ErrorCode.NON_RETRYABLE_FAILURE

    def __init__(self, message: str, *, details: dict[str, Any] | None = None,
                 field_errors: list[FieldError] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.field_errors = field_errors or []

    @property
    def retryable(self) -> bool:
        return self.code in RETRYABLE_CODES

    def to_info(self) -> ErrorInfo:
        return ErrorInfo(code=self.code, message=self.message, retryable=self.retryable,
                         details=self.details, field_errors=self.field_errors)

    @classmethod
    def from_info(cls, info: ErrorInfo) -> FormalLabError:
        err_cls = _BY_CODE.get(info.code, FormalLabError)
        return err_cls(info.message, details=info.details, field_errors=info.field_errors)


class InvalidInput(FormalLabError):
    code = ErrorCode.INVALID_INPUT


class VersionMismatch(FormalLabError):
    code = ErrorCode.VERSION_MISMATCH


class Unsupported(FormalLabError):
    code = ErrorCode.UNSUPPORTED


class Timeout(FormalLabError):
    code = ErrorCode.TIMEOUT


class ResultUnknown(FormalLabError):
    code = ErrorCode.RESULT_UNKNOWN


class Cancelled(FormalLabError):
    code = ErrorCode.CANCELLED


class RetryableFailure(FormalLabError):
    code = ErrorCode.RETRYABLE_FAILURE


class NonRetryableFailure(FormalLabError):
    code = ErrorCode.NON_RETRYABLE_FAILURE


class NotFound(FormalLabError):
    code = ErrorCode.NOT_FOUND


class Conflict(FormalLabError):
    code = ErrorCode.CONFLICT


_BY_CODE: dict[ErrorCode, type[FormalLabError]] = {
    c.code: c
    for c in (InvalidInput, VersionMismatch, Unsupported, Timeout, ResultUnknown, Cancelled,
              RetryableFailure, NonRetryableFailure, NotFound, Conflict)
}
