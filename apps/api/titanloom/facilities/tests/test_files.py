from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from titanloom.access.api.testing import as_principal
from titanloom.facilities import api as fac
from titanloom.facilities.api.testing import InMemoryFacilities, NotRegistered
from titanloom.kernel import db
from titanloom.kernel.errors import AppError
from titanloom.kernel.reg.errors import ErrorCode

from .conftest import LEAVE_TARGET

LV1 = fac.ObjectRef("leave", "LV-0001")
LV2 = fac.ObjectRef("leave", "LV-0002")
SEES: set[str] = set()


@pytest.fixture(autouse=True)
def _authorizer(ready: InMemoryFacilities) -> None:
    SEES.clear()
    SEES.add("acc-A0004")

    def can_see(obj: fac.ObjectRef) -> bool:
        from titanloom.access import api as access

        return access.whoami().account_id in SEES and obj.type == "leave"

    fac.ref_authorizer("attendance", can_see)


def _ref(asset: tuple[str, int], obj: fac.ObjectRef = LV1, field: str = "attachment") -> fac.AssetRef:
    with db.transaction():
        return fac.add_ref(*asset, ref_module="attendance", ref_object=obj, ref_field=field)


def _grant(asset: tuple[str, int], obj: fac.ObjectRef = LV1, field: str = "attachment") -> fac.DownloadGrant:
    return fac.download_grant(*asset, ref_module="attendance", ref_object=obj, ref_field=field)


def test_same_bytes_are_stored_once_but_authorized_per_reference(ready: InMemoryFacilities) -> None:
    a = ready.put_asset(b"same", "a.pdf")
    b = ready.put_asset(b"same", "b.pdf")
    assert a == b and len(ready.assets) == 1
    _ref(a, LV1)
    _ref(a, LV2)
    SEES.add("acc-H0012")
    with as_principal("acc-A0004"):
        assert _grant(a, LV1).asset_id == a[0]
    with as_principal("acc-I0002"), pytest.raises(AppError) as err:  # 看不到挂靠对象的人，同一个文件也下不了
        _grant(a, LV1)
    assert err.value.code == ErrorCode.ACCESS_DENIED
    assert err.value.details in (None, {})  # 不透露任何信息


def test_download_needs_an_existing_reference(ready: InMemoryFacilities) -> None:
    a = ready.put_asset(b"x", "x.pdf")
    with as_principal("acc-A0004"), pytest.raises(AppError) as err:
        _grant(a)
    assert err.value.code == ErrorCode.RESOURCE_NOT_FOUND
    _ref(a)
    with as_principal("acc-A0004"):
        grant = _grant(a)
    assert grant.url.startswith("stub://") and grant.expires_at > ready.clock.now()
    with as_principal("acc-A0004"), pytest.raises(AppError):
        _grant(a, field="other")  # 引用的字段不对


def test_add_ref_is_idempotent_and_rolls_back(ready: InMemoryFacilities, tx_session: Session) -> None:
    a = ready.put_asset(b"x", "x.pdf")
    assert _ref(a) == _ref(a) and len(ready.refs) == 1
    tx_session.commit()
    with db.transaction():
        fac.add_ref(*a, ref_module="attendance", ref_object=LV2, ref_field="attachment")
    tx_session.rollback()
    assert len(ready.refs) == 1
    with db.transaction():
        fac.remove_ref(*a, ref_module="attendance", ref_object=LV1, ref_field="attachment")
        fac.remove_ref(*a, ref_module="attendance", ref_object=LV1, ref_field="attachment")  # 重复无影响
    assert ready.refs == ()


@pytest.mark.parametrize("state", ["quarantined", "withdrawn", "purged"])
def test_unusable_versions_cannot_be_referenced(ready: InMemoryFacilities, state: fac.AssetState) -> None:
    a = ready.put_asset(b"x", "x.pdf", state=state)
    with pytest.raises(AppError) as err, db.transaction():
        fac.add_ref(*a, ref_module="attendance", ref_object=LV1, ref_field="attachment")
    assert err.value.code == ErrorCode.INVALID_REQUEST


def test_quarantined_after_reference_cannot_be_downloaded(ready: InMemoryFacilities) -> None:
    a = ready.put_asset(b"x", "x.pdf", state="checking")
    _ref(a)  # 检查中可以先引用
    with as_principal("acc-A0004"), pytest.raises(AppError) as checking:
        _grant(a)
    ready.set_asset_state(*a, "quarantined")
    with as_principal("acc-A0004"), pytest.raises(AppError) as quarantined:
        _grant(a)
    assert {checking.value.code, quarantined.value.code} == {ErrorCode.DEPENDENCY_BLOCKED}
    assert [v.state for v in fac.assets_of("attendance", LV1)] == ["quarantined"]


def test_upload_rules_size_and_type(ready: InMemoryFacilities) -> None:
    for name in ("run.exe", "macro.xlsm", "x.DOCM"):
        with pytest.raises(AppError) as blocked:
            ready.put_asset(b"x", name)
        assert blocked.value.code == ErrorCode.INVALID_REQUEST
    with pytest.raises(AppError) as big:
        ready.put_asset(b"x", "big.pdf", size=50 * 1024 * 1024 + 1)
    assert big.value.code == ErrorCode.PAYLOAD_TOO_LARGE
    ready.put_asset(b"v", "clip.mp4", "video/mp4", size=200 * 1024 * 1024)  # 视频 / 3D 放宽到 200 MB


def test_download_without_registered_authorizer(ready: InMemoryFacilities) -> None:
    a = ready.put_asset(b"x", "x.pdf")
    with db.transaction():
        fac.add_ref(*a, ref_module="forms", ref_object=LV1, ref_field="f")
    with pytest.raises(NotRegistered):
        fac.download_grant(*a, ref_module="forms", ref_object=LV1, ref_field="f")
    assert LEAVE_TARGET  # 保持导入用于其它测试文件
