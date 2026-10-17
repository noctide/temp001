"""契约骨架校验（第七部分）：国际化——键名、错误码文案键、键清单、语言包、LocalizedText。
来源：国际化与本地化规范 3–7。运行：python test_contracts_part7.py"""
import json, pathlib, copy, sys, re
from jsonschema import Draft202012Validator
root = pathlib.Path(__file__).parent
names = ["error", "prepare-result", "i18n-key-manifest", "language-pack", "localized-text"]
S = {n: json.loads((root / f"{n}.schema.json").read_text(encoding="utf-8")) for n in names}
for n in S: Draft202012Validator.check_schema(S[n])
def ok(n, d): return not list(Draft202012Validator(S[n]).iter_errors(d))
fails = []
def check(label, cond):
    print(("PASS " if cond else "FAIL ") + label)
    if not cond: fails.append(label)

# ---- 错误码注册表：每个码都有由错误码机械推导的文案键，且唯一
reg = json.loads((root / "error-codes.json").read_text(encoding="utf-8"))["codes"]
def derive(code):
    p = code.lower().split("_"); return "errors." + p[0] + "".join(x.capitalize() for x in p[1:])
check("每个错误码都有 messageKey", all("messageKey" in c for c in reg))
check("messageKey 由错误码机械推导", all(c["messageKey"] == derive(c["code"]) for c in reg))
check("messageKey 不重复", len({c["messageKey"] for c in reg}) == len(reg))
key_pat = re.compile(S["error"]["$defs"]["errorBody"]["properties"]["messageKey"]["pattern"])
check("错误码文案键符合错误体 Schema 的键名格式", key_pat is not None and all(key_pat.match(c["messageKey"]) for c in reg))

# ---- 键名格式（准备结果中的通用键）
pr_key = None
def find_pat(o):
    global pr_key
    if isinstance(o, dict):
        mk = o.get("properties", {}).get("messageKey")
        if isinstance(mk, dict) and "pattern" in mk: pr_key = re.compile(mk["pattern"])
        for v in o.values(): find_pat(v)
    elif isinstance(o, list):
        for v in o: find_pat(v)
find_pat(S["prepare-result"])
check("通用键名：命名空间.路径 一层一层 合法", pr_key is not None and all(pr_key.match(k) for k in
      ["dataproc.pipelineRun.preview", "attendance.schedule.publishConfirm", "common.save", "plugin.acme-gauge.settings.title"]))
check("通用键名：只有一段被拒", not pr_key.match("save"))
check("通用键名：冒号格式被拒", not pr_key.match("attendance:schedule.publishConfirm"))
check("通用键名：大写开头的段被拒", not pr_key.match("attendance.Schedule.publish"))
check("通用键名：以显示文字为键被拒", not pr_key.match("attendance.确定"))

# ---- 键清单
mf = {"namespace": "attendance", "keys": {
    "schedule.publishConfirm": {"description": "发布排班前的确认", "critical": True,
        "params": {"count": "number", "month": "date"},
        "defaults": {"zh-CN": "确认发布 {{month, date}} 的 {{count, number}} 条排班？",
                     "en-US": {"one": "Publish {{count, number}} shift for {{month, date}}?",
                               "other": "Publish {{count, number}} shifts for {{month, date}}?"}}},
    "schedule.title": {"description": "排班页标题", "defaults": {"zh-CN": "排班", "en-US": "Schedules"}}}}
check("键清单有效", ok("i18n-key-manifest", mf))
x = copy.deepcopy(mf); del x["keys"]["schedule.title"]["defaults"]["en-US"]
check("出厂默认文案必须同时有 zh-CN 与 en-US", not ok("i18n-key-manifest", x))
x = copy.deepcopy(mf); x["keys"]["schedule.title"]["defaults"]["en-US"] = {"one": "Schedule"}
check("复数形式必须有 other", not ok("i18n-key-manifest", x))
x = copy.deepcopy(mf); x["keys"]["Schedule.Title"] = x["keys"].pop("schedule.title")
check("键路径须小驼峰分段", not ok("i18n-key-manifest", x))
x = copy.deepcopy(mf); del x["keys"]["schedule.title"]["description"]
check("每个键须有用途说明", not ok("i18n-key-manifest", x))

def params_in(s): return set(re.findall(r"\{\{\s*([a-zA-Z0-9]+)", s))
def texts(v): return [v] if isinstance(v, str) else list(v.values())
consistent = True
for k, d in mf["keys"].items():
    zh = set().union(*[params_in(t) for t in texts(d["defaults"]["zh-CN"])])
    for t in texts(d["defaults"]["en-US"]):
        if params_in(t) != zh: consistent = False
    if "params" in d and zh and set(d["params"]) != zh: consistent = False
check("示例清单：中英文参数集合一致且与登记参数一致", consistent)

# ---- 语言包
lp = {"packId": "lp_zh", "version": 3, "locale": "zh-CN", "state": "active", "criticalComplete": True,
      "namespaces": {"attendance": {"schedule.title": "排班", "schedule.publishConfirm": "确认发布？"},
                     "errors": {"resourceVersionConflict": "资源已被他人修改"}},
      "publishedAt": "2026-10-03T08:00:00Z"}
check("已激活语言包有效", ok("language-pack", lp))
x = copy.deepcopy(lp); x["criticalComplete"] = False; x["missingKeys"] = ["attendance.schedule.publishConfirm"]
check("关键文案缺失的语言包不得处于 active", not ok("language-pack", x))
x["state"] = "published"
check("关键文案缺失的语言包可发布但不激活", ok("language-pack", x))
x = copy.deepcopy(lp); x["namespaces"]["attendance"]["shift_other"] = "{{count}} shifts"
check("复数后缀键合法", ok("language-pack", x))
x = copy.deepcopy(lp); x["namespaces"]["Attendance"] = {}
check("命名空间须小写", not ok("language-pack", x))

# ---- LocalizedText
check("LocalizedText 有效", ok("localized-text", {"zh-CN": "部门", "en-US": "Department"}))
check("LocalizedText 只有中文有效（英文回退中文）", ok("localized-text", {"zh-CN": "部门"}))
check("LocalizedText 必须有 zh-CN", not ok("localized-text", {"en-US": "Department"}))
check("LocalizedText 语言标签须为 BCP 47", not ok("localized-text", {"zh-CN": "部门", "english": "Department"}))
check("LocalizedText 值不得为空", not ok("localized-text", {"zh-CN": ""}))

print(f"\n{'全部通过' if not fails else '失败 %d 项' % len(fails)}")
sys.exit(1 if fails else 0)
