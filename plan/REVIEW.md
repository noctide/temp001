# 审核手册（所有做审核的对话框先读这一份）

> 正本在仓库：`plan/REVIEW.md`，归架构维护。审出新的坑就补进第 5 节。聊天对话框通过桥接读它（VM 路径 `$HOME/mnt/02_Titanloom-dev/hq/plan/REVIEW.md`）；code 模式直接读。

## 0. 谁审什么

| 对话框 | 审什么 | 入口 |
| --- | --- | --- |
| 表单审核 | 表单 Agent（`forms/M2-forms`）每个阶段 | 本手册 + 第 4 节"表单"卡 + 项目文档《交接说明-10-20-表单审核》 |
| 底座审核 | code 模式在 `local/integration` 上的提交（kernel、access、execution、facilities、plugin_host、shell、admin、ops/tools） | 本手册第 3 节 |
| 主对话框（架构） | 考勤 Agent、数据处理（设计页 + 以后的 Agent）、跨项目的事 | 本手册 + 第 4 节对应卡 |
| 以后新开的项目 | 照"项目卡"格式在第 4 节加一张卡，再开对话框 | — |

一个提交只归一个对话框审。审完结论写进对应的说明书（`plan/wp/<编号>.md`）或本手册第 6 节（底座），别的对话框读那里就知道结论。

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
   VM 里**不要进 `wt\*`，也不要执行 `git worktree prune`**（VM 看 Windows 建的 worktree 都显示 prunable）。tlvenv 不在了：新建 venv，再 `pip install uv jsonschema pyyaml`。
2. **对照三样东西逐条看**：说明书该阶段的"验收"、后端详细设计、上次审核记录里"带到下阶段"的项。
3. **问题要实际运行复现出来**，写成"输入 → 实际 → 应该"。不能只凭读代码判断。
4. **不信"全过"**：Agent 写的测试结果要自己重跑。凡是"两份实现必须一致"的（如公式前后端），要做对拍：随机生成大量输入，两边比对。
5. **通过**：
   - 合入：`git merge --no-ff -m "<项目>: … · 阶段 N（架构审核通过）" <分支>`。hq 干净时可用 `tl.py wp merge <编号> --keep`；hq 里有 code 模式的半成品时它会拒绝执行，就手动合。
   - 说明书 `stage: N`、`status: 执行中`，末尾加审核记录（通过 + 带到下阶段的小项）。**只 add 自己改的文件**，`plan/HANDOFF.md` 归 code 模式，不动。
   - 给用户一段转给 Agent 的话，第一步永远是 `git merge local/integration`。
6. **不通过**：说明书末尾写返工意见（逐条：问题、怎么复现的、怎么改），`status: 返工`，提交；给用户的转发话术：merge → 读审核记录 → 改 → 贴 `tl check`（和 vitest）输出 → 回复"做完了"。
7. **需要改契约**（加用例、补规则）：直接改 `packages/contracts/`，跑 `tl.py check --only contracts`，和审核记录一起提交。

## 3. 底座审核（code 模式的提交）

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
| 1 数据库与迁移脚手架 | b806593 | 待复审 54c9c89 |
| 2 access.api | 0fb2942 + 10fb0a3 | 待复审 54c9c89 |
| 3 execution.api | 05b164d | 待复审 54c9c89 |
| 4 facilities.api | eaaa8fc | **返工**（10-20 底座审核）：R4-1～R4-6 必改（其中 R4-2、R4-3、R4-4 改接口签名，趁还没人用先改） |

**底座审核记录 · 2026-10-20**

环境：VM 克隆 `local/integration`@10fb0a3；`tl check` 12 项过（tsc 跳过，本步无前端）。另在 VM 里起了 PostgreSQL 16.2（pip 包 pgserver 自带的二进制），`TITANLOOM_TEST_DB_URL` 指向它跑全部后端测试：227 passed、0 skipped——第 1 步"没在真实 PG 上验证"这一项已补上。

*第 1 步（通过）*
- 实测：照 `create.ps1` 的 SQL 建 owner / app 两个账号与 attendance schema → `tl db revision attendance -m init` 生成 10 张表 → `tl db upgrade` 成功 → 再 revision 一次是空迁移（模型与库一致）→ app 账号能读写、不能建表。临时 schema fixture 在真库上两条测试都过。
- **R1-1（必改，下一个模块加表之前）**：运行账号的权限只在 `create.ps1` 里按"当时已有表的模块"授予。之后新模块（表单、access、execution、facilities 都快加表了）由 `tl db upgrade` 的 `CREATE SCHEMA IF NOT EXISTS` 自动建 schema，运行账号对它**没有 USAGE、也没有默认权限**。复现：删掉 attendance schema → `tl db upgrade` 重建 → 用 titanloom_app 查 `attendance.type` → `permission denied for schema attendance`。应该：`run_env` 建 schema 时一并 `GRANT USAGE` 并设 `ALTER DEFAULT PRIVILEGES … TO <运行账号>`（运行账号名从连接串 `TITANLOOM_DB_URL` 取，或固定 `titanloom_app`）；或者 schema 不存在时直接报错"先重跑 create.ps1"。二选一，补一条带库测试。
- 小项（不挡）：模块 metadata 的 schema 不等于模块名时，`only_mine` 会把所有表滤掉、静默生成空迁移，`module_metadata` 里加一句断言；运行账号也能改 `<模块>_alembic` 版本表，以后可以收回（REVOKE 该表的写权限）。

