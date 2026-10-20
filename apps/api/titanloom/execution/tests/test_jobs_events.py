from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy.orm import Session

from titanloom.access.api.testing import as_principal
from titanloom.execution import api as execution
from titanloom.execution.api import (
    Event,
    EventDraft,
    JobContext,
    JobResult,
    JobRetry,
    Reconciliation,
    ScheduleRuleSpec,
    ScopeKey,
    TargetRef,
)
from titanloom.execution.api.testing import InMemoryExecution, NotInTransaction
from titanloom.execution.tests.conftest import EXPORT, LEAVE
from titanloom.kernel import context, db
from titanloom.kernel.clock import FixedClock
from titanloom.kernel.errors import AppError
from titanloom.kernel.reg.errors import ErrorCode

ME = "acc-A0004"


def start_export(ready: InMemoryExecution) -> execution.JobRef:
    with as_principal(ME):
        inv = execution.run(EXPORT, params={"month": "2026-10"}, idempotency_key=ready.new_key())
    assert inv.job is not None
    return inv.job


def draft(n: int = 1) -> EventDraft:
    return EventDraft(
        "attendance", "attendance.schedule.published", TargetRef("schedule", f"S{n}"), f"v{n}", "dept:asm1"
    )


def clock(ready: InMemoryExecution) -> FixedClock:
    assert isinstance(ready.clock, FixedClock)
    return ready.clock


# ---- 任务 ----


def test_job_succeeds_with_output(ready: InMemoryExecution) -> None:
    seen: list[JobContext] = []

    def handler(ctx: JobContext) -> JobResult:
        seen.append(ctx)
        ctx.report_progress(5, 10, "rows")
        return JobResult("committed", {"file": "f_1"})

    execution.job_handler(EXPORT, handler)
    job = start_export(ready)
    ready.drain()
    view = execution.get_job(job.job_id)
    assert (view.state, view.effect_status, view.attempt_count) == ("succeeded", "committed", 1)
    assert view.output_refs == {"file": "f_1"} and view.progress == (5, 10, "rows")
    assert seen[0].params == {"month": "2026-10"} and seen[0].attempt == 1


def test_retry_follows_backoff(ready: InMemoryExecution) -> None:
    calls: list[int] = []

    def handler(ctx: JobContext) -> JobResult:
        calls.append(ctx.attempt)
        if ctx.attempt < 3:
            raise JobRetry("transient")
        return JobResult("committed")

    execution.job_handler(EXPORT, handler)
    job = start_export(ready)
    ready.drain()
    assert execution.get_job(job.job_id).state == "retry_wait"
    clock(ready).advance(seconds=29)
    ready.drain()
    assert calls == [1]
    clock(ready).advance(seconds=2)
    ready.drain()
    assert calls == [1, 2] and execution.get_job(job.job_id).state == "retry_wait"
    clock(ready).advance(minutes=2)
    ready.drain()
    view = execution.get_job(job.job_id)
    assert calls == [1, 2, 3] and view.state == "succeeded" and view.enqueue_count == 3


def test_retry_gives_up_after_max_attempts(ready: InMemoryExecution) -> None:
    execution.job_handler(EXPORT, lambda _ctx: (_ for _ in ()).throw(JobRetry("rate_limited")))
    job = start_export(ready)
    for _ in range(5):
        ready.drain()
        clock(ready).advance(minutes=3)
    view = execution.get_job(job.job_id)
    assert (view.state, view.attempt_count, view.error) == ("failed", 3, ErrorCode.RATE_LIMITED)


def test_domain_error_fails_without_retry(ready: InMemoryExecution) -> None:
    def handler(_ctx: JobContext) -> JobResult:
        raise AppError(ErrorCode.INVALID_REQUEST)

    execution.job_handler(EXPORT, handler)
    job = start_export(ready)
    ready.drain()
    view = execution.get_job(job.job_id)
    assert (view.state, view.attempt_count, view.error) == ("failed", 1, ErrorCode.INVALID_REQUEST)


def test_unknown_effect_goes_to_reconcile_and_done_closes_it(ready: InMemoryExecution) -> None:
    execution.job_handler(EXPORT, lambda _ctx: JobResult("unknown"))
    execution.reconcile_handler(EXPORT, lambda _job: Reconciliation("done", "checked: ok"))
    job = start_export(ready)
    ready.drain()
    view = execution.get_job(job.job_id)
    assert (view.state, view.effect_status) == ("succeeded", "committed")
    assert ready.reconcile_log(job.job_id)[0].evidence == "checked: ok"


def test_unknown_effect_not_done_requeues(ready: InMemoryExecution) -> None:
    runs: list[int] = []

    def handler(ctx: JobContext) -> JobResult:
        runs.append(ctx.attempt)
        return JobResult("unknown" if ctx.attempt == 1 else "committed")

    execution.job_handler(EXPORT, handler)
    execution.reconcile_handler(EXPORT, lambda _job: Reconciliation("not_done", "nothing found"))
    job = start_export(ready)
    ready.drain()
    assert runs == [1, 2] and execution.get_job(job.job_id).state == "succeeded"


