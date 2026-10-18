"""请求上下文（后端详细设计·总图 2）：中间件在请求开始时设置，日志与错误体从这里取。"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass

from titanloom.kernel.ids import uuid7


@dataclass(frozen=True, slots=True)
class RequestContext:
    request_id: str
    principal_id: str | None = None
    job_id: str | None = None
    plugin_id: str | None = None


_ctx: ContextVar[RequestContext | None] = ContextVar("titanloom_request_ctx", default=None)


def current() -> RequestContext:
    """当前请求上下文；不在请求里（例如后台程序启动时）返回一个新的。"""
    c = _ctx.get()
    if c is None:
        c = RequestContext(request_id=new_request_id())
        _ctx.set(c)
    return c


def peek() -> RequestContext | None:
    """有就返回，没有不新建（日志用）。"""
    return _ctx.get()


def bind(ctx: RequestContext) -> object:
    """设置上下文，返回令牌，用完交给 reset。"""
    return _ctx.set(ctx)


def reset(token: object) -> None:
    _ctx.reset(token)  # pyright: ignore[reportArgumentType]


def new_request_id() -> str:
    return "req_" + uuid7().hex[:20]
