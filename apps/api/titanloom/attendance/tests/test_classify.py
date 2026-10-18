"""分类引擎测试（纯函数，不读库、不读时钟，所有策略输入由调用方传入）。

子方案 10：有效区间 E 与正常区间 N 求交得正常时长，其余按日期属性
（工作日/休息日/节假日）归入互斥加班类别；同一秒只进一类。
"""

from __future__ import annotations

import random

import pytest

from titanloom.attendance.domain.classify import (
    DayKind,
    classify,
)
from titanloom.attendance.domain.interval import Interval, merge, subtract, total_seconds

H = 3600


def _h(hours: float) -> int:
    return int(hours * H)


def test_classify_normal_only_workday() -> None:
    """正常区间内，工作日 -> 全部正常，无加班。"""
    effective = [(_h(9), _h(12)), (_h(13), _h(18))]  # 已扣休息
    normal = [(_h(9), _h(12)), (_h(13), _h(18))]
    c = classify(effective, normal, DayKind.WORKDAY)
    assert c.normal_seconds == 8 * H
    assert c.overtime_workday == 0
    assert c.overtime_restday == 0
    assert c.overtime_holiday == 0


def test_classify_overtime_workday() -> None:
    """超出正常区间的部分，工作日归工作日加班。"""
    effective = [(_h(9), _h(12)), (_h(13), _h(18)), (_h(18), _h(21))]
    normal = [(_h(9), _h(12)), (_h(13), _h(18))]
    c = classify(effective, normal, DayKind.WORKDAY)
    assert c.normal_seconds == 8 * H
    assert c.overtime_workday == 3 * H
    assert c.overtime_restday == 0
    assert c.overtime_holiday == 0


def test_classify_overtime_restday() -> None:
    effective = [(_h(9), _h(17))]
    normal = [(_h(9), _h(12)), (_h(13), _h(17))]
    c = classify(effective, normal, DayKind.RESTDAY)
    assert c.normal_seconds == 7 * H
    assert c.overtime_restday == 1 * H
    assert c.overtime_workday == 0
    assert c.overtime_holiday == 0


def test_classify_overtime_holiday() -> None:
    effective = [(_h(9), _h(17))]
    normal = [(_h(9), _h(12)), (_h(13), _h(17))]
    c = classify(effective, normal, DayKind.HOLIDAY)
    assert c.normal_seconds == 7 * H
    assert c.overtime_holiday == 1 * H
    assert c.overtime_workday == 0
    assert c.overtime_restday == 0


def test_classify_one_second_only_one_category() -> None:
    """同一秒只进一类：正常 + 各类加班合计 = 有效总时长，且互不重叠。"""
    effective = [(_h(9), _h(21))]
    normal = [(_h(9), _h(12)), (_h(13), _h(18))]
    c = classify(effective, normal, DayKind.WORKDAY)
    assert c.normal_seconds + c.overtime_workday == total_effective(effective)
    # 验证互斥：把各段时长加起来不重复
    assert c.normal_seconds == 8 * H
    assert c.overtime_workday == 4 * H


def test_classify_unknown_day_kind_rejected() -> None:
    with pytest.raises(ValueError, match="未知日期属性"):
        classify([], [], "weekend")  # type: ignore[arg-type]


def test_classify_empty() -> None:
    c = classify([], [], DayKind.WORKDAY)
    assert c.normal_seconds == 0
    assert c.overtime_workday == 0
    assert c.overtime_restday == 0
    assert c.overtime_holiday == 0


def test_classify_property_random() -> None:
    """基于性质：随机区间下，正常 + 三类加班 = 有效时长；各类 ≥ 0；有效 ≤ 工作总长；互斥。"""
    rng = random.Random(20261018)  # noqa: S311 — 固定种子，仅用于属性测试，非加密场景
    for _ in range(500):
        # 随机工作区间（1-5 段）
        work: list[Interval] = []
        for _ in range(rng.randint(1, 5)):
            s = rng.randint(0, 48 * H - 1)
            e = s + rng.randint(1, 2 * H)
            work.append((s, e))
        work = merge(work)

        # 随机休息区间（0-5 段）
        breaks: list[Interval] = []
        for _ in range(rng.randint(0, 5)):
            s = rng.randint(0, 48 * H - 1)
            e = s + rng.randint(1, 2 * H)
            breaks.append((s, e))

        effective = subtract(work, breaks)

        # 随机正常区间（0-5 段）
        normal: list[Interval] = []
        for _ in range(rng.randint(0, 5)):
            s = rng.randint(0, 48 * H - 1)
            e = s + rng.randint(1, 2 * H)
            normal.append((s, e))
        normal = merge(normal)

        day_kind = rng.choice(list(DayKind))
        c = classify(effective, normal, day_kind)

        eff_total = total_seconds(effective)
        assert c.normal_seconds >= 0, f"work={work} breaks={breaks} normal={normal} day={day_kind}"
        assert c.overtime_workday >= 0
        assert c.overtime_restday >= 0
        assert c.overtime_holiday >= 0
        # 正常 + 三类加班 = 有效时长（同一秒只进一类，互斥）
        assert c.normal_seconds + c.total_overtime == eff_total, (
            f"work={work} breaks={breaks} normal={normal} day={day_kind}"
        )
        # 有效时长 ≤ 工作区间总长
        assert eff_total <= total_seconds(work), f"work={work} breaks={breaks}"


def total_effective(intervals: list[tuple[int, int]]) -> int:
    return sum(e - s for s, e in intervals)
