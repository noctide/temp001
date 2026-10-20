"""考勤配置发布的纯校验（domain 层，不碰 DB、不读时钟）。

核心不变量（子方案 5、后端详细设计·考勤 2）：
同一配置类别、同适用范围（scope_kind + scope_ref）、同优先级的已发布版本，
有效期不得重叠；重叠拒绝发布。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class PublishConflictError(Exception):
    """同一配置类别、同适用范围、同优先级有效期重叠，拒绝发布。

    只携带结构化字段，不写中文 message；api 层再映射为错误码 + details。
    """

    candidate_id: str
    conflict_id: str
    kind: str  # 配置类别：type / shift / rule_set / plan / checkin_policy
    scope_kind: str  # org / dept / person
    scope_ref: str | None  # 部门或人员编号；org 时为 NULL
    priority: int
    candidate_range: tuple[date | None, date | None]  # (effective_from, effective_to)
    conflict_range: tuple[date | None, date | None]  # (effective_from, effective_to)


@dataclass(frozen=True)
class ConfigVersionRef:
    """发布冲突校验所需的最小版本信息（测试与 app 层均可构造）。"""

    id: str
    kind: str  # 配置类别
    scope_kind: str  # org / dept / person
    scope_ref: str | None  # 部门或人员编号；org 时为 NULL
    priority: int
    effective_from: date | None  # None = 从一开始（业务日）
    effective_to: date | None  # None = 永久有效（业务日）
    status: str  # draft / published / archived


def _range_overlap(
    a_from: date | None,
    a_to: date | None,
    b_from: date | None,
    b_to: date | None,
) -> bool:
    """半开区间 [from, to) 是否重叠；None 表示该端无穷（from=None 即从一开始，to=None 即永久）。"""
    lowers = [x for x in (a_from, b_from) if x is not None]
    uppers = [x for x in (a_to, b_to) if x is not None]
    lo = max(lowers) if lowers else None  # None 表示无下界
    hi = min(uppers) if uppers else None  # None 表示无上界
    # 只有当双方都有下界且都有上界，并且下界 >= 上界，才不重叠
    if lo is not None and hi is not None:
        return lo < hi
    return True


def assert_no_publish_overlap(
    existing: list[ConfigVersionRef],
    candidate: ConfigVersionRef,
    *,
    exclude_id: str | None = None,
) -> None:
    """若 candidate 以 published 发布会与已发布版本在同类别/同范围/同优先级下重叠，则抛 PublishConflictError。

    重叠判定键为（kind, scope_kind, scope_ref, priority）。
    """
    if candidate.status != "published":
        return
    for e in existing:
        if e.id == candidate.id or (exclude_id is not None and e.id == exclude_id):
            continue
        if e.status != "published":
            continue
        if (
            e.kind != candidate.kind
            or e.scope_kind != candidate.scope_kind
            or e.scope_ref != candidate.scope_ref
            or e.priority != candidate.priority
        ):
            continue
        if _range_overlap(
            candidate.effective_from,
            candidate.effective_to,
            e.effective_from,
            e.effective_to,
        ):
            raise PublishConflictError(
                candidate_id=candidate.id,
                conflict_id=e.id,
                kind=candidate.kind,
                scope_kind=candidate.scope_kind,
                scope_ref=candidate.scope_ref,
                priority=candidate.priority,
                candidate_range=(candidate.effective_from, candidate.effective_to),
                conflict_range=(e.effective_from, e.effective_to),
            )


__all__ = ["ConfigVersionRef", "PublishConflictError", "assert_no_publish_overlap"]
