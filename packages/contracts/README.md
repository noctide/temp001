# Titanloom 契约骨架（M0 草案）

来源：《平台能力契约与Agent接入规范》3.1、3.2、6.5、8.2、8.3、12.1 与总框架 8.3。
状态：草案，未冻结；与规范冲突时以规范为准。这里的 JSON Schema 只固化规范已明确写出的字段与禁止项，没有新增业务语义。

| 文件 | 内容 |
| --- | --- |
| capability-descriptor.schema.json | 能力描述符 v0.2（字段名对齐能力契约 3.3 示例；命名规则、业务写入必须幂等、draft_only 限制、Schema 引用须带摘要） |
| command.schema.json | 命令与状态（accepted 必须有 invocationRef，等待确认必须绑定影响摘要） |
| job-attempt.schema.json | JobAttempt：Worker、租约、单调 fencing token、副作用状态（来源：能力契约 8.1、8.4） |
| prepare-result / job-state-notification .schema.json | 命令准备结果（影响范围未知不得自动执行）、状态推送通知（只含 jobId 与 stateVersion） |
| job-run.schema.json | JobRun（unknown 副作用不得直接 canceled / succeeded，终态必须有 finishedAt） |
| error.schema.json | 错误体（不得携带栈等内部字段） |
| state-machines.json | 命令与 JobRun 的迁移表 |
| query-execute-request / query-execute-response .schema.json | Query 执行请求与响应（来源：能力契约 9.1–9.2）：不得提交 SQL 与连接，snapshot 必须带快照，decimal 用字符串编码 |
| config-activation / audit-event / platform-alert-rule .schema.json | 配置激活（pending 至 failed，逐目标记录）、审计事件（前后值只存摘要）、平台告警规则（不承载领域业务异常）（来源：后台治理 7.2–7.3、12.1–12.2） |
| error-codes.json | 错误码注册表：22 个取自能力契约 12.2，7 个拟定（proposed） |
| pipeline-run.schema.json | PipelineRun 领域状态（拟定）：运行、质量、发布三个维度与不变量（来源：数据处理 15.1） |
| idempotency-record.schema.json | 幂等记录：作用域、requestDigest、保留期与 tombstone（来源：能力契约 7.1、14.2） |
| invocation-context / delegation / confirmation / invocation / outbox-event .schema.json | 调用链对象：可信调用上下文、委托、确认、调用、事件信封（来源：能力契约 5.2、5.3、6.4、7.2、13，考勤 15.3） |
| channel-connection / delivery-route / inbound-endpoint / inbound-receipt .schema.json | 集成与消息通道对象（来源：集成与消息通道子方案 3、4）：目标只能是 SecretRef、入站必须鉴权与时间窗、命令类入站必须绑定身份 |
| field-ref / query-filterable / dataset-generation-changed .schema.json | 字段标识 FieldRef、Query 可筛选声明、数据代次变化事件载荷（拟定，来源：数据处理 12.6、可视化 8.2–8.3）；Query 请求新增按 FieldRef 的 filters，响应新增 dataGeneration 与列 fieldRef（能力契约 9.1） |
| i18n-key-manifest / language-pack / localized-text .schema.json | 键清单与出厂默认文案、已发布语言包（关键文案缺失不得激活）、配置数据中的多语言名称（来源：国际化规范 3–7）；错误码注册表每个码附由错误码推导的 `errors.` 文案键 |
| record-common / search-doc / search-provider .schema.json | 每张表通用列（UUIDv7、短编号、revision、UTC 时间、归属）、全局搜索索引条目（不存正文、可见性只存摘要）、SearchProvider 登记（必须有 check_visible 复核、可搜索操作只跳站内）（来源：后端详细设计·总图 6、9，Shell 9.7，能力契约 9.5）；租约与 fencing token 在 job-attempt，job-run 不另存 |
| grant / access-decision / access-filter / feature-layer / access-policy-changed .schema.json | 身份与权限：授权（角色与单项能力二选一、拒绝只针对单项能力、数据条件白名单、申请批准必有期限、管家只在资源准入行）、判定结果（卡在哪一关、原因只给文案键）、筛选条件（结构化谓词，不返回 SQL）、部门 / 项目收紧（只能往紧）、权限变化事件（来源：后端详细设计·身份与权限，ADR-027） |
| execution-binding / schedule-rule / trigger-occurrence / reconcile-case .schema.json | 命令与任务：能力执行登记（重道必须后台、不确定副作用不在可重试原因里）、定时规则（IANA 时区、补跑必须有上限、必须声明重叠策略）、计划时刻（UTC、错过与跳过记原因）、待核对（结论四种、必须附证据并经领域命令落地）（来源：后端详细设计·命令与任务，ADR-028） |
| asset-version / asset-ref / notification / notify-pref / todo-item .schema.json | 公共设施：文件版本（不暴露路径、检查未过不可用、首期 virusScan=not_performed）、文件引用（按引用鉴权）、站内通知（只站内链接、无业务明细、记语言包版本）、个人通知设置（必读 / 审批 / 账户安全不能关）、待办副本（组待办先办先得）；audit-event 加指纹链（来源：后端详细设计·公共设施，ADR-029） |
| plugin-manifest / composition-version / shell-me / resource-resolve / plugin-health .schema.json | M1 外壳：插件清单（清单外登记被拒、底座不可卸载、排空上限 600 秒、皮肤包不提供服务）、组合版本（底座必须启用、记上一版可回退）、我的外壳（入口不可用只标不藏、角标来源不可用为空）、稳定链接解析（链接不含部门、无权结果不泄露名称）、插件健康（连续 3 次才标不可用）（来源：后端详细设计·插件宿主 · Shell · 平台管理（M1），ADR-030） |
| test_contracts.py、test_contracts_part2.py … test_contracts_part12.py | 校验示例、负例与状态机一致性；`pip install jsonschema` 后分别运行 |

集成通道的 channel-connection、delivery-route、inbound-endpoint 现使用 revisionState 与 operationalState 两个字段，不再使用单一 state。尚未覆盖：MessageTemplate、DeliveryRecord / Attempt、ExternalIdentityRef，以及各领域能力的 inputSchema / outputSchema。字段只取自规范已写明部分，未写明的（如事件类型清单、数据级别枚举的最终取值）属提案，待冻结。
