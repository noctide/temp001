from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from titanloom.access.api.testing import as_principal
from titanloom.facilities import api as fac
from titanloom.facilities.api.testing import InMemoryFacilities, NotInTransaction, NotRegistered, TextParamMissing
from titanloom.kernel import db
from titanloom.kernel.errors import AppError
from titanloom.kernel.reg.errors import ErrorCode

from .conftest import LEAVE, LEAVE_TARGET, TODO_TYPE

KEY = fac.TodoKey(TODO_TYPE, "attendance:leave:LV-0001")
AMY, BOB, CAT = "acc-A0004", "acc-H0012", "acc-I0002"


def _open(*who: str, version: int = 1) -> fac.TodoView:
    with db.transaction():
        return fac.todo_open_in_tx(fac.TodoDraft(KEY, who, source_version=version, params={"name": "小王"}))


# ---- 待办 ----


def test_todo_needs_a_transaction(facilities_stub: InMemoryFacilities) -> None:
    fac.register_todo_type(fac.TodoTypeDecl(TODO_TYPE, "attendance", "attendance.leave.approveTitle", TODO_TYPE))
    with pytest.raises(NotInTransaction):
        fac.todo_open_in_tx(fac.TodoDraft(KEY, (AMY,), source_version=1))


def test_todo_needs_registered_type(ready: InMemoryFacilities) -> None:
    with pytest.raises(NotRegistered), db.transaction():
        fac.todo_open_in_tx(fac.TodoDraft(fac.TodoKey("x.unknown", "s"), (AMY,), source_version=1))


def test_open_is_idempotent_and_shows_in_my_todos(ready: InMemoryFacilities) -> None:
    first, again = _open(AMY, BOB), _open(AMY, BOB)
    assert first.todo_id == again.todo_id
    assert first.title_key == "attendance.leave.approveTitle"  # 默认用类型登记的
    with as_principal(AMY):
        assert [x.todo_id for x in fac.my_todos().items] == [first.todo_id]
    with as_principal(CAT):
        assert fac.my_todos().items == []


def test_todo_key_idempotent_by_source_version(ready: InMemoryFacilities) -> None:
    """R4-4：来源对象版本推进后可以再开一条；同一版本重投是幂等；旧一条还开着则冲突。"""
    first = _open(AMY, version=1)
    with db.transaction():
        fac.todo_close_in_tx(KEY, done_by=AMY)
    retry = _open(AMY, version=1)  # 同一个事件重投：不要再开一条
    assert retry.todo_id == first.todo_id and retry.state == "done"
    second = _open(AMY, version=2)  # 退回重提：来源版本更新，旧的已办完 → 新开一条
    assert second.todo_id != first.todo_id and second.state == "open" and second.source_version == 2
    assert _open(AMY, version=2).todo_id == second.todo_id  # 同一版本重投还是同一条
    with pytest.raises(AppError) as err, db.transaction():
        fac.todo_open_in_tx(fac.TodoDraft(KEY, (AMY,), source_version=3))
    assert err.value.code == ErrorCode.RESOURCE_VERSION_CONFLICT  # 旧的还开着
    with db.transaction():
        fac.todo_withdraw_in_tx(KEY)
    third = _open(AMY, version=3)  # 旧的撤回了，新版本可以开
    assert third.todo_id != second.todo_id and third.state == "open" and third.source_version == 3


def test_group_todo_first_to_finish_wins(ready: InMemoryFacilities) -> None:
    _open(AMY, BOB)
    with db.transaction():
        won = fac.todo_close_in_tx(KEY, done_by=BOB)
        late = fac.todo_close_in_tx(KEY, done_by=AMY)
    assert (won.state, won.done_by) == ("done", BOB)
    assert late.done_by == BOB  # 不覆盖
    with as_principal(AMY):
        mine = fac.my_todos(state="done").items[0]
    assert mine.done_by != AMY  # 前端据此显示“已由他人办理”


def test_close_by_non_assignee_is_rejected(ready: InMemoryFacilities) -> None:
    _open(AMY)
    with pytest.raises(AppError) as err, db.transaction():
        fac.todo_close_in_tx(KEY, done_by=CAT)
    assert err.value.code == ErrorCode.INVALID_REQUEST


