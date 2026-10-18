"""tl check 的各项检查（开发项目划分规范 5.5、6；工程质量与代码规范 9）。

每项返回 Result(name, status, lines)：status ∈ ok / fail / warn / skip。
规则只从 projects.yaml、各模块 manifest.yaml、i18n/、packages/contracts 读，不另写一份。
"""

from __future__ import annotations

import ast
import difflib
import hashlib
import itertools
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
API = ROOT / "apps" / "api" / "titanloom"
WEB = ROOT / "apps" / "web"
CONTRACTS = ROOT / "packages" / "contracts"
INTEGRATION = "local/integration"
# 执行 Agent 在 worktree 里总能改的文件
ALWAYS_OK = ("PROGRESS.md",)  # 旧位置：只为搬家那次提交放行（2026-10-18 起进度文件在 plan/progress/<编号>.md）


@dataclass
class Result:
    name: str
    status: str = "ok"
    lines: list[str] = field(default_factory=list)

    def fail(self, msg: str) -> None:
        self.status = "fail"
        self.lines.append(msg)

    def warn(self, msg: str) -> None:
        if self.status == "ok":
            self.status = "warn"
        self.lines.append(msg)


def projects() -> dict[str, dict]:
    data = yaml.safe_load((ROOT / "projects.yaml").read_text(encoding="utf-8"))
    return {k: (v or {}) for k, v in data.items()}


def modules() -> dict[str, str]:
    """包名 → 项目名"""
    return {v["module"]: k for k, v in projects().items() if v.get("module")}


def run(cmd: list[str], cwd: Path = ROOT) -> tuple[int, str]:
    # Windows 控制台默认不是 UTF-8：子进程统一按 UTF-8 读写（中文输出、读配置文件）
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)  # noqa: S603
    return p.returncode, (p.stdout + p.stderr).strip()


def tail(text: str, n: int = 12) -> list[str]:
    return text.splitlines()[-n:]


# ---------------------------------------------------------------- 外部工具
PY_TARGETS = ["apps/api", "ops/tools", "ops/synthetic-data"]


def c_ruff() -> Result:
    r = Result("格式与静态检查（ruff）")
    code, out = run([sys.executable, "-m", "ruff", "check", "--output-format", "concise", *PY_TARGETS])
    if code:
        r.fail("ruff check 没过：")
        r.lines += tail(out, 20)
    code, out = run([sys.executable, "-m", "ruff", "format", "--check", *PY_TARGETS])
    if code:
        r.fail("格式不对（跑 uv run ruff format 修）：")
        r.lines += [x for x in out.splitlines() if "reformat" in x.lower()][:20]
    return r


def c_pyright() -> Result:
    r = Result("类型检查（pyright strict）")
    exe = shutil.which("pyright", path=str(Path(sys.executable).parent))
    cmd = [exe] if exe else [sys.executable, "-m", "pyright"]
    code, out = run(cmd)
    if code:
        r.fail("pyright 有错：")
        r.lines += [x.strip() for x in out.splitlines() if " - error" in x][:25] or tail(out)
    return r


def c_pytest() -> Result:
    r = Result("测试（pytest）")
    code, out = run([sys.executable, "-m", "pytest", "-p", "no:cacheprovider"])
    last = [x.strip() for x in out.splitlines() if re.search(r"\d+ (passed|failed|error)", x)][-1:] or tail(out, 1)
    if code and code != 5:
        r.fail("测试没过：")
        r.lines += tail(out, 25)
    else:
        r.lines += last
    return r


def c_contracts() -> Result:
    r = Result("契约测试（packages/contracts）")
    tests = sorted(CONTRACTS.glob("test_*.py"))
    bad = []
    for t in tests:
        code, out = run([sys.executable, t.name], cwd=CONTRACTS)
        if code or not out.endswith("全部通过"):
            bad.append(f"{t.name}：{tail(out, 1)[0] if out else code}")
    if bad:
        for b in bad:
            r.fail(b)
    else:
        r.lines.append(f"{len(tests)} 个文件全部通过")
    return r


