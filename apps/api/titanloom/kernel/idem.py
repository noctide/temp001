"""幂等（能力契约 7；总图 11"幂等"）：同（主体, 能力, 键）去重；同键不同载荷 → 409。

请求摘要用规范化 JSON 的 SHA-256；记录表在 execution 模块（idempotency_record），这里只给摘要与键校验。
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

KEY_RE = re.compile(r"^[A-Za-z0-9_\-:.]{8,128}$")


def valid_key(key: str) -> bool:
    return bool(KEY_RE.match(key))


def canonical(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def request_digest(payload: Any) -> str:
    """契约里的 requestDigest：sha256:<hex>。"""
    return "sha256:" + hashlib.sha256(canonical(payload)).hexdigest()
