"""表达式抽象语法树。"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from titanloom.forms.domain.expr.types import ValueKind


@dataclass(frozen=True)
class Literal:
    value: Decimal
    kind: ValueKind = ValueKind.NUMBER


@dataclass(frozen=True)
class FieldRef:
    code: str


@dataclass(frozen=True)
class Binary:
    op: str
    left: Expr
    right: Expr


@dataclass(frozen=True)
class Unary:
    op: str  # "not"
    operand: Expr


@dataclass(frozen=True)
class Call:
    name: str
    args: list[Expr]


Expr = Literal | FieldRef | Binary | Unary | Call
