from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from uuid import uuid4

import pytest

from titanloom.access.api.testing import InMemoryAccess, as_principal
from titanloom.access.api.types import Whoami
from titanloom.execution import api as execution
from titanloom.execution.api import PreviewSpec, TargetRef, command_id, command_uuid
from titanloom.execution.api.testing import InMemoryExecution, NotRegistered, key_at
from titanloom.execution.tests.conftest import EXPORT, LEAVE, PUBLISH
from titanloom.kernel.clock import FixedClock
from titanloom.kernel.errors import AppError
from titanloom.kernel.reg.errors import ErrorCode

ME = "acc-A0004"


def code_of(exc: pytest.ExceptionInfo[AppError]) -> ErrorCode:
    return exc.value.code


def test_prepare_returns_ready_for_auto_and_awaiting_for_confirm(ready: InMemoryExecution) -> None:
    with as_principal(ME):
        a = execution.prepare(LEAVE, params={"days": 1}, idempotency_key=ready.new_key())
        b = execution.prepare(PUBLISH, params={"month": "2026-10"}, idempotency_key=ready.new_key())
    assert (a.state, a.confirmation_required, a.effective_policy) == ("ready", False, "allow")
    assert (b.state, b.confirmation_required, b.effective_policy) == ("awaiting_confirmation", True, "confirm")
    assert a.command_id.startswith("cmd_") and len(a.command_id) == 36
    assert command_id(command_uuid(a.command_id)) == a.command_id


def test_same_key_same_request_returns_same_command(ready: InMemoryExecution) -> None:
    key = ready.new_key()
    with as_principal(ME):
        a = execution.prepare(LEAVE, params={"days": 1}, idempotency_key=key)
        b = execution.prepare(LEAVE, params={"days": 1}, idempotency_key=key)
        with pytest.raises(AppError) as e:
            execution.prepare(LEAVE, params={"days": 2}, idempotency_key=key)
    assert a.command_id == b.command_id
    assert code_of(e) is ErrorCode.IDEMPOTENCY_CONFLICT


def test_key_window(ready: InMemoryExecution) -> None:
    now = ready.clock.now()
    with as_principal(ME):
        with pytest.raises(AppError) as old:
            execution.prepare(LEAVE, params={}, idempotency_key=key_at(now - timedelta(hours=25)))
        with pytest.raises(AppError) as future:
            execution.prepare(LEAVE, params={}, idempotency_key=key_at(now + timedelta(minutes=6)))
        with pytest.raises(AppError) as junk:
            execution.prepare(LEAVE, params={}, idempotency_key="not-a-uuid")
        execution.prepare(LEAVE, params={}, idempotency_key=key_at(now - timedelta(hours=23)))
    assert code_of(old) is ErrorCode.IDEMPOTENCY_WINDOW_EXPIRED
    assert code_of(future) is ErrorCode.INPUT_VALIDATION_FAILED
    assert code_of(junk) is ErrorCode.INPUT_VALIDATION_FAILED


def test_access_is_checked(ready: InMemoryExecution) -> None:
    with as_principal("acc-B0001"), pytest.raises(AppError) as e:  # 没授权
        execution.prepare(LEAVE, params={}, idempotency_key=ready.new_key())
    assert code_of(e) is ErrorCode.ACCESS_DENIED


def test_unregistered_capability(ready: InMemoryExecution) -> None:
    with as_principal(ME), pytest.raises(NotRegistered):
        execution.prepare("attendance.nothing.here", params={}, idempotency_key=ready.new_key())


def test_submit_without_confirmation_is_refused(ready: InMemoryExecution) -> None:
    key = ready.new_key()
    with as_principal(ME):
        p = execution.prepare(PUBLISH, params={}, idempotency_key=key)
        with pytest.raises(AppError) as e:
            execution.submit(p.command_id, idempotency_key=key)
    assert code_of(e) is ErrorCode.CONFIRMATION_REQUIRED


def test_confirm_then_submit_consumes_confirmation(ready: InMemoryExecution) -> None:
    key = ready.new_key()
    with as_principal(ME):
        p = execution.prepare(PUBLISH, params={}, idempotency_key=key)
        c = execution.confirm(p.command_id, command_digest=p.command_digest)
        assert c.confirmed_by == ME and c.command_digest == p.command_digest
        inv = execution.submit(p.command_id, idempotency_key=key)
        again = execution.submit(p.command_id, idempotency_key=key)  # 重复提交 = 同一回执
    used = ready.confirmation_of(p.command_id)
    assert used is not None and used.consumed and used.consumed_by_invocation == inv.invocation_id
    assert again.invocation_id == inv.invocation_id and len(ready.invocations) == 1
    assert ready.command_state(p.command_id) == "accepted"


