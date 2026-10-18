"""业务参数读取（后台治理 7.5；ADR-022）。

参数在各模块 manifest.yaml 登记（默认值、范围、层级），代码只用生成的键常量读取，不写死数值。
值的层级：平台 → 部门（按看的人所在部门取）。正式的取值来源（配置服务、变更事件刷新）由 admin / facilities 在 M1 接上；
在那之前 ParamStore 只有登记的默认值，测试可用 override。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from titanloom.kernel.reg.manifest import PARAMS


class UnknownParam(KeyError):
    pass


class ParamStore:
    def __init__(self, values: Mapping[tuple[str, str | None], Any] | None = None):
        self._values: dict[tuple[str, str | None], Any] = dict(values or {})

    def get(self, key: str, dept: str | None = None) -> Any:
        if key not in PARAMS:
            raise UnknownParam(key)
        if dept is not None and (key, dept) in self._values:
            return self._values[(key, dept)]
        if (key, None) in self._values:
            return self._values[(key, None)]
        return PARAMS[key]["default"]

    def override(self, key: str, value: Any, dept: str | None = None) -> None:
        """测试与引导用。正式修改走平台管理 › 业务参数（有版本、审批、审计）。"""
        if key not in PARAMS:
            raise UnknownParam(key)
        self._values[(key, dept)] = value
