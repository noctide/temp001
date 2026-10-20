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
