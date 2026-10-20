"""每个模块各自一套迁移（总图 6、12；工程规范 4.3）。

- 迁移脚本放各模块 `migrations/versions/`；公共的 env.py 与模板在 `kernel/alembic_env/`，模块里不再各写一份。
- 每个模块独立的版本表 `<模块>.<模块>_alembic`，建在本模块 schema 里；自动生成只比对本模块 schema。
- 表结构的正本是模块 `store/models.py` 的 `metadata`（约定变量名），迁移从它生成，不手写第二份。
- 迁移用 owner 账号（`TITANLOOM_DB_OWNER_URL`）；只前滚（先扩展、再迁移校验、再收缩），不写 downgrade。
- 新模块的 schema 由迁移自动建出来时，同时给运行账号 USAGE 与默认读写权限（`ensure_schema`），
  不再靠 `ops/db/create.ps1` 事先为“当时已有表的模块”授权；运行账号不存在则报错，让人先跑 create.ps1。
"""

from __future__ import annotations

import os
from importlib import import_module
from pathlib import Path

from alembic import command, context
from alembic.config import Config
from sqlalchemy import Connection, MetaData, engine_from_config, pool, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import make_url

from titanloom.kernel import db as kdb

_PKG = Path(__file__).resolve().parents[1]
_ENV_DIR = Path(__file__).resolve().parent / "alembic_env"
DEFAULT_RUNTIME_ROLE = "titanloom_app"  # 与 ops/db/create.ps1 里的运行账号同名


class RuntimeRoleMissing(RuntimeError):
    """运行账号在库里不存在：建库脚本没跑过（或账号名对不上），先重跑 ops/db/create.ps1。"""


def runtime_role() -> str:
    """运行账号名：取 `TITANLOOM_DB_URL` 里的用户名，没设就用默认的 titanloom_app。"""
    url = os.environ.get(kdb.ENV_URL)
    return (make_url(url).username if url else None) or DEFAULT_RUNTIME_ROLE


def migrations_dir(module: str) -> Path:
    return _PKG / module / "migrations"


def version_table(module: str) -> str:
    return f"{module}_alembic"


def module_metadata(module: str) -> MetaData:
    models = import_module(f"titanloom.{module}.store.models")
    md = getattr(models, "metadata", None)
    if not isinstance(md, MetaData):
        raise RuntimeError(f"{module}.store.models 里没有名为 metadata 的 MetaData")
    return md


def config_for(module: str, url: str | None = None) -> Config:
    versions = migrations_dir(module) / "versions"
    versions.mkdir(parents=True, exist_ok=True)
    cfg = Config()
    cfg.set_main_option("script_location", str(_ENV_DIR))
    cfg.set_main_option("version_locations", str(versions))
    cfg.set_main_option("path_separator", "os")
    cfg.set_main_option("sqlalchemy.url", (url or kdb.database_url(owner=True)).replace("%", "%%"))
    cfg.attributes["module"] = module
    return cfg


def upgrade(module: str, revision: str = "head", url: str | None = None) -> None:
    command.upgrade(config_for(module, url), revision)


def new_revision(module: str, message: str, url: str | None = None) -> None:
    """从 store/models.py 与当前数据库的差别生成一份迁移脚本；生成后要人看一遍再提交。"""
    command.revision(config_for(module, url), message=message, autogenerate=True)


def ensure_schema(conn: Connection, schema: str, role: str) -> None:
    """建模块 schema（已有则跳过），并让运行账号能用：USAGE、现有表的读写、以及之后新建表 / 序列的默认权限。

    每次迁移都执行（授权可重复）。运行账号只读写、不能建表，建表权限仍只在 owner 手里。
    """
    if conn.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": role}).scalar() is None:
        raise RuntimeRoleMissing(f"运行账号 {role!r} 不存在：先重跑 ops/db/create.ps1，再迁移")
    q = postgresql.dialect().identifier_preparer.quote_identifier
    s, r = q(schema), q(role)
    for sql in (
        f"CREATE SCHEMA IF NOT EXISTS {s}",
        f"GRANT USAGE ON SCHEMA {s} TO {r}",
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {s} TO {r}",
        f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA {s} TO {r}",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA {s} GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {r}",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA {s} GRANT USAGE, SELECT ON SEQUENCES TO {r}",
    ):
        conn.execute(text(sql))


def run_env(cfg: Config | None = None) -> None:
    """env.py 调用：在线执行迁移。"""
    cfg = cfg or context.config
    module: str = cfg.attributes["module"]
    metadata = module_metadata(module)
    section = cfg.get_section(cfg.config_ini_section, {})
    engine = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)

    def only_mine(obj: object, name: str | None, type_: str, reflected: bool, compare_to: object) -> bool:
        if type_ == "table":
            return getattr(obj, "schema", None) == module
        return True

    with engine.connect() as conn:
        ensure_schema(conn, module, runtime_role())
        conn.commit()
        context.configure(
            connection=conn,
            target_metadata=metadata,
            include_schemas=True,
            include_object=only_mine,
            version_table=version_table(module),
            version_table_schema=module,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
