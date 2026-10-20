import { describe, expect, it } from "vitest";
import { devSession } from "./devSession";

describe("devSession", () => {
  it("和原型一样用 ?role= 切换示例身份，未知身份回到部门负责人", () => {
    expect(devSession("").scope).toBe(devSession("?role=lead").scope);
    expect(devSession("?role=member").avatar).not.toBe(devSession("").avatar);
    expect(devSession("?role=nobody")).toEqual(devSession(""));
  });
});
