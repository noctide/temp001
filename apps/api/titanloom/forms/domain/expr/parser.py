"""语法分析器：文本 -> AST。

优先级（从低到高）：or > and > not > 比较 > +/- > * / > 原子。
"""

from __future__ import annotations

from decimal import Decimal

from titanloom.forms.domain.expr import ast as ast_
from titanloom.forms.domain.expr.errors import ExprError
from titanloom.forms.domain.expr.lexer import (
    COMMA,
    EOF,
    FIELD_REF,
    IDENT,
    LPAREN,
    NUMBER,
    RPAREN,
    Token,
    tokenize,
)

_COMPARISON_OPS = frozenset({"=", "!=", "<", "<=", ">", ">="})
_ADDITIVE_OPS = frozenset({"+", "-"})
_MULTIPLICATIVE_OPS = frozenset({"*", "/"})


class _Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.pos = 0

    @property
    def current(self) -> Token:
        return self.tokens[self.pos]

    def advance(self) -> Token:
        token = self.current
        self.pos += 1
        return token

    def match(self, type_: str, value: str | None = None) -> bool:
        t = self.current
        if t.type != type_:
            return False
        if value is not None and t.value != value:
            return False
        self.pos += 1
        return True

    def expect(self, type_: str, value: str | None = None) -> Token:
        t = self.current
        if t.type != type_ or (value is not None and t.value != value):
            raise ExprError(
                "SYNTAX",
                f"期望 {type_}，实际 {t.type} {t.value!r} (位置 {t.pos})",
            )
        self.pos += 1
        return t

    def parse(self, text: str) -> ast_.Expr:
        tokens = tokenize(text)
        self.tokens = tokens
        self.pos = 0
        expr = self._or()
        self.expect(EOF)
        return expr

    def _or(self) -> ast_.Expr:
        left = self._and()
        while self.match(IDENT, "or"):
            right = self._and()
            left = ast_.Binary("or", left, right)
        return left

    def _and(self) -> ast_.Expr:
        left = self._not()
        while self.match(IDENT, "and"):
            right = self._not()
            left = ast_.Binary("and", left, right)
        return left

    def _not(self) -> ast_.Expr:
        if self.match(IDENT, "not"):
            operand = self._not()
            return ast_.Unary("not", operand)
        return self._comparison()

    def _comparison(self) -> ast_.Expr:
        left = self._additive()
        while self.current.value in _COMPARISON_OPS:
            op = self.current.value
            self.advance()
            right = self._additive()
            left = ast_.Binary(op, left, right)
        return left

    def _additive(self) -> ast_.Expr:
        left = self._multiplicative()
        while self.current.value in _ADDITIVE_OPS:
            op = self.current.value
            self.advance()
            right = self._multiplicative()
            left = ast_.Binary(op, left, right)
        return left

    def _multiplicative(self) -> ast_.Expr:
        left = self._primary()
        while self.current.value in _MULTIPLICATIVE_OPS:
            op = self.current.value
            self.advance()
            right = self._primary()
            left = ast_.Binary(op, left, right)
        return left

    def _primary(self) -> ast_.Expr:
        t = self.current
        if t.type == NUMBER:
            self.advance()
            return ast_.Literal(Decimal(t.value), ast_.ValueKind.NUMBER)
        if t.type == FIELD_REF:
            self.advance()
            return ast_.FieldRef(t.value[1:])  # 去掉前导 $
        if t.type == IDENT:
            name = t.value
            self.advance()
            if self.match(LPAREN):  # 消费 (；match 不会窄化 current.type，避免 pyright 误报
                args: list[ast_.Expr] = []
                if self.current.type != RPAREN:
                    args.append(self._or())
                    while self.match(COMMA):
                        args.append(self._or())
                self.expect(RPAREN)
                return ast_.Call(name, args)
            raise ExprError("SYNTAX", f"意外的标识符：{name!r}")
        if t.type == LPAREN:
            self.advance()
            inner = self._or()
            self.expect(RPAREN)
            return inner
        raise ExprError("SYNTAX", f"意外的符号：{t.type} {t.value!r} (位置 {t.pos})")


def parse(text: str) -> ast_.Expr:
    return _Parser([]).parse(text)


def referenced_fields(text: str) -> list[str]:
    """解析表达式，返回其中引用的字段编码（不含 $，可能重复）。解析失败返回空。"""
    try:
        tree = parse(text)
    except ExprError:
        return []
    refs: list[str] = []

    def collect(node: ast_.Expr) -> None:
        if isinstance(node, ast_.FieldRef):
            refs.append(node.code)
        elif isinstance(node, ast_.Binary):
            collect(node.left)
            collect(node.right)
        elif isinstance(node, ast_.Unary):
            collect(node.operand)
        elif isinstance(node, ast_.Call):
            for arg in node.args:
                collect(arg)
        # Literal: 无引用

    collect(tree)
    return refs
