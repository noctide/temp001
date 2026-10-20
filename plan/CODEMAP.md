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

（api 层还没有对外函数）

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