def c_web() -> Result:
    r = Result("前端类型检查（tsc）")
    if not (WEB / "node_modules").exists():
        r.status = "skip"
        r.lines.append("没装前端依赖（pnpm install）——跳过")
        return r
    # 直接用项目里装的 tsc，不经 pnpm（各版本 pnpm 的命令行参数不一样）
    tsc = shutil.which("tsc", path=str(WEB / "node_modules" / ".bin"))
    if not tsc:
        r.status = "skip"
        r.lines.append("apps/web/node_modules/.bin 里没有 tsc（pnpm install）——跳过")
        return r
    code, out = run([tsc, "-p", "tsconfig.json", "--noEmit"], cwd=WEB)
    if code and "MODULE_NOT_FOUND" in out:
        r.status = "skip"
        r.lines.append("前端依赖是另一个系统装的（例如 Windows 装、这里是 Linux）——跳过，在装依赖的那台机器上跑")
        return r
    if code:
        r.fail("tsc 有错：")
        r.lines += tail(out, 20)
    return r


# ---------------------------------------------------------------- 模块边界
DOMAIN_FORBIDDEN_EXT = ["sqlalchemy", "fastapi", "starlette", "psycopg", "httpx", "httpx2", "alembic", "uvicorn"]


def importlinter_config() -> str:
    mods = sorted(modules())
    lines = ["[importlinter]", "root_package = titanloom", "include_external_packages = True", ""]
    n = 0
    for m in mods:
        others = [f"titanloom.{o}.{layer}" for o in mods if o != m for layer in ("app", "domain", "store")]
        n += 1
        lines += [
            f"[importlinter:contract:{n}]",
            f"name = {m} 只能引用别的模块的 api 层与 kernel",
            "type = forbidden",
            f"source_modules = titanloom.{m}",
            "forbidden_modules =",
            *[f"    {o}" for o in others],
            "",
        ]
    n += 1
    lines += [
        f"[importlinter:contract:{n}]",
        "name = kernel 不引用任何业务模块",
        "type = forbidden",
        "source_modules = titanloom.kernel",
        "forbidden_modules =",
        *[f"    titanloom.{m}" for m in mods],
        "",
    ]
    n += 1
    lines += [
        f"[importlinter:contract:{n}]",
        "name = domain 层是纯业务规则：不碰数据库、网络、Web 框架",
        "type = forbidden",
        "source_modules =",
        *[f"    titanloom.{m}.domain" for m in mods],
        "forbidden_modules =",
        *[f"    {e}" for e in DOMAIN_FORBIDDEN_EXT],
        "",
    ]
    return "\n".join(lines)


def c_boundaries() -> Result:
    r = Result("模块边界（import-linter，按 projects.yaml 生成）")
    with tempfile.NamedTemporaryFile("w", suffix=".ini", delete=False, encoding="utf-8") as f:
        f.write(importlinter_config())
        cfg = f.name
    exe = shutil.which("lint-imports", path=str(Path(sys.executable).parent)) or "lint-imports"
    env_path = str(ROOT / "apps" / "api")
    old = os.environ.get("PYTHONPATH")
    os.environ["PYTHONPATH"] = env_path + (os.pathsep + old if old else "")
    try:
        code, out = run([exe, "--config", cfg, "--no-cache"])
    finally:
        os.unlink(cfg)
        if old is None:
            os.environ.pop("PYTHONPATH", None)
        else:
            os.environ["PYTHONPATH"] = old
    if code:
        r.fail("有越界的引用：")
        r.lines += [x for x in out.splitlines() if x.strip() and ("->" in x or "BROKEN" in x or "-" in x[:3])][
            :30
        ] or tail(out, 30)
    else:
        kept = re.search(r"Contracts: (\d+) kept", out)
        r.lines.append(f"{kept.group(1) if kept else '?'} 条约定都守住了")
    return r


# ---------------------------------------------------------------- 范围
def git(*args: str) -> str:
    code, out = run(["git", *args])
    return out if code == 0 else ""


def branch() -> str:
    return git("rev-parse", "--abbrev-ref", "HEAD")


def changed_files() -> list[str]:
    base = git("merge-base", "HEAD", INTEGRATION)
    files: set[str] = set()
    if base:
        files.update(x for x in git("diff", "--name-only", f"{base}...HEAD").splitlines() if x)
    files.update(x for x in git("diff", "--name-only", "HEAD").splitlines() if x)
    files.update(x for x in git("ls-files", "--others", "--exclude-standard").splitlines() if x)
    return sorted(files)


