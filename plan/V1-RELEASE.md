# V1 发布计划（表单 · 考勤 · 数据处理，2026-10-29 定）

目标：第一个能部署、给大家用的版本，只含 **表单、考勤、数据处理** 三个功能；其余模块第二版再做。代码放 GitHub（私有仓库，见"发布"）。

## 范围

- 进 V1：forms、attendance、dataproc（各 7 阶段，含前端）；它们依赖的底座真实实现 access、execution、facilities；最小外壳（登录、导航、顶栏：shell 前端 + 后端会话）；装配（`main.py --bases=real`）、文件解析器（Excel/CSV）、PG 实测、部署脚本。
- 不进 V1：visualization、automation、knowledge、agent、integration、admin 后台、plugin-host 完整形态。这些目录在 V1 发布仓库里不带（发布时用 `ops/tools` 导出清单剔除空壳），第二版再补。
- 底座三份工作包（`M1-*-real`）已经是最小集，V1 全部阶段都要（execution 的后台程序、access 的登录与撤权、facilities 的文件与待办，三个模块都实际在用）。

## 关键路径与批次

| 批次 | 工作包 | 说明 |
| --- | --- | --- |
| 立即 | M2-forms 阶段 3、M2-attendance 阶段 2 | 接口与桩已发布，不用等真底座 |
| 立即 | M1-execution-real、M1-facilities-real、M1-access-real | 关键路径；三者互相独立（各自文件夹） |
| 立即 | A1-standalone-run | 小活，先合入，之后每阶段加 `--smoke` 门禁 |
| 底座 3 阶段后 | M3-dataproc 阶段 1 起 | 需要文件解析器（先 CSV 桩） |
| 新工作包（架构写说明书） | V1-assemble：`--bases=real` 装配、文件解析器、最小外壳登录、部署脚本、PG 全链冒烟 | 底座各自 install 完成后做 |
| 收尾 | V1 出口：三模块在真 PG 上跑通全链冒烟；GitHub 私有仓库推送 | 见"发布" |

并发：先放到 5 个（forms、attendance、三个底座），A1 插空，dataproc 等底座就绪。

## 分工

- 架构（Claude）：说明书、派工、审核、合入，不写产品代码。
- Codex（`codex exec`，我可直接后台派）：execution-real、facilities-real。
- opencode：forms、attendance（原来就是它做的）。
- DeepSeek harness：access-real，后面 dataproc。
- 审核：实现者与审核者必须是不同工具；初审由另一工具做，架构复核后 `tl.py wp merge`。
- opencode 不在 PATH，dsh 只有交互入口：这两个需要维护者在对应文件夹打开，说"读 START.md，照着做"。

## 发布（GitHub）

- 先本地全部合入、`tl check` 与 `--smoke` 全过，再推；推送前和维护者确认仓库名与可见性（默认私有），不在此之前推送。
- 推送前检查：不含密码、`.env`、个人数据；`.pnpm-store`、`.venv`、`node_modules`、`.tmp`、`_tmp_*` 不入库（已有 `.gitignore`，推前核对）；示例数据只用合成人设。
