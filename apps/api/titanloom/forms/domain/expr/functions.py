"""内置函数实现（functions.json 的 6 个函数：daysBetween/workdays/hoursBetween/sum/if/round）。

SIGNATURES 供发布前静态检查（函数名、参数个数、类型）使用，与实现放在一起避免两套声明。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import cast

from titanloom.forms.domain.expr.errors import ExprError
from titanloom.forms.domain.expr.types import Value, ValueKind


def _require_args(name: str, args: list[Value], expected: list[ValueKind]) -> None:
    if len(args) != len(expected):
        raise ExprError(
            "TYPE_MISMATCH",
            f"{name} 需要 {len(expected)} 个参数，实际 {len(args)} 个",
        )
    for index, (arg, exp) in enumerate(zip(args, expected, strict=False), start=1):
        if arg.kind != exp:
            raise ExprError(
                "TYPE_MISMATCH",
                f"{name} 第 {index} 个参数期望 {exp}，实际 {arg.kind}",
            )


def _as_number(value: Value, where: str) -> Decimal:
    if value.kind != ValueKind.NUMBER:
        raise ExprError("TYPE_MISMATCH", f"{where} 期望 number，实际 {value.kind}")
    return cast(Decimal, value.value)


def _as_date(value: Value, where: str) -> date:
    if value.kind != ValueKind.DATE:
        raise ExprError("TYPE_MISMATCH", f"{where} 期望 date，实际 {value.kind}")
    return cast(date, value.value)


def _as_time(value: Value, where: str) -> time:
    if value.kind != ValueKind.TIME:
        raise ExprError("TYPE_MISMATCH", f"{where} 期望 time，实际 {value.kind}")
    return cast(time, value.value)


def _as_bool(value: Value, where: str) -> bool:
    if value.kind != ValueKind.BOOL:
        raise ExprError("TYPE_MISMATCH", f"{where} 期望 bool，实际 {value.kind}")
    return cast(bool, value.value)


def daysBetween(args: list[Value]) -> Value:
    _require_args("daysBetween", args, [ValueKind.DATE, ValueKind.DATE])
    d1 = _as_date(args[0], "daysBetween")
    d2 = _as_date(args[1], "daysBetween")
    return Value(ValueKind.NUMBER, Decimal((d1 - d2).days))


def workdays(args: list[Value]) -> Value:
    """含首尾；没有日历时按周一至周五。"""
    _require_args("workdays", args, [ValueKind.DATE, ValueKind.DATE])
    d1 = _as_date(args[0], "workdays")
    d2 = _as_date(args[1], "workdays")
    lo, hi = (d1, d2) if d1 <= d2 else (d2, d1)
    count = 0
    cur = lo
    while cur <= hi:
        if cur.weekday() < 5:  # Mon-Fri
            count += 1
        cur = cur + timedelta(days=1)
    return Value(ValueKind.NUMBER, Decimal(count))


def hoursBetween(args: list[Value]) -> Value:
    """结束早于开始时按跨夜计算。"""
    _require_args("hoursBetween", args, [ValueKind.TIME, ValueKind.TIME])
    t1 = _as_time(args[0], "hoursBetween")
    t2 = _as_time(args[1], "hoursBetween")
    m1 = t1.hour * 60 + t1.minute
    m2 = t2.hour * 60 + t2.minute
    minutes = (m2 - m1) if m2 >= m1 else (24 * 60 - m1) + m2
    return Value(ValueKind.NUMBER, Decimal(minutes) / Decimal(60))


def sum_fn(args: list[Value]) -> Value:
    total = Decimal(0)
    for index, arg in enumerate(args, start=1):
        total += _as_number(arg, f"sum 第 {index} 个参数")
    return Value(ValueKind.NUMBER, total)


def if_fn(args: list[Value]) -> Value:
    if len(args) != 3:
        raise ExprError("TYPE_MISMATCH", f"if 需要 3 个参数，实际 {len(args)} 个")
    cond = _as_bool(args[0], "if 第 1 个参数")
    return args[1] if cond else args[2]


def round_fn(args: list[Value]) -> Value:
    if len(args) != 2:
        raise ExprError("TYPE_MISMATCH", f"round 需要 2 个参数，实际 {len(args)} 个")
    x = _as_number(args[0], "round 第 1 个参数")
    n = _as_number(args[1], "round 第 2 个参数")
    if n != n.to_integral_value():
        raise ExprError("TYPE_MISMATCH", "round 第 2 个参数必须是整数")
    step = Decimal(1).scaleb(-int(n))
    return Value(ValueKind.NUMBER, x.quantize(step, rounding=ROUND_HALF_UP))


FUNCTIONS: dict[str, Callable[[list[Value]], Value]] = {
    "daysBetween": daysBetween,
    "workdays": workdays,
    "hoursBetween": hoursBetween,
    "sum": sum_fn,
    "if": if_fn,
    "round": round_fn,
}


@dataclass(frozen=True)
class Signature:
    """函数签名：固定参数；varargs 为可变参数类型；returns 为 None 时按实参推断（if）。"""

    args: tuple[ValueKind | None, ...]  # None = any
    varargs: ValueKind | None = None
    returns: ValueKind | None = None


SIGNATURES: dict[str, Signature] = {
    "daysBetween": Signature((ValueKind.DATE, ValueKind.DATE), returns=ValueKind.NUMBER),
    "workdays": Signature((ValueKind.DATE, ValueKind.DATE), returns=ValueKind.NUMBER),
    "hoursBetween": Signature((ValueKind.TIME, ValueKind.TIME), returns=ValueKind.NUMBER),
    "sum": Signature((), varargs=ValueKind.NUMBER, returns=ValueKind.NUMBER),
    "if": Signature((ValueKind.BOOL, None, None)),
    "round": Signature((ValueKind.NUMBER, ValueKind.NUMBER), returns=ValueKind.NUMBER),
}
