"""阶段 2 验收：引用提取、依赖环、预算与发布前静态检查（FW11）。

预算值为业务参数（forms.expr.depthLimit / forms.expr.computeMs），字段引用数不设上限
——设计里的"20 次"是引用基表的次数，阶段一没有基表查找函数。
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from titanloom.forms.domain.expr import (
    COMPUTE_BUDGET_MS,
    DEFAULT_DEPTH_LIMIT,
    ExprError,
    evaluate,
    expression_depth,
    parse,
    parse_field_value,
    referenced_fields,
)
from titanloom.forms.domain.expr.dependency import has_cycle
from titanloom.forms.domain.expr.types import Value
from titanloom.forms.domain.field import FieldDefinition, FieldKind
from titanloom.forms.domain.form import FormDefinition, publish
from titanloom.forms.domain.publish_check import CheckKind, PublishCheckFailed
from titanloom.forms.tests.helpers import cyclic_form
from titanloom.kernel.params import ParamStore
from titanloom.kernel.reg.manifest import P


def _num(value: str) -> Value:
    return parse_field_value("number", value)


def _field(code: str, kind: FieldKind = FieldKind.NUMBER) -> FieldDefinition:
    return FieldDefinition(code=code, label_zh=code, label_en=code, kind=kind)


def _problems_of(form: FormDefinition) -> list[str]:
    with pytest.raises(PublishCheckFailed) as exc_info:
        publish(form, datetime(2026, 10, 20, 9, 0, tzinfo=UTC))
    return [p.kind for p in exc_info.value.problems]


def test_referenced_fields() -> None:
    assert referenced_fields("$a + $b * 2") == ["a", "b"]
    assert referenced_fields("daysBetween($end, $start) + 1") == ["end", "start"]
    assert referenced_fields("if($h > 8, $h - 8, 0)") == ["h"]
    assert referenced_fields("42") == []


def test_referenced_fields_deduped_and_ordered() -> None:
    assert referenced_fields("$a + $a + $b") == ["a", "b"]


def test_referenced_fields_does_not_swallow_syntax_error() -> None:
    with pytest.raises(ExprError, match="SYNTAX"):
        referenced_fields("sum($a, ")


def test_unknown_function_raises() -> None:
    with pytest.raises(ExprError, match="UNKNOWN_FUNCTION"):
        evaluate("eval($a)", {"a": _num("1")})


def test_has_cycle_detects_direct_and_indirect_cycle() -> None:
    assert has_cycle({"a": {"b"}, "b": {"c"}, "c": {"a"}}) is True
    assert has_cycle({"a": {"b"}, "b": {"c"}, "c": set()}) is False
    assert has_cycle({"a": {"a"}}) is True


def test_expression_depth() -> None:
    assert expression_depth(parse("$a + $b")) == 2
    assert expression_depth(parse("daysBetween($end, $start) + 1")) == 3


def test_budget_defaults_come_from_registered_params() -> None:
    params = ParamStore()
    assert DEFAULT_DEPTH_LIMIT == params.get(P.forms.expr.depthLimit) == 32
    assert COMPUTE_BUDGET_MS == params.get(P.forms.expr.computeMs) == 10


def test_no_field_reference_limit() -> None:
    """引用字段多不是问题：一张表单 25+ 个字段正常（设计里的上限是引用基表次数）。"""
    fields = {f"f{i}": _num("1") for i in range(30)}
    expr = "sum(" + ", ".join(f"${name}" for name in fields) + ")"
    assert evaluate(expr, fields) == _num("30")
    assert len(referenced_fields(expr)) == 30


def test_cycle_rejected_at_publish() -> None:
    """FW11：字段公式间循环依赖，发布前检查必须拒绝。"""
    with pytest.raises(PublishCheckFailed) as exc_info:
        publish(cyclic_form(), datetime(2026, 10, 20, 9, 0, tzinfo=UTC))
    assert any(p.kind == CheckKind.CYCLE for p in exc_info.value.problems)


def test_depth_exceeded_at_publish() -> None:
    """嵌套深度超 32 的公式，发布前检查拒绝。"""
    form = FormDefinition(owner="刘畅")
    form.add_field(_field("a"))
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
        publish(form, datetime(2026, 10, 20, 9, 0, tzinfo=UTC))
    assert any(p.kind == CheckKind.BUDGET_DEPTH for p in exc_info.value.problems)


def test_syntax_error_rejected_at_publish() -> None:
    form = FormDefinition(owner="刘畅")
    form.add_field(_field("a"))
    form.add_field(
        FieldDefinition(
            code="b",
            label_zh="B",
            label_en="B",
            kind=FieldKind.NUMBER,
            settings={"formula": "sum($a, "},
        )
    )
    assert CheckKind.SYNTAX in _problems_of(form)


def test_unknown_function_rejected_at_publish() -> None:
    form = FormDefinition(owner="刘畅")
    form.add_field(_field("a"))
    form.add_field(
        FieldDefinition(
            code="b",
            label_zh="B",
            label_en="B",
            kind=FieldKind.NUMBER,
            settings={"formula": "eval($a)"},
        )
    )
    assert CheckKind.UNKNOWN_FUNCTION in _problems_of(form)


def test_type_mismatch_rejected_at_publish() -> None:
    """能静态判断的类型不符：文本字段参与加法、条件结果不是 bool。"""
    form = FormDefinition(owner="刘畅")
    form.add_field(_field("name", FieldKind.TEXT))
    form.add_field(_field("n"))
    form.add_field(
        FieldDefinition(
            code="bad_formula",
            label_zh="Bad",
            label_en="Bad",
            kind=FieldKind.NUMBER,
            settings={"formula": "$name + 1"},
        )
    )
    assert CheckKind.TYPE_MISMATCH in _problems_of(form)

    form = FormDefinition(owner="刘畅")
    form.add_field(_field("n"))
    form.sections[0] = replace(form.sections[0], show_condition="$n + 1")
    assert CheckKind.TYPE_MISMATCH in _problems_of(form)


def test_type_mismatch_in_function_args_rejected_at_publish() -> None:
    form = FormDefinition(owner="刘畅")
    form.add_field(_field("n"))
    form.add_field(
        FieldDefinition(
            code="days",
            label_zh="Days",
            label_en="Days",
            kind=FieldKind.NUMBER,
            settings={"formula": "daysBetween($n, $n)"},
        )
    )
    assert CheckKind.TYPE_MISMATCH in _problems_of(form)
