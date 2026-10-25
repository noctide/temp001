# 审核手册（所有做审核的对话框、Agent 先读这一份）

## 给审核 Agent 的开场（任何工具都行：Claude、opencode、Codex、DeepSeek Harness……）

维护者会说："你是审核者，读 `plan/REVIEW.md` 开头这一节，审 <编号>。" 你就照下面做。

**规矩**
- 你在正本 `D:\05_project\02_Titanloom-dev\hq` 里工作（只有审核者能在这里写），**不在任何 `projects\<项目>` 里改东西**——那是实现者的。
- **审核者不能是做这件活的那个 Agent**（同一个会话不能自己审自己）。
- 你只写：说明书末尾的审核记录（`plan/wp/<编号>.md`）、审计证据（`review/<项目>/`）、需要时的契约用例（`packages/contracts/`）；**不改产品代码**，发现问题写成返工意见让实现者改。
- 开始前 `git status` 必须是干净的；不干净就停下告诉维护者，不要动别人的改动。

**步骤（PowerShell）**
```powershell
cd D:\05_project\02_Titanloom-dev\hq
git status --short                                     # 必须没有输出
git log --oneline local/integration..<项目>/<编号>       # 这次要审哪些提交
git worktree add --detach ..\review-tmp <项目>/<编号>     # 临时检出一份来跑，不碰实现者的文件夹
cd ..\review-tmp
uv sync; pnpm install
uv run python ops/tools/tl.py check                    # 全套检查，要全过
uv run python ops/tools/tl.py run <模块> --smoke         # 单独运行（A1 合入后才有；arch 项目没有这一步）
# 读代码，对照：说明书该阶段的"验收"、后端详细设计、上次审核记录里"带到下阶段"的项；问题要实际跑出来
cd ..\hq
git worktree remove --force ..\review-tmp
```
然后按第 2 节第 6–9 条：写证据（`review/<项目>/<编号>-阶段<N>-<日期>.md`，并在该项目 `README.md` 时间线加一行）→ 通过就 `uv run python ops/tools/tl.py wp merge <编号> --keep`（整个工作包最后一个阶段不加 `--keep`）并在说明书写审核记录；不通过就写返工意见、`status: 返工`。**提交时只 add 你写的文件。**
最后给维护者一段可以转给实现者的话（第一步永远是 `git merge local/integration`）。

**拿不准的**：设计里写了的照设计；纯技术的你定并写进审核记录；业务问题停下问维护者。

---

> 正本在仓库：`plan/REVIEW.md`，归架构维护。审出新的坑就补进第 5 节。聊天对话框通过桥接读它（VM 路径 `$HOME/mnt/02_Titanloom-dev/hq/plan/REVIEW.md`）；code 模式直接读。

## 0. 谁审什么

| 对话框 | 审什么 | 入口 |
| --- | --- | --- |
| 表单审核 | 表单 Agent（`forms/M2-forms`）每个阶段 | 本手册 + 第 4 节"表单"卡 + 项目文档《交接说明-10-20-表单审核》 |
| 底座审核 | code 模式在 `local/integration` 上的提交（kernel、access、execution、facilities、plugin_host、shell、admin、ops/tools） | 本手册第 3 节 |
| 主对话框（架构） | 考勤 Agent、数据处理（设计页 + 以后的 Agent）、跨项目的事 | 本手册 + 第 4 节对应卡 |
| 以后新开的项目 | 照"项目卡"格式在第 4 节加一张卡，再开对话框 | — |

一个提交只归一个对话框审。项目的文件夹在 `D:\05_project\02_Titanloom-dev\projects\<项目>`（Agent 的工作区），审计证据在仓库 `review/<项目>/`。审完结论写进对应的说明书（`plan/wp/<编号>.md`）或本手册第 6 节（底座），别的对话框读那里就知道结论。

## 1. 先判断收到的是什么

- **只动了 `plan/progress/<编号>.md`**（Agent 在停等或记进度）：不审，回"收到"。
- **"<编号> 阶段 N 做完了"**：走第 2 节。
- **code 模式说"底座第 N 步完成"或提交了 arch 路径**：走第 3 节。
- **Agent 或 code 模式提问 / 要确认设计**：设计里写了的照设计答；纯技术问题自己定，写进审核记录；业务问题问用户（一次最多 3 个）。

