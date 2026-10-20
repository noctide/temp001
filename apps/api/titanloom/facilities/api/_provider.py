"""facilities.api 背后的实现怎么装入（只两处：create_app() 启动时装真实实现；测试用 testing 里的 fixture 装测试桩）。

当前主体、请求编号、语言取自 `kernel.context`，不经过这里。
"""

from __future__ import annotations

from collections.abc import Callable, Generator, Mapping, Sequence
from contextlib import contextmanager
from typing import Protocol

from titanloom.access.api import Target
from titanloom.facilities.api import types as t
from titanloom.kernel.paging import Page


class FacilitiesApi(Protocol):
    # 审计
    def audit_in_tx(self, draft: t.AuditDraft) -> str: ...

    def audit_for(
        self,
        target: t.ObjectRef,
        *,
        access_target: Target | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> Page[t.AuditEvent]: ...

    # 待办
    def register_todo_type(self, decl: t.TodoTypeDecl) -> None: ...

    def todo_open_in_tx(self, draft: t.TodoDraft) -> t.TodoView: ...

    def todo_reassign_in_tx(self, key: t.TodoKey, assignees: Sequence[str]) -> t.TodoView: ...

    def todo_close_in_tx(self, key: t.TodoKey, *, done_by: str) -> t.TodoView: ...

    def todo_withdraw_in_tx(self, key: t.TodoKey) -> t.TodoView: ...

    def get_todo(self, key: t.TodoKey) -> t.TodoView: ...

    def my_todos(
        self, *, state: t.TodoState | None = None, cursor: str | None = None, limit: int | None = None
    ) -> Page[t.TodoView]: ...

    # 通知
    def notify_in_tx(self, draft: t.NotifyDraft) -> None: ...

    def my_notifications(
        self, *, unread_only: bool = False, cursor: str | None = None, limit: int | None = None
    ) -> Page[t.NotificationView]: ...

    def mark_read(self, notification_ids: Sequence[str]) -> int: ...

    def unread_count(self) -> int: ...

    # 文案
    def register_texts(self, module: str, texts: Mapping[str, t.TextEntry]) -> None: ...

    def text(self, key: str, params: Mapping[str, object] | None = None, *, lang: t.Lang | None = None) -> str: ...

    def pack_version(self, lang: t.Lang) -> str: ...

    # 文件引用
    def ref_authorizer(self, ref_module: str, check: Callable[[t.ObjectRef], bool]) -> None: ...

    def add_ref(
        self, asset_id: str, version: int, *, ref_module: str, ref_object: t.ObjectRef, ref_field: str
    ) -> t.AssetRef: ...

    def remove_ref(
        self, asset_id: str, version: int, *, ref_module: str, ref_object: t.ObjectRef, ref_field: str
    ) -> None: ...

    def assets_of(self, ref_module: str, ref_object: t.ObjectRef) -> tuple[t.AssetVersionView, ...]: ...

    def download_grant(
        self, asset_id: str, version: int, *, ref_module: str, ref_object: t.ObjectRef, ref_field: str
    ) -> t.DownloadGrant: ...


_provider: FacilitiesApi | None = None


def set_provider(provider: FacilitiesApi | None) -> FacilitiesApi | None:
    """装入实现，返回原来的（用完要装回去）。"""
    global _provider
    previous = _provider
    _provider = provider
    return previous


@contextmanager
def use_provider(provider: FacilitiesApi) -> Generator[FacilitiesApi]:
    previous = set_provider(provider)
    try:
        yield provider
    finally:
        set_provider(previous)


def provider() -> FacilitiesApi:
    if _provider is None:
        raise RuntimeError("facilities 的实现还没装入：启动时由 create_app() 装，测试用 facilities_stub")
    return _provider
