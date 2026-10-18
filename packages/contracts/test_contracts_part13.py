"""契约骨架校验（第十三部分）：M2 考勤与表单的状态机、事件类型登记、表达式函数与用例。
来源：后端详细设计·考勤、后端详细设计·表单（2026-10-18）。运行：python test_contracts_part13.py"""
import json, pathlib, re
root = pathlib.Path(__file__).parent
fails = []
def check(label, cond):
    print(("PASS " if cond else "FAIL ") + label)
    if not cond: fails.append(label)

sm = json.loads((root / "state-machines.json").read_text(encoding="utf-8"))
for name in ["attendanceDeclaration", "attendanceAlertHandling", "attendanceBatch", "attendancePeriod", "formsTask"]:
    m = sm[name]; t = m["transitions"]
    check(f"{name}: 初始状态已定义", all(s in t for s in m["initial"]))
    check(f"{name}: 迁移目标均已定义", all(x in t for v in t.values() for x in v))
    check(f"{name}: 终态无后续迁移", all(t[s] == [] for s in m["terminal"]))
    def reach(s, seen=None):
        seen = seen if seen is not None else set()
        for n in t[s]:
            if n not in seen: seen.add(n); reach(n, seen)
        return seen
    check(f"{name}: 每个状态都能从初始状态到达", all(s in set().union(*[reach(i) | {i} for i in m["initial"]]) for s in t))

d = sm["attendanceDeclaration"]["transitions"]
check("填报：确认后只能经更正重新提交，不能直接改回草稿", d["confirmed"] == ["submitted"])
check("提报批次：已生成只能撤销", sm["attendanceBatch"]["transitions"]["generated"] == ["revoked"])

ev = json.loads((root / "event-types.json").read_text(encoding="utf-8"))["types"]
names = [e["type"] for e in ev]
check("事件类型不重复", len(names) == len(set(names)))
check("事件类型 = 模块.对象.动作", all(re.match(r"^[a-z]+\.[a-z][a-z_]*\.[a-z][a-z_]*$", n) for n in names))
check("每个事件写了说明与出处", all(e.get("desc") and e.get("source") for e in ev))

fn = json.loads((root / "expressions" / "functions.json").read_text(encoding="utf-8"))
cs = json.loads((root / "expressions" / "cases.json").read_text(encoding="utf-8"))["cases"]
known = {f["name"] for f in fn["functions"]}
check("函数名不重复", len(known) == len(fn["functions"]))
check("每个函数有中英显示名", all(f.get("zh") and f.get("en") for f in fn["functions"]))
ids = [c["id"] for c in cs]
check("用例编号不重复", len(ids) == len(set(ids)))
used = {m for c in cs if "expect" in c for m in re.findall(r"([a-zA-Z_]+)\(", c["expr"])}
check("正常用例只用登记的函数", used <= known)
check("每个登记的函数至少一个用例", known <= used)
check("错误用例的错误码都已登记", all(c["expectError"] in fn["errors"] for c in cs if "expectError" in c))
check("数值用例不用 float（十进制字符串）", all(isinstance(c["expect"]["value"], str) for c in cs if "expect" in c))

print(f"\n{len(fails)} 项失败" if fails else "\n全部通过")
