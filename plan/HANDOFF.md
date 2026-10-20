# 架构交接（code 模式先读这一份）

> 最后更新：2026-10-18 10:30（PT）。每次结束一段工作都更新本文件，再提交。项目文档里的"交接说明"是给聊天会话的副本，以本文件为准。

## 1. 我是谁、在干什么

你是 Titanloom 的架构（Claude）。维护者 Leo。分工：
- **架构做**：框架、脚手架、配置、公共代码（kernel、`apps/web/src/shared/`、ops/tools）、M1 底座（access / execution / facilities / plugin_host / shell / admin 后端）、文件解析器、每个开发项目的后端设计页、审核与合入。
- **执行 Agent 做**：一个开发项目一个 Agent，按 `plan/wp/<编号>.md` 分阶段做，每阶段报告后你审核。
- 同时最多 3 个 Agent；派工顺序见 `docs/Titanloom-实施路线与首期工程基线-V1.0.md` 5.4。
- 全部只在本地，**不推 GitHub**（M4 完成时提醒一次是否备份）。
- 给维护者的命令写 **PowerShell 7** 版。
- 设计流程：草图 → 维护者确认 → 定稿；每页最多问 3 处，纯技术默认值列页尾，开头写"这页说了什么"。后端先设计再开工。

## 2. 现在的状态

| 项 | 状态 |
| --- | --- |
| 正本 | `hq`，分支 `local/integration` |
| 门禁 | `uv run python ops/tools/tl.py check`（12 项全过） |
| M2-attendance | 阶段 1 已合入（1f2f1bc）。**停着等底座接口**（阶段 2 起要用）。worktree `wt\M2-attendance` |
| M2-forms | 阶段 1 已合入（edb95cf），正在做阶段 2（表达式，不需要底座）。worktree `wt\M2-forms` |
| 数据处理 | 待派：先出后端设计页 `sketch-backend-dataproc.html`（放 `D:\05_project\02_Titanloom\fidelity\WireFrame`），确认后写 `plan/wp/M3-dataproc.md` |

审核记录在各说明书末尾；Agent 进度在 `plan/progress/<编号>.md`（在它们自己的分支上）。

## 3. 下一步：底座接口（按这个顺序做）

目标：先把**接口 + 测试桩**发布出来，让考勤能做阶段 2、表单能做阶段 3；实现随后补。每一块做完都 `tl check`、提交、更新本文件。

1. **数据库与迁移脚手架（kernel）** —— ✅ 已做（2026-10-18）：`kernel/db.py`（同步会话，`transaction()` 嵌套加入外层）、`kernel/migrate.py` + `kernel/alembic_env/`（公共 env，模块只放 `migrations/versions/`）、`kernel/testing.py`（`schema_session_fixture(metadata)`，环境变量 `TITANLOOM_TEST_DB_URL`，没设就跳过）、`tl.py db upgrade|revision|modules`、`ops/db/create.ps1`。**还没在真实 PostgreSQL 上跑过**（本机未检测到 PG：迁移、建库脚本、带库的 fixture 待维护者在装了 PG 的环境验证）。原要求如下：
   - `kernel/db.py`：引擎、会话、`transaction()`（一个请求一个事务；模块的 store 只拿会话不建引擎）；连接串从环境变量读。
   - Alembic：每个模块独立迁移目录 `apps/api/titanloom/<模块>/migrations/` 和独立 version 表 `<模块>_alembic`（总图 12）；`tl.py db upgrade [模块]`、`tl.py db revision <模块> -m …`（从模块 `store/models.py` 的 metadata 自动生成）。
   - 测试工具：`kernel/testing.py` 提供临时 schema / 事务回滚的 pytest fixture；没有数据库时这类测试跳过。
   - Windows 建库脚本 `ops/db/create.ps1`（建库、每模块一个 schema 和账号；密码维护者本地输入，不进仓库）。
