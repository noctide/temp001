"""facilities.api 的内存测试桩（给别的模块的测试用；真实实现是另一回事）。

    from titanloom.facilities.api.testing import facilities_stub      # 放进模块 tests/conftest.py

    def test_x(facilities_stub, access_stub, tx_session):
        with as_principal("acc-H0012"):
            ...业务改动...
            audit_in_tx(AuditDraft(...))
        tx_session.commit()
        assert facilities_stub.audits[-1].result == "succeeded"

它做什么：审计的哈希链、待办（多人先到先得、按 (类型, 来源, 版本) 幂等）、通知（收件人按权限筛、幂等键去重、
合并键 5 分钟合并、发送时定稿文字与语言包版本）、文案按语言取字、文件引用（同样字节只在 blob 层去重、按挂靠对象授权、
隔离区不可下载）。
它不做什么：不上传 / 检查 / 派生文件，不存保留期，不做通知偏好、免打扰与外发，不做搜索。
事务：名字带 in_tx 的不在 kernel.db 事务里就报错；事务里做的一切随会话回滚一起撤销。
测试要用带库的会话时，用 execution.api.testing 的 `tx_session` fixture。
"""

from __future__ import annotations

import hashlib
import string
from collections.abc import Callable, Generator, Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta
from typing import Any

import pytest

from titanloom.access import api as access_api
from titanloom.access.api import Target
from titanloom.access.api.testing import InMemoryAccess
from titanloom.facilities.api import _provider
from titanloom.facilities.api import types as t
from titanloom.kernel import context, db
from titanloom.kernel.clock import Clock
from titanloom.kernel.errors import AppError
from titanloom.kernel.idem import request_digest
from titanloom.kernel.ids import uuid7
from titanloom.kernel.paging import Page, clamp_limit, decode_cursor, encode_cursor
from titanloom.kernel.reg.errors import ErrorCode
from titanloom.kernel.testing import track_rollback

MERGE_WINDOW = timedelta(minutes=5)
GRANT_TTL = timedelta(minutes=5)
MAX_BYTES = 50 * 1024 * 1024
MAX_BYTES_MEDIA = 200 * 1024 * 1024
_BLOCKED_SUFFIXES = (".exe", ".dll", ".bat", ".cmd", ".com", ".msi", ".ps1", ".sh", ".docm", ".xlsm", ".pptm")
_UNAVAILABLE: frozenset[t.AssetState] = frozenset({"quarantined", "withdrawn", "pending_purge", "purged"})


class RegistrationConflict(ValueError):
    """同一个编号重复登记且内容不同。"""


class NotRegistered(LookupError):
    """用了没登记的待办类型、文案键或挂靠模块。"""


class NotInTransaction(RuntimeError):
    """名字带 in_tx 的调用必须在 kernel.db 事务里。"""


class TextParamMissing(KeyError):
    """文案里的占位符没给参数。"""


@dataclass(slots=True)
class _Todo:
    seq: int
    todo_id: str
    key: t.TodoKey
    source_version: int
    title_key: str
    params: Mapping[str, Any]
    due_at: datetime | None
    state: t.TodoState
    opened_at: datetime
    assignees: tuple[str, ...]
    done_by: str | None = None
    done_at: datetime | None = None


@dataclass(slots=True)
class _Notif:
    seq: int
    notification_id: str
    recipient: str
    draft: t.NotifyDraft
    params: Mapping[str, Any]
    lang: t.Lang
    text: str  # 发送（或合并更新）时渲染好的，读取不再重渲染
    pack_version: str  # 渲染时用的语言包版本
    created_at: datetime
    last_at: datetime
    count: int = 1
    read_at: datetime | None = None


@dataclass(slots=True)
class _Asset:
    asset_id: str
    version: int
    state: t.AssetState
    name: str
    content_type: str
    size: int
    sha256: str
    created_at: datetime


@dataclass(slots=True)
class _Blob:
    sha256: str
    size: int
    ref_count: int


@dataclass(frozen=True, slots=True)
class BlobState:
    """测试用：blob（字节内容）一层。同样字节只一份 blob，引用计数是引用它的 asset 版本数。"""

    sha256: str
    size: int
    ref_count: int


