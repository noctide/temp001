"""facilities.api：别的模块唯一能引用的公共设施入口（公共设施 8）。

    from titanloom.facilities.api import audit_in_tx, notify_in_tx, todo_open_in_tx, text, add_ref

实现在启动时装入（见 `_provider`）。登记类的调用（register_todo_type / register_texts / ref_authorizer）
放在模块自己的启动函数里，与 access.api.register 同一处。名字带 `_in_tx` 的必须在 kernel.db 事务里调用，
和业务改动同成同败。本轮不含 HTTP 路由、文件上传与检查、搜索、通知偏好与外发。
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from titanloom.facilities.api import _provider
from titanloom.facilities.api._provider import FacilitiesApi, set_provider, use_provider
from titanloom.facilities.api.types import (
    AUDIT_READ_CAPABILITY,
    DEFAULT_LANG,
    LANGS,
    MANDATORY_CATEGORIES,
    AssetRef,
    AssetState,
    AssetVersionView,
    AuditDraft,
    AuditEvent,
    AuditResult,
    CallerType,
    Category,
    DownloadGrant,
    Lang,
    NotificationView,
    NotifyDraft,
    ObjectRef,
    Severity,
    TextEntry,
    TodoDraft,
    TodoKey,
    TodoState,
    TodoTypeDecl,
    TodoView,
    digest,
)
from titanloom.kernel.paging import Page

__all__ = [
    "AUDIT_READ_CAPABILITY",
    "DEFAULT_LANG",
    "LANGS",
    "MANDATORY_CATEGORIES",
    "AssetRef",
    "AssetState",
    "AssetVersionView",
    "AuditDraft",
    "AuditEvent",
    "AuditResult",
    "CallerType",
    "Category",
    "DownloadGrant",
    "FacilitiesApi",
    "Lang",
    "NotificationView",
    "NotifyDraft",
    "ObjectRef",
    "Page",
    "Severity",
    "TextEntry",
    "TodoDraft",
    "TodoKey",
    "TodoState",
    "TodoTypeDecl",
    "TodoView",
    "add_ref",
    "assets_of",
    "audit_for",
    "audit_in_tx",
    "digest",
    "download_grant",
    "get_todo",
    "mark_read",
    "my_notifications",
    "my_todos",
    "notify_in_tx",
    "pack_version",
    "ref_authorizer",
    "register_texts",
    "register_todo_type",
    "remove_ref",
    "set_provider",
    "text",
    "todo_close_in_tx",
    "todo_open_in_tx",
    "todo_reassign_in_tx",
    "todo_withdraw_in_tx",
    "unread_count",
    "use_provider",
]


# ---- 审计 ----


def audit_in_tx(draft: AuditDraft) -> str:
    """在业务改动的同一事务里写一条审计，返回 event_id。只追加、不可改；前后值只存摘要（用 `digest()` 算）。

    谁（含代办的执行者）、何时、策略版本由实现从请求上下文与时钟补。事务回滚则审计一并撤销。
    """
    return _provider.provider().audit_in_tx(draft)


def audit_for(target: ObjectRef, *, cursor: str | None = None, limit: int | None = None) -> Page[AuditEvent]:
    """按对象查审计，新的在前。需要 `facilities.audit.read`；查看本身也会记一条审计。"""
    return _provider.provider().audit_for(target, cursor=cursor, limit=limit)


# ---- 待办 ----


def register_todo_type(decl: TodoTypeDecl) -> None:
    """登记待办类型。同样内容重复登记没有影响；内容不同报错。"""
    _provider.provider().register_todo_type(decl)


def todo_open_in_tx(draft: TodoDraft) -> TodoView:
    """新建待办。同一 (类型, 来源引用) 已有未关闭的，原样返回（幂等）。多个办理人 = 一条多人待办。"""
    return _provider.provider().todo_open_in_tx(draft)


def todo_reassign_in_tx(key: TodoKey, assignees: Sequence[str]) -> TodoView:
    """改办理人。办理人没变则无影响；已关闭的待办 CONFLICT 类错误（RESOURCE_VERSION_CONFLICT）。"""
    return _provider.provider().todo_reassign_in_tx(key, assignees)


def todo_close_in_tx(key: TodoKey, *, done_by: str) -> TodoView:
    """办完。多人待办先到先得：之后再关的返回已有结果，不覆盖 done_by。done_by 必须是办理人。"""
    return _provider.provider().todo_close_in_tx(key, done_by=done_by)


def todo_withdraw_in_tx(key: TodoKey) -> TodoView:
    """来源对象不需要办了（撤回、取消）。已办完的保持办完。"""
    return _provider.provider().todo_withdraw_in_tx(key)


def get_todo(key: TodoKey) -> TodoView:
    """给所属模块读自己的待办状态；没有则 RESOURCE_NOT_FOUND。"""
    return _provider.provider().get_todo(key)


def my_todos(*, state: TodoState | None = None, cursor: str | None = None, limit: int | None = None) -> Page[TodoView]:
    """我的待办（我是办理人的），新的在前。收件箱自己不改状态：办理走待办类型登记的能力。"""
    return _provider.provider().my_todos(state=state, cursor=cursor, limit=limit)


# ---- 通知 ----


def notify_in_tx(draft: NotifyDraft) -> None:
    """在事务里发应用内通知。看不到对象的收件人被去掉；按收件人语言渲染并记语言包版本；
    同一收件人同一去重键 5 分钟内合并计数。不返回谁收到了谁没有。"""
    _provider.provider().notify_in_tx(draft)


def my_notifications(
    *, unread_only: bool = False, cursor: str | None = None, limit: int | None = None
) -> Page[NotificationView]:
    """我的通知，新的在前。"""
    return _provider.provider().my_notifications(unread_only=unread_only, cursor=cursor, limit=limit)


def mark_read(notification_ids: Sequence[str]) -> int:
    """标已读，只对自己的生效；返回实际改变的条数。"""
    return _provider.provider().mark_read(notification_ids)


def unread_count() -> int:
    return _provider.provider().unread_count()


# ---- 文案 ----


def register_texts(module: str, texts: Mapping[str, TextEntry]) -> None:
    """登记本模块的文案键（键以模块名开头，两种语言都要有）。同样内容重复登记没有影响。"""
    _provider.provider().register_texts(module, texts)


def text(key: str, params: Mapping[str, object] | None = None, *, lang: Lang | None = None) -> str:
    """后端取字。lang 不给就用请求上下文的语言，再没有用默认语言。键没登记 / 缺参数是程序错误。"""
    return _provider.provider().text(key, params, lang=lang)


def pack_version(lang: Lang) -> str:
    """当前语言包版本（前端按版本下载、通知记录渲染时用的版本）。"""
    return _provider.provider().pack_version(lang)


# ---- 文件引用 ----


def ref_authorizer(ref_module: str, check: Callable[[ObjectRef], bool]) -> None:
    """登记“当前主体能不能看到这个挂靠对象”。文件的下载权限跟随挂靠对象（公共设施 3）。"""
    _provider.provider().ref_authorizer(ref_module, check)


def add_ref(asset_id: str, version: int, *, ref_module: str, ref_object: ObjectRef, ref_field: str) -> AssetRef:
    """业务对象引用一个文件版本（在事务里）。已隔离 / 撤回 / 清除的不能引；重复引用返回原引用。"""
    return _provider.provider().add_ref(
        asset_id, version, ref_module=ref_module, ref_object=ref_object, ref_field=ref_field
    )


def remove_ref(asset_id: str, version: int, *, ref_module: str, ref_object: ObjectRef, ref_field: str) -> None:
    """取消引用（在事务里）。没有引用的文件版本过宽限期后清理。引用本来就不存在则无影响。"""
    _provider.provider().remove_ref(
        asset_id, version, ref_module=ref_module, ref_object=ref_object, ref_field=ref_field
    )


def assets_of(ref_module: str, ref_object: ObjectRef) -> tuple[AssetVersionView, ...]:
    """某个对象引用着的文件版本及状态。调用者已经确认过当前主体能看这个对象。"""
    return _provider.provider().assets_of(ref_module, ref_object)


def download_grant(
    asset_id: str, version: int, *, ref_module: str, ref_object: ObjectRef, ref_field: str
) -> DownloadGrant:
    """凭引用换下载许可：引用必须存在，挂靠对象对当前主体可见，文件版本必须可用（隔离区不可下）。"""
    return _provider.provider().download_grant(
        asset_id, version, ref_module=ref_module, ref_object=ref_object, ref_field=ref_field
    )
