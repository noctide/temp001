"""契约骨架校验（第六部分）：FieldRef、Query 可筛选声明、按 FieldRef 筛选、数据代次。
来源：数据处理 12.6、能力契约 9.1、可视化 8.2–8.3。运行：python test_contracts_part6.py"""
import json, pathlib, copy, sys
from jsonschema import Draft202012Validator
root = pathlib.Path(__file__).parent
names = ["query-execute-request", "query-execute-response", "field-ref", "query-filterable",
         "dataset-generation-changed", "outbox-event"]
S = {n: json.loads((root / f"{n}.schema.json").read_text(encoding="utf-8")) for n in names}
for n in S: Draft202012Validator.check_schema(S[n])
def ok(n, d): return not list(Draft202012Validator(S[n]).iter_errors(d))
fails = []
def check(label, cond):
    print(("PASS " if cond else "FAIL ") + label)
    if not cond: fails.append(label)

# ---- Query 请求：按 FieldRef 筛选（能力契约 9.1 示例）
rq = {"contractVersion": "1.0.0", "queryVersion": "4", "parameters": {"month": "2026-09"},
      "filters": [{"field": "fld_department", "op": "in", "values": ["dept_05"]}],
      "page": {"limit": 100, "cursor": None},
      "consistency": {"mode": "snapshot", "snapshotId": "snap_hours_202609"}}
check("Query 请求带 filters 有效(规范 9.1 示例)", ok("query-execute-request", rq))
x = copy.deepcopy(rq); del x["filters"]
check("不带 filters 仍有效(向后兼容)", ok("query-execute-request", x))
x = copy.deepcopy(rq); x["filters"][0]["field"] = "department"
check("筛选字段必须是 FieldRef（fld_ 前缀）", not ok("query-execute-request", x))
x = copy.deepcopy(rq); x["filters"][0] = {"field": "fld_department", "op": "in"}
check("in 必须带 values", not ok("query-execute-request", x))
x = copy.deepcopy(rq); x["filters"][0] = {"field": "fld_department", "op": "in", "values": []}
check("in 的 values 不得为空", not ok("query-execute-request", x))
x = copy.deepcopy(rq); x["filters"][0] = {"field": "fld_work_date", "op": "range", "from": "2026-09-01", "to": "2026-10-01"}
check("range 带 from/to 有效（左闭右开）", ok("query-execute-request", x))
x = copy.deepcopy(rq); x["filters"][0] = {"field": "fld_work_date", "op": "range"}
check("range 至少带 from 或 to", not ok("query-execute-request", x))
x = copy.deepcopy(rq); x["filters"][0] = {"field": "fld_work_date", "op": "range", "from": "2026-09-01", "values": ["x"]}
check("range 不得混用 values", not ok("query-execute-request", x))
x = copy.deepcopy(rq); x["filters"][0] = {"field": "fld_work_date", "op": "relative", "value": "last_7_days"}
check("relative 用令牌由服务端解析，有效", ok("query-execute-request", x))
x = copy.deepcopy(rq); x["filters"][0] = {"field": "fld_work_date", "op": "relative", "value": "2026-09-01/2026-10-01"}
check("relative 不接受调用方拼接的区间", not ok("query-execute-request", x))
x = copy.deepcopy(rq); x["filters"][0] = {"field": "fld_department", "op": "eq", "value": "dept_05", "sql": "1=1"}
check("筛选项不接受额外字段（如 SQL 片段）", not ok("query-execute-request", x))
x = copy.deepcopy(rq); x["filters"][0] = {"field": "fld_department", "op": "like", "value": "%"}
check("不支持的操作被拒", not ok("query-execute-request", x))

# ---- Query 响应：dataGeneration 与列 fieldRef
rs = {"requestId": "req_002", "data": {"queryId": "q_hours", "queryVersion": "4", "datasetVersion": "32",
      "dataGeneration": 57, "snapshotId": "snap_hours_202609",
      "sourceWatermarks": [{"sourceId": "src_hours", "version": "batch_88"}],
      "dataAsOf": "2026-09-26T09:00:00Z", "qualityStatus": "passed",
      "columns": [{"name": "employeeId", "type": "string", "fieldRef": "fld_employee"},
                  {"name": "hours", "type": "decimal", "scale": 2, "encoding": "string"}],
      "rows": [{"employeeId": "000123", "hours": "168.50"}], "nextCursor": None, "truncated": False}}
check("Query 响应带 dataGeneration 与 fieldRef 有效(规范 9.1 示例)", ok("query-execute-response", rs))
x = copy.deepcopy(rs); x["data"]["dataGeneration"] = -1
check("dataGeneration 不得为负", not ok("query-execute-response", x))
x = copy.deepcopy(rs); x["data"]["columns"][0]["fieldRef"] = "employee"
check("列 fieldRef 必须是 FieldRef 格式", not ok("query-execute-response", x))

