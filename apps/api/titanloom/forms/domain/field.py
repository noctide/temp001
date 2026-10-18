"""字段定义：稳定 code + 显示名 + 类型 + 设置。

字段类型按值的类型划分（子方案 26.3.1）。公式、显示条件、组件绑定均
只引用 code；改名只改显示名，code 不变（FW18）。
FieldDefinition 不可变：改名/改设置返回新对象，发布时快照共享不可变对象，
旧版本不受草稿后续改动影响（FW06）。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from types import MappingProxyType
from typing import Any


class FieldKind(StrEnum):
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    TIME = "time"
    OPTION = "option"
    PERSON = "person"
    LOOKUP = "lookup"
    COMPUTED = "computed"
    REPEATING_GROUP = "repeating_group"
    ATTACHMENT = "attachment"
    HTML = "html"


@dataclass(frozen=True)
class FieldDefinition:
    code: str  # 稳定字段编号，不随显示名变更
    label_zh: str
    label_en: str
    kind: FieldKind = FieldKind.TEXT
    settings: Mapping[str, Any] | None = None
    required: bool = False

    def __post_init__(self) -> None:
        raw: Mapping[str, Any] | None = self.settings
        frozen: Mapping[str, Any] = MappingProxyType({}) if raw is None else MappingProxyType(dict(raw))
        object.__setattr__(self, "settings", frozen)

    def with_label(self, *, label_zh: str | None = None, label_en: str | None = None) -> FieldDefinition:
        """改名：返回新对象，code 不变；按 code 引用的公式/条件不受影响（FW18）。"""
        return replace(
            self,
            label_zh=self.label_zh if label_zh is None else label_zh,
            label_en=self.label_en if label_en is None else label_en,
        )

    def with_settings(self, settings: Mapping[str, Any]) -> FieldDefinition:
        return replace(self, settings=settings)

    def with_required(self, required: bool) -> FieldDefinition:
        return replace(self, required=required)
