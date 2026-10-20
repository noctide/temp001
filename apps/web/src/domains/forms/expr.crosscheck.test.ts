import { describe, it, expect } from "vitest";
import { evaluate, expectString, parseFieldValue, type Val } from "./expr";

interface FieldCase {
  type: string;
  value: string;
}
interface CrossCase {
  id: string;
  expr: string;
  fields: Record<string, FieldCase>;
  expect: { type: string; value: string };
}
interface Fixture {
  seed: number;
  count: number;
  cases: CrossCase[];
}

// 后端 `tests/expr_crosscheck.py` 按固定种子生成，前端读同一文件比对
const fixture = (await import("./expr.crosscheck.json")).default as Fixture;

describe("前后端对拍（后端生成期望，前端读同一文件）", () => {
  it("用例数 ≥ 300，固定种子", () => {
    expect(fixture.cases.length).toBeGreaterThanOrEqual(300);
    expect(fixture.cases.length).toBe(fixture.count);
    expect(fixture.seed).toBe(20261020);
  });

  for (const c of fixture.cases) {
    it(c.id, () => {
      const fields: Record<string, Val> = {};
      for (const [code, info] of Object.entries(c.fields)) {
        fields[code] = parseFieldValue(info.type, info.value);
      }
      const result = evaluate(c.expr, fields);
      expect(result.kind).toBe("number");
      expect(expectString(result)).toBe(c.expect.value);
    });
  }
});
