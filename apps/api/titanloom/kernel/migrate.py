"""每个模块各自一套迁移（总图 6、12；工程规范 4.3）。

- 迁移脚本放各模块 `migrations/versions/`；公共的 env.py 与模板在 `kernel/alembic_env/`，模块里不再各写一份。
- 每个模块独立的版本表 `<模块>.<模块>_alembic`，建在本模块 schema 里；自动生成只比对本模块 schema。
- 表结构的正本是模块 `store/models.py` 的 `metadata`（约定变量名），迁移从它生成，不手写第二份。
- 迁移用 owner 账号（`TITANLOOM_DB_OWNER_URL`）；只前滚（先扩展、再迁移校验、再收缩），不写 downgrade。
"""

from __future__ import annotations

from importlib import import_module
from pathlib import Path

from alembic import command, context
from alembic.config import Config
from sqlalchemy import MetaData, engine_from_config, pool, text

from titanloom.kernel import db as kdb

_PKG = Path(__file__).resolve().parents[1]
_ENV_DIR = Path(__file__).resolve().parent / "alembic_env"


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
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{module}"'))
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
