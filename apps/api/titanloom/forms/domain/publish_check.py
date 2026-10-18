"""发布前检查：公式/显示条件引用的字段必须已定义；依赖图无环；在预算内。

问题列表结构化（字段编号、在哪个字段 / 分区、问题种类），不拼中文句子；
api 层再按需要映射为 INPUT_VALIDATION_FAILED + details，界面用文案键。
子方案 26.3.4。阶段 2 改用表达式解析器给出的引用字段列表，删掉正则。
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from titanloom.forms.domain.expr import (
    DEFAULT_DEPTH_LIMIT,
    DEFAULT_REF_LIMIT,
    count_refs,
    expression_depth,
    parse,
)
from titanloom.forms.domain.expr.dependency import extract_refs, has_cycle
from titanloom.forms.domain.expr.errors import ExprError


class CheckKind(StrEnum):
    UNDEFINED_FIELD = "UNDEFINED_FIELD"
    CYCLE = "CYCLE"
    BUDGET_DEPTH = "BUDGET_DEPTH"
    BUDGET_REFS = "BUDGET_REFS"


@dataclass(frozen=True)
class CheckProblem:
    """单个检查问题。

    section_index 为 None 时为字段层面的问题；field_code 为 None 时为分区层面的问题。
    ref 为引用的字段编码（不含 $），对 CYCLE/预算问题可为空。
    """

    section_index: int | None
    field_code: str | None
    ref: str
    kind: CheckKind = CheckKind.UNDEFINED_FIELD


class PublishCheckFailed(Exception):
    """发布前检查不通过，携带结构化问题列表（exc.problems）。"""

    def __init__(self, problems: list[CheckProblem]) -> None:
        self.problems = list(problems)
        summary = "; ".join(
            f"section={p.section_index} field={p.field_code} ref={p.ref} kind={p.kind}" for p in problems
        )
        super().__init__(summary or "publish check failed")


def publish_check(
    defined: set[str],
    expressions: Iterable[tuple[int | None, str | None, str | None]],
) -> bool:
    """定义的字段码集合 + 待校验表达式（分区索引、字段码、表达式）。

    引用未定义字段、存在循环依赖或超预算则抛 PublishCheckFailed，全部通过返回 True。
    """
    problems: list[CheckProblem] = []
    deps: dict[str, set[str]] = {}
    for section_index, field_code, expr in expressions:
        if not expr:
            continue
        _check_expression(section_index, field_code, expr, defined, problems, deps)
    if has_cycle(deps):
        problems.append(
            CheckProblem(
                section_index=None,
                field_code=None,
                ref="",
                kind=CheckKind.CYCLE,
            )
        )
    if problems:
        raise PublishCheckFailed(problems)
    return True


def _check_expression(
    section_index: int | None,
    field_code: str | None,
    expr: str,
    defined: set[str],
    problems: list[CheckProblem],
    deps: dict[str, set[str]],
) -> None:
    """校验单个表达式：引用是否已定义、依赖边、预算（深度/引用数）。"""
    refs = extract_refs(expr)
    for ref in refs:
        if ref not in defined:
            problems.append(
                CheckProblem(
                    section_index=section_index,
                    field_code=field_code,
                    ref=ref,
                )
            )
    if field_code is not None:
        deps[field_code] = set(refs)
    # 预算预检：深度与引用数（解析失败的表达式由求值时的 SYNTAX 兜底）
    try:
        tree = parse(expr)
    except ExprError:
        return
    if expression_depth(tree) > DEFAULT_DEPTH_LIMIT:
        problems.append(
            CheckProblem(
                section_index=section_index,
                field_code=field_code,
                ref="",
                kind=CheckKind.BUDGET_DEPTH,
            )
        )
    if count_refs(tree) > DEFAULT_REF_LIMIT:
        problems.append(
            CheckProblem(
                section_index=section_index,
                field_code=field_code,
                ref="",
                kind=CheckKind.BUDGET_REFS,
            )
        )
