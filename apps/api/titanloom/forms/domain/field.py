"""字段定义：稳定 code + 显示名 + 类型 + 设置。

公式、显示条件、组件绑定均只引用 code；显示名变更不影响它们（FW18）。
子方案 26.3.1：字段类型按值的类型划分。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class FieldKind:
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


@dataclass
class FieldDefinition:
    code: str  # 稳定字段编号，不随显示名变更
    label_zh: str
    label_en: str
    kind: str = FieldKind.TEXT
    required: bool = False

    def __post_init__(self) -> None:
        self.settings: dict[str, Any] = {}
