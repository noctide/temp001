"""数据库连接与事务（总图 2 第 7 关、5、6；总框架 12.3）。

规矩：
- 引擎只在这里建；模块的 store 只拿会话（`transaction()` / `current_session()`），不建引擎、不读连接串。
- 一个请求（或一件后台任务）一个事务：最外层 `transaction()` 负责提交 / 回滚；里面再调用只是加入同一个事务，
  不提前提交。业务记录、幂等记录、审计、outbox 事件因此能一次写完（能力契约 7.2）。
- 连接串从环境变量读（不进仓库）：`TITANLOOM_DB_URL` 是运行账号；`TITANLOOM_DB_OWNER_URL` 是迁移用的 owner 账号，
  没设时迁移也用运行账号（本机开发）。形如 `postgresql+psycopg://user:password@localhost:5432/titanloom`。
- 首期用同步会话（psycopg 3）：路由写成普通 `def`，由框架放进线程池；Runner 本来就是同步循环。
"""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

ENV_URL = "TITANLOOM_DB_URL"
ENV_OWNER_URL = "TITANLOOM_DB_OWNER_URL"

_engine: Engine | None = None
_current: ContextVar[Session | None] = ContextVar("titanloom_db_session", default=None)


class DatabaseNotConfigured(RuntimeError):
    """没有设置连接串。启动期的配置错误，不是业务错误，不走 AppError。"""


def database_url(owner: bool = False) -> str:
    """owner=True 取迁移账号的连接串，没设则退回运行账号。"""
    url = (os.environ.get(ENV_OWNER_URL) if owner else None) or os.environ.get(ENV_URL)
    if not url:
        raise DatabaseNotConfigured(f"环境变量 {ENV_URL} 没有设置")
    return url


def make_engine(url: str) -> Engine:
    # pool_pre_ping：连接被数据库断开后不把坏连接交给业务；连接上限 20 由部署参数控制（总图 1）
    return create_engine(url, pool_pre_ping=True, future=True)


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = make_engine(database_url())
    return _engine


def set_engine(engine: Engine | None) -> None:
    """测试与引导用：换掉（或清掉）进程里共用的引擎。"""
    global _engine
    _engine = engine


def current_session() -> Session:
    """当前事务里的会话；不在 `transaction()` 里调用是程序错误。"""
    s = _current.get()
    if s is None:
        raise RuntimeError("不在事务里：先用 transaction() 包起来")
    return s


def in_transaction() -> bool:
    return _current.get() is not None


@contextmanager
def transaction() -> Generator[Session]:
    """最外层：开会话、正常结束提交、出错回滚。已在事务里：加入它，由最外层决定提交。"""
    outer = _current.get()
    if outer is not None:
        yield outer
        return
    session = Session(get_engine(), expire_on_commit=False)
    token = _current.set(session)
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        _current.reset(token)
        session.close()


@contextmanager
def bind_session(session: Session) -> Generator[Session]:
    """把一个现成的会话当作当前事务（测试用：事务回滚的 fixture 用它；里面的 transaction() 都加入它）。"""
    token = _current.set(session)
    try:
        yield session
    finally:
        _current.reset(token)
