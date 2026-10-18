"""阶段 2 验收：后端表达式求值器跑 `packages/contracts/expressions/cases.json` 的全部用例。

Python 与前端都只实现 functions.json 的函数，并都跑同一批 cases.json（规范 5.5）。
"""

from __future__ import annotations

import json
from datetime import date, time
from pathlib import Path
from typing import TypedDict

import pytest

from titanloom.forms.domain.expr import ExprError, Value, ValueKind, evaluate, parse_field_value
from titanloom.kernel.exact import dec

CASES_PATH = Path(__file__).resolve().parents[5] / "packages" / "contracts" / "expressions" / "cases.json"


class _FieldCase(TypedDict):
    type: str
    value: str


class _Case(TypedDict, total=False):
    id: str
    expr: str
    fields: dict[str, _FieldCase]
    expect: dict[str, str]
    expectError: str


_RAW_CASES = json.loads(CASES_PATH.read_text(encoding="utf-8"))
CASES: list[_Case] = _RAW_CASES["cases"]


def _fields_of(case: _Case) -> dict[str, Value]:
    fields: dict[str, Value] = {}
    for code, info in (case.get("fields") or {}).items():
        fields[code] = parse_field_value(info["type"], info["value"])
    return fields


def _expect_value(result: Value, expect: dict[str, str]) -> None:
    assert result.kind == ValueKind(expect["type"])
    typ = expect["type"]
    val = expect["value"]
    if typ == "number":
        assert result.value == dec(val)
    elif typ == "date":
        assert result.value == date.fromisoformat(val)
    elif typ == "time":
        assert result.value == time.fromisoformat(val)
    elif typ == "text":
        assert result.value == val
    else:  # bool
        assert result.value is (val == "true")


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_expression_case(case: _Case) -> None:
    fields = _fields_of(case)
    expr = case.get("expr")
    assert expr is not None
    if "expectError" in case:
        with pytest.raises(ExprError, match=case.get("expectError")):
            evaluate(expr, fields)
    else:
        result = evaluate(expr, fields)
        expect = case.get("expect")
        assert expect is not None
        _expect_value(result, expect)
