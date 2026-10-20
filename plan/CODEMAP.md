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

（api 层还没有对外函数）

## facilities

登记：params 0 · features 0 · pages 0 · objects 0

（api 层还没有对外函数）

## forms

登记：params 0 · features 0 · pages 0 · objects 0

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
