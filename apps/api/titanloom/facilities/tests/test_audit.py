from __future__ import annotations

from dataclasses import replace

import pytest
from sqlalchemy.orm import Session

from titanloom.access.api import Target
from titanloom.access.api.testing import Cond, InMemoryAccess, as_principal
from titanloom.facilities import api as fac
from titanloom.facilities.api.testing import InMemoryFacilities, NotInTransaction
from titanloom.kernel import context, db
from titanloom.kernel.errors import AppError
from titanloom.kernel.reg.errors import ErrorCode

LEAVE = fac.ObjectRef("leave", "LV-0001")
# 装配一部（asm1）的请假单：真实归属用于数据范围判定
LEAVE_TARGET = Target("leave", "LV-0001", dept_id="asm1")


def _draft(result: fac.AuditResult = "succeeded", **kw: object) -> fac.AuditDraft:
    return fac.AuditDraft("attendance.leave.create", "1.0.0", LEAVE, result, **kw)  # pyright: ignore[reportArgumentType]


def test_audit_must_be_written_inside_a_transaction(
    access_stub: InMemoryAccess, facilities_stub: InMemoryFacilities
) -> None:
    with pytest.raises(NotInTransaction):
        fac.audit_in_tx(_draft())


def test_audit_fills_who_when_and_policy(ready: InMemoryFacilities, access_stub: InMemoryAccess) -> None:
    with as_principal("acc-A0004"), db.transaction():
        fac.audit_in_tx(_draft(before_digest=fac.digest({"days": 1}), after_digest=fac.digest({"days": 2})))
    ev = ready.audits[-1]
    assert ev.principal_id == "acc-A0004"
    assert ev.executor_id is None
    assert ev.caller_type == "human"
    assert ev.occurred_at.tzinfo is not None
    assert ev.policy_version_set["policyRev"] >= 0
    assert ev.before_digest is not None and ev.before_digest.startswith("sha256:")
    assert ev.before_digest != ev.after_digest


def test_audit_without_principal_is_system(ready: InMemoryFacilities) -> None:
    token = context.bind(context.RequestContext("req_x", job_id="job-1"))
    try:
        with db.transaction():
            fac.audit_in_tx(_draft())
    finally:
        context.reset(token)
    ev = ready.audits[-1]
    assert (ev.principal_id, ev.caller_type, ev.job_id) == ("system", "job", "job-1")


def test_audit_rolls_back_with_the_business_change(ready: InMemoryFacilities, tx_session: Session) -> None:
    with as_principal("acc-A0004"), db.transaction():
        fac.audit_in_tx(_draft())
    tx_session.rollback()
    assert ready.audits == ()
    with as_principal("acc-A0004"), db.transaction():
        fac.audit_in_tx(_draft())
    assert len(ready.audits) == 1


def test_hash_chain_detects_tampering(ready: InMemoryFacilities) -> None:
    with as_principal("acc-A0004"), db.transaction():
        for _ in range(3):
            fac.audit_in_tx(_draft())
    assert ready.audits[0].prev_hash is None
    assert ready.audits[1].prev_hash == ready.audits[0].hash
    assert ready.verify_chain()
    ready.tamper(1, reason="偷偷改的")
    assert not ready.verify_chain()


def test_reading_audit_needs_the_capability_and_is_itself_audited(ready: InMemoryFacilities) -> None:
    with as_principal("acc-A0004"), db.transaction():
        fac.audit_in_tx(_draft())
    with as_principal("acc-A0004"), pytest.raises(AppError) as err:
        fac.audit_for(LEAVE)
    assert err.value.code == ErrorCode.ACCESS_DENIED
    with as_principal("acc-H0012"):
        page = fac.audit_for(LEAVE)
    assert [e.capability_id for e in page.items] == ["attendance.leave.create"]
    seen = ready.audits[-1]
    assert (seen.capability_id, seen.principal_id, seen.target) == (fac.AUDIT_READ_CAPABILITY, "acc-H0012", LEAVE)
    with as_principal("acc-H0012"):
        again = fac.audit_for(LEAVE)
    assert len(again.items) == 2  # 上一次的查看也在里面


def test_audit_for_pages_newest_first_and_filters_by_object(ready: InMemoryFacilities) -> None:
    other = fac.ObjectRef("leave", "LV-0002")
    with as_principal("acc-A0004"), db.transaction():
        for i in range(5):
            fac.audit_in_tx(_draft(reason=f"n{i}"))
        fac.audit_in_tx(fac.AuditDraft("attendance.leave.create", "1.0.0", other, "succeeded"))
    with as_principal("acc-H0012"):
        first = fac.audit_for(LEAVE, limit=2)
        assert [e.reason for e in first.items] == ["n4", "n3"]
        assert first.next_cursor is not None
        second = fac.audit_for(LEAVE, cursor=first.next_cursor, limit=2)
        assert [e.reason for e in second.items] == ["n2", "n1"]
        with pytest.raises(AppError) as err:
            fac.audit_for(LEAVE, cursor="bad!")
    assert err.value.code == ErrorCode.INVALID_REQUEST


def test_audit_read_follows_the_objects_data_scope(ready: InMemoryFacilities, access_stub: InMemoryAccess) -> None:
    """R4-3：仓储物流负责人只被授予“本部门”的 audit.read，不能看装配一部请假单的审计。"""
    access_stub.grant("acc-W0003", fac.AUDIT_READ_CAPABILITY, Cond.own_dept("deptId"))
    with as_principal("acc-A0004"), db.transaction():
        fac.audit_in_tx(_draft())
    with as_principal("acc-W0003"), pytest.raises(AppError) as err:
        fac.audit_for(LEAVE, access_target=LEAVE_TARGET)  # 装配一部的对象，不在他部门
    assert err.value.code == ErrorCode.ACCESS_DENIED
    own = fac.ObjectRef("leave", "LV-0009")
    with as_principal("acc-W0003"):
        assert fac.audit_for(own, access_target=Target("leave", "LV-0009", dept_id="wh")).items == []
    # 不给对象归属：只有“全部”范围的授权能过
    with as_principal("acc-W0003"), pytest.raises(AppError) as err:
        fac.audit_for(LEAVE)
    assert err.value.code == ErrorCode.ACCESS_DENIED
    with as_principal("acc-H0012"):
        assert len(fac.audit_for(LEAVE).items) == 1


def test_audit_digests_must_be_hashes(ready: InMemoryFacilities) -> None:
    """R4-6：前后摘要只收 digest() 的输出，塞明文直接拒绝。"""
    with pytest.raises(ValueError):
        _draft(before_digest="身份证 110101199001011234")
    with pytest.raises(ValueError):
        _draft(after_digest="sha256:xyz")
    with pytest.raises(ValueError):
        _draft(before_digest="md5:" + "a" * 32)
    ok = _draft(before_digest=fac.digest({"days": 1}), after_digest=None)
    assert ok.before_digest is not None and ok.before_digest.startswith("sha256:")


def test_acting_for_records_executor(ready: InMemoryFacilities, access_stub: InMemoryAccess) -> None:
    # 管家代办：主体是被代办的本人，执行者是管家
    access_stub.add_service("svc-butler", "管家")
    real = access_stub.whoami
    access_stub.whoami = lambda: replace(real(), acting_for="acc-A0004")  # type: ignore[method-assign]
    try:
        with as_principal("svc-butler"), db.transaction():
            fac.audit_in_tx(_draft())
    finally:
        access_stub.whoami = real  # type: ignore[method-assign]
    ev = ready.audits[-1]
    assert ev.principal_id == "acc-A0004"
    assert ev.executor_id == "svc-butler"
