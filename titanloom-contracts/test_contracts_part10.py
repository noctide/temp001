"""契约骨架校验（第十部分）：命令与任务——执行登记、定时规则、计划时刻、待核对。
来源：后端详细设计·命令与任务；能力契约 6–8；工具自动化 9。运行：python test_contracts_part10.py"""
import json, pathlib, copy, sys
from jsonschema import Draft202012Validator
root = pathlib.Path(__file__).parent
names = ["execution-binding", "schedule-rule", "trigger-occurrence", "reconcile-case"]
S = {n: json.loads((root / f"{n}.schema.json").read_text(encoding="utf-8")) for n in names}
for n in S: Draft202012Validator.check_schema(S[n])
def ok(n, d): return not list(Draft202012Validator(S[n]).iter_errors(d))
fails = []
def check(label, cond):
    print(("PASS " if cond else "FAIL ") + label)
    if not cond: fails.append(label)
T = "2026-10-17T01:00:00Z"

b = {"capabilityId": "titanloom.attendance.access_import.run", "contractVersion": "1.0.0", "module": "attendance",
     "mode": "async", "lane": "heavy", "confirmPolicy": "auto", "maxRunSec": 1800,
     "retry": {"maxAttempts": 3, "backoffSec": [30, 120], "jitter": 0.2, "retryOn": ["transient", "dependency_unavailable"]},
     "cancellable": True, "reconcile": {"autoWindowMin": 15}}
check("执行登记示例（门禁导入 · 重道）有效", ok("execution-binding", b))
x = copy.deepcopy(b); x["mode"] = "sync"
check("重道必须后台执行", not ok("execution-binding", x))
x = copy.deepcopy(b); del x["lane"]
check("后台执行必须选道", not ok("execution-binding", x))
x = copy.deepcopy(b); x["mode"] = "sync"; del x["lane"]
check("同步执行不选道", ok("execution-binding", x))
x = copy.deepcopy(b); x["retry"]["retryOn"] = ["unknown_effect"]
check("副作用不确定不在可重试原因里", not ok("execution-binding", x))
x = copy.deepcopy(b); x["retry"]["maxAttempts"] = 0
check("至少一次尝试", not ok("execution-binding", x))

r = {"ruleId": "sr-1", "ownerModule": "automation", "bindingRef": "auto:9am-reminder", "rrule": "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR;BYHOUR=9;BYMINUTE=0",
     "timeZone": "Asia/Shanghai", "misfire": {"policy": "skip"}, "overlap": "skip_new", "status": "active"}
check("定时规则示例（工作日 9 点 · 不补跑）有效", ok("schedule-rule", r))
x = copy.deepcopy(r); x["misfire"] = {"policy": "catch_up"}
check("补跑必须有次数与时间窗上限", not ok("schedule-rule", x))
x["misfire"].update({"maxCatchUp": 3, "withinHours": 24})
check("补跑带上限有效", ok("schedule-rule", x))
x = copy.deepcopy(r); x["timeZone"] = "+08:00"
check("时区用 IANA 名称，不用固定偏移", not ok("schedule-rule", x))
x = copy.deepcopy(r); del x["overlap"]
check("必须声明重叠策略", not ok("schedule-rule", x))

o = {"ruleId": "sr-1", "plannedAt": "2026-10-17T01:00:00Z", "state": "placed", "jobId": "j1", "recordedAt": T}
check("计划时刻（已放任务）有效", ok("trigger-occurrence", o))
check("错过必须写原因", not ok("trigger-occurrence", {"ruleId": "sr-1", "plannedAt": "2026-10-17T01:00:00Z", "state": "missed", "recordedAt": T}))
check("错过带原因有效", ok("trigger-occurrence", {"ruleId": "sr-1", "plannedAt": "2026-10-17T01:00:00Z", "state": "missed", "reasonKey": "execution.occurrence.hostDown", "recordedAt": T}))
x = copy.deepcopy(o); x["plannedAt"] = "2026-10-17T09:00:00+08:00"
check("计划时刻存 UTC", not ok("trigger-occurrence", x))
x = copy.deepcopy(o); x["state"] = "skipped_overlap"; x["reasonKey"] = "execution.occurrence.previousRunning"
check("跳过的时刻不得挂任务", not ok("trigger-occurrence", x))

c = {"caseId": "rc-1", "jobId": "j9", "openedAt": T, "autoUntil": "2026-10-17T01:15:00Z", "state": "auto_checking"}
check("待核对（自动查证中）有效", ok("reconcile-case", c))
x = copy.deepcopy(c); x["state"] = "concluded"; x["conclusion"] = "done"
check("下结论必须有人、时间和证据", not ok("reconcile-case", x))
x.update({"decidedBy": "p-zhouning", "decidedAt": T, "evidence": [{"kind": "peer_query", "ref": "msg-77"}]})
check("结论必须经领域命令落地", not ok("reconcile-case", x))
x["domainCommandRef"] = "cmd-55"
check("完整结论有效", ok("reconcile-case", x))
x = copy.deepcopy(x); x["conclusion"] = "mark_success"
check("没有'直接标成功'", not ok("reconcile-case", x))

print(f"\n{'全部通过' if not fails else str(len(fails)) + ' 项失败'}")
sys.exit(1 if fails else 0)