*第 2 步（返工）*
- 第 6 节 access.api 的四条决定逐条核过：模块级函数 + provider 可替换、`to_sqlalchemy` 只生成表达式且缺字段报错、本轮不写的四个接口没写签名、`require()` 错误码映射与 details 只含 failedStep / reasonKey——都符合。拒绝优先、无允许即拒、filter 与逐条 check（纯函数层面）一致都有测试。
- **R2-1（必改）筛选条件翻成 SQL 后，字段为空的行与 check 结论相反。** 复现（真 PG）：给 A0004 "全部" + 拒绝 `projectId = pr1`；一行 `projectId = NULL` 的记录 → `check` 允许、`AccessFilter.matches` 允许、`to_sqlalchemy` 查不出来（`NOT (proj = 'pr1')` 遇到 NULL 得 NULL）。应该：`not` 里的每个谓词翻成 `col IS NULL OR NOT (…)`（或 `coalesce`），`test_types_sql` 的样本行加 NULL 值（`ids()` 已经同时比对 SQL 与 matches，加上就能抓住）。
- **R2-2（必改，数据外泄）filter 给的遮挡列比逐条 check 少。** 复现：A0004 有"全部（遮 idNumber）"+"本部门（不遮）"两条允许 → `filter` 的 `mask_columns = ()`；对质检部的记录 `check` 返回 `maskColumns: [idNumber]`。也就是列表页会把别的部门的身份证号露出来。原因：`_mask` 取"所有允许条件共同要遮的列"，但这只对逐行判定成立。应该：本轮先保守——filter 的遮挡列取**会被用到的允许条件的并集**（宁可本部门也遮），并在属性测试里加一条"filter 的遮挡列 ⊇ 每一行 check 的遮挡列"；"按行解除遮挡"（契约里给遮挡列附上 unless 谓词）留到真实实现之前再定。
- **R2-3（接口口径，架构定）**：`check(subject=别人)` 的 docstring 写"查别人需要诊断资格"，但 facilities 发通知时要用它筛收件人。定为：`subject=` 是进程内模块调用，可信、不做诊断资格校验；"诊断资格"只在 HTTP `/explain` 与以后的 `explain()` 上校验。改 docstring 即可。
- 带到真实实现：① 行为测试现在写在桩的造数据方法上（`registered.grant`、直接清 `_grants`），真实实现出来时要拆出"同一批接口行为测试对桩和真实各跑一遍"（第 3 节第 3 条）；② 桩没有办法造"管家代办"（execution 的测试是临时替换 `whoami` 做的），给 `as_principal` 加 `acting_for=` 参数，表单 / 考勤的管家场景都会用到。

*第 3 步（返工）*
- 第 6 节 execution.api 的五条决定逐条核过：confirm 只能本人、管家 / 服务身份 / 别人一律 ACCESS_DENIED、一次性且绑定 commandId 与摘要；run = 同事务 prepare + submit、要确认的抛 CONFIRMATION_REQUIRED；预览进摘要；`cmd_` + 32 位 hex、任务 `JR-` 序号；subscribe 按序投递 + `redeliver`——都符合，也都有测试。
- **R3-1（必改）给了 expected_version、但能力没登记 version_validator 时，提交不检查版本、直接通过。** 复现：LEAVE 不登记校验器，`prepare(…, target=leave/L1, expected_version="v1")` → `submit` 成功。验收要点"准备后版本变化提交被拒"因此会被"忘了登记"悄悄绕过。应该：`prepare` 时带了 expected_version 而该能力没有校验器 → 直接报 `NotRegistered`（与"未登记的能力直接报错"同一口径），补测试。
- **R3-2（必改，桩与真实行为不一致）事务还没提交，订阅者就收到了事件。** 复现：在 tx_session 里 `emit_in_tx` → `drain()` → 订阅者收到 → `rollback()` → 事件没了，但订阅者已经处理过。真实的发件箱只投递已提交的事件，Agent 在桩上测过的东西到真实环境会不一样。应该：桩里事件在所在会话提交后才可投递（`after_commit` 时标为可投递；不在事务里写的不存在，因为 emit 必须在事务里），`drain()` 不投递未提交的事件，补测试。
- **R3-3（顺手改，重复代码）**：`InMemoryExecution._touch` 和第 4 步挪到 kernel 的 `track_rollback` 是同一套逻辑（快照 + 回滚还原），改成调用 `track_rollback`；"连续 8 行相同"的检查没抓到它。
- 本步不涉及、留给真实实现验收：并发提交只产生一个调用、旧 fencing token 被拒、原进程存活不回收租约、重道无饥饿（桩单线程，测不了）。

