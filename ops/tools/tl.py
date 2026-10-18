"""Titanloom 开发工具（架构维护；开发项目划分规范 5.4–5.6）。

用法：
    uv run python ops/tools/tl.py scaffold            按 projects.yaml 补齐模块骨架（只补缺的文件，不覆盖）
    uv run python ops/tools/tl.py check [--fast] [--only a,b]   全套门禁（本地与 CI 同一条）
    uv run python ops/tools/tl.py gen                 从正本生成常量（kernel/reg、前端 shared/base/reg）与 plan/CODEMAP.md
    uv run python ops/tools/tl.py status              生成 plan/STATUS.md
    uv run python ops/tools/tl.py wp start|launch|merge <编号> [--agent 名字]   工作包（见 wp.py）

所有规则从 projects.yaml 读，不另写一份。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import checks
import gen
import wp

ROOT = Path(__file__).resolve().parents[2]
API = ROOT / "apps" / "api" / "titanloom"
WEB = ROOT / "apps" / "web" / "src"
LAYERS = ("api", "app", "domain", "store")
LAYER_DOC = {
    "api": "对外口：路由、请求 / 返回结构、能力编号、格式校验、转交。别的模块只能引用这一层。",
    "app": "办事流程：按总图第 2 节顺序调用授权、规则、写库、发事件。",
    "domain": "纯业务规则与状态迁移：不碰数据库、网络、时钟（时间由参数传入）。",
    "store": "本模块的表、读写方法；只读写本模块 schema。",
}


def load_projects() -> dict[str, dict]:
    data = yaml.safe_load((ROOT / "projects.yaml").read_text(encoding="utf-8"))
    return {k: (v or {}) for k, v in data.items()}


def write_if_missing(path: Path, text: str, made: list[Path]) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    made.append(path)


def module_agents_md(name: str, proj: str, info: dict) -> str:
    paths = "\n".join(f"- `{p}`" for p in info.get("paths", []))
    reads = "、".join(info.get("read", [])) or "（只有共同必读）"
    return f"""# {name} 模块 · 执行 Agent 说明

先读仓库根目录 `AGENTS.md`（唯一正本的规则），这里只写本模块的事。本文件由 `tl.py scaffold` 按 `projects.yaml` 生成，改清单请找架构。

- 开发项目：`{proj}`；分支名 `{proj}/<工作包编号>`
- 允许修改的路径（工作包可再收窄）：
{paths}
- 必读（除共同必读外）：{reads}
- 共同必读：工程质量与代码规范全文；后端详细设计·总图全文；国际化规范 1–5、7–9；开发项目划分规范 1、2.2、5、6；总框架 4、5；能力契约 2、3、12。
- 本模块登记的业务参数、功能、页面声明写在 `manifest.yaml`；文案键写在 `i18n/` 下本模块的命名空间文件。
"""


def manifest_yaml(name: str, proj: str) -> str:
    return f"""# {name} 模块描述符（开发项目划分规范 5.5：唯一正本）
