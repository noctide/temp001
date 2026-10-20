/* 表达式求值（前端）：与后端 `apps/api/titanloom/forms/domain/expr` 位对齐。
 * 只实现 `packages/contracts/expressions/functions.json` 的 6 个函数；
 * 数值用 BigInt 缩放整数（值 = digits × 10^-scale），不经 float；对外按十进制字符串编码。
 * 运算规则照 functions.json 的 arithmetic：+ − × 精确；÷ 保留 28 位有效数字、HALF_EVEN；
 * 结果去掉小数末尾多余的 0，整数不去 0（10 仍是 10）。 */

// ---------------------------------------------------------------------------
// 十进制（Dec）：{ neg, digits, scale }，值 = sign * digits * 10^-scale
// ---------------------------------------------------------------------------

export interface Dec {
  neg: boolean;
  digits: bigint; // >= 0
  scale: number;  // >= 0，小数位数
}

const TEN = 10n;
// functions.json · arithmetic.divisionSignificantDigits
const DIV_SIG = 28;

function pow10(n: number): bigint {
  return TEN ** BigInt(n);
}

function norm(d: Dec): Dec {
  let { neg, digits, scale } = d;
  if (digits === 0n) return { neg: false, digits: 0n, scale: 0 };
  while (scale > 0 && digits % TEN === 0n) {
    digits /= TEN;
    scale--;
  }
  return { neg, digits, scale };
}

export function decFromString(s: string): Dec {
  s = s.trim();
  let neg = false;
  if (s.startsWith("-")) { neg = true; s = s.slice(1); }
  else if (s.startsWith("+")) { s = s.slice(1); }
  const dot = s.indexOf(".");
  let digits: bigint;
  let scale = 0;
  if (dot >= 0) {
    scale = s.length - dot - 1;
    digits = BigInt(s.slice(0, dot) + s.slice(dot + 1));
  } else {
    digits = BigInt(s);
  }
  return norm({ neg, digits, scale });
}

export function decToString(d: Dec): string {
  d = norm(d);
  if (d.digits === 0n) return "0";
  const { neg, digits, scale } = d;
  const s = digits.toString();
  let body: string;
  if (scale === 0) {
    body = s;
  } else if (scale >= s.length) {
    body = "0." + "0".repeat(scale - s.length) + s;
  } else {
    body = s.slice(0, s.length - scale) + "." + s.slice(s.length - scale);
  }
  return (neg ? "-" : "") + body;
}

function alignedDigits(a: Dec, b: Dec): [bigint, bigint] {
  const scale = Math.max(a.scale, b.scale);
  return [a.digits * pow10(scale - a.scale), b.digits * pow10(scale - b.scale)];
}

export function decCmp(a: Dec, b: Dec): number {
  a = norm(a); b = norm(b);
  if (a.neg && !b.neg) return -1;
  if (!a.neg && b.neg) return 1;
  const [x, y] = alignedDigits(a, b);
  const c = x === y ? 0 : x < y ? -1 : 1;
  return a.neg ? -c : c;
}
export function decEq(a: Dec, b: Dec): boolean { return decCmp(a, b) === 0; }
export function decLt(a: Dec, b: Dec): boolean { return decCmp(a, b) < 0; }
export function decLe(a: Dec, b: Dec): boolean { return decCmp(a, b) <= 0; }
export function decGt(a: Dec, b: Dec): boolean { return decCmp(a, b) > 0; }
export function decGe(a: Dec, b: Dec): boolean { return decCmp(a, b) >= 0; }

export function decAdd(a: Dec, b: Dec): Dec {
  a = norm(a); b = norm(b);
  const scale = Math.max(a.scale, b.scale);
  const [x, y] = alignedDigits(a, b);
  if (a.neg === b.neg) return norm({ neg: a.neg, digits: x + y, scale });
  if (x === y) return { neg: false, digits: 0n, scale: 0 };
  if (x > y) return norm({ neg: a.neg, digits: x - y, scale });
  return norm({ neg: b.neg, digits: y - x, scale });
}
export function decSub(a: Dec, b: Dec): Dec { return decAdd(a, { neg: !b.neg, digits: b.digits, scale: b.scale }); }

