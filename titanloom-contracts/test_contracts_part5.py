"""M0 契约骨架校验（第五部分）：JobAttempt、验证证据、准备结果、状态通知、命令固定。运行：python test_contracts_part5.py"""
import json, pathlib, copy, sys
from jsonschema import Draft202012Validator
root=pathlib.Path(__file__).parent
names=["job-attempt","invocation","prepare-result","job-state-notification","command","capability-descriptor"]
S={n:json.loads((root/f"{n}.schema.json").read_text(encoding="utf-8")) for n in names}
for n in S: Draft202012Validator.check_schema(S[n])
def ok(n,d): return not list(Draft202012Validator(S[n]).iter_errors(d))
fails=[]
def check(l,c):
    print(("PASS " if c else "FAIL ")+l)
    if not c: fails.append(l)
T="2026-10-02T09:00:00Z"; T2="2026-10-02T10:00:00Z"; H="sha256:"+"c"*64

at={"attemptId":"att_1","jobId":"job_1","attemptNo":1,"workerId":"w1","fencingToken":7,"leaseExpiresAt":T2,"startedAt":T,"outcome":"running","effectStatus":"none"}
check("JobAttempt(运行中)有效", ok("job-attempt",at))
x=copy.deepcopy(at); del x["fencingToken"]
check("JobAttempt 必须有 fencing token", not ok("job-attempt",x))
x=copy.deepcopy(at); x["fencingToken"]=0
check("fencing token 为正整数", not ok("job-attempt",x))
x=copy.deepcopy(at); x["finishedAt"]=T2
check("运行中的尝试不得有 finishedAt", not ok("job-attempt",x))
x=copy.deepcopy(at); x.update(outcome="lease_lost",finishedAt=T2,effectStatus="unknown")
check("丢失租约且副作用不确定如实记录有效", ok("job-attempt",x))
x=copy.deepcopy(at); x.update(outcome="succeeded",finishedAt=T2,effectStatus="unknown")
check("副作用不确定的尝试不得 succeeded", not ok("job-attempt",x))
x=copy.deepcopy(at); x.update(outcome="failed")
check("结束的尝试必须有 finishedAt", not ok("job-attempt",x))

iv={"invocationId":"inv_1","commandId":"cmd_1","capabilityId":"titanloom.data.pipeline.run","contractVersion":"1.0.0","contextRef":"ctx_1","acceptedAt":T,"receiptKind":"async_receipt","jobRef":"job_1","verification":{"state":"pending"}}
check("验证待定的调用有效(验证器不可用时保持待验证)", ok("invocation",iv))
x=copy.deepcopy(iv); x["verification"]={"state":"verified"}
check("verified 必须有验证器版本、时间与领域运行引用", not ok("invocation",x))
x["verification"]={"state":"verified","validatorVersion":"1.0.0","verifiedAt":T2,"domainRunRef":"pipelinerun:pr_1","inputVersions":["ds@12"],"outputRefs":["dsv@13"],"observedOutcome":"published"}
check("verified 带完整证据有效", ok("invocation",x))
x=copy.deepcopy(iv); x["verification"]={"state":"unavailable"}
check("验证器不可用如实记录有效", ok("invocation",x))
x=copy.deepcopy(iv); x["verification"]={"state":"verified","validatorVersion":"1","verifiedAt":T2,"domainRunRef":"r","naturalLanguageResult":"成功了"}
check("不接受自然语言结果代替证据字段", not ok("invocation",x))

pr={"requestId":"req_001","data":{"commandId":"cmd_001","state":"awaiting_confirmation","capabilityId":"titanloom.data.pipeline.run","contractVersion":"1.0.0","commandDigest":H,"expiresAt":T2,"effectivePolicy":"confirm","preview":{"messageKey":"dataproc.pipelineRun.preview","messageParams":{"period":"2026-09"},"effectScope":"registered_pipeline_outputs","estimateStatus":"bounded_estimate"},"confirmation":{"required":True,"interactionRef":"confirm_ui_001"}}}
check("准备结果有效(规范 6.2 示例)", ok("prepare-result",pr))
x=copy.deepcopy(pr); x["data"]["confirmation"]["required"]=False
check("等待确认状态必须要求确认", not ok("prepare-result",x))
x=copy.deepcopy(pr); x["data"]["preview"]["estimateStatus"]="unknown"
check("影响范围未知且为 confirm 策略仍需确认，有效", ok("prepare-result",x))
x["data"]["effectivePolicy"]="allow"; x["data"]["state"]="ready"; x["data"]["confirmation"]["required"]=False
check("影响范围未知时不得自动执行(allow 或 ready)", not ok("prepare-result",x))
x=copy.deepcopy(pr); x["data"]["effectivePolicy"]="deny"; x["data"]["state"]="ready"; x["data"]["confirmation"]["required"]=False
check("deny 策略不得 ready", not ok("prepare-result",x))
x=copy.deepcopy(pr); x["data"]["preview"]["estimateStatus"]="roughly"
check("估计状态枚举受限", not ok("prepare-result",x))

check("状态通知只含 jobId 与 stateVersion", ok("job-state-notification",{"jobId":"job_1","stateVersion":4}))
check("状态通知不得携带业务数据", not ok("job-state-notification",{"jobId":"job_1","stateVersion":4,"rows":[1]}))

cmd={"commandId":"cmd_1","capabilityId":"titanloom.data.pipeline.run","contractVersion":"1.0.0","state":"ready","principalId":"u1","workspaceId":"w1","idempotencyKey":"0192f3b4-7c1a-7d2e-8a5b-3c4d5e6f7a8b","requestDigest":H,"commandDigest":H,"target":{"type":"Pipeline","id":"pl_hours"},"expectedResourceVersion":"7","createdAt":T,"expiresAt":T2}
check("命令固定到精确目标与版本有效", ok("command",cmd))
x=copy.deepcopy(cmd); x["expectedResourceVersion"]="latest"
check("待确认命令不得留 latest 版本", not ok("command",x))
x=copy.deepcopy(cmd); x["target"]["id"]="latest"
check("待确认命令不得留 latest 目标", not ok("command",x))

cap=json.loads((root/"examples"/"capability.pipeline-run.json").read_text(encoding="utf-8"))
check("描述符示例(对齐规范 3.3)有效", ok("capability-descriptor",cap))
x=copy.deepcopy(cap); x["bindings"]={}
check("描述符绑定不得为空", not ok("capability-descriptor",x))
x=copy.deepcopy(cap); x["resultVerification"]["evidence"]=[]
check("验证必须有成功证据字段", not ok("capability-descriptor",x))
x=copy.deepcopy(cap); x["implementationRef"]="plugin-latest"
check("实现引用必须是精确版本", not ok("capability-descriptor",x))
x=copy.deepcopy(cap); x["execution"]["mode"]="whenever"
check("执行模式枚举受限", not ok("capability-descriptor",x))
print(f"\n{len(fails)} 项失败" if fails else "\n全部通过"); sys.exit(1 if fails else 0)
