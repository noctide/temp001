"""表单草稿与发布版本（阶段 1）：草稿可编辑，发布形成不可变版本（FW06）。"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as _field
from datetime import datetime

from titanloom.forms.domain.field import FieldDefinition
from titanloom.forms.domain.publish_check import publish_check


@dataclass
class Section:
    """表单的分区：标题、字段列表、计算公式、显示条件。"""

    title: str = ""
    formula: str | None = None
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
        return self._fields[code]

    def add_field(self, definition: FieldDefinition) -> None:
        self._fields[definition.code] = definition
        if definition.code not in self.sections[0].fields:
            self.sections[0].fields.append(definition.code)

    def remove_field(self, code: str) -> None:
        if code not in self._fields:
            raise KeyError(f"字段不存在：{code}")
        del self._fields[code]
        for section in self.sections:
            if code in section.fields:
                section.fields.remove(code)

    def rename_field(self, code: str, new_zh: str, new_en: str | None = None) -> None:
        """改名只改显示名，code 不变；按 code 引用的公式/条件不受影响（FW18）。"""
        existing = self._fields[code]
        existing.label_zh = new_zh
        if new_en is not None:
            existing.label_en = new_en


def publish(draft: FormDefinition, published_at: datetime) -> FormRelease:
    """从草稿发布一个不可变版本；版本号递增，旧版本不受后续草稿改动影响（FW06）。"""
    expressions = [expr for section in draft.sections for expr in (section.formula, section.show_condition)]
    publish_check(set(draft.fields), expressions)
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
    snapshot = Section(title=section.title, formula=section.formula, show_condition=section.show_condition)
    snapshot.fields = list(section.fields)
    return snapshot
