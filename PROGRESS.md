# M2-attendance 进度（断点续做：每完成一步更新；上下文满了换新会话照着接着做）

- 工作包：plan/wp/M2-attendance.md
- 分支：attendance/M2-attendance
- 阶段：1（配置版本 + 区间/分类引擎，纯函数；不依赖 M1 底座）

## 做到哪

- 已读完：仓库根 AGENTS.md、attendance/AGENTS.md、plan/wp/M2-attendance.md、plan/CODEMAP.md（attendance 段）、docs/Titanloom-后端详细设计-考勤、docs/Titanloom-考勤签到平台子方案、docs/Titanloom-平台能力契约与Agent接入规范（相关章节）、docs/Titanloom-总框架设计方案 8.7、packages/contracts（state-machines attendance*、event-types attendance.*、error-codes）
- 基线 `uv run python ops/tools/tl.py check --fast` 已通过（✗ 0，8 项）
- 阶段 1 实现完成（待提交）：
  - domain/interval.py：区间 merge/intersect/subtract/total_seconds，半开 [start,end)，重叠/越界休息不重复扣，跨夜支持
  - domain/classify.py：有效区间 E 与正常区间 N 求交为正常，E−N 按日期属性（工作日/休息日/节假日）归互斥加班；所有策略输入由调用方传入，不猜默认（子方案第 23 条第 2 项）
  - store/models.py：5 对配置表（类型/班次/规则集/出勤方案/签到策略，定义+版本，schema attendance）
  - store/config.py：assert_no_publish_overlap，同范围同优先级已发布版本有效期重叠拒绝发布
  - migrations/versions/0001_initial.sql：上述 10 表的纯 SQL 迁移（无 alembic env，设计产物）
  - tests/test_interval.py（14）、tests/test_classify.py（10）、tests/test_config_publish.py（9）：33 个测试全部通过
- 决策：阶段 1 保持 manifest.yaml/i18n/attendance.yaml 为 0 登记（不新增 params/features/pages/objects/keys）。原因：tl.py gen 会改动 kernel/reg + web shared/base/reg，不在 attendance 允许修改路径内，会被 c_scope 拦截；阶段 1 纯后端函数、无界面，文案键与配置登记在后续有页面/接口时再补（架构审核）。

## 下一步

- `uv run python ops/tools/tl.py check --fast` 全部通过（✗ 0）；`uv run pytest apps/api/titanloom/attendance` 全部通过
- git commit -s（本地，不推送），提交信息第一行 `attendance: ...`，正文写设计章节，末尾 `Agent: <工具名>`
- 回复 “M2-attendance 阶段 1 做完了”，列出改文件与测试结果

## 问题 / 变更请求

（无）
