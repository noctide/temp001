"""execution.api：别的模块唯一能引用的 execution 入口（命令与任务 12）。

    from titanloom.execution.api import prepare, submit, enqueue_in_tx, emit_in_tx

实现在启动时装入（见 `_provider`）。登记类的调用（register_binding / job_handler / reconcile_handler /
version_validator / subscribe / schedule）放在模块自己的启动函数里，与 access.api.register 同一处。
本轮不含 HTTP 路由与运行中心。
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any

from titanloom.access.api import Target
from titanloom.execution.api import _provider
from titanloom.execution.api._provider import ExecutionApi, set_provider, use_provider
from titanloom.execution.api.types import (
    Confirmation,
    Event,
    EventDraft,
    ExecutionBinding,
    Invocation,
    JobContext,
    JobRef,
    JobResult,
    JobRetry,
    JobView,
    Lane,
    Misfire,
    Occurrence,
    PrepareResult,
    PreviewSpec,
    ReconcilePolicy,
    Reconciliation,
    RetryPolicy,
    ScheduleRuleSpec,
    ScopeKey,
    TargetRef,
    command_id,
    command_uuid,
)
from titanloom.kernel import db
from titanloom.kernel.errors import AppError
from titanloom.kernel.reg.errors import ErrorCode

__all__ = [
    "Confirmation",
    "Event",
    "EventDraft",
    "ExecutionApi",
    "ExecutionBinding",
    "Invocation",
    "JobContext",
    "JobRef",
    "JobResult",
    "JobRetry",
    "JobView",
    "Misfire",
    "Occurrence",
    "PrepareResult",
    "PreviewSpec",
    "ReconcilePolicy",
    "Reconciliation",
    "RetryPolicy",
    "ScheduleRuleSpec",
    "ScopeKey",
    "TargetRef",
    "cancel",
    "cancel_job",
    "command_id",
    "command_uuid",
    "confirm",
    "emit_in_tx",
    "end_schedule",
    "enqueue_in_tx",
    "get_job",
    "job_handler",
    "pause_schedule",
    "prepare",
    "reconcile_handler",
    "register_binding",
    "resume_schedule",
    "run",
    "schedule",
    "set_provider",
    "submit",
    "subscribe",
    "use_provider",
    "version_validator",
]


def register_binding(binding: ExecutionBinding) -> None:
    """登记能力的执行方式。同样内容重复登记没有影响；同一能力内容不同则报错。"""
    _provider.provider().register_binding(binding)


def job_handler(job_type: str, handler: Callable[[JobContext], JobResult]) -> None:
    """登记“拿到任务怎么干”。任务类型就是能力编号，或 enqueue_in_tx 用的类型名。"""
    _provider.provider().job_handler(job_type, handler)


def reconcile_handler(job_type: str, handler: Callable[[JobView], Reconciliation]) -> None:
    """登记领域的核对方法：副作用不确定时由平台调用，结论必须附证据。"""
    _provider.provider().reconcile_handler(job_type, handler)


def version_validator(capability_id: str, check: Callable[[TargetRef | None, str], bool]) -> None:
    """登记“目标版本还是不是准备时的那个”。提交时返回 False 则拒绝，要求重新准备。"""
    _provider.provider().version_validator(capability_id, check)


def prepare(
    capability_id: str,
    *,
    params: Mapping[str, Any],
    idempotency_key: str,
    target: TargetRef | None = None,
    expected_version: str | None = None,
    preview: PreviewSpec | None = None,
    scope: ScopeKey | None = None,
    access_target: Target | None = None,
) -> PrepareResult:
    """准备一条命令：固定参数与版本、算摘要、查权限、存预览。主体取自 kernel.context。

    同键同内容返回原命令，同键不同内容 IDEMPOTENCY_CONFLICT。预览由领域算好传入；
    预览未知（estimate_status=unknown）时一定要确认。
    """
    return _provider.provider().prepare(
        capability_id,
        params=params,
        idempotency_key=idempotency_key,
        target=target,
        expected_version=expected_version,
        preview=preview,
        scope=scope,
        access_target=access_target,
    )


def confirm(command_id: str, *, command_digest: str) -> Confirmation:
    """确认。只给 HTTP 确认界面调用：只有命令本人（人）能确认，管家、服务身份、代办一律 ACCESS_DENIED。"""
    return _provider.provider().confirm(command_id, command_digest=command_digest)


def submit(command_id: str, *, idempotency_key: str) -> Invocation:
    """提交 = 一次写完：复查权限与版本、消费确认、写调用与任务。同一事务。重复提交返回原调用。"""
    return _provider.provider().submit(command_id, idempotency_key=idempotency_key)


def run(
    capability_id: str,
    *,
    params: Mapping[str, Any],
    idempotency_key: str,
    target: TargetRef | None = None,
    expected_version: str | None = None,
    preview: PreviewSpec | None = None,
    scope: ScopeKey | None = None,
    access_target: Target | None = None,
) -> Invocation:
    """低影响操作：同一请求、同一事务里 prepare + submit，参数与 prepare 完全相同。

    需要确认的能力（登记要求确认，或预览未知）一律 CONFIRMATION_REQUIRED，整个事务回滚，什么也不留。
    """
    with db.transaction():
        prepared = prepare(
            capability_id,
            params=params,
            idempotency_key=idempotency_key,
            target=target,
            expected_version=expected_version,
            preview=preview,
            scope=scope,
            access_target=access_target,
        )
        if prepared.confirmation_required:
            raise AppError(ErrorCode.CONFIRMATION_REQUIRED, details={"capabilityId": capability_id})
        return submit(prepared.command_id, idempotency_key=idempotency_key)


def cancel(command_id: str) -> None:
    """取消还没接收的命令。已接收的要取消任务（cancel_job）。"""
    _provider.provider().cancel(command_id)


def cancel_job(job_id: uuid.UUID) -> JobView:
    """请求取消任务：没开始直接取消，运行中在检查点停；已完成的如实返回完成。"""
    return _provider.provider().cancel_job(job_id)


def enqueue_in_tx(
    job_type: str,
    *,
    owner_module: str,
    input_refs: Mapping[str, str],
    lane: Lane = "light",
    scope: ScopeKey | None = None,
    not_before: datetime | None = None,
    invocation_id: str | None = None,
) -> JobRef:
    """在调用者自己的事务里放一个后台任务；事务回滚则任务也没有。不在事务里报错。"""
    return _provider.provider().enqueue_in_tx(
        job_type,
        owner_module=owner_module,
        input_refs=input_refs,
        lane=lane,
        scope=scope,
        not_before=not_before,
        invocation_id=invocation_id,
    )


def emit_in_tx(event: EventDraft) -> str:
    """在调用者自己的事务里写一条事件到发件箱，返回事件编号。不在事务里报错。"""
    return _provider.provider().emit_in_tx(event)


def schedule(rule: ScheduleRuleSpec) -> str:
    """登记或修改定时规则（按 rule_id）。返回规则编号。"""
    return _provider.provider().schedule(rule)


def pause_schedule(rule_id: str) -> None:
    _provider.provider().set_schedule_status(rule_id, "paused")


def resume_schedule(rule_id: str) -> None:
    _provider.provider().set_schedule_status(rule_id, "active")


def end_schedule(rule_id: str) -> None:
    _provider.provider().set_schedule_status(rule_id, "ended")


def get_job(job_id: uuid.UUID) -> JobView:
    return _provider.provider().get_job(job_id)


def subscribe(subscriber: str, event_type: str, handler: Callable[[Event], None]) -> None:
    """订阅事件（event_type 可带 * 通配，如 attendance.*）。至少一次投递，handler 必须幂等（按 event_id 去重）。"""
    _provider.provider().subscribe(subscriber, event_type, handler)
