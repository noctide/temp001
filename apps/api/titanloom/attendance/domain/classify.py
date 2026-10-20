"""分类引擎（纯函数，不读库、不读时钟）。

子方案 10：有效区间 E 与正常区间 N 求交得正常时长；E − N 的其余部分按
日期属性归入互斥加班类别（工作日/休息日/节假日加班），同一秒只进一类。

所有策略输入（日期属性、正常区间）由调用方传入；本函数不猜默认值，
不碰数据库、时钟或配置服务（子方案第 23 条第 2 项：不得暗中猜定）。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .interval import Interval, intersect, subtract, total_seconds


class DayKind(StrEnum):
    WORKDAY = "workday"
    RESTDAY = "restday"
    HOLIDAY = "holiday"


@dataclass(frozen=True)
class Classified:
    normal_seconds: int
    overtime_workday: int
    overtime_restday: int
    overtime_holiday: int

    @property
    def total_overtime(self) -> int:
        return self.overtime_workday + self.overtime_restday + self.overtime_holiday


def classify(effective: list[Interval], normal: list[Interval], day_kind: DayKind) -> Classified:
    """把有效区间切成“正常”与“加班”，加班再按日期属性归类。"""
    normal_seconds = total_seconds(intersect(effective, normal))
    rest = subtract(effective, normal)
    rest_seconds = total_seconds(rest)

    overtime_workday = overtime_restday = overtime_holiday = 0
    if day_kind == DayKind.WORKDAY:
        overtime_workday = rest_seconds
    elif day_kind == DayKind.RESTDAY:
        overtime_restday = rest_seconds
    elif day_kind == DayKind.HOLIDAY:
        overtime_holiday = rest_seconds
    else:  # pragma: no cover - DayKind 是封闭枚举，做防御性校验
        raise ValueError(f"未知日期属性：{day_kind}")

    return Classified(
        normal_seconds=normal_seconds,
        overtime_workday=overtime_workday,
        overtime_restday=overtime_restday,
        overtime_holiday=overtime_holiday,
    )
