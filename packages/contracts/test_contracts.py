"""M0 契约骨架校验。运行：python test_contracts.py"""
import json, pathlib, copy, sys
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

root = pathlib.Path(__file__).parent
def load(p): return json.loads((root / p).read_text(encoding="utf-8"))

schemas = {n: load(n) for n in ["capability-descriptor.schema.json","command.schema.json","job-run.schema.json","error.schema.json"]}
registry = Registry().with_resources([(n, Resource.from_contents(s)) for n, s in schemas.items()])
def validator(name): return Draft202012Validator(schemas[name], registry=registry)
def ok(name, doc): return not list(validator(name).iter_errors(doc))

fails = []
def check(label, cond):
    print(("PASS " if cond else "FAIL ") + label)
    if not cond: fails.append(label)

cap = load("examples/capability.pipeline-run.json")
cmd = load("examples/command.accepted.json")
job = load("examples/job-run.reconciling.json")

check("示例能力描述符有效", ok("capability-descriptor.schema.json", cap))
check("示例命令(accepted)有效", ok("command.schema.json", cmd))
check("示例 JobRun(reconciling, effect unknown)有效", ok("job-run.schema.json", job))

# 负例：契约中明确禁止的情形
c = copy.deepcopy(cap); c["capabilityId"] = "admin.execute"
check("拒绝非 titanloom.<domain>.<resource>.<action> 命名", not ok("capability-descriptor.schema.json", c))
c = copy.deepcopy(cap); c["idempotency"]["required"] = False
check("business_write 必须要求幂等", not ok("capability-descriptor.schema.json", c))
c = copy.deepcopy(cap); c["authorization"]["agentPolicies"] = ["draft_only"]
check("draft_only 不得用于 business_write", not ok("capability-descriptor.schema.json", c))
c = copy.deepcopy(cap); c["inputSchema"]["ref"] = "https://evil.example/schema.json"
check("Schema 引用必须带摘要(不接受裸远程 URL)", not ok("capability-descriptor.schema.json", c))

m = copy.deepcopy(cmd); del m["invocationRef"]
check("accepted 命令必须有 invocationRef", not ok("command.schema.json", m))
m = copy.deepcopy(cmd); m["state"] = "ready"
check("非 accepted 命令不得有 invocationRef", not ok("command.schema.json", m))
m = copy.deepcopy(cmd); del m["idempotencyKey"]
check("创建命令必须带幂等键", not ok("command.schema.json", m))
m = copy.deepcopy(cmd); m["idempotencyKey"]="client_456"
check("幂等键必须是 UUIDv7，clientRequestId 不能代替", not ok("command.schema.json", m))
m = copy.deepcopy(cmd); del m["requestDigest"]
check("命令必须有 requestDigest", not ok("command.schema.json", m))
m = copy.deepcopy(cmd); del m["commandDigest"]
check("accepted 命令必须有 commandDigest", not ok("command.schema.json", m))
m = copy.deepcopy(cmd); m.update(state="awaiting_confirmation"); del m["invocationRef"]
check("awaiting_confirmation 必须绑定影响摘要", not ok("command.schema.json", m))

j = copy.deepcopy(job); j.update(state="running", effectStatus="none", currentAttemptRef="att_3")
check("running 的 JobRun 引用当前 JobAttempt 有效", ok("job-run.schema.json", j))
del j["currentAttemptRef"]
check("running 缺 currentAttemptRef 被拒", not ok("job-run.schema.json", j))
j = copy.deepcopy(job); j["fencingToken"] = 3
check("fencing token 不属于 JobRun(属于 JobAttempt)", not ok("job-run.schema.json", j))
j = copy.deepcopy(job); del j["enqueueCount"]
check("必须区分入队次数与执行尝试次数", not ok("job-run.schema.json", j))
j = copy.deepcopy(job); j["state"] = "canceled"; j["finishedAt"] = "2026-10-01T09:05:00Z"
check("effect unknown 不得直接 canceled(须先 reconciling)", not ok("job-run.schema.json", j))
j = copy.deepcopy(job); j["state"] = "succeeded"; j["finishedAt"] = "2026-10-01T09:05:00Z"
check("effect unknown 不得 succeeded", not ok("job-run.schema.json", j))
j = copy.deepcopy(job); j.update(state="failed", effectStatus="partial")
check("终态必须有 finishedAt", not ok("job-run.schema.json", j))
j = copy.deepcopy(job); j.update(state="failed", effectStatus="partial", finishedAt="2026-10-01T09:05:00Z")
check("failed + partial 副作用有效(须如实记录)", ok("job-run.schema.json", j))

err = {"requestId":"req_003","error":{"code":"RESOURCE_VERSION_CONFLICT","messageKey":"errors.resourceVersionConflict","messageParams":{},"retryable":False,"recoveryAction":"refresh_and_prepare","details":{"commandId":"cmd_001"}}}
check("规范 12.1 示例错误体有效", ok("error.schema.json", err))
e = copy.deepcopy(err); e["error"]["stack"] = "Traceback..."
check("错误体不得携带栈等内部字段", not ok("error.schema.json", e))

# 状态机：终态不复活、迁移目标均为已定义状态
sm = load("state-machines.json")
for name, enum_src in [("command", schemas["command.schema.json"]["properties"]["state"]["enum"]),
                       ("jobRun", schemas["job-run.schema.json"]["properties"]["state"]["enum"])]:
    t = sm[name]["transitions"]
    check(f"{name}: 状态机与 Schema 枚举一致", set(t) == set(enum_src))
    check(f"{name}: 迁移目标均已定义", all(x in t for v in t.values() for x in v))
    check(f"{name}: 终态无后续迁移", all(t[s] == [] for s in sm[name]["terminal"]))
    # 可达性
    def reach(s, seen=None):
        seen = seen or set()
        for n in t[s]:
            if n not in seen: seen.add(n); reach(n, seen)
        return seen
    check(f"{name}: 每个非终态都能到达终态", all(set(sm[name]["terminal"]) & (reach(s)|{s}) for s in t))

print(f"\n{len(fails)} 项失败" if fails else "\n全部通过")
sys.exit(1 if fails else 0)
