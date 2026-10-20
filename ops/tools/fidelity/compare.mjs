// 高保真比对：同一窗口、同一身份、同一份示例数据下，分别截原型页和正式页，逐像素比 + 按文字配对比字号 / 颜色 / 位置。
// 由 `tl.py fidelity` 和 `tl.py check` 调用（它们把 ops/tools/fidelity/pages.yaml 转成 JSON 传进来），一般不直接跑。
//
//   node ops/tools/fidelity/compare.mjs <config.json>
//
// 依赖装在 apps/web（playwright、pngjs、pixelmatch）。浏览器第一次要装：pnpm --dir apps/web exec playwright install chromium
// 退出码：0 通过，1 有页面不通过，2 环境问题（没装依赖、原型目录找不到、正式页打不开）。

import { createRequire } from "node:module";
import { createServer } from "node:http";
import { readFileSync, writeFileSync, mkdirSync, existsSync, statSync } from "node:fs";
import { join, resolve, extname, dirname, relative } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, "..", "..", "..");
const req = createRequire(process.env.TL_FID_REQUIRE || join(ROOT, "apps", "web", "package.json"));

let chromium, PNG, pixelmatch;
try {
  ({ chromium } = req("playwright"));
  ({ PNG } = req("pngjs"));
  pixelmatch = req("pixelmatch");
} catch (e) {
  console.error("缺前端依赖（playwright / pngjs / pixelmatch）：在仓库根目录跑 pnpm install，再跑 pnpm --dir apps/web exec playwright install chromium");
  process.exit(2);
}

const cfg = JSON.parse(readFileSync(process.argv[2], "utf8"));
const OUT = resolve(cfg.out);
mkdirSync(OUT, { recursive: true });

// ---------------------------------------------------------------- 静态服务（原型用 http 打开，避免 file:// 的各种限制）
const MIME = {
  ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
  ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
  ".webp": "image/webp", ".woff2": "font/woff2", ".woff": "font/woff", ".ttf": "font/ttf", ".otf": "font/otf",
  ".glb": "model/gltf-binary", ".gltf": "model/gltf+json", ".mp4": "video/mp4",
};

