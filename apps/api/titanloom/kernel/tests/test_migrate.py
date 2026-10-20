"""迁移脚手架（kernel.migrate）：配置按模块独立，版本表在本模块 schema。不连数据库。"""

from __future__ import annotations

from pathlib import Path

import pytest

from titanloom.kernel import migrate


def test_config_per_module() -> None:
    cfg = migrate.config_for("attendance", "postgresql+psycopg://o@h/db")
    assert cfg.attributes["module"] == "attendance"
    versions = Path(cfg.get_main_option("version_locations", ""))
    assert versions.parts[-3:] == ("attendance", "migrations", "versions")
    assert cfg.get_main_option("sqlalchemy.url") == "postgresql+psycopg://o@h/db"
    assert migrate.version_table("attendance") == "attendance_alembic"


def test_module_metadata_uses_models() -> None:
    md = migrate.module_metadata("attendance")
    assert md.schema == "attendance"
    assert "attendance.type" in md.tables


def test_module_without_models_is_an_error() -> None:
    with pytest.raises(ModuleNotFoundError):
        migrate.module_metadata("shell")


# ---- R1-1：迁移新建的 schema，运行账号要有权限 ----


class _FakeConn:
    """记下执行的 SQL；pg_roles 查询按 role_exists 回答。"""

    def __init__(self, role_exists: bool = True) -> None:
        self.role_exists = role_exists
        self.sql: list[str] = []

    def execute(self, stmt: object, params: object = None) -> _FakeConn:
        self.sql.append(str(stmt))
        return self

    def scalar(self) -> int | None:
        return 1 if self.role_exists else None


def test_new_schema_is_granted_to_runtime_role() -> None:
    conn = _FakeConn()
    migrate.ensure_schema(conn, "forms", "titanloom_app")  # type: ignore[arg-type]
    sql = "\n".join(conn.sql)
    assert 'CREATE SCHEMA IF NOT EXISTS "forms"' in sql
    assert 'GRANT USAGE ON SCHEMA "forms" TO "titanloom_app"' in sql
    assert (
        'ALTER DEFAULT PRIVILEGES IN SCHEMA "forms" GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "titanloom_app"'
        in sql
    )
    assert 'ALTER DEFAULT PRIVILEGES IN SCHEMA "forms" GRANT USAGE, SELECT ON SEQUENCES TO "titanloom_app"' in sql
    assert not any("CREATE TABLE" in line or "CREATE ON SCHEMA" in line for line in conn.sql)  # 运行账号不能建表


def test_missing_runtime_role_is_an_error_not_a_silent_ungranted_schema() -> None:
    conn = _FakeConn(role_exists=False)
    with pytest.raises(migrate.RuntimeRoleMissing, match=r"create\.ps1"):
        migrate.ensure_schema(conn, "forms", "titanloom_app")  # type: ignore[arg-type]
    assert not any("CREATE SCHEMA" in line for line in conn.sql)


def test_runtime_role_comes_from_runtime_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TITANLOOM_DB_URL", "postgresql+psycopg://svc_runtime:pw@h/db")
    assert migrate.runtime_role() == "svc_runtime"
    monkeypatch.delenv("TITANLOOM_DB_URL")
    assert migrate.runtime_role() == "titanloom_app"


def test_runtime_account_can_use_schema_created_by_migration() -> None:
    """带库：复现 R1-1——schema 由迁移自动建出来之后，运行账号能读写其中新建的表；不经 ensure_schema 则没有 USAGE。"""
    import uuid

    from sqlalchemy import text

    from titanloom.kernel.testing import connect_test_db

    engine = connect_test_db()
    tag = uuid.uuid4().hex[:10]
    role, granted, bare = f"tl_app_{tag}", f"s_{tag}_a", f"s_{tag}_b"
    with engine.connect() as conn:
        try:
            conn.execute(text(f'CREATE ROLE "{role}"'))
        except Exception:  # 没有建角色的权限就跳过
            conn.rollback()
            pytest.skip("测试库账号不能建角色，跳过")
        try:
            migrate.ensure_schema(conn, granted, role)
            conn.execute(text(f'CREATE TABLE "{granted}".t (id serial PRIMARY KEY)'))  # 先授权、后建表
            conn.execute(text(f'CREATE SCHEMA "{bare}"'))  # 原来的做法：只建 schema
            q = "SELECT has_schema_privilege(:r, :s, 'USAGE'), has_table_privilege(:r, :t, 'INSERT')"
            ok = conn.execute(text(q), {"r": role, "s": granted, "t": f'"{granted}".t'}).one()
            assert tuple(ok) == (True, True)
            usage = text("SELECT has_schema_privilege(:r, :s, 'USAGE')")
            assert conn.execute(usage, {"r": role, "s": bare}).scalar() is False
            seq = text("SELECT has_sequence_privilege(:r, :q, 'USAGE')")
            assert conn.execute(seq, {"r": role, "q": f'"{granted}".t_id_seq'}).scalar() is True
        finally:
            conn.rollback()  # DDL 在事务里，角色与 schema 一起撤销，库里不留东西
    engine.dispose()
