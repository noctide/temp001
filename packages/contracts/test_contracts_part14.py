"""契约骨架校验（第十四部分）：M3 数据处理的事件登记与查询形状。
来源：后端详细设计·数据处理（2026-10-20）。运行：python test_contracts_part14.py"""
import json, pathlib
root = pathlib.Path(__file__).parent
fails = []
def check(label, cond):
    print(("PASS " if cond else "FAIL ") + label)
    if not cond: fails.append(label)

ev = {e["type"] for e in json.loads((root / "event-types.json").read_text(encoding="utf-8"))["types"]}
for t in ["data.dataset.generation_changed", "data.dataset.stale", "data.run.finished",
          "data.reference.published", "data.quarantine.opened", "data.quarantine.resolved"]:
    check(f"事件已登记：{t}", t in ev)

gc = json.loads((root / "dataset-generation-changed.schema.json").read_text(encoding="utf-8"))
check("代次事件的类型名与登记一致", "data.dataset.generation_changed" in json.dumps(gc, ensure_ascii=False))

try:
    import jsonschema
except ImportError:
    jsonschema = None
rq = json.loads((root / "query-execute-request.schema.json").read_text(encoding="utf-8"))
check("查询请求有 shape（page / aggregate）", rq["properties"]["shape"]["enum"] == ["page", "aggregate"])
check("page 不再是无条件必填", "page" not in rq["required"])
if jsonschema:
    base = {"contractVersion": "1.0.0", "queryVersion": "4", "parameters": {}, "consistency": {"mode": "live"}}
    def ok(x):
        try: jsonschema.validate(x, rq); return True
        except jsonschema.ValidationError: return False
    check("默认形状要带 page", not ok(base) and ok({**base, "page": {"limit": 100}}))
    check("aggregate 不带 page", ok({**base, "shape": "aggregate"}) and not ok({**base, "shape": "aggregate", "page": {"limit": 100}}))
    check("page 每页上限 1000", not ok({**base, "page": {"limit": 1001}}))
else:
    print("SKIP 未安装 jsonschema，跳过实例校验")

print(f"\n{len(fails)} 项失败" if fails else "\n全部通过")
raise SystemExit(1 if fails else 0)
