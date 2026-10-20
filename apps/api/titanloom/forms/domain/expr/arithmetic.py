"""数值精确运算：+ − × 精确（不截断）；÷ 保留 28 位有效数字、HALF_EVEN。

evaluator 的运算符与 `sum()` 共用这一份，避免同一个规则两套写法。
"""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal, localcontext

from titanloom.forms.domain.expr.errors import ExprError

# functions.json · arithmetic.divisionSignificantDigits
DIVISION_SIGNIFICANT_DIGITS = 28


def arithmetic(op: str, a: Decimal, b: Decimal) -> Decimal:
    if op in ("+", "-", "*"):
        # 默认上下文只有 28 位，会截断长结果；按操作数位数取足够精度。
        with localcontext() as ctx:
            ctx.prec = _exact_precision(a, b, op)
            if op == "+":
                return a + b
            if op == "-":
                return a - b
            return a * b
    if op == "/":
        if b == 0:
            raise ExprError("DIVIDE_BY_ZERO", "除数不能为零")
        with localcontext() as ctx:
            ctx.prec = DIVISION_SIGNIFICANT_DIGITS
            ctx.rounding = ROUND_HALF_EVEN
            return a / b
    raise AssertionError(f"未知算术运算符：{op}")  # pragma: no cover


def _exact_precision(a: Decimal, b: Decimal, op: str) -> int:
    """+ − × 不截断所需的有效数字位数（两操作数结果的位数上界）。"""
    if op == "*":
        return len(a.as_tuple().digits) + len(b.as_tuple().digits) + 1
    int_digits = max(a.adjusted() + 1, b.adjusted() + 1, 0)
    frac_digits = max(0, -int(a.as_tuple().exponent), -int(b.as_tuple().exponent))
    return int_digits + frac_digits + 1
