---
id: M2-attendance
project: attendance
title: 考勤开发项目 · M2（领域基础与完整人工闭环）
status: 待派
agent: null
depends: [M1 底座接口（阶段 2 起）]
size: 整个项目，分 7 个阶段
stage: 0
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

（架构每阶段审核意见写在这里）

<!-- allow: plan/progress/M2-attendance.md, plan/wp/M2-attendance.md -->
