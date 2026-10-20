"""词法分析器：把表达式字符串切成 Token。"""

from __future__ import annotations

import re
from dataclasses import dataclass

from titanloom.forms.domain.expr.errors import ExprError

NUMBER = "NUMBER"
FIELD_REF = "FIELD_REF"
IDENT = "IDENT"
LPAREN = "LPAREN"
RPAREN = "RPAREN"
COMMA = "COMMA"
PLUS = "PLUS"
MINUS = "MINUS"
STAR = "STAR"
SLASH = "SLASH"
EQ = "EQ"
NE = "NE"
LTE = "LTE"
GTE = "GTE"
LT = "LT"
GT = "GT"
EOF = "EOF"

_TOKEN_SPEC: list[tuple[str, re.Pattern[str]]] = [
    (NE, re.compile(r"!=")),
    (LTE, re.compile(r"<=")),
    (GTE, re.compile(r">=")),
    (EQ, re.compile(r"=")),
    (LT, re.compile(r"<")),
    (GT, re.compile(r">")),
    (NUMBER, re.compile(r"\d+(?:\.\d+)?")),
    (FIELD_REF, re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*")),
    (IDENT, re.compile(r"[A-Za-z_][A-Za-z0-9_]*")),
    (LPAREN, re.compile(r"\(")),
    (RPAREN, re.compile(r"\)")),
    (COMMA, re.compile(r",")),
    (PLUS, re.compile(r"\+")),
    (MINUS, re.compile(r"-")),
    (STAR, re.compile(r"\*")),
    (SLASH, re.compile(r"/")),
]

_WS = re.compile(r"\s+")


@dataclass(frozen=True)
class Token:
    type: str
    value: str
    pos: int


def tokenize(text: str) -> list[Token]:
    tokens: list[Token] = []
    pos = 0
    while pos < len(text):
        m = _WS.match(text, pos)
        if m:
            pos = m.end()
            continue
        for token_type, pattern in _TOKEN_SPEC:
            m = pattern.match(text, pos)
            if m:
                tokens.append(Token(token_type, m.group(0), pos))
                pos = m.end()
                break
        else:
            raise ExprError("SYNTAX", f"非法字符：{text[pos]!r} (位置 {pos})")
    tokens.append(Token(EOF, "", len(text)))
    return tokens
