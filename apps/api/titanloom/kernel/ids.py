"""编号（总图 6；ADR-026）：内部 UUIDv7（应用侧生成、永不改变、不给人看）+ 给人看的短编号。"""

from __future__ import annotations

import os
import re
import threading
import time
import uuid

_lock = threading.Lock()
_last_ms = 0
_seq = 0


def uuid7(now_ms: int | None = None) -> uuid.UUID:
    """RFC 9562 UUIDv7：48 位毫秒时间 + 12 位单调序号 + 62 位随机。同一毫秒内单调递增。"""
    global _last_ms, _seq
    with _lock:
        ms = now_ms if now_ms is not None else time.time_ns() // 1_000_000
        if ms <= _last_ms:
            ms = _last_ms
            _seq = (_seq + 1) & 0xFFF
            if _seq == 0:  # 同一毫秒序号用完：借下一毫秒
                ms += 1
        else:
            _seq = int.from_bytes(os.urandom(2), "big") & 0x3FF  # 留出递增空间
        _last_ms = ms
        rand = int.from_bytes(os.urandom(8), "big") & ((1 << 62) - 1)
        value = (ms & ((1 << 48) - 1)) << 80 | 0x7 << 76 | _seq << 64 | 0b10 << 62 | rand
        return uuid.UUID(int=value)


def uuid7_ms(u: uuid.UUID) -> int:
    """取出 UUIDv7 里的毫秒时间（排查用）。"""
    return u.int >> 80


CODE_RE = re.compile(r"^[A-Z]{2,6}-[0-9]{3,8}$")


def short_code(prefix: str, seq: int, width: int = 4) -> str:
    """给人看的短编号，如 AU-0013（契约 record-common.code）。编码规则可改，不影响内部关联。"""
    code = f"{prefix}-{seq:0{width}d}"
    if not CODE_RE.match(code):
        raise ValueError(f"短编号不合规：{code}")
    return code
