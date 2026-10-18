"""公共内核（架构独占；开发项目划分规范 5.5 第 3 条）。

各模块只从这里拿公共工具，不在模块里另写一份：
    errors   统一错误体与 AppError（能力契约 12；契约 error.schema.json、error-codes.json）
    ids      UUIDv7 内部编号、给人看的短编号（总图 6）
    clock    时钟（领域层不直接读时间，由参数传入）、UTC 与业务日期（总框架 8.7）
    paging   （排序键, id）游标分页，禁止无界查询（工程规范 4.3）
    exact    精确数值：Decimal（不收 float）与对外字符串编码（数据处理 12.3）
    context  请求上下文（requestId、主体、jobId、pluginId）
    idem     幂等：请求摘要（能力契约 7）
    log      结构化日志（带上下文里的编号），凭据类字段自动打码
    params   业务参数读取（ADR-022；值按看的人所在部门取）
    reg      生成的常量（tl.py gen 生成，不手改）
"""
