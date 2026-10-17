"""M0 契约骨架校验（第三部分）：Query 请求与响应、错误码注册表。运行：python test_contracts_part3.py"""
import json, pathlib, copy, sys, re, glob
from jsonschema import Draft202012Validator
root = pathlib.Path(__file__).parent
S = {n: json.loads((root/f"{n}.schema.json").read_text(encoding="utf-8")) for n in ["query-execute-request","query-execute-response","error"]}
for n in S: Draft202012Validator.check_schema(S[n])
def ok(n,d): return not list(Draft202012Validator(S[n]).iter_errors(d))
fails=[]
def check(l,c):
    print(("PASS " if c else "FAIL ")+l)
    if not c: fails.append(l)
rq={"contractVersion":"1.0.0","queryVersion":"4","parameters":{"month":"2026-09"},"page":{"limit":100,"cursor":None},"consistency":{"mode":"snapshot","snapshotId":"snap_1"}}
check("Query 请求有效(规范 9.1 示例)", ok("query-execute-request",rq))
x=copy.deepcopy(rq); del x["consistency"]["snapshotId"]
check("snapshot 模式必须带 snapshotId", not ok("query-execute-request",x))
x=copy.deepcopy(rq); x["consistency"]={"mode":"live"}
check("live 模式无需快照有效", ok("query-execute-request",x))
x=copy.deepcopy(rq); x["sql"]="select * from t"
check("不允许提交任意 SQL", not ok("query-execute-request",x))
x=copy.deepcopy(rq); x["connection"]="postgres://x"
check("不允许提交底层连接", not ok("query-execute-request",x))
x=copy.deepcopy(rq); x["page"]["limit"]=100000
check("分页上限受约束", not ok("query-execute-request",x))
rs={"requestId":"req_002","data":{"queryId":"q_hours","queryVersion":"4","datasetVersion":"32","snapshotId":"snap_1","sourceWatermarks":[{"sourceId":"src_hours","version":"batch_88"}],"dataAsOf":"2026-09-26T09:00:00Z","qualityStatus":"passed","columns":[{"name":"employeeId","type":"string"},{"name":"hours","type":"decimal","scale":2,"encoding":"string"}],"rows":[{"employeeId":"000123","hours":"168.50"}],"nextCursor":None,"truncated":False}}
check("Query 响应有效(规范 9.1 示例)", ok("query-execute-response",rs))
x=copy.deepcopy(rs); x["data"]["qualityStatus"]="blocked"
check("blocked 数据不会发布，响应不得为 blocked", not ok("query-execute-response",x))
x=copy.deepcopy(rs); del x["data"]["columns"][1]["encoding"]
check("decimal 列必须声明字符串编码", not ok("query-execute-response",x))
x=copy.deepcopy(rs); del x["data"]["dataAsOf"]
check("响应必须带 dataAsOf", not ok("query-execute-response",x))
x=copy.deepcopy(rs); x["data"]["qualityStatus"]="warned"
check("warned 有效(带质量告警的成功响应)", ok("query-execute-response",x))
reg=json.loads((root/"error-codes.json").read_text(encoding="utf-8"))["codes"]
codes=[c["code"] for c in reg]
check("错误码唯一", len(codes)==len(set(codes)))
check("错误码格式合法", all(re.fullmatch(r"[A-Z][A-Z0-9_]*",c) for c in codes))
check("HTTP 状态码合法", all(400<=c["httpStatus"]<=504 for c in reg))
check("状态只能是 documented 或 proposed", all(c["status"] in ("documented","proposed") for c in reg))
check("仅 429 与 503 与 PROJECTION_STALE 可 retryable", all((not c["retryable"]) or c["httpStatus"] in (429,503) or c["code"]=="PROJECTION_STALE" for c in reg))
spec=open(glob.glob(str(root.parents[1]/"docs"/"Titanloom-平台能力契约*.md"))[0] if glob.glob(str(root.parents[1]/"docs"/"Titanloom-平台能力契约*.md")) else glob.glob(str(root.parent/"titanloom"/"Titanloom-平台能力契约*.md"))[0],encoding="utf-8").read()
miss=[c["code"] for c in reg if c["status"]=="documented" and c["code"] not in spec]
check("documented 错误码均出现在能力契约中", not miss)
bad=[]
for c in reg:
    body={"requestId":"r1","error":{"code":c["code"],"messageKey":c["messageKey"],"retryable":c["retryable"],"recoveryAction":c["recoveryAction"]}}
    if not ok("error",body): bad.append(c["code"])
check("注册表中每个错误码都能构造出合法错误体", not bad)
print(f"\n{len(fails)} 项失败" if fails else "\n全部通过"); sys.exit(1 if fails else 0)
