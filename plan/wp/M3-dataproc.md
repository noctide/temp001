---
id: M3-dataproc
project: dataproc
title: 数据处理开发项目 · M3（数据处理最小链）
status: 待派
agent: null
depends:
- M1 底座接口（access、execution、facilities 已发布）
- 文件解析器（Excel / CSV，架构做；阶段 1 导入基表、阶段 2 接入时要用，没交付前先用 CSV 桩）
size: 整个项目，分 7 个阶段
stage: 0
started: null
---
## 目标

实施路线 M3"数据处理最小链"做完：基表、接入、模型、运行三维度、数据集版本与原子发布 / 回退 / 快照、受控只读查询、流水线级血缘与图谱，前端按高保真做齐。M3 出口与子方案 18.1 中 M3 范围的场景全部有测试。

## 必读（按顺序）

1. 仓库根 `AGENTS.md`，`apps/api/titanloom/dataproc/AGENTS.md`
2. **《后端详细设计 · 数据处理》全文**（本项目的施工图）
3. 《数据处理平台子方案》全文（重点 6.1、7–15、18、21）
4. 共同必读与 `plan/CODEMAP.md` 的 kernel、access、execution、facilities、dataproc 几段
5. 契约：`pipeline-run.schema.json`、`query-execute-request/response.schema.json`、`query-filterable.schema.json`、`field-ref.schema.json`、`dataset-generation-changed.schema.json`、`event-types.json`（data.*）、`error-codes.json`
6. 前端高保真：`D:\05_project\02_Titanloom\fidelity\Prototype\Pipeline.html`；草图 `WireFrame\sketch-pipeline.html`、`sketch-refds.html`（只看，不复制代码结构）

## 阶段（每阶段做完报告一次，架构审核通过后合入，再做下一阶段）

| 阶段 | 内容 | 验收 |
| --- | --- | --- |
| 1 | 存储骨架；基表：定义、草稿修订、导入方案、宽表 → 长表（纯函数）、发布前检查、用法绑定、三种生效方式（只影响以后 / 回补历史 / 另出修订版，必选无默认） | 场景 10、12；重复键 / 有效期重叠被数据库约束拦；月中换岗例外有效期；空格子语义必须选；导入不自动删除 |
| 2 | 接入：来源、批次（内容哈希）、原始行（COPY）、清洗算子（SQL + Polars 两种实现，同一份用例对拍）、标准表、列画像、接入环节隔离区、错误定位 | 场景 6、9；重复导入不放大；错误定位到文件 / 工作表 / 行 / 列；对拍 0 不一致 |
| 3 | 模型与运行：DAG 版本（钉实现与摘要）、关系（多键、按日期取有效、膨胀估算）、指标与剔除规则、PipelineRun 三维度 + JobRun（重道）、检查点续做、样例预览（同步 SQL）/ 试运行 / 完整运行、质量门禁、跟随运行合并 | pipeline-run 契约测试；JobRun 成功而质量阻断不发布；场景 7、11、17、18；节假日区间扣除（场景 13） |
| 4 | 数据集版本：差异存储（_v_from / _v_to）、原子发布、回退 = 新版本、修订版与采用、快照、代次与分区代次、关账月份回补先自动快照、事件；考勤 / 表单增量拉取（用合成数据桩） | 场景 1、20；基于性质的测试（随机发布 / 回退 / 回补后任意版本读取正确）；发布中途杀进程无半个版本；业务提交不等待分析 |
| 5 | 受控只读查询：语义层聚合、可筛选声明、行列权限（access.filter → to_sqlalchemy）、page / aggregate 两种形状与上限、游标签名、缓存（分区代次） | 场景 19；能力契约 A29、A30；超限返回 QUERY_BUDGET_EXCEEDED 不截断；"全部"= 权限内全部 |
| 6 | 血缘边、使用方登记、影响分析、图谱快照、"在用旧数据"；隔离区修补与回流 | 场景 3；指标下钻到批次、规则版本、基表版本；未知字段血缘显示"未知 / 部分" |
| 7 | 前端：图谱、接入、模型、基表、数据集、隔离区、运行 | 按高保真；运行三列分开；手机只看状态；文案只用键 |

## 允许修改的路径

`apps/api/titanloom/dataproc/`、`apps/web/src/domains/dataproc/`、`i18n/dataproc.yaml`（见 projects.yaml）。

## 依赖

- 底座：`access.api`、`execution.api`、`facilities.api` 已发布接口与测试桩，直接用，**不要自己写替代品**。数据库与迁移用 kernel 脚手架，表结构只写在 `store/models.py`，迁移用 `tl.py db revision dataproc` 生成。
- 文件解析器（Excel / CSV）由架构交付；没交付前阶段 1、2 用 CSV 读入的桩，接口照解析器的签名。
- 考勤、表单的 `export_changes` 还没有：阶段 4 用合成数据桩，签名见后端设计 11 节。

## 不做的事

- 个人工作区、个人 SQL / Python 节点、个人插件（G-ISO 前不开放）；本地恢复副本。
- 外部服务算子、原生算子、数据服务的限流 / 认证 / 废弃窗口、运行拓扑历史回放。
- 不改契约、kernel、别的模块；要改提变更请求（写进 `plan/progress/M3-dataproc.md`）。
- 测试不用真实数据，只用合成人设与合成基表（职业分类、系数、节假日）。

## 审核记录

（还没有）
