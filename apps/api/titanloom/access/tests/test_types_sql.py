from __future__ import annotations

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, insert, select

from titanloom.access.api import AccessFilter, Predicate
from titanloom.access.api.sql import FilterFieldNotMapped, to_sqlalchemy
from titanloom.access.api.types import Decision

meta = MetaData()
rec = Table("rec", meta, Column("id", Integer, primary_key=True), Column("owner", String), Column("dept", String))
COLS = {"ownerId": rec.c.owner, "deptId": rec.c.dept}
ROWS = [
    {"id": 1, "owner": "A", "dept": "asm1"},
    {"id": 2, "owner": "B", "dept": "asm1"},
    {"id": 3, "owner": "A", "dept": "qa"},
    {"id": 4, "owner": "C", "dept": "wh"},
]


def ids(flt: AccessFilter) -> set[int]:
    engine = create_engine("sqlite://")
    meta.create_all(engine)
    with engine.begin() as c:
        c.execute(insert(rec), ROWS)
        got = {r.id for r in c.execute(select(rec.c.id).where(to_sqlalchemy(flt, COLS)))}
    expected = {int(r["id"]) for r in ROWS if flt.matches({"ownerId": r["owner"], "deptId": r["dept"]})}
    assert got == expected  # 翻译结果必须和纯函数 matches 一致
    return got


def test_all_none() -> None:
    assert ids(AccessFilter(1, all=True)) == {1, 2, 3, 4}
    assert ids(AccessFilter(1, none=True)) == set()


def test_union_minus_deny() -> None:
    flt = AccessFilter(
        1,
        any=(Predicate("ownerId", "eq", ("A",)), Predicate("deptId", "in", ("wh", "asm1"))),
        not_=(Predicate("deptId", "eq", ("qa",)), Predicate("ownerId", "eq", ("C",))),
    )
    assert ids(flt) == {1, 2}


def test_secondary_dept_expanded_values() -> None:
    assert ids(AccessFilter(1, any=(Predicate("deptId", "in", ("qa", "wh")),))) == {3, 4}


def test_mask_columns_carried() -> None:
    flt = AccessFilter(1, any=(Predicate("deptId", "eq", ("qa",)),), mask_columns=("idNumber",))
    assert flt.to_contract()["maskColumns"] == ["idNumber"]


def test_unmapped_field_raises_not_open_door() -> None:
    with pytest.raises(FilterFieldNotMapped):
        to_sqlalchemy(AccessFilter(1, any=(Predicate("projectId", "eq", ("p",)),)), COLS)
    with pytest.raises(FilterFieldNotMapped):
        to_sqlalchemy(
            AccessFilter(1, any=(Predicate("deptId", "eq", ("qa",)),), not_=(Predicate("typo", "eq", ("x",)),)), COLS
        )


def test_filter_shape_rules() -> None:
    with pytest.raises(ValueError):
        AccessFilter(1)
    with pytest.raises(ValueError):
        AccessFilter(1, all=True, none=True)
    with pytest.raises(ValueError):
        AccessFilter(1, none=True, mask_columns=("x",))
    with pytest.raises(ValueError):
        Predicate("a", "eq", ())
    with pytest.raises(ValueError):
        Predicate("a", "eq", (1, 2))


def test_decision_shape_rules() -> None:
    from datetime import UTC, datetime

    now = datetime(2026, 10, 20, tzinfo=UTC)
    with pytest.raises(ValueError):
        Decision(False, 1, now)
    with pytest.raises(ValueError):
        Decision(True, 1, now, can_request=True)
