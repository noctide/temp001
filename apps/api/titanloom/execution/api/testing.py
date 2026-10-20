"""execution.api 的内存测试桩（给别的模块的测试用；真实实现是另一回事）。

    from titanloom.execution.api.testing import execution_stub      # 放进模块 tests/conftest.py

    def test_x(execution_stub, access_stub):
        ...
        with as_principal("acc-H0012"):
            result = prepare("attendance.schedule.publish", params={...}, idempotency_key=execution_stub.new_key())
        execution_stub.drain()                       # 手动跑后台任务与事件投递
        assert [e.type for e in execution_stub.events] == ["attendance.schedule.published"]

它做什么：幂等、命令状态机、确认、版本复查、任务重试 / 待核对 / 取消、定时的“同一计划时刻只放一件”、事件按顺序投递。
它不做什么：不开线程、不展开 rrule（用 fire 手动触发一个计划时刻）、不限并发与租约；
同步能力的“业务本身”由调用者在自己的事务里做。

事务：enqueue_in_tx / emit_in_tx 不在 kernel.db 事务里就报错。在事务里做的一切（命令、任务、事件、定时记录）
随那个会话回滚而一起撤销（会话上挂事件钩子，第一次碰到时记一份快照）。测试要用带库的会话时，
用 `tx_session` fixture（内存 SQLite，只为了有一个可回滚的会话）。
"""

from __future__ import annotations

import copy
import fnmatch
import os
import re
import uuid
from collections.abc import Callable, Generator, Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from titanloom.access import api as access_api
from titanloom.access.api import Target
from titanloom.access.api.testing import InMemoryAccess
from titanloom.execution.api import _provider
from titanloom.execution.api import types as t
from titanloom.execution.api.types import (
    EventDraft,
    ExecutionBinding,
    Invocation,
    JobContext,
    JobRef,
    JobResult,
    JobRetry,
    JobState,
    JobView,
    Lane,
    Occurrence,
    PrepareResult,
    Reconciliation,
    RetryPolicy,
    RetryReason,
    ScheduleRuleSpec,
    ScopeKey,
    TargetRef,
    command_id,
    command_uuid,
)
from titanloom.kernel import context, db
from titanloom.kernel.clock import Clock, ensure_utc
from titanloom.kernel.errors import AppError
from titanloom.kernel.idem import request_digest
from titanloom.kernel.ids import short_code, uuid7, uuid7_ms
from titanloom.kernel.reg.errors import ErrorCode

COMMAND_TTL = timedelta(minutes=15)
KEY_PAST = timedelta(hours=24)
KEY_FUTURE = timedelta(minutes=5)
_EVENT_TYPE_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")
_TERMINAL: frozenset[JobState] = frozenset({"succeeded", "failed", "canceled", "timed_out"})
_RETRY_ERROR: dict[RetryReason, ErrorCode] = {
    "transient": ErrorCode.DEPENDENCY_UNAVAILABLE,
    "dependency_unavailable": ErrorCode.DEPENDENCY_UNAVAILABLE,
    "rate_limited": ErrorCode.RATE_LIMITED,
    "timeout_before_effect": ErrorCode.REQUEST_DEADLINE_EXCEEDED,
}


class BindingConflict(ValueError):
    """同一个能力重复登记且内容不同。"""


class NotRegistered(LookupError):
    """用了没登记的能力、处理器或规则。"""


class NotInTransaction(RuntimeError):
    """enqueue_in_tx / emit_in_tx 必须在 kernel.db 事务里调用。"""


def key_at(when: datetime) -> str:
    """造一个时间戳在 when 的 UUIDv7 防重复编号（不碰 kernel.ids 的全局单调状态）。"""
    ms = int(ensure_utc(when).timestamp() * 1000)
    rand = int.from_bytes(os.urandom(10), "big")
    value = (
        (ms & ((1 << 48) - 1)) << 80 | 0x7 << 76 | (rand >> 62 & 0xFFF) << 64 | 0b10 << 62 | (rand & ((1 << 62) - 1))
    )
    return str(uuid.UUID(int=value))


