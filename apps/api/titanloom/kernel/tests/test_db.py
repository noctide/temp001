"""数据库连接与事务（kernel.db）、测试工具（kernel.testing）。事务语义用临时文件 SQLite 验证，不需要 PostgreSQL。"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, create_engine, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from titanloom.kernel import db as kdb
from titanloom.kernel.testing import schema_session_fixture

demo = MetaData(schema="demo")
item = Table("item", demo, Column("id", Integer, primary_key=True))

db_session = schema_session_fixture(demo)


@pytest.fixture
def sqlite_engine() -> Generator[Engine]:
    # 不用 pytest 的 tmp_path：Windows 上它的 pytest-current 链接可能被占用而在退出时报错
    with TemporaryDirectory() as d:
        engine = create_engine(f"sqlite:///{Path(d) / 't.db'}")
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY)"))
        kdb.set_engine(engine)
        yield engine
        kdb.set_engine(None)
        engine.dispose()


def count(engine: Engine) -> int:
    with engine.connect() as conn:
        return conn.execute(text("SELECT count(*) FROM t")).scalar_one()


def test_commit_on_success(sqlite_engine: Engine) -> None:
    with kdb.transaction() as s:
        s.execute(text("INSERT INTO t VALUES (1)"))
    assert count(sqlite_engine) == 1


def test_rollback_on_error(sqlite_engine: Engine) -> None:
    with pytest.raises(ValueError, match="boom"), kdb.transaction() as s:
        s.execute(text("INSERT INTO t VALUES (1)"))
        raise ValueError("boom")
    assert count(sqlite_engine) == 0


def test_nested_joins_outer_and_rolls_back_together(sqlite_engine: Engine) -> None:
    with pytest.raises(ValueError, match="late"), kdb.transaction() as outer:
        outer.execute(text("INSERT INTO t VALUES (1)"))
        with kdb.transaction() as inner:
            assert inner is outer  # 加入同一个事务，不另开
            inner.execute(text("INSERT INTO t VALUES (2)"))
        raise ValueError("late")  # 里层“成功”了，外层失败，两条都不留
    assert count(sqlite_engine) == 0


def test_nested_does_not_commit_early(sqlite_engine: Engine) -> None:
    with kdb.transaction():
        with kdb.transaction() as inner:
            inner.execute(text("INSERT INTO t VALUES (1)"))
        assert count(sqlite_engine) == 0  # 里层结束不提交，要等最外层
    assert count(sqlite_engine) == 1


def test_current_session_outside_transaction() -> None:
    assert not kdb.in_transaction()
    with pytest.raises(RuntimeError, match="不在事务里"):
        kdb.current_session()


def test_context_cleared_after_exit(sqlite_engine: Engine) -> None:
    with kdb.transaction():
        assert kdb.in_transaction()
    assert not kdb.in_transaction()


def test_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(kdb.ENV_URL, raising=False)
    monkeypatch.delenv(kdb.ENV_OWNER_URL, raising=False)
    with pytest.raises(kdb.DatabaseNotConfigured):
        kdb.database_url()
    monkeypatch.setenv(kdb.ENV_URL, "postgresql+psycopg://app@h/db")
    assert kdb.database_url() == "postgresql+psycopg://app@h/db"
    assert kdb.database_url(owner=True) == "postgresql+psycopg://app@h/db"  # 没设 owner 就退回运行账号
    monkeypatch.setenv(kdb.ENV_OWNER_URL, "postgresql+psycopg://owner@h/db")
    assert kdb.database_url(owner=True) == "postgresql+psycopg://owner@h/db"
    assert kdb.database_url() == "postgresql+psycopg://app@h/db"


def test_schema_session_fixture_rolls_back_between_tests(db_session: Session) -> None:
    """需要 PostgreSQL（TITANLOOM_TEST_DB_URL）；没设时跳过。"""
    assert kdb.current_session() is db_session
    with kdb.transaction() as s:  # store 里的写法：加入测试事务
        s.execute(item.insert().values(id=1))
    assert db_session.execute(select(func.count()).select_from(item)).scalar_one() == 1


def test_schema_session_fixture_starts_clean(db_session: Session) -> None:
    assert db_session.execute(select(func.count()).select_from(item)).scalar_one() == 0
