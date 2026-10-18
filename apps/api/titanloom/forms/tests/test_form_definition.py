"""阶段 1 验收：字段与表单定义、草稿 / 发布 / 版本（FW06、FW18）。

示例与测试里的人名只用合成数据人设表（ops/synthetic-data/personas.json）。
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from titanloom.forms.domain.field import FieldDefinition, FieldKind
from titanloom.forms.domain.form import FormDefinition, publish
from titanloom.forms.domain.publish_check import PublishCheckFailed, publish_check


def _field(code: str, label: str, kind: str = FieldKind.TEXT) -> FieldDefinition:
    return FieldDefinition(code=code, label_zh=label, label_en=label, kind=kind)


def test_field_rename_keeps_formula_and_condition_references() -> None:
    """FW18：字段改名只改显示名，公式/显示条件按稳定 code 引用，仍有效。"""
    form = FormDefinition(owner="刘畅")
    form.add_field(_field("start_date", "开始日期", FieldKind.DATE))
    form.add_field(_field("end_date", "结束日期", FieldKind.DATE))
    form.sections[0].formula = "daysBetween($end_date, $start_date) + 1"
    form.sections[0].show_condition = "$end_date > $start_date"

    form.rename_field("end_date", "完成日期")

    assert form.field("end_date").label_zh == "完成日期"
    assert form.sections[0].formula == "daysBetween($end_date, $start_date) + 1"
    assert form.sections[0].show_condition == "$end_date > $start_date"


def test_publish_creates_immutable_release() -> None:
    """FW06：发布形成不可变版本；草稿后续改动不改已发布的版本。"""
    form = FormDefinition(owner="刘畅")
    form.add_field(_field("a", "字段A"))
    form.sections[0].formula = "$a"

    released = publish(form, datetime(2026, 10, 18, 9, 0, tzinfo=UTC))

    assert released.version == 1
    assert released.sections[0].formula == "$a"
    assert released.fields["a"].label_zh == "字段A"

    # 草稿继续改：新增字段、改公式
    form.add_field(_field("b", "字段B", FieldKind.NUMBER))
    form.sections[0].formula = "$a + $b"
    released2 = publish(form, datetime(2026, 10, 18, 10, 0, tzinfo=UTC))

    assert released2.version == 2
    assert released2.sections[0].formula == "$a + $b"
    assert len(form.releases) == 2

    # 旧版本快照不变：运行中的记录继续按原版本走
    assert released.version == 1
    assert released.sections[0].formula == "$a"
    assert set(released.fields) == {"a"}


def test_publish_check_rejects_undefined_field_reference() -> None:
    """公式/显示条件引用未定义字段，发布前检查必须拒绝（子方案 26.3.4）。"""
    form = FormDefinition(owner="刘畅")
    form.add_field(_field("a", "字段A"))
    form.sections[0].formula = "$a + $nope"

    def _exprs(form: FormDefinition) -> list[str | None]:
        return [expr for section in form.sections for expr in (section.formula, section.show_condition)]

    with pytest.raises(PublishCheckFailed, match="nope"):
        publish_check(set(form.fields), _exprs(form))

    form.sections[0].show_condition = "$missing > 0"
    with pytest.raises(PublishCheckFailed, match="missing"):
        publish_check(set(form.fields), _exprs(form))


def test_publish_check_accepts_defined_fields() -> None:
    """引用均已定义的字段，发布前检查通过。"""
    form = FormDefinition(owner="刘畅")
    form.add_field(_field("a", "字段A", FieldKind.NUMBER))
    form.add_field(_field("b", "字段B", FieldKind.NUMBER))
    form.sections[0].formula = "$a + $b"
    form.sections[0].show_condition = "$b > 0"

    def _exprs(f: FormDefinition) -> list[str | None]:
        return [expr for section in f.sections for expr in (section.formula, section.show_condition)]

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
