"""测试共享构造器，避免多个测试文件里重复造表单。"""

from __future__ import annotations

from titanloom.forms.domain.field import FieldDefinition, FieldKind
from titanloom.forms.domain.form import FormDefinition


def cyclic_form(owner: str = "刘畅") -> FormDefinition:
    """a 的公式引用 b，b 的公式引用 a：循环依赖（FW11）。"""
    form = FormDefinition(owner=owner)
    form.add_field(
        FieldDefinition(
            code="a",
            label_zh="A",
            label_en="A",
            kind=FieldKind.NUMBER,
            settings={"formula": "$b + 1"},
        )
    )
    form.add_field(
        FieldDefinition(
            code="b",
            label_zh="B",
            label_en="B",
            kind=FieldKind.NUMBER,
            settings={"formula": "$a + 1"},
        )
    )
    return form
