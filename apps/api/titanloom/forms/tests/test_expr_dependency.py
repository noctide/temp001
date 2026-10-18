"""阶段 2 验收：表达式字段引用提取、依赖图环检测与预算（FW11 循环依赖发布前拒绝）。"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from titanloom.forms.domain.expr import (
    DEFAULT_DEPTH_LIMIT,
    DEFAULT_REF_LIMIT,
    ExprError,
    count_refs,
    evaluate,
    expression_depth,
    extract_refs,
    parse,
    parse_field_value,
)
from titanloom.forms.domain.expr.dependency import has_cycle
from titanloom.forms.domain.expr.types import Value
from titanloom.forms.domain.field import FieldDefinition, FieldKind
from titanloom.forms.domain.form import FormDefinition, publish
from titanloom.forms.domain.publish_check import CheckKind, PublishCheckFailed
from titanloom.forms.tests.helpers import cyclic_form


def _num(value: str) -> Value:
    return parse_field_value("number", value)


def test_extract_refs() -> None:
    assert extract_refs("$a + $b * 2") == ["a", "b"]
    assert extract_refs("daysBetween($end, $start) + 1") == ["end", "start"]
    assert extract_refs("if($h > 8, $h - 8, 0)") == ["h"]
    assert extract_refs("42") == []
    assert extract_refs("") == []


def test_extract_refs_deduped_and_ordered() -> None:
    assert extract_refs("$a + $a + $b") == ["a", "b"]


def test_unknown_function_raises() -> None:
    with pytest.raises(ExprError, match="UNKNOWN_FUNCTION"):
        evaluate("eval($a)", {"a": _num("1")})


def test_has_cycle_detects_direct_and_indirect_cycle() -> None:
    assert has_cycle({"a": {"b"}, "b": {"c"}, "c": {"a"}}) is True
    assert has_cycle({"a": {"b"}, "b": {"c"}, "c": set()}) is False
    assert has_cycle({"a": {"a"}}) is True


def test_expression_depth_and_ref_count() -> None:
    assert expression_depth(parse("$a + $b")) == 2
    assert expression_depth(parse("daysBetween($end, $start) + 1")) == 3
    assert count_refs(parse("$a + $a + $b")) == 3  # 计重不去重
    assert count_refs(parse("42")) == 0


def test_budget_refs_exceeded() -> None:
    fields = {f"f{i}": _num("1") for i in range(DEFAULT_REF_LIMIT + 1)}
    expr = "+".join(f"${name}" for name in fields)
    with pytest.raises(ExprError, match="BUDGET_REFS"):
        evaluate(expr, fields, ref_limit=DEFAULT_REF_LIMIT)


def test_cycle_rejected_at_publish() -> None:
    """FW11：字段公式间循环依赖，发布前检查必须拒绝。"""
    form = cyclic_form()
    with pytest.raises(PublishCheckFailed) as exc_info:
        publish(form, datetime(2026, 10, 18, 9, 0, tzinfo=UTC))
    assert any(p.kind == CheckKind.CYCLE for p in exc_info.value.problems)


def test_depth_exceeded_at_publish() -> None:
    """嵌套深度超 32 的公式，发布前检查拒绝。"""
    form = FormDefinition(owner="刘畅")
    form.add_field(
        FieldDefinition(
            code="a",
            label_zh="A",
            label_en="A",
            kind=FieldKind.NUMBER,
            settings={"formula": "round($a, 0)"},
        )
    )
    inner = "$a"
    for _ in range(DEFAULT_DEPTH_LIMIT + 1):
        inner = f"round({inner}, 0)"
    form.add_field(
        FieldDefinition(
            code="deep",
            label_zh="Deep",
            label_en="Deep",
            kind=FieldKind.NUMBER,
            settings={"formula": inner},
        )
    )
    with pytest.raises(PublishCheckFailed) as exc_info:
        publish(form, datetime(2026, 10, 18, 9, 0, tzinfo=UTC))
    assert any(p.kind == CheckKind.BUDGET_DEPTH for p in exc_info.value.problems)
