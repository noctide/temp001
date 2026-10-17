"""M0 契约骨架校验（第二部分）：调用链对象与集成通道对象。运行：python test_contracts_part2.py"""
import json, pathlib, copy, sys
from jsonschema import Draft202012Validator
root = pathlib.Path(__file__).parent
names = ["pipeline-run","idempotency-record","invocation-context","delegation","confirmation","invocation","outbox-event","channel-connection","delivery-route","inbound-endpoint","inbound-receipt"]
S = {n: json.loads((root/f"{n}.schema.json").read_text(encoding="utf-8")) for n in names}
for n in names: Draft202012Validator.check_schema(S[n])
def ok(n, d): return not list(Draft202012Validator(S[n]).iter_errors(d))
fails=[]
def check(l,c):
    print(("PASS " if c else "FAIL ")+l)
    if not c: fails.append(l)
H="sha256:"+"a"*64; T="2026-10-02T09:00:00Z"; T2="2026-10-02T10:00:00Z"
check("全部 Schema 本身合法", True)

ctx={"principalId":"p1","invocationType":"human_session","workspaceId":"w1","audience":"titanloom-api","expiresAt":T2,"policyVersionSet":{"authz":3},"requestId":"r1","traceId":"t1"}
check("人工会话上下文有效", ok("invocation-context",ctx))
a=copy.deepcopy(ctx); a["invocationType"]="agent_runtime"
check("Agent 调用缺运行端与委托被拒", not ok("invocation-context",a))
a.update(executorId="e1",runtimeId="rt1",delegationId="d1",delegationVersion=2)
check("Agent 调用带运行端与委托有效", ok("invocation-context",a))

dl={"delegationId":"d1","version":1,"principalId":"p1","executorId":"e1","purpose":"月度效率计算","scope":{"capabilities":["titanloom.data.query.execute"],"resources":["dataset:ds1"]},"validFrom":T,"validUntil":T2,"revocable":True,"state":"active"}
check("委托有效", ok("delegation",dl))
b=copy.deepcopy(dl); b["scope"]["capabilities"]=[]
check("委托范围不得为空", not ok("delegation",b))
b=copy.deepcopy(dl); b["revocable"]=False
check("委托必须可撤销", not ok("delegation",b))

cf={"confirmationId":"c1","commandId":"cmd_1","confirmedBy":"p1","confirmerType":"human","principalId":"p1","commandDigest":H,"impactSummaryDigest":H,"createdAt":T,"expiresAt":T2,"consumed":False}
check("确认(未消费)有效", ok("confirmation",cf))
c=copy.deepcopy(cf); c["confirmerType"]="agent"
check("Agent 不能确认自己", not ok("confirmation",c))
c=copy.deepcopy(cf); c["consumed"]=True
check("已消费确认必须记录消费它的调用", not ok("confirmation",c))
c["consumedByInvocation"]="inv_1"
check("已消费确认带调用引用有效", ok("confirmation",c))

idem={"workspaceId":"w1","principalId":"p1","capabilityId":"titanloom.data.pipeline.run","contractMajor":1,"idempotencyKey":"0192f3b4-7c1a-7d2e-8a5b-3c4d5e6f7a8b","requestDigest":H,"commandId":"cmd_1","createdAt":T,"retainUntil":T2,"tombstone":False}
check("幂等记录有效", ok("idempotency-record",idem))
x=copy.deepcopy(idem); x["idempotencyKey"]="abc"
check("幂等记录键必须是 UUIDv7", not ok("idempotency-record",x))
x=copy.deepcopy(idem); del x["requestDigest"]
check("幂等记录必须有 requestDigest", not ok("idempotency-record",x))

inv={"invocationId":"inv_1","commandId":"cmd_1","capabilityId":"titanloom.data.pipeline.run","contractVersion":"1.0.0","contextRef":"ctx_1","acceptedAt":T,"receiptKind":"async_receipt","jobRef":"job_1"}
check("异步调用有效", ok("invocation",inv))
d=copy.deepcopy(inv); del d["jobRef"]
check("异步回执必须有 jobRef", not ok("invocation",d))

