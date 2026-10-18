---
id: M2-forms
project: forms
title: 表单开发项目 · M2（表单平台阶段一）
status: 返工
agent: null
depends:
- M1 底座接口（阶段 3 起）
size: 整个项目，分 7 个阶段
stage: 0
started: 2026-10-18 15:03
---
## 目标

表单子方案"阶段一（M2）"做完：表单定义与发布、公式与显示条件（前后端）、记录与修订、最小流程、Excel / CSV / 粘贴导入、记录页，前端按高保真做齐。子方案 24 节阶段一开放的 FW 条目全部有测试。

## 必读（按顺序）

1. 仓库根 `AGENTS.md`，`apps/api/titanloom/forms/AGENTS.md`
2. **《后端详细设计 · 表单平台》全文**（本项目的施工图）
3. 《表单平台子方案》全文
4. 共同必读与 `plan/CODEMAP.md` 的 kernel、forms 两段
5. 契约：`packages/contracts/expressions/`（函数清单与用例，两端都要跑）、`state-machines.json`（formsTask）、`event-types.json`（forms.*）
6. 前端高保真：`D:\05_project\02_Titanloom\fidelity\Prototype\` 的 Forms、FormDesigner、FormFill、FormRecords（只看，不复制代码结构）

## 阶段（每阶段做完报告一次，架构审核通过后合入）

| 阶段 | 内容 | 验收 |
| --- | --- | --- |
| 1 | 字段与表单定义、草稿 / 发布 / 版本、发布前检查 | 字段改名不影响引用（FW18）；新版本不改运行中的（FW06）。**不依赖底座，可立即开工** |
| 2 | 表达式与显示条件：后端求值器 + 前端 `expr.ts`，都跑 `packages/contracts/expressions/cases.json` | 用例两端全过；循环依赖、超预算发布前拒绝（FW11）。**不依赖底座** |
| 3 | 记录、修订、提交 / 更正 / 作废 / 撤回、并发、字段来源 | FW01、FW02、FW03、FW14、FW15、FW20、FW22、FW23 |
| 4 | 最小流程：开始、审批、办理、排他分支、退回、结束；办理人解析；待办 | FW07、FW08；组待办先办先得 |
| 5 | Excel / CSV / 粘贴导入 | FW04、FW05、FW09 |
| 6 | 记录页：可见范围、敏感字段、导出 | FW21 |
| 7 | 前端：表单列表、设计器两步、填写三种方式、记录页 | 按高保真；文案只用键 |

## 允许修改的路径

`apps/api/titanloom/forms/`、`apps/web/src/domains/forms/`、`i18n/forms.yaml`（见 projects.yaml）。

## 依赖的底座（M1，由架构做）

阶段 3 起要用 `access.api`、`execution.api`、`facilities.api`。架构先发布接口和测试桩；**接口没出来之前只做阶段 1、2**，不要自己写替代品。

## 不做的事

- 不做阶段二、三：并行网关以外的高级节点、转办 / 加签 / 会签、HTML 组件（官方组件在阶段二）、L1 脚本、Quick Capture。
- 不改契约（包括 expressions 用例）、kernel、别的模块；要加用例或改契约提变更请求。

## 审核记录

### 阶段 1 · 2026-10-18 · 返工（提交 ae711d7）

做得好：只做 domain、不碰数据库与底座，符合当前约束；字段用稳定编号、改名只改显示名的思路对。

必须改（改完再报"阶段 1 做完了"）：
1. **FW06 实际不成立**：发布后在草稿里 `rename_field`，已发布版本的显示名也跟着变了（已复现）——`FormRelease.fields` 只是浅拷贝，和草稿共用同一个 `FieldDefinition` 对象。`FieldDefinition` 改为 frozen，改名 / 改设置返回新对象；发布时快照不可变（`Mapping` / tuple）。补测试："发布后改名、改设置、删字段，旧版本都不变"。
2. **公式放错了位置**：公式是"计算字段"的设置，不是分区属性。`Section` 只留标题、字段列表、显示条件；去掉 `Section.formula`，计算字段的表达式放进该字段的 settings。
3. **settings 要是正式字段**：现在在 `__post_init__` 里赋值，不参与复制和比较。改为 dataclass 字段（不可变映射）；`FieldKind` 改为 `StrEnum`，`kind: FieldKind`。
4. **检查结果结构化**：`PublishCheckFailed` 带问题列表（字段编号、在哪个字段 / 分区、问题种类），不拼中文句子；之后 api 层映射为 `INPUT_VALIDATION_FAILED` + details，界面用文案键。`remove_field` / `field()` 的中文 KeyError 同理。
5. **进度文件搬家**：先 `git merge local/integration`（拿到新的检查工具），再 `git mv PROGRESS.md plan/progress/M2-forms.md`，以后只更新它。

阶段 2 提前说明：
- `publish_check` 里用正则找 `$引用` 是临时做法；阶段 2 必须改为用表达式解析器给出的"引用字段列表"，删掉正则，否则同一件事两套写法（规范 5.5）。阶段 2 审核会查。
- 持久化（表单、版本、字段表）阶段 1、2 不做可以；迁移脚手架由架构随底座发布，阶段 3 开工前补 store。