2. **`access.api`**（`docs/Titanloom-后端详细设计-身份与权限-V1.0.md` 10 节）—— ✅ 接口 + 测试桩已做（2026-10-20，维护者已确认签名）：模块级函数 `whoami / check / access_filter / members / memberships / register`，实现经 `_provider.set_provider()` 装入（只两处：`create_app()` 启动装真实实现；测试用 `access.api.testing.access_stub` fixture，结束后恢复）；主体取自 `kernel.context`；`Decision.require()` 抛 AppError（功能开放 → FEATURE_NOT_OPEN；身份关按原因 → AUTHENTICATION_REQUIRED / TOKEN_EXPIRED / ACCOUNT_LOCKED / DELEGATION_REVOKED；其余 ACCESS_DENIED；details 只有 failedStep 与 reasonKey）；`access.api.sql.to_sqlalchemy(filter, 字段→列)` 缺字段直接报错。**待办**：① `create_app()` 还没有，装入真实实现的那一处等应用入口做出来再接；② `explain / who_can / find_people / write_grant` 没做（考勤阶段 2 用不到），做的时候一次把 Protocol、桩、真实实现的签名定好；③ ~~契约缺口 all+not~~ 已解决（维护者选 A，2026-10-20）：契约允许 `all` 带 `not`，`AccessFilter`、`to_sqlalchemy`、桩 `filter` 已同步；④ 第二人批准（SECOND_APPROVAL_REQUIRED）等流程出来再接。原要求如下：
   - 先做：`whoami`、`check`、`filter`、`members`、`register`（考勤阶段 2 要用的就这五个）。
   - 接口用 Protocol + 数据类定义在 `access/api/`；同时给 `access/api/testing.py` 一个**测试桩**（内存里的人、部门、授权，按合成人设表），其他模块的测试只用它。
   - 契约：`packages/contracts` 里 access-decision、access-filter。
3. **`execution.api`**（命令与任务 12 节）—— ✅ 接口 + 测试桩已做（2026-10-20，维护者已确认签名）：模块级函数 `register_binding / job_handler / reconcile_handler / version_validator / prepare / confirm / submit / run / cancel / cancel_job / enqueue_in_tx / emit_in_tx / schedule / pause_schedule / resume_schedule / end_schedule / get_job / subscribe`，实现经 `_provider.set_provider()` 装入；桩 `execution.api.testing`：`execution_stub`（依赖 `access_stub`，共用时钟）+ `tx_session`（内存 SQLite 会话，用来测回滚）。确认以外的要点：`confirm` 仅命令本人（人）可调，管家 / 服务身份 / 代办一律 ACCESS_DENIED，确认一次性、绑定 commandId + 摘要；`run` = 同事务 prepare + submit，要确认的能力抛 CONFIRMATION_REQUIRED；commandId = `cmd_`+uuid7 全 32 位十六进制；任务号 `JR-0001`；事件至少一次投递，桩有 `redeliver(event_id)`，订阅者必须幂等。**与确认稿的差异**：登记类用普通调用（`job_handler` / `reconcile_handler` / `version_validator` / `subscribe`）不用装饰器；多了 `cancel_job`；`submit` 的键必须与 `prepare` 的键相同。**局限**：桩只有一个工作区；不展开 rrule（`fire(rule_id, planned_at)` 手动触发）；新订阅者从“现在”起收；`drain()` 手动推进后台任务与事件；能力编号在命令 / 调用契约里是短编号，在 execution-binding 契约里加 `titanloom.` 前缀；没有命令的任务（直接 `enqueue_in_tx`）还没有对应的 job-run 契约输出。原要求如下：
   - 先做：`register_binding`、`prepare` / `submit`（含幂等键）、`enqueue_in_tx`、`emit_in_tx`、`schedule`；同样配测试桩（同步执行、记录发出的事件和任务，供断言）。
4. **`facilities.api`**（公共设施 8 节）—— ✅ 接口 + 测试桩已做（2026-10-20，维护者说“继续”按提议签名执行）：模块级函数 `audit_in_tx / audit_for`、`register_todo_type / todo_open_in_tx / todo_reassign_in_tx / todo_close_in_tx / todo_withdraw_in_tx / get_todo / my_todos`、`notify_in_tx / my_notifications / mark_read / unread_count`、`register_texts / text / pack_version`、`ref_authorizer / add_ref / remove_ref / assets_of / download_grant`，实现经 `_provider.set_provider()` 装入；桩 `facilities.api.testing.facilities_stub`（依赖 `access_stub`，共用时钟；测回滚用 `kernel.testing.tx_session`，已从 execution 桩挪到 kernel）。要点：审计与业务同事务、哈希链（桩有 `verify_chain()`），前后值只存 `digest()` 摘要，查看审计需 `facilities.audit.read` 且自身留痕；多人待办只有一条、先办先得（`done_by`≠自己即“已由他人办理”），以 (类型, 来源引用) 幂等；通知收件人给账户，设了 `view_capability` 就按 `access.check(subject=…)` 去掉看不到对象的人（不回告），同去重键 5 分钟合并，按收件人语言渲染并记语言包版本；文案键以模块名开头、两种语言必备，`text()` 的语言取 `RequestContext.lang`（本步给 kernel 加了可选字段 `lang`）；文件下载权限跟随挂靠对象：引用模块用 `ref_authorizer` 登记“能否看到该对象”，隔离区 / 检查中不可下载，内容指纹去重（桩用 `put_asset` 造文件）。**局限 / 待办**：上传（分片、检查、派生物）、保留期清理、通知偏好 / 免打扰 / 外发、搜索契约、文案发布流程与前端语言包下载都没做；账户语言偏好的来源未定（桩用 `set_language`）；审计的 `delegation_id` 暂为空（`Whoami` 还没有这个字段）；待办事件（todo.opened 等）桩里直接写副本，真实实现再接 `emit_in_tx`。原要求如下：
   - 先做：审计（事务内写入）、待办（事务内发出 / 办完、登记类型）、通知（事务内发出）、文件（登记 / 取消引用、按引用下载）、文案（后端按语言取字）；同样配测试桩。
