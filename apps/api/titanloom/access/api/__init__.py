"""access.api：别的模块唯一能引用的 access 入口（身份与权限 10）。

    from titanloom.access.api import check, access_filter, whoami

实现在启动时装入（见 `_provider`），模块代码只调这里的函数。本轮不含 explain / who_can / find_people / write_grant。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date

from titanloom.access.api import _provider
from titanloom.access.api._provider import AccessApi, set_provider, use_provider
from titanloom.access.api.types import (
    AccessFilter,
    CapabilityDecl,
    Decision,
    FeatureDecl,
    Member,
    Membership,
    Predicate,
    ScopeRef,
    StepResult,
    Target,
    Whoami,
)

__all__ = [
    "AccessApi",
    "AccessFilter",
    "CapabilityDecl",
    "Decision",
    "FeatureDecl",
    "Member",
    "Membership",
    "Predicate",
    "ScopeRef",
    "StepResult",
    "Target",
    "Whoami",
    "access_filter",
    "check",
    "members",
    "memberships",
    "register",
    "set_provider",
    "use_provider",
    "whoami",
]


def whoami() -> Whoami:
    """当前主体、所在部门（含兼岗）、是否管家代办。主体取自 kernel.context。"""
    return _provider.provider().whoami()


def check(capability: str, target: Target | None = None, *, subject: str | None = None) -> Decision:
    """能不能。subject 默认当前主体；查别人需要诊断资格。"""
    return _provider.provider().check(capability, target, subject=subject)


def access_filter(capability: str, resource_type: str, *, subject: str | None = None) -> AccessFilter:
    """能看哪些。翻译成查询条件用 access.api.sql.to_sqlalchemy。"""
    return _provider.provider().filter(capability, resource_type, subject=subject)


def members(scope: ScopeRef, *, on: date | None = None, include_descendants: bool = False) -> tuple[Member, ...]:
    """部门 / 项目成员，可按日期。"""
    return _provider.provider().members(scope, on=on, include_descendants=include_descendants)


def memberships(person_id: str, *, on: date | None = None) -> tuple[Membership, ...]:
    """某人所在的部门与项目，可按日期。"""
    return _provider.provider().memberships(person_id, on=on)


def register(
    module: str,
    *,
    capabilities: Sequence[CapabilityDecl] = (),
    features: Sequence[FeatureDecl] = (),
    permission_fields: Mapping[str, Sequence[str]] | None = None,
    maskable_columns: Mapping[str, Sequence[str]] | None = None,
) -> None:
    """模块登记能力、功能、权限字段、可遮挡列。同样内容重复登记没有影响；同一个编号内容不同则报错。"""
    _provider.provider().register(
        module,
        capabilities=capabilities,
        features=features,
        permission_fields=permission_fields,
        maskable_columns=maskable_columns,
    )
