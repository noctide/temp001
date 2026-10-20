import { describe, it, expect } from "vitest";
import {
  decAdd,
  decDiv,
  decFromString,
  decMul,
  decToString,
  evaluate,
  parseFieldValue,
  ExprError,
  expectString,
  type Val,
} from "./expr";

interface FieldCase { type: string; value: string }
interface Case {
  id: string;
  expr: string;
  fields: Record<string, FieldCase>;
  expect?: { type: string; value: string };
  expectError?: string;
}

const casesJson = (await import("../../../../../packages/contracts/expressions/cases.json")).default as {
  cases: Case[];
};

describe("十进制运算规则（functions.json 的 arithmetic）", () => {
  it("整数末尾的 0 不去掉，小数末尾的 0 去掉", () => {
    expect(decToString(decFromString("10"))).toBe("10");
    expect(decToString(decMul(decFromString("10"), decFromString("1")))).toBe("10");
    expect(decToString(decFromString("2.50"))).toBe("2.5");
    expect(decToString(decAdd(decFromString("100"), decFromString("0.50")))).toBe("100.5");
  });

  it("除法保留 28 位有效数字（HALF_EVEN）", () => {
    expect(decToString(decDiv(decFromString("1"), decFromString("8")))).toBe("0.125");
    expect(decToString(decDiv(decFromString("1"), decFromString("3")))).toBe("0.3333333333333333333333333333");
    expect(decToString(decDiv(decFromString("2"), decFromString("3")))).toBe("0.6666666666666666666666666667");
    expect(decToString(decDiv(decFromString("12345678901234567890123456789"), decFromString("3")))).toBe(
      "4115226300411522630041152263",
    );
  });
});

describe("表达式求值器（与后端 position-aligned，跑 cases.json）", () => {
  for (const c of casesJson.cases) {
    it(c.id, () => {
      const fields: Record<string, Val> = {};
      for (const [code, info] of Object.entries(c.fields ?? {})) {
        fields[code] = parseFieldValue(info.type, info.value);
      }
      if (c.expectError) {
        let threw = false;
        try {
          evaluate(c.expr, fields);
        } catch (e) {
          threw = true;
          expect((e as ExprError).code).toBe(c.expectError);
        }
        expect(threw).toBe(true);
      } else {
        const result = evaluate(c.expr, fields);
        expect(result.kind).toBe(c.expect!.type);
        expect(expectString(result)).toBe(c.expect!.value);
      }
    });
  }
});
