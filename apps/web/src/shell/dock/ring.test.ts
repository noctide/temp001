import { describe, expect, it } from "vitest";
import { K } from "../../shared/base/reg";
import { place, placeSub, ringDefault, ringGeo, ringList, type RingEnv } from "./ring";

const env = (o: Partial<RingEnv> = {}): RingEnv => ({
  pending: 13,
  agentOk: true,
  autoOk: true,
  pageActions: [],
  askPage: { label: "问这一页" },
  ...o,
});

describe("ringList", () => {
  it("默认五格：管家 · 待办 · 客服 · 反馈 · 选取，待办带条数", () => {
    const L = ringList(ringDefault(), env());
    expect(L.map((x) => x.k)).toEqual(["ask", "todo", "help", "fb", "pick"]);
    expect(L[1]).toMatchObject({ name: K.shell.dock.ring.todo.name, params: { count: 13 } });
  });
  it("管家必留，勾掉也在；没开放管家时管家类格子都不出现", () => {
    const c = { ...ringDefault(), on: [] as never[] };
    expect(ringList(c, env()).map((x) => x.k)).toEqual(["ask"]);
    const all = { ...ringDefault(), on: ringDefault().order };
    expect(ringList(all, env({ agentOk: false })).map((x) => x.k)).toEqual(["todo", "help", "fb", "pick", "auto"]);
    expect(ringList(all, env({ autoOk: false })).map((x) => x.k)).not.toContain("auto");
  });
  it("这一页的动作并进管家的二级（最多取 2 个、带二级的摊平、总共最多 5 项），关掉就没有", () => {
    const pageActions = [{ label: "A" }, { label: "B", sub: [{ label: "B1" }, { label: "B2" }, { label: "B3" }] }, { label: "C" }];
    const ask = ringList(ringDefault(), env({ pageActions }))[0];
    expect(ask?.sub?.map((x) => x.label)).toEqual(["问这一页", "A", "B1", "B2", "B3"]);
    expect(ask?.direct).toBe(true);
    expect(ringList({ ...ringDefault(), page: false }, env({ pageActions }))[0]?.sub).toBeUndefined();
  });
});

describe("ringGeo", () => {
  it("球在右下角：圈朝左上展开，第 1 格在球正左边 132", () => {
    const g = ringGeo({ left: 1368, top: 828, width: 52, height: 52 }, 1440, 900);
    expect(g.left && g.up).toBe(true);
    const p = place(g, 5, 0);
    expect(Math.round(p.x)).toBe(1394 - 132);
    expect(Math.round(p.y)).toBe(854);
    const p5 = place(g, 5, 4); // 第 5 格在外圈（208），在两条边中间
    expect(Math.hypot(p5.x - g.cx, p5.y - g.cy)).toBeCloseTo(208);
    expect(p5.ang).toBeCloseTo(225);
  });
  it("球拖到左上：圈朝右下展开", () => {
    const g = ringGeo({ left: 20, top: 100, width: 52, height: 52 }, 1440, 900);
    expect(g.left || g.up).toBe(false);
    expect(place(g, 4, 0).x).toBeGreaterThan(46);
    const s = placeSub(g, place(g, 4, 0).ang, 3, 1);
    expect(Math.hypot(s.x - g.cx, s.y - g.cy)).toBeCloseTo(278);
  });
});