@dataclass(slots=True)
class _Cmd:
    id: uuid.UUID
    capability_id: str
    contract_version: str
    state: str
    principal: str
    delegation: str | None
    key: str
    request_digest: str
    command_digest: str
    params: Mapping[str, Any]
    target: TargetRef | None
    expected_version: str | None
    preview: t.PreviewSpec | None
    scope: ScopeKey
    access_target: Target | None
    confirm_required: bool
    created_at: datetime
    expires_at: datetime
    confirmation_id: str | None = None
    invocation_id: str | None = None


@dataclass(slots=True)
class _Job:
    id: uuid.UUID
    code: str
    job_type: str
    owner_module: str
    lane: Lane
    scope: ScopeKey
    input_refs: Mapping[str, str]
    created_at: datetime
    not_before: datetime | None = None
    state: JobState = "queued"
    effect: str = "none"
    attempts: int = 0
    enqueues: int = 1
    output_refs: Mapping[str, str] = field(default_factory=lambda: {})
    progress: tuple[int, int | None, str | None] | None = None
    checkpoint: Mapping[str, Any] | None = None
    manual_review: bool = False
    command_id: str | None = None
    invocation_id: str | None = None
    finished_at: datetime | None = None
    error: ErrorCode | None = None
    next_run: datetime | None = None
    rule_id: str | None = None
    reconcile_started: datetime | None = None
    last_reconcile: datetime | None = None


@dataclass(slots=True)
class _State:
    commands: dict[uuid.UUID, _Cmd] = field(default_factory=lambda: {})
    idem: dict[tuple[str, ...], uuid.UUID] = field(default_factory=lambda: {})
    confirmations: dict[str, t.Confirmation] = field(default_factory=lambda: {})
    invocations: dict[str, Invocation] = field(default_factory=lambda: {})
    jobs: dict[uuid.UUID, _Job] = field(default_factory=lambda: {})
    events: list[t.Event] = field(default_factory=lambda: [])
    cursors: dict[str, int] = field(default_factory=lambda: {})
    rules: dict[str, ScheduleRuleSpec] = field(default_factory=lambda: {})
    occurrences: dict[tuple[str, datetime], Occurrence] = field(default_factory=lambda: {})
    reconcile_log: dict[uuid.UUID, list[Reconciliation]] = field(default_factory=lambda: {})
    job_seq: int = 0
    event_seq: int = 0


