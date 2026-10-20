from __future__ import annotations

from collections.abc import Generator

import pytest

from titanloom.access.api import CapabilityDecl
from titanloom.access.api.testing import InMemoryAccess, access_stub
from titanloom.execution import api as execution
from titanloom.execution.api.testing import InMemoryExecution, execution_stub, tx_session

__all__ = ["EXPORT", "LEAVE", "PUBLISH", "access_stub", "execution_stub", "ready", "tx_session"]

PUBLISH = "attendance.schedule.publish"  # 同步，必须确认
LEAVE = "attendance.leave.create"  # 同步，直接办
EXPORT = "attendance.report.export"  # 后台，可取消

_CAPS = (PUBLISH, LEAVE, EXPORT)


@pytest.fixture
def ready(
    access_stub: InMemoryAccess, execution_stub: InMemoryExecution, tx_session: object
) -> Generator[InMemoryExecution]:
    """三个能力登记到 access 与 execution，几个人都授权；事务会话已绑定。"""
    access_stub.register("attendance", capabilities=[CapabilityDecl(c) for c in _CAPS])
    access_stub.add_service("svc-butler", "管家")
    for account in ("acc-A0004", "acc-H0012", "acc-I0002", "svc-butler"):
        for cap in _CAPS:
            access_stub.grant(account, cap)
    execution.register_binding(
        execution.ExecutionBinding(PUBLISH, "1.0.0", "attendance", "sync", confirm_policy="confirm")
    )
    execution.register_binding(execution.ExecutionBinding(LEAVE, "1.0.0", "attendance", "sync"))
    execution.register_binding(
        execution.ExecutionBinding(
            EXPORT,
            "1.0.0",
            "attendance",
            "async",
            lane="heavy",
            cancellable=True,
            reconcile=execution.ReconcilePolicy(),
        )
    )
    yield execution_stub