def test_same_confirmation_cannot_be_consumed_twice(ready: InMemoryExecution) -> None:
    """一份确认绑定一条命令、只能用一次：别的命令拿不到它。"""
    k1, k2 = ready.new_key(), ready.new_key()
    with as_principal(ME):
        p1 = execution.prepare(PUBLISH, params={"n": 1}, idempotency_key=k1)
        p2 = execution.prepare(PUBLISH, params={"n": 1}, idempotency_key=k2)
        execution.confirm(p1.command_id, command_digest=p1.command_digest)
        execution.submit(p1.command_id, idempotency_key=k1)
        with pytest.raises(AppError) as unconfirmed:
            execution.submit(p2.command_id, idempotency_key=k2)
        with pytest.raises(AppError) as stale:
            execution.confirm(p2.command_id, command_digest=p1.command_digest)  # 摘要绑定命令
    first = ready.confirmation_of(p1.command_id)
    assert first is not None and first.consumed
    assert code_of(unconfirmed) is ErrorCode.CONFIRMATION_REQUIRED
    assert code_of(stale) is ErrorCode.RESOURCE_VERSION_CONFLICT
    assert ready.confirmation_of(p2.command_id) is None
    assert len(ready.invocations) == 1


def test_butler_cannot_confirm(ready: InMemoryExecution, access_stub: InMemoryAccess) -> None:
    key = ready.new_key()
    with as_principal(ME):
        p = execution.prepare(PUBLISH, params={}, idempotency_key=key)
    with as_principal("svc-butler"), pytest.raises(AppError) as service:  # 服务身份
        execution.confirm(p.command_id, command_digest=p.command_digest)
    with as_principal("acc-H0012"), pytest.raises(AppError) as other:  # 别人
        execution.confirm(p.command_id, command_digest=p.command_digest)

    real = access_stub.whoami

    def acting() -> Whoami:  # 代办：whoami 带 acting_for
        return replace(real(), acting_for=ME)

    access_stub.whoami = acting  # type: ignore[method-assign]
    try:
        with as_principal(ME), pytest.raises(AppError) as proxy:
            execution.confirm(p.command_id, command_digest=p.command_digest)
    finally:
        access_stub.whoami = real  # type: ignore[method-assign]
    assert {code_of(service), code_of(other), code_of(proxy)} == {ErrorCode.ACCESS_DENIED}
    assert ready.confirmation_of(p.command_id) is None


def test_digest_mismatch_is_rejected(ready: InMemoryExecution) -> None:
    with as_principal(ME):
        p = execution.prepare(PUBLISH, params={}, idempotency_key=ready.new_key())
        with pytest.raises(AppError) as e:
            execution.confirm(p.command_id, command_digest="sha256:" + "0" * 64)
    assert code_of(e) is ErrorCode.RESOURCE_VERSION_CONFLICT


def test_preview_goes_into_digest_and_unknown_forces_confirm(ready: InMemoryExecution) -> None:
    a = PreviewSpec("attendance.preview.leave", "single", "exact", counts={"people": 1})
    b = PreviewSpec("attendance.preview.leave", "single", "exact", counts={"people": 2})
    u = PreviewSpec("attendance.preview.leave", "many", "unknown", affected=(TargetRef("leave", "L1"),))
    with as_principal(ME):
        pa = execution.prepare(LEAVE, params={}, idempotency_key=ready.new_key(), preview=a)
        pb = execution.prepare(LEAVE, params={}, idempotency_key=ready.new_key(), preview=b)
        pu = execution.prepare(LEAVE, params={}, idempotency_key=ready.new_key(), preview=u)
    assert pa.command_digest != pb.command_digest
    assert pu.confirmation_required and pu.effective_policy == "confirm"
    assert pa.to_contract("req")["data"]["preview"]["messageKey"] == "attendance.preview.leave"


def test_command_expires_after_15_minutes(ready: InMemoryExecution) -> None:
    key = ready.new_key()
    assert isinstance(ready.clock, FixedClock)
    with as_principal(ME):
        p = execution.prepare(LEAVE, params={}, idempotency_key=key)
        ready.clock.advance(minutes=15)
        with pytest.raises(AppError) as e:
            execution.submit(p.command_id, idempotency_key=key)
    assert code_of(e) is ErrorCode.COMMAND_EXPIRED
    assert ready.command_state(p.command_id) == "expired"


