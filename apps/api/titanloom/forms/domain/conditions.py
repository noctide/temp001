"""显示条件求值：结果必须为 bool（FW14 服务端独立评估，前后端位对齐）。"""

from __future__ import annotations

from typing import cast

from titanloom.forms.domain.expr.errors import ExprError
from titanloom.forms.domain.expr.evaluator import evaluate
from titanloom.forms.domain.expr.types import Value, ValueKind


def evaluate_condition(expr: str | None, fields: dict[str, Value]) -> bool:
    """求值显示条件。

    expr 为空或空字符串视为 true；求值结果非 bool 抛 TYPE_MISMATCH；
    引用未定义字段抛 UNKNOWN_FIELD。
    """
    if not expr:
        return True
    result = evaluate(expr, fields)
    if result.kind != ValueKind.BOOL:
        raise ExprError("TYPE_MISMATCH", f"显示条件结果必须为 bool，实际 {result.kind}")
    return cast(bool, result.value)