@dataclass(slots=True)
class _State:
    audits: list[t.AuditEvent] = field(default_factory=lambda: [])
    todos: dict[t.TodoKey, _Todo] = field(default_factory=lambda: {})
    notifs: list[_Notif] = field(default_factory=lambda: [])
    assets: dict[tuple[str, int], _Asset] = field(default_factory=lambda: {})
    blobs: dict[str, _Blob] = field(default_factory=lambda: {})
    refs: list[t.AssetRef] = field(default_factory=lambda: [])
    seq: int = 0


def _page[T](rows: Sequence[tuple[int, str, T]], cursor: str | None, limit: int | None) -> Page[T]:
    """rows 是 (序号, 编号, 内容)，按序号从新到旧；游标记住上一页最后一条的序号。"""
    after: int | None = None
    if cursor is not None:
        try:
            after = int(decode_cursor(cursor)[0])
        except (ValueError, TypeError) as e:
            raise AppError(ErrorCode.INVALID_REQUEST, details={"field": "cursor"}) from e
    size = clamp_limit(limit)
    rest = [r for r in rows if after is None or r[0] < after]
    head = rest[:size]
    more = len(rest) > size
    return Page(items=[r[2] for r in head], next_cursor=encode_cursor(head[-1][0], head[-1][1]) if more else None)


