import { describe, expect, it } from "vitest";
import { activeNav } from "./nav";

describe("activeNav", () => {
  it("首页只认根路径", () => {
    expect(activeNav("/")).toBe("home");
    expect(activeNav("/xyz")).toBeNull();
  });
  it("其余认前缀，不误认相似前缀", () => {
    expect(activeNav("/forms")).toBe("forms");
    expect(activeNav("/forms/fa/fill")).toBe("forms");
    expect(activeNav("/formsx")).toBeNull();
    expect(activeNav("/admin/plugins")).toBe("admin");
  });
});
