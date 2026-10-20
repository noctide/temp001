"""execution.api 背后的实现怎么装入（只两处：create_app() 启动时装真实实现；测试用 testing 里的 fixture 装测试桩）。

当前主体、请求编号取自 `kernel.context`，不经过这里。
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Generator, Mapping
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Protocol

from titanloom.access.api import Target
from titanloom.execution.api import types as t


class ExecutionApi(Protocol):
    def register_binding(self, binding: t.ExecutionBinding) -> None: ...

    def job_handler(self, job_type: str, handler: Callable[[t.JobContext], t.JobResult]) -> None: ...

    def reconcile_handler(self, job_type: str, handler: Callable[[t.JobView], t.Reconciliation]) -> None: ...

    def version_validator(self, capability_id: str, check: Callable[[t.TargetRef | None, str], bool]) -> None: ...

    def prepare(
        self,
        capability_id: str,
        *,
        params: Mapping[str, Any],
        idempotency_key: str,
        target: t.TargetRef | None = None,
        expected_version: str | None = None,
        preview: t.PreviewSpec | None = None,
        scope: t.ScopeKey | None = None,
        access_target: Target | None = None,
    ) -> t.PrepareResult: ...

    def confirm(self, command_id: str, *, command_digest: str) -> t.Confirmation: ...

    def submit(self, command_id: str, *, idempotency_key: str) -> t.Invocation: ...

    def cancel(self, command_id: str) -> None: ...

    def cancel_job(self, job_id: uuid.UUID) -> t.JobView: ...

    def enqueue_in_tx(
        self,
        job_type: str,
        *,
        owner_module: str,
        input_refs: Mapping[str, str],
        lane: t.Lane = "light",
        scope: t.ScopeKey | None = None,
        not_before: datetime | None = None,
        invocation_id: str | None = None,
    ) -> t.JobRef: ...

    def emit_in_tx(self, event: t.EventDraft) -> str: ...

    def schedule(self, rule: t.ScheduleRuleSpec) -> str: ...

    def set_schedule_status(self, rule_id: str, status: str) -> None: ...

    def get_job(self, job_id: uuid.UUID) -> t.JobView: ...

    def subscribe(self, subscriber: str, event_type: str, handler: Callable[[t.Event], None]) -> None: ...


_provider: ExecutionApi | None = None


def set_provider(provider: ExecutionApi | None) -> ExecutionApi | None:
    """装入实现，返回原来的（用完要装回去）。"""
    global _provider
    previous = _provider
    _provider = provider
    return previous


@contextmanager
def use_provider(provider: ExecutionApi) -> Generator[ExecutionApi]:
    previous = set_provider(provider)
    try:
        yield provider
    finally:
        set_provider(previous)


def provider() -> ExecutionApi:
    if _provider is None:
        raise RuntimeError("execution 的实现还没装入：启动时由 create_app() 装，测试用 execution_stub")
    return _provider
