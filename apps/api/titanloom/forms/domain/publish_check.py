"""发布前检查：公式/显示条件引用的字段必须已定义；否则抛 PublishCheckFailed。

问题列表结构化（字段编号、在哪个字段 / 分区、问题种类），不拼中文句子；
api 层再按需要映射为 INPUT_VALIDATION_FAILED + details，界面用文案键。
子方案 26.3.4。
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

_FIELD_REF = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")


@dataclass(frozen=True)
class CheckProblem:
    """单个检查问题。section_index 为 None 时为字段层面的问题；field_code 为 None 时为分区层面的问题。"""

    section_index: int | None
    field_code: str | None
    ref: str  # 引用的字段，如 "$nope"
    kind: str = "UNDEFINED_FIELD"  # 问题种类


class PublishCheckFailed(Exception):
    """发布前检查不通过，携带结构化问题列表（exc.problems）。"""

    def __init__(self, problems: list[CheckProblem]) -> None:
        self.problems = list(problems)
        summary = "; ".join(
            f"section={p.section_index} field={p.field_code} ref={p.ref} kind={p.kind}" for p in problems
        )
        super().__init__(summary or "发布前检查不通过")


def publish_check(
    defined: set[str],
    expressions: Iterable[tuple[int | None, str | None, str | None]],
) -> bool:
    """定义的字段码集合 + 待校验表达式（分区索引、字段码、表达式）。

    引用未定义字段则抛 PublishCheckFailed，全部定义则返回 True。
    """
    problems: list[CheckProblem] = []
    for section_index, field_code, expr in expressions:
        if not expr:
            continue
        for ref in _FIELD_REF.findall(expr):
            if ref not in defined:
                problems.append(
                    CheckProblem(
                        section_index=section_index,
                        field_code=field_code,
                        ref=ref,
                    )
                )
    if problems:
        raise PublishCheckFailed(problems)
    return True
