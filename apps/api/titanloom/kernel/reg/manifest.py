"""由 ops/tools/tl.py gen 生成，不要手改；改正本后重新生成（开发项目划分规范 5.5）。"""

from typing import Any

# 业务参数（各模块 manifest.yaml）：键 → 登记内容（默认值、单位、范围、层级…）
PARAMS: dict[str, dict[str, Any]] = {
    "forms.expr.computeMs": {
        "default": 10,
        "desc": "单次公式求值的时间预算；应用层按它计时，超出按计算失败处理（后端详细设计·表单 4）",
        "key": "forms.expr.computeMs",
        "layers": [
            "platform"
        ],
        "module": "forms",
        "name": "单次公式计算时限",
        "range": [
            1,
            1000
        ],
        "unit": "毫秒"
    },
    "forms.expr.depthLimit": {
        "default": 32,
        "desc": "单条公式语法树的最大嵌套层数；发布前检查与求值共用，超出即拒绝（后端详细设计·表单 4）",
        "key": "forms.expr.depthLimit",
        "layers": [
            "platform"
        ],
        "module": "forms",
        "name": "公式嵌套深度上限",
        "range": [
            1,
            128
        ],
        "unit": "层"
    }
}

# 功能开放（各模块 manifest.yaml）
FEATURES: dict[str, dict[str, Any]] = {}

class P:
    class forms:
        class expr:
            computeMs = "forms.expr.computeMs"
            depthLimit = "forms.expr.depthLimit"


class F:
    pass
