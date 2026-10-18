# M2-forms 进度（断点续做：每完成一步更新；上下文满了换新会话照着接着做）

- 工作包：plan/wp/M2-forms.md
- 分支：forms/M2-forms（基准 331fb6a [local/integration]；已合并 local/integration，拿到新检查工具与阶段 1 审核意见）

## 做到哪

- 已读完全部必读：仓库 AGENTS.md、forms/AGENTS.md、plan/wp/M2-forms.md（含审核记录·阶段 1 及阶段 2 提前说明）、plan/CODEMAP.md、后端详细设计·表单、表单平台子方案、平台能力契约、插件与扩展体系#2、contracts/expressions（functions.json + cases.json）、kernel 现有工具、tl.py check/gen/checks 机制。
- tl.py check 全量基线：12 项，✗ 0。
- 提交 ae711d7 被架构审核**返工**。审核记录 5 条全部落地（本阶段重做）：
  1. FW06 真不可变：FieldDefinition 改为 frozen StrEnum、settings 改为不可变 Mapping（MappingProxyType）；改名/改设置返回新对象（with_label/with_settings/with_required）；发布时快照共享不可变对象，旧版本不受草稿后续改动影响；补测试“发布后改名/改设置/删字段，旧版本都不变”。
  2. 公式挪出分区：Section 只留标题/字段列表/显示条件；计算字段表达式放进字段 settings["formula"]。
  3. settings 正式字段 + FieldKind 为 StrEnum，kind: FieldKind。
  4. 检查结果结构化：PublishCheckFailed 携带 CheckProblem 列表（section_index、field_code、ref、kind），不拼中文句子；field()/remove_field() KeyError 只带字段编号。
  5. 进度文件搬家：git mv PROGRESS.md plan/progress/M2-forms.md，以后只更新它。
- 重做后 tl.py check：12 项 ✗ 0；pytest 14 passed；契约测试 13 文件全部通过。
- 仅本地提交（返工重提 pending），未推送、未合并。

## 下一步

1. 当前：运行 tl.py check 全量确认 ✗ 0，再 `git commit -s` 提交阶段 1 重做（提交信息末尾 Agent: OpenCode），更新 plan/progress/M2-forms.md，回复"M2-forms 阶段 1 做完了"，等审核。
2. 阶段 2：表达式与显示条件（FW11 + cases.json 两端全过）。先写 tests，再实现 domain/expr/*（lexer/parser/ast/types/functions/evaluator/dependency/errors，预算：深度 32、字段引用 20、环检测）、domain/conditions.py；publish_check 阶段 2 应改为用表达式解析器给出的引用字段列表，删掉正则（审核提前说明）。前端 apps/web/src/domains/forms/expr.ts + vitest 跑同一批 cases.json。
3. 每阶段：tl.py check 全量通过（✗ 0），git commit -s（仅本地），更新 plan/progress/M2-forms.md，回复"M2-forms 阶段 N 做完了"。

## 问题 / 变更请求

（无）