# 本模块登记的业务参数、功能（功能开放）、页面声明、对象类型。代码只用 tl.py gen 生成的常量，不手写这些键。
# 新增条目要写清用途；tl.py check 做唯一与相似检查，架构审核后才收。
module: {name}
project: {proj}
db_schema: {name}
params: []      # 业务参数：key、名称、单位、默认值、范围、层级、读取方（后台治理 7.5、ADR-022）
features: []    # 功能开放：id、名称、影响等级、出厂档位、是否归部门 / 项目（后台治理 4.6）
pages: []       # 页面声明：可读视图、页面动作、可搜索操作（工程规范 4.4）
objects: []     # 对象类型：给审计、文件引用、搜索用的类型名
"""


def scaffold() -> int:
    projects = load_projects()
    made: list[Path] = []
    write_if_missing(API / "__init__.py", '"""Titanloom 主程序包（模块化单体，后端详细设计·总图 1、5）。"""\n', made)
    write_if_missing(
        API / "kernel" / "__init__.py", '"""公共内核（架构独占；开发项目划分规范 5.5 第 3 条）。"""\n', made
    )
    for proj, info in projects.items():
        name = info.get("module")
        if not name:
            continue
        base = API / name
        write_if_missing(base / "__init__.py", f'"""{proj} 模块。别的模块只能引用 titanloom.{name}.api。"""\n', made)
        for layer in LAYERS:
            write_if_missing(base / layer / "__init__.py", f'"""{name}.{layer}：{LAYER_DOC[layer]}"""\n', made)
        write_if_missing(
            base / "migrations" / "README.md",
            f"# {name} 迁移\n\n只建本模块 schema `{name}` 里的表；先扩展、迁移校验、再收缩；只前滚（工程规范 4.3）。\n",
            made,
        )
        write_if_missing(base / "tests" / "__init__.py", "", made)
        write_if_missing(base / "manifest.yaml", manifest_yaml(name, proj), made)
        write_if_missing(base / "AGENTS.md", module_agents_md(name, proj, info), made)
        for p in info.get("paths", []):
            if p.startswith("apps/web/src/domains/"):
                write_if_missing(
                    ROOT / p / "index.ts",
                    f"// {proj} 前端领域目录：领域之间不互相导入，只经 Shell 公共接口、路由与契约生成的 SDK（工程规范 2.3）。\nexport {{}};\n",
                    made,
                )
            if p.startswith("i18n/") and p.endswith(".yaml"):
                ns = Path(p).stem
                body = "terms: []\n" if ns == "glossary" else "keys: {}\n"
                head = (
                    f"# 文案键清单与出厂默认文案（国际化规范 3、5.2）。键 = {ns}.页面.区域….名称\nnamespace: {ns}\n"
                    if ns != "glossary"
                    else "# 术语表出厂默认（国际化规范 10）\n"
                )
                write_if_missing(ROOT / p, head + body, made)
    for p in made:
        print("新建", p.relative_to(ROOT).as_posix())
    print(f"共新建 {len(made)} 个文件")
    return 0


MARK = {"ok": "✓", "fail": "✗", "warn": "!", "skip": "–"}


def check(fast: bool, only: list[str]) -> int:
    names = only or (list(checks.FAST) if fast else list(checks.ALL))
    bad = [n for n in names if n not in checks.ALL]
    if bad:
        print("没有这项检查：" + ", ".join(bad), file=sys.stderr)
        return 2
    results = []
    for n in names:
        try:
            r = checks.ALL[n]()
        except Exception as e:  # 检查本身出错也要报出来，不吞掉
            r = checks.Result(n, "fail", [f"检查本身出错：{type(e).__name__}: {e}"])
        results.append(r)
        print(f"{MARK[r.status]} {r.name}" + (f" —— {r.lines[0]}" if r.lines and r.status in ("ok", "skip") else ""))
        if r.status in ("fail", "warn"):
            for line in r.lines:
                print("    " + line)
    fails = [r for r in results if r.status == "fail"]
    warns = [r for r in results if r.status == "warn"]
    try:  # 给状态页用（plan/.last-check.json 不入库）
        import json
        from datetime import UTC, datetime

        wp.LAST.write_text(
            json.dumps(
                {
                    "at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
                    "branch": checks.branch(),
                    "total": len(results),
                    "fail": len(fails),
                    "warn": len(warns),
                    "problems": [f"{MARK[r.status]} {r.name}" for r in results if r.status in ("fail", "warn")],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except OSError:
        pass
    print()
    print(
        f"{'没过' if fails else '通过'}：{len(results)} 项 · ✗ {len(fails)} · ! {len(warns)}（! 是提醒，架构审核时看）"
    )
    return 1 if fails else 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):  # Windows 控制台不是 UTF-8 时也能打出中文和 ✓
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")  # pyright: ignore[reportAttributeAccessIssue]
    ap = argparse.ArgumentParser(prog="tl", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("scaffold", help="按 projects.yaml 补齐模块骨架")
    pc = sub.add_parser("check", help="全套门禁：本地和推送后的 CI 跑同一条")
    pc.add_argument("--fast", action="store_true", help="只跑快的（不跑类型检查、测试、契约测试、前端）")
    pc.add_argument("--only", default="", help="只跑某几项，逗号分隔：" + ",".join(checks.ALL))
    sub.add_parser("gen", help="从正本生成常量与代码地图")
    sub.add_parser("status", help="生成 plan/STATUS.md")
    pw = sub.add_parser("wp", help="工作包：start 建 worktree · launch 打启动指令 · merge 审核通过后合入")
    pw.add_argument("action", choices=["start", "launch", "merge"])
    pw.add_argument("id")
    pw.add_argument("--agent", default=None, help="交给哪个 Agent（start 时记下）")
    args = ap.parse_args(argv)
    if args.cmd == "gen":
        changed = gen.write_all()
        for c in changed:
            print("已更新", c.relative_to(ROOT).as_posix())
        print(f"生成完毕（{len(changed)} 个文件有变化）")
        return 0
    if args.cmd == "status":
        return wp.status()
    if args.cmd == "wp":
        return {
            "start": lambda: wp.start(args.id, args.agent),
            "launch": lambda: wp.launch(args.id),
            "merge": lambda: wp.merge(args.id),
        }[args.action]()
    if args.cmd == "scaffold":
        return scaffold()
    if args.cmd == "check":
        return check(args.fast, [x for x in args.only.split(",") if x])
    print(f"{args.cmd}：还没落成（阶段 A2 / A3）", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
