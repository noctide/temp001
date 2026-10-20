"""测试工具（工程规范 4.3；各模块的数据库测试都用这里，不各写一份）。

用法（模块的 `tests/conftest.py`）：

    from titanloom.kernel.testing import schema_session_fixture
    from titanloom.attendance.store.models import metadata

    db = schema_session_fixture(metadata)      # 测试里写参数 `db` 就拿到一个会话

每个测试拿到的是：临时 schema（名字随机，把 metadata 里的表建在里面）+ 一个绑定为“当前事务”的会话，
测试里 store 调 `transaction()` 都加入它；测试结束整个 schema 删掉，不留数据，不碰真实 schema。
没设 `TITANLOOM_TEST_DB_URL`（或连不上）时，这类测试自动跳过，不算失败。
测试库必须是专门的库，不要指向有真实数据的库。
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable, Generator

import pytest
from sqlalchemy import Engine, MetaData, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from titanloom.kernel import db as kdb

ENV_TEST_URL = "TITANLOOM_TEST_DB_URL"


def connect_test_db() -> Engine:
    """连测试库；没设或连不上就跳过当前测试。"""
    url = os.environ.get(ENV_TEST_URL)
    if not url:
        pytest.skip(f"没设置 {ENV_TEST_URL}，跳过需要数据库的测试")
    engine = kdb.make_engine(url)
    try:
        with engine.connect():
            pass
    except SQLAlchemyError:
        engine.dispose()
        pytest.skip("连不上测试库，跳过需要数据库的测试")
    return engine


def schema_session_fixture(*metadatas: MetaData) -> Callable[..., Generator[Session]]:
    """生成一个 pytest fixture：临时 schema 里建好这些 metadata 的表，交出一个当前事务的会话。"""

    @pytest.fixture
    def _db() -> Generator[Session]:
        engine = connect_test_db()
        tmp = f"t_{uuid.uuid4().hex[:12]}"
        names = {m.schema for m in metadatas if m.schema}
        mapping = {n: tmp for n in names}
        # 一个测试里的几个模块 schema 映射到同一个临时 schema；表名跨模块重名时请分开测试
        with engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA "{tmp}"'))
            mconn = conn.execution_options(schema_translate_map=mapping)
            for m in metadatas:
                m.create_all(mconn)
        try:
            conn = engine.connect().execution_options(schema_translate_map=mapping)
            outer = conn.begin()
            session = Session(bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False)
            try:
                with kdb.bind_session(session):
                    yield session
            finally:
                session.close()
                outer.rollback()
                conn.close()
        finally:
            with engine.begin() as conn:
                conn.execute(text(f'DROP SCHEMA "{tmp}" CASCADE'))
            engine.dispose()

    return _db