export function decMul(a: Dec, b: Dec): Dec {
  a = norm(a); b = norm(b);
  if (a.digits === 0n || b.digits === 0n) return { neg: false, digits: 0n, scale: 0 };
  return norm({ neg: a.neg !== b.neg, digits: a.digits * b.digits, scale: a.scale + b.scale });
}

export function decDiv(a: Dec, b: Dec): Dec {
  a = norm(a); b = norm(b);
  if (b.digits === 0n) throw new Error("divide by zero");
  if (a.digits === 0n) return { neg: false, digits: 0n, scale: 0 };
  const neg = a.neg !== b.neg;
  // value = (a.digits / b.digits) × 10^(b.scale − a.scale)
  const exp = b.scale - a.scale;
  // 让整数商至少 DIV_SIG+1 位（多一位保护位），再按有效数字舍入
  const dA = a.digits.toString().length;
  const dB = b.digits.toString().length;
  const guard = Math.max(0, DIV_SIG + 1 - (dA - dB));
  const numerator = a.digits * pow10(guard);
  let digits = numerator / b.digits;
  const remainder = numerator % b.digits;
  let resultScale = guard - exp;
  if (resultScale < 0) {
    digits *= pow10(-resultScale);
    resultScale = 0;
  }
  const len = digits.toString().length;
  if (len > DIV_SIG) {
    const drop = len - DIV_SIG;
    const divisor = pow10(drop);
    const kept = digits / divisor;
    const dropped = digits % divisor;
    const half = divisor / 2n;
    let roundUp: boolean;
    if (dropped > half) roundUp = true;
    else if (dropped < half) roundUp = false;
    else roundUp = remainder !== 0n || kept % 2n === 1n; // HALF_EVEN
    digits = kept + (roundUp ? 1n : 0n);
    resultScale -= drop;
    if (resultScale < 0) {
      digits *= pow10(-resultScale);
      resultScale = 0;
    }
  }
  return norm({ neg, digits, scale: resultScale });
}

// ---------------------------------------------------------------------------
// 错误
// ---------------------------------------------------------------------------

export class ExprError extends Error {
  readonly code: string;
  constructor(code: string, message = "") {
    super(code + (message ? ": " + message : ""));
    this.code = code;
    Object.setPrototypeOf(this, ExprError.prototype);
  }
}

// ---------------------------------------------------------------------------
// 值类型
// ---------------------------------------------------------------------------

export type ValueKind = "number" | "date" | "time" | "text" | "bool";

interface NumVal { kind: "number"; dec: Dec }
interface DateVal { kind: "date"; value: Date }   // UTC 日期
interface TimeVal { kind: "time"; value: number }  // 分钟（00:00 起）
interface TextVal { kind: "text"; value: string }
interface BoolVal { kind: "bool"; value: boolean }
export type Val = NumVal | DateVal | TimeVal | TextVal | BoolVal;

function numVal(d: Dec): NumVal { return { kind: "number", dec: d }; }

export function parseFieldValue(kind: string, text: string): Val {
  if (kind === "number") return numVal(decFromString(text));
  if (kind === "date") return { kind: "date", value: new Date(text + "T00:00:00Z") };
  if (kind === "time") {
    const parts = text.split(":");
    const h = Number(parts[0]!);
    const m = Number(parts[1]!);
    return { kind: "time", value: h * 60 + m };
  }
  if (kind === "text") return { kind: "text", value: text };
  if (kind === "bool") return { kind: "bool", value: text.toLowerCase() === "true" };
  throw new Error(`unknown field type: ${kind}`);
}

export function encodeVal(v: Val): string {
  if (v.kind === "number") return decToString(v.dec);
  if (v.kind === "date") return v.value.toISOString().slice(0, 10);
  if (v.kind === "time") {
    const m = v.value;
    const h = Math.floor(m / 60), mm = m % 60;
    return String(h).padStart(2, "0") + ":" + String(mm).padStart(2, "0");
  }
  if (v.kind === "text") return v.value;
  if (v.kind === "bool") return v.value ? "true" : "false";
  throw new Error("unreachable");
}

// ---------------------------------------------------------------------------
// 词法分析
// ---------------------------------------------------------------------------

const TOK = {
  NUMBER: "NUMBER", FIELD_REF: "FIELD_REF", IDENT: "IDENT",
  LPAREN: "LPAREN", RPAREN: "RPAREN", COMMA: "COMMA",
  PLUS: "PLUS", MINUS: "MINUS", STAR: "STAR", SLASH: "SLASH",
  EQ: "EQ", NE: "NE", LTE: "LTE", GTE: "GTE", LT: "LT", GT: "GT",
  EOF: "EOF",
} as const;

