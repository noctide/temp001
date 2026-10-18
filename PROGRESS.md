# M2-forms 进度（断点续做：每完成一步更新；上下文满了换新会话照着接着做）

- 工作包：plan/wp/M2-forms.md
- 分支：forms/M2-forms（基准 331fb6a [local/integration]）

## 做到哪

- 已读完全部必读：仓库 AGENTS.md、forms/AGENTS.md、plan/wp/M2-forms.md、plan/CODEMAP.md、后端详细设计·表单、表单平台子方案、平台能力契约、插件与扩展体系#2、contracts/expressions（functions.json + cases.json）、kernel 现有工具、tl.py check/gen/checks 机制。
- tl.py check 全量基线：12 项，✗ 0（pytest 9 passed，契约 13 文件全部通过，前端 tsc 跳过）。
- 方案已与用户确认：阶段 1–2 只做 domain 层（纯 Python/TS，不碰 DB/网络/时钟；表单定义、草稿、发布版本为内存领域对象，底座 access/execution/facilities API 未发布不造替代品）；表达式错误用 domain 自定义 ExprError，不占用注册错误码；manifest.yaml / i18n/forms.yaml 暂不新增登记。

## 下一步

1. 阶段 1：字段与表单定义、草稿/发布/版本、发布前检查（FW06、FW18）——先写 tests/test_form_definition.py，再实现 domain/field.py、domain/form.py、domain/publish_check.py。
2. 阶段 2：表达式与显示条件（FW11 + cases.json 两端全过）——先写 tests，再实现 domain/expr/*、domain/conditions.py，以及前端 expr.ts + vitest。
3. 每阶段：tl.py check 全量通过（✗ 0），git commit -s（仅本地，不推送），更新 PROGRESS.md，回复"M2-forms 阶段 N 做完了"。

## 问题 / 变更请求

（无）