function serve(root, inject) {
  return new Promise((ok) => {
    const srv = createServer((rq, rs) => {
      const p = decodeURIComponent(new URL(rq.url, "http://x").pathname);
      const f = resolve(root, "." + (p === "/" ? "/index.html" : p));
      if (!f.startsWith(resolve(root)) || !existsSync(f) || statSync(f).isDirectory()) {
        rs.writeHead(404); rs.end(); return;
      }
      let body = readFileSync(f);
      const ext = extname(f).toLowerCase();
      if (inject && ext === ".html" && inject[p.replace(/^\//, "")]) {
        body = Buffer.from(body.toString("utf8").replace("</head>", inject[p.replace(/^\//, "")] + "</head>"));
      }
      rs.writeHead(200, { "content-type": MIME[ext] || "application/octet-stream", "cache-control": "no-store" });
      rs.end(body);
    });
    srv.listen(0, "127.0.0.1", () => ok({ srv, url: `http://127.0.0.1:${srv.address().port}` }));
  });
}

// ---------------------------------------------------------------- 页面里取样式（两边同一段代码）
const PROBE_PROPS = ["fontSize", "fontWeight", "lineHeight", "color", "backgroundColor", "borderTopColor", "borderTopWidth",
  "borderTopLeftRadius", "paddingTop", "paddingRight", "paddingBottom", "paddingLeft", "letterSpacing"];

function collect({ props, probes, maxText, scope }) {
  const vis = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return null;
    const s = getComputedStyle(el);
    if (s.visibility === "hidden" || s.display === "none" || +s.opacity === 0) return null;
    return r;
  };
  const pick = (el, r) => {
    const s = getComputedStyle(el);
    const o = { box: [r.left + scrollX, r.top + scrollY, r.width, r.height].map((v) => Math.round(v)) };
    for (const k of props) o[k] = s[k];
    o.font = s.fontFamily.split(",")[0].replace(/["']/g, "").trim();
    return o;
  };
  // 1. 文字配对：每个"自己带文字"的可见元素，按 文字 + 第几次出现 当钥匙
  const texts = {};
  const seen = {};
  const roots = scope && scope.length ? scope.flatMap((s) => [...document.querySelectorAll(s)]) : [document.body];
  const els = roots.flatMap((r) => [r, ...r.querySelectorAll("*")]);
  for (const el of els) {
    if (["SCRIPT", "STYLE", "NOSCRIPT", "TEMPLATE", "svg"].includes(el.tagName)) continue;
    let own = "";
    for (const n of el.childNodes) if (n.nodeType === 3) own += n.textContent;
    own = own.replace(/\s+/g, " ").trim();
    if (!own || own.length > maxText) continue;
    const r = vis(el);
    if (!r) continue;
    seen[own] = (seen[own] || 0) + 1;
    texts[own + "#" + seen[own]] = Object.assign({ tag: el.tagName.toLowerCase() }, pick(el, r));
  }
  // 2. 指定的关键位置
  const named = {};
  for (const [name, sel] of Object.entries(probes || {})) {
    const el = sel && document.querySelector(sel);
    const r = el && vis(el);
    named[name] = r ? pick(el, r) : null;
  }
  return { texts, named, size: [document.documentElement.scrollWidth, document.documentElement.scrollHeight] };
}

// ---------------------------------------------------------------- 截图
async function shoot(browser, url, viewport, now, maskSel, probes, opt) {
  const ctx = await browser.newContext({ viewport, deviceScaleFactor: 1, locale: "zh-CN", timezoneId: cfg.timezone || "Asia/Shanghai", reducedMotion: "reduce" });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e.message || e)));
  if (now) await page.clock.setFixedTime(new Date(now));
  let resp;
  try {
    resp = await page.goto(url, { waitUntil: "networkidle", timeout: 30000 });
  } catch (e) {
    await ctx.close();
    return { error: `打不开：${url}（${String(e.message).split("\n")[0]}）` };
  }
  if (resp && resp.status() >= 400) {
    await ctx.close();
    return { error: `打不开：${url}（HTTP ${resp.status()}）` };
  }
  await page.addStyleTag({ content: "*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}" });
  if (opt.hide && opt.hide.length) await page.addStyleTag({ content: opt.hide.join(",") + "{visibility:hidden!important}" });
  await page.evaluate(() => document.fonts && document.fonts.ready);
  await page.waitForTimeout(cfg.settle_ms ?? 400);
  const data = await page.evaluate(collect, { props: PROBE_PROPS, probes, maxText: 40, scope: opt.scope || null });
  const mask = (maskSel || []).map((s) => page.locator(s));
  const png = await page.screenshot({ fullPage: opt.fullPage, animations: "disabled", caret: "hide", mask, maskColor: "#FF00FF" });
  await ctx.close();
  return { png, data, errors };
}

// ---------------------------------------------------------------- 比对
function pad(img, w, h) {
  if (img.width === w && img.height === h) return img;
  const o = new PNG({ width: w, height: h });
  o.data.fill(255);
  PNG.bitblt(img, o, 0, 0, img.width, img.height, 0, 0);
  return o;
}

function diffPng(a, b, threshold) {
  const A0 = PNG.sync.read(a), B0 = PNG.sync.read(b);
  const w = Math.max(A0.width, B0.width), h = Math.max(A0.height, B0.height);
  const A = pad(A0, w, h), B = pad(B0, w, h);
  const D = new PNG({ width: w, height: h });
  const n = pixelmatch(A.data, B.data, D.data, w, h, { threshold, includeAA: false, alpha: 0.25, diffColor: [220, 30, 30] });
  return { n, ratio: n / (w * h), w, h, sizeA: [A0.width, A0.height], sizeB: [B0.width, B0.height], png: PNG.sync.write(D) };
}

const LABEL = {
  fontSize: "字号", fontWeight: "字重", lineHeight: "行高", color: "文字颜色", backgroundColor: "底色", borderTopColor: "边线颜色",
  borderTopWidth: "边线粗细", borderTopLeftRadius: "圆角", paddingTop: "上内距", paddingRight: "右内距", paddingBottom: "下内距",
  paddingLeft: "左内距", letterSpacing: "字距", font: "字体", box: "位置 / 大小", tag: "标签",
};

function cmpEl(a, b, tol, props) {
  const out = [];
  for (const k of props) {
    if (k === "box") {
      const d = a.box.map((v, i) => Math.abs(v - b.box[i]));
      if (Math.max(...d) > tol) out.push(`${LABEL.box}：原型 ${a.box.join(",")} · 正式 ${b.box.join(",")}`);
    } else if (a[k] !== b[k]) out.push(`${LABEL[k] || k}：原型 ${a[k]} · 正式 ${b[k]}`);
  }
  return out;
}

function compareData(P, A, page) {
  const tol = page.box_tolerance ?? cfg.box_tolerance ?? 2;
  const ignore = (page.ignore_text || []).map((s) => new RegExp(s));
  const textProps = ["font", "fontSize", "fontWeight", "color", "box"];
  const missing = [], styled = [], extra = [];
  for (const [k, p] of Object.entries(P.texts)) {
    const t = k.replace(/#\d+$/, "");
    if (ignore.some((r) => r.test(t))) continue;
    const a = A.texts[k];
    if (!a) { missing.push(t); continue; }
    const d = cmpEl(p, a, tol, textProps);
    if (d.length) styled.push({ text: t, diffs: d });
  }
  for (const k of Object.keys(A.texts)) {
    const t = k.replace(/#\d+$/, "");
    if (!P.texts[k] && !ignore.some((r) => r.test(t))) extra.push(t);
  }
  const named = [];
  const allProps = ["box", "font", ...PROBE_PROPS];
  for (const [name, p] of Object.entries(P.named)) {
    const a = A.named[name];
    if (!p && !a) continue; // 这个状态下两边都没有（例如空状态没有导入提示）
    if (!p) named.push({ name, diffs: ["原型这个状态下没有，正式页却有"] });
    else if (!a) named.push({ name, diffs: ["正式页里没找到（应带 data-fid=\"" + name + "\"）"] });
    else {
      const d = cmpEl(p, a, tol, allProps);
      if (d.length) named.push({ name, diffs: d });
    }
  }
  return { missing, styled, extra, named, total: Object.keys(P.texts).length };
}

// ---------------------------------------------------------------- 报告
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

function reportHtml(rows) {
  const li = (arr, f) => (arr.length ? `<ul>${arr.slice(0, 60).map((x) => `<li>${f(x)}</li>`).join("")}${arr.length > 60 ? `<li>……还有 ${arr.length - 60} 条</li>` : ""}</ul>` : "");
  const body = rows.map((r) => {
    if (r.error) return `<section><h2>${esc(r.id)} <b class="bad">环境问题</b></h2><p>${esc(r.error)}</p></section>`;
    const c = r.cmp;
    return `<section id="${esc(r.id)}"><h2>${esc(r.id)} <b class="${r.pass ? "ok" : "bad"}">${r.pass ? "通过" : "不通过"}</b></h2>
<p class="meta">像素差异 ${(r.diff.ratio * 100).toFixed(2)}%（上限 ${(r.maxDiff * 100).toFixed(2)}%）· 原型 ${r.diff.sizeA.join("×")} · 正式 ${r.diff.sizeB.join("×")} · 文字配对 ${c.total - c.missing.length}/${c.total}</p>
${r.reasons.length ? `<p class="why">${r.reasons.map(esc).join("<br>")}</p>` : ""}
<div class="shots"><figure><figcaption>原型</figcaption><img src="${r.files.proto}"></figure><figure><figcaption>正式页</figcaption><img src="${r.files.app}"></figure><figure><figcaption>差异（红色）</figcaption><img src="${r.files.diff}"></figure></div>
<details open><summary>关键位置不一致（${c.named.length}）</summary>${li(c.named, (x) => `<b>${esc(x.name)}</b>：${x.diffs.map(esc).join("；")}`)}</details>
<details${c.missing.length ? " open" : ""}><summary>原型有、正式页没有的文字（${c.missing.length}）</summary>${li(c.missing, esc)}</details>
<details${c.styled.length ? " open" : ""}><summary>文字一样但样式 / 位置不一样（${c.styled.length}）</summary>${li(c.styled, (x) => `<b>${esc(x.text)}</b>：${x.diffs.map(esc).join("；")}`)}</details>
<details><summary>正式页多出来的文字（${c.extra.length}）</summary>${li(c.extra, esc)}</details>
${r.errors.length ? `<details open><summary>页面脚本报错（${r.errors.length}）</summary>${li(r.errors, esc)}</details>` : ""}
</section>`;
  }).join("\n");
  return `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>高保真比对</title>
<style>:root{--bg:#EEECE8;--fg:#1A1A19;--mut:#75736D;--line:#D9D7D2;--bad:#B3261E;--ok:#2E6B4C}
@media (prefers-color-scheme:dark){:root{--bg:#1A1A19;--fg:#EEECE8;--mut:#A7A5A0;--line:#45443F}}
body{margin:0;padding:24px 16px;background:var(--bg);color:var(--fg);font:14px/1.6 'Noto Sans SC',system-ui,sans-serif}
h1{font-size:22px;margin:0 0 4px}h2{font-size:16px;margin:28px 0 4px;border-top:1px solid var(--fg);padding-top:12px}
b.ok{color:var(--ok)}b.bad{color:var(--bad)}.meta{color:var(--mut);margin:0 0 6px}.why{color:var(--bad)}
.shots{display:flex;gap:12px;overflow-x:auto}figure{margin:0;flex:1 1 0;min-width:260px}figcaption{font-size:12px;color:var(--mut)}
img{width:100%;border:1px solid var(--line);display:block}summary{cursor:pointer;margin-top:8px}ul{margin:4px 0;padding-left:20px}</style></head>
<body><h1>高保真比对</h1><p class="meta">${esc(new Date().toISOString())} · 默认窗口 ${cfg.viewport.width}×${cfg.viewport.height}</p>${body}</body></html>`;
}

// ---------------------------------------------------------------- 主流程
const protoRoot = resolve(cfg.prototype_root);
if (!existsSync(join(protoRoot, "assets", "mono.css"))) {
  console.error(`原型目录不对：${protoRoot}（里面应有 assets/mono.css）——设环境变量 TL_PROTOTYPE 指到 fidelity/Prototype`);
  process.exit(2);
}
const proto = await serve(protoRoot);
let appBase = cfg.app_url;
let appSrv = null;
if (cfg.self_test) {
  // 自检：正式页这一侧也用原型，可选择注入一段"改坏"的样式，证明比对能抓到
  appSrv = await serve(protoRoot, cfg.self_test.inject || null);
  appBase = appSrv.url;
}
if (!appBase) {
  console.error("没有正式页地址（--app-url 或环境变量 TL_APP_URL）");
  process.exit(2);
}

const browser = await chromium.launch(cfg.chromium ? { executablePath: cfg.chromium } : {});
const rows = [];
let envBad = false;
for (const page of cfg.pages) {
  for (const st of page.states || [{ name: "默认", query: "" }]) {
    const viewport = st.viewport || page.viewport || cfg.viewport;
    const id = `${page.name}·${st.name}`;
    const q = (s) => (s ? (s.startsWith("?") ? s : "?" + s) : "");
    const protoUrl = `${proto.url}/${page.proto}${q([st.query, cfg.proto_query].filter(Boolean).join("&"))}`;
    const appPath = cfg.self_test ? "/" + page.proto : page.app;
    const appQ = cfg.self_test ? [st.query, cfg.proto_query].filter(Boolean).join("&") : (st.app_query ?? st.query);
    const appUrl = `${appBase.replace(/\/$/, "")}${appPath}${q(appQ)}`;
    const maskP = (page.mask || []).map((m) => (typeof m === "string" ? m : m.proto)).filter(Boolean);
    const maskA = (page.mask || []).map((m) => (typeof m === "string" ? m : m.app)).filter(Boolean);
    const probesP = {}, probesA = {};
    for (const [name, sel] of Object.entries(page.probes || {})) {
      probesP[name] = typeof sel === "string" ? sel : sel.proto;
      probesA[name] = cfg.self_test || page.same_selectors ? probesP[name] : (typeof sel === "string" ? `[data-fid="${name}"]` : sel.app || `[data-fid="${name}"]`);
    }
    const opt = { scope: page.scope || null, fullPage: page.full_page ?? true, hide: page.hide || [] };
    const P = await shoot(browser, protoUrl, viewport, cfg.now, maskP, probesP, opt);
    const A = P.error ? null : await shoot(browser, appUrl, viewport, cfg.now, maskA, probesA, opt);
    const err = P.error || (A && A.error);
    if (err) { rows.push({ id, error: err }); envBad = true; console.log(`✗ ${id}：${err}`); continue; }
    const dir = join(OUT, page.name, st.name);
    mkdirSync(dir, { recursive: true });
    const diff = diffPng(P.png, A.png, cfg.pixel_threshold ?? 0.1);
    writeFileSync(join(dir, "proto.png"), P.png);
    writeFileSync(join(dir, "app.png"), A.png);
    writeFileSync(join(dir, "diff.png"), diff.png);
    const cmp = compareData(P.data, A.data, page);
    const maxDiff = page.max_diff ?? cfg.max_diff ?? 0.005;
    const reasons = [];
    if (diff.ratio > maxDiff) reasons.push(`像素差异 ${(diff.ratio * 100).toFixed(2)}% 超过上限 ${(maxDiff * 100).toFixed(2)}%`);
    if (diff.sizeA[1] !== diff.sizeB[1]) reasons.push(`页面高度不同：原型 ${diff.sizeA[1]} · 正式 ${diff.sizeB[1]}`);
    if (cmp.named.length) reasons.push(`关键位置不一致 ${cmp.named.length} 处`);
    if (cmp.missing.length) reasons.push(`缺文字 ${cmp.missing.length} 处`);
    if (cmp.styled.length) reasons.push(`文字样式 / 位置不一致 ${cmp.styled.length} 处`);
    if (A.errors.length) reasons.push(`正式页脚本报错 ${A.errors.length} 条`);
    const pass = reasons.length === 0;
    const rel = (f) => relative(OUT, join(dir, f)).split("\\").join("/");
    rows.push({ id, pass, diff: { ratio: diff.ratio, sizeA: diff.sizeA, sizeB: diff.sizeB }, maxDiff, cmp, reasons, errors: A.errors,
      files: { proto: rel("proto.png"), app: rel("app.png"), diff: rel("diff.png") } });
    console.log(`${pass ? "✓" : "✗"} ${id}：像素差异 ${(diff.ratio * 100).toFixed(2)}%${reasons.length ? " · " + reasons.join("；") : ""}`);
  }
}
await browser.close();
proto.srv.close();
if (appSrv) appSrv.srv.close();

writeFileSync(join(OUT, "report.html"), reportHtml(rows));
writeFileSync(join(OUT, "result.json"), JSON.stringify(rows.map(({ files, ...r }) => r), null, 1));
console.log(`报告：${join(OUT, "report.html")}`);
process.exit(envBad ? 2 : rows.every((r) => r.pass) ? 0 : 1);
