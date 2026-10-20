---
id: M2-attendance
project: attendance
title: 考勤开发项目 · M2（领域基础与完整人工闭环）
status: 执行中
agent: null
depends:
- M1 底座接口（阶段 2 起）
size: 整个项目，分 7 个阶段
stage: 1
started: 2026-10-18 15:03
---
## 目标

考勤子方案"阶段一：领域基础与完整人工闭环"做完：配置版本、时长计算、签到、填报 → 处理 → 正式结果、额度、排班发布与调班、异常与疑似漏报、提报批次，前端按高保真做齐。子方案 21 节验收全部有测试。

## 必读（按顺序）

1. 仓库根 `AGENTS.md`，`apps/api/titanloom/attendance/AGENTS.md`
2. **《后端详细设计 · 考勤》全文**（本项目的施工图）
3. 《考勤签到平台子方案》全文
4. 共同必读（AGENTS.md 里列的）与 `plan/CODEMAP.md` 的 kernel、attendance 两段
5. 契约：`packages/contracts/state-machines.json`（attendance*）、`event-types.json`（attendance.*）、`error-codes.json`
6. 前端高保真：`D:\05_project\02_Titanloom\fidelity\Prototype\Attendance.html`（只看，不复制它的代码结构）

## 阶段（每阶段做完报告一次，架构审核通过后合入，再做下一阶段）

| 阶段 | 内容 | 验收 |
| --- | --- | --- |
| 1 | 配置版本（类型、班次、规则集、出勤方案、签到策略）的表与草稿 / 发布；**区间与分类引擎**（纯函数） | 子方案 10.1 三例、重叠休息、越界休息、跨夜；基于性质的测试；同范围同优先级重叠拒绝发布。**不依赖底座，可立即开工** |
| 2 | 签到事件（只追加、来源去重）、签到页接口、今日出勤统计 | 子方案 20.1 口径；缺卡不当旷工；门禁读不到不算未签到 |
| 3 | 填报 → 处理（标记已提报 / 只记录 / 退回）→ 正式结果 → 额度账 | 并发两条不能合计超额；重复提交不重复占；驳回 / 撤回释放；审核期间修订变了确认失效 |
| 4 | 排班草稿 / 检查（重道任务）/ 发布 / 调班 | 跨月检查不清零、缺边界标不完整；6休1 与 7 天上限独立；调班不覆盖旧版本 |
| 5 | 异常与疑似漏报定时任务、提醒 | 去重指纹；忽略要写原因；通知失败不丢异常 |
| 6 | 提报批次、导出（重道）、撤销、需重报与更正批次 | 工号前导零；多段休息按配置表达或明确失败；不以"已下载"推断已接收 |
| 7 | 前端：签到、考勤表两层、提报、出勤明细、异常、类型与规则 | 按高保真；390 宽无横滚；文案只用键 |

## 允许修改的路径

`apps/api/titanloom/attendance/`、`apps/web/src/domains/attendance/`、`i18n/attendance.yaml`（见 projects.yaml）。

## 依赖的底座（M1，由架构做）

阶段 2 起要用 `access.api`（check / filter / whoami / members）、`execution.api`（prepare / submit / enqueue_in_tx / emit_in_tx / schedule）、`facilities.api`（审计、文件、通知、待办、文案）。架构先发布这些接口和测试桩；**接口没出来之前只做阶段 1**，不要自己写替代品。

## 不做的事

- 不写人员主数据、授权、命令、任务、审计、文件、通知的实现（底座的事）。
- 不做阶段二、三的内容：管家规则草案、自动排班求解器、大屏点名、外部反馈适配器、期间封账完整版。
- 不改契约、kernel、别的模块；要改提变更请求（写进 PROGRESS.md）。

## 审核记录

### 阶段 1 · 2026-10-18 · 返工（提交 3572efd）

做得好：区间引擎正确，子方案 10.1 三例、重叠 / 越界休息、跨夜都有测试；分类"同一秒只进一类"有测试；没碰底座、没造替代品。