# ---- FieldRef
fr = {"id": "fld_work_date", "label": {"zh-CN": "工作日期", "en-US": "Work date"}, "dataType": "date", "grain": "day",
      "timezone": "Asia/Shanghai", "domain": "attendance", "owner": "role_data_owner", "version": 1, "status": "active"}
check("日期型 FieldRef 有效", ok("field-ref", fr))
x = copy.deepcopy(fr); del x["timezone"]
check("日期型 FieldRef 必须声明业务时区", not ok("field-ref", x))
x = copy.deepcopy(fr); del x["grain"]
check("日期型 FieldRef 必须声明粒度", not ok("field-ref", x))
x = copy.deepcopy(fr); x["status"] = "deprecated"
check("废弃 FieldRef 必须给出替代项", not ok("field-ref", x))
x["replacedBy"] = "fld_work_day"
check("废弃并给出替代项有效", ok("field-ref", x))
x = copy.deepcopy(fr); x["options"] = {"queryId": "q_opts", "dictionaryRef": "dict_x"}
check("选项来源只能二选一", not ok("field-ref", x))
x = {"id": "fld_department", "label": {"zh-CN": "部门"}, "dataType": "string", "permissionDimension": True,
     "domain": "platform", "owner": "role_md", "version": 2, "status": "active", "options": {"queryId": "q_dept_options"}}
check("字符串型 FieldRef 无需时区", ok("field-ref", x))

# ---- Query 可筛选声明
qf = {"queryId": "q_hours", "queryVersion": "4", "derivation": "semantic", "grain": "day",
      "filterable": [{"fieldRef": "fld_department", "param": "department", "operators": ["eq", "in"], "maxValues": 50},
                     {"fieldRef": "fld_work_date", "param": "workDate", "operators": ["range", "relative"], "required": True}]}
check("语义层推导的可筛选声明有效", ok("query-filterable", qf))
x = copy.deepcopy(qf); x["derivation"] = "declared"
check("手写 SQL 的声明必须给出参数绑定位置", not ok("query-filterable", x))
for item in x["filterable"]: item["sqlBinding"] = ":" + item["param"]
check("手写 SQL 声明带绑定位置有效", ok("query-filterable", x))
x = copy.deepcopy(qf); x["filterable"][0]["operators"] = []
check("至少声明一种操作", not ok("query-filterable", x))
x = copy.deepcopy(qf); x["filterable"][0]["operators"] = ["eq", "eq"]
check("操作不得重复", not ok("query-filterable", x))

# ---- 数据代次事件：载荷与事件信封
gp = {"datasetId": "ds_hours", "generation": 58, "previousGeneration": 57, "datasetVersion": "33",
      "changeKind": "publish", "dataAsOf": "2026-09-27T09:00:00Z",
      "sourceWatermarks": [{"sourceId": "src_hours", "version": "batch_89"}], "qualityResult": "passed"}
check("代次变化载荷有效", ok("dataset-generation-changed", gp))
x = copy.deepcopy(gp); x["changeKind"] = "rollback"; x["datasetVersion"] = "31"; x["generation"] = 59; x["previousGeneration"] = 58
check("回退也递增代次，有效", ok("dataset-generation-changed", x))
x = copy.deepcopy(gp); x["qualityResult"] = "blocked"
check("blocked 批次不发布，不产生代次事件", not ok("dataset-generation-changed", x))
x = copy.deepcopy(gp); x["rows"] = [{"hours": "1"}]
check("代次事件不得携带数据行", not ok("dataset-generation-changed", x))
x = copy.deepcopy(gp); x["generation"] = 0
check("代次从 1 起", not ok("dataset-generation-changed", x))
ev = {"eventId": "evt_1", "type": "data.dataset.generation_changed", "schemaVersion": 1, "source": "data",
      "scope": "w1", "subject": {"type": "Dataset", "id": "ds_hours"}, "sourceVersion": "33",
      "occurredAt": "2026-09-27T09:00:00Z", "recordedAt": "2026-09-27T09:00:01Z", "correlationId": "c1"}
check("代次事件信封类型名合法", ok("outbox-event", ev))
# 一致性：载荷只允许已发布的质量结论，与 Query 响应的 qualityStatus 取值一致
check("代次载荷与 Query 响应的质量取值集合一致",
      set(S["dataset-generation-changed"]["properties"]["qualityResult"]["enum"]) ==
      set(S["query-execute-response"]["properties"]["data"]["properties"]["qualityStatus"]["enum"]))

print(f"\n{'全部通过' if not fails else '失败 %d 项' % len(fails)}")
sys.exit(1 if fails else 0)
