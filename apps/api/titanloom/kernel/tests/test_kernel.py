"""公共内核的单元测试。"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from titanloom.kernel import clock, context, exact, idem, ids, log, paging
from titanloom.kernel.errors import AppError, error_response
from titanloom.kernel.reg.errors import ERRORS, ErrorCode


def test_uuid7_version_order_and_time(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ids, "_last_ms", 0)  # 别的测试用真实时间生成过 id，会把单调下限抬到现在
    a = ids.uuid7(1_700_000_000_000)
    b = ids.uuid7(1_700_000_000_000)
    c = ids.uuid7(1_700_000_000_001)
    assert a.version == 7 and a.variant == uuid.RFC_4122
    assert a < b < c  # 同一毫秒内也单调递增
    assert ids.uuid7_ms(c) == 1_700_000_000_001


def test_short_code() -> None:
    assert ids.short_code("AU", 13) == "AU-0013"
    with pytest.raises(ValueError, match="短编号不合规"):
        ids.short_code("au", 1)


def test_clock_and_business_date() -> None:
    fc = clock.FixedClock(datetime(2026, 10, 2, 17, 30, tzinfo=UTC))
    assert clock.to_iso(fc.now()) == "2026-10-02T17:30:00Z"
    # 北京时间已经是 10-03 凌晨：考勤归属日按业务时区算
    assert clock.business_date(fc.now(), "Asia/Shanghai") == date(2026, 10, 3)
    fc.advance(hours=1)
    assert fc.now().hour == 18
    with pytest.raises(ValueError, match="时区"):
        clock.ensure_utc(datetime(2026, 1, 1))  # noqa: DTZ001 — 故意不带时区


def test_paging_cursor_roundtrip_and_limit() -> None:
    cur = paging.encode_cursor("2026-10-03T01:00:00Z", "abc")
    assert paging.decode_cursor(cur) == ("2026-10-03T01:00:00Z", "abc")
    assert paging.clamp_limit(None) == paging.DEFAULT_LIMIT
    assert paging.clamp_limit(10_000) == paging.MAX_LIMIT
    with pytest.raises(ValueError, match="游标无效"):
        paging.decode_cursor("!!!")


def test_exact_numbers() -> None:
    assert exact.dec("8.50") == Decimal("8.50")
    with pytest.raises(TypeError):
        exact.dec(8.5)  # pyright: ignore[reportArgumentType]
    with pytest.raises(ValueError, match="规范"):
        exact.parse_text("1e3")
    assert exact.encode(Decimal("1E+3")) == "1000"
    assert exact.quantize(Decimal("7.125")) == Decimal("7.13")


def test_idempotency_digest_is_order_independent() -> None:
    assert idem.request_digest({"a": 1, "b": [1, 2]}) == idem.request_digest({"b": [1, 2], "a": 1})
    assert idem.request_digest({"a": 1}).startswith("sha256:")
    assert idem.valid_key("k-0123456789") and not idem.valid_key("short")


def test_error_body_matches_registry() -> None:
    err = AppError(ErrorCode.RESOURCE_VERSION_CONFLICT, details={"currentRevision": 3})
    body = error_response(err, "req_1", show_details=False).model_dump(by_alias=True, exclude_none=True)
    meta = ERRORS[ErrorCode.RESOURCE_VERSION_CONFLICT]
    assert body["error"]["messageKey"] == meta.message_key
    assert body["error"]["retryable"] is meta.retryable
    assert "details" not in body["error"]  # 没有开发者资格看不到 details
    shown = error_response(err, "req_1", show_details=True).model_dump(by_alias=True)
    assert shown["error"]["details"] == {"currentRevision": 3}


def test_log_is_json_with_request_id_and_redacts_secrets(capsys: pytest.CaptureFixture[str]) -> None:
    log.setup()
    token = context.bind(context.RequestContext(request_id="req_x"))
    try:
        log.get_logger("t").info(
            "登录", extra={"fields": {"user": "林晓", "password": "p@ss", "nested": {"apiKey": "k"}}}
        )
    finally:
        context.reset(token)
    line = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert line["requestId"] == "req_x"
    assert line["password"] == log.MASK and line["nested"]["apiKey"] == log.MASK
    assert line["user"] == "林晓"
    logging.getLogger("titanloom").handlers.clear()
