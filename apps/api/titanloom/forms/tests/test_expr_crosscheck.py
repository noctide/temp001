"""阶段 2 再返工：前后端对拍用例文件必须由后端求值器生成、且与当前实现一致。

前端 `expr.crosscheck.test.ts` 读同一文件比对；改了求值器后重新生成：
    uv run python -m titanloom.forms.tests.expr_crosscheck
"""

from __future__ import annotations

import json

from titanloom.forms.tests.expr_crosscheck import CASE_COUNT, FIXTURE_PATH, build_fixture


def test_crosscheck_fixture_matches_backend() -> None:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert fixture == build_fixture()


def test_crosscheck_fixture_has_enough_cases() -> None:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert fixture["count"] >= 300
    assert len(fixture["cases"]) == fixture["count"] == CASE_COUNT
