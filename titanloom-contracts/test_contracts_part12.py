"""契约骨架校验（第十二部分）：插件清单、组合版本、我的外壳、稳定链接解析、插件健康。
来源：后端详细设计·插件宿主 · Shell · 平台管理（M1）；插件与扩展体系；Shell 4、5。运行：python test_contracts_part12.py"""
import json, pathlib, copy, sys
from jsonschema import Draft202012Validator
root = pathlib.Path(__file__).parent
names = ["plugin-manifest", "composition-version", "shell-me", "resource-resolve", "plugin-health"]
S = {n: json.loads((root / f"{n}.schema.json").read_text(encoding="utf-8")) for n in names}
for n in S: Draft202012Validator.check_schema(S[n])
def ok(n, d): return not list(Draft202012Validator(S[n]).iter_errors(d))
fails = []
def check(label, cond):
    print(("PASS " if cond else "FAIL ") + label)
    if not cond: fails.append(label)
T = "2026-10-17T01:00:00Z"

m = {"id": "titanloom.forms", "version": "1.0.0", "kind": "domain", "removable": True,
     "requires": {"services": [{"id": "titanloom.access.authz", "range": "^1"}]},
     "provides": {"services": [{"id": "titanloom.forms.records", "version": "1.0.0"}],
                  "extensionPoints": [{"id": "titanloom.forms.field-type", "version": "1.0.0", "cardinality": "many", "thirdParty": False}]},
     "registers": {"features": ["form.create"], "pages": [{"id": "forms.list", "route": "/forms", "devices": ["desktop", "mobile"]}],
                   "nav": [{"slot": "shell.nav.primary", "order": 30, "labelKey": "forms.nav.title"}], "i18n": "i18n/forms.yaml"},
     "drainSec": 60}
check("清单示例（表单）有效", ok("plugin-manifest", m))
x = copy.deepcopy(m); x["kind"] = "core"
check("底座插件不可卸载", not ok("plugin-manifest", x))
x = copy.deepcopy(m); x["drainSec"] = 3600
check("排空时间上限 10 分钟", not ok("plugin-manifest", x))
x = copy.deepcopy(m); x["registers"]["routes"] = ["/anything"]
check("清单外登记类型被拒", not ok("plugin-manifest", x))
x = copy.deepcopy(m); x["registers"]["nav"][0]["labelKey"] = "表单"
check("导航名称用文案键", not ok("plugin-manifest", x))
sk = {"id": "acme.glass-skin", "version": "1.0.0", "kind": "skin", "removable": True, "requires": {}, "provides": {}, "registers": {}}
check("皮肤包清单有效", ok("plugin-manifest", sk))
x = copy.deepcopy(sk); x["provides"] = {"services": [{"id": "acme.glass.api", "version": "1.0.0"}]}
check("皮肤包不能提供服务", not ok("plugin-manifest", x))
x = copy.deepcopy(sk); x["registers"] = {"capabilities": ["titanloom.x.y.z"]}
check("皮肤包不能登记能力", not ok("plugin-manifest", x))

c = {"version": 2, "previous": 1, "createdBy": "p-guyuan", "createdAt": T, "reason": "停用知识模块（试运行期不用）",
     "plugins": [{"id": "titanloom.access", "version": "1.0.0", "kind": "core", "state": "active"},
                 {"id": "titanloom.knowledge", "version": "1.0.0", "kind": "domain", "state": "disabled"}]}
check("组合版本示例有效", ok("composition-version", c))
x = copy.deepcopy(c); x["plugins"][0]["state"] = "disabled"
check("底座不能被停用", not ok("composition-version", x))
x = copy.deepcopy(c); del x["previous"]
check("新版本必须记上一版（可回退）", not ok("composition-version", x))
x = copy.deepcopy(c); x["reason"] = ""
check("原因必填", not ok("composition-version", x))

me = {"person": {"id": "p-linxiao", "name": "林晓"}, "depts": ["dept-assembly-1"], "lang": "zh-CN", "tz": "Asia/Shanghai",
      "scopeMenu": [{"kind": "dept", "id": "dept-assembly-1"}], "currentScope": {"kind": "dept", "id": "dept-assembly-1"}, "scopeEpoch": 1,
      "nav": [{"pageId": "forms.list", "labelKey": "forms.nav.title", "state": "ok", "route": "/forms"},
              {"pageId": "knowledge.home", "labelKey": "knowledge.nav.title", "state": "unavailable"}],
      "features": {"form.create": "requestable", "data.conn": "hidden"}, "homeRef": "/r/shell/home/HP-0003",
      "langPack": {"lang": "zh-CN", "version": "zh-CN@37"}, "badges": {"todo": None, "messages": 2},
      "ring": ["agent", "todo", "support", "feedback", "pick"], "policyRev": 32, "compositionVersion": 2}
check("我的外壳示例（待办来源不可用为 null）有效", ok("shell-me", me))
x = copy.deepcopy(me); x["nav"][1]["state"] = "hidden"
check("不可用的入口不藏，只能标不可用", not ok("shell-me", x))
x = copy.deepcopy(me); x["features"]["form.create"] = "maybe"
check("功能状态只有三种", not ok("shell-me", x))
x = copy.deepcopy(me); x["ring"].append("extra")
check("快捷圈最多五格", not ok("shell-me", x))

r = {"ref": "/r/forms/form/FM-0031", "outcome": "switch_scope", "route": "/forms/FM-0031", "scope": {"kind": "project", "id": "bp-safety"}}
check("链接解析（切范围）有效", ok("resource-resolve", r))
check("链接里不能带部门", not ok("resource-resolve", {"ref": "/r/forms/dept-assembly-1/form/FM-0031", "outcome": "open", "route": "/forms/FM-0031"}))
check("不是你的部门：不泄露名称", not ok("resource-resolve", {"ref": "/r/forms/form/FM-0031", "outcome": "not_your_dept", "title": "装配二部交接班"}))
check("不是你的部门：有效", ok("resource-resolve", {"ref": "/r/forms/form/FM-0031", "outcome": "not_your_dept"}))
check("打开必须给地址", not ok("resource-resolve", {"ref": "/r/forms/form/FM-0031", "outcome": "open"}))

h = {"pluginId": "titanloom.knowledge", "status": "down", "checkedAt": T, "consecutiveDown": 3, "reasonKey": "plugins.health.dbSchema", "since": T}
check("健康：不可用有效", ok("plugin-health", h))
x = copy.deepcopy(h); x["consecutiveDown"] = 1
check("连续 3 次才标不可用", not ok("plugin-health", x))
x = copy.deepcopy(h); del x["reasonKey"]
check("不可用必须写原因", not ok("plugin-health", x))

print(f"\n{'全部通过' if not fails else str(len(fails)) + ' 项失败'}")
sys.exit(1 if fails else 0)