## 2. 执行 Agent 的阶段审核（通用流程）

1. **在副本里跑，不碰正本工作区**：
   ```bash
   export UV_CACHE_DIR=$HOME/.uvcache UV_PROJECT_ENVIRONMENT=$HOME/hq-venv; U=$HOME/tlvenv/bin/uv
   cd $HOME/mnt/02_Titanloom-dev/hq && rm -rf $HOME/rv && git clone -q . $HOME/rv && cd $HOME/rv
   git branch -q local/integration origin/local/integration; git checkout -q -b <项目>/<编号> origin/<项目>/<编号>
   npx -y pnpm@9.15.0 install --frozen-lockfile   # 有前端改动必须装，否则 tsc / vitest 被跳过
   $U run python ops/tools/tl.py check            # 12 项全过
   (cd apps/web && node_modules/.bin/vitest run)   # 前端测试实际跑
   git diff --stat local/integration...HEAD        # 只改了允许路径？说明书 plan/wp 没被改？
   ```
   VM 里**不要进 `projects\*`，也不要执行 `git worktree prune`**（VM 看 Windows 建的 worktree 都显示 prunable）。tlvenv 不在了：新建 venv，再 `pip install uv jsonschema pyyaml`。
2. **对照三样东西逐条看**：说明书该阶段的"验收"、后端详细设计、上次审核记录里"带到下阶段"的项。
3. **问题要实际运行复现出来**，写成"输入 → 实际 → 应该"。不能只凭读代码判断。
4. **不信"全过"**：Agent 写的测试结果要自己重跑。凡是"两份实现必须一致"的（如公式前后端），要做对拍：随机生成大量输入，两边比对。
5. **单独运行**（工作包 A1 合入后生效）：在副本里跑 `tl.py run <模块> --smoke`（Agent 报告里也要贴）；合入时 `wp merge` 会在合并后的正本上再跑一遍，不过自动撤销合并。
6. **留证据**：在 `review/<项目>/` 新建 `<编号>-阶段<N>-<日期>.md`（格式见 `review/README.md`），贴 tl check、测试、单独运行（`tl.py run <模块> --smoke`，做出来以后）的输出，并在该项目的 `review/<项目>/README.md` 时间线加一行。通过和返工都要留。
7. **通过**：
   - 合入：`tl.py wp merge <编号> --keep`（A1 合入后会先跑单独运行门禁）。hq 里有别人没提交的改动时它会拒绝执行：先让对方提交，或手动 `git merge --no-ff --no-commit <分支>` → `tl.py run <模块> --smoke` → 通过再提交。
   - 说明书 `stage: N`、`status: 执行中`，末尾加审核记录（通过 + 带到下阶段的小项）。**只 add 自己改的文件**，`plan/HANDOFF.md` 归 code 模式，不动。
   - 给用户一段转给 Agent 的话，第一步永远是 `git merge local/integration`。
8. **不通过**：说明书末尾写返工意见（逐条：问题、怎么复现的、怎么改），`status: 返工`，提交；给用户的转发话术：merge → 读审核记录 → 改 → 贴 `tl check`（和 vitest）输出 → 回复"做完了"。
9. **需要改契约**（加用例、补规则）：直接改 `packages/contracts/`，跑 `tl.py check --only contracts`，和审核记录一起提交。

## 3. 底座审核（code 模式的提交）

证据写进 `review/arch/M1-底座审核记录.md`（底座四步合在一起记），结论汇总更新第 6 节的表。

审法同第 2 节第 1、3、4 步，但直接在 `local/integration` 上看那次提交（`git show --stat <提交>`）。逐项看：

1. **对照设计的"验收要点"**，每条都要有测试：
   - 身份与权限：设计 12 节末尾（拒绝优先、无允许即拒、管家 ⊆ 本人、filter 与逐条 check 一致、看不到的对象不出现……）
   - 命令与任务：设计 12 节末尾（同键同摘要返回原命令、并发只一个调用、版本变了提交被拒、管家不能确认、旧 fencing 被拒、重投不重复……）
   - 公共设施：设计 9 节后（同字节一份 blob、审计与业务同成同败、组待办先办先得、夜间延发……）