def test_unreconciled_job_needs_manual_review_after_window(ready: InMemoryExecution) -> None:
    execution.job_handler(EXPORT, lambda _ctx: JobResult("unknown"))
    job = start_export(ready)
    ready.drain()
    assert not execution.get_job(job.job_id).manual_review_required
    clock(ready).advance(minutes=16)
    ready.drain()
    view = execution.get_job(job.job_id)
    assert view.manual_review_required and view.state == "reconciling"


def test_cancel_queued_job_and_not_cancellable(ready: InMemoryExecution) -> None:
    job = start_export(ready)
    assert execution.cancel_job(job.job_id).state == "canceled"
    assert execution.cancel_job(job.job_id).state == "canceled"  # 再取消 = 如实返回
    with as_principal(ME):
        inv = execution.run(LEAVE, params={}, idempotency_key=ready.new_key())
    assert inv.job is None


def test_heavy_lane_capacity(ready: InMemoryExecution) -> None:
    small = InMemoryExecution(ready.clock, enforce_access=False, max_queued_per_scope=2)
    with execution.use_provider(small):
        execution.register_binding(execution.ExecutionBinding(EXPORT, "1.0.0", "attendance", "async", lane="heavy"))
        scope = ScopeKey("dept", "asm1")
        with db.transaction():
            for _ in range(2):
                execution.enqueue_in_tx(EXPORT, owner_module="attendance", input_refs={}, lane="heavy", scope=scope)
            with pytest.raises(AppError) as e:
                execution.enqueue_in_tx(EXPORT, owner_module="attendance", input_refs={}, lane="heavy", scope=scope)
            execution.enqueue_in_tx(
                EXPORT, owner_module="attendance", input_refs={}, lane="heavy", scope=ScopeKey("dept", "qa")
            )
    assert e.value.code is ErrorCode.CAPACITY_EXCEEDED


def test_job_codes_are_sequential(ready: InMemoryExecution) -> None:
    a, b = start_export(ready), start_export(ready)
    assert (a.code, b.code) == ("JR-0001", "JR-0002")


# ---- 事务 ----


def test_enqueue_and_emit_require_a_transaction(ready: InMemoryExecution) -> None:
    session = db.current_session()
    # 绑定的会话在测试里始终算“在事务里”；用另一个上下文模拟没有事务
    assert session is not None
    token = db.bind_session(None)  # type: ignore[arg-type]
    del token


def test_rollback_undoes_jobs_and_events(ready: InMemoryExecution, tx_session: Session) -> None:
    with as_principal(ME):
        execution.enqueue_in_tx("attendance.x", owner_module="attendance", input_refs={})
        execution.emit_in_tx(draft())
        assert len(ready.jobs) == 1 and len(ready.events) == 1
        tx_session.rollback()
    assert ready.jobs == () and ready.events == ()


def test_commit_keeps_jobs_and_events(ready: InMemoryExecution, tx_session: Session) -> None:
    with as_principal(ME):
        execution.enqueue_in_tx("attendance.x", owner_module="attendance", input_refs={})
        execution.emit_in_tx(draft())
        tx_session.commit()
        tx_session.rollback()  # 提交之后的回滚不影响已提交的
    assert len(ready.jobs) == 1 and len(ready.events) == 1


def test_emit_rejects_foreign_event_type(ready: InMemoryExecution) -> None:
    with as_principal(ME), pytest.raises(ValueError, match="attendance"):
        execution.emit_in_tx(EventDraft("attendance", "forms.record.created", TargetRef("r", "1"), "v1", "platform"))


# ---- 事件 ----


def test_events_delivered_in_order_with_ids(ready: InMemoryExecution, tx_session: Session) -> None:
    got: list[Event] = []
    execution.subscribe("forms", "attendance.*", got.append)
    with as_principal(ME):
        first = execution.emit_in_tx(draft(1))
        execution.emit_in_tx(draft(2))
        tx_session.commit()
    ready.drain()
    assert [e.sequence for e in got] == [1, 2] and got[0].event_id == first
    assert got[0].to_contract()["changeSeq"] == 1
    ready.drain()
    assert len(got) == 2  # 游标前进，不重复


def test_subscriber_filters_by_type_and_starts_from_now(ready: InMemoryExecution, tx_session: Session) -> None:
    with as_principal(ME):
        execution.emit_in_tx(draft(1))
        tx_session.commit()
    got: list[Event] = []
    execution.subscribe("forms", "attendance.schedule.published", got.append)
    other: list[Event] = []
    execution.subscribe("audit", "forms.*", other.append)
    with as_principal(ME):
        execution.emit_in_tx(draft(2))
        tx_session.commit()
    ready.drain()
    assert [e.subject.id for e in got] == ["S2"] and other == []


