"""发布前检查：公式/显示条件完整解析、函数与类型校验、字段引用、依赖图无环、在预算内。

问题列表结构化（字段编号、在哪个字段 / 分区、问题种类），不拼中文句子；
api 层再按需要映射为 INPUT_VALIDATION_FAILED + details，界面用文案键。
子方案 26.3.4；预算值来自业务参数 forms.expr.depthLimit。
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from titanloom.forms.domain.expr.dependency import has_cycle
from titanloom.forms.domain.expr.errors import ExprError
from titanloom.forms.domain.expr.evaluator import DEFAULT_DEPTH_LIMIT, expression_depth
from titanloom.forms.domain.expr.parser import field_refs, parse
from titanloom.forms.domain.expr.static import static_type
from titanloom.forms.domain.expr.types import ValueKind
from titanloom.forms.domain.field import FieldKind


class CheckKind(StrEnum):
    UNDEFINED_FIELD = "UNDEFINED_FIELD"
    CYCLE = "CYCLE"
    BUDGET_DEPTH = "BUDGET_DEPTH"
    SYNTAX = "SYNTAX"
    UNKNOWN_FUNCTION = "UNKNOWN_FUNCTION"
    TYPE_MISMATCH = "TYPE_MISMATCH"


@dataclass(frozen=True)
class CheckProblem:
    """单个检查问题。

    section_index 为 None 时为字段层面的问题；field_code 为 None 时为分区层面的问题。
    ref 为引用的字段编码（不含 $），对 CYCLE/预算/语法问题为空。
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


# 字段类型 -> 表达式值类型；查询、计算、附件等静态类型未知，留给求值阶段。
_FIELD_VALUE_KIND: dict[FieldKind, ValueKind | None] = {
    FieldKind.TEXT: ValueKind.TEXT,
    FieldKind.NUMBER: ValueKind.NUMBER,
    FieldKind.DATE: ValueKind.DATE,
    FieldKind.TIME: ValueKind.TIME,
    FieldKind.OPTION: ValueKind.TEXT,
    FieldKind.PERSON: ValueKind.TEXT,
    FieldKind.LOOKUP: None,
    FieldKind.COMPUTED: None,
    FieldKind.REPEATING_GROUP: None,
    FieldKind.ATTACHMENT: None,
    FieldKind.HTML: None,
}

_EXPR_TO_CHECK: dict[str, CheckKind] = {
    "SYNTAX": CheckKind.SYNTAX,
    "UNKNOWN_FUNCTION": CheckKind.UNKNOWN_FUNCTION,
    "TYPE_MISMATCH": CheckKind.TYPE_MISMATCH,
}


def publish_check(
    defined: set[str] | Mapping[str, FieldKind],
    expressions: Iterable[tuple[int | None, str | None, str | None]],
) -> bool:
    """已定义字段（编码集合，或编码 -> 字段类型）+ 待校验表达式（分区索引、字段码、表达式）。

    引用未定义字段、语法错误、未知函数、静态类型不符、循环依赖或超预算则抛
    PublishCheckFailed，全部通过返回 True。
    """
    if isinstance(defined, Mapping):
        defined_codes = set(defined)
        field_types = {code: _FIELD_VALUE_KIND.get(kind) for code, kind in defined.items()}
    else:
        defined_codes = set(defined)
        field_types = {}
    problems: list[CheckProblem] = []
    deps: dict[str, set[str]] = {}
    for section_index, field_code, expr in expressions:
        if not expr:
            continue
        _check_expression(section_index, field_code, expr, defined_codes, field_types, problems, deps)
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
    defined_codes: set[str],
    field_types: Mapping[str, ValueKind | None],
    problems: list[CheckProblem],
    deps: dict[str, set[str]],
) -> None:
    """完整解析单个表达式：语法、引用、依赖边、预算、函数与静态类型。"""
    try:
        tree = parse(expr)
    except ExprError as exc:
        problems.append(_problem(section_index, field_code, "", exc.code))
        return
    refs = field_refs(tree)
    for ref in refs:
        if ref not in defined_codes:
            problems.append(
                CheckProblem(
                    section_index=section_index,
                    field_code=field_code,
                    ref=ref,
                )
            )
    if field_code is not None:
        deps[field_code] = set(refs)
    if expression_depth(tree) > DEFAULT_DEPTH_LIMIT:
        problems.append(
            CheckProblem(
                section_index=section_index,
                field_code=field_code,
                ref="",
                kind=CheckKind.BUDGET_DEPTH,
            )
        )
    try:
        result = static_type(tree, field_types)
    except ExprError as exc:
        problems.append(_problem(section_index, field_code, "", exc.code))
        return
    # 分区显示条件的结果必须是 bool（能静态判断时才报）。
    if field_code is None and result is not None and result != ValueKind.BOOL:
        problems.append(
            CheckProblem(
                section_index=section_index,
                field_code=field_code,
                ref="",
                kind=CheckKind.TYPE_MISMATCH,
            )
        )


def _problem(
    section_index: int | None,
    field_code: str | None,
    ref: str,
    code: str,
) -> CheckProblem:
    return CheckProblem(
        section_index=section_index,
        field_code=field_code,
        ref=ref,
        kind=_EXPR_TO_CHECK.get(code, CheckKind.SYNTAX),
    )
