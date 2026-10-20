"""access.api 的内存测试桩（给别的模块的测试用；真实实现是另一回事）。

    from titanloom.access.api.testing import access_stub        # 放进模块 tests/conftest.py

    def test_x(access_stub):
        access_stub.grant("acc-A0004", "attendance.record.read", Cond.own_dept("deptId"))
        with as_principal("acc-A0004"):
            assert check("attendance.record.read", Target(dept_id="装配一部")).allowed

判定顺序与 check / filter 共用同一套授权计算，所以“filter 与逐条 check 一致”。它是桩不是缩小版真实现：
没有角色、组、委托、缓存，只有：账户或部门（含下级）→ 能力 → 允许 / 拒绝 → 数据条件。
未登记的能力、权限字段直接报错，用来抓拼写错误。
"""

from __future__ import annotations

from collections.abc import Generator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Literal

import pytest

from titanloom.access.api import _provider
from titanloom.access.api.types import (
    AccessFilter,
    CapabilityDecl,
    Decision,
    DeptRef,
    FeatureDecl,
    Member,
    Membership,
    Predicate,
    ScopeRef,
    Step,
    StepResult,
    Target,
    Whoami,
)
from titanloom.kernel import context
from titanloom.kernel.clock import Clock, FixedClock
from titanloom.kernel.errors import AppError
from titanloom.kernel.reg.errors import ErrorCode


class RegistrationConflict(ValueError):
    """同一个编号重复登记且内容不同。"""


class NotRegistered(LookupError):
    """用了没登记的能力、资源类型或权限字段。"""


@dataclass(frozen=True, slots=True)
class Cond:
    """数据条件（身份与权限 6，只有登记的几种）。field 是调用模块登记的权限字段，all 不需要。"""

    kind: Literal["all", "self", "own_dept", "dept", "project"]
    field: str | None = None
    ref: str | None = None
    tree: bool = False

    @staticmethod
    def all() -> Cond:
        return Cond("all")

    @staticmethod
    def self_(field: str) -> Cond:
        return Cond("self", field)

    @staticmethod
    def own_dept(field: str, *, tree: bool = False) -> Cond:
        return Cond("own_dept", field, tree=tree)

    @staticmethod
    def dept(field: str, dept_id: str, *, tree: bool = False) -> Cond:
        return Cond("dept", field, dept_id, tree)

    @staticmethod
    def project(field: str, project_id: str) -> Cond:
        return Cond("project", field, project_id)


@dataclass(frozen=True, slots=True)
class Grant:
    id: str
    subject: str  # 账户编号，或 "dept:<部门编号>"（该部门含下级的在职人员）
    capability: str
    effect: Literal["allow", "deny"]
    condition: Cond
    mask: tuple[str, ...] = ()


@dataclass(slots=True)
class _Employment:
    person_id: str
    dept_id: str
    primary: bool
    start: date
    end: date | None


@dataclass(slots=True)
class _Account:
    person_id: str | None
    kind: Literal["human", "service", "emergency"] = "human"
    status: Literal["active", "disabled", "locked"] = "active"


@dataclass(slots=True)
class _Registry:
    capabilities: dict[str, CapabilityDecl] = field(default_factory=lambda: {})
    features: dict[str, FeatureDecl] = field(default_factory=lambda: {})
    permission_fields: dict[str, tuple[str, ...]] = field(default_factory=lambda: {})
    maskable_columns: dict[str, tuple[str, ...]] = field(default_factory=lambda: {})


_EPOCH = date(2000, 1, 1)


