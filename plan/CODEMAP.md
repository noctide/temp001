# 代码地图

由 `tl.py gen` 生成，不要手改。**动手前先查这里：要用的东西已经有了就用，不要再写一份**（开发项目划分规范 5.5）。
别的模块只能引用对方 `api` 层与 `kernel`。

## kernel（公共内核，架构独占）

- `titanloom.kernel.clock`
  - `class Clock` — （没写说明）
  - `class SystemClock` — （没写说明）
  - `class FixedClock` — 测试用：固定时间，可前进。
  - `def ensure_utc` — （没写说明）
  - `def business_date` — 某一时刻在业务时区里是哪一天（考勤归属日等）；显示时区变化不影响它。
  - `def to_iso` — 对外的时间一律 ISO 8601 UTC，以 Z 结尾（契约 record-common）。
- `titanloom.kernel.context`
  - `class RequestContext` — （没写说明）
  - `def current` — 当前请求上下文；不在请求里（例如后台程序启动时）返回一个新的。
  - `def peek` — 有就返回，没有不新建（日志用）。
  - `def bind` — 设置上下文，返回令牌，用完交给 reset。
  - `def reset` — （没写说明）
  - `def new_request_id` — （没写说明）
- `titanloom.kernel.db`
  - `class DatabaseNotConfigured` — 没有设置连接串。启动期的配置错误，不是业务错误，不走 AppError。
  - `def database_url` — owner=True 取迁移账号的连接串，没设则退回运行账号。
  - `def make_engine` — （没写说明）
  - `def get_engine` — （没写说明）
  - `def set_engine` — 测试与引导用：换掉（或清掉）进程里共用的引擎。
  - `def current_session` — 当前事务里的会话；不在 `transaction()` 里调用是程序错误。
  - `def in_transaction` — （没写说明）
  - `def transaction` — 最外层：开会话、正常结束提交、出错回滚。已在事务里：加入它，由最外层决定提交。
  - `def bind_session` — 把一个现成的会话当作当前事务（测试用：事务回滚的 fixture 用它；里面的 transaction() 都加入它）。
- `titanloom.kernel.errors`
  - `class AppError` — 业务可预期的错误。code 必须是登记过的 ErrorCode。
  - `class ErrorBody` — （没写说明）
  - `class ErrorResponse` — （没写说明）
  - `def error_response` — details 只给有开发者资格的人看（总图 7"出错"）。
- `titanloom.kernel.exact`
  - `def dec` — 把字符串、整数变成 Decimal；不收 float（float 一进来就已经不精确了），不收无穷与 NaN。
  - `def parse_text` — 接口收到的数字字符串：只认规范写法（不认科学计数、空格、千分位）。
  - `def encode` — 对外编码：定点字符串，不用科学计数法。
  - `def quantize` — （没写说明）
- `titanloom.kernel.idem`
  - `def valid_key` — （没写说明）
  - `def canonical` — （没写说明）
  - `def request_digest` — 契约里的 requestDigest：sha256:<hex>。
- `titanloom.kernel.ids`
  - `def uuid7` — RFC 9562 UUIDv7：48 位毫秒时间 + 12 位单调序号 + 62 位随机。同一毫秒内单调递增。
  - `def uuid7_ms` — 取出 UUIDv7 里的毫秒时间（排查用）。
  - `def short_code` — 给人看的短编号，如 AU-0013（契约 record-common.code）。编码规则可改，不影响内部关联。
- `titanloom.kernel.log`
  - `def redact` — （没写说明）
  - `class JsonFormatter` — （没写说明）
  - `def get_logger` — （没写说明）
  - `def setup` — （没写说明）
- `titanloom.kernel.migrate`
  - `def migrations_dir` — （没写说明）
  - `def version_table` — （没写说明）
  - `def module_metadata` — （没写说明）
  - `def config_for` — （没写说明）
  - `def upgrade` — （没写说明）
  - `def new_revision` — 从 store/models.py 与当前数据库的差别生成一份迁移脚本；生成后要人看一遍再提交。
  - `def run_env` — env.py 调用：在线执行迁移。
- `titanloom.kernel.paging`
  - `class Page` — （没写说明）
  - `def clamp_limit` — （没写说明）
  - `def encode_cursor` — （没写说明）
  - `def decode_cursor` — （没写说明）
