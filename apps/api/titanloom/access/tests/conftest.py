from __future__ import annotations

from collections.abc import Generator

import pytest

from titanloom.access.api import CapabilityDecl, FeatureDecl
from titanloom.access.api.testing import InMemoryAccess, access_stub

__all__ = ["access_stub", "registered"]

READ = "attendance.record.read"
CREATE = "attendance.leave.create"


@pytest.fixture
def registered(access_stub: InMemoryAccess) -> Generator[InMemoryAccess]:
    access_stub.register(
        "attendance",
        capabilities=[CapabilityDecl(READ), CapabilityDecl(CREATE, feature_id="attendance.leave")],
        features=[FeatureDecl("attendance.leave", "features.attendanceLeave")],
        permission_fields={"record": ["ownerId", "deptId", "projectId"]},
        maskable_columns={"record": ["idNumber"]},
    )
    yield access_stub
