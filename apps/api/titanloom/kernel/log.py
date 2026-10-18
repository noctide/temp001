"""结构化日志（工程规范 4.1"日志"）：一行一个 JSON，带 requestId / jobId / pluginId；凭据类字段自动打码。"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from titanloom.kernel import context

SECRET_WORDS = ("password", "passwd", "secret", "token", "authorization", "cookie", "apikey", "api_key", "credential")
MASK = "***"


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():  # pyright: ignore[reportUnknownVariableType]
            key = str(k)  # pyright: ignore[reportUnknownArgumentType]
            out[key] = MASK if any(w in key.lower() for w in SECRET_WORDS) else redact(v)
        return out
    if isinstance(value, list | tuple):
        return [redact(v) for v in value]  # pyright: ignore[reportUnknownVariableType]
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat().replace("+00:00", "Z"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": record.getMessage(),
        }
        c = context.peek()
        if c is not None:
            for name, v in (("requestId", c.request_id), ("jobId", c.job_id), ("pluginId", c.plugin_id)):
                if v:
                    data[name] = v
        extra = getattr(record, "fields", None)
        if isinstance(extra, dict):
            data.update(redact(extra))  # pyright: ignore[reportUnknownArgumentType]
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False, default=str)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"titanloom.{name}")


def setup(level: int = logging.INFO) -> None:
    h = logging.StreamHandler()
    h.setFormatter(JsonFormatter())
    root = logging.getLogger("titanloom")
    root.handlers[:] = [h]
    root.setLevel(level)
    root.propagate = False
