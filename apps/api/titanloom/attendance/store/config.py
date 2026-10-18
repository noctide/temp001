"""考勤配置发布的纯校验（store 层，不碰 DB、不读时钟）。

核心不变量（子方案 5、后端详细设计·考勤 2）：
同一适用范围、同优先级的已发布版本，有效期不得重叠；重叠拒绝发布。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


class PublishConflictError(ValueError):
    """同范围同优先级有效期重叠，拒绝发布。"""


@dataclass(frozen=True)
class ConfigVersionRef:
    """发布冲突校验所需的最小版本信息（测试与 app 层均可构造）。"""

    id: str
    scope: str
    priority: int
    effective_from: datetime | None  # None = 从一开始
    effective_to: datetime | None  # None = 永久有效
    status: str  # draft / published / archived


def _range_overlap(
    a_from: datetime | None,
    a_to: datetime | None,
    b_from: datetime | None,
    b_to: datetime | None,
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
    """若 candidate 以 published 发布会与已发布版本在同范围同优先级下重叠，则抛 PublishConflictError。"""
    if candidate.status != "published":
        return
    for e in existing:
        if e.id == candidate.id or (exclude_id is not None and e.id == exclude_id):
            continue
        if e.status != "published":
            continue
        if e.scope != candidate.scope or e.priority != candidate.priority:
            continue
        if _range_overlap(candidate.effective_from, candidate.effective_to, e.effective_from, e.effective_to):
            raise PublishConflictError(
                f"配置“{candidate.id}”的生效期 [{candidate.effective_from}, {candidate.effective_to}) "
                f"与已发布版本“{e.id}”的 [{e.effective_from}, {e.effective_to}) 重叠（"
                f"范围={candidate.scope}，优先级={candidate.priority}），拒绝发布"
            )


__all__ = ["ConfigVersionRef", "PublishConflictError", "assert_no_publish_overlap"]