def wp_extra_paths(wp: str) -> list[str]:
    # 额外放行只认集成分支上的说明书（架构写的），工作分支自己加的 allow 不算
    text = git("show", f"{INTEGRATION}:plan/wp/{wp}.md")
    if not text:
        return []
    m = re.search(r"<!--\s*allow:\s*(.+?)\s*-->", text, re.S)
    return [x.strip() for x in m.group(1).split(",")] if m else []


def allowed(path: str, prefixes: list[str]) -> bool:
    for p in prefixes:
        if p.endswith("/") and path.startswith(p):
            return True
        if path == p or fnmatch(path, p):
            return True
    return path in ALWAYS_OK


def c_scope() -> Result:
    r = Result("改动范围（只改本项目允许的路径）")
    b = branch()
    proj, _, wp = b.partition("/")
    P = projects()
    if b in (INTEGRATION, "main", "HEAD", "") or proj not in P or not wp:
        r.status = "skip"
        r.lines.append(f"当前分支 {b or '?'} 不是工作包分支（<项目>/<编号>）——跳过")
        return r
    if P[proj].get("owner") == "arch":
        r.status = "skip"
        r.lines.append("架构分支——不限范围")
        return r
    prefixes = list(P[proj].get("paths", [])) + wp_extra_paths(wp) + [f"plan/progress/{wp}.md"]
    out = [f for f in changed_files() if not allowed(f, prefixes)]
    if out:
        r.fail(f"项目 {proj} 不该改这些文件（要改请提变更请求）：")
        r.lines += [f"  {f}" for f in out[:30]]
    else:
        r.lines.append(f"项目 {proj} · 工作包 {wp}：改动都在允许路径内")
    return r


# ---------------------------------------------------------------- 文案键
KEY_SEG = re.compile(r"^[a-z][A-Za-z0-9]*$")


def i18n_keys() -> dict[str, dict]:
    keys: dict[str, dict] = {}
    for f in sorted((ROOT / "i18n").glob("*.yaml")):
        if f.stem == "glossary":
            continue
        data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        ns = data.get("namespace", f.stem)
        for k, v in (data.get("keys") or {}).items():
            keys[f"{ns}.{k}"] = {"file": f.name, **(v or {})}
    return keys


def c_i18n() -> Result:
    r = Result("文案键（国际化规范 3、5.2）")
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        r.status = "skip"
        r.lines.append("没装 jsonschema——跳过")
        return r
    schema = json.loads((CONTRACTS / "i18n-key-manifest.schema.json").read_text(encoding="utf-8"))
    v = Draft202012Validator(schema)
    for f in sorted((ROOT / "i18n").glob("*.yaml")):
        if f.stem == "glossary":
            continue
        data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        for e in v.iter_errors(data):
            r.fail(f"{f.name}：{'/'.join(map(str, e.path))} {e.message}")
        if data.get("namespace") != f.stem:
            r.fail(f"{f.name}：namespace 应为 {f.stem}")
        for k, item in (data.get("keys") or {}).items():
            d = (item or {}).get("defaults", {})
            pz, pe = (
                set(re.findall(r"{{\s*(\w+)", json.dumps(d.get("zh-CN", "")))),
                set(re.findall(r"{{\s*(\w+)", json.dumps(d.get("en-US", "")))),
            )
            if pz != pe:
                r.fail(f"{f.stem}.{k}：中英参数不一样（{sorted(pz)} / {sorted(pe)}）")
    keys = sorted(i18n_keys())
    for a, b in itertools.pairwise(keys):
        if b.startswith(a + "."):
            r.fail(f"{a} 既是一个键，又是 {b} 的上一层（国际化规范 3：同一层改名，如 …Short）")
    # 错误码的键由错误码推导，且 errors.yaml 里要有
    reg = json.loads((CONTRACTS / "error-codes.json").read_text(encoding="utf-8"))["codes"]
    have = set(keys)
    miss = [c["messageKey"] for c in reg if c["messageKey"] not in have]
    if miss:
        r.warn(
            f"错误码文案还没登记 {len(miss)} 个（i18n/errors.yaml，contracts 项目补）：{', '.join(miss[:5])}{' …' if len(miss) > 5 else ''}"
        )
    r.lines.insert(0, f"{len(keys)} 个键")
    return r


