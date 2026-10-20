"""execution.api 的数据类型（命令与任务 12；契约 command / prepare-result / execution-binding / outbox-event 等）。

全部是冻结的数据类；时间一律带时区。`to_contract()` 输出契约里的 camelCase 形状。
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from titanloom.kernel.clock import ensure_utc, to_iso
from titanloom.kernel.reg.errors import ErrorCode

Mode = Literal["sync", "async"]
Lane = Literal["light", "heavy"]
ConfirmPolicy = Literal["auto", "confirm"]
EstimateStatus = Literal["exact", "bounded_estimate", "unknown"]
CommandState = Literal["prepared", "awaiting_confirmation", "ready", "accepted", "canceled", "expired"]
JobState = Literal[
    "queued", "running", "retry_wait", "cancel_requested", "reconciling", "succeeded", "failed", "canceled", "timed_out"
]
EffectStatus = Literal["none", "committed", "partial", "unknown"]
RetryReason = Literal["transient", "dependency_unavailable", "rate_limited", "timeout_before_effect"]
Conclusion = Literal["done", "not_done", "partial", "unclear"]

_CAP_RE = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")
_MSG_KEY_RE = re.compile(r"^(plugin\.[a-z0-9-]+|[a-z][a-z0-9]*)(\.[a-z][A-Za-z0-9]*)+$")
_RRULE_RE = re.compile(r"^(FREQ=|RRULE:FREQ=)")
_TZ_RE = re.compile(r"^[A-Za-z_]+(/[A-Za-z0-9_+-]+)+$")


def command_id(u: uuid.UUID) -> str:
    """对外命令编号：cmd_ + uuid7 的全部 32 位十六进制；内部仍是同一个 uuid。"""
    return "cmd_" + u.hex


def command_uuid(cid: str) -> uuid.UUID:
    if not cid.startswith("cmd_"):
        raise ValueError(f"不是命令编号：{cid!r}")
    return uuid.UUID(hex=cid[4:])


def _need_tz(ts: datetime | None) -> None:
    if ts is not None:
        ensure_utc(ts)


@dataclass(frozen=True, slots=True)
class TargetRef:
    """命令作用的对象。id 必须是具体的，不能是 latest（规范 6.3）。"""

    type: str
    id: str

    def __post_init__(self) -> None:
        if self.id == "latest":
            raise ValueError("目标编号不能是 latest")


@dataclass(frozen=True, slots=True)
class ScopeKey:
    """重道按范围轮流、限排队（命令与任务 7）。"""

    kind: Literal["dept", "project", "platform"]
    id: str = "-"


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 3
    backoff_sec: tuple[int, ...] = (30, 120)
    jitter: float = 0.2
    retry_on: tuple[RetryReason, ...] = ("transient", "dependency_unavailable", "rate_limited", "timeout_before_effect")

    def __post_init__(self) -> None:
        if not 1 <= self.max_attempts <= 10 or len(self.backoff_sec) > 9 or not 0 <= self.jitter <= 0.5:
            raise ValueError("重试参数超出契约范围")

    def to_contract(self) -> dict[str, Any]:
        return {
            "maxAttempts": self.max_attempts,
            "backoffSec": list(self.backoff_sec),
            "jitter": self.jitter,
            "retryOn": list(self.retry_on),
        }


@dataclass(frozen=True, slots=True)
class ReconcilePolicy:
    auto_window_min: int = 15
    interval_sec: int = 60

    def to_contract(self) -> dict[str, Any]:
        return {"autoWindowMin": self.auto_window_min, "intervalSec": self.interval_sec}


@dataclass(frozen=True, slots=True)
class ExecutionBinding:
    """能力的执行登记。id 与 access 的能力编号一致（模块.资源.动作），输出契约时加 titanloom. 前缀。"""

    capability_id: str
    contract_version: str
    module: str
    mode: Mode
    lane: Lane | None = None
    confirm_policy: ConfirmPolicy = "auto"
    max_run_sec: int = 60
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    cancellable: bool = False
    reconcile: ReconcilePolicy | None = None

    def __post_init__(self) -> None:
        if not _CAP_RE.match(self.capability_id) or self.capability_id.split(".")[0] != self.module:
            raise ValueError(f"能力编号不合规或不属于模块 {self.module}：{self.capability_id!r}")
        if (self.mode == "async") != (self.lane is not None):
            raise ValueError("只有后台执行（async）才有道，且必须有")
        if not 1 <= self.max_run_sec <= 86400:
            raise ValueError("maxRunSec 超出范围")

    @property
    def major(self) -> str:
        return self.contract_version.split(".")[0]

    def to_contract(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "capabilityId": "titanloom." + self.capability_id,
            "contractVersion": self.contract_version,
            "module": self.module,
            "mode": self.mode,
            "confirmPolicy": self.confirm_policy,
            "maxRunSec": self.max_run_sec,
            "retry": self.retry.to_contract(),
            "cancellable": self.cancellable,
        }
        if self.lane:
            out["lane"] = self.lane
        if self.reconcile:
            out["reconcile"] = self.reconcile.to_contract()
        return out


@dataclass(frozen=True, slots=True)
class PreviewSpec:
    """影响预览：由领域算好传入，结构化（文案键 + 参数 + 数量 + 受影响对象），不是成句文字。会进命令摘要。"""

    message_key: str
    effect_scope: str
    estimate_status: EstimateStatus
    message_params: Mapping[str, Any] = field(default_factory=lambda: {})
    counts: Mapping[str, int] = field(default_factory=lambda: {})
    affected: tuple[TargetRef, ...] = ()

    def __post_init__(self) -> None:
        if not _MSG_KEY_RE.match(self.message_key):
            raise ValueError(f"文案键不合规：{self.message_key!r}")

    def digest_form(self) -> dict[str, Any]:
        return {
            "messageKey": self.message_key,
            "messageParams": dict(self.message_params),
            "effectScope": self.effect_scope,
            "estimateStatus": self.estimate_status,
            "counts": dict(self.counts),
            "affected": [[a.type, a.id] for a in self.affected],
        }

    def to_contract(self) -> dict[str, Any]:
        """契约的 preview 不允许多余字段，数量与受影响对象放进 messageParams。"""
        params = dict(self.message_params)
        if self.counts:
            params["counts"] = dict(self.counts)
        if self.affected:
            params["affected"] = [{"type": a.type, "id": a.id} for a in self.affected]
        return {
            "messageKey": self.message_key,
            "messageParams": params,
            "effectScope": self.effect_scope,
            "estimateStatus": self.estimate_status,
        }


@dataclass(frozen=True, slots=True)
class PrepareResult:
    command_id: str
    state: CommandState
    capability_id: str
    contract_version: str
    command_digest: str
    expires_at: datetime
    effective_policy: Literal["confirm", "allow"]
    preview: PreviewSpec | None
    confirmation_required: bool

    def to_contract(self, request_id: str) -> dict[str, Any]:
        if self.state not in ("awaiting_confirmation", "ready"):
            raise ValueError("准备结果只在 awaiting_confirmation / ready 时输出")
        preview = self.preview.to_contract() if self.preview else None
        data: dict[str, Any] = {
            "commandId": self.command_id,
            "state": self.state,
            "capabilityId": self.capability_id,
            "contractVersion": self.contract_version,
            "commandDigest": self.command_digest,
            "expiresAt": to_iso(self.expires_at),
            "effectivePolicy": self.effective_policy,
            "confirmation": {"required": self.confirmation_required},
        }
        data["preview"] = preview or {
            "messageKey": "execution.noPreview",
            "effectScope": "none",
            "estimateStatus": "exact",
        }
        return {"requestId": request_id, "data": data}


@dataclass(frozen=True, slots=True)
class Confirmation:
    confirmation_id: str
    command_id: str
    command_digest: str
    confirmed_by: str
    created_at: datetime
    expires_at: datetime
    consumed: bool = False
    consumed_by_invocation: str | None = None


@dataclass(frozen=True, slots=True)
class JobRef:
    """job_id 是内部 uuid7；code 是给人看的 JR-xxxx。"""

    job_id: uuid.UUID
    code: str


@dataclass(frozen=True, slots=True)
class Invocation:
    invocation_id: str
    command_id: str
    capability_id: str
    contract_version: str
    accepted_at: datetime
    receipt_kind: Literal["sync_result", "async_receipt"]
    job: JobRef | None = None

    def to_contract(self, context_ref: str) -> dict[str, Any]:
        out: dict[str, Any] = {
            "invocationId": self.invocation_id,
            "commandId": self.command_id,
            "capabilityId": self.capability_id,
            "contractVersion": self.contract_version,
            "contextRef": context_ref,
            "acceptedAt": to_iso(self.accepted_at),
            "receiptKind": self.receipt_kind,
        }
        if self.job:
            out["jobRef"] = self.job.job_id.hex
        return out


@dataclass(frozen=True, slots=True)
class EventDraft:
    """要写进发件箱的事件。只带类型、对象、版本，不带业务明细（契约 outbox-event）。"""

    source: str
    type: str
    subject: TargetRef
    source_version: str
    scope: str
    minimal_change: Mapping[str, Any] | None = None
    schema_version: int = 1
    occurred_at: datetime | None = None
    correction_of: str | None = None
    causation_id: str | None = None

    def __post_init__(self) -> None:
        _need_tz(self.occurred_at)


@dataclass(frozen=True, slots=True)
class Event:
    """交给订阅者的事件。至少一次投递：处理必须幂等，按 event_id 去重。"""

    event_id: str
    sequence: int
    type: str
    schema_version: int
    source: str
    scope: str
    subject: TargetRef
    source_version: str
    occurred_at: datetime
    recorded_at: datetime
    correlation_id: str
    causation_id: str | None = None
    correction_of: str | None = None
    minimal_change: Mapping[str, Any] | None = None

    def to_contract(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "eventId": self.event_id,
            "type": self.type,
            "schemaVersion": self.schema_version,
            "source": self.source,
            "scope": self.scope,
            "subject": {"type": self.subject.type, "id": self.subject.id},
            "sourceVersion": self.source_version,
            "occurredAt": to_iso(self.occurred_at),
            "recordedAt": to_iso(self.recorded_at),
            "correlationId": self.correlation_id,
            "changeSeq": self.sequence,
        }
        if self.causation_id:
            out["causationId"] = self.causation_id
        if self.correction_of:
            out["correctionOf"] = self.correction_of
        if self.minimal_change is not None:
            out["minimalChange"] = dict(self.minimal_change)
        return out


class JobRetry(Exception):
    def __init__(self, reason: RetryReason):
        super().__init__(reason)
        self.reason: RetryReason = reason


@dataclass(frozen=True, slots=True)
class JobResult:
    """处理器交回的结果。effect_status=unknown 表示不知道做没做成：进待核对，不自动重发。"""

    effect_status: EffectStatus
    output_refs: Mapping[str, str] = field(default_factory=lambda: {})


@dataclass(frozen=True, slots=True)
class Reconciliation:
    """领域核对方法的结论，必须附证据。"""

    conclusion: Conclusion
    evidence: str


@dataclass(slots=True)
class JobContext:
    """处理器拿到的东西：输入、检查点、进度、取消。"""

    job: JobRef
    job_type: str
    attempt: int
    input_refs: Mapping[str, str]
    params: Mapping[str, Any]
    target: TargetRef | None
    checkpoint: Mapping[str, Any] | None
    _report: Callable[[int, int | None, str | None], None]
    _is_cancel_requested: Callable[[], bool]
    _save_checkpoint: Callable[[Mapping[str, Any]], None]

    def report_progress(self, done: int, total: int | None = None, unit: str | None = None) -> None:
        self._report(done, total, unit)

    def cancel_requested(self) -> bool:
        return self._is_cancel_requested()

    def save_checkpoint(self, data: Mapping[str, Any]) -> None:
        self._save_checkpoint(data)


@dataclass(frozen=True, slots=True)
class JobView:
    job: JobRef
    job_type: str
    owner_module: str
    lane: Lane
    scope: ScopeKey
    state: JobState
    effect_status: EffectStatus
    attempt_count: int
    enqueue_count: int
    input_refs: Mapping[str, str]
    output_refs: Mapping[str, str]
    progress: tuple[int, int | None, str | None] | None
    manual_review_required: bool
    command_id: str | None
    invocation_id: str | None
    created_at: datetime
    finished_at: datetime | None
    error: ErrorCode | None


@dataclass(frozen=True, slots=True)
class Misfire:
    policy: Literal["skip", "catch_up"] = "skip"
    max_catch_up: int | None = None
    within_hours: int | None = None

    def __post_init__(self) -> None:
        if self.policy == "catch_up" and (self.max_catch_up is None or self.within_hours is None):
            raise ValueError("补跑必须声明次数与时间窗上限")

    def to_contract(self) -> dict[str, Any]:
        out: dict[str, Any] = {"policy": self.policy}
        if self.max_catch_up is not None:
            out["maxCatchUp"] = self.max_catch_up
        if self.within_hours is not None:
            out["withinHours"] = self.within_hours
        return out


@dataclass(frozen=True, slots=True)
class ScheduleRuleSpec:
    rule_id: str
    owner_module: str
    capability_id: str
    rrule: str
    time_zone: str = "Asia/Shanghai"
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    misfire: Misfire = field(default_factory=Misfire)
    overlap: Literal["skip_new", "allow"] = "skip_new"
    status: Literal["active", "paused", "ended"] = "active"

    def __post_init__(self) -> None:
        if not _RRULE_RE.match(self.rrule) or not _TZ_RE.match(self.time_zone):
            raise ValueError("rrule 或时区格式不合规")
        _need_tz(self.valid_from)
        _need_tz(self.valid_to)

    def to_contract(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "ruleId": self.rule_id,
            "ownerModule": self.owner_module,
            "bindingRef": self.capability_id,
            "rrule": self.rrule,
            "timeZone": self.time_zone,
            "misfire": self.misfire.to_contract(),
            "overlap": self.overlap,
            "status": self.status,
        }
        if self.valid_from:
            out["validFrom"] = to_iso(self.valid_from)
        if self.valid_to:
            out["validTo"] = to_iso(self.valid_to)
        return out


@dataclass(frozen=True, slots=True)
class Occurrence:
    """一个计划时刻的去向。同一规则同一时刻只记一条（唯一）。"""

    rule_id: str
    planned_at: datetime
    outcome: Literal["enqueued", "skipped_overlap", "skipped_inactive"]
    job: JobRef | None = None