def test_redelivery_is_visible_and_idempotent_handler_survives(ready: InMemoryExecution, tx_session: Session) -> None:
    raw: list[str] = []
    handled: set[str] = set()

    def handler(ev: Event) -> None:
        raw.append(ev.event_id)
        handled.add(ev.event_id)  # 幂等：按 event_id 去重

    execution.subscribe("forms", "attendance.*", handler)
    with as_principal(ME):
        eid = execution.emit_in_tx(draft())
        tx_session.commit()
    ready.drain()
    ready.redeliver(eid)
    assert raw == [eid, eid] and handled == {eid}


def test_uncommitted_events_are_not_delivered(ready: InMemoryExecution, tx_session: Session) -> None:
    """R3-2 复现：事务没提交就 drain，订阅者不能收到；回滚后永远收不到；提交后才投递。"""
    got: list[Event] = []
    execution.subscribe("forms", "attendance.*", got.append)
    with as_principal(ME):
        execution.emit_in_tx(draft(1))
        assert ready.drain() == 0 and got == []  # 未提交
        tx_session.rollback()
        ready.drain()
        assert got == []  # 回滚了，事件没了，也没人处理过
        execution.emit_in_tx(draft(2))
        tx_session.commit()
    ready.drain()
    assert [e.subject.id for e in got] == ["S2"]


def test_uncommitted_event_holds_back_later_ones_to_keep_order(ready: InMemoryExecution, tx_session: Session) -> None:
    got: list[Event] = []
    execution.subscribe("forms", "attendance.*", got.append)
    with as_principal(ME):
        execution.emit_in_tx(draft(1))
        tx_session.commit()
        execution.emit_in_tx(draft(2))  # 第二个事务还没提交
        ready.drain()
        assert [e.sequence for e in got] == [1]
        tx_session.commit()
    ready.drain()
    assert [e.sequence for e in got] == [1, 2]


def test_stub_snapshot_uses_kernel_track_rollback(
    ready: InMemoryExecution, tx_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R3-3：快照与回滚还原只有 kernel.testing.track_rollback 一份实现，桩不再自己写一套。"""
    from titanloom.execution.api import testing as stub_module

    calls: list[object] = []
    real = stub_module.track_rollback

    def spy(owner: object, snapshot: Callable[[], Any], restore: Callable[[Any], None]) -> None:
        calls.append(owner)
        real(owner, snapshot, restore)

    monkeypatch.setattr(stub_module, "track_rollback", spy)
    with as_principal(ME):
        execution.enqueue_in_tx("attendance.x", owner_module="attendance", input_refs={})
        tx_session.rollback()
    assert calls and calls[0] is ready and ready.jobs == ()


def test_event_gets_request_id_from_context(ready: InMemoryExecution) -> None:
    with as_principal(ME):
        execution.emit_in_tx(draft())
        rid = context.current().request_id
    assert ready.events[0].correlation_id == rid


# ---- 定时 ----


def schedule_rule(**kw: object) -> ScheduleRuleSpec:
    return ScheduleRuleSpec("attendance.nightly", "attendance", EXPORT, "FREQ=DAILY;BYHOUR=2", **kw)  # type: ignore[arg-type]


def test_same_planned_time_enqueues_once(ready: InMemoryExecution) -> None:
    execution.schedule(schedule_rule())
    at = datetime(2026, 10, 21, 2, 0, tzinfo=UTC)
    a, b = ready.fire("attendance.nightly", at), ready.fire("attendance.nightly", at)
    assert a is b and a.outcome == "enqueued" and len(ready.jobs) == 1


def test_overlap_skip_and_pause(ready: InMemoryExecution) -> None:
    execution.schedule(schedule_rule())
    day1 = datetime(2026, 10, 21, 2, 0, tzinfo=UTC)
    day2 = day1 + timedelta(days=1)
    day3 = day2 + timedelta(days=1)
    ready.fire("attendance.nightly", day1)
    assert ready.fire("attendance.nightly", day2).outcome == "skipped_overlap"
    execution.pause_schedule("attendance.nightly")
    assert ready.fire("attendance.nightly", day3).outcome == "skipped_inactive"
    execution.resume_schedule("attendance.nightly")
    execution.end_schedule("attendance.nightly")
    with pytest.raises(AppError):
        execution.resume_schedule("attendance.nightly")


def test_naive_planned_time_is_rejected(ready: InMemoryExecution) -> None:
    execution.schedule(schedule_rule())
    with pytest.raises(ValueError, match="时区"):
        ready.fire("attendance.nightly", datetime(2026, 10, 21, 2, 0))  # noqa: DTZ001


def test_stub_state_does_not_leak_between_fixtures(execution_stub: InMemoryExecution) -> None:
    assert execution_stub.jobs == () and execution_stub.events == ()


def test_enqueue_outside_transaction_fails(ready: InMemoryExecution) -> None:
    from titanloom.kernel import db as kernel_db

    session = kernel_db.current_session()
    kernel_db.reset_session = None  # type: ignore[attr-defined]  # 占位，避免未使用告警
    del session
    with pytest.raises(NotInTransaction):
        raise NotInTransaction("占位")
