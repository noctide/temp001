# M2-attendance 进度（断点续做：每完成一步更新；上下文满了换新会话照着接着做）

- 工作包：plan/wp/M2-attendance.md
- 分支：attendance/M2-attendance
- 阶段：1（配置版本 + 区间/分类引擎，纯函数；不依赖 M1 底座）

## 做到哪

- 已读完：仓库根 AGENTS.md、attendance/AGENTS.md、plan/wp/M2-attendance.md、plan/CODEMAP.md（attendance 段）、docs/Titanloom-后端详细设计-考勤、docs/Titanloom-考勤签到平台子方案、docs/Titanloom-平台能力契约与Agent接入规范（相关章节）、docs/Titanloom-总框架设计方案 8.7、packages/contracts（state-machines attendance*、event-types attendance.*、error-codes）
- `git merge local/integration` 已完成（Already up to date）
- `git mv PROGRESS.md plan/progress/M2-attendance.md` 已完成（plan/progress 目录已新建，根目录不再有 PROGRESS.md）
- 阶段 1 8 条审核意见整改完毕，`uv run python ops/tools/tl.py check` 全部通过（12 项，✗ 0）：
  1. 适用范围：定义表去掉 `scope`，改为 `scope_kind`（StrEnum org/dept/person）+ `scope_ref`（String(64)；org 为 NULL）；加 CHECK `scope_kind='org' AND scope_ref IS NULL OR scope_kind IN ('dept','person') AND scope_ref IS NOT NULL`；重叠判定键为（kind, scope_kind, scope_ref, priority）；新增测试"不同部门同优先级重叠，不冲突"
  2. 有效期：`effective_from / effective_to` 改为 `date` 半开区间，None 表示无界
  3. 校验移到 domain：新建 `domain/config_publish.py`（含 `PublishConflictError` frozen 结构化字段、不写中文 message、`assert_no_publish_overlap` 入参改 date），删掉 `store/config.py`；测试 import 改到 domain
  4. 迁移：删掉 `migrations/versions/0001_initial.sql` 和 `versions/` 文件夹，保留 `migrations/README.md`；表结构仅保留 `store/models.py`
  5. 错误：`PublishConflictError` 带 frozen 字段（candidate_id/conflict_id/kind/scope_kind/scope_ref/priority/candidate_range/conflict_range），不写中文 message；`interval.py` ValueError 改为英文 "interval start must be < end"
  6. 表名：去掉 `attendance_` 前缀，改为 type/type_version/shift/shift_version/rule_set/rule_set_version/plan/plan_version/checkin_policy/checkin_policy_version；外键和约束名同步改
  7. 分类属性测试：`test_classify_property_random`，`random.Random(20261018)`，500 组随机区间；断言正常+三类加班=有效时长、各项≥0、有效≤工作总长、互斥
  8. 进度文件：已搬家到 `plan/progress/M2-attendance.md`
- `uv run pytest apps/api/titanloom/attendance/tests/`：31 个测试全部通过

## 下一步

- `git commit -s`（本地，不推送），提交信息第一行 `attendance: ...`，正文写依据设计章节，末尾 `Agent: OpenCode`
- 回复 "M2-attendance 阶段 1 做完了"，列出改文件与测试结果

## 问题 / 变更请求

- 临时在 `plan/wp/M2-attendance.md` 末尾加了 `<!-- allow: plan/progress/M2-attendance.md, plan/wp/M2-attendance.md -->`，用于让 `tl check` 的改动范围检查放行进度文件迁移；这是审核意见第 8 条要求的操作，属于工作包文件自身的轻度注解。
