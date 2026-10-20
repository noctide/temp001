"""facilities.api 的数据类型（公共设施 8；契约 audit-event / notification / todo-item / asset-ref / asset-version）。

全部是冻结的数据类；时间一律带时区。账户、人员编号是字符串。
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from titanloom.access.api import Target
from titanloom.kernel.clock import ensure_utc
from titanloom.kernel.idem import request_digest

Lang = Literal["zh-CN", "en-US"]
LANGS: tuple[Lang, ...] = ("zh-CN", "en-US")
DEFAULT_LANG: Lang = "zh-CN"

AuditResult = Literal["accepted", "succeeded", "failed", "denied", "partial", "unknown"]
CallerType = Literal["human", "service", "job", "system"]
TodoState = Literal["open", "done", "withdrawn"]
Category = Literal["approval", "task_result", "must_read", "system", "collaboration", "account_security", "alert"]
Severity = Literal["info", "warning", "critical"]
AssetState = Literal["checking", "available", "quarantined", "withdrawn", "pending_purge", "purged"]

# 应用内关不掉的几类（公共设施 5）
MANDATORY_CATEGORIES: frozenset[Category] = frozenset({"approval", "must_read", "account_security"})
AUDIT_READ_CAPABILITY = "facilities.audit.read"

_TEXT_KEY_RE = re.compile(r"^(plugin\.[a-z0-9-]+|[a-z][a-z0-9]*)(\.[a-z][A-Za-z0-9]*)+$")
_TYPE_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def digest(value: Any) -> str:
    """审计里只存前后值的摘要（sha256:<hex>），不存原值。"""
    return request_digest(value)


def _need_tz(*stamps: datetime | None) -> None:
    for ts in stamps:
        if ts is not None:
            ensure_utc(ts)


@dataclass(frozen=True, slots=True)
class ObjectRef:
    """一个业务对象：审计的对象、通知的主题、文件引用的挂靠对象。id 必须是具体的。"""

    type: str
    id: str

    def __post_init__(self) -> None:
        if not _TYPE_RE.match(self.type) or not self.id or self.id == "latest":
            raise ValueError(f"对象引用不合法：{self.type!r}/{self.id!r}")


# ---- 审计 ----


@dataclass(frozen=True, slots=True)
class AuditDraft:
    """调用方交的内容；谁、何时、哪个代办、策略版本由实现从请求上下文与时钟补。前后摘要只收 `digest()` 的输出。

    前后值只收摘要：`digest()` 的输出（sha256:<64 位 hex>），不收明文与其它格式。
    """

    capability_id: str
    contract_version: str
    target: ObjectRef
    result: AuditResult
    before_digest: str | None = None
    after_digest: str | None = None
    reason: str | None = None
    confirmation_id: str | None = None
    command_id: str | None = None
    job_id: str | None = None
    evidence_ref: str | None = None

    def __post_init__(self) -> None:
        for name in ("before_digest", "after_digest"):
            value = getattr(self, name)
            if value is not None and not _DIGEST_RE.match(value):
                raise ValueError(f"{name} 只收 digest() 的摘要（sha256:<64 位 hex>），不收明文：{value!r}")


@dataclass(frozen=True, slots=True)
class AuditEvent:
    event_id: str
    occurred_at: datetime
    received_at: datetime
    principal_id: str
    executor_id: str | None
    caller_type: CallerType
    delegation_id: str | None
    policy_version_set: Mapping[str, Any]
    capability_id: str
    contract_version: str
    target: ObjectRef
    result: AuditResult
    before_digest: str | None
    after_digest: str | None
    reason: str | None
    confirmation_id: str | None
    command_id: str | None
    job_id: str | None
    evidence_ref: str | None
    prev_hash: str | None
    hash: str


# ---- 待办 ----


@dataclass(frozen=True, slots=True)
class TodoKey:
    """一条待办的身份：待办类型 + 来源对象引用（幂等靠它）。source_ref 形如 attendance:leave:LV-0001。"""

    type: str
    source_ref: str

    def __post_init__(self) -> None:
        if not _TYPE_RE.match(self.type) or not self.source_ref:
            raise ValueError(f"待办标识不合法：{self.type!r}/{self.source_ref!r}")


@dataclass(frozen=True, slots=True)
class TodoTypeDecl:
    """登记待办类型。办理（完成 / 驳回等）由 handle_capability 这个能力完成，收件箱自己不改状态。"""

    type: str
    module: str
    title_key: str
    handle_capability: str
    batchable: bool = False

    def __post_init__(self) -> None:
        if not _TYPE_RE.match(self.type) or not _TEXT_KEY_RE.match(self.title_key):
            raise ValueError(f"待办类型声明不合法：{self.type!r}")


@dataclass(frozen=True, slots=True)
class TodoDraft:
    """模块在事务里发出的新待办 / 换人事件。source_version 是来源对象事件的版本：(类型, 来源引用, 版本) 幂等。"""

    key: TodoKey
    assignees: tuple[str, ...]
    source_version: int
    title_key: str | None = None  # 不给就用类型登记的
    params: Mapping[str, Any] = field(default_factory=lambda: {})
    due_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.assignees:
            raise ValueError("待办至少要有一个办理人")
        if self.source_version < 1:
            raise ValueError(f"来源版本从 1 起：{self.source_version!r}")
        _need_tz(self.due_at)


@dataclass(frozen=True, slots=True)
class TodoView:
    """契约 todo-item。多人待办一条、先办先得；source_version 是开这条待办时的来源版本。

    done_by 不是自己即“已由他人办理”。来源版本推进后旧的已办完 / 撤回才另开一条。
    """

    todo_id: str
    key: TodoKey
    title_key: str
    params: Mapping[str, Any]
    due_at: datetime | None
    state: TodoState
    opened_at: datetime
    assignees: tuple[str, ...]
    done_by: str | None = None
    done_at: datetime | None = None
    source_version: int = 1


# ---- 通知 ----


@dataclass(frozen=True, slots=True)
class NotifyDraft:
    """应用内通知。idempotency_key 管同一事件重投、merge_key 管 5 分钟同类合并；看不到对象的收件人被去掉。

    收件人是账户；设了 view_capability 的，看不到对象的收件人会被去掉（不报错、不回告）。
    idempotency_key 是同一事件的幂等键（至少一次投递重投时什么也不做），merge_key 是同类合并键
    （同一收件人 5 分钟内合并计数）。不给 merge_key 就不合并。
    """

    type: str
    category: Category
    severity: Severity
    recipients: tuple[str, ...]
    message_key: str
    idempotency_key: str
    params: Mapping[str, Any] = field(default_factory=lambda: {})
    merge_key: str | None = None
    subject: ObjectRef | None = None
    view_capability: str | None = None
    access_target: Target | None = None  # 传给 access.api.check 判定收件人能不能看到对象

    def __post_init__(self) -> None:
        if not _TYPE_RE.match(self.type) or not _TEXT_KEY_RE.match(self.message_key):
            raise ValueError(f"通知类型或文案键不合法：{self.type!r} / {self.message_key!r}")
        if not self.idempotency_key:
            raise ValueError("通知必须有幂等键（同一事件重投时什么也不做）")
        if self.merge_key is not None and not self.merge_key:
            raise ValueError("合并键给了就不能是空串")


@dataclass(frozen=True, slots=True)
class NotificationView:
    notification_id: str
    type: str
    category: Category
    severity: Severity
    subject: ObjectRef | None
    message_key: str
    params: Mapping[str, Any]
    text: str  # 按收件人语言渲染好的
    lang: Lang
    pack_version: str
    count: int  # 5 分钟内同一去重键合并的次数
    created_at: datetime
    last_at: datetime
    read_at: datetime | None = None

    @property
    def mandatory(self) -> bool:
        return self.category in MANDATORY_CATEGORIES


# ---- 文案 ----


@dataclass(frozen=True, slots=True)
class TextEntry:
    """一个文案键的两种语言版本；用 {name} 占位。"""

    zh_cn: str
    en_us: str

    def get(self, lang: Lang) -> str:
        return self.zh_cn if lang == "zh-CN" else self.en_us


# ---- 文件 ----


@dataclass(frozen=True, slots=True)
class AssetRef:
    """契约 asset-ref：业务对象只引用 asset_id + version。"""

    asset_id: str
    version: int
    ref_module: str
    ref_object: ObjectRef
    ref_field: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class AssetVersionView:
    asset_id: str
    version: int
    state: AssetState
    name: str
    content_type: str
    size: int
    sha256: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class DownloadGrant:
    """一次性短时下载许可；没有匿名长链接（公共设施 3）。"""

    asset_id: str
    version: int
    name: str
    content_type: str
    size: int
    url: str
    expires_at: datetime


def is_text_key(key: str) -> bool:
    return bool(_TEXT_KEY_RE.match(key))