- `titanloom.kernel.params`
  - `class UnknownParam` — （没写说明）
  - `class ParamStore` — （没写说明）
- `titanloom.kernel.testing`
  - `def connect_test_db` — 连测试库；没设或连不上就跳过当前测试。
  - `def schema_session_fixture` — 生成一个 pytest fixture：临时 schema 里建好这些 metadata 的表，交出一个当前事务的会话。
  - `def track_rollback` — 内存测试桩的事务支持：在 kernel.db 事务里第一次改动前调用，会话回滚时用 restore 还原到那时的快照。
  - `def tx_session` — 一个内存 SQLite 会话并设为当前事务：测试里 session.commit() / rollback() 模拟请求成功 / 失败。

生成的常量：`titanloom.kernel.reg`（ErrorCode、K 文案键、P 业务参数、F 功能）；前端 `shared/base/reg`。

## access

登记：params 0 · features 0 · pages 0 · objects 0

- `access.api.__init__.whoami` — 当前主体、所在部门（含兼岗）、是否管家代办。主体取自 kernel.context。
- `access.api.__init__.check` — 能不能。subject 默认当前主体；查别人需要诊断资格。
- `access.api.__init__.access_filter` — 能看哪些。翻译成查询条件用 access.api.sql.to_sqlalchemy。
- `access.api.__init__.members` — 部门 / 项目成员，可按日期。
- `access.api.__init__.memberships` — 某人所在的部门与项目，可按日期。
- `access.api.__init__.register` — 模块登记能力、功能、权限字段、可遮挡列。同样内容重复登记没有影响；同一个编号内容不同则报错。
- `access.api._provider.AccessApi` — （没写说明）
- `access.api._provider.set_provider` — 装入实现，返回原来的（用完要装回去）。
- `access.api._provider.use_provider` — （没写说明）
- `access.api._provider.provider` — （没写说明）
- `access.api.sql.FilterFieldNotMapped` — 筛选条件用到的权限字段，调用方没有给出对应的列。程序错误，不能当作“不限”放行。
- `access.api.sql.to_sqlalchemy` — 返回可直接 `.where(...)` 的条件。columns：权限字段名 → 列。
- `access.api.testing.RegistrationConflict` — 同一个编号重复登记且内容不同。
- `access.api.testing.NotRegistered` — 用了没登记的能力、资源类型或权限字段。
- `access.api.testing.Cond` — 数据条件（身份与权限 6，只有登记的几种）。field 是调用模块登记的权限字段，all 不需要。
- `access.api.testing.Grant` — （没写说明）
- `access.api.testing.InMemoryAccess` — （没写说明）
- `access.api.testing.as_principal` — 测试里以某个账户的身份办事（设置 kernel 的请求上下文，结束后恢复）。
- `access.api.testing.access_stub` — 装入合成小组织的测试桩；测试结束恢复原来的实现，状态不外漏。
- `access.api.types.DeptRef` — （没写说明）
- `access.api.types.Whoami` — 当前主体。departments 含兼岗；acting_for 有值表示管家代办（值 = 被代办本人的账户）。
- `access.api.types.Target` — 判定的对象及其真实归属。没有对象（只问“有没有这项能力”）时传 None。
- `access.api.types.StepResult` — （没写说明）
- `access.api.types.Decision` — 能不能（契约 access-decision）。拒绝时 failed_step 与 reason_key 必有。
- `access.api.types.Predicate` — field 必须是调用模块登记的权限字段（身份与权限 6、12）。eq 只有一个值。
- `access.api.types.AccessFilter` — 能看哪些（契约 access-filter）：all / none / 允许条件之并减去拒绝条件之并，附须遮挡的列。
- `access.api.types.ScopeRef` — （没写说明）
- `access.api.types.Member` — 部门 / 项目成员；一律带部门（重名靠部门区分，身份与权限 3）。
- `access.api.types.Membership` — （没写说明）
- `access.api.types.CapabilityDecl` — 模块登记的能力。新能力默认谁都没有（身份与权限 7）。feature_id 非空 = 属于功能开放的“新建 / 发起”类。
- `access.api.types.FeatureDecl` — （没写说明）

