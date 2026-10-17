"""契约骨架校验（第八部分）：后端总图——通用列、全局搜索索引条目、SearchProvider 登记。
来源：后端详细设计·总图 6、9；Shell 9.7；能力契约 9.5。运行：python test_contracts_part8.py"""
import json, pathlib, copy, sys
from jsonschema import Draft202012Validator
root = pathlib.Path(__file__).parent
names = ["record-common", "search-doc", "search-provider", "job-run", "job-attempt"]
S = {n: json.loads((root / f"{n}.schema.json").read_text(encoding="utf-8")) for n in names}
for n in S: Draft202012Validator.check_schema(S[n])
def ok(n, d): return not list(Draft202012Validator(S[n]).iter_errors(d))
fails = []
def check(label, cond):
    print(("PASS " if cond else "FAIL ") + label)
    if not cond: fails.append(label)

# ---- 通用列
rec = {"id": "0192a1b2-c3d4-7e5f-8a9b-0c1d2e3f4a5b", "code": "AU-0013", "revision": 1,
       "createdAt": "2026-10-17T01:02:03Z", "createdBy": "p-tangning", "updatedAt": "2026-10-17T01:02:03Z",
       "updatedBy": "p-tangning", "status": "active", "scopeKind": "dept", "scopeId": "dept-assembly-1"}
check("通用列示例有效", ok("record-common", rec))
x = copy.deepcopy(rec); x["id"] = "0192a1b2-c3d4-4e5f-8a9b-0c1d2e3f4a5b"
check("id 必须是 UUIDv7（拒绝 v4）", not ok("record-common", x))
x = copy.deepcopy(rec); del x["scopeId"]
check("部门 / 项目归属必须有 scopeId", not ok("record-common", x))
x = copy.deepcopy(rec); x["scopeKind"] = "personal"; del x["scopeId"]
check("个人归属可无 scopeId", ok("record-common", x))
x = copy.deepcopy(rec); x["createdAt"] = "2026-10-17T09:02:03+08:00"
check("时间一律存 UTC（Z 结尾）", not ok("record-common", x))
x = copy.deepcopy(rec); x["revision"] = 0
check("revision 从 1 起", not ok("record-common", x))
x = copy.deepcopy(rec); del x["code"]
check("短编号可选", ok("record-common", x))

# ---- 搜索索引条目
doc = {"objectType": "attendance.makeupRequest", "objectId": "0192a1b2-c3d4-7e5f-8a9b-0c1d2e3f4a5b",
       "module": "attendance", "scopeKind": "dept", "scopeId": "dept-assembly-1",
       "visibility": {"mode": "scope_members"}, "titleZh": "补签申请", "titleEn": "Makeup punch request",
       "aliases": ["补卡"], "pinyinFull": ["buqianshenqing"], "pinyinInitials": ["bqsq"],
       "excerpt": "10-02 补下班卡", "updatedAt": "2026-10-17T01:02:03Z"}
check("搜索条目示例有效", ok("search-doc", doc))
x = copy.deepcopy(doc); x["body"] = "正文全文"
check("索引不存正文等未登记字段", not ok("search-doc", x))
x = copy.deepcopy(doc); x["excerpt"] = "字" * 501
check("摘要不超过 500 字", not ok("search-doc", x))
x = copy.deepcopy(doc); x["pinyinFull"] = ["a"] * 9
check("多音字组合上限 8 种", not ok("search-doc", x))
x = copy.deepcopy(doc); x["visibility"] = {"mode": "grantees"}
check("按授权可见必须引用人员集合", not ok("search-doc", x))
x = copy.deepcopy(doc); x["visibility"] = {"mode": "grantees", "principalSetRef": "ps-1", "members": ["a", "b"]}
check("可见性不内联名单", not ok("search-doc", x))
x = copy.deepcopy(doc); del x["scopeId"]
check("部门归属条目必须有 scopeId", not ok("search-doc", x))

# ---- SearchProvider 登记
prov = {"module": "attendance",
        "objectTypes": [{"objectType": "attendance.makeupRequest", "group": "form", "labelKey": "attendance.makeup.title",
                         "sensitiveFieldsExcluded": True}],
        "actions": [{"actionId": "attendance.makeup.new", "labelKey": "attendance.makeup.new", "route": "/attendance/makeup/new",
                     "keywords": ["补签", "补卡", "makeup"], "capabilityId": "titanloom.attendance.makeup_request.submit"}],
        "checkVisibleCapability": "titanloom.attendance.search.check_visible",
        "reindexEvent": "attendance.makeupRequest.changed", "nightlyReconcile": True}
check("SearchProvider 示例有效", ok("search-provider", prov))
x = copy.deepcopy(prov); del x["checkVisibleCapability"]
check("必须提供 check_visible 复核", not ok("search-provider", x))
x = copy.deepcopy(prov); x["objectTypes"][0]["sensitiveFieldsExcluded"] = False
check("敏感字段不得进索引", not ok("search-provider", x))
x = copy.deepcopy(prov); x["actions"][0]["route"] = "https://evil.example/x"
check("可搜索操作只能跳站内路由", not ok("search-provider", x))
x = copy.deepcopy(prov); x["actions"][0]["labelKey"] = "补签"
check("操作名称用文案键，不写死文字", not ok("search-provider", x))
x = copy.deepcopy(prov); x["nightlyReconcile"] = False
check("不得关闭每晚对账", not ok("search-provider", x))

# ---- 租约在 JobAttempt 上（总图 4、11）
check("JobAttempt 带 workerId / fencingToken / leaseExpiresAt",
      all(k in S["job-attempt"]["required"] for k in ["workerId", "fencingToken", "leaseExpiresAt"]))
check("JobRun 不另存租约字段", not any(k in S["job-run"]["properties"] for k in ["leaseOwner", "leaseUntil", "fencingToken"]))

print(f"\n{'全部通过' if not fails else str(len(fails)) + ' 项失败'}")
sys.exit(1 if fails else 0)
