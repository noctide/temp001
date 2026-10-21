// 全局悬浮窗（Shell 子方案）：悬浮球 + 快捷圈 + 调整快捷圈。结构、类名和高保真原型 assets/dock.js 一一对应，样式来自 dock.css。
// 待办 / 客服 / 反馈小窗、待办抽屉、选取、管家侧栏下一步再接；现在点这几格只发出 tl:dock 事件。
import { Fragment, useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { K } from "../../shared/base/reg";
import { t } from "../../shared/base/i18n";
import { Icon } from "../../shared/ui/icons";
import {
  RING_ITEMS,
  defaultBall,
  fabStyle,
  loadCfg,
  loadPos,
  place,
  placeSub,
  popStyle,
  ringDefault,
  ringGeo,
  ringList,
  saveCfg,
  savePos,
  type BallPos,
  type PageAction,
  type Rect,
  type RingCfg,
  type RingEntry,
  type RingKey,
} from "./ring";
import { pendingFor, type DockRole } from "./todos";

export interface DockProps {
  role: DockRole;
  agentOk?: boolean; // 功能开放 · 用智能管家（接权限后由 shell 给）
  autoOk?: boolean; // 功能开放 · 建自动化
  pageActions?: PageAction[]; // 这一页在「管家」二级里的动作
  onOpen?: (k: RingKey) => void; // 待办 / 客服 / 反馈 / 选取（小窗做好前由外面接）
}

const MOBILE_RING = 600; // 窄于这个宽度，圈改成底部列表（和原型一致）

function emit(k: RingKey) {
  window.dispatchEvent(new CustomEvent("tl:dock", { detail: { open: k } }));
}

export function Dock({ role, agentOk = true, autoOk = true, pageActions = [], onOpen = emit }: DockProps) {
  const pending = useMemo(() => pendingFor(role), [role]);
  const over = pending.some((x) => x.due.k === "over");

  const [cfg, setCfg] = useState<RingCfg>(loadCfg);
  const [pos, setPos] = useState<BallPos | null>(loadPos);
  const [ring, setRing] = useState(false);
  const [rset, setRset] = useState(false);
  const [list, setList] = useState<RingEntry[]>([]);
  const [sel, setSel] = useState(0);
  const [sub, setSub] = useState<number | null>(null);
  const [subSel, setSubSel] = useState(0);
  const [kb, setKb] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [toasts, setToasts] = useState<{ id: number; msg: string }[]>([]);
  const [, setVp] = useState(0); // 窗口大小变了重画圈
  const fabRef = useRef<HTMLButtonElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const justDragged = useRef(false);
  const hoverT = useRef<number | undefined>(undefined);

  const open = ring || rset;
  // 球的位置不算悬停时上浮的 1px（transform），圈的位置才稳定；offset* 不受 transform 影响
  const ball = (): Rect => {
    const f = fabRef.current;
    return f ? { left: f.offsetLeft, top: f.offsetTop, width: f.offsetWidth, height: f.offsetHeight } : defaultBall(window.innerWidth, window.innerHeight);
  };

  const toast = useCallback((msg: string) => {
    const id = Date.now() + Math.random();
    setToasts((x) => [...x, { id, msg }]);
    window.setTimeout(() => setToasts((x) => x.filter((y) => y.id !== id)), 3600);
  }, []);

  const askPage: PageAction = useMemo(() => ({ label: t(K.shell.dock.ring.askPage), run: () => (location.href = "/agent") }), []);

  const ringOpen = useCallback(
    (s: number, byKeyboard: boolean) => {
      const L = ringList(cfg, { pending: pending.length, agentOk, autoOk, pageActions, askPage });
      setList(L);
      setSel(Math.min(s, L.length - 1));
      setSub(null);
      setKb(byKeyboard);
      setRset(false);
      setRing(true);
    },
    [cfg, pending.length, agentOk, autoOk, pageActions, askPage],
  );
  const closeAll = useCallback(() => {
    setRing(false);
    setRset(false);
    setSub(null);
  }, []);

  const ringRun = useCallback(
    (i: number, s: number | null) => {
      const x = list[i];
      if (!x) return;
      if (x.sub && s == null && !x.direct) {
        setSub(i);
        setSubSel(0);
        setSel(i);
        return;
      }
      setRing(false);
      setSub(null);
      if (s != null && x.sub) {
        const a = x.sub[s];
        if (a?.run) a.run();
        return;
      }
      switch (x.k) {
        case "ask":
        case "tasks":
          location.href = "/agent"; // 管家侧栏做好前先进管家页
          break;
        case "auto":
          location.href = "/automation";
          break;
        default:
          onOpen(x.k);
      }
    },
    [list, onOpen],
  );

  // 打开圈后把焦点放到选中的格子上（键盘可以直接接着操作）
  useEffect(() => {
    if (ring) rootRef.current?.querySelector<HTMLElement>(".dk-ri.on")?.focus();
  }, [ring, sel]);

  // 键盘：Ctrl / ⌘ + J 开圈（开着时再按 = 问管家）；圈里方向键、数字键、回车、Esc
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const typing = !!target?.matches?.("input,textarea,select");
      if ((e.ctrlKey || e.metaKey) && (e.key === "j" || e.key === "J")) {
        e.preventDefault();
        e.stopImmediatePropagation();
        if (ring) ringRun(0, null);
        else ringOpen(0, true);
        return;
      }
      if (ring) {
        const n = list.length;
        if (!n) return;
        if (e.key === "Escape") {
          e.preventDefault();
          if (sub != null) setSub(null);
          else {
            closeAll();
            fabRef.current?.focus();
          }
          return;
        }
        if (/^[1-8]$/.test(e.key) && !typing) {
          const i = +e.key - 1;
          if (i < n) {
            e.preventDefault();
            ringRun(i, null);
          }
          return;
        }
        if (sub != null) {
          const subs = list[sub]?.sub ?? [];
          if (e.key === "ArrowLeft") (e.preventDefault(), setSub(null));
          else if (e.key === "ArrowUp") (e.preventDefault(), setSubSel((v) => (v + 1) % subs.length));
          else if (e.key === "ArrowDown") (e.preventDefault(), setSubSel((v) => (v - 1 + subs.length) % subs.length));
          else if (e.key === "Enter" || e.key === " ") (e.preventDefault(), ringRun(sub, subSel));
          return;
        }
        if (e.key === "ArrowRight" && list[sel]?.sub) {
          e.preventDefault();
          setSub(sel);
          setSubSel(0);
        } else if (e.key === "ArrowUp" || (e.key === "Tab" && !e.shiftKey)) {
          e.preventDefault();
          setSel((v) => (v + 1) % n);
        } else if (e.key === "ArrowDown" || (e.key === "Tab" && e.shiftKey)) {
          e.preventDefault();
          setSel((v) => (v - 1 + n) % n);
        } else if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          ringRun(sel, null);
        } else if ((e.key === "j" || e.key === "J") && !typing) {
          e.preventDefault();
          ringRun(0, null);
        }
        return;
      }
      if (rset && e.key === "Escape") setRset(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [ring, rset, list, sel, sub, subSel, ringOpen, ringRun, closeAll]);

  useEffect(() => {
    const onResize = () => setVp((v) => v + 1);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  // 拖动：按住移动超过 5 px 就是拖，松手吸到最近的左 / 右边
  const onPointerDown = (e: React.PointerEvent<HTMLButtonElement>) => {
    const f = e.currentTarget;
    if (e.button > 0) return;
    const sx = e.clientX;
    const sy = e.clientY;
    const r0 = f.getBoundingClientRect();
    let moved = false;
    const move = (ev: PointerEvent) => {
      const dx = ev.clientX - sx;
      const dy = ev.clientY - sy;
      if (!moved && Math.hypot(dx, dy) < 5) return;
      if (!moved) {
        moved = true;
        setDragging(true);
        closeAll();
        f.setPointerCapture?.(ev.pointerId);
      }
      f.style.left = Math.max(4, Math.min(window.innerWidth - r0.width - 4, r0.left + dx)) + "px";
      f.style.right = "auto";
      f.style.top = Math.max(4, Math.min(window.innerHeight - r0.height - 4, r0.top + dy)) + "px";
      f.style.bottom = "auto";
    };
    const up = () => {
      document.removeEventListener("pointermove", move);
      document.removeEventListener("pointerup", up);
      if (!moved) return;
      setDragging(false);
      justDragged.current = true;
      window.setTimeout(() => (justDragged.current = false), 300);
      const r = f.getBoundingClientRect();
      const p: BallPos = { side: r.left + r.width / 2 < window.innerWidth / 2 ? "l" : "r", b: Math.round(window.innerHeight - r.bottom) };
      f.removeAttribute("style");
      savePos(p);
      setPos(p);
    };
    document.addEventListener("pointermove", move);
    document.addEventListener("pointerup", up);
  };

  const onFab = () => {
    if (justDragged.current) {
      justDragged.current = false;
      return;
    }
    if (open) closeAll();
    else ringOpen(0, false);
  };

  const updateCfg = (c: RingCfg) => {
    saveCfg(c);
    setCfg(c);
  };

  const W = window.innerWidth;
  const H = window.innerHeight;

  return (
    <div id="dk-root" ref={rootRef}>
      <div id="dk-errw" />
      <div id="dk-ringw">{ring && (W <= MOBILE_RING ? renderSheet() : renderRing())}</div>
      <div id="dk-selw" />
      <div id="dk-fabw">
        <button
          type="button"
          ref={fabRef}
          className={"dk-fab" + (dragging ? " drag" : "")}
          style={fabStyle(pos, H) as CSSProperties}
          aria-expanded={open}
          aria-haspopup="menu"
          aria-label={t(K.shell.dock.fab.label, { count: pending.length })}
          title={t(K.shell.dock.fab.tip)}
          onClick={onFab}
          onPointerDown={onPointerDown}
        >
          <Icon name={open ? "x" : "spark"} className="dk-i" hidden />
          {!open && pending.length > 0 && <b className={over ? "bad" : ""}>{pending.length}</b>}
        </button>
      </div>
      <div id="dk-popw">{rset && renderSettings()}</div>
      <div id="dk-drw" />
      <div id="dk-pk" />
      <div className="dk-toasts" id="dk-toasts">
        {toasts.map((x) => (
          <div key={x.id} className="m-toast">
            {x.msg}
          </div>
        ))}
      </div>
    </div>
  );

  function itemName(x: RingEntry) {
    return t(x.name, x.params);
  }

  function renderRing() {
    const g = ringGeo(ball(), W, H);
    const n = list.length;
    const ox = g.left ? { right: Math.round(W - g.cx + 36) } : { left: Math.round(g.cx + 36) };
    const ty = Math.round(g.cy + (g.up ? 1 : -1) * 36);
    const parent = sub != null ? list[sub] : undefined;
    return (
      <>
        <div className="dk-rscrim" aria-hidden="true" onClick={closeAll} />
        <div className="dk-ring" role="menu" aria-label={t(K.shell.dock.ring.label)}>
          {list.map((x, i) => {
            const p = place(g, n, i);
            const name = itemName(x);
            const desc = t(x.desc);
            return (
              <button
                key={x.k}
                type="button"
                role="menuitem"
                className={"dk-ri" + (i === sel ? " on" : "") + (x.sub ? " has" : "")}
                style={{ left: Math.round(p.x), top: Math.round(p.y) }}
                title={desc}
                aria-label={t(K.shell.dock.ring.itemLabel, { name, desc })}
                onClick={() => ringRun(i, null)}
                onMouseEnter={() => {
                  window.clearTimeout(hoverT.current);
                  if (x.sub && sub !== i)
                    hoverT.current = window.setTimeout(() => {
                      setSub(i);
                      setSubSel(0);
                      setSel(i);
                    }, 200);
                }}
                onMouseLeave={() => window.clearTimeout(hoverT.current)}
              >
                <span className="n">{i + 1}</span>
                {name}
              </button>
            );
          })}
          {parent?.sub &&
            parent.sub.map((s, j) => {
              const q = placeSub(g, place(g, n, sub as number).ang, parent.sub?.length ?? 0, j);
              return (
                <button
                  key={"s" + j}
                  type="button"
                  role="menuitem"
                  className={"dk-ri sub" + (j === subSel ? " on" : "")}
                  style={{ left: Math.round(q.x), top: Math.round(q.y) }}
                  onClick={() => ringRun(sub as number, j)}
                >
                  {s.label}
                </button>
              );
            })}
          <div className="dk-rfoot" style={{ ...ox, top: ty }}>
            <button
              type="button"
              className="dk-rset"
              title={t(K.shell.dock.ring.adjustTip)}
              onClick={() => {
                setRing(false);
                setRset(true);
              }}
            >
              {t(K.shell.dock.ring.adjust)}
            </button>
            <span className="dk-rhint">
              {kb ? t(K.shell.dock.ring.hintKeys, { name: list[sel] ? itemName(list[sel]) : "" }) : t(K.shell.dock.ring.hintDrag)}
            </span>
          </div>
        </div>
      </>
    );
  }

  function renderSheet() {
    return (
      <>
        <div className="dk-rscrim" onClick={closeAll} />
        <div className="dk-rsheet m-pop" role="menu" aria-label={t(K.shell.dock.ring.labelShort)}>
          {list.map((x, i) => sheetRow(x, i))}
          <button
            type="button"
            className="dk-rrow set"
            onClick={() => {
              setRing(false);
              setRset(true);
            }}
          >
            <span>{t(K.shell.dock.ring.adjustMore)}</span>
          </button>
        </div>
      </>
    );
  }

  function sheetRow(x: RingEntry, i: number) {
    return (
      <Fragment key={x.k}>
        <button type="button" role="menuitem" className={"dk-rrow" + (i === sel ? " on" : "")} onClick={() => ringRun(i, null)}>
          <b>{itemName(x)}</b>
          <span>{t(x.desc)}</span>
        </button>
        {x.sub &&
          (sub === i || x.direct) &&
          x.sub.map((s, j) => (
            <button key={j} type="button" role="menuitem" className="dk-rrow sub" onClick={() => ringRun(i, j)}>
              <b>{s.label}</b>
            </button>
          ))}
      </Fragment>
    );
  }

  function renderSettings() {
    const c = cfg;
    const pg = pageActions;
    return (
      <div className="dk-pop dk-rsp" role="dialog" aria-label={t(K.shell.dock.ringSet.title)} style={popStyle(pos, ball(), H) as CSSProperties}>
        <div className="dk-rsh">
          <b>{t(K.shell.dock.ringSet.title)}</b>
          <button type="button" className="dk-x" aria-label={t(K.shell.dock.ringSet.close)} onClick={() => setRset(false)}>
            <Icon name="x" className="dk-i" hidden />
          </button>
        </div>
        <div className="dk-body">
          <p className="m-small" style={{ margin: "0 0 6px" }}>
            {t(K.shell.dock.ringSet.intro)}
          </p>
          {c.order.map((k, i) => {
            const it = RING_ITEMS[k];
            const dis = !!it.agent && !agentOk;
            const note = it.lock ? t(K.shell.dock.ringSet.locked) : dis ? t(K.shell.dock.ringSet.agentClosed) : t(it.desc);
            return (
              <div key={k} className={"dk-rsr" + (dis ? " dis" : "")}>
                <label>
                  <input
                    type="checkbox"
                    checked={c.on.includes(k) || !!it.lock}
                    disabled={!!it.lock || dis}
                    onChange={() => updateCfg({ ...c, on: c.on.includes(k) ? c.on.filter((y) => y !== k) : [...c.on, k] })}
                  />{" "}
                  {t(it.name)}
                  <span className="m-small">{note}</span>
                </label>
                <span>
                  <button type="button" className="dk-x" aria-label={t(K.shell.dock.ringSet.up)} disabled={i === 0} onClick={() => updateCfg(move(c, i, -1))}>
                    ↑
                  </button>
                  <button
                    type="button"
                    className="dk-x"
                    aria-label={t(K.shell.dock.ringSet.down)}
                    disabled={i === c.order.length - 1}
                    onClick={() => updateCfg(move(c, i, 1))}
                  >
                    ↓
                  </button>
                </span>
              </div>
            );
          })}
          <div className="dk-rsr">
            <label>
              <input type="checkbox" checked={c.page} disabled={!agentOk} onChange={() => updateCfg({ ...c, page: !c.page })} />{" "}
              {t(K.shell.dock.ringSet.page)}
              <span className="m-small">
                {pg.length
                  ? t(K.shell.dock.ringSet.pageList, { list: pg.slice(0, 2).map((a) => a.label).join("、") })
                  : t(K.shell.dock.ringSet.pageNone)}
              </span>
            </label>
          </div>
          <p className="m-small" style={{ margin: "10px 0 4px" }}>
            {t(K.shell.dock.ringSet.plugins)}
          </p>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 6 }}>
            <button
              type="button"
              className="m-btn m-btn-s"
              onClick={() => {
                savePos(null);
                setPos(null);
                toast(t(K.shell.dock.ringSet.homeDone));
              }}
            >
              {t(K.shell.dock.ringSet.home)}
            </button>
            <button
              type="button"
              className="m-btn m-btn-s m-btn-t"
              onClick={() => {
                updateCfg(ringDefault());
                toast(t(K.shell.dock.ringSet.resetDone));
              }}
            >
              {t(K.shell.dock.ringSet.reset)}
            </button>
          </div>
        </div>
      </div>
    );
  }
}

function move(c: RingCfg, i: number, d: number): RingCfg {
  const j = i + d;
  if (j < 0 || j >= c.order.length) return c;
  const order = [...c.order];
  [order[i], order[j]] = [order[j] as RingKey, order[i] as RingKey];
  return { ...c, order };
}
