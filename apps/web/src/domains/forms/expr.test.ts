import { describe, it, expect } from "vitest";
import { evaluate, parseFieldValue, ExprError, expectString, type Val } from "./expr";

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