class InMemoryAccess:
    def __init__(self, clock: Clock | None = None):
        self.clock: Clock = clock or FixedClock(datetime(2026, 10, 20, 8, 0, tzinfo=UTC))
        self.policy_rev = 1
        self._depts: dict[str, tuple[str, str | None]] = {}
        self._people: dict[str, str] = {}
        self._jobs: list[_Employment] = []
        self._accounts: dict[str, _Account] = {}
        self._account_names: dict[str, str] = {}
        self._projects: dict[str, str] = {}
        self._project_members: list[tuple[str, str, str | None]] = []
        self._grants: list[Grant] = []
        self._open_features: set[str] = set()
        self._reg = _Registry()

    # ---- 造数据（每次改动版本号 +1） ----
    def _bump(self) -> None:
        self.policy_rev += 1

    def add_dept(self, dept_id: str, name: str, parent: str | None = None) -> None:
        self._depts[dept_id] = (name, parent)
        self._bump()

    def add_person(self, person_id: str, name: str, dept_id: str, *, account: str | None = None,
                   extra_depts: Sequence[str] = (), start: date = _EPOCH, end: date | None = None) -> None:  # fmt: skip
        self._people[person_id] = name
        self._jobs.append(_Employment(person_id, dept_id, True, start, end))
        self._jobs.extend(_Employment(person_id, d, False, start, end) for d in extra_depts)
        if account:
            self._accounts[account] = _Account(person_id)
            self._account_names[account] = name
        self._bump()

    def add_service(self, account: str, name: str) -> None:
        self._accounts[account] = _Account(None, "service")
        self._account_names[account] = name
        self._bump()

    def set_account_status(self, account: str, status: Literal["active", "disabled", "locked"]) -> None:
        self._accounts[account].status = status
        self._bump()

    def add_project(self, project_id: str, name: str, members: Mapping[str, str | None]) -> None:
        self._projects[project_id] = name
        self._project_members.extend((project_id, p, r) for p, r in members.items())
        self._bump()

    def open_feature(self, feature_id: str, *, opened: bool = True) -> None:
        (self._open_features.add if opened else self._open_features.discard)(feature_id)
        self._bump()

    def grant(self, subject: str, capability: str, condition: Cond | None = None, *,
              effect: Literal["allow", "deny"] = "allow", mask: Sequence[str] = ()) -> Grant:  # fmt: skip
        g = Grant(f"g{len(self._grants) + 1}", subject, capability, effect, condition or Cond.all(), tuple(mask))
        self._grants.append(g)
        self._bump()
        return g

    # ---- 组织辅助 ----
    def _tree(self, dept_id: str) -> set[str]:
        out = {dept_id}
        grew = True
        while grew:
            grew = False
            for d, (_, parent) in self._depts.items():
                if parent in out and d not in out:
                    out.add(d)
                    grew = True
        return out

    def _depts_of(self, person_id: str | None, on: date) -> list[str]:
        return [
            j.dept_id
            for j in self._jobs
            if j.person_id == person_id and j.start <= on and (j.end is None or on <= j.end)
        ]

    def _today(self) -> date:
        return self.clock.now().date()

    def _subjects(self, account: str) -> set[str]:
        """账户本身，加上它任职部门及其各级上级部门的 "dept:" 主体。"""
        acct = self._accounts[account]
        out = {account}
        for d in self._depts_of(acct.person_id, self._today()):
            cur: str | None = d
            while cur is not None:
                out.add(f"dept:{cur}")
                cur = self._depts[cur][1]
        return out

    def _current_account(self) -> str | None:
        return context.current().principal_id

    # ---- 条件 ----
    def _own_depts(self, account: str, cond: Cond) -> set[str]:
        base = set(self._depts_of(self._accounts[account].person_id, self._today()))
        if not cond.tree:
            return base
        out: set[str] = set()
        for d in base:
            out |= self._tree(d)
        return out

    def _matches(self, cond: Cond, account: str, t: Target) -> bool:
        pid = self._accounts[account].person_id
        if cond.kind == "all":
            return True
        if cond.kind == "self":
            return pid is not None and t.owner_person_id == pid
        if cond.kind == "own_dept":
            return t.dept_id is not None and t.dept_id in self._own_depts(account, cond)
        if cond.kind == "dept":
            return (
                t.dept_id is not None
                and cond.ref is not None
                and t.dept_id in (self._tree(cond.ref) if cond.tree else {cond.ref})
            )
        return t.project_id is not None and t.project_id == cond.ref

    def _predicate(self, cond: Cond, account: str) -> Predicate | None:
        """数据条件 → 谓词；部门范围在这里展开成编号。None = 什么都匹配不上。"""
        if cond.field is None:
            raise ValueError("这种条件需要权限字段")
        pid = self._accounts[account].person_id
        if cond.kind == "self":
            return Predicate(cond.field, "eq", (pid,)) if pid else None
        if cond.kind == "project":
            return Predicate(cond.field, "eq", (cond.ref,))
        ids = (
            self._own_depts(account, cond)
            if cond.kind == "own_dept"
            else (self._tree(cond.ref or "") if cond.tree else {cond.ref or ""})
        )
        return Predicate(cond.field, "in", tuple(sorted(ids))) if ids else None

    # ---- 判定 ----
    def _capability(self, capability: str) -> CapabilityDecl:
        cap = self._reg.capabilities.get(capability)
        if cap is None:
            raise NotRegistered(f"能力 {capability!r} 没有登记")
        return cap

    def _identity(self, account: str) -> tuple[str, str] | None:
        a = self._accounts.get(account)
        if a is None:
            return "access.identity.authRequired", "none"
        if a.status == "locked":
            return "access.identity.accountLocked", "none"
        if a.status == "disabled":
            return "access.identity.authRequired", "none"
        return None

    def _grants_for(self, account: str, capability: str, effect: str) -> list[Grant]:
        subs = self._subjects(account)
        return [g for g in self._grants if g.capability == capability and g.effect == effect and g.subject in subs]

    def check(self, capability: str, target: Target | None = None, *, subject: str | None = None) -> Decision:
        cap = self._capability(capability)
        account = subject or self._current_account() or ""
        now = self.clock.now()
        done: list[StepResult] = []

        def deny(
            step: Step, key: str, *, can_request: bool = False, params: Mapping[str, object] | None = None
        ) -> Decision:
            done.append(StepResult(step, "fail", key, dict(params or {})))
            rest = [
                s
                for s in ("identity", "feature", "grant", "agent_gate", "data_scope", "state")
                if s not in {d.step for d in done}
            ]
            done.extend(StepResult(s, "not_checked") for s in rest)  # type: ignore[arg-type]
            return Decision(False, self.policy_rev, now, step, key, can_request=can_request, steps=tuple(done))

        bad = self._identity(account)
        if bad:
            return deny("identity", bad[0])
        done.append(StepResult("identity", "pass"))
        if cap.feature_id:
            if cap.feature_id not in self._open_features:
                return deny("feature", "access.feature.notOpen", can_request=True)
            done.append(StepResult("feature", "pass"))
        else:
            done.append(StepResult("feature", "not_applicable"))
        t = target or Target()
        denies = [g for g in self._grants_for(account, capability, "deny") if self._matches(g.condition, account, t)]
        if denies:
            return deny("grant", "access.grant.denied")
        allows = self._grants_for(account, capability, "allow")
        if not allows:
            return deny("grant", "access.grant.noAllow", can_request=True)
        done.append(StepResult("grant", "pass", grant_refs=tuple(g.id for g in allows)))
        done.append(StepResult("agent_gate", "not_applicable"))
        if target is None:
            matched = allows
            done.append(StepResult("data_scope", "not_applicable"))
        else:
            matched = [g for g in allows if self._matches(g.condition, account, t)]
            if not matched:
                return deny("data_scope", "access.dataScope.outOfScope", can_request=True)
            done.append(StepResult("data_scope", "pass", grant_refs=tuple(g.id for g in matched)))
        done.append(StepResult("state", "not_applicable"))
        masks = self._mask(matched)
        return Decision(
            True, self.policy_rev, now, matched_grant_refs=tuple(g.id for g in matched),
            constraints={"maskColumns": list(masks)} if masks else {}, steps=tuple(done),
        )  # fmt: skip

    @staticmethod
    def _mask(allows: Sequence[Grant]) -> tuple[str, ...]:
        """逐行判定时，各条命中的允许共同要求遮挡的列：只要有一条没要求遮挡，这列就看得到。"""
        common: set[str] = set(allows[0].mask) if allows else set()
        for g in allows[1:]:
            common &= set(g.mask)
        return tuple(sorted(common))

    def filter(self, capability: str, resource_type: str, *, subject: str | None = None) -> AccessFilter:
        cap = self._capability(capability)
        account = subject or self._current_account() or ""
        rev = self.policy_rev
        if self._identity(account) or (cap.feature_id and cap.feature_id not in self._open_features):
            return AccessFilter(rev, none=True)
        allows = self._grants_for(account, capability, "allow")
        denies = self._grants_for(account, capability, "deny")
        if not allows or any(g.condition.kind == "all" for g in denies):
            return AccessFilter(rev, none=True)
        fields = self._reg.permission_fields.get(resource_type)
        for g in (*allows, *denies):
            if g.condition.kind != "all" and (fields is None or g.condition.field not in fields):
                raise NotRegistered(f"{resource_type!r} 没有登记权限字段 {g.condition.field!r}")
        deny_preds = _dedupe(self._predicate(g.condition, account) for g in denies)
        if any(g.condition.kind == "all" for g in allows):
            return AccessFilter(rev, all=True, not_=deny_preds, mask_columns=_mask_union(allows))
        used = [g for g in allows if self._predicate(g.condition, account) is not None]
        if not used:
            return AccessFilter(rev, none=True)
        allow_preds = _dedupe(self._predicate(g.condition, account) for g in used)
        return AccessFilter(rev, any=allow_preds, not_=deny_preds, mask_columns=_mask_union(used))

    # ---- 身份、成员 ----
    def whoami(self) -> Whoami:
        account = self._current_account()
        if account is None or account not in self._accounts:
            raise AppError(ErrorCode.AUTHENTICATION_REQUIRED)
        a = self._accounts[account]
        today = self._today()
        depts = tuple(
            DeptRef(j.dept_id, self._depts[j.dept_id][0], j.primary)
            for j in self._jobs
            if j.person_id == a.person_id and j.start <= today and (j.end is None or today <= j.end)
        )
        return Whoami(account, a.person_id, self._account_names[account], a.kind, depts, self.policy_rev)

    def members(
        self, scope: ScopeRef, *, on: date | None = None, include_descendants: bool = False
    ) -> tuple[Member, ...]:
        day = on or self._today()
        out: list[Member] = []
        if scope.kind == "dept":
            ids = self._tree(scope.id) if include_descendants else {scope.id}
            for j in self._jobs:
                if j.dept_id in ids and j.start <= day and (j.end is None or day <= j.end):
                    out.append(
                        Member(j.person_id, self._people[j.person_id], j.dept_id, self._depts[j.dept_id][0], None, day)
                    )
        else:
            for pr, pid, role in self._project_members:
                if pr == scope.id:
                    d = next(iter(self._depts_of(pid, day)), None)
                    out.append(Member(pid, self._people[pid], d or "", self._depts[d][0] if d else "", role, day))
        return tuple(sorted(out, key=lambda m: (m.dept_id, m.person_id)))

    def memberships(self, person_id: str, *, on: date | None = None) -> tuple[Membership, ...]:
        day = on or self._today()
        out = [Membership("dept", d, self._depts[d][0]) for d in self._depts_of(person_id, day)]
        out += [
            Membership("project", p, self._projects[p], r) for p, pid, r in self._project_members if pid == person_id
        ]
        return tuple(out)

    # ---- 登记 ----
    def register(
        self,
        module: str,
        *,
        maskable_columns: Mapping[str, Sequence[str]] | None = None,
        permission_fields: Mapping[str, Sequence[str]] | None = None,
        features: Sequence[FeatureDecl] = (),
        capabilities: Sequence[CapabilityDecl] = (),
    ) -> None:
        for c in capabilities:
            if not c.id.startswith(module + "."):
                raise RegistrationConflict(f"能力 {c.id!r} 不属于模块 {module!r}")
            _put(self._reg.capabilities, c.id, c)
        for f in features:
            _put(self._reg.features, f.id, f)
        for rt, fields in (permission_fields or {}).items():
            _put(self._reg.permission_fields, rt, tuple(fields))
        for rt, cols in (maskable_columns or {}).items():
            _put(self._reg.maskable_columns, rt, tuple(cols))
        for c in capabilities:
            if c.feature_id and c.feature_id not in self._reg.features:
                raise NotRegistered(f"能力 {c.id!r} 引用的功能 {c.feature_id!r} 没有登记")

    @staticmethod
    def demo(clock: Clock | None = None) -> InMemoryAccess:
        """合成数据里的小组织：6 个叶子部门加上级“生产中心”，12 人（有重名，严述无账户）。账户 = acc-工号。"""
        s = InMemoryAccess(clock)
        s.add_dept("prod", "生产中心")
        for d, n in [
            ("asm1", "装配一部"),
            ("asm2", "装配二部"),
            ("qa", "质检部"),
            ("wh", "仓储物流"),
            ("hr", "人事行政"),
            ("it", "信息部"),
        ]:
            s.add_dept(d, n, "prod" if d in ("asm1", "asm2", "qa", "wh") else None)
        for code, name, dept in [
            ("A0004", "刘畅", "asm1"), ("A0077", "王磊", "asm1"), ("A0102", "张燕", "asm1"), ("A0219", "张燕", "asm1"),
            ("B0001", "马骁", "asm2"), ("B0118", "陈默", "asm2"), ("Q0003", "赵一鸣", "qa"), ("W0003", "何川", "wh"),
            ("W0015", "王磊", "wh"), ("H0012", "周宁", "hr"), ("I0002", "顾远", "it"),
        ]:  # fmt: skip
            s.add_person(code, name, dept, account=f"acc-{code}")
        s.add_person("B0233", "严述", "asm2")
        return s


