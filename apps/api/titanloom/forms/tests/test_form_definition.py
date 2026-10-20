"""阶段 1 验收：字段与表单定义、草稿 / 发布 / 版本（FW06、FW18）。

示例与测试里的人名只用合成数据人设表（ops/synthetic-data/personas.json）。
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from types import MappingProxyType

import pytest

from titanloom.forms.domain.field import FieldDefinition, FieldKind
from titanloom.forms.domain.form import FormDefinition, publish
from titanloom.forms.domain.publish_check import (
    CheckKind,
    CheckProblem,
    PublishCheckFailed,
    publish_check,
)
from titanloom.forms.tests.helpers import cyclic_form


def _field(code: str, label: str, kind: FieldKind = FieldKind.TEXT) -> FieldDefinition:
    return FieldDefinition(code=code, label_zh=label, label_en=label, kind=kind)


def _set_show_condition(form: FormDefinition, section_index: int, cond: str | None) -> None:
    form.sections[section_index] = replace(form.sections[section_index], show_condition=cond)


def test_field_rename_keeps_code_and_references() -> None:
    """FW18：字段改名只改显示名，code 不变；公式/显示条件按 code 引用，仍有效。"""
    form = FormDefinition(owner="刘畅")
    form.add_field(_field("start_date", "开始日期", FieldKind.DATE))
    form.add_field(
        FieldDefinition(
            code="end_date",
            label_zh="结束日期",
            label_en="End Date",
            kind=FieldKind.DATE,
            settings={"formula": "daysBetween($end_date, $start_date) + 1"},
        )
    )
    _set_show_condition(form, 0, "$end_date > $start_date")

    form.rename_field("end_date", "完成日期")

    assert form.field("end_date").label_zh == "完成日期"
    assert form.field("end_date").code == "end_date"
    mapping = form.field("end_date").settings or {}
    assert mapping.get("formula") == "daysBetween($end_date, $start_date) + 1"
    assert form.sections[0].show_condition == "$end_date > $start_date"


def test_field_settings_are_immutable_mapping() -> None:
    """字段 settings 是不可变映射，原对象不受改动影响。"""
    f = _field("a", "字段A", FieldKind.NUMBER)
    assert isinstance(f.settings, MappingProxyType)
    assert f.settings == {}
    f2 = f.with_settings({"formula": "$a * 2"})
    assert f.settings == {}
    mapping = f2.settings or {}
    assert mapping.get("formula") == "$a * 2"


def test_publish_creates_immutable_release() -> None:
    """FW06：发布形成不可变版本；草稿后续改名/改设置/删字段，旧版本都不变。"""
    form = FormDefinition(owner="刘畅")
    form.add_field(_field("a", "字段A", FieldKind.NUMBER))
    form.add_field(
        FieldDefinition(
            code="b",
            label_zh="字段B",
            label_en="Field B",
            kind=FieldKind.NUMBER,
            settings={"formula": "$a * 2"},
        )
    )
    _set_show_condition(form, 0, "$b > 0")

    released = publish(form, datetime(2026, 10, 18, 9, 0, tzinfo=UTC))

    assert released.version == 1
    assert released.fields["a"].label_zh == "字段A"
    assert released.sections[0].show_condition == "$b > 0"
    mapping = released.fields["b"].settings or {}
    assert mapping.get("formula") == "$a * 2"

    # 草稿继续改：改名、改设置、新增字段、删字段（删的字段不再被任何公式引用）
    form.rename_field("a", "字段甲")
    form.add_field(
        FieldDefinition(
            code="b",
            label_zh="字段B",
            label_en="Field B",
            kind=FieldKind.NUMBER,
            settings={"formula": "$c * 2"},
        )
    )
    form.add_field(_field("c", "字段C", FieldKind.NUMBER))
    form.remove_field("a")

    released2 = publish(form, datetime(2026, 10, 18, 10, 0, tzinfo=UTC))
    assert released2.version == 2
    assert released2.fields["b"].label_zh == "字段B"
    mapping = released2.fields["b"].settings or {}
    assert mapping.get("formula") == "$c * 2"
    assert set(released2.fields) == {"b", "c"}

    # 旧版本快照完全不变：运行中的记录继续按原版本走
    assert released.version == 1
    assert released.fields["a"].label_zh == "字段A"
    mapping = released.fields["b"].settings or {}
    assert mapping.get("formula") == "$a * 2"
    assert released.sections[0].show_condition == "$b > 0"
    assert "c" not in released.fields


def test_publish_check_rejects_undefined_field_reference() -> None:
    """分区显示条件 / 字段公式 引用未定义字段，发布前检查必须拒绝（子方案 26.3.4）。"""
    form = FormDefinition(owner="刘畅")
    form.add_field(_field("a", "字段A", FieldKind.NUMBER))
    _set_show_condition(form, 0, "$nope > 0")

    problems = _capture_publish_check_failure(form)
    assert any(p.section_index == 0 and p.field_code is None and p.ref == "nope" for p in problems)

    _set_show_condition(form, 0, None)
    form.add_field(
        FieldDefinition(
            code="b",
            label_zh="字段B",
            label_en="Field B",
            kind=FieldKind.NUMBER,
            settings={"formula": "$a + $missing"},
        )
    )
    problems = _capture_publish_check_failure(form)
    assert any(p.section_index is None and p.field_code == "b" and p.ref == "missing" for p in problems)


def test_publish_check_rejects_cycle() -> None:
    """FW11：字段公式间循环依赖，发布前检查必须拒绝。"""
    form = cyclic_form()
    problems = _capture_publish_check_failure(form)
    assert any(p.kind == CheckKind.CYCLE for p in problems)


def test_publish_check_accepts_defined_fields() -> None:
    """引用均已定义的字段，发布前检查通过。"""
    form = FormDefinition(owner="刘畅")
    form.add_field(_field("a", "字段A", FieldKind.NUMBER))
    form.add_field(_field("b", "字段B", FieldKind.NUMBER))
    _set_show_condition(form, 0, "$b > 0")
    form.add_field(
        FieldDefinition(
            code="c",
            label_zh="字段C",
            label_en="Field C",
            kind=FieldKind.NUMBER,
            settings={"formula": "$a + $b"},
        )
    )

    assert publish_check(set(form.fields), _exprs(form)) is True


def test_draft_can_add_remove_fields_before_publish() -> None:
    """草稿可持续编辑，发布前不形成不可变版本。"""
    form = FormDefinition(owner="刘畅")
    form.add_field(_field("a", "字段A"))
    assert len(form.fields) == 1

    form.remove_field("a")
    assert len(form.fields) == 0

    form.add_field(_field("c", "字段C", FieldKind.DATE))
    assert form.field("c").kind == FieldKind.DATE


def test_field_missing_raises_key_error_with_code() -> None:
    """field() / remove_field() 的 KeyError 只带字段编号，不拼中文句子。"""
    form = FormDefinition(owner="刘畅")
    with pytest.raises(KeyError, match="nope"):
        form.field("nope")
    with pytest.raises(KeyError, match="nope"):
        form.remove_field("nope")


# ---------------------------------------------------------------- helpers


def _exprs(
    form: FormDefinition,
) -> list[tuple[int | None, str | None, str | None]]:
    expressions: list[tuple[int | None, str | None, str | None]] = []
    for index, section in enumerate(form.sections):
        if section.show_condition:
            expressions.append((index, None, section.show_condition))
    for code, definition in form.fields.items():
        mapping = definition.settings or {}
        expr = mapping.get("formula")
        if isinstance(expr, str):
            expressions.append((None, code, expr))
    return expressions


def _capture_publish_check_failure(
    form: FormDefinition,
) -> list[CheckProblem]:
    try:
        publish_check(set(form.fields), _exprs(form))
    except PublishCheckFailed as exc:
        return exc.problems
    raise AssertionError("应当抛出 PublishCheckFailed")
