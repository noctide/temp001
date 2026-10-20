"""依赖图环检测（供 publish_check 使用，引用列表来自 parser.referenced_fields）。"""

from __future__ import annotations


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