# ---------------------------------------------------------------- 登记表（manifest）
MANIFEST_LISTS = {"params": "key", "features": "id", "pages": "id", "objects": "type"}


def manifests() -> dict[str, dict]:
    out = {}
    for m in modules():
        f = API / m / "manifest.yaml"
        out[m] = (yaml.safe_load(f.read_text(encoding="utf-8")) or {}) if f.exists() else {}
    return out


def c_registry() -> Result:
    r = Result("登记表（唯一 · 相似检查）")
    seen: dict[str, dict[str, str]] = defaultdict(dict)
    entries: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for m, data in manifests().items():
        if not data:
            r.fail(f"{m}：缺 manifest.yaml（跑 tl.py scaffold）")
            continue
        if data.get("module") != m:
            r.fail(f"{m}/manifest.yaml：module 应为 {m}")
        for lst, idk in MANIFEST_LISTS.items():
            for it in data.get(lst) or []:
                k = (it or {}).get(idk)
                if not k:
                    r.fail(f"{m}/manifest.yaml：{lst} 里有一条缺 {idk}")
                    continue
                if (
                    lst in ("params", "features")
                    and not str(k).startswith(m.replace("_", "") + ".")
                    and not str(k).startswith(m + ".")
                ):
                    r.fail(f"{m}：{lst} 的键 {k} 要以本模块开头（{m}.…）")
                if k in seen[lst]:
                    r.fail(f"{lst} 键重复：{k}（{seen[lst][k]} 和 {m}）")
                seen[lst][k] = m
                if not it.get("name") or not it.get("desc"):
                    r.fail(f"{m}：{lst} {k} 要写 name（名称）和 desc（用途）")
                entries[lst].append((m, it))
    # 相似检查：名称相近，或单位 + 默认值相同且说明相近 → 提醒架构判断是不是同一件事
    for lst, items in entries.items():
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                (ma, a), (mb, b) = items[i], items[j]
                na, nb = str(a.get("name", "")), str(b.get("name", ""))
                sim = difflib.SequenceMatcher(None, na, nb).ratio()
                same_shape = (
                    lst == "params"
                    and a.get("unit") == b.get("unit")
                    and a.get("default") == b.get("default")
                    and difflib.SequenceMatcher(None, str(a.get("desc", "")), str(b.get("desc", ""))).ratio() > 0.6
                )
                if sim >= 0.8 or same_shape:
                    r.warn(
                        f"相似：{lst} {a.get(MANIFEST_LISTS[lst])}「{na}」（{ma}）和 {b.get(MANIFEST_LISTS[lst])}「{nb}」（{mb}）——是不是同一件事？"
                    )
    total = sum(len(v) for v in entries.values())
    r.lines.insert(
        0,
        f"{total} 条登记（参数 {len(entries['params'])} · 功能 {len(entries['features'])} · 页面 {len(entries['pages'])} · 对象 {len(entries['objects'])}）",
    )
    return r


# ---------------------------------------------------------------- 手写的登记键
def registered_literals() -> set[str]:
    lits: set[str] = set()
    reg = json.loads((CONTRACTS / "error-codes.json").read_text(encoding="utf-8"))["codes"]
    lits.update(c["code"] for c in reg)
    lits.update(i18n_keys())
    for data in manifests().values():
        for lst, idk in MANIFEST_LISTS.items():
            if lst in ("params", "features"):
                lits.update(str(it.get(idk)) for it in data.get(lst) or [] if it and it.get(idk))
    return lits


def code_files() -> list[Path]:
    files = [p for p in API.rglob("*.py") if "kernel" not in p.parts or p.parts[-2] != "reg"]
    files += [p for p in (WEB / "src").rglob("*.ts*")] if (WEB / "src").exists() else []
    return [
        p
        for p in files
        if "node_modules" not in p.parts
        and "generated" not in p.parts
        and "/kernel/reg/" not in p.as_posix()
        and "/shared/base/reg/" not in p.as_posix()  # 生成物本来就由正本生成
    ]


