"""M0 契约骨架校验（第四部分）：配置生命周期、激活、审计、平台告警。运行：python test_contracts_part4.py"""
import json, pathlib, copy, sys
from jsonschema import Draft202012Validator
root = pathlib.Path(__file__).parent
names=["config-activation","audit-event","platform-alert-rule","channel-connection","delivery-route","inbound-endpoint"]
S={n:json.loads((root/f"{n}.schema.json").read_text(encoding="utf-8")) for n in names}
for n in S: Draft202012Validator.check_schema(S[n])
def ok(n,d): return not list(Draft202012Validator(S[n]).iter_errors(d))
fails=[]
def check(l,c):
    print(("PASS " if c else "FAIL ")+l)
    if not c: fails.append(l)
T="2026-10-02T09:00:00Z"; T2="2026-10-02T10:00:00Z"; H="sha256:"+"b"*64

# 修订、激活、运行开关三维度分离
for n in ["channel-connection","delivery-route","inbound-endpoint"]:
    props=S[n]["properties"]
    check(f"{n}: 不再使用单一 state", "state" not in props and "state" not in S[n]["required"])
    check(f"{n}: 含 revisionState 与 operationalState", "revisionState" in props and "operationalState" in props)
    check(f"{n}: 修订状态枚举与后台治理 7.2 一致", props["revisionState"]["enum"]==["draft","validated","published","superseded","withdrawn"])

ac={"activationId":"act_1","configType":"delivery-route","configId":"r1","targetRevision":3,"previousRevision":2,"state":"effective","targets":[{"targetRef":"node:a","appliedRevision":3,"state":"applied"}],"createdAt":T,"finishedAt":T2}
check("激活(全部目标已应用)有效", ok("config-activation",ac))
x=copy.deepcopy(ac); x["targets"].append({"targetRef":"node:b","appliedRevision":2,"state":"failed"})
check("存在失败目标时不得为 effective", not ok("config-activation",x))
x["state"]="partial"
check("部分生效如实记录有效", ok("config-activation",x))
x=copy.deepcopy(ac); x["state"]="applying"; del x["finishedAt"]
check("应用中无需 finishedAt", ok("config-activation",x))
x=copy.deepcopy(ac); del x["finishedAt"]
check("effective 必须有 finishedAt", not ok("config-activation",x))
x=copy.deepcopy(ac); x["state"]="published"
check("激活状态不得混入修订状态词", not ok("config-activation",x))
x=copy.deepcopy(ac); x["targets"]=[]
check("激活必须至少有一个目标", not ok("config-activation",x))

au={"eventId":"aud_1","occurredAt":T,"receivedAt":T2,"principalId":"p1","capabilityId":"titanloom.integration.channel.publish","contractVersion":"1.0.0","target":{"type":"ChannelConnection","id":"ch1"},"beforeDigest":H,"afterDigest":H,"policyVersionSet":{"authz":3},"result":"succeeded","commandId":"cmd_1"}
check("审计事件有效", ok("audit-event",au))
x=copy.deepcopy(au); x["before"]={"url":"https://hook.example/x?token=SECRET"}
check("审计不得存前后值原文，只存摘要", not ok("audit-event",x))
x=copy.deepcopy(au); del x["policyVersionSet"]
check("审计必须记录策略版本", not ok("audit-event",x))
x=copy.deepcopy(au); x["result"]="ok"
check("审计结果枚举受限", not ok("audit-event",x))
x=copy.deepcopy(au); x["result"]="unknown"
check("外部副作用不确定时可如实记 unknown", ok("audit-event",x))

al={"ruleId":"ar1","revision":1,"scope":"platform","signal":"queue_backlog","windowSeconds":300,"threshold":100,"comparison":">","severity":"warning","dedupeKeyTemplate":"queue:{queue}","recovery":{"condition":"below_threshold","holdSeconds":120},"routeRefs":["route:ops"]}
check("平台告警规则有效", ok("platform-alert-rule",al))
x=copy.deepcopy(al); x["signal"]="attendance_missing_declaration"
check("平台告警不承载领域业务异常", not ok("platform-alert-rule",x))
x=copy.deepcopy(al); del x["recovery"]
check("告警规则必须有恢复条件", not ok("platform-alert-rule",x))
x=copy.deepcopy(al); x["routeRefs"]=[]
check("告警规则必须有路由", not ok("platform-alert-rule",x))
print(f"\n{len(fails)} 项失败" if fails else "\n全部通过"); sys.exit(1 if fails else 0)
