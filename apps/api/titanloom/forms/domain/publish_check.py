"""发布前检查：公式/显示条件引用的字段必须已定义；否则拒绝发布（子方案 26.3.4）。"""

from __future__ import annotations

import re
from collections.abc import Iterable

_FIELD_REF = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")


class PublishCheckFailed(Exception):
    """发布前检查不通过。"""


def publish_check(defined: set[str], expressions: Iterable[str | None]) -> bool:
    """定义的字段码集合 + 待校验表达式；引用未定义字段则抛 PublishCheckFailed。"""
    problems: list[str] = []
    for index, expr in enumerate(expressions):
        if not expr:
            continue
        for ref in _FIELD_REF.findall(expr):
            if ref not in defined:
                problems.append(f"表达式 {index} 引用未定义字段 ${ref}")
    if problems:
        raise PublishCheckFailed("；".join(problems))
    return True
