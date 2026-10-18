"""表单草稿与发布版本（阶段 1）：草稿可编辑，发布形成不可变版本（FW06）。

Section 只留标题、字段列表、显示条件；计算字段的表达式放进该字段的
settings（公式不是分区属性）。
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as _field
from datetime import datetime
from types import MappingProxyType

from titanloom.forms.domain.field import FieldDefinition
from titanloom.forms.domain.publish_check import publish_check


@dataclass
class Section:
    """表单的分区：标题、字段列表、显示条件。"""

    title: str = ""
    show_condition: str | None = None

    def __post_init__(self) -> None:
        self.fields: list[str] = []


@dataclass(frozen=True)
class FormRelease:
    """发布后的不可改版本（快照）。运行中的记录绑定版本号（FW06）。"""

    form_id: str
    version: int
    published_at: datetime
    fields: dict[str, FieldDefinition]
    sections: list[Section]


@dataclass
class FormDefinition:
    """草稿，只有作者可见，可持续编辑（子方案 26.1）。"""

    owner: str
    form_id: str | None = None
    sections: list[Section] = _field(default_factory=lambda: [Section()])

    def __post_init__(self) -> None:
        self._fields: dict[str, FieldDefinition] = {}
        self.releases: list[FormRelease] = []

    @property
    def fields(self) -> dict[str, FieldDefinition]:
        result: dict[str, FieldDefinition] = {}
        result.update(self._fields)
        return result

    def field(self, code: str) -> FieldDefinition:
        if code not in self._fields:
            raise KeyError(code)
        return self._fields[code]

    def add_field(self, definition: FieldDefinition) -> None:
        self._fields[definition.code] = definition
        if definition.code not in self.sections[0].fields:
            self.sections[0].fields.append(definition.code)

    def remove_field(self, code: str) -> None:
        if code not in self._fields:
            raise KeyError(code)
        del self._fields[code]
        for section in self.sections:
            if code in section.fields:
                section.fields.remove(code)

    def rename_field(self, code: str, new_zh: str, new_en: str | None = None) -> None:
        """改名只改显示名，返回新 FieldDefinition，code 不变（FW18）。"""
        existing = self.field(code)  # KeyError(code) 若不存在
        self._fields[code] = existing.with_label(label_zh=new_zh, label_en=new_en)


def _collect_expressions(
    draft: FormDefinition,
) -> list[tuple[int | None, str | None, str | None]]:
    """收集需在发布前检查的表达式：分区显示条件、字段 settings 里的公式。"""
    expressions: list[tuple[int | None, str | None, str | None]] = []
    for index, section in enumerate(draft.sections):
        if section.show_condition:
            expressions.append((index, None, section.show_condition))
    for code, definition in draft.fields.items():
        mapping = definition.settings or MappingProxyType({})
        expr = mapping.get("formula")
        if isinstance(expr, str):
            expressions.append((None, code, expr))
    return expressions


def publish(draft: FormDefinition, published_at: datetime) -> FormRelease:
    """从草稿发布一个不可变版本；版本号递增，旧版本不受后续草稿改动影响（FW06）。"""
    publish_check(set(draft.fields), _collect_expressions(draft))
    version = draft.releases[-1].version + 1 if draft.releases else 1
    release = FormRelease(
        form_id=draft.form_id or "",
        version=version,
        published_at=published_at,
        fields=dict(draft.fields),
        sections=[_snapshot_section(s) for s in draft.sections],
    )
    draft.releases.append(release)
    return release


def _snapshot_section(section: Section) -> Section:
    """复制一个分区快照，避免共享可变的字段列表。"""
    snapshot = Section(title=section.title, show_condition=section.show_condition)
    snapshot.fields = list(section.fields)
    return snapshot
