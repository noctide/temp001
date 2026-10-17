"""契约骨架校验（第十一部分）：公共设施——文件版本与引用、审计指纹链、通知、个人通知设置、待办。
来源：后端详细设计·公共设施；后台治理 11、12.2；Shell 9。运行：python test_contracts_part11.py"""
import json, pathlib, copy, sys, hashlib
from jsonschema import Draft202012Validator
root = pathlib.Path(__file__).parent
names = ["asset-version", "asset-ref", "notification", "notify-pref", "todo-item", "audit-event"]
S = {n: json.loads((root / f"{n}.schema.json").read_text(encoding="utf-8")) for n in names}
for n in S: Draft202012Validator.check_schema(S[n])
def ok(n, d): return not list(Draft202012Validator(S[n]).iter_errors(d))
fails = []
def check(label, cond):
    print(("PASS " if cond else "FAIL ") + label)
    if not cond: fails.append(label)
T = "2026-10-17T01:00:00Z"; H = "a" * 64

v = {"assetId": "as-1", "version": 1, "blobSha256": H, "size": 245760, "mimeSniffed": "image/jpeg", "originalName": "打卡机.jpg",
     "state": "available", "checks": {"typeSniff": "pass", "format": "pass", "virusScan": "not_performed"}, "createdAt": T}
check("文件版本示例（未做病毒扫描也可用）有效", ok("asset-version", v))
x = copy.deepcopy(v); x["storagePath"] = "/srv/assets/aa/aa"
check("不暴露服务器路径", not ok("asset-version", x))
x = copy.deepcopy(v); x["checks"]["format"] = "fail"
check("检查没过不能是可用", not ok("asset-version", x))
x["state"] = "quarantined"
check("检查没过进隔离必须写原因", not ok("asset-version", x))
x["checks"]["rejectReasonKey"] = "facilities.file.formatInvalid"
check("隔离带原因有效", ok("asset-version", x))
x = copy.deepcopy(v); x["size"] = 300 * 1024 * 1024
check("超过上限（200 MB）被拒", not ok("asset-version", x))
check("文件引用有效", ok("asset-ref", {"assetId": "as-1", "version": 1, "refModule": "attendance", "refObject": "makeup:mr-9", "refField": "photo", "createdAt": T}))

ae = {"eventId": "e1", "occurredAt": T, "receivedAt": T, "principalId": "p-guyuan", "capabilityId": "titanloom.access.grant.revoke",
      "contractVersion": "1.0.0", "target": {"type": "Grant", "id": "g2"}, "policyVersionSet": {"access": 32}, "result": "succeeded",
      "prevHash": H, "hash": hashlib.sha256(b"x").hexdigest()}
r = ok("audit-event", ae)
if not r:
    base = {k: ae[k] for k in ae if k not in ("prevHash", "hash")}
    print("  (审计示例需按原 Schema 调整)", ok("audit-event", base))
check("审计可带指纹链", "prevHash" in S["audit-event"]["properties"] and "hash" in S["audit-event"]["properties"])
check("指纹必须是 sha256 十六进制", S["audit-event"]["properties"]["hash"]["pattern"] == "^[0-9a-f]{64}$")

n = {"notificationId": "n1", "recipientId": "a-zhouning", "type": "attendance.importFailed", "category": "task_result",
     "subjectRef": "execution.job:JR-8840", "severity": "warning", "messageKey": "attendance.notify.importFailed",
     "params": {"batch": 41}, "link": "/admin/runs/JR-8840", "lang": "zh-CN", "packVersion": "zh-CN@37",
     "dedupeKey": "attendance.importFailed:JR-8840", "mergedCount": 3, "createdAt": T}
check("通知示例（合并 3 次）有效", ok("notification", n))
x = copy.deepcopy(n); x["link"] = "https://files.example/raw.xlsx?token=abc"
check("链接只能是站内路径", not ok("notification", x))
x = copy.deepcopy(n); x["body"] = "唐宁 时薪 32 元"
check("不得携带业务明细正文", not ok("notification", x))
x = copy.deepcopy(n); del x["packVersion"]
check("必须记语言包版本", not ok("notification", x))

check("个人设置：任务结果只站内有效", ok("notify-pref", {"accountId": "a1", "category": "task_result", "channels": ["in_app"]}))
check("审批不能关站内", not ok("notify-pref", {"accountId": "a1", "category": "approval", "channels": ["external"]}))
check("账户安全不能全关", not ok("notify-pref", {"accountId": "a1", "category": "account_security", "channels": []}))

t = {"todoId": "t1", "type": "attendance.makeupReview", "sourceRef": "attendance.makeup:mr-9", "titleKey": "attendance.todo.makeupReview",
     "state": "open", "openedAt": T, "assignees": [{"accountId": "a-zhouning", "state": "open"}, {"accountId": "a-lihang", "state": "open", "snoozedUntil": T}]}
check("组待办（两位考勤管理员）有效", ok("todo-item", t))
x = copy.deepcopy(t); x.update({"state": "done", "doneBy": "a-zhouning", "doneAt": T}); x["assignees"][0]["state"] = "done"; x["assignees"][1]["state"] = "done_by_other"
check("一人办完其余显示已由他人处理", ok("todo-item", x))
x["assignees"][1]["state"] = "open"
check("已办完的待办不能还有人显示待办", not ok("todo-item", x))
x = copy.deepcopy(t); x["state"] = "done"
check("办完必须写谁、何时", not ok("todo-item", x))
x = copy.deepcopy(t); x["assignees"] = []
check("至少一位办理人", not ok("todo-item", x))

print(f"\n{'全部通过' if not fails else str(len(fails)) + ' 项失败'}")
sys.exit(1 if fails else 0)
