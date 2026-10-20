"""表达式静态检查：函数名、参数个数、能静态判断的类型（发布前检查用）。

只做不依赖运行时值就能确定的判断；字段类型未知（如查询字段）时返回 None，留给求值阶段。
"""

from __future__ import annotations

from collections.abc import Mapping

from titanloom.forms.domain.expr import ast as ast_
from titanloom.forms.domain.expr.errors import ExprError
from titanloom.forms.domain.expr.functions import SIGNATURES
from titanloom.forms.domain.expr.types import ValueKind

_ARITHMETIC_OPS = frozenset({"+", "-", "*", "/"})
_COMPARISON_OPS = frozenset({"=", "!=", "<", "<=", ">", ">="})
_ORDERING_OPS = frozenset({"<", "<=", ">", ">="})
_LOGICAL_OPS = frozenset({"and", "or"})


def static_type(tree: ast_.Expr, fields: Mapping[str, ValueKind | None]) -> ValueKind | None:
    """返回表达式的静态类型；无法静态判断时返回 None。类型错误抛 TYPE_MISMATCH。"""
    match tree:
        case ast_.Literal():
            return ValueKind.NUMBER
        case ast_.FieldRef(code=code):
            return fields.get(code)
        case ast_.Unary(op=op, operand=operand):
            if op != "not":
                raise ExprError("SYNTAX", f"未知一元运算符：{op}")
            _expect(static_type(operand, fields), ValueKind.BOOL, "not")
            return ValueKind.BOOL
        case ast_.Binary(op=op, left=left, right=right):
            return _binary_type(op, static_type(left, fields), static_type(right, fields))
        case ast_.Call(name=name, args=args):
            return _call_type(name, args, fields)
        case _:
            raise AssertionError(f"未知表达式节点：{tree!r}")  # pragma: no cover


def _binary_type(op: str, left: ValueKind | None, right: ValueKind | None) -> ValueKind:
    if op in _LOGICAL_OPS:
        _expect(left, ValueKind.BOOL, op)
        _expect(right, ValueKind.BOOL, op)
        return ValueKind.BOOL
    if op in _ARITHMETIC_OPS:
        _expect(left, ValueKind.NUMBER, op)
        _expect(right, ValueKind.NUMBER, op)
        return ValueKind.NUMBER
    if op in _COMPARISON_OPS:
        if left is not None and right is not None and left != right:
            raise ExprError("TYPE_MISMATCH", f"{op} 两侧类型不一致：{left} vs {right}")
        if op in _ORDERING_OPS and ValueKind.BOOL in (left, right):
            raise ExprError("TYPE_MISMATCH", "布尔值不支持大小比较")
        return ValueKind.BOOL
    raise ExprError("SYNTAX", f"未知运算符：{op}")


def _call_type(name: str, args: list[ast_.Expr], fields: Mapping[str, ValueKind | None]) -> ValueKind | None:
    signature = SIGNATURES.get(name)
    if signature is None:
        raise ExprError("UNKNOWN_FUNCTION", f"未知函数：{name}")
    types = [static_type(arg, fields) for arg in args]
    if signature.varargs is None:
        if len(types) != len(signature.args):
            raise ExprError(
                "TYPE_MISMATCH",
                f"{name} 需要 {len(signature.args)} 个参数，实际 {len(types)} 个",
            )
        for index, (actual, expected) in enumerate(zip(types, signature.args, strict=True), start=1):
            _expect(actual, expected, f"{name} 第 {index} 个参数")
    else:
        for index, actual in enumerate(types, start=1):
            _expect(actual, signature.varargs, f"{name} 第 {index} 个参数")
    if name == "if":
        first, second = types[1], types[2]
        return first if first is not None and first == second else None
    return signature.returns


def _expect(actual: ValueKind | None, expected: ValueKind | None, where: str) -> None:
    if actual is not None and expected is not None and actual != expected:
        raise ExprError("TYPE_MISMATCH", f"{where} 期望 {expected}，实际 {actual}")
