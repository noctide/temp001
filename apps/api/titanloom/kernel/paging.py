"""游标分页（工程规范 4.3；总图 6）：按（排序键, id）稳定排序，禁止无界查询。"""

from __future__ import annotations

import base64
import json
from typing import Any

from pydantic import BaseModel

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


class Page[T](BaseModel):
    items: list[T]
    next_cursor: str | None = None


def clamp_limit(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_LIMIT
    return max(1, min(int(limit), MAX_LIMIT))


def encode_cursor(sort_key: Any, row_id: str) -> str:
    raw = json.dumps([sort_key, row_id], ensure_ascii=False, separators=(",", ":"), default=str)
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[Any, str]:
    pad = "=" * (-len(cursor) % 4)
    try:
        sort_key, row_id = json.loads(base64.urlsafe_b64decode(cursor + pad))
    except (ValueError, TypeError) as e:
        raise ValueError("游标无效") from e
    if not isinstance(row_id, str):
        raise ValueError("游标无效")
    return sort_key, row_id