def test_reassign_and_withdraw(ready: InMemoryFacilities) -> None:
    _open(AMY)
    with db.transaction():
        moved = fac.todo_reassign_in_tx(KEY, (BOB, BOB))
    assert moved.assignees == (BOB,)
    with as_principal(AMY):
        assert fac.my_todos().items == []
    with db.transaction():
        assert fac.todo_withdraw_in_tx(KEY).state == "withdrawn"
    with pytest.raises(AppError) as err, db.transaction():
        fac.todo_reassign_in_tx(KEY, (CAT,))
    assert err.value.code == ErrorCode.RESOURCE_VERSION_CONFLICT


def test_todo_changes_roll_back(ready: InMemoryFacilities, tx_session: Session) -> None:
    _open(AMY)
    tx_session.rollback()
    assert ready.todos == ()
    _open(AMY)
    tx_session.commit()
    with db.transaction():
        fac.todo_close_in_tx(KEY, done_by=AMY)
    tx_session.rollback()
    assert fac.get_todo(KEY).state == "open"


def test_unknown_todo_is_not_found(ready: InMemoryFacilities) -> None:
    with pytest.raises(AppError) as err:
        fac.get_todo(KEY)
    assert err.value.code == ErrorCode.RESOURCE_NOT_FOUND


# ---- 通知 ----


_notify_seq = 0


def _notify(
    *who: str, idem: str | None = None, merge: str | None = None, view: bool = True, name: str = "小王"
) -> None:
    global _notify_seq
    _notify_seq += 1
    with db.transaction():
        fac.notify_in_tx(
            fac.NotifyDraft(
                "attendance.leave.submitted",
                "approval",
                "info",
                tuple(who),
                "attendance.leave.submitted",
                idem or f"event-{_notify_seq}",
                {"name": name},
                merge_key=merge,
                subject=fac.ObjectRef("leave", "LV-0001"),
                view_capability=LEAVE if view else None,
                access_target=LEAVE_TARGET if view else None,
            )
        )


def test_recipients_who_cannot_see_the_object_are_dropped(ready: InMemoryFacilities, access_stub: object) -> None:
    _notify(AMY, "acc-B0001")  # B0001 没有 LEAVE 能力
    assert ready.recipients_of([n.notification_id for n in ready.notifications]) == (AMY,)
    with as_principal("acc-B0001"):
        assert fac.unread_count() == 0


def test_rendered_in_recipient_language_with_pack_version(ready: InMemoryFacilities) -> None:
    ready.set_language(BOB, "en-US")
    _notify(AMY, BOB)
    with as_principal(AMY):
        zh = fac.my_notifications().items[0]
    with as_principal(BOB):
        en = fac.my_notifications().items[0]
    assert (zh.text, zh.lang) == ("小王 提交了请假", "zh-CN")
    assert (en.text, en.lang) == ("小王 requested leave", "en-US")
    assert zh.pack_version == fac.pack_version("zh-CN") and en.pack_version.startswith("en-US@")


def test_redelivered_event_is_not_counted_again(ready: InMemoryFacilities) -> None:
    """R4-2：同一事件重投（至少一次投递）什么也不做，合并计数不涨。"""
    _notify(AMY, idem="evt-1", merge="leave-LV-0001", name="一")
    _notify(AMY, idem="evt-1", merge="leave-LV-0001", name="一")  # 同一个事件重投
    with as_principal(AMY):
        items = fac.my_notifications().items
    assert len(items) == 1 and items[0].count == 1
    # 之后真正的新事件才合并计数
    _notify(AMY, idem="evt-2", merge="leave-LV-0001", name="二")
    with as_principal(AMY):
        items = fac.my_notifications().items
    assert len(items) == 1 and items[0].count == 2


def test_same_merge_key_merges_within_five_minutes(ready: InMemoryFacilities, access_stub: object) -> None:
    _notify(AMY, idem="evt-1", merge="leave-LV-0001", name="一")
    ready.clock.advance(minutes=4)  # type: ignore[attr-defined]
    _notify(AMY, idem="evt-2", merge="leave-LV-0001", name="二")
    with as_principal(AMY):
        items = fac.my_notifications().items
    assert len(items) == 1 and items[0].count == 2 and items[0].text.startswith("二")
    ready.clock.advance(minutes=6)  # type: ignore[attr-defined]
    _notify(AMY, idem="evt-3", merge="leave-LV-0001")
    with as_principal(AMY):
        assert len(fac.my_notifications().items) == 2  # 超过 5 分钟另起一条


