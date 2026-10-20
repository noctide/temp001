from __future__ import annotations

from collections.abc import Generator

import pytest

from titanloom.access.api import CapabilityDecl, Target
from titanloom.access.api.testing import InMemoryAccess, access_stub
from titanloom.facilities import api as fac
from titanloom.facilities.api.testing import InMemoryFacilities, facilities_stub
from titanloom.kernel.testing import tx_session

__all__ = ["LEAVE", "LEAVE_TARGET", "access_stub", "facilities_stub", "ready", "tx_session"]

LEAVE = "attendance.leave.view"  # 能看某条请假
LEAVE_TARGET = Target("leave", "LV-0001", dept_id="D-001")
TODO_TYPE = "attendance.leave.approve"


@pytest.fixture
def ready(
    access_stub: InMemoryAccess, facilities_stub: InMemoryFacilities, tx_session: object
) -> Generator[InMemoryFacilities]:
    """能力登记好、几个人授权好；待办类型与文案键登记好；事务会话已绑定。"""
    access_stub.register("attendance", capabilities=[CapabilityDecl(LEAVE)])
    access_stub.register("facilities", capabilities=[CapabilityDecl(fac.AUDIT_READ_CAPABILITY)])
    for account in ("acc-A0004", "acc-H0012", "acc-I0002"):
        access_stub.grant(account, LEAVE)
    access_stub.grant("acc-H0012", fac.AUDIT_READ_CAPABILITY)
    facilities_stub.register_texts(
        "attendance",
        {
            "attendance.leave.submitted": fac.TextEntry("{name} 提交了请假", "{name} requested leave"),
            "attendance.leave.approveTitle": fac.TextEntry("审批请假", "Approve leave"),
        },
    )
    fac.register_todo_type(
        fac.TodoTypeDecl(
            "attendance.leave.approve", "attendance", "attendance.leave.approveTitle", "attendance.leave.approve"
        )
    )
    yield facilities_stub
