"""区间引擎测试（纯函数，不读库、不读时钟）。

覆盖子方案 10.1 三例、重叠休息、越界休息、跨夜，以及基于性质的测试。
"""

from __future__ import annotations

import pytest

from titanloom.attendance.domain.interval import (
    intersect,
    merge,
    subtract,
    total_seconds,
)

H = 3600  # 1 小时秒数


def _h(hours: float) -> int:
    return int(hours * H)


def test_merge_basic() -> None:
    assert merge([(_h(9), _h(12)), (_h(13), _h(18))]) == [(_h(9), _h(12)), (_h(13), _h(18))]
    # 重叠合并
    assert merge([(_h(9), _h(13)), (_h(12), _h(18))]) == [(_h(9), _h(18))]
    # 相邻合并
    assert merge([(_h(9), _h(12)), (_h(12), _h(18))]) == [(_h(9), _h(18))]
    assert merge([]) == []


def test_merge_unsorted() -> None:
    assert merge([(_h(13), _h(18)), (_h(9), _h(12))]) == [(_h(9), _h(12)), (_h(13), _h(18))]


def test_subtract_10_1_case1() -> None:
    """09:00--18:00 扣 12:00--13:00 -> 两段，8h。"""
    work = [(_h(9), _h(18))]
    breaks = [(_h(12), _h(13))]
    assert subtract(work, breaks) == [(_h(9), _h(12)), (_h(13), _h(18))]
    assert total_seconds(subtract(work, breaks)) == 8 * H


def test_subtract_10_1_case2() -> None:
    """09:00--21:00 扣两段休息 -> 三段，10h。"""
    work = [(_h(9), _h(21))]
    breaks = [(_h(12), _h(13)), (_h(18), _h(19))]
    assert subtract(work, breaks) == [(_h(9), _h(12)), (_h(13), _h(18)), (_h(19), _h(21))]
    assert total_seconds(subtract(work, breaks)) == 10 * H


def test_subtract_overlapping_breaks_not_double_counted() -> None:
    """重叠休息合并后只扣相交部分，不重复扣时。"""
    work = [(_h(9), _h(18))]
    breaks = [(_h(12), _h(13)), (_h(12.5), _h(13.5))]
    result = subtract(work, breaks)
    # 休息并集为 [12:00, 13:30)，有效两段 [9:00,12:00), [13:30,18:00) = 7.5h
    assert result == [(_h(9), _h(12)), (_h(13.5), _h(18))]
    assert total_seconds(result) == 7 * H + 30 * 60


def test_subtract_break_partially_outside_work() -> None:
    """越界休息只扣与工作相交的部分。"""
    work = [(_h(9), _h(18))]
    breaks = [(_h(8), _h(9.5))]
    assert subtract(work, breaks) == [(_h(9.5), _h(18))]
    assert total_seconds(subtract(work, breaks)) == 8 * H + 30 * 60


def test_subtract_break_fully_outside_work() -> None:
    """完全在工作之外的休息不扣。"""
    work = [(_h(9), _h(18))]
    breaks = [(_h(6), _h(8)), (_h(19), _h(21))]
    assert subtract(work, breaks) == [(_h(9), _h(18))]
    assert total_seconds(subtract(work, breaks)) == 9 * H


def test_subtract_cross_midnight() -> None:
    """夜班 20:00--次日08:00，休息 23:30--次日00:30 -> 共 11h。"""
    work = [(_h(20), _h(24) + _h(8))]
    breaks = [(_h(23.5), _h(24.5))]
    result = subtract(work, breaks)
    # work [20h,32h)=[72000,115200)。breaks [23.5h,24.5h)=[84600,88200)
    # 有效 [72000,84600)=3.5h + [88200,115200)=7.5h = 11h
    expected = [(_h(20), _h(23.5)), (_h(24.5), _h(32))]
    assert result == expected
    assert total_seconds(result) == 11 * H


def test_subtract_multiple_work_intervals() -> None:
    work = [(_h(9), _h(12)), (_h(13), _h(18))]
    breaks = [(_h(10), _h(11)), (_h(14), _h(15))]
    assert subtract(work, breaks) == [(_h(9), _h(10)), (_h(11), _h(12)), (_h(13), _h(14)), (_h(15), _h(18))]


def test_intersect_basic() -> None:
    a = [(_h(9), _h(18))]
    b = [(_h(12), _h(15)), (_h(16), _h(20))]
    assert intersect(a, b) == [(_h(12), _h(15)), (_h(16), _h(18))]
    assert intersect([], b) == []
    assert intersect(a, []) == []


def test_total_seconds_empty() -> None:
    assert total_seconds([]) == 0


def test_interval_must_have_start_before_end() -> None:
    with pytest.raises(ValueError, match="区间非法"):
        merge([(_h(12), _h(9))])
    with pytest.raises(ValueError, match="区间非法"):
        subtract([(_h(12), _h(9))], [])


def test_property_effective_not_exceeds_work() -> None:
    """基于性质：有效时长不超过工作区间总时长。"""
    cases = [
        ([(_h(9), _h(18))], [(_h(12), _h(13))]),
        ([(_h(9), _h(21))], [(_h(12), _h(13)), (_h(18), _h(19))]),
        ([(_h(20), _h(32))], [(_h(23.5), _h(24.5))]),
        ([(_h(0), _h(24))], [(_h(6), _h(8)), (_h(12), _h(14)), (_h(22), _h(23))]),
    ]
    for work, breaks in cases:
        eff = subtract(work, breaks)
        assert total_seconds(eff) <= total_seconds(merge(work)), f"{work} - {breaks}"
        # 输出区间不重叠且有序
        merged = merge(eff)
        assert eff == merged
        for s, e in eff:
            assert s < e


def test_property_breaks_outside_work_not_deducted() -> None:
    """基于性质：完全越界的休息不减少有效时长。"""
    work = [(_h(9), _h(18))]
    breaks = [(_h(0), _h(8)), (_h(19), _h(24))]
    assert total_seconds(subtract(work, breaks)) == total_seconds(work)