ev={"eventId":"e1","type":"attendance.declaration.confirmed","schemaVersion":1,"source":"attendance","scope":"w1","subject":{"type":"AttendanceDeclaration","id":"decl_1"},"sourceVersion":"3","occurredAt":T,"recordedAt":T,"correlationId":"corr_1"}
check("统一事件信封有效", ok("outbox-event",ev))
e=copy.deepcopy(ev); e["payload"]={"all":"data"}
check("事件信封不得夹带完整载荷字段", not ok("outbox-event",e))

ch={"channelId":"ch1","revision":1,"channelType":"generic_webhook","targetSecretRef":"secret:ch1/target","maxDataClass":"internal","timeoutSeconds":5,"maxResponseBytes":65536,"rateLimit":{"perMinute":30,"concurrency":1},"egressApprovalRef":"egress:ap1","revisionState":"draft","operationalState":"disabled"}
check("通道有效", ok("channel-connection",ch))
x=copy.deepcopy(ch); x["url"]="https://hook.example/abc?token=SECRET"
check("通道不允许明文 url 字段", not ok("channel-connection",x))
x=copy.deepcopy(ch); x["token"]="abc"
check("通道不允许明文 token 字段", not ok("channel-connection",x))
x=copy.deepcopy(ch); x["targetSecretRef"]="https://hook.example/abc"
check("目标必须是 SecretRef 而非 URL", not ok("channel-connection",x))
x=copy.deepcopy(ch); x["followRedirects"]=True
check("通道不得默认跟随重定向", not ok("channel-connection",x))
x=copy.deepcopy(ch); x["verifyTls"]=False
check("关闭证书校验须有批准引用", not ok("channel-connection",x))
x=copy.deepcopy(ch); del x["egressApprovalRef"]
check("通道必须有出网批准引用", not ok("channel-connection",x))
x=copy.deepcopy(ch); x["rateLimit"]["concurrency"]=50
check("通道并发有上限", not ok("channel-connection",x))

rt={"routeId":"r1","revision":1,"sources":[{"category":"platform_alert","minSeverity":"warning"}],"channelIds":["ch1"],"templateVersionRef":"tpl1@3","dedupeKeyTemplate":"{category}:{resourceId}","revisionState":"draft","operationalState":"disabled"}
check("路由有效", ok("delivery-route",rt))
x=copy.deepcopy(rt); x["channelIds"]=[]
check("路由必须有通道", not ok("delivery-route",x))
# 跨对象规则参考实现：模板变量级别不得高于通道上限
rank={"public":0,"internal":1,"restricted":2}
def route_publishable(var_classes, channel): return all(rank[c]<=rank[channel["maxDataClass"]] for c in var_classes)
check("模板含 restricted 变量发往 internal 通道不可发布", not route_publishable(["internal","restricted"], ch))
check("模板变量不高于通道上限可发布", route_publishable(["public","internal"], ch))

ep={"endpointId":"ep1","revision":1,"pathId":"Xk3m9Qw2Lp7Rt5Yv8Zb1Nc","purpose":"event_ingest","auth":{"scheme":"hmac_sha256","secretRef":"secret:ep1/key"},"timestampToleranceSeconds":300,"maxBodyBytes":65536,"rateLimit":{"perMinute":60},"revisionState":"draft","operationalState":"disabled"}
check("入站端点(事件接入)有效", ok("inbound-endpoint",ep))
x=copy.deepcopy(ep); x["pathId"]="abc"
check("路径标识过短被拒", not ok("inbound-endpoint",x))
x=copy.deepcopy(ep); del x["auth"]
check("入站必须有鉴权", not ok("inbound-endpoint",x))
x=copy.deepcopy(ep); x["timestampToleranceSeconds"]=86400
check("时间窗不得过大", not ok("inbound-endpoint",x))
x=copy.deepcopy(ep); x["purpose"]="command"
check("命令类入站必须声明身份绑定", not ok("inbound-endpoint",x))
x["identityBindingRequired"]=False
check("命令类入站不得关闭身份绑定", not ok("inbound-endpoint",x))
x["identityBindingRequired"]=True
check("命令类入站启用身份绑定有效", ok("inbound-endpoint",x))
x=copy.deepcopy(ep); x["auth"]["previousSecretRef"]="secret:ep1/old"
check("保留旧密钥必须给重叠截止时间", not ok("inbound-endpoint",x))
x["auth"]["overlapUntil"]=T2
check("旧密钥带重叠截止时间有效", ok("inbound-endpoint",x))