必须改（改完再报"阶段 1 做完了"）：
1. **适用范围缺"对象"**：`ConfigVersionRef` 只有范围种类（org / dept / person），没有是哪个部门、哪个人。两个不同部门、同优先级、有效期重叠的配置会互相拒绝发布（已复现）。定义表改为 `scope_kind` + `scope_ref`（部门或人员编号；全公司为空），重叠判定按（配置类别, scope_kind, scope_ref, priority）。补一条"不同部门不冲突"的测试。
2. **有效期用业务日**：`effective_from / effective_to` 改为 `date`（半开，业务日），不用 timestamptz（设计 2："时间存 UTC，业务日另存"，配置按业务日启用）。
3. **发布冲突是业务规则，放 domain**：`store/config.py` 的校验移到 `domain/`（如 `domain/config_publish.py`）；store 只放表与读写（总图 5 四层）。
4. **删掉手写 `migrations/versions/0001_initial.sql`**：它和 `store/models.py` 是同一份表结构写两遍（规范 5.5）。迁移脚手架（Alembic，每模块独立 version 表 `attendance_alembic`）由架构随底座发布，之后从 models 生成。阶段 1 只保留 models.py。
5. **错误不拼中文句子**：`PublishConflictError` 改为带结构化字段（冲突版本编号、scope_kind、scope_ref、priority、两个区间），不写 message 文案；之后 api 层映射为 `INPUT_VALIDATION_FAILED` + details，界面用文案键。`interval` 里的 ValueError 是程序断言，可保留但不要中文。
6. **表名去掉重复前缀**：schema 已是 `attendance`，表名用 `type`、`type_version`、`shift`、`shift_version`、`rule_set`……
7. **分类引擎补基于性质的测试**：随机区间下，正常 + 各类加班 = 有效时长、各类不为负、互斥（设计 10）。
8. **进度文件搬家**：先 `git merge local/integration`（拿到新的检查工具），再 `git mv PROGRESS.md plan/progress/M2-attendance.md`，以后只更新它。

### 阶段 1 · 2026-10-18 · 通过（提交 30e6554，已合入）

8 条都落实了：适用范围加了对象（不同部门同优先级不再互相冲突，已验证）、有效期改为业务日、校验移到 domain、删掉手写 SQL、错误结构化、表名去前缀、分类加了 500 组随机性质测试、进度文件搬家。tl check 12 项全过，31 个测试通过。

两个流程问题（这次架构处理了，下次不许再犯）：
- **没有先 `git merge local/integration`**（第 1 步），所以没看到审核记录和新的检查工具。
- **自己在说明书里加了 `<!-- allow: ... -->` 给自己放行**。说明书归架构，执行 Agent 不许改；这行合入时已删掉，范围检查也改成只认集成分支上的说明书。需要额外路径 → 写进进度文件的"变更请求"。
- 另外，上一次搬家时在 hq 里建过文件，已清理。所有命令只在 `wt\M2-attendance` 里执行。

带到阶段 2 一起改：
1. `store/models.py` 里模块级变量 `type = …` 遮住了 Python 内置 `type`；变量名改为 `type_def`、`type_def_version`（表名仍是 `type`）。
2. `kind`、`scope_kind`、`status` 用 StrEnum（`ConfigKind`、`ScopeKind`、`VersionStatus`），不用裸字符串；表上的 CHECK 从枚举值生成，不再手写一遍。

### 底座接口已发布 · 2026-10-20 · 提交 eaaa8fc

`access.api`（b806593 前后、0fb2942）、`execution.api`（05b164d）、`facilities.api`（eaaa8fc）的接口与内存测试桩都已在 `local/integration` 上。先 `git merge local/integration`，测试用各模块 `api.testing` 的 fixture（`access_stub`、`execution_stub`、`facilities_stub`、`tx_session`），细节见 `plan/HANDOFF.md` §3 第 2–4 步。考勤阶段 2 用到的：`whoami / check / access_filter / members`，`register_binding / prepare / submit / enqueue_in_tx / emit_in_tx / schedule`，`audit_in_tx / todo_*_in_tx / notify_in_tx / text / add_ref`。真实实现还没有，桩之外不要自己造替代品。
