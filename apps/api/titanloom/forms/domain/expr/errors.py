"""表达式求值错误（domain-local，不占用注册的 error-codes.json 键）。"""

from __future__ import annotations


class ExprError(Exception):
    """表达式解析/求值错误。

    code: UNKNOWN_FIELD | UNKNOWN_FUNCTION | TYPE_MISMATCH | SYNTAX |
          DIVIDE_BY_ZERO | CYCLE | BUDGET_DEPTH
    """

    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        self.message = message
        text = f"{code}: {message}" if message else code
        super().__init__(text)