class InMemoryExecution:
    """execution.api 的测试桩。time 取 clock，主体与代办取 access.api。"""

    def __init__(
        self, clock: Clock, *, enforce_access: bool = True, max_queued_per_scope: int = 20, max_queued: int = 200
    ):
        self.clock = clock
        self.enforce_access = enforce_access
        self.max_queued_per_scope = max_queued_per_scope
        self.max_queued = max_queued
        self._s = _State()
        self._bindings: dict[str, ExecutionBinding] = {}
        self._handlers: dict[str, Callable[[JobContext], JobResult]] = {}
        self._reconcilers: dict[str, Callable[[JobView], Reconciliation]] = {}
        self._validators: dict[str, Callable[[TargetRef | None, str], bool]] = {}
        self._subs: dict[str, list[tuple[str, Callable[[t.Event], None]]]] = {}
        self._cursor_start: dict[str, int] = {}

    # ---- 给测试断言用 ----

    def new_key(self) -> str:
        """一个时间戳在“现在”的防重复编号（桩的时钟可能不是真实时间）。"""
        return key_at(self.clock.now())

    @property
    def events(self) -> tuple[t.Event, ...]:
        return tuple(self._s.events)

    @property
    def jobs(self) -> tuple[JobView, ...]:
        return tuple(self._view(j) for j in self._s.jobs.values())

    @property
    def invocations(self) -> tuple[Invocation, ...]:
        return tuple(self._s.invocations.values())

    def command_state(self, cid: str) -> str:
        cmd = self._s.commands[command_uuid(cid)]
        self._expire(cmd)
        return cmd.state

    def confirmation_of(self, cid: str) -> t.Confirmation | None:
        c = self._s.commands[command_uuid(cid)].confirmation_id
        return self._s.confirmations[c] if c else None

    def occurrences(self, rule_id: str) -> tuple[Occurrence, ...]:
        return tuple(o for (r, _), o in self._s.occurrences.items() if r == rule_id)

    def reconcile_log(self, job_id: uuid.UUID) -> tuple[Reconciliation, ...]:
        return tuple(self._s.reconcile_log.get(job_id, ()))

    # ---- 事务：第一次碰到会话就记一份快照，会话回滚就还原 ----

    def _touch(self) -> None:
        if not db.in_transaction():
            return
        session = db.current_session()
        marker = ("execution_stub", id(self))
        if marker in session.info:
            return
        session.info[marker] = copy.deepcopy(self._s)
        session.connection()  # 让会话真的开始，回滚才会触发钩子

        def on_rollback(_: Session) -> None:
            snap = session.info.pop(marker, None)
            if snap is not None:
                self._s = snap

        def on_commit(_: Session) -> None:
            session.info.pop(marker, None)

        event.listen(session, "after_rollback", on_rollback)
        event.listen(session, "after_commit", on_commit)

    @staticmethod
    def _require_tx(what: str) -> None:
        if not db.in_transaction():
            raise NotInTransaction(f"{what} 必须在事务里调用（kernel.db.transaction()）")

    # ---- 登记 ----

    def register_binding(self, binding: ExecutionBinding) -> None:
        old = self._bindings.get(binding.capability_id)
        if old is not None and old != binding:
            raise BindingConflict(f"{binding.capability_id} 已用不同内容登记过")
        self._bindings[binding.capability_id] = binding

    def job_handler(self, job_type: str, handler: Callable[[JobContext], JobResult]) -> None:
        self._handlers[job_type] = handler

    def reconcile_handler(self, job_type: str, handler: Callable[[JobView], Reconciliation]) -> None:
        self._reconcilers[job_type] = handler

    def version_validator(self, capability_id: str, check: Callable[[TargetRef | None, str], bool]) -> None:
        self._binding(capability_id)
        self._validators[capability_id] = check

    def _binding(self, capability_id: str) -> ExecutionBinding:
        b = self._bindings.get(capability_id)
        if b is None:
            raise NotRegistered(f"能力 {capability_id!r} 没有登记执行方式")
        return b

    # ---- 准备 / 确认 / 提交 ----

    def _principal(self) -> tuple[str, str | None]:
        me = access_api.whoami()
        return (me.acting_for, me.account_id) if me.acting_for else (me.account_id, None)

    def _check_access(self, capability_id: str, access_target: Target | None) -> None:
        if self.enforce_access:
            access_api.check(capability_id, access_target).require()

    def _expire(self, cmd: _Cmd) -> None:
        if cmd.state in ("prepared", "awaiting_confirmation", "ready") and self.clock.now() >= cmd.expires_at:
            cmd.state = "expired"

    def _result(self, cmd: _Cmd) -> PrepareResult:
        return PrepareResult(
            command_id(cmd.id),
            cmd.state,  # pyright: ignore[reportArgumentType]
            cmd.capability_id,
            cmd.contract_version,
            cmd.command_digest,
            cmd.expires_at,
            "confirm" if cmd.confirm_required else "allow",
            cmd.preview,
            cmd.confirm_required,
        )

    def _check_key(self, key: str) -> None:
        try:
            u = uuid.UUID(key)
        except ValueError:
            raise AppError(ErrorCode.INPUT_VALIDATION_FAILED, details={"field": "idempotencyKey"}) from None
        if u.version != 7 or u.variant != uuid.RFC_4122:
            raise AppError(ErrorCode.INPUT_VALIDATION_FAILED, details={"field": "idempotencyKey"})
        made = datetime.fromtimestamp(uuid7_ms(u) / 1000, UTC)
        now = self.clock.now()
        if made < now - KEY_PAST:
            raise AppError(ErrorCode.IDEMPOTENCY_WINDOW_EXPIRED)
        if made > now + KEY_FUTURE:
            raise AppError(ErrorCode.INPUT_VALIDATION_FAILED, details={"field": "idempotencyKey"})

    def prepare(
        self,
        capability_id: str,
        *,
        params: Mapping[str, Any],
        idempotency_key: str,
        target: TargetRef | None = None,
        expected_version: str | None = None,
        preview: t.PreviewSpec | None = None,
        scope: ScopeKey | None = None,
        access_target: Target | None = None,
    ) -> PrepareResult:
        self._touch()
        b = self._binding(capability_id)
        principal, delegation = self._principal()
        self._check_access(capability_id, access_target)
        if expected_version == "latest":
            raise AppError(ErrorCode.INPUT_VALIDATION_FAILED, details={"field": "expectedVersion"})
        req = request_digest(
            {
                "capabilityId": capability_id,
                "params": dict(params),
                "target": [target.type, target.id] if target else None,
                "expectedVersion": expected_version,
            }
        )
        scope_key = (principal, delegation or "", capability_id, b.major, idempotency_key)
        existing = self._s.idem.get(scope_key)
        if existing is not None:
            cmd = self._s.commands[existing]
            if cmd.request_digest != req:
                raise AppError(ErrorCode.IDEMPOTENCY_CONFLICT)
            self._expire(cmd)
            return self._result(cmd)
        self._check_key(idempotency_key)
        needs_confirm = b.confirm_policy == "confirm" or (preview is not None and preview.estimate_status == "unknown")
        cid = uuid7()
        digest = request_digest(
            {
                "c": capability_id,
                "v": b.contract_version,
                "p": principal,
                "d": delegation,
                "r": req,
                "pv": preview.digest_form() if preview else None,
                "id": cid.hex,
            }
        )
        now = self.clock.now()
        cmd = _Cmd(
            cid,
            capability_id,
            b.contract_version,
            "awaiting_confirmation" if needs_confirm else "ready",
            principal,
            delegation,
            idempotency_key,
            req,
            digest,
            copy.deepcopy(dict(params)),
            target,
            expected_version,
            preview,
            scope or ScopeKey("platform"),
            access_target,
            needs_confirm,
            now,
            now + COMMAND_TTL,
        )
        self._s.commands[cmd.id] = cmd
        self._s.idem[scope_key] = cmd.id
        return self._result(cmd)

    def _owned(self, cid: str) -> _Cmd:
        try:
            cmd = self._s.commands.get(command_uuid(cid))
        except ValueError:
            cmd = None
        if cmd is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND)
        if self._principal()[0] != cmd.principal:
            raise AppError(ErrorCode.ACCESS_DENIED)
        self._expire(cmd)
        return cmd

    def confirm(self, command_id: str, *, command_digest: str) -> t.Confirmation:
        self._touch()
        me = access_api.whoami()
        cmd = self._owned(command_id)
        if me.kind != "human" or me.acting_for is not None or me.account_id != cmd.principal:
            raise AppError(ErrorCode.ACCESS_DENIED)
        if cmd.state == "expired":
            raise AppError(ErrorCode.COMMAND_EXPIRED)
        if command_digest != cmd.command_digest:
            raise AppError(ErrorCode.RESOURCE_VERSION_CONFLICT)
        if cmd.state == "ready" and cmd.confirmation_id and not self._s.confirmations[cmd.confirmation_id].consumed:
            return self._s.confirmations[cmd.confirmation_id]
        if cmd.state != "awaiting_confirmation":
            raise AppError(ErrorCode.RESOURCE_VERSION_CONFLICT)
        conf = t.Confirmation(
            "conf_" + uuid7().hex, command_id, cmd.command_digest, me.account_id, self.clock.now(), cmd.expires_at
        )
        self._s.confirmations[conf.confirmation_id] = conf
        cmd.confirmation_id = conf.confirmation_id
        cmd.state = "ready"
        return conf

    def submit(self, command_id: str, *, idempotency_key: str) -> Invocation:
        self._touch()
        cmd = self._owned(command_id)
        if idempotency_key != cmd.key:
            raise AppError(ErrorCode.IDEMPOTENCY_CONFLICT)
        if cmd.state == "accepted" and cmd.invocation_id:
            return self._s.invocations[cmd.invocation_id]
        if cmd.state in ("expired", "canceled"):
            raise AppError(ErrorCode.COMMAND_EXPIRED)
        b = self._binding(cmd.capability_id)
        self._check_access(cmd.capability_id, cmd.access_target)
        check = self._validators.get(cmd.capability_id)
        if cmd.expected_version is not None and check is not None and not check(cmd.target, cmd.expected_version):
            raise AppError(ErrorCode.RESOURCE_VERSION_CONFLICT)
        if cmd.confirm_required and not (cmd.state == "ready" and cmd.confirmation_id):
            raise AppError(ErrorCode.CONFIRMATION_REQUIRED)
        inv_id = "inv_" + uuid7().hex
        job: JobRef | None = None
        if b.mode == "async":
            assert b.lane is not None  # noqa: S101 - ExecutionBinding 已保证
            job = self._new_job(
                cmd.capability_id, b.module, {"commandId": command_id}, b.lane, cmd.scope, None, command_id, inv_id
            )
        if cmd.confirmation_id:
            conf = self._s.confirmations[cmd.confirmation_id]
            self._s.confirmations[conf.confirmation_id] = replace(conf, consumed=True, consumed_by_invocation=inv_id)
        inv = Invocation(
            inv_id,
            command_id,
            cmd.capability_id,
            cmd.contract_version,
            self.clock.now(),
            "async_receipt" if job else "sync_result",
            job,
        )
        self._s.invocations[inv_id] = inv
        cmd.invocation_id = inv_id
        cmd.state = "accepted"
        return inv

    def cancel(self, command_id: str) -> None:
        self._touch()
        cmd = self._owned(command_id)
        if cmd.state == "accepted":
            raise AppError(ErrorCode.INVALID_REQUEST, details={"reason": "alreadyAccepted"})
        if cmd.state in ("prepared", "awaiting_confirmation", "ready"):
            cmd.state = "canceled"

    # ---- 任务 ----

    def _new_job(
        self,
        job_type: str,
        owner_module: str,
        input_refs: Mapping[str, str],
        lane: Lane,
        scope: ScopeKey | None,
        not_before: datetime | None,
        cmd_id: str | None,
        invocation_id: str | None,
        rule_id: str | None = None,
    ) -> JobRef:
        scope = scope or ScopeKey("platform")
        if lane == "heavy":
            waiting = [j for j in self._s.jobs.values() if j.lane == "heavy" and j.state in ("queued", "retry_wait")]
            if len(waiting) >= self.max_queued or sum(j.scope == scope for j in waiting) >= self.max_queued_per_scope:
                raise AppError(ErrorCode.CAPACITY_EXCEEDED)
        self._s.job_seq += 1
        j = _Job(
            uuid7(),
            short_code("JR", self._s.job_seq),
            job_type,
            owner_module,
            lane,
            scope,
            dict(input_refs),
            self.clock.now(),
            not_before,
            command_id=cmd_id,
            invocation_id=invocation_id,
            rule_id=rule_id,
        )
        self._s.jobs[j.id] = j
        return JobRef(j.id, j.code)

    def enqueue_in_tx(
        self,
        job_type: str,
        *,
        owner_module: str,
        input_refs: Mapping[str, str],
        lane: Lane = "light",
        scope: t.ScopeKey | None = None,
        not_before: datetime | None = None,
        invocation_id: str | None = None,
    ) -> JobRef:
        self._require_tx("enqueue_in_tx")
        self._touch()
        if not_before is not None:
            ensure_utc(not_before)
        return self._new_job(job_type, owner_module, input_refs, lane, scope, not_before, None, invocation_id)

    def _view(self, j: _Job) -> JobView:
        return JobView(
            JobRef(j.id, j.code),
            j.job_type,
            j.owner_module,
            j.lane,
            j.scope,
            j.state,
            j.effect,  # pyright: ignore[reportArgumentType]
            j.attempts,
            j.enqueues,
            dict(j.input_refs),
            dict(j.output_refs),
            j.progress,
            j.manual_review,
            j.command_id,
            j.invocation_id,
            j.created_at,
            j.finished_at,
            j.error,
        )

    def get_job(self, job_id: uuid.UUID) -> JobView:
        j = self._s.jobs.get(job_id)
        if j is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND)
        return self._view(j)

    def cancel_job(self, job_id: uuid.UUID) -> JobView:
        self._touch()
        j = self._s.jobs.get(job_id)
        if j is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND)
        b = self._bindings.get(j.job_type)
        if j.state in _TERMINAL or j.state == "cancel_requested":
            return self._view(j)
        if b is not None and not b.cancellable:
            raise AppError(ErrorCode.INVALID_REQUEST, details={"reason": "notCancellable"})
        if j.state in ("queued", "retry_wait"):
            self._finish(j, "canceled", "none")
        elif j.state == "running":
            j.state = "cancel_requested"
        return self._view(j)

    def _finish(self, j: _Job, state: JobState, effect: str, error: ErrorCode | None = None) -> None:
        j.state, j.effect, j.error, j.finished_at = state, effect, error, self.clock.now()

    def _policy(self, job_type: str) -> RetryPolicy:
        b = self._bindings.get(job_type)
        return b.retry if b else RetryPolicy()

    def _attempt(self, j: _Job) -> None:
        handler = self._handlers.get(j.job_type)
        if handler is None:
            raise NotRegistered(f"任务类型 {j.job_type!r} 没有登记处理器")
        cmd = self._s.commands.get(command_uuid(j.command_id)) if j.command_id else None
        j.attempts += 1
        j.state = "running"
        j.next_run = None

        def report(done: int, total: int | None, unit: str | None) -> None:
            j.progress = (done, total, unit)

        def save(data: Mapping[str, Any]) -> None:
            j.checkpoint = dict(data)

        ctx = JobContext(
            JobRef(j.id, j.code),
            j.job_type,
            j.attempts,
            dict(j.input_refs),
            copy.deepcopy(dict(cmd.params)) if cmd else {},
            cmd.target if cmd else None,
            j.checkpoint,
            report,
            lambda: j.state == "cancel_requested",
            save,
        )
        try:
            res = handler(ctx)
        except JobRetry as r:
            self._retry_or_fail(j, r.reason)
            return
        except AppError as e:
            self._finish(j, "failed", "none", e.code)
            return
        j.output_refs = dict(res.output_refs)
        if res.effect_status == "unknown":
            j.state, j.effect, j.reconcile_started = "reconciling", "unknown", self.clock.now()
        elif res.effect_status == "partial":
            j.manual_review = True
            self._finish(j, "failed", "partial")
        elif self._cancel_asked(j) and res.effect_status == "none":
            self._finish(j, "canceled", "none")
        else:
            self._finish(j, "succeeded", res.effect_status)

    @staticmethod
    def _cancel_asked(j: _Job) -> bool:
        return cast(str, j.state) == "cancel_requested"

    def _retry_or_fail(self, j: _Job, reason: RetryReason) -> None:
        policy = self._policy(j.job_type)
        if reason in policy.retry_on and j.attempts < policy.max_attempts:
            steps = policy.backoff_sec
            wait = steps[min(j.attempts - 1, len(steps) - 1)] if steps else 0
            j.state, j.next_run, j.enqueues = "retry_wait", self.clock.now() + timedelta(seconds=wait), j.enqueues + 1
        else:
            self._finish(j, "failed", "none", _RETRY_ERROR[reason])

    def _reconcile(self, j: _Job) -> bool:
        now = self.clock.now()
        b = self._bindings.get(j.job_type)
        window = timedelta(minutes=b.reconcile.auto_window_min if b and b.reconcile else 15)
        every = timedelta(seconds=b.reconcile.interval_sec if b and b.reconcile else 60)
        fn = self._reconcilers.get(j.job_type)
        if fn is not None and (j.last_reconcile is None or now >= j.last_reconcile + every):
            j.last_reconcile = now
            r = fn(self._view(j))
            self._s.reconcile_log.setdefault(j.id, []).append(r)
            if r.conclusion == "done":
                self._finish(j, "succeeded", "committed")
                return True
            if r.conclusion == "not_done":
                j.state, j.effect, j.enqueues = "queued", "none", j.enqueues + 1
                return True
            if r.conclusion == "partial":
                j.manual_review = True
                self._finish(j, "failed", "partial")
                return True
        if not j.manual_review and j.reconcile_started is not None and now >= j.reconcile_started + window:
            j.manual_review = True
            return True
        return False

    def _run_jobs(self) -> int:
        now = self.clock.now()
        n = 0
        for j in list(self._s.jobs.values()):
            if (j.state == "queued" and (j.not_before is None or j.not_before <= now)) or (
                j.state == "retry_wait" and j.next_run is not None and j.next_run <= now
            ):
                self._attempt(j)
            elif j.state == "reconciling":
                n += self._reconcile(j)
                continue
            else:
                continue
            n += 1
        return n

    # ---- 事件 ----

    def emit_in_tx(self, event: EventDraft) -> str:
        self._require_tx("emit_in_tx")
        self._touch()
        if not _EVENT_TYPE_RE.match(event.type) or event.type.split(".")[0] != event.source:
            raise ValueError(f"事件类型不合规或不属于模块 {event.source}：{event.type!r}")
        now = self.clock.now()
        self._s.event_seq += 1
        ev = t.Event(
            "evt_" + uuid7().hex,
            self._s.event_seq,
            event.type,
            event.schema_version,
            event.source,
            event.scope,
            event.subject,
            event.source_version,
            ensure_utc(event.occurred_at) if event.occurred_at else now,
            now,
            context.current().request_id,
            event.causation_id,
            event.correction_of,
            copy.deepcopy(event.minimal_change),
        )
        self._s.events.append(ev)
        return ev.event_id

    def subscribe(self, subscriber: str, event_type: str, handler: Callable[[t.Event], None]) -> None:
        self._subs.setdefault(subscriber, []).append((event_type, handler))
        self._cursor_start.setdefault(subscriber, self._s.event_seq)  # 新订阅者从“现在”起收

    def _deliver(self, subscriber: str, ev: t.Event) -> None:
        for pattern, handler in self._subs[subscriber]:
            if fnmatch.fnmatchcase(ev.type, pattern):
                handler(ev)

    def _deliver_events(self) -> int:
        n = 0
        for sub in list(self._subs):
            while True:
                cursor = self._s.cursors.get(sub, self._cursor_start[sub])
                nxt = next((e for e in self._s.events if e.sequence > cursor), None)
                if nxt is None:
                    break
                self._deliver(sub, nxt)
                self._s.cursors[sub] = nxt.sequence
                n += 1
        return n

    def redeliver(self, event_id: str) -> None:
        """模拟至少一次投递的重发：不查重，所有匹配的订阅者再收一遍。处理必须幂等。"""
        ev = next((e for e in self._s.events if e.event_id == event_id), None)
        if ev is None:
            raise KeyError(event_id)
        for sub in list(self._subs):
            self._deliver(sub, ev)

    # ---- 定时 ----

    def schedule(self, rule: ScheduleRuleSpec) -> str:
        b = self._binding(rule.capability_id)
        if b.mode != "async" or b.module != rule.owner_module:
            raise ValueError("定时规则只能指向本模块的后台（async）能力")
        self._s.rules[rule.rule_id] = rule
        return rule.rule_id

    def set_schedule_status(self, rule_id: str, status: str) -> None:
        self._touch()
        rule = self._s.rules.get(rule_id)
        if rule is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND)
        if rule.status == "ended" and status != "ended":
            raise AppError(ErrorCode.INVALID_REQUEST, details={"reason": "ended"})
        self._s.rules[rule_id] = replace(rule, status=cast(Any, status))

    def fire(self, rule_id: str, planned_at: datetime) -> Occurrence:
        """到了一个计划时刻。同一规则同一时刻只放一件，重复触发返回原记录。"""
        self._touch()
        at = ensure_utc(planned_at)
        rule = self._s.rules.get(rule_id)
        if rule is None:
            raise NotRegistered(f"定时规则 {rule_id!r} 没有登记")
        if (rule_id, at) in self._s.occurrences:
            return self._s.occurrences[(rule_id, at)]
        b = self._binding(rule.capability_id)
        active = rule.status == "active" and not (rule.valid_from and at < rule.valid_from)
        active = active and not (rule.valid_to and at > rule.valid_to)
        running = any(j.rule_id == rule_id and j.state not in _TERMINAL for j in self._s.jobs.values())
        if not active:
            occ = Occurrence(rule_id, at, "skipped_inactive")
        elif rule.overlap == "skip_new" and running:
            occ = Occurrence(rule_id, at, "skipped_overlap")
        else:
            assert b.lane is not None  # noqa: S101 - schedule() 已保证是 async
            ref = self._new_job(
                b.capability_id,
                b.module,
                {"ruleId": rule_id, "plannedAt": at.isoformat()},
                b.lane,
                None,
                None,
                None,
                None,
                rule_id,
            )
            occ = Occurrence(rule_id, at, "enqueued", ref)
        self._s.occurrences[(rule_id, at)] = occ
        return occ

    # ---- 手动推进 ----

    def drain(self, *, max_rounds: int = 100) -> int:
        """投递事件、跑到点的后台任务、做核对，直到没有进展。返回做了几件事。处理器里要写库就在事务里调用它。"""
        self._touch()
        total = 0
        for _ in range(max_rounds):
            done = self._deliver_events() + self._run_jobs()
            total += done
            if not done:
                return total
        raise RuntimeError("drain 超过轮数仍有进展：处理器可能在无限产生任务或事件")


@pytest.fixture
def execution_stub(access_stub: InMemoryAccess) -> Generator[InMemoryExecution]:
    """装入测试桩（时钟与 access_stub 共用）；测试结束恢复原来的实现，状态不外漏。"""
    stub = InMemoryExecution(access_stub.clock)
    previous = _provider.set_provider(stub)
    try:
        yield stub
    finally:
        _provider.set_provider(previous)


@pytest.fixture
def tx_session() -> Generator[Session]:
    """一个内存 SQLite 会话并设为当前事务：测试里 session.commit() / rollback() 模拟请求成功 / 失败。"""
    engine: Engine = create_engine("sqlite://", poolclass=StaticPool)
    session = Session(engine, expire_on_commit=False)
    with db.bind_session(session):
        yield session
    session.close()
    engine.dispose()