2. **对照已确认的接口决定**（第 6 节），一条条核。
3. **测试桩和真实实现是同一个接口**：都实现同一个 Protocol；同一批"接口行为测试"对桩和真实实现各跑一遍。只给桩写的测试不算。
4. **接口签名一次定好**：同一功能不出两套参数；本轮不做的接口连签名也不写。
5. **不重复**：没有在模块里重写 kernel 已有的东西（编号、时间、分页、幂等、错误体、Decimal）；`tl check` 的"重复代码"项要过。
6. **错误与安全**：错误一律 `AppError(ErrorCode…)`；details 不泄露调用者看不到的对象；日志里没有密钥或业务明文。
7. **对等待中的 Agent 的影响**：这一步发布后，哪些 Agent 可以继续？在对应说明书写"底座接口已发布（提交号）"，告诉负责那个项目的对话框（或直接给用户转发话术）。

## 4. 项目卡

### 表单（M2-forms）
- 设计：`docs/Titanloom-后端详细设计-表单-V1.0.md`；验收用例：表单子方案 24 节 FW；契约：`packages/contracts/expressions/`（c01–c31、`arithmetic` 规则）。
- 必查：公式改动要做前后端对拍（后端 `titanloom.forms.domain.expr.evaluate` 写 JSON，前端 tsc 编 `expr.ts` 后比对；上次 6000 组 0 不一致）；记录表共用一张，jsonb 加生成列；服务端重算、不信客户端（FW15）；隐藏分区不存值；写入走 execution、权限走 access、审计和待办走 facilities。
- 详细交接：项目文档《Titanloom-交接说明-10-20-表单审核》。

### 考勤（M2-attendance）
- 设计：`docs/Titanloom-后端详细设计-考勤-V1.0.md`；验收：考勤子方案 21 节；ADR-031。
- 必查：时长计算是纯函数（不读库、不读时钟），有基于性质的随机测试；时长用整数秒、区间半开；额度账每人每月一行加锁，两条并发填报不能合计超额；提交即占额度，退回 / 撤回释放；跨月按业务日；配置的适用范围 = 类别 + scope_kind + scope_ref + 优先级；表名不带 `attendance_` 前缀。
- 带到阶段 2 的项：`type` 变量遮住了内置名，改成 `type_def`；kind / scope_kind / status 改用 StrEnum，CHECK 从枚举生成。

### 架构工程 A1：单独运行（A1-standalone-run）
- 说明书：`plan/wp/A1-standalone-run.md`（8 项，含验收）。项目是 arch，没有"单独运行"那一步。
- 必查：补丁应用后 `tl check` 两项（类型、模块边界）修好；在 Windows 上实际 `tl.py run forms`：导航只剩首页和表单、顶上有黄色横幅、`?role=zym` 换人、Ctrl+C 前后端都停；故意让某模块 `dev/smoke.py` 抛错时 `wp merge` 拒绝合入且 hq 回到原样（`git status` 干净）；`tl.py here` 在 projects 里和 hq 里的提示都对；`wp start` 写出 `START.md` 且不进仓库；`wp start` 的 Permission denied 有结论。
- A1 是单阶段：通过后用 `tl.py wp merge A1-standalone-run`（不加 `--keep`），它会删掉 `projects\arch` 和分支；若在 VM 里删不掉，按提示在 Windows 上删。

### 底座真实实现（M1-access-real、M1-execution-real、M1-facilities-real）
- 必查：**同一批行为测试对桩和真实各跑一遍**（`impl` 参数化），审核时一定设 `TITANLOOM_TEST_DB_URL` 连本机 PostgreSQL 跑 real 一侧；接口签名没变（对照第 6 节）；10-20 / 10-24 桩审出的坑（`review/arch/M1-底座审核记录.md`）在真实实现里同一口径；迁移是生成的、从空库能 upgrade；并发类验收（并发提交只一个调用、组待办先办先得、额度类加锁）要用两个真数据库连接实测。
- 证据写进 `review/<底座>/`（access、execution、facilities 各自的文件夹）。

