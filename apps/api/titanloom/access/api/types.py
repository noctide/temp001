"""access.api 的数据类型（契约 access-decision、access-filter；身份与权限 5、6、10）。

全部冻结。`to_contract()` 输出契约里的 camelCase 结构，字段缺省就不出现，可直接用 JSON Schema 校验。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal

from titanloom.kernel.clock import to_iso
from titanloom.kernel.errors import AppError
from titanloom.kernel.reg.errors import ErrorCode

Step = Literal["identity", "feature", "grant", "agent_gate", "data_scope", "state"]
StepOutcome = Literal["pass", "fail", "not_checked", "not_applicable"]
Impact = Literal["low", "medium", "high"]

STEPS: tuple[Step, ...] = ("identity", "feature", "grant", "agent_gate", "data_scope", "state")

# 第 1 关（身份）不过时，按原因文案键换成各自的错误码；认不出的按“需要登录”处理
IDENTITY_REASONS: dict[str, ErrorCode] = {
    "access.identity.authRequired": ErrorCode.AUTHENTICATION_REQUIRED,
    "access.identity.tokenExpired": ErrorCode.TOKEN_EXPIRED,
    "access.identity.accountLocked": ErrorCode.ACCOUNT_LOCKED,
    "access.identity.delegationRevoked": ErrorCode.DELEGATION_REVOKED,
}


@dataclass(frozen=True, slots=True)
class DeptRef:
    id: str
    name: str
    is_primary: bool = False


@dataclass(frozen=True, slots=True)
class Whoami:
    """当前主体。departments 含兼岗；acting_for 有值表示管家代办（值 = 被代办本人的账户）。"""

    account_id: str
    person_id: str | None
    name: str
    kind: Literal["human", "service", "emergency"]
    departments: tuple[DeptRef, ...]
    policy_rev: int
    acting_for: str | None = None


@dataclass(frozen=True, slots=True)
class Target:
    """判定的对象及其真实归属。没有对象（只问“有没有这项能力”）时传 None。"""

    object_type: str | None = None
    object_id: str | None = None
    dept_id: str | None = None
    project_id: str | None = None
    owner_person_id: str | None = None


@dataclass(frozen=True, slots=True)
class StepResult:
    step: Step
    result: StepOutcome
    reason_key: str | None = None
    reason_params: Mapping[str, Any] = field(default_factory=lambda: {})
    grant_refs: tuple[str, ...] = ()

    def to_contract(self) -> dict[str, Any]:
        out: dict[str, Any] = {"step": self.step, "result": self.result}
        if self.reason_key:
            out["reasonKey"] = self.reason_key
        if self.reason_params:
            out["reasonParams"] = dict(self.reason_params)
        if self.grant_refs:
            out["grantRefs"] = list(self.grant_refs)
        return out


@dataclass(frozen=True, slots=True)
class Decision:
    """能不能（契约 access-decision）。拒绝时 failed_step 与 reason_key 必有。"""

    allowed: bool
    policy_rev: int
    decided_at: datetime
    failed_step: Step | None = None
    reason_key: str | None = None
    reason_params: Mapping[str, Any] = field(default_factory=lambda: {})
    contact_ref: str | None = None
    can_request: bool | None = None
    matched_grant_refs: tuple[str, ...] = ()
    constraints: Mapping[str, Any] = field(default_factory=lambda: {})
    steps: tuple[StepResult, ...] = ()

    def __post_init__(self) -> None:
        if self.allowed and (self.failed_step is not None or self.can_request is not None):
            raise ValueError("允许的结果不能带 failed_step / can_request")
        if not self.allowed and (self.failed_step is None or not self.reason_key):
            raise ValueError("拒绝的结果必须有 failed_step 和 reason_key")

    def require(self) -> None:
        """不允许就抛 AppError。details 只放卡在哪一关和原因文案键：看不到的对象，名称与数量不出现（身份与权限 5）。"""
        if self.allowed:
            return
        details: dict[str, Any] = {"failedStep": self.failed_step, "reasonKey": self.reason_key}
        if self.failed_step == "identity":
            code = IDENTITY_REASONS.get(self.reason_key or "", ErrorCode.AUTHENTICATION_REQUIRED)
        elif self.failed_step == "feature":
            code = ErrorCode.FEATURE_NOT_OPEN
        else:
            code = ErrorCode.ACCESS_DENIED
        raise AppError(code, details=details)

    def to_contract(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "decision": "allow" if self.allowed else "deny",
            "policyRev": self.policy_rev,
            "decidedAt": to_iso(self.decided_at),
        }
        if self.failed_step:
            out["failedStep"] = self.failed_step
        if self.reason_key:
            out["reasonKey"] = self.reason_key
        if self.reason_params:
            out["reasonParams"] = dict(self.reason_params)
        if self.contact_ref:
            out["contactRef"] = self.contact_ref
        if self.can_request is not None:
            out["canRequest"] = self.can_request
        if self.matched_grant_refs:
            out["matchedGrantRefs"] = list(self.matched_grant_refs)
        if self.constraints:
            out["constraints"] = dict(self.constraints)
        if self.steps:
            out["steps"] = [s.to_contract() for s in self.steps]
        return out


@dataclass(frozen=True, slots=True)
class Predicate:
    """field 必须是调用模块登记的权限字段（身份与权限 6、12）。eq 只有一个值。"""

    field: str
    op: Literal["in", "eq"]
    values: tuple[Any, ...]

    def __post_init__(self) -> None:
        if not self.values:
            raise ValueError("谓词至少要有一个值")
        if self.op == "eq" and len(self.values) != 1:
            raise ValueError("eq 只能有一个值")

    def matches(self, row: Mapping[str, Any]) -> bool:
        v = row[self.field]
        return v == self.values[0] if self.op == "eq" else v in self.values

    def to_contract(self) -> dict[str, Any]:
        return {"field": self.field, "op": self.op, "values": list(self.values)}


@dataclass(frozen=True, slots=True)
class AccessFilter:
    """能看哪些（契约 access-filter）：all / none / 允许条件之并，再减去拒绝条件之并（all 也可带 not），附须遮挡的列。

    “本人部门（含下级）”这类条件在 filter 这一步就展开成部门编号列表，调用方不用再去查组织树。
    """

    policy_rev: int
    all: bool = False
    none: bool = False
    any: tuple[Predicate, ...] = ()
    not_: tuple[Predicate, ...] = ()
    mask_columns: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (self.all, self.none, bool(self.any)).count(True) != 1:
            raise ValueError("all、none、any 必须且只能有一个")
        if self.none and (self.not_ or self.mask_columns):
            raise ValueError("none 不能带 not 和 mask_columns")

    def matches(self, row: Mapping[str, Any]) -> bool:
        """这一行能不能看。纯函数，给模块单测和属性测试用；真实查询走 access.api.sql。"""
        if self.none:
            return False
        if self.all:
            return not any(p.matches(row) for p in self.not_)
        return any(p.matches(row) for p in self.any) and not any(p.matches(row) for p in self.not_)

    def to_contract(self) -> dict[str, Any]:
        out: dict[str, Any] = {"policyRev": self.policy_rev}
        if self.all:
            out["all"] = True
            if self.not_:
                out["not"] = [p.to_contract() for p in self.not_]
        elif self.none:
            out["none"] = True
        else:
            out["any"] = [p.to_contract() for p in self.any]
            if self.not_:
                out["not"] = [p.to_contract() for p in self.not_]
            if self.mask_columns:
                out["maskColumns"] = list(self.mask_columns)
        if self.all and self.mask_columns:
            out["maskColumns"] = list(self.mask_columns)
        return out


@dataclass(frozen=True, slots=True)
class ScopeRef:
    kind: Literal["dept", "project"]
    id: str


@dataclass(frozen=True, slots=True)
class Member:
    """部门 / 项目成员；一律带部门（重名靠部门区分，身份与权限 3）。"""

    person_id: str
    name: str
    dept_id: str
    dept_name: str
    role: str | None = None
    on: date | None = None


@dataclass(frozen=True, slots=True)
class Membership:
    kind: Literal["dept", "project"]
    id: str
    name: str
    role: str | None = None


@dataclass(frozen=True, slots=True)
class CapabilityDecl:
    """模块登记的能力。新能力默认谁都没有（身份与权限 7）。feature_id 非空 = 属于功能开放的“新建 / 发起”类。"""

    id: str
    impact: Impact = "low"
    assignable_to_role: bool = True
    no_cache: bool = False
    feature_id: str | None = None


@dataclass(frozen=True, slots=True)
class FeatureDecl:
    id: str
    name_key: str
    impact: Impact = "low"
    default_tier: Literal["all", "designated", "none"] = "all"
    per_dept: bool = False