class InMemoryFacilities:
    """facilities.api 的测试桩。时间取 clock，主体与权限取 access.api。"""

    def __init__(self, clock: Clock, *, enforce_access: bool = True):
        self.clock = clock
        self.enforce_access = enforce_access
        self._s = _State()
        self._todo_types: dict[str, t.TodoTypeDecl] = {}
        self._texts: dict[str, t.TextEntry] = {}
        self._pack_n: dict[t.Lang, int] = {lang: 0 for lang in t.LANGS}
        self._langs: dict[str, t.Lang] = {}
        self._authorizers: dict[str, Callable[[t.ObjectRef], bool]] = {}

    # ---- 给测试断言用 ----

    @property
    def audits(self) -> tuple[t.AuditEvent, ...]:
        return tuple(self._s.audits)

    @property
    def todos(self) -> tuple[t.TodoView, ...]:
        return tuple(self._todo_view(x) for x in self._s.todos.values())

    @property
    def notifications(self) -> tuple[t.NotificationView, ...]:
        """所有收件人的通知（测试用，不按人筛）。"""
        return tuple(self._notif_view(n) for n in self._s.notifs)

    @property
    def assets(self) -> tuple[t.AssetVersionView, ...]:
        return tuple(self._asset_view(a) for a in self._s.assets.values())

    @property
    def blobs(self) -> tuple[BlobState, ...]:
        """所有 blob（同样字节只一份），带引用它的 asset 版本数。"""
        return tuple(BlobState(b.sha256, b.size, b.ref_count) for b in self._s.blobs.values())

    @property
    def refs(self) -> tuple[t.AssetRef, ...]:
        return tuple(self._s.refs)

    def recipients_of(self, notification_ids: Sequence[str]) -> tuple[str, ...]:
        ids = set(notification_ids)
        return tuple(n.recipient for n in self._s.notifs if n.notification_id in ids)

    def set_language(self, account_id: str, lang: t.Lang) -> None:
        """某个账户的界面语言（真实实现来自账户设置；默认 zh-CN）。"""
        self._langs[account_id] = lang

    def verify_chain(self) -> bool:
        """审计哈希链是否完好（逐条重算 hash，并核对 prev_hash）。"""
        prev: str | None = None
        for ev in self._s.audits:
            if ev.prev_hash != prev or ev.hash != self._hash(ev):
                return False
            prev = ev.hash
        return True

    def tamper(self, index: int, **changes: Any) -> None:
        """测试用：偷偷改一条审计，用来验证 verify_chain 能发现。"""
        self._s.audits[index] = replace(self._s.audits[index], **changes)

    def put_asset(
        self,
        data: bytes,
        name: str,
        content_type: str = "application/octet-stream",
        *,
        size: int | None = None,
        state: t.AssetState = "available",
    ) -> tuple[str, int]:
        """测试用：代替“上传 + 检查”，直接造一个文件版本。每次调用都是一个新文件（自己的名字与状态），
        只在 blob（字节）层按 sha256 去重：同样字节只存一份。

        size 可以声明一个比 data 大的尺寸，用来测上限而不必真造那么多字节。
        """
        real = len(data) if size is None else size
        limit = MAX_BYTES_MEDIA if content_type.startswith(("video/", "model/")) else MAX_BYTES
        if real > limit:
            raise AppError(ErrorCode.PAYLOAD_TOO_LARGE, details={"maxBytes": limit})
        if name.lower().endswith(_BLOCKED_SUFFIXES):
            raise AppError(ErrorCode.INVALID_REQUEST, details={"field": "name", "reason": "file_type_blocked"})
        sha = hashlib.sha256(data).hexdigest()
        self._touch()
        blob = self._s.blobs.get(sha)
        if blob is None:
            blob = self._s.blobs[sha] = _Blob(sha, len(data), 0)
        blob.ref_count += 1
        asset_id = "ast_" + uuid7().hex
        self._s.assets[(asset_id, 1)] = _Asset(asset_id, 1, state, name, content_type, real, sha, self.clock.now())
        return asset_id, 1

    def set_asset_state(self, asset_id: str, version: int, state: t.AssetState) -> None:
        """测试用：模拟检查结果、撤回、清除。"""
        self._touch()
        self._s.assets[(asset_id, version)].state = state

    # ---- 事务 ----

    def _touch(self) -> None:
        def restore(snap: _State) -> None:
            self._s = snap

        track_rollback(self, lambda: _copy(self._s), restore)

    @staticmethod
    def _require_tx(what: str) -> None:
        if not db.in_transaction():
            raise NotInTransaction(f"{what} 必须在事务里调用（kernel.db.transaction()）")

    def _next_seq(self) -> int:
        self._s.seq += 1
        return self._s.seq

    # ---- 当前主体 ----

    def _principal(self) -> str:
        """当前主体：代办时是被代办的本人。"""
        me = access_api.whoami()
        return me.acting_for or me.account_id

    # ---- 审计 ----

    @staticmethod
    def _hash(ev: t.AuditEvent) -> str:
        body = asdict(replace(ev, hash=""))
        return request_digest(body)

    def _append_audit(self, draft: t.AuditDraft) -> str:
        self._touch()
        ctx = context.current()
        now = self.clock.now()
        if ctx.principal_id is None:
            principal, executor, caller, rev = "system", None, "job" if ctx.job_id else "system", 0
        else:
            me = access_api.whoami()
            principal = me.acting_for or me.account_id
            executor = me.account_id if me.acting_for else None
            caller = "job" if ctx.job_id else ("service" if me.kind == "service" else "human")
            rev = me.policy_rev
        prev = self._s.audits[-1].hash if self._s.audits else None
        ev = t.AuditEvent(
            event_id="aud_" + uuid7().hex,
            occurred_at=now,
            received_at=now,
            principal_id=principal,
            executor_id=executor,
            caller_type=caller,  # pyright: ignore[reportArgumentType]
            delegation_id=None,
            policy_version_set={"policyRev": rev},
            capability_id=draft.capability_id,
            contract_version=draft.contract_version,
            target=draft.target,
            result=draft.result,
            before_digest=draft.before_digest,
            after_digest=draft.after_digest,
            reason=draft.reason,
            confirmation_id=draft.confirmation_id,
            command_id=draft.command_id,
            job_id=draft.job_id or ctx.job_id,
            evidence_ref=draft.evidence_ref,
            prev_hash=prev,
            hash="",
        )
        ev = replace(ev, hash=self._hash(ev))
        self._s.audits.append(ev)
        return ev.event_id

    def audit_in_tx(self, draft: t.AuditDraft) -> str:
        self._require_tx("audit_in_tx")
        return self._append_audit(draft)

    def audit_for(
        self,
        target: t.ObjectRef,
        *,
        access_target: Target | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> Page[t.AuditEvent]:
        if self.enforce_access:
            # access_target 是对象的真实归属；不给 = 归属未知，只有“全部”范围的授权能过。
            access_api.check(
                t.AUDIT_READ_CAPABILITY, access_target if access_target is not None else Target()
            ).require()
        rows = [(i, ev.event_id, ev) for i, ev in enumerate(self._s.audits, 1) if ev.target == target]
        page = _page(rows[::-1], cursor, limit)
        self._append_audit(t.AuditDraft(t.AUDIT_READ_CAPABILITY, "1.0.0", target, "succeeded"))  # 查看审计本身也留痕
        return page

    # ---- 待办 ----

    def register_todo_type(self, decl: t.TodoTypeDecl) -> None:
        old = self._todo_types.get(decl.type)
        if old is not None and old != decl:
            raise RegistrationConflict(f"待办类型 {decl.type} 已用不同内容登记过")
        self._todo_types[decl.type] = decl

    def _todo_view(self, x: _Todo) -> t.TodoView:
        return t.TodoView(
            x.todo_id,
            x.key,
            x.title_key,
            x.params,
            x.due_at,
            x.state,
            x.opened_at,
            x.assignees,
            x.done_by,
            x.done_at,
            source_version=x.source_version,
        )

    def _todo(self, key: t.TodoKey) -> _Todo:
        found = self._s.todos.get(key)
        if found is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, details={"type": key.type})
        return found

    def todo_open_in_tx(self, draft: t.TodoDraft) -> t.TodoView:
        self._require_tx("todo_open_in_tx")
        decl = self._todo_types.get(draft.key.type)
        if decl is None:
            raise NotRegistered(f"待办类型 {draft.key.type!r} 没有登记")
        current = self._s.todos.get(draft.key)
        if current is not None:
            if draft.source_version <= current.source_version:
                return self._todo_view(current)  # 同一事件重投 / 迟到的旧事件：什么也不做
            if current.state == "open":
                raise AppError(
                    ErrorCode.RESOURCE_VERSION_CONFLICT,
                    details={"state": current.state, "sourceVersion": current.source_version},
                )
        self._touch()
        now = self.clock.now()
        x = _Todo(
            self._next_seq(),
            "td_" + uuid7().hex,
            draft.key,
            draft.source_version,
            draft.title_key or decl.title_key,
            dict(draft.params),
            draft.due_at,
            "open",
            now,
            tuple(dict.fromkeys(draft.assignees)),
        )
        self._s.todos[draft.key] = x
        return self._todo_view(x)

    def todo_reassign_in_tx(self, key: t.TodoKey, assignees: Sequence[str]) -> t.TodoView:
        self._require_tx("todo_reassign_in_tx")
        x = self._todo(key)
        if x.state != "open":
            raise AppError(ErrorCode.RESOURCE_VERSION_CONFLICT, details={"state": x.state})
        who = tuple(dict.fromkeys(assignees))
        if not who:
            raise AppError(ErrorCode.INVALID_REQUEST, details={"field": "assignees"})
        if who != x.assignees:
            self._touch()
            x.assignees = who
        return self._todo_view(x)

    def todo_close_in_tx(self, key: t.TodoKey, *, done_by: str) -> t.TodoView:
        self._require_tx("todo_close_in_tx")
        x = self._todo(key)
        if x.state == "done":
            return self._todo_view(x)  # 先到先得
        if x.state == "withdrawn":
            raise AppError(ErrorCode.RESOURCE_VERSION_CONFLICT, details={"state": x.state})
        if done_by not in x.assignees:
            raise AppError(ErrorCode.INVALID_REQUEST, details={"field": "done_by"})
        self._touch()
        x.state, x.done_by, x.done_at = "done", done_by, self.clock.now()
        return self._todo_view(x)

    def todo_withdraw_in_tx(self, key: t.TodoKey) -> t.TodoView:
        self._require_tx("todo_withdraw_in_tx")
        x = self._todo(key)
        if x.state == "open":
            self._touch()
            x.state = "withdrawn"
        return self._todo_view(x)

    def get_todo(self, key: t.TodoKey) -> t.TodoView:
        return self._todo_view(self._todo(key))

    def my_todos(
        self, *, state: t.TodoState | None = None, cursor: str | None = None, limit: int | None = None
    ) -> Page[t.TodoView]:
        me = self._principal()
        mine = [x for x in self._s.todos.values() if me in x.assignees and (state is None or x.state == state)]
        rows = sorted(((x.seq, x.todo_id, self._todo_view(x)) for x in mine), key=lambda r: -r[0])
        return _page(rows, cursor, limit)

    # ---- 文案 ----

    def register_texts(self, module: str, texts: Mapping[str, t.TextEntry]) -> None:
        changed = False
        for key, entry in texts.items():
            if not key.startswith(module + ".") or not t.is_text_key(key):
                raise ValueError(f"文案键 {key!r} 不合法或不属于模块 {module}")
            old = self._texts.get(key)
            if old == entry:
                continue
            self._texts[key] = entry
            changed = True
        if changed:
            for lang in t.LANGS:
                self._pack_n[lang] += 1

    def pack_version(self, lang: t.Lang) -> str:
        return f"{lang}@{self._pack_n[lang]}"

    def _render(self, key: str, params: Mapping[str, object] | None, lang: t.Lang) -> str:
        entry = self._texts.get(key)
        if entry is None:
            raise NotRegistered(f"文案键 {key!r} 没有登记")
        try:
            return string.Formatter().vformat(entry.get(lang), (), dict(params or {}))
        except KeyError as e:
            raise TextParamMissing(f"{key} 缺参数 {e.args[0]}") from e

    def text(self, key: str, params: Mapping[str, object] | None = None, *, lang: t.Lang | None = None) -> str:
        wanted = lang or context.current().lang or t.DEFAULT_LANG
        return self._render(key, params, wanted if wanted in t.LANGS else t.DEFAULT_LANG)  # pyright: ignore[reportArgumentType]

    # ---- 通知 ----

    def _notif_view(self, n: _Notif) -> t.NotificationView:
        d = n.draft
        return t.NotificationView(
            n.notification_id,
            d.type,
            d.category,
            d.severity,
            d.subject,
            d.message_key,
            n.params,
            n.text,
            n.lang,
            n.pack_version,
            n.count,
            n.created_at,
            n.last_at,
            n.read_at,
        )

    def notify_in_tx(self, draft: t.NotifyDraft) -> None:
        self._require_tx("notify_in_tx")
        if draft.message_key not in self._texts:
            raise NotRegistered(f"文案键 {draft.message_key!r} 没有登记")
        self._touch()
        now = self.clock.now()
        for who in dict.fromkeys(draft.recipients):
            if (
                draft.view_capability is not None
                and not access_api.check(draft.view_capability, draft.access_target, subject=who).allowed
            ):
                continue
            # 幂等键：同一收件人同一事件已经发过，重投时什么也不做（合并计数也不变）
            if any(n.recipient == who and n.draft.idempotency_key == draft.idempotency_key for n in self._s.notifs):
                continue
            same = next(
                (
                    n
                    for n in reversed(self._s.notifs)
                    if draft.merge_key is not None
                    and n.recipient == who
                    and n.draft.merge_key == draft.merge_key
                    and n.read_at is None
                    and now - n.last_at < MERGE_WINDOW
                ),
                None,
            )
            if same is not None:
                same.count += 1
                same.last_at = now
                same.params = dict(draft.params)
                same.text = self._render(same.draft.message_key, same.params, same.lang)
                same.pack_version = self.pack_version(same.lang)
                continue
            lang = self._langs.get(who, t.DEFAULT_LANG)
            self._s.notifs.append(
                _Notif(
                    self._next_seq(),
                    "nt_" + uuid7().hex,
                    who,
                    draft,
                    dict(draft.params),
                    lang,
                    self._render(draft.message_key, draft.params, lang),
                    self.pack_version(lang),
                    now,
                    now,
                )
            )

    def my_notifications(
        self, *, unread_only: bool = False, cursor: str | None = None, limit: int | None = None
    ) -> Page[t.NotificationView]:
        me = self._principal()
        mine = [n for n in self._s.notifs if n.recipient == me and (not unread_only or n.read_at is None)]
        rows = sorted(((n.seq, n.notification_id, self._notif_view(n)) for n in mine), key=lambda r: -r[0])
        return _page(rows, cursor, limit)

    def mark_read(self, notification_ids: Sequence[str]) -> int:
        me = self._principal()
        ids = set(notification_ids)
        todo = [n for n in self._s.notifs if n.notification_id in ids and n.recipient == me and n.read_at is None]
        if todo:
            self._touch()
            now = self.clock.now()
            for n in todo:
                n.read_at = now
        return len(todo)

    def unread_count(self) -> int:
        me = self._principal()
        return sum(1 for n in self._s.notifs if n.recipient == me and n.read_at is None)

    # ---- 文件引用 ----

    def _asset_view(self, a: _Asset) -> t.AssetVersionView:
        return t.AssetVersionView(
            a.asset_id, a.version, a.state, a.name, a.content_type, a.size, a.sha256, a.created_at
        )

    def _asset(self, asset_id: str, version: int) -> _Asset:
        found = self._s.assets.get((asset_id, version))
        if found is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, details={"assetId": asset_id})
        return found

    def ref_authorizer(self, ref_module: str, check: Callable[[t.ObjectRef], bool]) -> None:
        self._authorizers[ref_module] = check

    @staticmethod
    def _same(r: t.AssetRef, asset_id: str, version: int, mod: str, obj: t.ObjectRef, field_: str) -> bool:
        return (r.asset_id, r.version, r.ref_module, r.ref_object, r.ref_field) == (asset_id, version, mod, obj, field_)

    def add_ref(
        self, asset_id: str, version: int, *, ref_module: str, ref_object: t.ObjectRef, ref_field: str
    ) -> t.AssetRef:
        self._require_tx("add_ref")
        a = self._asset(asset_id, version)
        if a.state in _UNAVAILABLE:
            raise AppError(ErrorCode.INVALID_REQUEST, details={"field": "asset", "state": a.state})
        for r in self._s.refs:
            if self._same(r, asset_id, version, ref_module, ref_object, ref_field):
                return r
        self._touch()
        ref = t.AssetRef(asset_id, version, ref_module, ref_object, ref_field, self.clock.now())
        self._s.refs.append(ref)
        return ref

    def remove_ref(
        self, asset_id: str, version: int, *, ref_module: str, ref_object: t.ObjectRef, ref_field: str
    ) -> None:
        self._require_tx("remove_ref")
        keep = [r for r in self._s.refs if not self._same(r, asset_id, version, ref_module, ref_object, ref_field)]
        if len(keep) != len(self._s.refs):
            self._touch()
            self._s.refs = keep

    def assets_of(self, ref_module: str, ref_object: t.ObjectRef) -> tuple[t.AssetVersionView, ...]:
        return tuple(
            self._asset_view(self._asset(r.asset_id, r.version))
            for r in self._s.refs
            if r.ref_module == ref_module and r.ref_object == ref_object
        )

    def download_grant(
        self, asset_id: str, version: int, *, ref_module: str, ref_object: t.ObjectRef, ref_field: str
    ) -> t.DownloadGrant:
        check = self._authorizers.get(ref_module)
        if check is None:
            raise NotRegistered(f"模块 {ref_module!r} 没有登记 ref_authorizer")
        if not check(ref_object):
            raise AppError(ErrorCode.ACCESS_DENIED)
        if not any(self._same(r, asset_id, version, ref_module, ref_object, ref_field) for r in self._s.refs):
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, details={"assetId": asset_id})
        a = self._asset(asset_id, version)
        if a.state != "available":
            raise AppError(ErrorCode.DEPENDENCY_BLOCKED, details={"assetId": asset_id, "state": a.state})
        return t.DownloadGrant(
            asset_id,
            version,
            a.name,
            a.content_type,
            a.size,
            f"stub://download/{asset_id}/{version}/{uuid7().hex[:12]}",
            self.clock.now() + GRANT_TTL,
        )


def _copy(state: _State) -> _State:
    return _State(
        list(state.audits),
        {k: replace(v) for k, v in state.todos.items()},
        [replace(n) for n in state.notifs],
        {k: replace(v) for k, v in state.assets.items()},
        {k: replace(v) for k, v in state.blobs.items()},
        list(state.refs),
        state.seq,
    )


@pytest.fixture
def facilities_stub(access_stub: InMemoryAccess) -> Generator[InMemoryFacilities]:
    """装入测试桩（时钟与 access_stub 共用）；测试结束恢复原来的实现，状态不外漏。"""
    stub = InMemoryFacilities(access_stub.clock)
    previous = _provider.set_provider(stub)
    try:
        yield stub
    finally:
        _provider.set_provider(previous)