5. 发布后：更新 `plan/CODEMAP.md`（`tl.py gen`），在两份说明书的审核记录里写"底座接口已发布（提交号）"，告诉维护者转告考勤 Agent 继续阶段 2。
6. 然后：三块底座的真实实现 → 插件宿主 A → 文件解析器（Excel / CSV，**表单阶段 5 之前**）→ Shell A1 前后端 → 后台 P1 前后端。

接口规矩：模块之间只 import 对方的 `api` 和 `kernel`；接口签名一次定好（同一功能不出两套参数）；错误一律 `AppError(ErrorCode…)`；时间带时区；分页用 kernel 的游标。

> 待维护者确认的两点：① 首期用同步 SQLAlchemy 会话（路由写普通 `def`）；② 运行账号目前是一个 `titanloom_app`（对各模块 schema 读写），按模块分账号需要每模块一个引擎，先不做，模块间隔离靠 import-linter 与审核。

### 待维护者决定（累计）

1. ~~**access-filter 的 all + not 缺口**~~ **已决：选 A（维护者，2026-10-20），契约与 access.api 已改。**原问题：契约规定 `all` 不能再带 `not`，所以"全部减去拒绝条件"无法表达，测试桩现在直接 `NotImplementedError`。选项：A. 契约改为允许 `all` + `not`（改 access-filter 契约与 `access.api.types`、`sql.to_sqlalchemy` 已能支持）；B. 真实实现把它改写成 `any`（要把"全部"展开成枚举，部门多了会很长）。我倾向 A。
2. 首期用同步 SQLAlchemy 会话；运行账号先用单一 `titanloom_app`（见上）。
3. 第 1 步迁移与建库脚本需在装了 PostgreSQL 的环境验证。

## 4. 审核与合入（Agent 报"阶段 N 做完了"时）

1. 在 VM 里把 hq 克隆到临时目录、切到 Agent 分支、跑 `tl check`（不要在 VM 里碰 `wt\*`，也**不要 `git worktree prune`**——VM 看 Windows 的 worktree 都是 prunable）。
2. 读代码，对照设计与说明书验收；能复现的问题要实际跑出来。
3. 通过：`uv run python ops/tools/tl.py wp merge <编号> --keep`，在说明书写审核记录（通过 + 带到下阶段的小项）。合并冲突在说明书上时以 hq 版本为准（说明书归架构）。
4. 不通过：把意见写进说明书审核记录、状态改"返工"、提交，给维护者一段可以转给 Agent 的话（第一步永远是 `git merge local/integration`）。
5. 已发生过的违规（审核时留意）：Agent 在 hq 里执行命令；Agent 自己往说明书加 `allow` 放行（检查工具已改为只认集成分支上的说明书）。

## 5. 环境

- Windows 上：`uv sync`、`pnpm install`（apps/web）、PostgreSQL 16 已装；worktree 只能在 Windows 上建（`tl.py wp start`）。
- VM 里：`export UV_CACHE_DIR=$HOME/.uvcache UV_PROJECT_ENVIRONMENT=$HOME/hq-venv`，用 `$HOME/tlvenv/bin/uv`；没有就新建 venv 再 `pip install uv jsonschema pyyaml`。VM 跑不了 Windows 装的前端依赖，tsc 那项跳过是正常的。
- 原型：`D:\05_project\02_Titanloom\fidelity`（Prototype、WireFrame；改前备份到 `_backup`）。

## 6. 遗留

- A4 样例链（M1 出口用的示例命令全链路）。
- 合成数据扩充：孙悦两层部门、脏数据、跨月样本。
- 原型里的部门默认外观页（Project.html）。
