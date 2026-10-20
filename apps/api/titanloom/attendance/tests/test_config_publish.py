"""配置发布纯校验测试：同类别/同范围/同优先级有效期重叠拒绝发布。"""

from __future__ import annotations

from datetime import date

import pytest

from titanloom.attendance.domain.config_publish import (
    ConfigVersionRef,
    PublishConflictError,
    assert_no_publish_overlap,
)

D1 = date(2026, 11, 1)
D2 = date(2026, 12, 1)
D3 = date(2027, 1, 1)


def ref(
    *,
    id: str = "v1",
    kind: str = "type",
    scope_kind: str = "org",
    scope_ref: str | None = None,
    priority: int = 0,
    start: date | None = None,
    end: date | None = None,
    status: str = "published",
) -> ConfigVersionRef:
    return ConfigVersionRef(
        id=id,
        kind=kind,
        scope_kind=scope_kind,
        scope_ref=scope_ref,
        priority=priority,
        effective_from=start,
        effective_to=end,
        status=status,
    )


def test_same_scope_same_priority_overlap_rejected() -> None:
    existing = [ref(id="v1", start=D1, end=D2)]
    candidate = ref(id="v2", start=date(2026, 11, 15), end=D3)
    with pytest.raises(PublishConflictError):
        assert_no_publish_overlap(existing, candidate)


def test_different_dept_same_priority_not_conflict() -> None:
    """不同部门、同优先级、有效期重叠：不冲突，可并发布。"""
    existing = [ref(id="v1", scope_kind="dept", scope_ref="dept-a", start=D1, end=D2)]
    candidate = ref(id="v2", scope_kind="dept", scope_ref="dept-b", start=D1, end=D2)
    assert_no_publish_overlap(existing, candidate)  # 不抛


def test_different_scope_kind_allowed() -> None:
    existing = [ref(id="v1", scope_kind="org", scope_ref=None, start=D1, end=D2)]
    candidate = ref(id="v2", scope_kind="dept", scope_ref="dept-a", start=D1, end=D2)
    assert_no_publish_overlap(existing, candidate)  # 不抛


def test_different_priority_allowed() -> None:
    existing = [ref(id="v1", priority=0, start=D1, end=D2)]
    candidate = ref(id="v2", priority=1, start=D1, end=D2)
    assert_no_publish_overlap(existing, candidate)


def test_draft_not_checked() -> None:
    existing = [ref(id="v1", start=D1, end=D2)]
    candidate = ref(id="v2", start=D1, end=D3, status="draft")
    assert_no_publish_overlap(existing, candidate)


def test_adjacent_not_overlap() -> None:
    """相邻边界 end==start 不算重叠（半开区间）。"""
    existing = [ref(id="v1", start=D1, end=D2)]
    candidate = ref(id="v2", start=D2, end=D3)
    assert_no_publish_overlap(existing, candidate)


def test_exclude_self_on_update() -> None:
    """同一版本重新发布时不与自己冲突（候选与已有同 id）。"""
    existing = [ref(id="v1", start=D1, end=D2)]
    candidate = ref(id="v1", start=D1, end=D2)
    assert_no_publish_overlap(existing, candidate)


def test_contains_fully() -> None:
    existing = [ref(id="v1", start=D1, end=D3)]
    candidate = ref(id="v2", start=D2, end=date(2026, 12, 15))
    with pytest.raises(PublishConflictError):
        assert_no_publish_overlap(existing, candidate)


def test_open_ended_overlaps_anything() -> None:
    existing = [ref(id="v1", start=None, end=None)]  # 永久有效
    candidate = ref(id="v2", start=D1, end=D2)
    with pytest.raises(PublishConflictError):
        assert_no_publish_overlap(existing, candidate)
