"""契约骨架校验（第九部分）：身份与权限——授权、判定结果、筛选条件、功能开放收紧、权限变化事件。
来源：后端详细设计·身份与权限；总框架 8.5；后台治理 4.3–4.6。运行：python test_contracts_part9.py"""
import json, pathlib, copy, sys
from jsonschema import Draft202012Validator
root = pathlib.Path(__file__).parent
names = ["grant", "access-decision", "access-filter", "feature-layer", "access-policy-changed"]
S = {n: json.loads((root / f"{n}.schema.json").read_text(encoding="utf-8")) for n in names}
for n in S: Draft202012Validator.check_schema(S[n])
def ok(n, d): return not list(Draft202012Validator(S[n]).iter_errors(d))
fails = []
def check(label, cond):
    print(("PASS " if cond else "FAIL ") + label)
    if not cond: fails.append(label)
T = "2026-10-17T01:00:00Z"

# ---- 授权
g = {"grantId": "g1", "subjectKind": "group", "subjectId": "grp-all-dept-leads", "scopeKind": "platform",
     "roleId": "role-dept-lead", "dataCondition": {"kind": "own_dept"}, "effect": "allow",
     "source": "manual", "grantedBy": "p-guyuan", "validFrom": T}
check("授权示例（全体部门负责人 · 本人部门）有效", ok("grant", g))
x = copy.deepcopy(g); x["capabilityId"] = "titanloom.attendance.report.export"
check("角色与单项能力只能二选一", not ok("grant", x))
x = copy.deepcopy(g); del x["roleId"]
check("必须有角色或单项能力", not ok("grant", x))
deny = {"grantId": "g2", "subjectKind": "account", "subjectId": "a-wangkexin", "scopeKind": "resource",
        "resourceRef": "dataproc.dataset:monthly-hours", "capabilityId": "titanloom.dataproc.dataset.export",
        "effect": "deny", "source": "manual", "grantedBy": "p-guyuan", "validFrom": T}
check("显式拒绝（王可欣 · 月度工时汇总 · 导出）有效", ok("grant", deny))
x = copy.deepcopy(deny); del x["capabilityId"]; x["roleId"] = "role-x"
check("拒绝只能针对单项能力，不能拒绝整个角色", not ok("grant", x))
x = copy.deepcopy(deny); del x["resourceRef"]
check("资源范围的授权必须指明资源", not ok("grant", x))
x = copy.deepcopy(g); x["dataCondition"] = {"kind": "expr", "expr": "dept == me.dept"}
check("数据条件不接受自由公式", not ok("grant", x))
x = copy.deepcopy(g); x["dataCondition"] = {"kind": "depts"}
check("指定部门必须列出部门", not ok("grant", x))
x = copy.deepcopy(g); x["dataCondition"] = {"kind": "field_own_dept"}
check("某字段 = 本人部门必须写字段", not ok("grant", x))
x = copy.deepcopy(g); x["source"] = "request"; x["requestRef"] = "req-1"
check("申请批准的授权必须有到期日", not ok("grant", x))
x["validTo"] = "2027-01-15T15:59:59Z"
check("申请批准的授权带到期日有效", ok("grant", x))
x = copy.deepcopy(g); x["subjectKind"] = "agent"
check("管家只能出现在资源准入（三门）行", not ok("grant", x))
x = copy.deepcopy(deny); x["subjectKind"] = "agent"; x["subjectId"] = "agent"; x["effect"] = "allow"
check("三门：资源准入行有效", ok("grant", x))

# ---- 判定结果
d = {"decision": "deny", "policyRev": 32, "decidedAt": T, "failedStep": "grant",
     "reasonKey": "access.reason.notGranted", "contactRef": "person:p-zhaoyiming", "canRequest": True,
     "steps": [{"step": "identity", "result": "pass"}, {"step": "feature", "result": "not_applicable"},
               {"step": "grant", "result": "fail", "reasonKey": "access.reason.notGranted"},
               {"step": "agent_gate", "result": "not_applicable"}, {"step": "data_scope", "result": "not_checked"},
               {"step": "state", "result": "not_checked"}]}
