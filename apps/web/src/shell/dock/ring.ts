// 悬浮球快捷圈的规则（Shell 子方案；草图 WireFrame/sketch-askagent.html v3，10-13 用户定）。和原型 assets/dock.js 同一套：
// 格子 = 管家（必留）· 待办 · 客服 · 反馈 · 选取 · 任务 · 自动；「管家」的二级 = 问这一页 + 这一页声明的动作（最多 2 个，摊平后最多 5 项）。
// 个人设置存本机：格子与顺序 tl.ring.v1，球的位置 tl.fab.pos.v1（键名和原型一致）。
import { K } from "../../shared/base/reg";

export type RingKey = "ask" | "todo" | "help" | "fb" | "pick" | "tasks" | "auto";

export interface RingCfg {
  order: RingKey[];
  on: RingKey[];
  page: boolean;
  v: 2;
}

export interface BallPos {
  side: "l" | "r";
  b: number; // 离窗口底边的距离
}

interface ItemDef {
  name: string; // 文案键
  desc: string; // 文案键
  agent?: boolean; // 要「用智能管家」功能
  lock?: boolean; // 必留
}

export const RING_ITEMS: Record<RingKey, ItemDef> = {
  ask: { name: K.shell.dock.ring.ask.name, desc: K.shell.dock.ring.ask.desc, agent: true, lock: true },
  todo: { name: K.shell.dock.ring.todo.nameShort, desc: K.shell.dock.ring.todo.desc },
  help: { name: K.shell.dock.ring.help.name, desc: K.shell.dock.ring.help.desc },
  fb: { name: K.shell.dock.ring.fb.name, desc: K.shell.dock.ring.fb.desc },
  pick: { name: K.shell.dock.ring.pick.name, desc: K.shell.dock.ring.pick.desc },
  tasks: { name: K.shell.dock.ring.tasks.name, desc: K.shell.dock.ring.tasks.desc, agent: true },
  auto: { name: K.shell.dock.ring.auto.name, desc: K.shell.dock.ring.auto.desc },
};

export const MAX_SLOTS = 8;
const CFG_KEY = "tl.ring.v1";
const POS_KEY = "tl.fab.pos.v1";

export const ringDefault = (): RingCfg => ({
  order: ["ask", "todo", "help", "fb", "pick", "tasks", "auto"],
  on: ["ask", "todo", "help", "fb", "pick"],
  page: true,
  v: 2,
});

function load<T>(key: string): T | null {
  try {
    return JSON.parse(localStorage.getItem(key) ?? "null") as T | null;
  } catch {
    return null;
  }
}
function save(key: string, v: unknown): void {
  try {
    if (v == null) localStorage.removeItem(key);
    else localStorage.setItem(key, JSON.stringify(v));
  } catch {
    /* 隐私模式等存不了就算了：只是个人便利 */
  }
}

export const loadCfg = (): RingCfg => {
  const c = load<RingCfg>(CFG_KEY);
  return c && c.v === 2 ? c : ringDefault();
};
export const saveCfg = (c: RingCfg): void => save(CFG_KEY, c);
export const loadPos = (): BallPos | null => load<BallPos>(POS_KEY);
export const savePos = (p: BallPos | null): void => save(POS_KEY, p);

/** 这一页在「管家」二级里提供的动作（页面声明；带二级的动作会被摊平）。 */
export interface PageAction {
  label: string; // 已经翻译好的文字
  run?: () => void;
  q?: string; // 直接问管家的话
  sub?: PageAction[];
}

export interface RingEntry {
  k: RingKey;
  name: string; // 文案键
  params?: Record<string, number>;
  desc: string; // 文案键
  sub?: PageAction[];
  direct?: boolean; // 点一下直接执行（二级靠停留 / → 展开）
}

export interface RingEnv {
  pending: number; // 待办条数
  agentOk: boolean; // 能不能用管家（功能开放 · 用智能管家）
  autoOk: boolean; // 能不能建自动化（功能开放）
  pageActions: PageAction[];
  askPage: PageAction; // 「问这一页」
}