### 数据处理（M3-dataproc，待派）
- 设计：`docs/Titanloom-后端详细设计-数据处理-V1.0.md`；验收：M3 出口 + 数据处理子方案 18.1（场景 14、16 待 G-ISO）；ADR-034；说明书 `plan/wp/M3-dataproc.md`。
- 必查：数据集行表 `_v_from / _v_to` 只写差异，无变化不出版本；发布（差异、指针、代次、分区代次、血缘、outbox、审计）同一事务；回退是新版本、代次只增；JobRun 成功而质量阻断不发布（pipeline-run 契约）；基表生效方式必选无默认、用法绑定决定每天取哪版；关账月份回补先自动快照；SQL 与 Polars 实现同一份用例对拍；查询只收声明过的 FieldRef 筛选、行权限走 access.filter → to_sqlalchemy、aggregate 超限报错不截断；表名不拼用户输入。
- 派工前提：底座三块已发布；文件解析器没交付前允许 CSV 桩；考勤 / 表单的 export_changes 用桩。

## 5. 踩过的坑（审核时留意）
- Agent 写"两端全过"，其实前端没跑：前端测试一定自己跑。
- 一份数据写两遍：手写 SQL 迁移和 models 并存；两个查引用的函数并存。
- 浅拷贝导致"已发布版本"被草稿改动带着变。
- 读错设计里的数（预算"引用基表 20 次"看成"引用字段 20 次"）。
- Agent 在 hq 里执行命令；Agent 自己往说明书加 `allow` 放行（检查工具已改为只认集成分支上的说明书）。
- 桥接断线重连后删除权限会失效，git 留下 `.git/HEAD.lock`、`.git/objects/maintenance.lock`、`tmp_obj_*`：重新申请删除权限（`D:\05_project\02_Titanloom-dev`）后删掉。

## 6. 底座：已确认的接口决定（审核 code 模式时逐条核）

**access.api**
- 调用方式：模块级函数，背后实现可替换。`create_app()` 装真实实现，测试用 fixture 装桩，用完恢复原状；当前主体从 `kernel.context` 取。
- SQL 翻译：`access.api.sql.to_sqlalchemy`，调用方传"字段名→列"的映射，在调用方自己的 store 层执行。只生成 SQLAlchemy 表达式；"含下级部门"在 filter 阶段就展开成列表；缺少已登记的权限字段时直接报错。
- 本轮不做 explain、who_can、find_people、write_grant，签名也不写。
- `require()` 的错误码：功能开关没开 → `FEATURE_NOT_OPEN`；身份关不过 → 细分为 `AUTHENTICATION_REQUIRED` / `TOKEN_EXPIRED` / `ACCOUNT_LOCKED` / `DELEGATION_REVOKED`；其余 → `ACCESS_DENIED`；details 不泄露看不到的对象。

**execution.api**
- `confirm`：只能由命令的本人主体、在平台确认界面确认；管家、服务身份调用时抛 `ACCESS_DENIED`；一次性有效，绑定 commandId 和摘要；需要确认却没确认就 submit → `CONFIRMATION_REQUIRED`。
- `run()` = 同一事务里的 prepare + submit，参数与 prepare 完全相同；需要确认的能力调 run 抛 `CONFIRMATION_REQUIRED`；仍然要记命令和防重复记录。
- 预览由领域模块自己算好传入，是结构化数据，并计入摘要。
- 编号：命令用 `cmd_` 加 uuid7 的全部 32 位 hex，不截断；任务对外显示 `JR-` 加短编号（序号来自数据库序列），内部用 uuid7。
- `subscribe`：测试桩按顺序同步投递事件，提供 `redeliver(event_id)` 模拟重复投递；真实环境至少投递一次，handler 必须幂等；事件里带 event_id 和序号。

**审核结论记录**（每审一步加一行）
| 步骤 | 提交 | 结论 |
| --- | --- | --- |
| 1 数据库与迁移脚手架 | b806593 → 54c9c89 | **通过**（10-24 复审） |
| 2 access.api | 0fb2942 + 10fb0a3 → 54c9c89 | **通过**（10-24 复审） |
| 3 execution.api | 05b164d → 54c9c89 | **通过**（10-24 复审） |
| 4 facilities.api | eaaa8fc → 103255d → a9878b6 | **通过**（10-25 复审） |

**详细审核记录**：`review/arch/M1-底座审核记录.md`（10-20 初审、10-24 复审，以后每次复审接着往下写）。