*第 4 步（返工）*
- 已对照：设计 8 节接口（上传 / 派生 / 保留期 / 偏好 / 外发 / 搜索本轮不做，HANDOFF 已写明）、9 节后验收要点。做对了的：审计与业务同成同败、哈希链篡改可查、查看审计也留痕、组待办先办先得、看不到对象的人收不到通知、5 分钟合并、按收件人语言渲染、检查失败不能下载、下载凭引用并跟随挂靠对象鉴权、无匿名链接、桩已用 kernel 的 `track_rollback`。以下 6 条都在 VM 上跑出来了：
- **R4-1（必改，桩的语义和设计不同）同样字节上传两次，变成同一个文件。** 复现：`put_asset(b"same","张三-病假条.pdf")`、`put_asset(b"same","李四-病假条.pdf")` → 返回同一个 asset_id，只剩张三的文件名；撤回张三那份，李四那份也成了 withdrawn。设计是 asset / asset_version / blob 三层：**去重只在 blob（字节）层**，两次上传是两个文件、各自的名字和状态。应该：桩拆出 blob（sha256 → 引用计数），`put_asset` 每次新建文件；现有测试 `test_same_bytes_are_stored_once…` 里 `a == b` 的断言改成"两个 asset、一个 blob"。
- **R4-2（必改，改签名）重投一次，通知的合并计数就 +1。** 复现：同一事件重投（至少一次投递）→ 同 dedupe_key 发两次 → `count == 2`。设计要求"重试与重投不重复"，又要求"5 分钟内同类合并计数"，现在一个键管两件事。应该：`NotifyDraft` 拆成 `idempotency_key`（同一事件，再来一次什么也不做）和 `merge_key`（同类 5 分钟合并计数）。顺带给真实实现：设计 10 节写的唯一键 `(recipient_id, dedupe_key)` 与 5 分钟窗口不能同时成立，真实实现要把唯一约束放在幂等键上、合并另算。
- **R4-3（必改，改签名）审计查看不看数据范围。** 复现：仓储物流负责人只被授予"本部门"的 `facilities.audit.read`，`audit_for(装配一部的请假单)` 照样返回 1 条。原因：`audit_for(target)` 只有 ObjectRef，没有对象的归属，`check` 只能问"有没有这项能力"。设计要求部门负责人只看本部门相关。应该：`audit_for` 加 `access_target: Target`（与 `NotifyDraft.access_target` 同一口径），用它做 `check(...).require()`；不给就只允许"全部"范围的人。
- **R4-4（必改，改签名）同一个来源对象办完以后不能再开待办。** 复现：请假单 LV-0001 的审批待办办完 → 退回重提要再开一条 → `todo_open_in_tx` 抛 `RESOURCE_VERSION_CONFLICT`。设计 10 节是"按 sourceRef + 事件版本幂等"。应该：`TodoDraft` 加 `source_version`；(类型, 来源, 版本) 相同 = 幂等返回；版本更新且旧的已办完 / 撤回 = 新开一条；旧的还开着 = 冲突。
- **R4-5（必改）通知显示的语言包版本和文字是"现在的"，不是发送时的。** 复现：发通知时 `zh-CN@1`，之后改文案 → 再读同一条通知变成 `zh-CN@2`、文字也变了。设计是"渲染时记语言包版本"。应该：发送（或合并更新）时把渲染好的文字和版本存进通知，读取只返回存下的。
- **R4-6（必改，安全）审计的前后摘要可以直接塞明文。** 复现：`AuditDraft(before_digest="身份证 110101199001011234")` 照存不误。应该：`AuditDraft.__post_init__` 要求 `before_digest` / `after_digest` 为空或形如 `sha256:<64 位 hex>`（即 `digest()` 的输出），否则报错；补测试。
- 带到真实实现：`delegation_id` 等 Whoami 有了再接（HANDOFF 已写）；通知收件人筛选依赖 R2-3 的口径（`check(subject=)` 模块内调用不校验诊断资格）；`view_capability` 不给时不筛收件人——带 `subject` 的通知是否强制要求给，真实实现前定。
- 对等待中的 Agent：facilities 的签名要变（R4-2、R4-3、R4-4），考勤 / 表单如果已经开始用 `notify_in_tx`、`audit_for`、`todo_open_in_tx`，改完后要跟着改；在第 4 步复审通过之前，别让 Agent 照现在的签名写大量代码。

返工完成后：code 模式跑 `tl check`，并在本表把对应行改成"待复审 <提交号>"。
