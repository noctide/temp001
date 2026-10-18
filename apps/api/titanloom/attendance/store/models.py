"""attendance.store：本模块的表与读写方法；只读写本模块 schema `attendance`。

阶段 1 先提供配置表结构与“发布时同范围同优先级有效期重叠拒绝”的纯校验；
不依赖底座 M1 的会话/连接，纯函数可在内存测试，真正的读写走 app 层后再接 DB。
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    Column,
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


def _definition_table(kind: str) -> Table:
    return Table(
        f"attendance_{kind}",
        metadata,
        Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
        Column("key", String(100), nullable=False, unique=True),
        Column("name", String(200), nullable=False),
        Column("description", String(1000)),
        Column("scope", String(40), nullable=False),  # org / dept / person / employment
        Column("priority", Integer, nullable=False, server_default=text("0")),
        Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
        comment=f"考勤配置定义：{kind}",
    )


def _version_table(kind: str) -> Table:
    return Table(
        f"attendance_{kind}_version",
        metadata,
        Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
        Column(
            "definition_id",
            UUID(as_uuid=True),
            ForeignKey(f"attendance_{kind}.id", ondelete="CASCADE"),
            nullable=False,
        ),
        Column("version_no", Integer, nullable=False),
        Column("effective_from", DateTime(timezone=True)),  # None = 从一开始
        Column("effective_to", DateTime(timezone=True)),  # None = 永久有效
        Column("status", String(20), nullable=False, server_default=text("'draft'")),
        Column("content", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
        Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
        UniqueConstraint("definition_id", "version_no", name=f"ux_{kind}_version_definition_version"),
        CheckConstraint(_VERSION_STATUS_CHECK, name=f"ck_{kind}_version_status"),
        comment=f"考勤配置版本：{kind}，发布后不可改，按有效期启用",
    )


# 各配置类的定义表与版本表（子方案 5：每类“定义”+“版本”两张表；版本化发布）
attendance_type = _definition_table("type")
attendance_type_version = _version_table("type")

attendance_shift = _definition_table("shift")
attendance_shift_version = _version_table("shift")

attendance_rule_set = _definition_table("rule_set")
attendance_rule_set_version = _version_table("rule_set")

attendance_plan = _definition_table("plan")
attendance_plan_version = _version_table("plan")

attendance_checkin_policy = _definition_table("checkin_policy")
attendance_checkin_policy_version = _version_table("checkin_policy")

__all__ = [
    "attendance_checkin_policy",
    "attendance_checkin_policy_version",
    "attendance_plan",
    "attendance_plan_version",
    "attendance_rule_set",
    "attendance_rule_set_version",
    "attendance_shift",
    "attendance_shift_version",
    "attendance_type",
    "attendance_type_version",
    "metadata",
]
