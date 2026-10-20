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
- 后端测试：103 passed, 2 skipped；契约测试 13 个文件全部通过。
- 前端在 Windows 上实际运行 `pnpm --dir apps/web test`（vitest 2.1.8 / node v26.4.0）：
  28 tests passed（26 个 cases.json 用例 + 2 个算术规则用例）。

```
> @titanloom/web@0.0.0 test D:\05_project\02_Titanloom-dev\wt\M2-forms\apps\web
> vitest run --passWithNoTests

 ✓ src/domains/forms/expr.test.ts (28 tests) 17ms

 Test Files  1 passed (1)
      Tests  28 passed (28)
   Duration  2.00s
```

- `uv run python ops/tools/tl.py check`：12 项全过（✗ 0、! 0），含 tsc、pyright strict、ruff、pytest、契约测试、范围检查。

## 下一步

- 本次提交阶段 2 返工（仅本地，`git commit -s`，末尾 `Agent: OpenCode`），等架构审核。
- 阶段 3（记录/修订/最小流程等）依赖 M1 底座接口，底座发布前不开工。

## 环境限制（已解决）

- 之前记录的"本机 vitest 无法执行"是错误结论：当时是 `expr.ts` 的十进制死循环耗尽内存。
  本次重写后 vitest 2.1.8 在 Windows / node v26.4.0 上正常跑完 28 个测试。

## 问题 / 变更请求

（无）
