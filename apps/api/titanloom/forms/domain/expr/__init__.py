"""表达式求值与显示条件（domain 层，纯 Python，不碰数据库/网络/时钟）。"""

from titanloom.forms.domain.expr.dependency import extract_refs
from titanloom.forms.domain.expr.errors import ExprError
from titanloom.forms.domain.expr.evaluator import (
    DEFAULT_DEPTH_LIMIT,
    DEFAULT_REF_LIMIT,
    count_refs,
    evaluate,
    expression_depth,
)
from titanloom.forms.domain.expr.functions import FUNCTIONS
from titanloom.forms.domain.expr.parser import parse, referenced_fields
from titanloom.forms.domain.expr.types import Value, ValueKind, number, parse_field_value

__all__ = [
    "DEFAULT_DEPTH_LIMIT",
    "DEFAULT_REF_LIMIT",
    "FUNCTIONS",
    "ExprError",
    "Value",
    "ValueKind",
    "count_refs",
    "evaluate",
    "expression_depth",
    "extract_refs",
    "number",
    "parse",
    "parse_field_value",
    "referenced_fields",
]
