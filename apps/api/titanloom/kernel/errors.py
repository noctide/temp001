"""统一错误体（能力契约 12；契约 error.schema.json）。

代码里只抛 AppError，错误码只用生成的 ErrorCode；对外只返回登记的错误码与文案键，不暴露栈、SQL、路径、凭据。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from titanloom.kernel.reg.errors import ERRORS, ErrorCode


class AppError(Exception):
    """业务可预期的错误。code 必须是登记过的 ErrorCode。"""

    def __init__(self, code: ErrorCode, params: dict[str, Any] | None = None, details: dict[str, Any] | None = None):
        super().__init__(code.value)
        self.code = code
        self.params: dict[str, Any] = params or {}
        self.details: dict[str, Any] = details or {}

    @property
    def http_status(self) -> int:
        return ERRORS[self.code].http_status


class ErrorBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    code: str
    message_key: str = Field(alias="messageKey")
    message_params: dict[str, Any] = Field(default_factory=dict, alias="messageParams")
    retryable: bool
    recovery_action: str | None = Field(default=None, alias="recoveryAction")
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    request_id: str = Field(alias="requestId")
    error: ErrorBody


def error_response(err: AppError, request_id: str, *, show_details: bool) -> ErrorResponse:
    """details 只给有开发者资格的人看（总图 7"出错"）。"""
    meta = ERRORS[err.code]
    body = ErrorBody(
        code=err.code.value,
        messageKey=meta.message_key,
        messageParams=err.params,
        retryable=meta.retryable,
        recoveryAction=meta.recovery_action,
        details=err.details if show_details and err.details else None,
    )
    return ErrorResponse(requestId=request_id, error=body)
