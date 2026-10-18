"""工作包与进度（开发项目划分规范 5.4、5.6）。

plan/wp/<编号>.md 是工作包正本，开头一段 YAML：
    ---
    id: M0-07
    project: contracts
    title: 错误码文案
    status: 待派        # 待派 · 执行中 · 待审 · 返工 · 已合本地 · 已推送
    agent:              # 交给了谁（opencode / Codex / DeepSeek Harness …）
    depends: []
    size: 200           # 预计改动行数（不含测试），超过约 400 拆
    ---
后面是正文：目标、设计依据、图、接口、验收、允许路径、不做的事；审核意见也记在这里。

    tl.py wp start <编号>    （在维护者的 Windows 上跑：worktree 记的是本机绝对路径）建 worktree ../wt/<编号>（分支 <项目>/<编号>，从 local/integration 切出）、写 plan/progress/<编号>.md、状态 → 执行中
    tl.py wp launch <编号>   打出给执行 Agent 的启动指令（贴进 opencode / Codex / DeepSeek Harness）
    tl.py wp merge <编号> --keep   一个阶段审核通过：保留历史合入 local/integration，worktree 继续（2026-10-18：一个开发项目一个 Agent，按阶段审核）
    tl.py wp merge <编号>    整个里程碑做完：压成一个提交合入、删 worktree、状态 → 已合本地
    tl.py status             生成 plan/STATUS.md
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
WP = ROOT / "plan" / "wp"
WT = ROOT.parent / "wt"
API = ROOT / "apps" / "api" / "titanloom"
INTEGRATION = "local/integration"
STATES = ["待派", "执行中", "待审", "返工", "已合本地", "已推送"]
LAST = ROOT / "plan" / ".last-check.json"


def git(*args: str, cwd: Path = ROOT) -> str:
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")  # noqa: S603, S607
    if p.returncode:
        raise SystemExit(f"git {' '.join(args)} 失败：{p.stderr.strip()}")
    return p.stdout.strip()


def read(wid: str) -> tuple[dict[str, Any], str, Path]:
    f = WP / f"{wid}.md"
    if not f.exists():
        raise SystemExit(f"没有工作包 {wid}（plan/wp/{wid}.md）")
    text = f.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not m:
        raise SystemExit(f"{wid}：开头缺 YAML 段（--- … ---）")
    return yaml.safe_load(m.group(1)) or {}, m.group(2), f


def write(meta: dict[str, Any], body: str, f: Path) -> None:
    head = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False).strip()
    f.write_text(f"---\n{head}\n---\n{body}", encoding="utf-8", newline="\n")


def set_status(wid: str, status: str, **extra: Any) -> None:
    meta, body, f = read(wid)
    meta["status"] = status
    meta.update({k: v for k, v in extra.items() if v is not None})
    write(meta, body, f)


def projects() -> dict[str, dict[str, Any]]:
    return yaml.safe_load((ROOT / "projects.yaml").read_text(encoding="utf-8"))


def start(wid: str, agent: str | None) -> int:
    meta, _, _ = read(wid)
    proj = meta["project"]
    branch = f"{proj}/{wid}"
    path = WT / wid
    if path.exists():
        raise SystemExit(f"{path} 已经存在")
    git("worktree", "add", str(path), "-b", branch, INTEGRATION)
    prog = path / "plan" / "progress" / f"{wid}.md"  # 每个项目一份，合入时不和别的项目冲突
    prog.parent.mkdir(parents=True, exist_ok=True)
    prog.write_text(
        f"# {wid} 进度（断点续做：每完成一步更新；上下文满了换新会话照着接着做）\n\n"
        f"- 工作包：plan/wp/{wid}.md\n- 分支：{branch}\n\n## 做到哪\n\n（还没开始）\n\n## 下一步\n\n1. 读工作包和必读\n\n## 问题 / 变更请求\n\n（无）\n",
        encoding="utf-8",
        newline="\n",
    )
    set_status(wid, "执行中", agent=agent, started=datetime.now(UTC).strftime("%Y-%m-%d %H:%M"))
    print(f"已建 worktree {path}（分支 {branch}）。启动指令：")
    return launch(wid)


def launch(wid: str) -> int:
    meta, _, _ = read(wid)
    proj = meta["project"]
    info = projects().get(proj) or {}
    reads = "、".join(info.get("read") or []) or "（只有共同必读）"
    path = WT / wid
    mod_doc = (
        f"apps/api/titanloom/{info['module']}/AGENTS.md" if info.get("module") else "本项目目录的 AGENTS.md（如有）"
    )
    print(
        f"""你是 Titanloom 项目的执行 Agent，负责工作包 {wid}「{meta.get("title", "")}」。

工作目录：{path}（已在分支 {proj}/{wid}，从 local/integration 切出）。

先读，按顺序：
1. 仓库根目录 AGENTS.md（规则唯一正本），再读 {mod_doc}
2. 工作包 plan/wp/{wid}.md（目标、依据、验收、允许路径、不做的事）
3. plan/CODEMAP.md 里本模块和要调用的模块那一段——已经有的就用，不要再写一份
4. 本项目必读：{reads}
5. plan/progress/{wid}.md（上次做到哪、审核意见怎么改）

