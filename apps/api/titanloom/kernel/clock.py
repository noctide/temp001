"""时间（总框架 8.7；工程规范 4.1）：只用带时区的时间，绝对时间存 UTC，业务日期按业务时区算。

领域层不直接读时钟：由 app 层拿 Clock.now() 传进去，测试用 FixedClock。
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FixedClock:
    """测试用：固定时间，可前进。"""

    def __init__(self, at: datetime):
        if at.tzinfo is None:
            raise ValueError("FixedClock 需要带时区的时间")
        self._at = at.astimezone(UTC)

    def now(self) -> datetime:
        return self._at

    def advance(self, **kw: float) -> None:
        self._at += timedelta(**kw)


def ensure_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        raise ValueError("不接受没有时区的时间")
    return ts.astimezone(UTC)


def business_date(ts: datetime, tz: str) -> date:
    """某一时刻在业务时区里是哪一天（考勤归属日等）；显示时区变化不影响它。"""
    return ensure_utc(ts).astimezone(ZoneInfo(tz)).date()


def to_iso(ts: datetime) -> str:
    """对外的时间一律 ISO 8601 UTC，以 Z 结尾（契约 record-common）。"""
    return ensure_utc(ts).isoformat().replace("+00:00", "Z")
