# M2-forms 进度（断点续做；每完成一步更新；上下文满了换新会话照着接着做）

- 工作包：plan/wp/M2-forms.md
- 分支：forms/M2-forms（基准 331fb6a [local/integration]；已合并 local/integration，stage: 2）

## 做到哪

- 阶段 1 已审核通过并合入。
- 阶段 2 已完成：
  - 后端 domain/expr/*（lexer/parser/ast/types/functions/evaluator/dependency/errors，预算深度 32、字段引用 20、环检测）与 domain/conditions.py；
  - 前端 apps/web/src/domains/forms/expr.ts + apps/web/src/domains/forms/expr.test.ts（vitest，跑同一批 cases.json）；
  - publish_check 改用表达式解析器给出的引用字段列表，删掉正则；CheckProblem.kind 改为 StrEnum，去掉中文兜底句；
  - FormRelease/Section 改为不可变（Mapping/tuple/frozen）。
- tl.py check 全量通过：12 项 ✗ 0（含前端 tsc）；pytest 50 passed；契约测试 13 文件全部通过；无重复代码；范围检查通过。

## 下一步

- 本次提交阶段 2（仅本地，`git commit -s`，末尾 Agent: OpenCode），更新 plan/progress/M2-forms.md，回复"M2-forms 阶段 2 做完了"，等架构审核。
- 阶段 3（记录/修订/最小流程等）依赖 M1 底座接口，底座发布前不开工。

## 环境限制（已记录）

- 本机 vitest 无法执行：Node 运行时在 cgroup 内存限制下启动即 OOM（`node --check` 解析正常，但运行脚本堆迅速涨至 ~4GB OOM）；tl check 的前端项只跑 tsc，不跑 vitest，故不影响 tl check。前端表达式逻辑与后端位对齐（同一套 cases.json、相同函数语义），已用 tsc 严格模式通过类型检查。

## 问题 / 变更请求

（无）
