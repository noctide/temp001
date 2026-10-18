"""阶段 2 验收：显示条件求值（结果必须为 bool，FW14 服务端独立评估）。"""

from __future__ import annotations

import pytest

from titanloom.forms.domain.conditions import evaluate_condition
from titanloom.forms.domain.expr import ExprError, parse_field_value
from titanloom.forms.domain.expr.types import Value


def test_condition_true() -> None:
    fields: dict[str, Value] = {"age": parse_field_value("number", "10")}
    assert evaluate_condition("$age > 8", fields) is True


def test_condition_false() -> None:
    fields: dict[str, Value] = {"age": parse_field_value("number", "5")}
    assert evaluate_condition("$age > 8", fields) is False


def test_condition_and_or() -> None:
    fields: dict[str, Value] = {
        "a": parse_field_value("number", "5"),
        "b": parse_field_value("number", "12"),
    }
    assert evaluate_condition("$a > 8 and $b > 8", fields) is False
    assert evaluate_condition("$a > 8 or $b > 8", fields) is True


def test_condition_must_be_bool() -> None:
    """FW14：显示条件求值结果必须为 bool，非 bool 拒绝。"""
    fields: dict[str, Value] = {"name": parse_field_value("text", "abc")}
    with pytest.raises(ExprError):
        evaluate_condition("$name", fields)


def test_condition_undefined_field() -> None:
    fields: dict[str, Value] = {}
    with pytest.raises(ExprError):
        evaluate_condition("$nope > 0", fields)
