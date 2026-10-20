"""把 AccessFilter 翻成 SQLAlchemy 表达式（身份与权限 6；在调用模块自己的 store 层执行）。

只做 IN / 等于 / 并 / 差，只生成表达式，不拼 SQL 字符串，也不去查组织树（部门范围在 filter 时已展开成编号）。
"""

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import ColumnElement, and_, false, not_, or_, true

from titanloom.access.api.types import AccessFilter, Predicate


class FilterFieldNotMapped(ValueError):
    """筛选条件用到的权限字段，调用方没有给出对应的列。程序错误，不能当作“不限”放行。"""


def _one(p: Predicate, columns: Mapping[str, ColumnElement[object]]) -> ColumnElement[bool]:
    col = columns.get(p.field)
    if col is None:
        raise FilterFieldNotMapped(f"权限字段 {p.field!r} 没有对应的列")
    return col == p.values[0] if p.op == "eq" else col.in_(p.values)


def to_sqlalchemy(flt: AccessFilter, columns: Mapping[str, ColumnElement[object]]) -> ColumnElement[bool]:
    """返回可直接 `.where(...)` 的条件。columns：权限字段名 → 列。"""
    if flt.none:
        return false()
    if flt.all:
        return true()
    allow = or_(*[_one(p, columns) for p in flt.any])
    if not flt.not_:
        return allow
    return and_(allow, *[not_(_one(p, columns)) for p in flt.not_])