def test_submit_key_must_match(ready: InMemoryExecution) -> None:
    with as_principal(ME):
        p = execution.prepare(LEAVE, params={}, idempotency_key=ready.new_key())
        with pytest.raises(AppError) as e:
            execution.submit(p.command_id, idempotency_key=ready.new_key())
    assert code_of(e) is ErrorCode.IDEMPOTENCY_CONFLICT


def test_other_principal_cannot_touch_command(ready: InMemoryExecution) -> None:
    key = ready.new_key()
    with as_principal(ME):
        p = execution.prepare(LEAVE, params={}, idempotency_key=key)
    with as_principal("acc-H0012"), pytest.raises(AppError) as e:
        execution.submit(p.command_id, idempotency_key=key)
    assert code_of(e) is ErrorCode.ACCESS_DENIED


def test_cancel_before_submit(ready: InMemoryExecution) -> None:
    key = ready.new_key()
    with as_principal(ME):
        p = execution.prepare(LEAVE, params={}, idempotency_key=key)
        execution.cancel(p.command_id)
        with pytest.raises(AppError) as e:
            execution.submit(p.command_id, idempotency_key=key)
    assert code_of(e) is ErrorCode.COMMAND_EXPIRED


def test_version_conflict_on_submit(ready: InMemoryExecution) -> None:
    execution.version_validator(LEAVE, lambda _target, version: version == "v2")
    ok, bad = ready.new_key(), ready.new_key()
    leave = TargetRef("leave", "L1")
    with as_principal(ME):
        p1 = execution.prepare(LEAVE, params={}, idempotency_key=ok, target=leave, expected_version="v2")
        p2 = execution.prepare(LEAVE, params={}, idempotency_key=bad, target=leave, expected_version="v1")
        execution.submit(p1.command_id, idempotency_key=ok)
        with pytest.raises(AppError) as e:
            execution.submit(p2.command_id, idempotency_key=bad)
    assert code_of(e) is ErrorCode.RESOURCE_VERSION_CONFLICT


def test_expected_version_without_validator_is_not_silently_ignored(ready: InMemoryExecution) -> None:
    """R3-1：给了 expected_version 但能力没登记校验器，不能让提交悄悄跳过版本检查。"""
    with as_principal(ME), pytest.raises(NotRegistered, match="version_validator"):
        execution.prepare(
            LEAVE,
            params={},
            idempotency_key=ready.new_key(),
            target=TargetRef("leave", "L1"),
            expected_version="v1",
        )


def test_expected_version_latest_is_rejected(ready: InMemoryExecution) -> None:
    with as_principal(ME), pytest.raises(AppError) as e:
        execution.prepare(LEAVE, params={}, idempotency_key=ready.new_key(), expected_version="latest")
    assert code_of(e) is ErrorCode.INPUT_VALIDATION_FAILED


def test_run_is_prepare_plus_submit(ready: InMemoryExecution) -> None:
    with as_principal(ME):
        inv = execution.run(LEAVE, params={"days": 1}, idempotency_key=ready.new_key())
    assert inv.receipt_kind == "sync_result" and inv.job is None
    assert ready.command_state(inv.command_id) == "accepted"


def test_run_on_confirm_binding_raises(ready: InMemoryExecution) -> None:
    with as_principal(ME), pytest.raises(AppError) as e:
        execution.run(PUBLISH, params={}, idempotency_key=ready.new_key())
    assert code_of(e) is ErrorCode.CONFIRMATION_REQUIRED
    assert e.value.details == {"capabilityId": PUBLISH}
    assert ready.invocations == ()


def test_run_async_returns_job(ready: InMemoryExecution) -> None:
    with as_principal(ME):
        inv = execution.run(EXPORT, params={"month": "2026-10"}, idempotency_key=ready.new_key())
    assert inv.receipt_kind == "async_receipt" and inv.job is not None
    assert inv.job.code == "JR-0001"
    assert execution.get_job(inv.job.job_id).state == "queued"


def test_get_job_unknown(ready: InMemoryExecution) -> None:
    with pytest.raises(AppError) as e:
        execution.get_job(uuid4())
    assert code_of(e) is ErrorCode.RESOURCE_NOT_FOUND