def c_literals() -> Result:
    r = Result("只用生成的常量（不手写登记键）")
    lits = registered_literals()
    if not lits:
        r.lines.append("还没有登记的键")
        return r
    pat = re.compile(r"""["']([A-Za-z][A-Za-z0-9_.]+)["']""")
    hits = []
    for f in code_files():
        if f.parts[-2] == "tests" or f.name.startswith("test_"):
            continue
        for n, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for m in pat.finditer(line):
                if m.group(1) in lits:
                    hits.append(f'{f.relative_to(ROOT).as_posix()}:{n}  "{m.group(1)}"')
    for h in hits[:30]:
        r.fail(h)
    if not hits:
        r.lines.append(f"检查了 {len(lits)} 个登记键")
    return r


# ---------------------------------------------------------------- 查重
WINDOW = 8


def _norm(line: str) -> str:
    line = line.strip()
    if (
        not line
        or line.startswith(("#", "//", '"""', "'''", "import ", "from ", "export {", "}"))
        or line in ("pass", "...", ")", "]", "});", "})")
    ):
        return ""
    return re.sub(r"\s+", " ", line)


def c_dups() -> Result:
    r = Result(f"重复代码（连续 {WINDOW} 行相同）· 与内核同名的函数")
    blocks: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for f in code_files():
        rel = f.relative_to(ROOT).as_posix()
        lines = [(i + 1, _norm(x)) for i, x in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines())]
        lines = [(i, x) for i, x in lines if x]
        for k in range(len(lines) - WINDOW + 1):
            chunk = "\n".join(x for _, x in lines[k : k + WINDOW])
            h = hashlib.sha1(chunk.encode()).hexdigest()  # noqa: S324 — 只做查重指纹
            blocks[h].append((rel, lines[k][0]))
    reported: set[tuple[str, str]] = set()
    for locs in blocks.values():
        files = sorted({f for f, _ in locs})
        if len(files) < 2:
            continue
        key = (files[0], files[1])
        if key in reported:
            continue
        reported.add(key)
        a = next(x for x in locs if x[0] == files[0])
        b = next(x for x in locs if x[0] == files[1])
        r.fail(f"{a[0]}:{a[1]} 和 {b[0]}:{b[1]} 有一段一样——收进 kernel 或互相引用 api 层")
    # 与内核同名的公共函数：多半是又写了一份
    kernel_names: set[str] = set()
    for f in (API / "kernel").rglob("*.py"):
        if "tests" in f.parts:
            continue
        for node in ast.parse(f.read_text(encoding="utf-8")).body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not node.name.startswith(
                "_"
            ):
                kernel_names.add(node.name)
    for f in API.rglob("*.py"):
        if "kernel" in f.relative_to(API).parts[:1] or "tests" in f.parts:
            continue
        for node in ast.parse(f.read_text(encoding="utf-8")).body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name in kernel_names:
                r.fail(
                    f"{f.relative_to(ROOT).as_posix()}:{node.lineno} 定义了和 kernel 同名的 {node.name}——用 kernel 的，不要再写一份"
                )
    if r.status == "ok":
        r.lines.append(f"查了 {len(code_files())} 个文件")
    return r


def c_gen() -> Result:
    r = Result("生成物与正本一致（tl.py gen）")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import gen

    stale = gen.stale()
    if stale:
        r.fail("这些生成物和正本对不上——跑 uv run python ops/tools/tl.py gen（生成物不手改）：")
        r.lines += [f"  {p.relative_to(ROOT).as_posix()}" for p in stale]
    else:
        r.lines.append(f"{len(gen.outputs())} 个生成物都是最新的")
    return r


ALL = {
    "gen": c_gen,
    "ruff": c_ruff,
    "types": c_pyright,
    "test": c_pytest,
    "contracts": c_contracts,
    "web": c_web,
    "bounds": c_boundaries,
    "scope": c_scope,
    "i18n": c_i18n,
    "registry": c_registry,
    "literals": c_literals,
    "dups": c_dups,
}
FAST = ("gen", "ruff", "bounds", "scope", "i18n", "registry", "literals", "dups")