## admin

登记：params 0 · features 0 · pages 0 · objects 0

（api 层还没有对外函数）

## agent

登记：params 0 · features 0 · pages 0 · objects 0

（api 层还没有对外函数）

## attendance

登记：params 0 · features 0 · pages 0 · objects 0

（api 层还没有对外函数）

## automation

登记：params 0 · features 0 · pages 0 · objects 0

（api 层还没有对外函数）

## dataproc

登记：params 0 · features 0 · pages 0 · objects 0

（api 层还没有对外函数）

## execution

登记：params 0 · features 0 · pages 0 · objects 0

- `execution.api.__init__.register_binding` — 登记能力的执行方式。同样内容重复登记没有影响；同一能力内容不同则报错。
- `execution.api.__init__.job_handler` — 登记“拿到任务怎么干”。任务类型就是能力编号，或 enqueue_in_tx 用的类型名。
- `execution.api.__init__.reconcile_handler` — 登记领域的核对方法：副作用不确定时由平台调用，结论必须附证据。
- `execution.api.__init__.version_validator` — 登记“目标版本还是不是准备时的那个”。提交时返回 False 则拒绝，要求重新准备。
- `execution.api.__init__.prepare` — 准备一条命令：固定参数与版本、算摘要、查权限、存预览。主体取自 kernel.context。
- `execution.api.__init__.confirm` — 确认。只给 HTTP 确认界面调用：只有命令本人（人）能确认，管家、服务身份、代办一律 ACCESS_DENIED。
- `execution.api.__init__.submit` — 提交 = 一次写完：复查权限与版本、消费确认、写调用与任务。同一事务。重复提交返回原调用。
- `execution.api.__init__.run` — 低影响操作：同一请求、同一事务里 prepare + submit，参数与 prepare 完全相同。
- `execution.api.__init__.cancel` — 取消还没接收的命令。已接收的要取消任务（cancel_job）。
- `execution.api.__init__.cancel_job` — 请求取消任务：没开始直接取消，运行中在检查点停；已完成的如实返回完成。
- `execution.api.__init__.enqueue_in_tx` — 在调用者自己的事务里放一个后台任务；事务回滚则任务也没有。不在事务里报错。
- `execution.api.__init__.emit_in_tx` — 在调用者自己的事务里写一条事件到发件箱，返回事件编号。不在事务里报错。
- `execution.api.__init__.schedule` — 登记或修改定时规则（按 rule_id）。返回规则编号。
- `execution.api.__init__.pause_schedule` — （没写说明）
- `execution.api.__init__.resume_schedule` — （没写说明）
- `execution.api.__init__.end_schedule` — （没写说明）
- `execution.api.__init__.get_job` — （没写说明）
- `execution.api.__init__.subscribe` — 订阅事件（event_type 可带 * 通配，如 attendance.*）。至少一次投递，handler 必须幂等（按 event_id 去重）。
- `execution.api._provider.ExecutionApi` — （没写说明）
- `execution.api._provider.set_provider` — 装入实现，返回原来的（用完要装回去）。
- `execution.api._provider.use_provider` — （没写说明）
- `execution.api._provider.provider` — （没写说明）
- `execution.api.testing.BindingConflict` — 同一个能力重复登记且内容不同。
- `execution.api.testing.NotRegistered` — 用了没登记的能力、处理器或规则。
- `execution.api.testing.NotInTransaction` — enqueue_in_tx / emit_in_tx 必须在 kernel.db 事务里调用。
- `execution.api.testing.key_at` — 造一个时间戳在 when 的 UUIDv7 防重复编号（不碰 kernel.ids 的全局单调状态）。
- `execution.api.testing.InMemoryExecution` — execution.api 的测试桩。time 取 clock，主体与代办取 access.api。
- `execution.api.testing.execution_stub` — 装入测试桩（时钟与 access_stub 共用）；测试结束恢复原来的实现，状态不外漏。
- `execution.api.types.command_id` — 对外命令编号：cmd_ + uuid7 的全部 32 位十六进制；内部仍是同一个 uuid。
- `execution.api.types.command_uuid` — （没写说明）
- `execution.api.types.TargetRef` — 命令作用的对象。id 必须是具体的，不能是 latest（规范 6.3）。
- `execution.api.types.ScopeKey` — 重道按范围轮流、限排队（命令与任务 7）。
- `execution.api.types.RetryPolicy` — （没写说明）
- `execution.api.types.ReconcilePolicy` — （没写说明）
- `execution.api.types.ExecutionBinding` — 能力的执行登记。id 与 access 的能力编号一致（模块.资源.动作），输出契约时加 titanloom. 前缀。
- `execution.api.types.PreviewSpec` — 影响预览：由领域算好传入，结构化（文案键 + 参数 + 数量 + 受影响对象），不是成句文字。会进命令摘要。
- `execution.api.types.PrepareResult` — （没写说明）
- `execution.api.types.Confirmation` — （没写说明）
- `execution.api.types.JobRef` — job_id 是内部 uuid7；code 是给人看的 JR-xxxx。
- `execution.api.types.Invocation` — （没写说明）
- `execution.api.types.EventDraft` — 要写进发件箱的事件。只带类型、对象、版本，不带业务明细（契约 outbox-event）。
- `execution.api.types.Event` — 交给订阅者的事件。至少一次投递：处理必须幂等，按 event_id 去重。
- `execution.api.types.JobRetry` — （没写说明）
- `execution.api.types.JobResult` — 处理器交回的结果。effect_status=unknown 表示不知道做没做成：进待核对，不自动重发。
- `execution.api.types.Reconciliation` — 领域核对方法的结论，必须附证据。
- `execution.api.types.JobContext` — 处理器拿到的东西：输入、检查点、进度、取消。
- `execution.api.types.JobView` — （没写说明）
- `execution.api.types.Misfire` — （没写说明）
- `execution.api.types.ScheduleRuleSpec` — （没写说明）
- `execution.api.types.Occurrence` — 一个计划时刻的去向。同一规则同一时刻只记一条（唯一）。

