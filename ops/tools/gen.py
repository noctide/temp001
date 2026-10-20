"""tl gen：从唯一正本生成常量与代码地图（开发项目划分规范 5.5）。生成物不手改；tl check 检查是否和正本一致。

正本 → 生成物
    packages/contracts/error-codes.json   → kernel/reg/errors.py、web shared/base/reg/errors.ts
    i18n/<命名空间>.yaml                   → kernel/reg/i18n.py、web shared/base/reg/i18n.ts、i18n.seed.ts
    各模块 manifest.yaml（参数、功能）      → kernel/reg/manifest.py、web shared/base/reg/manifest.ts
    各模块 api 层 + kernel 的公开函数       → plan/CODEMAP.md
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
API = ROOT / "apps" / "api" / "titanloom"
REG_PY = API / "kernel" / "reg"
REG_TS = ROOT / "apps" / "web" / "src" / "shared" / "base" / "reg"
CONTRACTS = ROOT / "packages" / "contracts"
HEAD_PY = '"""由 ops/tools/tl.py gen 生成，不要手改；改正本后重新生成（开发项目划分规范 5.5）。"""\n'
HEAD_TS = "// 由 ops/tools/tl.py gen 生成，不要手改；改正本后重新生成（开发项目划分规范 5.5）。\n"
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _projects() -> dict[str, dict[str, Any]]:
    data = yaml.safe_load((ROOT / "projects.yaml").read_text(encoding="utf-8"))
    return {k: (v or {}) for k, v in data.items()}


def _modules() -> list[str]:
    return sorted(v["module"] for v in _projects().values() if v.get("module"))


def _manifests() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for m in _modules():
        f = API / m / "manifest.yaml"
        out[m] = (yaml.safe_load(f.read_text(encoding="utf-8")) or {}) if f.exists() else {}
    return out


def _i18n() -> dict[str, dict[str, Any]]:
    keys: dict[str, dict[str, Any]] = {}
    for f in sorted((ROOT / "i18n").glob("*.yaml")):
        if f.stem == "glossary":
            continue
        data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        ns = data.get("namespace", f.stem)
        for k, v in (data.get("keys") or {}).items():
            keys[f"{ns}.{k}"] = v or {}
    return dict(sorted(keys.items()))


def _errors() -> list[dict[str, Any]]:
    return json.loads((CONTRACTS / "error-codes.json").read_text(encoding="utf-8"))["codes"]


# ---------------------------------------------------------------- 键 → 嵌套常量
def _tree(keys: list[str]) -> dict[str, Any]:
    t: dict[str, Any] = {}
    for k in keys:
        node = t
        parts = k.split(".")
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = k
    return t


def _py_tree(name: str, tree: dict[str, Any], ind: int = 0) -> list[str]:
    pad = "    " * ind
    out = [f"{pad}class {name}:"]
    if not tree:
        out.append(f"{pad}    pass")
    for k in sorted(tree):
        v = tree[k]
        safe = k if IDENT.match(k) and k not in ("class", "def", "import", "from", "pass") else f"{k}_"
        if isinstance(v, dict):
            out += _py_tree(safe, v, ind + 1)  # pyright: ignore[reportUnknownArgumentType]
        else:
            out.append(f'{pad}    {safe} = "{v}"')
    return out


def _ts_tree(tree: dict[str, Any], ind: int = 1) -> str:
    if not tree:
        return "{}"
    pad = "  " * ind
    rows = []
    for k in sorted(tree):
        v = tree[k]
        key = k if IDENT.match(k) else json.dumps(k)
        rows.append(f"{pad}{key}: " + (_ts_tree(v, ind + 1) if isinstance(v, dict) else json.dumps(v)) + ",")  # pyright: ignore[reportUnknownArgumentType]
    return "{\n" + "\n".join(rows) + "\n" + "  " * (ind - 1) + "}"


# ---------------------------------------------------------------- 各生成物
def gen_errors_py(codes: list[dict[str, Any]]) -> str:
    lines = [
        HEAD_PY,
        "from dataclasses import dataclass",
        "from enum import StrEnum",
        "",
        "",
        "class ErrorCode(StrEnum):",
        *[f'    {c["code"]} = "{c["code"]}"' for c in codes],
        "",
        "",
        "@dataclass(frozen=True)",
        "class ErrorMeta:",
        "    http_status: int",
        "    retryable: bool",
        "    recovery_action: str | None",
        "    message_key: str",
        "",
        "",
        "ERRORS: dict[ErrorCode, ErrorMeta] = {",
        *[
            f"    ErrorCode.{c['code']}: ErrorMeta({c['httpStatus']}, {c['retryable']}, "
            f"{json.dumps(c.get('recoveryAction'))}, {json.dumps(c['messageKey'])}),".replace("null", "None")
            for c in codes
        ],
        "}",
        "",
    ]
    return "\n".join(lines)


def gen_errors_ts(codes: list[dict[str, Any]]) -> str:
    body = ",\n".join(
        f"  {c['code']}: {{ http: {c['httpStatus']}, retryable: {str(c['retryable']).lower()}, "
        f"recovery: {json.dumps(c.get('recoveryAction'))}, messageKey: {json.dumps(c['messageKey'])} }}"
        for c in codes
    )
    return HEAD_TS + f"export const ERRORS = {{\n{body},\n}} as const;\nexport type ErrorCode = keyof typeof ERRORS;\n"


def gen_i18n_py(keys: dict[str, dict[str, Any]]) -> str:
    return (
        HEAD_PY
        + "\n# 文案键：K.<命名空间>.<页面>…<名称>（国际化规范 3）\n"
        + "\n".join(_py_tree("K", _tree(list(keys))))
        + "\n"
    )


def gen_i18n_ts(keys: dict[str, dict[str, Any]]) -> str:
    return (
        HEAD_TS
        + "// 文案键：K.<命名空间>.<页面>…<名称>（国际化规范 3）\nexport const K = "
        + _ts_tree(_tree(list(keys)))
        + " as const;\n"
    )


SEED_LANGS = ("zh-CN", "en-US")


def gen_i18n_seed_ts(keys: dict[str, dict[str, Any]]) -> str:
    """出厂默认文案（国际化规范 5.2）。语言包服务接通前，前端用它兜底；上线后以后台发布的语言包为准。"""
    seed: dict[str, dict[str, str]] = {lang: {} for lang in SEED_LANGS}
    for k, v in keys.items():
        defaults: dict[str, str] = v.get("defaults") or {}
        for lang in SEED_LANGS:
            if defaults.get(lang):
                seed[lang][k] = defaults[lang]
    return (
        HEAD_TS
        + "// 出厂默认文案：语言包服务接通前前端用它兜底（国际化规范 5.2）；只由 shared/base/i18n.ts 引用。\n"
        + "export const SEED: Record<string, Record<string, string>> = "
        + json.dumps(seed, ensure_ascii=False, indent=2)
        + ";\n"
    )


def _entries(lst: str) -> list[tuple[str, dict[str, Any]]]:
    out: list[tuple[str, dict[str, Any]]] = []
    for m, data in _manifests().items():
        for it in data.get(lst) or []:
            if it:
                out.append((m, it))
    return out


def gen_manifest_py() -> str:
    params = {it["key"]: {**it, "module": m} for m, it in _entries("params") if it.get("key")}
    feats = {it["id"]: {**it, "module": m} for m, it in _entries("features") if it.get("id")}
    return (
        (
            HEAD_PY
            + "\nfrom typing import Any\n\n"
            + "# 业务参数（各模块 manifest.yaml）：键 → 登记内容（默认值、单位、范围、层级…）\n"
            + f"PARAMS: dict[str, dict[str, Any]] = {json.dumps(params, ensure_ascii=False, indent=4, sort_keys=True)}\n\n"
            + "# 功能开放（各模块 manifest.yaml）\n"
            + f"FEATURES: dict[str, dict[str, Any]] = {json.dumps(feats, ensure_ascii=False, indent=4, sort_keys=True)}\n\n"
            + "\n".join(_py_tree("P", _tree(sorted(params))))
            + "\n\n\n"
            + "\n".join(_py_tree("F", _tree(sorted(feats))))
            + "\n"
        )
        .replace(": null", ": None")
        .replace(": true", ": True")
        .replace(": false", ": False")
    )


def gen_manifest_ts() -> str:
    params = sorted(it["key"] for _, it in _entries("params") if it.get("key"))
    feats = sorted(it["id"] for _, it in _entries("features") if it.get("id"))
    return (
        HEAD_TS
        + f"export const P = {_ts_tree(_tree(params))} as const;\nexport const F = {_ts_tree(_tree(feats))} as const;\n"
    )


def _public(path: Path) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return out
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) and not node.name.startswith("_"):
            doc = (ast.get_docstring(node) or "").strip().splitlines()
            kind = "class" if isinstance(node, ast.ClassDef) else "def"
            out.append((f"{kind} {node.name}", doc[0] if doc else "（没写说明）"))
    return out


def gen_codemap() -> str:
    lines = [
        "# 代码地图",
        "",
        "由 `tl.py gen` 生成，不要手改。**动手前先查这里：要用的东西已经有了就用，不要再写一份**（开发项目划分规范 5.5）。",
        "别的模块只能引用对方 `api` 层与 `kernel`。",
        "",
        "## kernel（公共内核，架构独占）",
        "",
    ]
    for f in sorted((API / "kernel").glob("*.py")):
        if f.name == "__init__.py":
            continue
        items = _public(f)
        if items:
            lines.append(f"- `titanloom.kernel.{f.stem}`")
            lines += [f"  - `{n}` — {d}" for n, d in items]
    lines += [
        "",
        "生成的常量：`titanloom.kernel.reg`（ErrorCode、K 文案键、P 业务参数、F 功能）；前端 `shared/base/reg`。",
        "",
    ]
    mans = _manifests()
    for m in _modules():
        api = API / m / "api"
        items: list[tuple[str, str]] = []
        for f in sorted(api.rglob("*.py")):
            mod = ".".join(f.relative_to(API).with_suffix("").parts)
            items += [(f"{mod}.{n.split(' ')[1]}", d) for n, d in _public(f)]
        data = mans.get(m, {})
        counts = " · ".join(f"{k} {len(data.get(k) or [])}" for k in ("params", "features", "pages", "objects"))
        lines += [f"## {m}", "", f"登记：{counts}", ""]
        lines += [f"- `{n}` — {d}" for n, d in items] or ["（api 层还没有对外函数）"]
        lines.append("")
    return "\n".join(lines)


def outputs() -> dict[Path, str]:
    codes = _errors()
    keys = _i18n()
    return {
        REG_PY / "__init__.py": HEAD_PY,
        REG_PY / "errors.py": gen_errors_py(codes),
        REG_PY / "i18n.py": gen_i18n_py(keys),
        REG_PY / "manifest.py": gen_manifest_py(),
        REG_TS / "errors.ts": gen_errors_ts(codes),
        REG_TS / "i18n.ts": gen_i18n_ts(keys),
        REG_TS / "i18n.seed.ts": gen_i18n_seed_ts(keys),
        REG_TS / "manifest.ts": gen_manifest_ts(),
        REG_TS / "index.ts": HEAD_TS
        + 'export * from "./errors";\nexport * from "./i18n";\nexport * from "./manifest";\n',
        ROOT / "plan" / "CODEMAP.md": gen_codemap(),
    }


def write_all() -> list[Path]:
    changed: list[Path] = []
    for p, text in outputs().items():
        if not p.exists() or p.read_text(encoding="utf-8") != text:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8", newline="\n")
            changed.append(p)
    return changed


def stale() -> list[Path]:
    """和正本不一致的生成物（tl check 用）。"""
    return [p for p, text in outputs().items() if not p.exists() or p.read_text(encoding="utf-8") != text]
