"""精确数值（工程规范 4.1；数据处理 12.3）：金额、工时、比率用 Decimal，不用 float；对外按字符串编码。"""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

HOURS = Decimal("0.01")  # 工时默认保留两位；各模块按设计另定的，传 step
_TEXT = re.compile(r"^-?(0|[1-9][0-9]*)(\.[0-9]+)?$")


def dec(value: str | int | Decimal) -> Decimal:
    """把字符串、整数变成 Decimal；不收 float（float 一进来就已经不精确了），不收无穷与 NaN。"""
    if isinstance(value, float):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise TypeError("精确数值不收 float，请传字符串")
    try:
        d = Decimal(value)
    except InvalidOperation as e:
        raise ValueError(f"不是数值：{value!r}") from e
    if not d.is_finite():
        raise ValueError("精确数值不能是无穷或 NaN")
    return d


def parse_text(text: str) -> Decimal:
    """接口收到的数字字符串：只认规范写法（不认科学计数、空格、千分位）。"""
    if not _TEXT.match(text):
        raise ValueError(f"不是规范的数字字符串：{text!r}")
    return Decimal(text)


def encode(value: Decimal) -> str:
    """对外编码：定点字符串，不用科学计数法。"""
    s = format(value, "f")
    return "0" if s == "-0" else s


def quantize(value: Decimal, step: Decimal = HOURS) -> Decimal:
    return value.quantize(step, rounding=ROUND_HALF_UP)
