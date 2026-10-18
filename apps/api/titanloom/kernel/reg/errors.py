"""由 ops/tools/tl.py gen 生成，不要手改；改正本后重新生成（开发项目划分规范 5.5）。"""

from dataclasses import dataclass
from enum import StrEnum


class ErrorCode(StrEnum):
    INVALID_REQUEST = "INVALID_REQUEST"
    INPUT_VALIDATION_FAILED = "INPUT_VALIDATION_FAILED"
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    ACCESS_DENIED = "ACCESS_DENIED"
    DELEGATION_REVOKED = "DELEGATION_REVOKED"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    RESOURCE_VERSION_CONFLICT = "RESOURCE_VERSION_CONFLICT"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    CAPABILITY_DISABLED = "CAPABILITY_DISABLED"
    CONTRACT_VERSION_UNSUPPORTED = "CONTRACT_VERSION_UNSUPPORTED"
    COMMAND_EXPIRED = "COMMAND_EXPIRED"
    RESULT_EXPIRED = "RESULT_EXPIRED"
    IDEMPOTENCY_WINDOW_EXPIRED = "IDEMPOTENCY_WINDOW_EXPIRED"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    RESULT_TOO_LARGE = "RESULT_TOO_LARGE"
    QUERY_BUDGET_EXCEEDED = "QUERY_BUDGET_EXCEEDED"
    RATE_LIMITED = "RATE_LIMITED"
    CAPACITY_EXCEEDED = "CAPACITY_EXCEEDED"
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"
    REQUEST_DEADLINE_EXCEEDED = "REQUEST_DEADLINE_EXCEEDED"
    DEPENDENCY_BLOCKED = "DEPENDENCY_BLOCKED"
    PROJECTION_STALE = "PROJECTION_STALE"
    PARTIAL_ACTIVATION = "PARTIAL_ACTIVATION"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    EGRESS_TARGET_NOT_APPROVED = "EGRESS_TARGET_NOT_APPROVED"
    CHANNEL_DISABLED = "CHANNEL_DISABLED"
    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
    FEATURE_NOT_OPEN = "FEATURE_NOT_OPEN"
    SECOND_APPROVAL_REQUIRED = "SECOND_APPROVAL_REQUIRED"


@dataclass(frozen=True)
class ErrorMeta:
    http_status: int
    retryable: bool
    recovery_action: str | None
    message_key: str


ERRORS: dict[ErrorCode, ErrorMeta] = {
    ErrorCode.INVALID_REQUEST: ErrorMeta(400, False, "fix_input", "errors.invalidRequest"),
    ErrorCode.INPUT_VALIDATION_FAILED: ErrorMeta(422, False, "fix_input", "errors.inputValidationFailed"),
    ErrorCode.AUTHENTICATION_REQUIRED: ErrorMeta(401, False, "reauthenticate", "errors.authenticationRequired"),
    ErrorCode.TOKEN_EXPIRED: ErrorMeta(401, False, "reauthenticate", "errors.tokenExpired"),
    ErrorCode.ACCESS_DENIED: ErrorMeta(403, False, "stop", "errors.accessDenied"),
    ErrorCode.DELEGATION_REVOKED: ErrorMeta(403, False, "stop", "errors.delegationRevoked"),
    ErrorCode.RESOURCE_NOT_FOUND: ErrorMeta(404, False, "none", "errors.resourceNotFound"),
    ErrorCode.CONFIRMATION_REQUIRED: ErrorMeta(409, False, "confirm_then_submit", "errors.confirmationRequired"),
    ErrorCode.RESOURCE_VERSION_CONFLICT: ErrorMeta(409, False, "refresh_and_prepare", "errors.resourceVersionConflict"),
    ErrorCode.IDEMPOTENCY_CONFLICT: ErrorMeta(409, False, "check_intent", "errors.idempotencyConflict"),
    ErrorCode.CAPABILITY_DISABLED: ErrorMeta(409, False, "stop_or_migrate", "errors.capabilityDisabled"),
    ErrorCode.CONTRACT_VERSION_UNSUPPORTED: ErrorMeta(409, False, "stop_or_migrate", "errors.contractVersionUnsupported"),
    ErrorCode.COMMAND_EXPIRED: ErrorMeta(410, False, "check_business_fact", "errors.commandExpired"),
    ErrorCode.RESULT_EXPIRED: ErrorMeta(410, False, "check_business_fact", "errors.resultExpired"),
    ErrorCode.IDEMPOTENCY_WINDOW_EXPIRED: ErrorMeta(410, False, "check_business_fact", "errors.idempotencyWindowExpired"),
    ErrorCode.PAYLOAD_TOO_LARGE: ErrorMeta(413, False, "shrink_or_use_asset", "errors.payloadTooLarge"),
    ErrorCode.RESULT_TOO_LARGE: ErrorMeta(413, False, "shrink_or_use_asset", "errors.resultTooLarge"),
    ErrorCode.QUERY_BUDGET_EXCEEDED: ErrorMeta(422, False, "narrow_or_async", "errors.queryBudgetExceeded"),
    ErrorCode.RATE_LIMITED: ErrorMeta(429, True, "backoff_retry_after", "errors.rateLimited"),
    ErrorCode.CAPACITY_EXCEEDED: ErrorMeta(429, True, "backoff_retry_after", "errors.capacityExceeded"),
    ErrorCode.DEPENDENCY_UNAVAILABLE: ErrorMeta(503, True, "retry_per_contract", "errors.dependencyUnavailable"),
    ErrorCode.REQUEST_DEADLINE_EXCEEDED: ErrorMeta(504, False, "query_original_execution", "errors.requestDeadlineExceeded"),
    ErrorCode.DEPENDENCY_BLOCKED: ErrorMeta(409, False, "resolve_dependencies", "errors.dependencyBlocked"),
    ErrorCode.PROJECTION_STALE: ErrorMeta(409, True, "refresh_projection", "errors.projectionStale"),
    ErrorCode.PARTIAL_ACTIVATION: ErrorMeta(409, False, "reconcile", "errors.partialActivation"),
    ErrorCode.RECONCILIATION_REQUIRED: ErrorMeta(409, False, "reconcile", "errors.reconciliationRequired"),
    ErrorCode.BUDGET_EXCEEDED: ErrorMeta(429, False, "narrow_or_request_quota", "errors.budgetExceeded"),
    ErrorCode.EGRESS_TARGET_NOT_APPROVED: ErrorMeta(403, False, "stop", "errors.egressTargetNotApproved"),
    ErrorCode.CHANNEL_DISABLED: ErrorMeta(409, False, "enable_channel", "errors.channelDisabled"),
    ErrorCode.ACCOUNT_LOCKED: ErrorMeta(423, False, "wait_and_retry", "errors.accountLocked"),
    ErrorCode.FEATURE_NOT_OPEN: ErrorMeta(403, False, "request_access", "errors.featureNotOpen"),
    ErrorCode.SECOND_APPROVAL_REQUIRED: ErrorMeta(409, False, "await_approval", "errors.secondApprovalRequired"),
}
