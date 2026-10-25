# 进度

由 `tl.py status` 生成（2026-10-25 11:51 UTC），不要手改。

## 工作包

待派 2 · 执行中 2 · 待审 0 · 返工 0 · 已合本地 0 · 已推送 0

| 编号 | 项目 | 标题 | 状态 | 谁在做 | 依赖 | 预计行数 |
| --- | --- | --- | --- | --- | --- | --- |
| A1-standalone-run | arch | 架构工程 · 每个模块单独运行（tl.py run）与合并前门禁 | 待派 |  |  | 一个阶段（有草稿补丁，约 1000 行改动，大半已写好） |
| M3-dataproc | dataproc | 数据处理开发项目 · M3（数据处理最小链） | 待派 |  | M1 底座接口（access、execution、facilities 已发布）, 文件解析器（Excel / CSV，架构做；阶段 1 导入基表、阶段 2 接入时要用，没交付前先用 CSV 桩） | 整个项目，分 7 个阶段 |
| M2-attendance | attendance | 考勤开发项目 · M2（领域基础与完整人工闭环） | 执行中 |  | M1 底座接口（阶段 2 起） | 整个项目，分 7 个阶段 |
| M2-forms | forms | 表单开发项目 · M2（表单平台阶段一） | 执行中 |  | M1 底座接口（阶段 3 起） | 整个项目，分 7 个阶段 |

## 模块规模

| 模块 | 代码行（不含测试） | 文件 | 测试数 |
| --- | --- | --- | --- |
| kernel | 791 | 18 | 25 |
| access | 781 | 9 | 36 |
| admin | 5 | 5 | 0 |
| agent | 5 | 5 | 0 |
| attendance | 290 | 9 | 31 |
| automation | 5 | 5 | 0 |
| dataproc | 5 | 5 | 0 |
| execution | 1369 | 8 | 48 |
| facilities | 1044 | 8 | 41 |
| forms | 1023 | 20 | 30 |
| integration | 5 | 5 | 0 |
| knowledge | 5 | 5 | 0 |
| plugin_host | 5 | 5 | 0 |
| shell | 5 | 5 | 0 |
| visualization | 5 | 5 | 0 |

## 最近一次 tl check

2026-10-25 11:26 UTC · 分支 local/integration · ✗ 0 · ! 0 · 共 1 项