def _put[T](store: dict[str, T], key: str, value: T) -> None:
    if key in store and store[key] != value:
        raise RegistrationConflict(f"{key!r} 已登记且内容不同")
    store[key] = value


def _mask_union(allows: Sequence[Grant]) -> tuple[str, ...]:
    """列表（filter）不逐行判定，遮挡列取会用到的各条允许之并：宁可多遮，不能把别的部门的列露出来。"""
    return tuple(sorted({c for g in allows for c in g.mask}))


def _dedupe(preds: Sequence[Predicate | None] | Generator[Predicate | None]) -> tuple[Predicate, ...]:
    out: list[Predicate] = []
    for p in preds:
        if p is not None and p not in out:
            out.append(p)
    return tuple(out)


@contextmanager
def as_principal(account_id: str) -> Generator[None]:
    """测试里以某个账户的身份办事（设置 kernel 的请求上下文，结束后恢复）。"""
    token = context.bind(context.RequestContext(context.new_request_id(), principal_id=account_id))
    try:
        yield
    finally:
        context.reset(token)


@pytest.fixture
def access_stub() -> Generator[InMemoryAccess]:
    """装入合成小组织的测试桩；测试结束恢复原来的实现，状态不外漏。"""
    stub = InMemoryAccess.demo()
    previous = _provider.set_provider(stub)
    try:
        yield stub
    finally:
        _provider.set_provider(previous)
