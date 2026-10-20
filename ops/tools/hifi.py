"""高保真比对（tl.py fidelity、tl.py check 的 hifi 项）。

三部分：
1. 同步：原型的公共样式（mono.css、mono-fonts.css、dock.css）和用到的字体，原样复制进正式前端
   （apps/web/src/shared/ui/generated/、apps/web/public/fonts/）。原型是唯一来源，正式前端不另写一份。
2. 静态：前端源码里不许直接写颜色（#xxxxxx、rgb()、hsl()），一律用设计变量 var(--m-*)。
   只有同步来的样式（HIFI_ALLOW）能写颜色值。
3. 截图：按 ops/tools/fidelity/pages.yaml，用同一窗口、同一身份、同一份数据截原型页和正式页，
   逐像素比 + 按文字配对比字号 / 颜色 / 位置；报告在 .fidelity/report.html。真正干活的是 fidelity/compare.mjs。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "apps" / "web"
HERE = Path(__file__).resolve().parent / "fidelity"
OUT = ROOT / ".fidelity"
GEN_UI = WEB / "src" / "shared" / "ui" / "generated"
FONTS = WEB / "public" / "fonts"
SYNC_CSS = ("mono.css", "mono-fonts.css", "dock.css")
FONT_URL = re.compile(r"url\((?:['\"])?fonts/([^)'\"]+)(?:['\"])?\)")
# 允许写颜色值的文件（从原型同步来的样式）
HIFI_ALLOW = ("apps/web/src/shared/ui/generated/",)
COLOR = re.compile(r"(?<![\w&/-])#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b|\b(?:rgba?|hsla?)\(")

# 自检时注入正式页一侧的"改坏"样式：模仿常见的走样（旧蓝色主色、标题字号、左边距、顶栏内距、导航当前项字重）
BREAK_CSS = (
    "<style>.m-btn-p{background:#2350B5!important;border-color:#2350B5!important}"
    ".m-display{font-size:30px!important}.m-page{padding-left:44px!important}"
    ".m-top{padding-left:24px!important}.m-rail a.on{font-weight:500!important}</style>"
)


def config() -> dict[str, Any]:
    return yaml.safe_load(  # pyright: ignore[reportAny]
        (HERE / "pages.yaml").read_text(encoding="utf-8")
    )


def prototype_root(cfg: dict[str, Any]) -> Path | None:
    env = os.environ.get("TL_PROTOTYPE")
    roots: list[str] = cfg.get("prototype_roots", [])
    cands = [Path(env)] if env else [(ROOT / p).resolve() for p in roots]
    for c in cands:
        if (c / "assets" / "mono.css").exists():
            return c
    return None


def synced(proto: Path) -> dict[Path, bytes]:
    """原型 → 正式前端应有的样式与字体（只带 mono-fonts.css 用到的字体）。"""
    out: dict[Path, bytes] = {}
    for name in SYNC_CSS:
        text = (proto / "assets" / name).read_text(encoding="utf-8")
        if name == "mono-fonts.css":
            for rel in FONT_URL.findall(text):
                out[FONTS / rel] = (proto / "assets" / "fonts" / rel).read_bytes()
            text = FONT_URL.sub(lambda m: f"url(/fonts/{m.group(1)})", text)
        head = (
            f"/* 由 tl.py fidelity --sync 从高保真原型 Prototype/assets/{name} 复制，不要手改；原型改了重新同步。 */\n"
        )
        out[GEN_UI / name] = (head + text).encode("utf-8")
    return out


def sync_stale(proto: Path) -> list[Path]:
    want = synced(proto)
    bad = [p for p, b in want.items() if not p.exists() or p.read_bytes() != b]
    extra = [p for p in FONTS.rglob("*") if p.is_file() and p not in want] if FONTS.exists() else []
    return bad + extra


def sync() -> tuple[int, str]:
    proto = prototype_root(config())
    if not proto:
        return 2, "找不到原型目录（设环境变量 TL_PROTOTYPE 指到 fidelity/Prototype）"
    want = synced(proto)
    changed: list[str] = []
    for p, b in want.items():
        if not p.exists() or p.read_bytes() != b:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b)
            changed.append(p.relative_to(ROOT).as_posix())
    for p in sorted(FONTS.rglob("*")) if FONTS.exists() else []:
        if p.is_file() and p not in want:
            p.unlink()
            changed.append(p.relative_to(ROOT).as_posix() + "（删掉，原型不用了）")
    css = [c for c in changed if c.endswith(".css")]
    return 0, f"同步完：{len(css)} 个样式、{len(changed) - len(css)} 个字体有变化" + "".join(f"\n  {c}" for c in css)


def color_literals() -> list[str]:
    src = WEB / "src"
    hits: list[str] = []
    if not src.exists():
        return hits
    for f in sorted(src.rglob("*")):
        if f.suffix not in (".ts", ".tsx", ".css", ".scss") or "node_modules" in f.parts:
            continue
        rel = f.relative_to(ROOT).as_posix()
        if rel.startswith(HIFI_ALLOW) or "/shared/base/reg/" in rel:
            continue
        for n, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if COLOR.search(line):
                hits.append(f"{rel}:{n}  {line.strip()[:100]}")
    return hits


def node() -> str | None:
    return shutil.which("node")


def has_deps() -> bool:
    nm = WEB / "node_modules"
    return all((nm / p).exists() for p in ("playwright", "pngjs", "pixelmatch"))


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_dev() -> tuple[subprocess.Popen[bytes] | None, str]:
    """没给正式页地址时，自己起一个 vite 开发服务；返回 (进程, 地址)。"""
    vite = shutil.which("vite", path=str(WEB / "node_modules" / ".bin"))
    if not vite:
        return None, ""
    port = _free_port()
    proc = subprocess.Popen(  # noqa: S603
        [vite, "--port", str(port), "--strictPort", "--host", "127.0.0.1"],
        cwd=WEB,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(60):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return proc, f"http://127.0.0.1:{port}"
        except OSError:
            time.sleep(0.5)
    proc.terminate()
    return None, ""


def _states(page: dict[str, Any]) -> list[dict[str, Any]]:
    return page.get("states", [])


def run(
    pages: list[str] | None = None,
    states: list[str] | None = None,
    app_url: str | None = None,
    only_enabled: bool = False,
    self_test: str | None = None,  # None / "same"（两边都是原型，应全过）/ "broken"（正式页一侧注入改坏的样式，应不过）
    out: Path = OUT,
) -> tuple[int, str]:
    """跑截图比对。返回 (退出码, 输出)：0 通过，1 不通过，2 环境问题，3 没有要比的页。"""
    cfg = config()
    d: dict[str, Any] = cfg.get("defaults", {})
    all_pages: list[dict[str, Any]] = cfg.get("pages", [])
    sel = [p for p in all_pages if (not pages or p["name"] in pages or p["proto"] in pages)]
    if only_enabled:
        sel = [p for p in sel if p.get("enabled")]
    if states:
        sel = [{**p, "states": [s for s in _states(p) if s["name"] in states]} for p in sel]
    if not sel:
        return 3, "没有要比的页"
    if not node():
        return 2, "没找到 node"
    if not has_deps():
        return (
            2,
            "apps/web 没装 playwright / pngjs / pixelmatch（pnpm install，再 pnpm --dir apps/web exec playwright install chromium）",
        )
    proto = prototype_root(cfg)
    if not proto:
        return 2, "找不到原型目录（设环境变量 TL_PROTOTYPE 指到 fidelity/Prototype）"
    job: dict[str, Any] = {
        **d,
        "prototype_root": str(proto),
        "out": str(out),
        "pages": sel,
        "app_url": app_url or os.environ.get("TL_APP_URL"),
    }
    if os.environ.get("TL_CHROMIUM"):
        job["chromium"] = os.environ["TL_CHROMIUM"]
    if self_test:
        job["self_test"] = {"inject": {p["proto"]: BREAK_CSS for p in sel}} if self_test == "broken" else {}
    dev = None
    if not job["app_url"] and not self_test:
        dev, url = start_dev()
        if not dev:
            return 2, "没有正式页地址，也起不来 vite（--app-url 或环境变量 TL_APP_URL）"
        job["app_url"] = url
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(job, f, ensure_ascii=False)
    try:
        p = subprocess.run(  # noqa: S603
            [node() or "node", str(HERE / "compare.mjs"), f.name],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return p.returncode, (p.stdout + p.stderr).strip()
    finally:
        Path(f.name).unlink(missing_ok=True)
        if dev:
            dev.terminate()
