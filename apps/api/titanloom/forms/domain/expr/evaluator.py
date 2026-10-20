"""表达式求值器：带预算（嵌套深度，业务参数 forms.expr.depthLimit）与类型检查。

对外暴露 evaluate 与预算常量；expression_depth 供 publish_check 预算预检用。
单次计算时限 forms.expr.computeMs 由应用层计时（领域层不直接读时钟）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
from decimal import Decimal
from typing import assert_never, cast

from titanloom.forms.domain.expr import ast as ast_
from titanloom.forms.domain.expr.arithmetic import arithmetic
from titanloom.forms.domain.expr.errors import ExprError
from titanloom.forms.domain.expr.functions import FUNCTIONS
from titanloom.forms.domain.expr.parser import parse
from titanloom.forms.domain.expr.types import Value, ValueKind
from titanloom.kernel.params import ParamStore
from titanloom.kernel.reg.manifest import P

_PARAMS = ParamStore()
DEFAULT_DEPTH_LIMIT = int(_PARAMS.get(P.forms.expr.depthLimit))
COMPUTE_BUDGET_MS = int(_PARAMS.get(P.forms.expr.computeMs))

_ARITHMETIC_OPS = frozenset({"+", "-", "*", "/"})
_COMPARISON_OPS = frozenset({"=", "!=", "<", "<=", ">", ">="})
_LOGICAL_OPS = frozenset({"and", "or"})


@dataclass
class _Budget:
    depth_limit: int


def evaluate(
    expr: str,
    fields: dict[str, Value],
    *,
    depth_limit: int = DEFAULT_DEPTH_LIMIT,
) -> Value:
    """求值表达式。fields: 字段编码 -> Value（携带类型）。"""
    try:
        tree = parse(expr)
    except ExprError:
        raise
    except Exception as exc:  # 词法/语法层面的意外异常统一为 SYNTAX
        raise ExprError("SYNTAX", str(exc)) from exc
    budget = _Budget(depth_limit)
    return _eval(tree, fields, budget, depth=0)


def _eval(node: ast_.Expr, fields: dict[str, Value], budget: _Budget, depth: int) -> Value:
    if depth > budget.depth_limit:
        raise ExprError("BUDGET_DEPTH", f"表达式嵌套深度超过 {budget.depth_limit}")
    match node:
        case ast_.Literal():
            return Value(node.kind, node.value)
        case ast_.FieldRef(code=code):
            if code not in fields:
                raise ExprError("UNKNOWN_FIELD", f"未定义的字段：{code}")
            return fields[code]
        case ast_.Unary(op=op, operand=operand):
            if op != "not":
                raise ExprError("SYNTAX", f"未知一元运算符：{op}")
            return Value(ValueKind.BOOL, not _as_bool(_eval(operand, fields, budget, depth + 1), "not"))
        case ast_.Binary(op=op, left=left, right=right):
            return _binary(op, left, right, fields, budget, depth + 1)
        case ast_.Call(name=name, args=args):
            return _call(name, args, fields, budget, depth + 1)
        case _:
            assert_never(node)  # pragma: no cover


def _binary(op: str, left: ast_.Expr, right: ast_.Expr, fields: dict[str, Value], budget: _Budget, depth: int) -> Value:
    if op in _LOGICAL_OPS:
        left_bool = _as_bool(_eval(left, fields, budget, depth), op)
        right_bool = _as_bool(_eval(right, fields, budget, depth), op)
        if op == "and":
            return Value(ValueKind.BOOL, left_bool and right_bool)
        return Value(ValueKind.BOOL, left_bool or right_bool)
    if op in _ARITHMETIC_OPS:
        return _arithmetic(op, left, right, fields, budget, depth)
    if op in _COMPARISON_OPS:
        return _comparison(op, left, right, fields, budget, depth)
    raise ExprError("SYNTAX", f"未知运算符：{op}")


def _arithmetic(
    op: str,
    left: ast_.Expr,
    right: ast_.Expr,
    fields: dict[str, Value],
    budget: _Budget,
    depth: int,
) -> Value:
    lv = _eval(left, fields, budget, depth)
    rv = _eval(right, fields, budget, depth)
    if lv.kind != ValueKind.NUMBER or rv.kind != ValueKind.NUMBER:
        raise ExprError("TYPE_MISMATCH", f"{op} 两侧须为 number")
    a = cast(Decimal, lv.value)
    b = cast(Decimal, rv.value)
    return Value(ValueKind.NUMBER, arithmetic(op, a, b))


def _comparison(
    op: str,
    left: ast_.Expr,
    right: ast_.Expr,
    fields: dict[str, Value],
    budget: _Budget,
    depth: int,
) -> Value:
    lv = _eval(left, fields, budget, depth)
    rv = _eval(right, fields, budget, depth)
    if lv.kind != rv.kind:
        raise ExprError("TYPE_MISMATCH", f"比较两侧类型不一致：{lv.kind} vs {rv.kind}")
    if op in ("=", "!="):
        result = lv.value == rv.value
        result = result if op == "=" else not result
    else:
        if lv.kind == ValueKind.BOOL:
            raise ExprError("TYPE_MISMATCH", "布尔值不支持大小比较")
        result = _compare_ordering(lv, rv, op)
    return Value(ValueKind.BOOL, result)


def _compare_ordering(lv: Value, rv: Value, op: str) -> bool:
    """两侧类型相同（已排除 bool），按 kind 分别比较并返回结果。"""
    match lv.kind:
        case ValueKind.NUMBER:
            a = cast(Decimal, lv.value)
            b = cast(Decimal, rv.value)
            cmp = (a > b) - (a < b)
        case ValueKind.DATE:
            a = cast(date, lv.value)
            b = cast(date, rv.value)
            cmp = (a > b) - (a < b)
        case ValueKind.TIME:
            a = cast(time, lv.value)
            b = cast(time, rv.value)
            cmp = (a > b) - (a < b)
        case ValueKind.TEXT:
            a = cast(str, lv.value)
            b = cast(str, rv.value)
            cmp = (a > b) - (a < b)
        case _:
            raise AssertionError("不支持的比较类型")  # pragma: no cover
    return {
        "<": cmp < 0,
        "<=": cmp <= 0,
        ">": cmp > 0,
        ">=": cmp >= 0,
    }[op]


def _call(name: str, args: list[ast_.Expr], fields: dict[str, Value], budget: _Budget, depth: int) -> Value:
    fn = FUNCTIONS.get(name)
    if fn is None:
        raise ExprError("UNKNOWN_FUNCTION", f"未知函数：{name}")
    evaluated = [_eval(arg, fields, budget, depth) for arg in args]
    return fn(evaluated)


def _as_bool(value: Value, where: str) -> bool:
    if value.kind != ValueKind.BOOL:
        raise ExprError("TYPE_MISMATCH", f"{where} 期望 bool，实际 {value.kind}")
    return cast(bool, value.value)


def expression_depth(tree: ast_.Expr) -> int:
    """表达式语法树深度（用于预算预检）。"""
    match tree:
        case ast_.Literal() | ast_.FieldRef():
            return 1
        case ast_.Unary(operand=operand):
            return 1 + expression_depth(operand)
        case ast_.Binary(left=left, right=right):
            return 1 + max(expression_depth(left), expression_depth(right))
        case ast_.Call(args=args):
            return 1 + max((expression_depth(a) for a in args), default=0)
        case _:
            assert_never(tree)  # pragma: no cover
