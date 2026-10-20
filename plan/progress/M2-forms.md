# M2-forms 进度（断点续做；每完成一步更新；上下文满了换新会话照着接着做）

- 工作包：plan/wp/M2-forms.md
- 分支：forms/M2-forms（已合并 local/integration，stage: 2 返工）

## 做到哪

- 阶段 1 已审核通过并合入。
- 阶段 2 返工（2026-10-20 审核 5 条）全部完成：
  1. 前端 `expr.ts` 十进制改为 BigInt 缩放整数（值 = 整数 × 10^-scale），删掉手写逐位加减、乘、除；
     `+ − ×` 精确，`÷` 保留 28 位有效数字、HALF_EVEN，去掉小数末尾 0、整数不去 0；`addDigits` 死循环与整数末尾 0 被吞的问题一并消失。
  2. `publish_check` 对每个表达式完整解析 + 函数名校验 + 静态类型检查；`CheckKind` 新增
     `SYNTAX` / `UNKNOWN_FUNCTION` / `TYPE_MISMATCH`；`referenced_fields` 解析失败不再吞错误（新增 `field_refs` 处理语法树）。
  3. 去掉字段引用上限（设计里的 20 次是引用基表，不是引用字段）；前端同步去掉 `BUDGET_REFS`；深度 32 保留。
  4. 预算登记为业务参数：`forms.expr.depthLimit`（32）、`forms.expr.computeMs`（10 ms），
     `tl.py gen` 后由 `P.forms.expr.*` + `ParamStore` 读取；应用层按 `COMPUTE_BUDGET_MS` 计时。
  5. `extract_refs` 删除，只保留 `referenced_fields`（去重保序）。
- 阶段 2 再返工（2026-10-20 审核 3 条，已合并 `local/integration` 拿到 c22–c30 与 arithmetic 规则）：
  1. 前端带小数除法：`decDiv` 补上 `10^(b.scale − a.scale)` 的指数（原来只算 `a.digits / b.digits`，
     `3 / 2.5` 得 0.12、`2.5 / 1` 得 25、`1000.05 * -0.75 / 10` 得 -750037.5、`round(3 / 0.1, 1)` 得 3）。
  2. 后端 `+ − ×` 改在按操作数算出的精度上下文里运算，不再被默认 28 位截断（c25、c30）；
     `÷` 显式用 28 位有效数字 + HALF_EVEN；`round` 量化也按操作数给足精度。
  3. 规范输出：新增 `format_number`（去小数末尾 0、整数不去 0、-0 → 0），后端契约测试改用它比较，
     不再直接比 Decimal 字符串；前端 `decToString` 沿用同一规范。
  4. 新增前后端对拍：`tests/expr_crosscheck.py` 固定种子 20261020 生成 320 个只含 `+ − × ÷ round`
     的算式并由后端算出期望，写入 `apps/web/src/domains/forms/expr.crosscheck.json`；
     `tests/test_expr_crosscheck.py` 校验文件与后端实现一致，前端 `expr.crosscheck.test.ts` 读同一文件比对。
     生成器统计：320 例（`+` 234、`-` 232、`×` 236、`÷` 215、`round` 235、引用字段 295）。
- 后端测试：145 passed, 2 skipped；契约测试 13 个文件全部通过。
- 前端在 Windows 上实际运行 `pnpm --dir apps/web test`（vitest 2.1.8 / node v26.4.0）：

```
> @titanloom/web@0.0.0 test D:\05_project\02_Titanloom-dev\wt\M2-forms\apps\web
> vitest run --passWithNoTests

 RUN  v2.1.8 D:/05_project/02_Titanloom-dev/wt/M2-forms/apps/web

 ✓ src/domains/forms/expr.test.ts (37 tests) 24ms
 ✓ src/domains/forms/expr.crosscheck.test.ts (321 tests) 105ms

 Test Files  2 passed (2)
      Tests  358 passed (358)
   Duration  1.93s
```

- `uv run python ops/tools/tl.py check`：12 项全过（✗ 0、! 0），含 tsc、pyright strict、ruff、pytest、契约测试、范围检查。

## 下一步

- 本次提交阶段 2 再返工（仅本地，`git commit -s`，末尾 `Agent: OpenCode`），等架构审核。
- 阶段 3（记录/修订/最小流程等）依赖 M1 底座接口，底座发布前不开工。

## 环境限制（已解决）

- 之前记录的"本机 vitest 无法执行"是错误结论：当时是 `expr.ts` 的十进制死循环耗尽内存。
  本次重写后 vitest 2.1.8 在 Windows / node v26.4.0 上正常跑完 28 个测试。

## 问题 / 变更请求

（无）