export function ringList(cfg: RingCfg, env: RingEnv): RingEntry[] {
  const out: RingEntry[] = [];
  for (const k of cfg.order) {
    const it = RING_ITEMS[k];
    if (!cfg.on.includes(k) && !it.lock) continue;
    if (it.agent && !env.agentOk) continue;
    if (k === "auto" && !env.autoOk) continue;
    out.push(
      k === "todo"
        ? { k, name: K.shell.dock.ring.todo.name, params: { count: env.pending }, desc: it.desc }
        : { k, name: it.name, desc: it.desc },
    );
  }
  const ask = out.find((x) => x.k === "ask");
  if (ask && cfg.page) {
    const sub: PageAction[] = [env.askPage];
    for (const a of env.pageActions.slice(0, 2)) {
      if (a.sub) sub.push(...a.sub);
      else sub.push(a);
    }
    if (sub.length > 1) {
      ask.sub = sub.slice(0, 5);
      ask.direct = true;
    }
  }
  return out.slice(0, MAX_SLOTS);
}

export interface Rect {
  left: number;
  top: number;
  width: number;
  height: number;
}

/** 圈朝屏幕里侧展开的四分之一圈：t ∈ [0, 1] 沿圈走，rad 是离球心的距离。 */
export function ringGeo(ball: Rect, W: number, H: number) {
  const cx = ball.left + ball.width / 2;
  const cy = ball.top + ball.height / 2;
  const left = cx > W / 2;
  const up = cy > H / 2;
  const pos = (rad: number, t: number) => {
    const ang = left ? (up ? 180 + 90 * t : 180 - 90 * t) : up ? 360 - 90 * t : 90 * t;
    const A = (ang * Math.PI) / 180;
    return { x: cx + rad * Math.cos(A), y: cy + rad * Math.sin(A), ang };
  };
  return { cx, cy, left, up, pos };
}
export type RingGeo = ReturnType<typeof ringGeo>;

/** 第 i 格的位置：前 4 格在内圈（132），其余在外圈（208）。 */
export function place(g: RingGeo, n: number, i: number) {
  const inner = Math.min(4, n);
  const outer = n - inner;
  if (i < inner) return g.pos(132, inner === 1 ? 0 : i / (inner - 1));
  const j = i - inner;
  return g.pos(208, outer <= 1 ? 0.5 : j / (outer - 1));
}

/** 二级小圆：在 278 的圈上，以所属格子的角度为中心排开。 */
export function placeSub(g: RingGeo, parentAng: number, count: number, j: number) {
  const spread = (j - (count - 1) / 2) * 0.16;
  const base = g.left ? (g.up ? (parentAng - 180) / 90 : (180 - parentAng) / 90) : g.up ? (360 - parentAng) / 90 : parentAng / 90;
  return g.pos(278, Math.max(0, Math.min(1, base + spread)));
}

/** 默认位置（球还没渲染时）：右下角。 */
export const defaultBall = (W: number, H: number): Rect => ({ left: W - 72, top: H - 72, width: 52, height: 52 });

/** 球的样式：没拖过就用 dock.css 的右下角。 */
export function fabStyle(pos: BallPos | null, H: number): Record<string, string | number> {
  if (!pos) return {};
  const b = Math.max(12, Math.min(H - 64, pos.b));
  return pos.side === "l" ? { left: 20, right: "auto", bottom: b } : { bottom: b };
}

/** 小窗贴着球朝里开。 */
export function popStyle(pos: BallPos | null, ball: Rect, H: number): Record<string, string | number> {
  if (!pos) return {};
  const up = ball.top > H / 2;
  const s: Record<string, string | number> = pos.side === "l" ? { left: 20, right: "auto" } : {};
  if (up) s.bottom = Math.round(H - ball.top + 12);
  else Object.assign(s, { top: Math.round(ball.top + ball.height + 12), bottom: "auto" });
  return s;
}