def test_notification_text_is_frozen_at_send_time(ready: InMemoryFacilities) -> None:
    """R4-5：渲染好的文字与语言包版本在发送时存下，之后改文案不影响已发的通知。"""
    _notify(AMY)
    with as_principal(AMY):
        before = fac.my_notifications().items[0]
    sent_pack = before.pack_version
    fac.register_texts(
        "attendance", {"attendance.leave.submitted": fac.TextEntry("{name} 交了请假（改过）", "{name} changed")}
    )
    assert fac.pack_version("zh-CN") != sent_pack  # 语言包确实更新了
    with as_principal(AMY):
        after = fac.my_notifications().items[0]
    assert after.text == before.text == "小王 提交了请假"
    assert after.pack_version == sent_pack


def test_merge_updates_stored_text_at_merge_time(ready: InMemoryFacilities) -> None:
    _notify(AMY, idem="evt-1", merge="leave-LV-0001", name="一")
    fac.register_texts(
        "attendance", {"attendance.leave.submitted": fac.TextEntry("{name} 交了请假（改过）", "{name} changed")}
    )
    ready.clock.advance(minutes=1)  # type: ignore[attr-defined]
    _notify(AMY, idem="evt-2", merge="leave-LV-0001", name="二")
    with as_principal(AMY):
        item = fac.my_notifications().items[0]
    assert item.count == 2 and item.text == "二 交了请假（改过）"
    assert item.pack_version == fac.pack_version("zh-CN")


def test_read_state_is_per_recipient(ready: InMemoryFacilities) -> None:
    _notify(AMY, BOB, view=False)
    with as_principal(AMY):
        mine = fac.my_notifications().items[0]
        assert fac.unread_count() == 1
        with as_principal(BOB):
            assert fac.mark_read([mine.notification_id]) == 0  # 不能替别人标
        assert fac.mark_read([mine.notification_id]) == 1
        assert fac.mark_read([mine.notification_id]) == 0
        assert fac.unread_count() == 0 and fac.my_notifications(unread_only=True).items == []
    with as_principal(BOB):
        assert fac.unread_count() == 1


def test_mandatory_categories(ready: InMemoryFacilities) -> None:
    _notify(AMY, view=False)
    assert ready.notifications[0].mandatory  # approval 关不掉
    assert {"approval", "must_read", "account_security"} == fac.MANDATORY_CATEGORIES


def test_notify_rolls_back_and_requires_registered_text(ready: InMemoryFacilities, tx_session: Session) -> None:
    with db.transaction():
        fac.notify_in_tx(
            fac.NotifyDraft("a.b", "system", "info", (AMY,), "attendance.leave.submitted", "evt-rb", {"name": "x"})
        )
    tx_session.rollback()
    assert ready.notifications == ()
    with pytest.raises(NotRegistered), db.transaction():
        fac.notify_in_tx(fac.NotifyDraft("a.b", "system", "info", (AMY,), "attendance.leave.nope", "evt-nope"))


# ---- 文案 ----


def test_text_uses_request_language_then_default(ready: InMemoryFacilities) -> None:
    from titanloom.kernel import context

    assert fac.text("attendance.leave.submitted", {"name": "A"}) == "A 提交了请假"
    token = context.bind(context.RequestContext("req_x", lang="en-US"))
    try:
        assert fac.text("attendance.leave.submitted", {"name": "A"}) == "A requested leave"
        assert fac.text("attendance.leave.submitted", {"name": "A"}, lang="zh-CN") == "A 提交了请假"
    finally:
        context.reset(token)


def test_text_errors_and_registration_rules(ready: InMemoryFacilities) -> None:
    with pytest.raises(NotRegistered):
        fac.text("attendance.leave.nope")
    with pytest.raises(TextParamMissing):
        fac.text("attendance.leave.submitted")
    with pytest.raises(ValueError):
        fac.register_texts("attendance", {"forms.x.y": fac.TextEntry("a", "b")})  # 不是本模块的键


def test_pack_version_moves_only_when_content_changes(ready: InMemoryFacilities) -> None:
    before = fac.pack_version("zh-CN")
    fac.register_texts("attendance", {"attendance.leave.approveTitle": fac.TextEntry("审批请假", "Approve leave")})
    assert fac.pack_version("zh-CN") == before
    fac.register_texts("attendance", {"attendance.leave.approveTitle": fac.TextEntry("审批请假单", "Approve leave")})
    assert fac.pack_version("zh-CN") != before
