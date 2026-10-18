"""字段引用提取与依赖图环检测（供 publish_check 使用，不再用正则）。"""

from __future__ import annotations

from titanloom.forms.domain.expr.parser import referenced_fields


def extract_refs(expr: str) -> list[str]:
    """解析表达式，返回其中引用的字段编码（不含 $，去重、保序）。"""
    refs = referenced_fields(expr)
    seen: set[str] = set()
    result: list[str] = []
    for ref in refs:
        if ref not in seen:
            seen.add(ref)
            result.append(ref)
    return result


def has_cycle(deps: dict[str, set[str]]) -> bool:
    """deps: 字段 -> 它引用的字段集合。判断依赖图是否存在环（FW11）。"""

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {}

    def dfs(node: str) -> bool:
        color[node] = GRAY
        for nxt in deps.get(node, ()):
            state = color.get(nxt, WHITE)
            if state == GRAY:
                return True
            if state == WHITE and dfs(nxt):
                return True
        color[node] = BLACK
        return False

    return any(color.get(start, WHITE) == WHITE and dfs(start) for start in deps)
