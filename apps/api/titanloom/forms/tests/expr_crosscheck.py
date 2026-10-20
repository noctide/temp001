"""前后端对拍用例生成器：固定种子生成只含 + − × ÷ round sum 的嵌套算式，后端算出期望值。

生成物 `apps/web/src/domains/forms/expr.crosscheck.json` 由前端测试读取比对。
改了求值器后重新生成：

    uv run python -m titanloom.forms.tests.expr_crosscheck
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import TypedDict, cast

from titanloom.forms.domain.expr import (
    ExprError,
    Value,
    ValueKind,
    evaluate,
    format_number,
    parse_field_value,
)

ROOT = Path(__file__).resolve().parents[5]
FIXTURE_PATH = ROOT / "apps" / "web" / "src" / "domains" / "forms" / "expr.crosscheck.json"

SEED = 20261020
CASE_COUNT = 320
FIELD_CODES = ("a", "b", "c", "d")


class FieldCase(TypedDict):
    type: str
    value: str


class Expect(TypedDict):
    type: str
    value: str


class CrossCase(TypedDict):
    id: str
    expr: str
    fields: dict[str, FieldCase]
    expect: Expect


class Fixture(TypedDict):
    note: str
    seed: int
    count: int
    cases: list[CrossCase]


class _Rng:
    """固定种子线性同余（只用于生成对拍算式，不作安全用途）。"""

    def __init__(self, seed: int) -> None:
        self._state = seed & 0xFFFFFFFFFFFFFFFF

    def _next(self) -> int:
        self._state = (self._state * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
        return self._state >> 11

    def below(self, n: int) -> int:
        return self._next() % n

    def between(self, lo: int, hi: int) -> int:
        return lo + self.below(hi - lo + 1)

    def pick(self, items: tuple[str, ...]) -> str:
        return items[self.below(len(items))]

    def chance(self, numerator: int, denominator: int) -> bool:
        return self.below(denominator) < numerator


def _number_text(rng: _Rng, *, allow_negative: bool) -> str:
    integer = rng.between(0, 9999)
    if rng.chance(3, 5):
        frac = "".join(str(rng.below(10)) for _ in range(rng.between(1, 4)))
        text = f"{integer}.{frac}"
    else:
        text = str(integer)
    if allow_negative and rng.chance(1, 3) and text != "0":
        text = "-" + text
    return text


def _expr(rng: _Rng, depth: int) -> str:
    if depth <= 0:
        if rng.chance(1, 2):
            return "$" + rng.pick(FIELD_CODES)
        return _number_text(rng, allow_negative=False)
    if rng.chance(1, 10):
        return f"({_expr(rng, depth - 1)})"  # 嵌套括号
    if rng.chance(1, 8):
        count = rng.between(2, 3)
        return "sum(" + ", ".join(_expr(rng, depth - 1) for _ in range(count)) + ")"
    if rng.chance(1, 6):
        return f"round({_expr(rng, depth - 1)}, {rng.between(0, 3)})"
    op = rng.pick(("+", "-", "*", "/"))
    return f"({_expr(rng, depth - 1)} {op} {_expr(rng, depth - 1)})"


def build_fixture() -> Fixture:
    rng = _Rng(SEED)
    cases: list[CrossCase] = []
    while len(cases) < CASE_COUNT:
        fields: dict[str, FieldCase] = {
            code: FieldCase(type="number", value=_number_text(rng, allow_negative=True)) for code in FIELD_CODES
        }
        expr = _expr(rng, rng.between(2, 4))
        values: dict[str, Value] = {
            code: parse_field_value(info["type"], info["value"]) for code, info in fields.items()
        }
        try:
            result = evaluate(expr, values)
        except ExprError as exc:
            if exc.code == "DIVIDE_BY_ZERO":
                continue  # 换一组，保证每个对拍用例都能算出结果
            raise
        if result.kind != ValueKind.NUMBER:
            raise AssertionError(f"对拍用例只生成数值算式：{expr}")
        cases.append(
            CrossCase(
                id=f"x{len(cases) + 1:03d}",
                expr=expr,
                fields=fields,
                expect=Expect(type="number", value=format_number(cast(Decimal, result.value))),
            )
        )
    return Fixture(
        note=(
            "前后端对拍用例（固定种子，后端求值器生成期望值）。不要手改；"
            "重新生成：uv run python -m titanloom.forms.tests.expr_crosscheck"
        ),
        seed=SEED,
        count=len(cases),
        cases=cases,
    )


def write_fixture() -> Path:
    FIXTURE_PATH.write_text(
        json.dumps(build_fixture(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return FIXTURE_PATH


if __name__ == "__main__":
    print(write_fixture())