check("判定示例（林晓看质检结果 · 卡在基础授权）有效", ok("access-decision", d))
x = copy.deepcopy(d); del x["failedStep"]
check("拒绝必须写卡在哪一关", not ok("access-decision", x))
x = copy.deepcopy(d); x["reasonKey"] = "没有授权"
check("原因只给文案键", not ok("access-decision", x))
x = copy.deepcopy(d); x["policyDocument"] = {"raw": "..."}
check("不返回策略原文", not ok("access-decision", x))
a = {"decision": "allow", "policyRev": 32, "decidedAt": T, "matchedGrantRefs": ["g1"]}
check("允许示例有效", ok("access-decision", a))
x = copy.deepcopy(a); x["failedStep"] = "grant"
check("允许不得带失败关", not ok("access-decision", x))

# ---- 筛选条件
f = {"policyRev": 32, "any": [{"field": "orgUnitId", "op": "in", "values": ["dept-assembly-1"]}],
     "not": [{"field": "orgUnitId", "op": "eq", "values": ["dept-qc"]}], "maskColumns": ["hourlyWage"]}
check("筛选条件示例（刘畅 · 团队出勤）有效", ok("access-filter", f))
check("不限", ok("access-filter", {"policyRev": 32, "all": True}))
check("一条都不能看", ok("access-filter", {"policyRev": 32, "none": True}))
check("不限与一条都不能看不能同时出现", not ok("access-filter", {"policyRev": 32, "all": True, "none": True}))
x = copy.deepcopy(f); x["sql"] = "org_unit_id in (...)"
check("不返回 SQL 字符串", not ok("access-filter", x))
check("必须是三种之一", not ok("access-filter", {"policyRev": 32}))

# ---- 功能开放收紧
fl = {"scopeKind": "dept", "scopeId": "dept-assembly-1", "featureId": "forms.create", "mode": "only",
      "onlyRoles": ["dept-role-lead"], "reason": "本部门表单统一由负责人建", "changedBy": "p-liuchang", "changedAt": T}
check("部门收紧示例有效", ok("feature-layer", fl))
x = copy.deepcopy(fl); del x["onlyRoles"]
check("只给…必须列出角色", not ok("feature-layer", x))
x = copy.deepcopy(fl); x["mode"] = "open_more"
check("只有 跟平台 / 只给 / 关掉 三种，不能往松", not ok("feature-layer", x))
x = copy.deepcopy(fl); x["reason"] = ""
check("理由必填", not ok("feature-layer", x))
x = copy.deepcopy(fl); x["mode"] = "off"
check("关掉时不得带角色列表", not ok("feature-layer", x))

# ---- 权限变化事件
e = {"rev": 32, "cause": "grant", "causeRef": "g2", "affectedPrincipals": ["a-wangkexin"], "changedAt": T}
check("权限变化事件有效", ok("access-policy-changed", e))
check("部门调整可影响全部", ok("access-policy-changed", {"rev": 33, "cause": "org", "all": True, "changedAt": T}))
x = copy.deepcopy(e); del x["affectedPrincipals"]
check("必须写影响谁或全部", not ok("access-policy-changed", x))

# ---- 错误码
reg = {c["code"]: c for c in json.loads((root / "error-codes.json").read_text(encoding="utf-8"))["codes"]}
check("登记 ACCOUNT_LOCKED / FEATURE_NOT_OPEN / SECOND_APPROVAL_REQUIRED",
      all(k in reg for k in ["ACCOUNT_LOCKED", "FEATURE_NOT_OPEN", "SECOND_APPROVAL_REQUIRED"]))

print(f"\n{'全部通过' if not fails else str(len(fails)) + ' 项失败'}")
sys.exit(1 if fails else 0)