做完：uv run python ops/tools/tl.py check 全部通过（✗ 0），最后一条提交写自查结果；只在本地提交（git commit -s，末尾 Agent: <你的工具名>），不推送、不合并。
按说明书的阶段一个一个做；**每做完一个阶段**回复一句"{wid} 阶段 N 做完了"，列出改了哪些文件、测试结果，等审核通过再做下一阶段。设计里没写、拿不准的，停下来写进 plan/progress/{wid}.md 告诉我。"""
    )
    return 0


def merge(wid: str, keep: bool = False) -> int:
    meta, _, _ = read(wid)
    proj = meta["project"]
    branch = f"{proj}/{wid}"
    if git("rev-parse", "--abbrev-ref", "HEAD") != INTEGRATION:
        raise SystemExit(f"先切到 {INTEGRATION}")
    if git("status", "--porcelain"):
        raise SystemExit("hq 里有没提交的改动，先处理")
    if keep:  # 阶段合入：保留历史，分支与 worktree 继续用
        stage = int(meta.get("stage") or 0) + 1
        git("merge", "--no-ff", "-m", f"{proj}: {meta.get('title', wid)} · 阶段 {stage}（架构审核通过）", branch)
        set_status(wid, "执行中", stage=stage)
        git("add", f"plan/wp/{wid}.md")
        git("commit", "-m", f"plan: {wid} 阶段 {stage} 已合本地")
        print(f"{wid} 阶段 {stage} 已合入 {INTEGRATION}；worktree 继续")
        return 0
    git("merge", "--squash", branch)
    log = git("log", "--format=%s%n%b", f"{INTEGRATION}..{branch}")
    agents = sorted(set(re.findall(r"^Agent:\s*(.+)$", log, re.M)))
    msg = f"{proj}: {meta.get('title', wid)}（工作包 {wid}，架构审核通过）\n\n" + "\n".join(
        f"- {x}" for x in git("log", "--format=%s", f"{INTEGRATION}..{branch}").splitlines()
    )
    if agents:
        msg += "\n\nAgent: " + ", ".join(agents)
    git("commit", "-s", "-m", msg)
    try:  # worktree 在 Windows 上建的，这里删不掉时让维护者在 Windows 上删
        if (WT / wid).exists():
            git("worktree", "remove", "--force", str(WT / wid))
        git("branch", "-D", branch)
    except SystemExit as e:
        print(
            f"（worktree / 分支没删掉：{e}；在建它的那台电脑上跑 git worktree remove ../wt/{wid} 和 git branch -D {branch}）"
        )
    set_status(wid, "已合本地", merged=datetime.now(UTC).strftime("%Y-%m-%d %H:%M"))
    git("add", f"plan/wp/{wid}.md")
    git("commit", "-m", f"plan: {wid} 已合本地")
    print(f"{wid} 已合入 {INTEGRATION}")
    return 0


# ---------------------------------------------------------------- 状态页
def _module_stats(m: str) -> tuple[int, int, int]:
    loc = tests = files = 0
    for f in (API / m).rglob("*.py"):
        text = f.read_text(encoding="utf-8")
        if "tests" in f.parts:
            tests += len(re.findall(r"^\s*(?:async\s+)?def test_", text, re.M))
        else:
            files += 1
            loc += sum(1 for x in text.splitlines() if x.strip() and not x.strip().startswith("#"))
    return loc, tests, files


def status() -> int:
    wps: list[dict[str, Any]] = []
    for f in sorted(WP.glob("*.md")):
        try:
            meta, _, _ = read(f.stem)
        except SystemExit:
            continue
        wps.append(meta)
    by = {s: [w for w in wps if w.get("status") == s] for s in STATES}
    lines = [
        "# 进度",
        "",
        f"由 `tl.py status` 生成（{datetime.now(UTC).strftime('%Y-%m-%d %H:%M')} UTC），不要手改。",
        "",
        "## 工作包",
        "",
        " · ".join(f"{s} {len(by[s])}" for s in STATES),
        "",
        "| 编号 | 项目 | 标题 | 状态 | 谁在做 | 依赖 | 预计行数 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for w in sorted(
        wps, key=lambda x: (STATES.index(x.get("status", "待派")) if x.get("status") in STATES else 9, str(x.get("id")))
    ):
        lines.append(
            f"| {w.get('id')} | {w.get('project')} | {w.get('title', '')} | {w.get('status', '')} | {w.get('agent') or ''} | "
            f"{', '.join(map(str, w.get('depends') or []))} | {w.get('size', '')} |"
        )
    lines += ["", "## 模块规模", "", "| 模块 | 代码行（不含测试） | 文件 | 测试数 |", "| --- | --- | --- | --- |"]
    mods = sorted(v["module"] for v in projects().values() if v and v.get("module"))
    for m in ["kernel", *mods]:
        loc, tests, files = _module_stats(m)
        lines.append(f"| {m} | {loc} | {files} | {tests} |")
    lines += ["", "## 最近一次 tl check", ""]
    if LAST.exists():
        last = json.loads(LAST.read_text(encoding="utf-8"))
        lines.append(
            f"{last['at']} · 分支 {last['branch']} · ✗ {last['fail']} · ! {last['warn']} · 共 {last['total']} 项"
        )
        lines += [f"- {x}" for x in last.get("problems", [])]
    else:
        lines.append("（还没跑过）")
    (ROOT / "plan" / "STATUS.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("已生成 plan/STATUS.md")
    return 0