rc={"receiptId":"rc1","endpointId":"ep1","endpointRevision":1,"deliveryId":"dlv_1","receivedAt":T,"payloadDigest":H,"state":"accepted"}
check("接收记录有效", ok("inbound-receipt",rc))
x=copy.deepcopy(rc); x["state"]="rejected"
check("拒绝的接收必须有原因", not ok("inbound-receipt",x))
x["rejectReason"]="bad_signature"
check("拒绝带原因有效", ok("inbound-receipt",x))

pr={"pipelineRunId":"pr_1","pipelineVersionRef":"pl_hours@7","runKind":"full_run","runState":"succeeded","qualityResult":"passed","publishResult":"published","outputDatasetVersionRef":"ds_eff@12","createdAt":T,"finishedAt":T2}
check("PipelineRun 发布成功有效", ok("pipeline-run",pr))
x=copy.deepcopy(pr); x["qualityResult"]="blocked"
check("质量阻断时不得 published", not ok("pipeline-run",x))
x=copy.deepcopy(pr); x.update(qualityResult="blocked",publishResult="not_published")
check("质量阻断且未发布有效(JobRun 成功不等于发布)", ok("pipeline-run",x))
x=copy.deepcopy(pr); x["runState"]="failed"
check("published 要求 runState=succeeded", not ok("pipeline-run",x))
x=copy.deepcopy(pr); del x["outputDatasetVersionRef"]
check("published 必须指向输出 Dataset 版本", not ok("pipeline-run",x))
x=copy.deepcopy(pr); x["runKind"]="dry_run"
check("Dry Run 不得发布", not ok("pipeline-run",x))
x=copy.deepcopy(pr); x.update(runKind="dry_run",publishResult="not_applicable",qualityResult="warned")
check("Dry Run 且 not_applicable 有效", ok("pipeline-run",x))
x=copy.deepcopy(pr); x.update(runState="reconciling",publishResult="published"); del x["finishedAt"]
check("reconciling 时不得标记 published", not ok("pipeline-run",x))
x=copy.deepcopy(pr); x.update(runState="reconciling",publishResult="unknown",qualityResult="not_evaluated"); del x["finishedAt"]
check("reconciling + unknown 有效", ok("pipeline-run",x))
x=copy.deepcopy(pr); del x["finishedAt"]
check("终态必须有 finishedAt", not ok("pipeline-run",x))

e=copy.deepcopy(ev); e["resourceId"]="decl_1"
check("旧字段名 resourceId 被拒(统一为 subject)", not ok("outbox-event",e))
e=copy.deepcopy(ev); del e["correlationId"]
check("事件必须带 correlationId", not ok("outbox-event",e))
e=copy.deepcopy(ev); e.update(changeSeq=41,correctionOf="e0")
check("增量游标与更正引用有效", ok("outbox-event",e))

e=copy.deepcopy(ev); e.update(causationId="evt_0",originRunRef="automationrun:ar_1")
check("事件可携带 causationId 与来源 Run（自动化循环保护）", ok("outbox-event",e))

print(f"\n{len(fails)} 项失败" if fails else "\n全部通过"); sys.exit(1 if fails else 0)
