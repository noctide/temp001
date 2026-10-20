# Titanloom · 执行 Agent 规则（唯一正本）

opencode、Codex、DeepSeek Harness、Claude 等所有执行 Agent 都按这一份做；各模块目录下还有一份 `AGENTS.md`，写本模块的允许路径与必读。规则依据：`docs/Titanloom-开发项目划分与多Agent协作规范-V1.0.md`（5.4–5.6、6、7）与 `docs/Titanloom-工程质量与代码规范-V1.0.md`。

## 开工前

1. 读工作包 `plan/wp/<编号>.md`（目标、设计依据、接口、验收、允许路径、不做的事、分支名、依赖）。
2. 读本模块 `AGENTS.md` 列的必读；读 `plan/CODEMAP.md` 里本模块和你要调用的模块那一段——**要用的东西先查有没有，有就用，不要再写一个**。
3. 读 `plan/progress/<编号>.md`：上次做到哪、下一步是什么（每个项目一份，合入时互不冲突）。

## 只做这些

- 只改工作包"允许修改的路径"里的文件（通常是本模块目录 + 本模块的 `i18n/<命名空间>.yaml`）。`tl check` 会拦。
- 不改：`apps/api/titanloom/kernel/`、`packages/contracts/`、别的模块、`projects.yaml`、`ops/tools/`、`docs/`、本文件。需要改 → 停下，在 `plan/progress/<编号>.md` 写"变更请求：要什么、为什么、对应设计章节"，告诉维护者。
- 设计里没写、你拿不准的：**不要自己补**，停下来写清楚问题。

## 写代码的规矩

- **分四层**（后端详细设计·总图 5）：`api` 对外口（路由、请求返回结构、能力编号）· `app` 办事流程 · `domain` 纯业务规则（不碰数据库、网络、时钟）· `store` 本模块的表与读写。别的模块只能引用对方的 `api` 层和 `kernel`。
- **只用生成的常量**：能力编号、错误码、事件、状态、业务参数键、功能、文案键都从生成的常量里取（后端 `titanloom.kernel.reg`、前端 `src/shared/base/reg`；`tl.py gen` 生成），不手写字符串；要新登记 → 改本模块 `manifest.yaml` 或 `i18n/<命名空间>.yaml`，写清用途，架构审核。
- **公共工具在 kernel**：错误体、编号（UUIDv7 + 短编号）、时间（只用带时区，存 UTC）、分页（排序键 + id 游标）、幂等、金额与工时（`Decimal`，不用 float）、结构化日志、业务参数读取、测试工具。没有你要的 → 变更请求，不要在模块里自己写一份。
- 可调的数值（上限、阈值、时长、开关）登记为业务参数，不写死。界面上不写中文字句，只用文案键。
- **前端页面照高保真做**（`D:\05_project\02_Titanloom\fidelity\Prototype\` 下同名页面；规则见 `ops/tools/fidelity/pages.yaml` 开头）：颜色、字号、圆角、间距只用设计变量 `var(--m-*)` 和公共组件，不直接写颜色值、不自己发明样式，公共组件要改提变更请求；开发模式认原型同样的 URL 参数（`role=member`、`empty=1` ……）切换示例身份和数据；清单里的关键位置加 `data-fid="<名字>"`。交前端页面前跑 `uv run python ops/tools/tl.py fidelity <页名>`，全过才交，回复里贴它的输出。
- 先写测试（验收用例、权限的拒绝用例、状态不变量），再实现。示例与测试里的人名、部门只用合成数据人设表（`ops/synthetic-data`）。

## 提交

- 只在本地分支提交，**不推送、不合并、不开合并请求**。
- `git commit -s`；提交信息第一行 `<模块>: <做了什么>`，正文写依据的设计章节，末尾另起一行 `Agent: <你的工具名>`。
- 每完成一步更新 `plan/progress/<编号>.md`（做到哪、下一步、遇到的问题）。
- 做完先跑 `uv run python ops/tools/tl.py check`，全部通过再交；最后一条提交写自查结果。然后回复一句"<编号> 做完了"，列出改了哪些文件、测试结果。

## 常用命令（Windows 用 PowerShell 也一样）

```
uv sync                                   # 装后端依赖（第一次）
uv run python ops/tools/tl.py check       # 全套检查
uv run pytest apps/api/titanloom/<模块>    # 只跑本模块测试
pnpm install && pnpm --dir apps/web dev   # 前端
pnpm --dir apps/web exec playwright install chromium   # 高保真比对用的浏览器（第一次）
uv run python ops/tools/tl.py fidelity <页名>          # 高保真比对，报告 .fidelity/report.html
```
