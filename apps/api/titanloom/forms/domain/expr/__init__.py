"""表达式求值与显示条件（domain 层，纯 Python，不碰数据库/网络/时钟）。"""

from titanloom.forms.domain.expr.errors import ExprError
from titanloom.forms.domain.expr.evaluator import (
    COMPUTE_BUDGET_MS,
    DEFAULT_DEPTH_LIMIT,
    evaluate,
    expression_depth,
)
from titanloom.forms.domain.expr.functions import FUNCTIONS
from titanloom.forms.domain.expr.parser import field_refs, parse, referenced_fields
from titanloom.forms.domain.expr.static import static_type
from titanloom.forms.domain.expr.types import (
    Value,
    ValueKind,
    format_number,
    number,
    parse_field_value,
)

__all__ = [
    "COMPUTE_BUDGET_MS",
    "DEFAULT_DEPTH_LIMIT",
    "FUNCTIONS",
    "ExprError",
    "Value",
    "ValueKind",
    "evaluate",
    "expression_depth",
    "field_refs",
    "format_number",
    "number",
    "parse",
    "parse_field_value",
    "referenced_fields",
    "static_type",
]
