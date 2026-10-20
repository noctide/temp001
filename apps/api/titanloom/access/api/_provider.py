"""access.api 背后的实现怎么装入（只两处：create_app() 启动时装真实实现；测试用 testing 里的 fixture 装测试桩）。

当前主体不放在这里：实现从 `kernel.context.current().principal_id` 取。
"""

from __future__ import annotations

from collections.abc import Generator, Mapping, Sequence
from contextlib import contextmanager
from datetime import date
from typing import Protocol

from titanloom.access.api.types import (
    AccessFilter,
    CapabilityDecl,
    Decision,
    FeatureDecl,
    Member,
    Membership,
    ScopeRef,
    Target,
    Whoami,
)


class AccessApi(Protocol):
    def whoami(self) -> Whoami: ...

    def check(self, capability: str, target: Target | None = None, *, subject: str | None = None) -> Decision: ...

    def filter(self, capability: str, resource_type: str, *, subject: str | None = None) -> AccessFilter: ...

    def members(
        self, scope: ScopeRef, *, on: date | None = None, include_descendants: bool = False
    ) -> tuple[Member, ...]: ...

    def memberships(self, person_id: str, *, on: date | None = None) -> tuple[Membership, ...]: ...

    def register(
        self,
        module: str,
        *,
        capabilities: Sequence[CapabilityDecl] = (),
        features: Sequence[FeatureDecl] = (),
        permission_fields: Mapping[str, Sequence[str]] | None = None,
        maskable_columns: Mapping[str, Sequence[str]] | None = None,
    ) -> None: ...


_provider: AccessApi | None = None


def set_provider(provider: AccessApi | None) -> AccessApi | None:
    """装入实现，返回原来的（用完要装回去）。"""
    global _provider
    previous = _provider
    _provider = provider
    return previous


@contextmanager
def use_provider(provider: AccessApi) -> Generator[AccessApi]:
    previous = set_provider(provider)
    try:
        yield provider
    finally:
        set_provider(previous)


def provider() -> AccessApi:
    if _provider is None:
        raise RuntimeError("access 的实现还没装入：启动时由 create_app() 装，测试用 access_stub")
    return _provider