interface Token { type: string; value: string; pos: number }

const TOKEN_SPEC: [string, RegExp][] = [
  [TOK.NE, /^!=/], [TOK.LTE, /^<=/], [TOK.GTE, /^>=/], [TOK.EQ, /^=/],
  [TOK.LT, /^</], [TOK.GT, /^>/], [TOK.NUMBER, /^\d+(?:\.\d+)?/],
  [TOK.FIELD_REF, /^\$[A-Za-z_][A-Za-z0-9_]*/], [TOK.IDENT, /^[A-Za-z_][A-Za-z0-9_]*/],
  [TOK.LPAREN, /^\(/], [TOK.RPAREN, /^\)/], [TOK.COMMA, /^,/],
  [TOK.PLUS, /^\+/], [TOK.MINUS, /^-/], [TOK.STAR, /^\*/], [TOK.SLASH, /^\//],
];
const WS = /^\s+/;

function tokenize(text: string): Token[] {
  const tokens: Token[] = [];
  let pos = 0;
  while (pos < text.length) {
    const m = WS.exec(text.slice(pos));
    if (m) { pos += m[0].length; continue; }
    const rest = text.slice(pos);
    let hit = false;
    for (const [type, re] of TOKEN_SPEC) {
      const mm = re.exec(rest);
      if (mm) { tokens.push({ type, value: mm[0], pos }); pos += mm[0].length; hit = true; break; }
    }
    if (!hit) throw new ExprError("SYNTAX", `非法字符：${text[pos]!} (位置 ${pos})`);
  }
  tokens.push({ type: TOK.EOF, value: "", pos });
  return tokens;
}

// ---------------------------------------------------------------------------
// 语法分析（递归下降）：or > and > not > 比较 > +/- > * / > 原子
// ---------------------------------------------------------------------------

interface LitNode { kind: "Literal"; dec: Dec }
interface RefNode { kind: "FieldRef"; code: string }
interface BinNode { kind: "Binary"; op: string; left: ExprNode; right: ExprNode }
interface UnNode { kind: "Unary"; op: "not"; operand: ExprNode }
interface CallNode { kind: "Call"; name: string; args: ExprNode[] }
export type ExprNode = LitNode | RefNode | BinNode | UnNode | CallNode;

const COMP_OPS = new Set(["=", "!=", "<", "<=", ">", ">="]);
const ADD_OPS = new Set(["+", "-"]);
const MUL_OPS = new Set(["*", "/"]);

// 三元比较结果 c (=-1/0/1) 与运算符 op 组合成布尔结果
function cmpResult(c: number, op: string): boolean {
  return op === "<" ? c < 0 : op === "<=" ? c <= 0 : op === ">" ? c > 0 : c >= 0;
}

class Parser {
  private tokens: Token[];
  private pos = 0;
  constructor(text: string) { this.tokens = tokenize(text); }
  private get cur(): Token { return this.tokens[this.pos]!; }
  private advance(): Token { return this.tokens[this.pos++]!; }
  private match(type: string, value?: string): boolean {
    const t = this.cur;
    if (t.type !== type) return false;
    if (value !== undefined && t.value !== value) return false;
    this.pos++;
    return true;
  }
  private expect(type: string, value?: string): Token {
    const t = this.cur;
    if (t.type !== type || (value !== undefined && t.value !== value)) {
      throw new ExprError("SYNTAX", `期望 ${type}，实际 ${t.type} ${JSON.stringify(t.value)} (位置 ${t.pos})`);
    }
    this.pos++;
    return t;
  }
  parse(): ExprNode {
    const expr = this.or();
    this.expect(TOK.EOF);
    return expr;
  }
  private or(): ExprNode {
    let left = this.and_();
    while (this.match(TOK.IDENT, "or")) left = { kind: "Binary", op: "or", left, right: this.and_() };
    return left;
  }
  private and_(): ExprNode {
    let left = this.not_();
    while (this.match(TOK.IDENT, "and")) left = { kind: "Binary", op: "and", left, right: this.not_() };
    return left;
  }
  private not_(): ExprNode {
    if (this.match(TOK.IDENT, "not")) return { kind: "Unary", op: "not", operand: this.not_() };
    return this.comparison();
  }
  private comparison(): ExprNode {
    let left = this.additive();
    while (COMP_OPS.has(this.cur.value)) {
      const op = this.cur.value;
      this.advance();
      left = { kind: "Binary", op, left, right: this.additive() };
    }
    return left;
  }
  private additive(): ExprNode {
    let left = this.multiplicative();
    while (ADD_OPS.has(this.cur.value)) {
      const op = this.cur.value;
      this.advance();
      left = { kind: "Binary", op, left, right: this.multiplicative() };
    }
    return left;
  }
  private multiplicative(): ExprNode {
    let left = this.primary();
    while (MUL_OPS.has(this.cur.value)) {
      const op = this.cur.value;
      this.advance();
      left = { kind: "Binary", op, left, right: this.primary() };
    }
    return left;
  }
  private primary(): ExprNode {
    const t = this.cur;
    if (t.type === TOK.NUMBER) {
      this.advance();
      return { kind: "Literal", dec: decFromString(t.value) };
    }
    if (t.type === TOK.FIELD_REF) {
      this.advance();
      return { kind: "FieldRef", code: t.value.slice(1) };
    }
    if (t.type === TOK.IDENT) {
      const name = t.value;
      this.advance();
      if (this.match(TOK.LPAREN)) {
        const args: ExprNode[] = [];
        if (!this.match(TOK.RPAREN)) {
          args.push(this.or());
          while (this.match(TOK.COMMA)) args.push(this.or());
        }
        this.expect(TOK.RPAREN);
        return { kind: "Call", name, args };
      }
      throw new ExprError("SYNTAX", `意外的标识符：${JSON.stringify(name)}`);
    }
    if (t.type === TOK.LPAREN) {
      this.advance();
      const inner = this.or();
      this.expect(TOK.RPAREN);
      return inner;
    }
    throw new ExprError("SYNTAX", `意外的符号：${t.type} ${JSON.stringify(t.value)} (位置 ${t.pos})`);
  }
}

export function parse(text: string): ExprNode { return new Parser(text).parse(); }

// ---------------------------------------------------------------------------
// 内置函数
// ---------------------------------------------------------------------------

function requireArgs(name: string, args: Val[], expected: ValueKind[]): void {
  if (args.length !== expected.length) {
    throw new ExprError("TYPE_MISMATCH", `${name} 需要 ${expected.length} 个参数，实际 ${args.length} 个`);
  }
  for (let i = 0; i < args.length; i++) {
    const arg = args[i]!;
    if (arg.kind !== expected[i]) {
      throw new ExprError("TYPE_MISMATCH", `${name} 第 ${i + 1} 个参数期望 ${expected[i]}，实际 ${arg.kind}`);
    }
  }
}
function asNumber(v: Val, where: string): Dec {
  if (v.kind !== "number") throw new ExprError("TYPE_MISMATCH", `${where} 期望 number，实际 ${v.kind}`);
  return v.dec;
}
function asDate(v: Val, where: string): Date {
  if (v.kind !== "date") throw new ExprError("TYPE_MISMATCH", `${where} 期望 date，实际 ${v.kind}`);
  return v.value;
}
function asTime(v: Val, where: string): number {
  if (v.kind !== "time") throw new ExprError("TYPE_MISMATCH", `${where} 期望 time，实际 ${v.kind}`);
  return v.value;
}
function asBool(v: Val, where: string): boolean {
  if (v.kind !== "bool") throw new ExprError("TYPE_MISMATCH", `${where} 期望 bool，实际 ${v.kind}`);
  return v.value;
}

const MS_PER_DAY = 24 * 60 * 60 * 1000;
function daysBetween(a: Val, b: Val): Val {
  requireArgs("daysBetween", [a, b], ["date", "date"]);
  const d1 = asDate(a, "daysBetween"), d2 = asDate(b, "daysBetween");
  const days = Math.round((d1.getTime() - d2.getTime()) / MS_PER_DAY);
  return numVal(decFromString(String(days)));
}
function workdays(a: Val, b: Val): Val {
  requireArgs("workdays", [a, b], ["date", "date"]);
  const d1 = asDate(a, "workdays"), d2 = asDate(b, "workdays");
  const lo = d1.getTime() <= d2.getTime() ? d1 : d2;
  const hi = d1.getTime() <= d2.getTime() ? d2 : d1;
  let count = 0;
  const cur = new Date(lo.getTime());
  while (cur.getTime() <= hi.getTime()) {
    const wd = cur.getUTCDay();
    if (wd >= 1 && wd <= 5) count++;
    cur.setUTCDate(cur.getUTCDate() + 1);
  }
  return numVal(decFromString(String(count)));
}
function hoursBetween(a: Val, b: Val): Val {
  requireArgs("hoursBetween", [a, b], ["time", "time"]);
  const m1 = asTime(a, "hoursBetween"), m2 = asTime(b, "hoursBetween");
  const minutes = m2 >= m1 ? m2 - m1 : (24 * 60 - m1) + m2;
  return numVal(decDiv(decFromString(String(minutes)), decFromString("60")));
}
function sumFn(args: Val[]): Val {
  let total = decFromString("0");
  for (const arg of args) total = decAdd(total, asNumber(arg, "sum"));
  return numVal(total);
}
function ifFn(args: Val[]): Val {
  if (args.length !== 3) throw new ExprError("TYPE_MISMATCH", `if 需要 3 个参数，实际 ${args.length} 个`);
  return asBool(args[0]!, "if 第 1 个参数") ? args[1]! : args[2]!;
}
function roundFn(args: Val[]): Val {
  if (args.length !== 2) throw new ExprError("TYPE_MISMATCH", `round 需要 2 个参数，实际 ${args.length} 个`);
  const x = asNumber(args[0]!, "round 第 1 个参数");
  const nVal = asNumber(args[1]!, "round 第 2 个参数");
  const nStr = decToString(nVal);
  if (!/^-?\d+$/.test(nStr)) throw new ExprError("TYPE_MISMATCH", "round 第 2 个参数必须是整数");
  const nInt = parseInt(nStr, 10);
  return numVal(decRound(x, nInt));
}

const FUNCTIONS: Record<string, (args: Val[]) => Val> = {
  daysBetween: (args) => daysBetween(args[0]!, args[1]!),
  workdays: (args) => workdays(args[0]!, args[1]!),
  hoursBetween: (args) => hoursBetween(args[0]!, args[1]!),
  sum: (args) => sumFn(args),
  if: (args) => ifFn(args),
  round: (args) => roundFn(args),
};

// x 量化到 10^-n，半数进位（HALF_UP，负数向远离 0 的方向）
function decRound(x: Dec, n: number): Dec {
  x = norm(x);
  if (n >= x.scale) return x;
  const drop = x.scale - n;
  const divisor = pow10(drop);
  const kept = x.digits / divisor;
  const dropped = x.digits % divisor;
  const roundUp = dropped * 2n >= divisor;
  const digits = kept + (roundUp ? 1n : 0n);
  if (n >= 0) return norm({ neg: x.neg, digits, scale: n });
  return norm({ neg: x.neg, digits: digits * pow10(-n), scale: 0 });
}

function resolveFunction(name: string): (args: Val[]) => Val {
  const fn = FUNCTIONS[name];
  if (!fn) throw new ExprError("UNKNOWN_FUNCTION", `未知函数：${name}`);
  return fn;
}

// ---------------------------------------------------------------------------
// 求值器
// ---------------------------------------------------------------------------

// 与业务参数 forms.expr.depthLimit 的出厂默认值一致；阶段 3 接 API 后由后端下发。
const DEFAULT_DEPTH_LIMIT = 32;

interface Budget { depthLimit: number }

export function evaluate(expr: string, fields: Record<string, Val>): Val {
  const tree = parse(expr);
  const budget: Budget = { depthLimit: DEFAULT_DEPTH_LIMIT };
  return evalNode(tree, fields, budget, 0);
}

function evalNode(node: ExprNode, fields: Record<string, Val>, budget: Budget, depth: number): Val {
  if (depth > budget.depthLimit) throw new ExprError("BUDGET_DEPTH", `表达式嵌套深度超过 ${budget.depthLimit}`);
  if (node.kind === "Literal") return numVal(node.dec);
  if (node.kind === "FieldRef") {
    if (!(node.code in fields)) throw new ExprError("UNKNOWN_FIELD", `未定义的字段：${node.code}`);
    return fields[node.code]!;
  }
  if (node.kind === "Unary") {
    const unary = node as UnNode;
    if (unary.op !== "not") throw new ExprError("SYNTAX", `未知一元运算符：${unary.op}`);
    const operand = asBool(evalNode(unary.operand, fields, budget, depth + 1), "not");
    return { kind: "bool", value: !operand };
  }
  if (node.kind === "Binary") return evalBinary(node.op, node.left, node.right, fields, budget, depth + 1);
  if (node.kind === "Call") {
    const fn = resolveFunction(node.name);
    const args = node.args.map((a) => evalNode(a, fields, budget, depth + 1));
    return fn(args);
  }
  throw new ExprError("SYNTAX", "未知表达式节点");
}

function evalBinary(op: string, left: ExprNode, right: ExprNode, fields: Record<string, Val>, budget: Budget, depth: number): Val {
  const lv = evalNode(left, fields, budget, depth);
  const rv = evalNode(right, fields, budget, depth);
  if (op === "and" || op === "or") {
    const l = asBool(lv, op), r = asBool(rv, op);
    return { kind: "bool", value: op === "and" ? l && r : l || r };
  }
  if (op === "+" || op === "-" || op === "*" || op === "/") {
    const a = asNumber(lv, op), b = asNumber(rv, op);
    let d: Dec;
    if (op === "+") d = decAdd(a, b);
    else if (op === "-") d = decSub(a, b);
    else if (op === "*") d = decMul(a, b);
    else {
      if (decEq(b, decFromString("0"))) throw new ExprError("DIVIDE_BY_ZERO", "除数不能为零");
      d = decDiv(a, b);
    }
    return numVal(d);
  }
  if (COMP_OPS.has(op)) {
    if (lv.kind !== rv.kind) throw new ExprError("TYPE_MISMATCH", `比较两侧类型不一致：${lv.kind} vs ${rv.kind}`);
    // 此处 rv.kind 与 lv.kind 相等（上面已断言），按 lv.kind 缩窄并对 rv 做类型断言
    if (op === "=" || op === "!=") {
      let eq: boolean;
      if (lv.kind === "number") eq = decEq(lv.dec, (rv as NumVal).dec);
      else if (lv.kind === "date") eq = lv.value.getTime() === (rv as DateVal).value.getTime();
      else if (lv.kind === "time") eq = lv.value === (rv as TimeVal).value;
      else if (lv.kind === "text") eq = lv.value === (rv as TextVal).value;
      else eq = lv.value === (rv as BoolVal).value;
      return { kind: "bool", value: op === "=" ? eq : !eq };
    }
    if (lv.kind === "bool") throw new ExprError("TYPE_MISMATCH", "布尔值不支持大小比较");
    let result: boolean;
    if (lv.kind === "number") {
      result = cmpResult(decCmp(lv.dec, (rv as NumVal).dec), op);
    } else if (lv.kind === "date") {
      result = cmpResult(lv.value.getTime() - (rv as DateVal).value.getTime(), op);
    } else if (lv.kind === "time") {
      result = cmpResult(lv.value - (rv as TimeVal).value, op);
    } else {
      const c = lv.value < (rv as TextVal).value ? -1 : lv.value > (rv as TextVal).value ? 1 : 0;
      result = cmpResult(c, op);
    }
    return { kind: "bool", value: result };
  }
  throw new ExprError("SYNTAX", `未知运算符：${op}`);
}

// ---------------------------------------------------------------------------
// 显示条件
// ---------------------------------------------------------------------------

export function evaluateCondition(expr: string | null, fields: Record<string, Val>): boolean {
  if (!expr) return true;
  const result = evaluate(expr, fields);
  if (result.kind !== "bool") throw new ExprError("TYPE_MISMATCH", `显示条件结果必须为 bool，实际 ${result.kind}`);
  return result.value;
}

// 供测试/外部比较用：把 Val 编码成与 cases.json 一致的字符串
export function expectString(v: Val): string {
  if (v.kind === "number") return decToString(v.dec);
  if (v.kind === "date") return v.value.toISOString().slice(0, 10);
  if (v.kind === "time") return encodeVal(v);
  if (v.kind === "text") return v.value;
  if (v.kind === "bool") return v.value ? "true" : "false";
  throw new Error("unreachable");
}
