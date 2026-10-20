"""attendance.store：本模块的表与读写方法；只读写本模块 schema `attendance`。

阶段 1 先提供配置表结构与“发布时同范围同优先级有效期重叠拒绝”的纯校验；
不依赖底座 M1 的会话/连接，纯函数可在内存测试，真正的读写走 app 层后再接 DB。
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

metadata = MetaData(schema="attendance")

_CONFIG_KINDS = ("type", "shift", "rule_set", "plan", "checkin_policy")
_VERSION_STATUS_CHECK = "status IN ('draft','published','archived')"

# scope_kind = 'org' 时 scope_ref 必须为 NULL；dept / person 时 scope_ref 必须非空。
_SCOPE_KIND_REF_CHECK = (
    "(scope_kind = 'org' AND scope_ref IS NULL) OR (scope_kind IN ('dept','person') AND scope_ref IS NOT NULL)"
)


def _definition_table(kind: str) -> Table:
    return Table(
        kind,
        metadata,
        Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
        Column("key", String(100), nullable=False, unique=True),
        Column("name", String(200), nullable=False),
        Column("description", String(1000)),
        Column("scope_kind", String(10), nullable=False, server_default=text("'org'")),
        Column("scope_ref", String(64)),
        Column("priority", Integer, nullable=False, server_default=text("0")),
        Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
        CheckConstraint(_SCOPE_KIND_REF_CHECK, name=f"ck_{kind}_scope_kind_ref"),
        comment=f"考勤配置定义：{kind}",
    )


def _version_table(kind: str) -> Table:
    return Table(
        f"{kind}_version",
        metadata,
        Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
        Column(
            "definition_id",
            UUID(as_uuid=True),
            ForeignKey(f"{kind}.id", ondelete="CASCADE"),
            nullable=False,
        ),
        Column("version_no", Integer, nullable=False),
        Column("effective_from", Date),  # None = 从一开始（业务日，半开区间）
        Column("effective_to", Date),  # None = 永久有效（业务日，半开区间）
        Column("status", String(20), nullable=False, server_default=text("'draft'")),
        Column("content", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
        Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
        UniqueConstraint("definition_id", "version_no", name=f"ux_{kind}_version_definition_version"),
        CheckConstraint(_VERSION_STATUS_CHECK, name=f"ck_{kind}_version_status"),
        comment=f"考勤配置版本：{kind}，发布后不可改，按业务日启用",
    )


# 各配置类的定义表与版本表（子方案 5：每类“定义”+“版本”两张表；版本化发布）
type = _definition_table("type")
type_version = _version_table("type")

shift = _definition_table("shift")
shift_version = _version_table("shift")

rule_set = _definition_table("rule_set")
rule_set_version = _version_table("rule_set")

plan = _definition_table("plan")
plan_version = _version_table("plan")

checkin_policy = _definition_table("checkin_policy")
checkin_policy_version = _version_table("checkin_policy")

__all__ = [
    "checkin_policy",
    "checkin_policy_version",
    "metadata",
    "plan",
    "plan_version",
    "rule_set",
    "rule_set_version",
    "shift",
    "shift_version",
    "type",
    "type_version",
]
