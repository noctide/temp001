"""区间运算（秒级整数，半开 [start, end)）：纯函数，不读库、不读时钟。

- merge：有序合并（重叠与相邻边界合并，同一秒不重复计）
- intersect：两段区间列表的交集
- subtract：工作区间并集 − 休息区间并集，只扣与工作相交的部分（重叠/越界休息不重复扣）
- total_seconds：区间列表总时长

用于子方案 10 区间计算与后端详细设计·考勤 4。
"""

from __future__ import annotations

Interval = tuple[int, int]


def _normalize(intervals: list[Interval]) -> list[Interval]:
    out: list[Interval] = []
    for start, end in intervals:
        if start >= end:
            raise ValueError("区间非法：start 必须小于 end")
        out.append((start, end))
    return sorted(out, key=lambda iv: (iv[0], iv[1]))


def merge(intervals: list[Interval]) -> list[Interval]:
    """把重叠或相邻的区间合并，输出有序、互不重叠、半开。"""
    src = _normalize(intervals)
    merged: list[Interval] = []
    for start, end in src:
        if merged and start <= merged[-1][1]:
            prev_start, prev_end = merged[-1]
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    return merged


def intersect(a: list[Interval], b: list[Interval]) -> list[Interval]:
    """两段已归并区间列表的交集。"""
    aa = merge(a)
    bb = merge(b)
    i = j = 0
    out: list[Interval] = []
    while i < len(aa) and j < len(bb):
        as_, ae = aa[i]
        bs, be = bb[j]
        lo = max(as_, bs)
        hi = min(ae, be)
        if lo < hi:
            out.append((lo, hi))
        if ae <= be:
            i += 1
        else:
            j += 1
    return out


def subtract(work: list[Interval], breaks: list[Interval]) -> list[Interval]:
    """有效 = 工作并集 − 休息并集；只扣与工作相交的部分，不重复扣重叠/越界休息。"""
    w = merge(work)
    b = merge(breaks)
    out: list[Interval] = []
    j = 0
    for ws, we in w:
        cur = ws
        while j < len(b) and b[j][1] <= ws:
            j += 1
        k = j
        while k < len(b) and cur < we:
            bs, be = b[k]
            if bs >= we:
                break
            if bs > cur:
                out.append((cur, min(bs, we)))
            cur = max(cur, be)
            if cur >= we:
                break
            k += 1
        if cur < we:
            out.append((cur, we))
    return out


def total_seconds(intervals: list[Interval]) -> int:
    return sum(end - start for start, end in intervals)
