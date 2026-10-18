"""表达式值类型：number（Decimal）、date、time、text、bool。

精确数值用 Decimal，不用 float；对外按十进制字符串编码。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
from decimal import Decimal
from enum import StrEnum

from titanloom.kernel.exact import dec


class ValueKind(StrEnum):
    NUMBER = "number"
    DATE = "date"
    TIME = "time"
    TEXT = "text"
    BOOL = "bool"


@dataclass(frozen=True)
class Value:
    kind: ValueKind
    value: Decimal | date | time | str | bool


def number(text: str) -> Decimal:
    """把规范数字字符串变成 Decimal。"""
    return dec(text)


def parse_field_value(kind: str, text: str) -> Value:
    """把契约里的字段值（type + value 字符串）转成 Value。"""
    if kind == ValueKind.NUMBER:
        return Value(ValueKind.NUMBER, dec(text))
    if kind == ValueKind.DATE:
        return Value(ValueKind.DATE, date.fromisoformat(text))
    if kind == ValueKind.TIME:
        return Value(ValueKind.TIME, time.fromisoformat(text))
    if kind == ValueKind.TEXT:
        return Value(ValueKind.TEXT, text)
    if kind == ValueKind.BOOL:
        return Value(ValueKind.BOOL, text.lower() == "true")
    raise ValueError(f"未知字段类型：{kind!r}")
