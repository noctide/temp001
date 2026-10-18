"""由 ops/tools/tl.py gen 生成，不要手改；改正本后重新生成（开发项目划分规范 5.5）。"""

from typing import Any

# 业务参数（各模块 manifest.yaml）：键 → 登记内容（默认值、单位、范围、层级…）
PARAMS: dict[str, dict[str, Any]] = {}

# 功能开放（各模块 manifest.yaml）
FEATURES: dict[str, dict[str, Any]] = {}

class P:
    pass


class F:
    pass