## facilities

登记：params 0 · features 0 · pages 0 · objects 0

- `facilities.api.__init__.audit_in_tx` — 在业务改动的同一事务里写一条审计，返回 event_id。只追加、不可改；前后值只存摘要（用 `digest()` 算）。
- `facilities.api.__init__.audit_for` — 按对象查审计，新的在前。需要 `facilities.audit.read`；查看本身也会记一条审计。
- `facilities.api.__init__.register_todo_type` — 登记待办类型。同样内容重复登记没有影响；内容不同报错。
- `facilities.api.__init__.todo_open_in_tx` — 新建待办。同一 (类型, 来源引用) 已有未关闭的，原样返回（幂等）。多个办理人 = 一条多人待办。
- `facilities.api.__init__.todo_reassign_in_tx` — 改办理人。办理人没变则无影响；已关闭的待办 CONFLICT 类错误（RESOURCE_VERSION_CONFLICT）。
- `facilities.api.__init__.todo_close_in_tx` — 办完。多人待办先到先得：之后再关的返回已有结果，不覆盖 done_by。done_by 必须是办理人。
- `facilities.api.__init__.todo_withdraw_in_tx` — 来源对象不需要办了（撤回、取消）。已办完的保持办完。
- `facilities.api.__init__.get_todo` — 给所属模块读自己的待办状态；没有则 RESOURCE_NOT_FOUND。
- `facilities.api.__init__.my_todos` — 我的待办（我是办理人的），新的在前。收件箱自己不改状态：办理走待办类型登记的能力。
- `facilities.api.__init__.notify_in_tx` — 在事务里发应用内通知。看不到对象的收件人被去掉；按收件人语言渲染并记语言包版本；
- `facilities.api.__init__.my_notifications` — 我的通知，新的在前。
- `facilities.api.__init__.mark_read` — 标已读，只对自己的生效；返回实际改变的条数。
- `facilities.api.__init__.unread_count` — （没写说明）
- `facilities.api.__init__.register_texts` — 登记本模块的文案键（键以模块名开头，两种语言都要有）。同样内容重复登记没有影响。
- `facilities.api.__init__.text` — 后端取字。lang 不给就用请求上下文的语言，再没有用默认语言。键没登记 / 缺参数是程序错误。
- `facilities.api.__init__.pack_version` — 当前语言包版本（前端按版本下载、通知记录渲染时用的版本）。
- `facilities.api.__init__.ref_authorizer` — 登记“当前主体能不能看到这个挂靠对象”。文件的下载权限跟随挂靠对象（公共设施 3）。
- `facilities.api.__init__.add_ref` — 业务对象引用一个文件版本（在事务里）。已隔离 / 撤回 / 清除的不能引；重复引用返回原引用。
- `facilities.api.__init__.remove_ref` — 取消引用（在事务里）。没有引用的文件版本过宽限期后清理。引用本来就不存在则无影响。
- `facilities.api.__init__.assets_of` — 某个对象引用着的文件版本及状态。调用者已经确认过当前主体能看这个对象。
- `facilities.api.__init__.download_grant` — 凭引用换下载许可：引用必须存在，挂靠对象对当前主体可见，文件版本必须可用（隔离区不可下）。
- `facilities.api._provider.FacilitiesApi` — （没写说明）
- `facilities.api._provider.set_provider` — 装入实现，返回原来的（用完要装回去）。
- `facilities.api._provider.use_provider` — （没写说明）
- `facilities.api._provider.provider` — （没写说明）
- `facilities.api.testing.RegistrationConflict` — 同一个编号重复登记且内容不同。
- `facilities.api.testing.NotRegistered` — 用了没登记的待办类型、文案键或挂靠模块。
- `facilities.api.testing.NotInTransaction` — 名字带 in_tx 的调用必须在 kernel.db 事务里。
- `facilities.api.testing.TextParamMissing` — 文案里的占位符没给参数。
- `facilities.api.testing.InMemoryFacilities` — facilities.api 的测试桩。时间取 clock，主体与权限取 access.api。
- `facilities.api.testing.facilities_stub` — 装入测试桩（时钟与 access_stub 共用）；测试结束恢复原来的实现，状态不外漏。
- `facilities.api.types.digest` — 审计里只存前后值的摘要（sha256:<hex>），不存原值。
- `facilities.api.types.ObjectRef` — 一个业务对象：审计的对象、通知的主题、文件引用的挂靠对象。id 必须是具体的。
- `facilities.api.types.AuditDraft` — 调用方交的内容；谁、何时、哪个代办、策略版本由实现从请求上下文与时钟补。
- `facilities.api.types.AuditEvent` — （没写说明）
- `facilities.api.types.TodoKey` — 一条待办的身份：待办类型 + 来源对象引用（幂等靠它）。source_ref 形如 attendance:leave:LV-0001。
- `facilities.api.types.TodoTypeDecl` — 登记待办类型。办理（完成 / 驳回等）由 handle_capability 这个能力完成，收件箱自己不改状态。
- `facilities.api.types.TodoDraft` — （没写说明）
- `facilities.api.types.TodoView` — 契约 todo-item。多人待办只有一条：先办的人记在 done_by，其余人看到“已由他人办理”（done_by 不是自己）。
- `facilities.api.types.NotifyDraft` — 应用内通知。收件人是账户；设了 view_capability 的，看不到对象的收件人会被去掉（不报错、不回告）。
- `facilities.api.types.NotificationView` — （没写说明）
- `facilities.api.types.TextEntry` — 一个文案键的两种语言版本；用 {name} 占位。
- `facilities.api.types.AssetRef` — 契约 asset-ref：业务对象只引用 asset_id + version。
- `facilities.api.types.AssetVersionView` — （没写说明）
- `facilities.api.types.DownloadGrant` — 一次性短时下载许可；没有匿名长链接（公共设施 3）。
- `facilities.api.types.is_text_key` — （没写说明）

## forms

登记：params 2 · features 0 · pages 0 · objects 0

（api 层还没有对外函数）

## integration

登记：params 0 · features 0 · pages 0 · objects 0

（api 层还没有对外函数）

## knowledge

登记：params 0 · features 0 · pages 0 · objects 0

（api 层还没有对外函数）

## plugin_host

登记：params 0 · features 0 · pages 0 · objects 0

（api 层还没有对外函数）

## shell

登记：params 0 · features 0 · pages 0 · objects 0

（api 层还没有对外函数）

## visualization

登记：params 0 · features 0 · pages 0 · objects 0

（api 层还没有对外函数）
