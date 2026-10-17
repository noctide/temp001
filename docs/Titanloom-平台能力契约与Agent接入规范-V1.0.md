# Titanloom · 平台能力契约与 Agent 接入规范

> 版本：V1.0｜设计日期：2026-09-26｜修订日期：2026-10-03｜状态：详细设计稿，可用于接口拆解与工程评审；未实现、未验收。
> 修订：2026-10-17 14.2 授权判定缓存改为登记 60 秒陈旧期限（ADR-027）；新增 9.5 全局搜索提供方（SearchProvider，ADR-026）；2026-10-01 全文档边界统一，平台运行告警改由 PlatformAlertRule / PlatformAlertInstance 管理、业务告警归所属领域（18，ADR-009）；不再预设公共 ContributionEvent / Contribution Graph 服务（18，ADR-010）；2026-10-03 9.1 Query 请求新增按 FieldRef 的 filters，响应新增 dataGeneration 与列 fieldRef（数据处理 12.6，拟定）；2026-10-03 通读 9.3–11、16：10.3 注明 WAIT_TIMEOUT 为 CLI 本地结果码，16 新增 A29（按 FieldRef 筛选）与 A30（数据代次）验收用例；2026-10-03 6.2 与 12.1 示例的 messageKey 改为国际化规范的键名格式。
> 项目定位：面向大型企业场景设计的开源项目；本文不表示任何组织已立项、授权部署或已交付。实际接入企业数据须遵守使用方的授权与数据规则。
> 文档定位：总框架的公共工程配套规范，不新增业务能力域，不替代各领域子方案或公共平台能力方案。
> 权威依据：《Titanloom-总框架设计方案-V1.0.md》及其现行同步基线；本规范负责
> Capability、Command、委托、幂等、确认和公共执行语义。
> 关联输入：数据处理、表单平台、考勤签到、工具自动化、知识与文档、数据可视化、Shell
> / 门户、后台治理及插件扩展等现行 V1.0
> 方案。领域内部对象和状态仍以所属方案为权威。
> 本规范定义跨平台命令、委托、幂等和公共执行语义；数据血缘由数据处理平台、平台运行告警与领域业务告警分别由各自 Owner 维护，跨资源依赖投影由后台治理维护，Notification 只负责投递。接口路径、字段和限额是拟采用的工程设计，不表示已有服务可调用。

## 1. 设计结论与首期范围

Titanloom 采用"统一能力契约 + 服务端授权与执行 + 多种薄接入端"。平台内置
Agent 使用受控 API / SDK；外部命令行 Agent 使用统一 `titanloom` CLI
和按需加载的 Skills；浏览器与其他应用通过 API
接入。全部入口复用业务规则、三道门、数据出口和任务设施。

  ---------------------------------------------------------------------------------------------------------------
  项目                    首期决定                         依据与边界
  ----------------------- -------------------------------- ------------------------------------------------------
  Platform Capability API 核心建设                         定义能力语义、输入输出、权限、执行与验证方式

  能力目录                核心建设                         可授权发现、按需读取、契约与实现版本可追踪

  HTTP API + Python /     核心建设                         配合现有 FastAPI、Python、React / TypeScript 基线
  TypeScript SDK                                           

  统一 CLI                实现首批业务命令                 一个客户端、多业务子命令；不为每中心单独维护认证体系

  Skills                  实现首批业务场景                 描述方法和限制，不承载权限裁决或权威计算

  MCP                     首期不实现、不部署、不作为依赖   保留总框架中性 Interaction Adapter
                                                           边界，不为其预建运行设施

  A2A                     有明确外部协作对象后再实施       能力卡、任务映射、身份信任与数据边界另行验收

  动态生成接入代码        不进入首期生产调用链             AI 辅助生成草稿，测试和发布后成为固定版本连接器
  ---------------------------------------------------------------------------------------------------------------

不以未经同条件验证的 Token 百分比或吞吐倍数决定架构。不将
CLI、Skills、MCP、A2A
视为安全边界本身；是否安全取决于身份、授权、隔离、数据出口和执行实现。

### 1.1 首期必须闭合的行为

1.  发现当前主体允许获知的能力，并读取精确版本的参数契约。
2.  查询获授权的已发布 Query，返回有界结果及数据版本。
3.  准备一个业务命令，显示影响，需要时由人工受控确认。
4.  提交已发布流水线运行，获得持久 JobRun / PipelineRun 引用。
5.  网络中断后查回同一执行记录，避免重复业务副作用。
6.  查询进度、申请取消、检查产物；撤权后停止后续受限操作和交付。
7.  模型不可用时，人工业务及已发布的确定性任务继续运行。

### 1.2 不在本规范中重建的能力

表单审批状态、考勤计算、流水线 DAG 恢复策略、Query SQL
计划、资产存储、页面发布和导播分别由所属模块管理。本文定义它们的公共调用边界，不实现通用业务流程引擎，也不把所有业务状态合并成
JobRun。

## 2. 结构与职责

``` mermaid
flowchart TD
    UI["网页与固定自动化"] --> API["受控 API / SDK"]
    IA["平台内置 Agent"] --> API
    EA["外部 Agent：CLI / GUI / WebUI"] --> AD["API 或统一 CLI"]
    SK["Skills：任务方法"] -.-> IA
    SK -.-> EA
    API --> G["身份、委托与能力授权边界"]
    AD --> G
    G --> B["所属模块业务服务"]
    B --> D["Dataset / Query 与 Asset 出口"]
    B --> J["持久任务服务"]
    J --> W["受限执行器"]
    W --> B
```

图中授权边界是共同服务契约，不要求独立网关进程。数据、文件二进制与进度推送仍有各自受控通路；不得为了统一入口而把所有流量和所有结果装入一个调用接口。

所有领域模块面向同一个平台级 Agent
提供可注册的领域能力和可选择的页面上下文入口；允许的写动作可以由 Agent
经同一服务端命令与领域业务规则执行，不限于生成建议或草稿。每项领域能力分别声明支持的读取、分析、建议、草稿、执行及管理范围；未实现或未授权不表示
Agent
被困在发起模块。跨模块任务保存当前目标领域、资源引用、委托、版本和相关证据，切换领域后按目标能力再次鉴权；页面导航或
Tool 描述不构成授权。领域事实和状态仍由所属模块拥有，Agent
运行时只负责协调和受控调用。

  -----------------------------------------------------------------------------------------------------
  构件                    负责                                     不负责
  ----------------------- ---------------------------------------- ------------------------------------
  Capability Registry     能力标识、契约、版本、绑定、上线状态     授予业务权限、执行任意代码

  Identity / Delegation   主体、运行端、短期凭证、可撤销委托       代替业务 ACL、资源准入
  Service                                                          

  Authorization Service   统一判定及策略版本                       用模型推断权限、信任客户端身份字段

  Command Service         准备、确认关联、提交幂等和调用记录       表单审批决定、领域数据写入规则

  Domain Service          业务状态、参数语义、事务、结果证明       将本域表开放给其他模块任意写入

  Job Service             任务持久化、领取、租约、尝试记录和状态   拥有所有中心的业务流程

  Executor / Runner       在授权、预算和隔离下执行具体任务         扩大委托、自行替换输入版本

  Model Delivery Guard    模型输入许可、过滤和交付记录             只靠脱敏提示词保护数据

  API / SDK / CLI Adapter 参数映射、认证接入、结构化输出           复制服务端规则、绕过三道门
  -----------------------------------------------------------------------------------------------------

Model Delivery Guard
是对现有模型输入检查职责的工程命名，可实现为共享组件，不要求新增服务。外部
Agent 接口的返回内容也必须经过等价的交付检查。

### 2.1 跨域调用与领域运行边界

跨模块主动调用统一遵循"调用者 → Capability / Command → 目标 Domain
Service → 必要时 Job Service / Executor"。Human、Agent、Automation 和 UI
不建立不同的业务后门；跨领域可以携带已验证的任务上下文和稳定资源引用，但到达目标领域后必须按目标能力、目标资源、当前委托和当前策略重新鉴权。

Command 表达希望目标领域执行的意图；DomainEvent
表达领域已经发生的事实。事件、通知、审计记录和 Shell /
后台投影不得代替领域 Command
修改业务事实。固定自动化消费领域事件或其他登记触发源时，其
TriggerOccurrence 与 AutomationRun 由工具自动化平台维护，再通过目标
Capability / Command 调用其他领域。

公共 JobRun / JobAttempt
只承担调度与执行语义。PipelineRun、AutomationRun、AgentTask、WorkflowInstance
等领域运行保留各自业务状态、取消、重跑和结果判定。Execution Retry 不等于
Domain Rerun；取消 JobRun 不自动等于取消领域运行。网络中断优先通过
commandId、invocationId、jobId 或领域 Run
引用恢复原执行，不以重新提交作为默认恢复方式。

## 3. 统一能力契约

### 3.1 标识与粒度

内置能力格式为
`titanloom.<domain>.<resource>.<action>`，示例：`titanloom.data.pipeline.run`。命名空间固定、不可翻译；名称与用户界面文字分离。扩展能力使用平台授予的发布者命名空间，不能抢占
`titanloom`。

能力按"可独立授权的业务动作"划分：读取元数据、读取内容、编辑草稿、发布、执行、下载分别登记。禁止一个
`admin.execute` 或 `run_anything`
接口承载所有动作。内部函数、画布节点和组件不必全部变为 Agent 工具。

  ------------------------------------------------------------------------------
  维度                                取值与规则
  ----------------------------------- ------------------------------------------
  `operationKind`                     `read` / `draft_write` / `business_write`
                                      / `control`

  `impactLevel`                       `low` / `medium` /
                                      `high`；按影响评估，读取敏感数据也可能是
                                      high

  `executionMode`                     `sync` / `async` / `adaptive`；adaptive
                                      的转换条件写入契约

  `effectModel`                       `none` / `atomic` / `staged_publish` /
                                      `external`

  `agentPolicies`                     能力支持的 `deny` / `draft_only` /
                                      `confirm` / `allow` 子集；不表示已授予

  `publicationState`                  `draft` / `active` / `deprecated` /
                                      `disabled` / `retired`
  ------------------------------------------------------------------------------

`impactLevel` 描述能力潜在影响，不能直接映射为自治风险
R0／R1／R2+。公共自治风险只适用于明确登记的 Agent 写入或控制动作：R0
是经版本化确定性规则证明不改变事实、权限、操作步骤或业务行为的有限修复，且领域已显式启用自动执行；R1
须经授权人员快速审核；R2+
须走正式人工审核或领域原有更严格流程。未分类、证据不足、来源失效或规则版本不符时不得归为
R0，按更严格路径处理。模型置信度不能单独证明
R0；数字、端口、命令、链接目标、业务口径和安全语义的修改默认不属于 R0。

该分级仅决定自动化上限，不授予资源权限，不代替基础 ACL、委托、Agent
三道门、能力策略、发布门槛及法定或业务审批。服务端在准备和提交边界重新核验风险级别、目标版本、规则证据与审核记录；规则升档使原确认失效时须重新准备。各领域登记允许的动作、例外、判定器版本、自动执行开关和回退条件，经平台治理审核后启用；知识域的
R0 规则不自动适用于数据处理或后台处置。精确风险判定 Schema
和跨领域验收属于后续工程契约。

`draft_only` 只用于有明确草稿语义的能力。正式 `pipeline.run`
不能因为返回"计划"就伪装成可执行草稿；准备命令与真正运行是两件事。

### 3.2 描述符字段

  ------------------------------------------------------------------------------------
  字段                                必需语义
  ----------------------------------- ------------------------------------------------
  `capabilityId` / `contractVersion`  稳定能力 ID 与精确契约版本

  `ownerModule` / `ownerTeamRef`      唯一业务所有者及维护责任引用

  `titleKey` / `descriptionKey`       本地化显示键；模型说明也按版本维护

  `inputSchema` / `outputSchema`      平台登记的 JSON Schema 引用及摘要

  `operationKind` / `impactLevel` /   动作性质、影响和副作用边界
  `effectModel`                       

  `resourceRequirements`              目标、输入、输出、依赖资源的解析与权限要求

  `preconditions`                     发布状态、资源版本、业务条件、锁或租约等

  `authorization`                     权限动作、支持策略、委托要求；实际决策在服务端

  `execution`                         模式、超时、预算类别、排队期限、取消和重试语义

  `idempotency`                       是否必需、作用域、保留期配置引用、业务去重规则

  `confirmation`                      是否支持影响预览，哪些条件要求人工确认

  `resultVerification`                成功证据及验证器版本；不能只有自然语言结果

  `modelDelivery`                     可交付信息类别、Schema / 样本准入与输出上限

  `bindings`                          受控 HTTP、SDK、CLI
                                      映射；不包含可由调用者任意替换的执行入口

  `implementationRef`                 精确实现 / 插件版本与摘要，平台内部可见

  `compatibility`                     SDK / 宿主版本范围、停用与迁移规则
  ------------------------------------------------------------------------------------

能力描述符不直接接受任意远程 Schema URL。依赖 Schema
在注册时解析、验证并打包，避免运行时外连、依赖漂移和循环解析。

### 3.3 一个完整方向的描述符示例

以下为 JSON 示例；Schema 引用代表拟登记资源，不是现存文件。

``` json
{
  "capabilityId": "titanloom.data.pipeline.run",
  "contractVersion": "1.0.0",
  "ownerModule": "data",
  "ownerTeamRef": "platform-data",
  "titleKey": "capability.data.pipeline.run.title",
  "descriptionKey": "capability.data.pipeline.run.description",
  "publicationState": "active",
  "operationKind": "business_write",
  "impactLevel": "medium",
  "effectModel": "staged_publish",
  "inputSchema": "schema:titanloom.data.pipeline.run.input:1.0.0",
  "outputSchema": "schema:titanloom.data.pipeline.run.output:1.0.0",
  "resourceRequirements": {
    "targetTypes": ["Pipeline"],
    "dependencyResolver": "data.pipeline.authorization.v1"
  },
  "preconditions": ["published_version_exists", "input_scope_authorized"],
  "authorization": {
    "action": "titanloom.data.pipeline.run",
    "agentPolicies": ["deny", "confirm", "allow"],
    "delegationRequiredForAgent": true
  },
  "execution": {
    "mode": "async",
    "budgetClass": "data.batch",
    "cancellation": "cooperative_and_process_termination",
    "retryPolicy": "registered_node_policy"
  },
  "idempotency": {
    "required": true,
    "retentionProfile": "command.standard"
  },
  "confirmation": {"supportsPreview": true},
  "resultVerification": {
    "validatorRef": "data.pipeline.run.verify.v1",
    "evidence": ["pipelineRunId", "inputVersions", "outputRefs", "qualityStatus"]
  },
  "modelDelivery": {"defaultProjection": "status_and_approved_summary"},
  "bindings": {"http": "command_protocol", "cli": "pipelines run"},
  "implementationRef": "builtin:data.pipeline.run:1.0.0",
  "compatibility": {"hostContract": "1.x"}
}
```

### 3.4 Schema 与版本规则

采用 OpenAPI 3.1.1 描述首期 HTTP 接口，JSON Schema 2020-12
描述可复用载荷。这是本规范选定的认证基线，不宣称是最新版本。SDK
从已发布的同一契约包生成，服务端业务校验在 Schema
校验之后执行。\[R1\]\[R2\]

-   命令输入拒绝未知字段、错误类型和未声明的枚举；不静默忽略拼错的参数。
-   OpenAPI、Schema、能力描述符与 SDK 绑定同一不可变发布清单和摘要。CI
    校验服务实现与发布契约一致。
-   外部 HTTP 主版本为 `/api/v1`；单个能力另有精确
    `contractVersion`。两个版本轴不能混用。
-   改变字段含义、单位、权限语义、必要参数或副作用属于破坏性变更；采用新
    major 并提供迁移。
-   新增响应枚举也可能破坏旧客户端，必须验证未知枚举回退，不能一律视作兼容。
-   已准备命令、已发布流程和已排队任务钉住精确版本。停用后不得自动改成
    `latest`。
-   安全禁用优先于版本固定；旧命令停止执行并返回明确错误。
-   新版本扩大权限范围或副作用时必须重新登记授权，不能自动继承旧角色和
    Agent 资格。

### 3.5 注册、启用与依赖停用

领域维护方提交描述符、Schema、固定实现、验证器、权限映射与测试证据；平台核验命名空间和宿主兼容后登记
draft。通过契约与权限验收才能 active；active 仅表示实现可用，Agent
三道门仍默认关闭。

deprecated
表示进入迁移期，已固定版本的获授权使用可在声明窗口内继续；disabled
表示停止新接收并按禁用原因处理中运行任务，安全禁用优先停止后续受限操作和交付；retired
表示不可再执行，仍保留审计与旧运行所需的契约元数据。停用实现或依赖时必须列出受影响的
Skills、流水线与排队命令，禁止静默重绑到其他版本。

## 4. 能力发现与按需上下文

### 4.1 发现流程

  -----------------------------------------------------------------------------------------------------------------------------
  阶段                    接口                                                           返回范围
  ----------------------- -------------------------------------------------------------- --------------------------------------
  搜索概要                `GET /api/v1/capabilities?q=...&limit=...&cursor=...`          当前主体允许获知的
                                                                                         ID、版本、用途、运行限制

  获取详情                `GET /api/v1/capabilities/{capabilityId}/versions/{version}`   获授权的输入输出
                                                                                         Schema、错误、示例和约束

  解析资源                所属模块的受控资源查找接口                                     当前范围可见的稳定资源 ID 与必要元数据

  准备执行                第 6 节命令接口或第 9 节 Query 接口                            基于实际资源再次授权，不信任目录缓存
  -----------------------------------------------------------------------------------------------------------------------------

发现权限与执行权限分开：可见能力可能因未指定目标、缺少确认或业务状态不允许而不可执行。目录只显示调用者有权知道的限制原因；对无权知道的能力、资源名称及数量不提供存在性线索。

通用输入类型不包含业务数据，也仍受目录权限控制；实际表结构、字段名、样本、文件名和目标列表另做资源与模型输入检查。不能为了让模型选工具，提前把全部业务
Schema 放入上下文。

首期使用受权限约束的关键词、标签和业务域搜索，不强制引入向量数据库。排序或语义检索以后可以替换，不影响执行授权。

### 4.2 缓存与 Token 预算

只预加载少量能力域摘要；详细能力和 Skill 按任务读取。目录缓存按主体 /
委托、运行端类别、工作空间、可见性策略版本和目录版本隔离；业务资源
Schema 缓存另绑定资源及数据版本。ETag / 304 之前仍验证当前可见性。

当目录、策略或模型输入规则变化，下一次模型调用重新筛选上下文。按需加载减少冗余，不保证固定的
Token 节省比例。

## 5. 身份、委托与三道门执行

### 5.1 三类调用路径

  ---------------------------------------------------------------------------------------------------------
  调用者                  身份来源                 执行约束
  ----------------------- ------------------------ --------------------------------------------------------
  人工网页 / 人工 CLI     平台登录，按部署接企业   基础权限、资源和运行条件；高影响操作按业务规则确认
                          OIDC                     

  交互式 Agent            已登记运行端 +           用户当前权限与委托范围求交，再叠加三道门和模型输入限制
                          用户显式委托             

  无人值守 Agent          已登记运行端 +           不保存个人登录令牌；仍完整执行三道门
                          有责任人的服务委托       

  独立固定自动化          经人工发布的固定任务 +   固定输入范围和用途；被 Agent 触发时仍带该次 Agent
                          专用服务身份             来源与委托
  ---------------------------------------------------------------------------------------------------------

内置 Agent 与外部 Agent 使用相同权限语义。平台不允许凭 `User-Agent`、CLI
名称或客户端传入 `actorType=human` 判定人工身份。

### 5.2 可信调用上下文

服务端认证后构建不可由模型篡改的 `InvocationContext`：

  --------------------------------------------------------------------------------
  字段                                来源
  ----------------------------------- --------------------------------------------
  `principalId`                       被验证的授权主体

  `executorId` / `runtimeId`          注册运行端及当前执行实例

  `invocationType`                    已验证的会话 / 凭证种类及注册信息

  `delegationId` /                    平台委托记录
  `delegationVersion`                 

  `workspaceId` /                     主体与资源归属共同解析
  `effectiveProjectScope`             

  `audience` / `expiresAt`            验证后的目标服务与有效期

  `agentTaskId` /                     受权限校验的任务关联，不只是客户端日志标签
  `parentInvocationId`                

  `modelBoundaryRef`                  该运行端登记并获批的模型服务 / 部署边界

  `policyVersionSet`                  本次实际使用的各级策略版本

  `requestId` / `traceId`             服务端生成或验证后的关联标识
  --------------------------------------------------------------------------------

请求可携带工作空间、项目、任务等选择器，但服务端必须验证关系；选择器不能成为授权证据。模型名称由客户端自报不产生数据发送许可。

### 5.3 凭证与委托规则

-   凭证由认证组件持有并附加，原始用户登录令牌、数据源密钥不得出现在模型可见参数、Skills、普通日志或
    CLI 输出中。
-   交互式 CLI
    登录通过受控浏览器流程完成，避免输入密码到命令行；如支持设备授权流，先完成企业身份服务兼容验收。
-   Agent
    获得的只能是短期受限调用能力；必要时采用代理附加凭证，避免给不可信脚本直接读取凭证的能力。
-   委托记录固定能力范围、资源范围、用途、责任人、有效期、预算、允许的模型边界及状态；Agent
    不能创建或修改自身扩权委托。
-   下游服务需要凭证时，由可信基础设施交换 /
    签发适合目标服务的短期凭证，并缩小范围；不把上游令牌无差别透传。RFC
    8693
    可作为对接现有身份系统的标准参考，但不要求首期新建完整身份产品。\[R3\]
-   默认禁止向外部 Agent
    再委托；以后开放须另行设计深度、范围收窄、责任链和撤权传播。
-   第三方运行端如果可任意读取人工登录凭证，就不能宣称平台可靠区分它与人工。认证接入验收必须验证凭证隔离和注册绑定，而不只检查请求字段。

### 5.4 服务端裁决顺序

1.  做请求大小、格式和速率预检，验证身份、运行端、委托和目标服务。
2.  解析目标资源的权威归属与实际依赖，验证任务关联；仅访问授权所需的受控元数据。
3.  检查基础 ACL、Agent 平台资格、范围启用、资源准入及来源血缘限制。
4.  检查数据行列范围、资产关联、输入约束和模型可见范围。
5.  检查业务状态、精确版本、确认要求、锁 / 租约和资源预算。
6.  进入事务或持久任务接收边界；执行点重新校验关键授权与版本。
7.  返回结果、读取缓存、下载产物和向模型交付时再验证相应权限。

三道门只收窄，不扩大基础权限；Agent
自身权限管理入口保持人工控制。未获资源准入时不先取明细再过滤。首期没有可靠字段血缘时按结果整体依赖从严处理，不等待字段级血缘完成才实施来源限制。

### 5.5 撤权与执行边界

撤权更新策略版本，终止后续受限调用；任务排队后执行前重新鉴权，运行中在检查点核验，结果交付再核验。新的
Agent 工作不能通过复制 Job、人工缓存、导出文件或 Player 身份绕过限制。

同库权限记录与业务提交采用可验证的版本检查及事务协调，界定撤权与提交的先后；跨服务使用明确的短期授权与最大陈旧期限。已经提交的业务事实不因撤权自动回滚，必要补偿属于新业务操作。运行前核验通过不等于获得长期永久许可。

## 6. 业务命令、影响预览与人工确认

### 6.1 准备与提交分开

首期对业务写入和控制动作采用统一两阶段命令协议；只读查询走第 9
节独立通路。准备阶段允许写命令记录、审计和预算内的预览任务，不产生目标业务写入、不提前占用业务锁。

  -----------------------------------------------------------------------------------------------------------
  HTTP 接口                                                      用途
  -------------------------------------------------------------- --------------------------------------------
  `POST /api/v1/capability-commands`                             验证并准备命令，返回影响预览及是否需要确认

  `GET /api/v1/capability-commands/{commandId}`                  获取有权访问的命令状态和执行引用

  `POST /api/v1/capability-commands/{commandId}/confirmations`   经验证的人工会话确认该具体命令

  `POST /api/v1/capability-commands/{commandId}/submit`          提交同一命令，产生至多一个逻辑执行接收记录

  `POST /api/v1/capability-commands/{commandId}/cancel`          取消尚未接受的命令；已接受则按 Job /
                                                                 业务取消流程处理
  -----------------------------------------------------------------------------------------------------------

两阶段设计主要用于固定授权与幂等语义。对无需确认的操作，SDK / CLI
可以自动连续准备和提交，用户不必手工操作两次。`--dry-run`
只准备，不提交。

``` json
{
  "capabilityId": "titanloom.data.pipeline.run",
  "contractVersion": "1.0.0",
  "workspaceId": "ws_ops",
  "projectId": "bp_efficiency",
  "target": {"type": "Pipeline", "id": "pl_hours"},
  "expectedResourceVersion": "17",
  "input": {
    "publishedVersion": "7",
    "period": {"startDate": "2026-09-01", "endDateExclusive": "2026-10-01"},
    "businessTimeZone": "Asia/Shanghai"
  },
  "agentTaskId": "at_123",
  "clientRequestId": "client_456"
}
```

认证凭证通过传输层认证组件处理，不出现在上述业务 JSON
中。所有创建命令请求必须带 `Idempotency-Key`；`clientRequestId`
只用于关联，不能代替幂等键。

### 6.2 准备结果

``` json
{
  "requestId": "req_001",
  "data": {
    "commandId": "cmd_001",
    "state": "awaiting_confirmation",
    "capabilityId": "titanloom.data.pipeline.run",
    "contractVersion": "1.0.0",
    "commandDigest": "sha256:example-command-digest",
    "expiresAt": "2026-09-26T09:40:00Z",
    "effectivePolicy": "confirm",
    "preview": {
      "messageKey": "dataproc.pipelineRun.preview",
      "messageParams": {"pipelineVersion": "7", "period": "2026-09"},
      "effectScope": "registered_pipeline_outputs",
      "estimateStatus": "bounded_estimate"
    },
    "confirmation": {
      "required": true,
      "interactionRef": "confirm_ui_001"
    }
  }
}
```

示例 ID
和摘要均为占位值，不可作为真实凭证或摘要使用。预览必须区分精确影响与估计；返回的名称、数量、样本仍受权限控制。无法描述高影响操作的资源范围时拒绝自动执行。

### 6.3 规范化、版本和目标固定

服务端按精确 Schema
解析类型，补齐显式默认值，固定业务时区、目标和输入版本，并使用版本化规范化算法产生摘要。摘要覆盖能力与契约、目标、前置版本、参数、输入依赖版本、影响范围、委托绑定和有业务效果的导出配置。传输
requestId、显示语言和确认记录本身不进入业务摘要；如果语言决定导出内容，则其作为业务参数进入摘要。

不能把
`latest`、模糊名称、动态查询目标集合直接留在待确认命令中。对于批量修改：固定目标集合
/
快照及上限；数据变化后重新准备。对于数据计算：固定来源水位或输入版本；无法固定时必须明确支持何种变化，禁止把"昨日数据"解释成随重试漂移的范围。

`expectedResourceVersion`
用于可变目标的并发校验；不可变目标用精确版本引用，契约明确二者的适用条件。需要页锁、导播租约的能力在提交边界验证有效锁，并校验资源版本，不能用版本检查代替现场互斥。

### 6.4 确认不是扩大授权

确认人必须有相应操作资格；平台在独立受控界面显示实际目标、影响、版本和规范化参数。确认记录绑定
commandId、摘要、确认人、授权主体与委托、有效期及一次性消费状态。Agent
不能确认自己，普通聊天文字"同意"不能直接生成有效确认。

策略、参数、版本或目标发生实质变化时重新准备并重新确认。确认不能绕过审批资格、发布门槛、On-air
限制或资源权限。可视化发布 / Take 首期仍不因本协议而开放给 Agent。

异步任务在接收事务中将确认记录一次性绑定到执行实例；等待入队不重复消费。实际产生副作用前仍核验确认所允许的执行期限和绑定内容；期限已过且未执行时不启动新副作用，返回需重新准备的结果。对同一次有效启动后的允许恢复，沿用原执行绑定和恢复规则，不把"一次性"错误实现为每次底层重试都要新确认。

### 6.5 命令状态

  -----------------------------------------------------------------------------------------------
  状态                      含义                                     允许的后续变化
  ------------------------- ---------------------------------------- ----------------------------
  `prepared`                持久记录已建立，预览或授权准备尚未完成   awaiting_confirmation /
                                                                     ready / canceled / expired

  `awaiting_confirmation`   其他检查通过，等待具体人工确认           ready / canceled / expired

  `ready`                   满足提交前条件；仍须执行点重查           accepted / canceled /
                                                                     expired

  `accepted`                已事务性接收并绑定执行 / 同步结果        接收事实终态，执行结果另查

  `canceled`                尚未接收即被取消，或准备被终止           终态；另建新命令

  `expired`                 未接收即超过有效期                       终态；另建新命令
  -----------------------------------------------------------------------------------------------

`prepared` 仅用于需要持久预览任务的能力；普通准备可直接返回 ready 或
awaiting_confirmation。首次授权失败返回错误并审计，不制造可提交命令。准备过程中失败则取消命令并记录原因。政策收紧使
ready 不再有效时，提交被拒绝，必要时取消或转回 awaiting_confirmation
并重新生成有效预览。

### 6.6 异步接收回执

提交返回 HTTP
202，并包含下面的结构。状态地址是受控资源路径，每次读取都重新鉴权；不能把
URL 持有者自动视为获授权主体。

``` json
{
  "requestId": "req_004",
  "data": {
    "commandId": "cmd_001",
    "commandState": "accepted",
    "invocationId": "inv_001",
    "jobId": "job_001",
    "jobState": "queued",
    "domainRunRef": {"type": "PipelineRun", "id": "pr_001"},
    "statusPath": "/api/v1/jobs/job_001",
    "businessOutcome": "pending"
  }
}
```

短同步操作返回 HTTP 200 和已验证结果；响应丢失后同样查原 commandId。API
已接收、后台计算完成、质量通过、正式发布分别是不同事实，回执只声明已知事实。

## 7. 幂等、事务和不确定结果

### 7.1 两层去重

**请求幂等**处理网络重试；**业务唯一性**处理用户重复表达同一业务动作。相同
Excel
内容哈希不一定意味着同一业务导入，需结合来源、期间、导入模式和映射版本判定；不能全局按文件哈希禁止所有再次导入。

准备命令的幂等作用域为
`workspaceId + principalId + delegationId（人工为空）+ capabilityId + contractMajor + Idempotency-Key`。唯一约束覆盖作用域，规范化请求摘要用于比较；执行实例或客户端副本
ID 不进入作用域，以允许故障转移后的同一请求重试。

实现上分开保存 `requestDigest` 和
`commandDigest`：前者按该契约固定规则规范化调用者提交的业务请求，用于识别重复；后者包含服务端首次解析并固定的目标、默认值与输入版本，用于确认和执行。遇到已存在的幂等键时先比较
requestDigest
并校验读取权限，再返回原命令，不重新按当前数据解析默认值而产生另一个执行意图。

-   同键同摘要返回原 commandId，不重建命令。
-   同键不同摘要返回 `IDEMPOTENCY_CONFLICT`，不覆盖旧命令。
-   `/submit` 以 commandId 为稳定接收键；并发提交必须事务性返回同一
    invocationId / jobId。
-   查询旧命令结果仍重新鉴权；幂等缓存不能绕过撤权。
-   已终结 / 过期命令不能被重试复活；新意图须明确创建新命令。
-   幂等记录保留期覆盖客户端重试、队列和恢复窗口。清理后保留有界
    tombstone /
    摘要索引；超出保证期拒绝旧操作的盲目重放，使用业务对账确认是否需要新命令。

### 7.2 接收与执行事务

异步提交在一个 PostgreSQL 事务中完成：锁定命令 → 校验最新状态与权限 →
原子绑定 / 消费确认 → 创建 Invocation、JobRun 和领域运行引用 → 写 outbox
→ 标记 accepted → 提交。任何一步失败不产生半接收记录。

最小部署可直接以持久 JobRun 为待领取源；标准部署由 outbox
发布消息。两者都通过唯一执行关联防止重复创建。Broker / Celery
只运输和调度，不拥有权威业务状态。

短同步写入在同一事务完成业务变更、幂等接收、结果记录和必要事件。外部系统写入不能假装与本库事务原子提交：登记外部操作
ID，使用对端幂等与对账；无对端保障时不自动重试不确定写入。

### 7.3 失败不等于未发生

  ----------------------------------------------------------------------------------------
  情况                                调用方行为
  ----------------------------------- ----------------------------------------------------
  收到 202                            已接收，保存 commandId / invocationId /
                                      jobId；不能报告业务成功

  submit 超时 / 连接断开              查询原 commandId，必要时重试同一
                                      submit；不换键重新提交

  任务运行中 Worker 失联              服务端恢复 / 对账；客户端不新建同一业务运行

  对端已写入但返回丢失                标记 reconciling，按对端操作 ID 查证

  确认未产生副作用且可重试            在预算内重试，记录同 JobRun 下新的 attempt

  无法证明成功或失败                  保持待核对，显示人工处理入口，不编造成功或自动重做
  ----------------------------------------------------------------------------------------

本设计提供"同一逻辑请求的去重接收 +
可恢复执行"，不承诺跨外部系统的恰好一次执行。

## 8. JobRun、恢复与取消

### 8.1 运行对象分离

  ----------------------------------------------------------------------------------------------
  对象                    事实所有者              关系与含义
  ----------------------- ----------------------- ----------------------------------------------
  AgentTask               智能管家                一个用户目标，可关联多个命令、审批和运行

  CapabilityCommand       公共命令服务            一份固定业务意图及准备、确认、接收状态

  Invocation              公共调用记录            一次被接收的能力调用；包含验证结论和运行引用

  JobRun                  公共任务服务            一次后台逻辑任务；可包含多个执行尝试

  JobAttempt              公共任务服务            一次具体领取与执行，绑定 Worker、租约和
                                                  fencing token

  PipelineRun             数据处理                DAG
                                                  节点依赖、输入输出版本、质量、发布与恢复事实

  WorkflowInstance        表单平台              审批人、业务状态和决定；等待审批不占用 Worker
  ----------------------------------------------------------------------------------------------

PipelineRun 可以关联一个根 JobRun 和多个节点
JobRun，聚合规则由数据模块维护。单个 JobRun
成功不等于整条流水线发布成功。本规范据总框架第 6.5
节明确领域所有权；数据处理第 15 节也明确两类状态分别维护。

### 8.2 JobRun 最小公共字段

`jobId`、`invocationId`、`commandId`、`jobType`、`ownerModule`、`domainRunRef`、`state`、`stateVersion`、`progress`、`attemptCount`、`inputRefs`、`implementationVersion`、`authorizationContextRef`、`budgetSnapshot`、`queueDeadlineAt`、`runDeadlineAt`、`createdAt`、`startedAt`、`finishedAt`、`outputRefs`、`effectStatus`、`error`。

授权上下文保存主体、委托和范围引用及提交时证据，不保存用于永久放行的过期权限快照。每次尝试均使用当前授权；固定输入
/ 实现版本不能随重试变更。

进度支持 `completedUnits`、`totalUnits`、`unit` 和可空
`percent`。未知总量时返回不确定进度，不捏造百分比。日志、错误和产物引用均有独立交付权限。

### 8.3 JobRun 状态与迁移

  ------------------------------------------------------------------------------------------
  状态                    含义                                       主要后续状态
  ----------------------- ------------------------------------------ -----------------------
  `queued`                已持久接收，等待资源                       running / canceled /
                                                                     timed_out / failed

  `running`               有有效执行租约                             succeeded / failed /
                                                                     retry_wait /
                                                                     cancel_requested /
                                                                     reconciling / timed_out

  `retry_wait`            已判定可重试，等待退避                     queued / canceled /
                                                                     timed_out / failed

  `cancel_requested`      已收到取消，等待执行端停止或确认提交结果   canceled / succeeded /
                                                                     failed / reconciling /
                                                                     timed_out

  `reconciling`           执行状态或外部副作用不确定                 succeeded / failed /
                                                                     canceled / retry_wait /
                                                                     timed_out

  `succeeded`             按任务契约完成并取得成功证据               终态

  `failed`                已知失败，记录已发生的副作用与恢复建议     终态

  `canceled`              确认停止，不再产生后续副作用               终态

  `timed_out`             达到平台任务期限，且已确认停止             终态
  ------------------------------------------------------------------------------------------

终态 JobRun 不复活；业务发起重新运行时创建新 JobRun，并记录
`retryOfJobId`
或领域恢复关联。自动尝试重试在进入终态前完成。失联时不能仅凭超时把未知外部副作用写成
canceled / timed_out；先进入 reconciling，超出核对窗口时标记
`manualReviewRequired` 并停止自动推进。

`effectStatus` 取 `none` / `committed` / `partial` /
`unknown`。任务失败或取消可以已有部分提交，必须明确显示已处理项；unknown
留在 reconciling，不能仅为结束 UI
而伪装成失败无影响。补偿是新的受控操作，不是把状态文字改回去。

### 8.4 领取与恢复

最小 Runner 以 PostgreSQL 持久记录领取任务，使用事务行锁 /
条件更新、租约和心跳；标准 Celery 消息只携带 jobId
等受控引用，两种实现执行同一领取协议。

每次领取生成单调递增的 fencing token。旧 Worker
丢失租约后，其状态更新和平台内部提交必须被拒绝。外部系统不支持 fencing
时，需要业务幂等键和对账，不能声称数据库租约能阻止已经发出的外部请求。

运行记录至少区分"入队次数"和"执行尝试次数"。outbox 重发、Broker
重投不会自动创建新任务。恢复时先确认先前尝试的提交状态和检查点，再决定重试范围；不机械重跑所有下游已完成节点。

### 8.5 取消与资源回收

`POST /api/v1/jobs/{jobId}/cancel`
经授权后返回取消请求的接收状态，默认重复请求幂等。取消需校验对应领域操作权限，不能因为有查看权限就取消任务。

-   未运行：禁止领取，转 canceled，释放排队额度。
-   运行中：设置
    cancel_requested，在检查点停止；必要时终止隔离进程、取消数据库查询。
-   原子提交已完成：返回真实结果，可为 succeeded，并注明取消晚于提交。
-   外部写入结果不确定：进入 reconciling。
-   临时文件清理先检查引用和运行占用；失败记账重试，不能删除共享检查点或正式资产。

取消控制作为停止既有任务的独立能力处理：原 Agent 委托失效后，Agent
不能获得额外权限，但平台撤权处理器应主动停止受限任务；有权人工仍可通过管理入口取消。

### 8.6 状态获取与推送

首期权威通路为 `GET /api/v1/jobs/{jobId}`，支持 `ETag`、`Retry-After`
和有界轮询；已有 WebSocket 通道可推送 `jobId + stateVersion`
变化通知，客户端收到后按需查权威状态。

订阅、重新订阅和交付均鉴权。推送丢失不丢业务事实；断线重连后查询当前状态，不按通知数量累加完成条数。服务端终止被撤权订阅，不能只等浏览器自行取消。

### 8.7 成功验证

每个能力在注册时绑定固定验证器与证据
Schema。同步操作在事务结果明确后验证；异步操作在领域模块完成后生成证据，再更新调用结果。证据至少包含
`validatorVersion`、`verifiedAt`、输入 /
输出版本、领域运行引用和可观察的业务结果；获准摘要另按模型交付规则生成。

JobRun 的 succeeded
表示它自己声明的工作已完成。若该任务只是"计算中间表"，不能据此推出
Dataset 已发布。`pipeline.run` 的 Invocation 结果必须结合 PipelineRun
的质量和发布结果；验证器暂时不可用时保持结果待验证，不让模型通过日志文字自行认定成功。验证读取也有受控权限，验证器不能借此把额外明细泄露到结果证据中。

## 9. 查询、文件与模型数据出口

### 9.1 Query 通路

`POST /api/v1/queries/{queryId}/execute` 映射
`titanloom.data.query.execute`，读取已发布 Query。请求固定
queryVersion、参数、分页或聚合要求；目标
Dataset、字段、过滤和执行计划由数据处理服务解析，不允许调用者提交任意底层连接或
SQL 替换正式 Query。

``` json
{
  "contractVersion": "1.0.0",
  "queryVersion": "4",
  "parameters": {"month": "2026-09"},
  "filters": [{"field": "fld_department", "op": "in", "values": ["dept_05"]}],
  "page": {"limit": 100, "cursor": null},
  "consistency": {"mode": "snapshot", "snapshotId": "snap_hours_202609"}
}
```

``` json
{
  "requestId": "req_002",
  "data": {
    "queryId": "q_hours",
    "queryVersion": "4",
    "datasetVersion": "32",
    "dataGeneration": 57,
    "snapshotId": "snap_hours_202609",
    "sourceWatermarks": [{"sourceId": "src_hours", "version": "batch_88"}],
    "dataAsOf": "2026-09-26T09:00:00Z",
    "qualityStatus": "passed",
    "columns": [
      {"name": "employeeId", "type": "string", "fieldRef": "fld_employee"},
      {"name": "hours", "type": "decimal", "scale": 2, "encoding": "string"}
    ],
    "rows": [{"employeeId": "000123", "hours": "168.50"}],
    "nextCursor": null,
    "truncated": false
  }
}
```

这是获准交付后的结果示例，不表示任意 Agent 可见工号或工时。Query
执行成功也可以带质量告警或新鲜度不足；客户端必须展示声明状态，不把 HTTP
200 当作指标已认证。

筛选按 FieldRef 经 `filters` 传入，只能使用该 Query 已声明为可筛选的 FieldRef，操作为
`eq`、`in`、`range`（左闭右开）、`relative`（由服务端按业务时区解析）、`search` 或
`hierarchy`；未声明的筛选返回参数错误，不静默忽略。`parameters` 只承载 Query
声明的其他参数。响应的 `dataGeneration` 是所读 Dataset 的数据代次，列上的
`fieldRef` 标明该列绑定的字段标识；两者的定义见数据处理子方案 12.6（拟定）。

### 9.2 一致性、精度与查询预算

-   `snapshot`
    模式要求固定快照，或由服务建立有期限的稳定读取版本；暂不支持时返回明确错误，不能悄悄降成
    live。
-   `live`
    模式允许页间数据变化，必须明确标识，不用于要求严格可重复的全量导出。
-   Cursor 必须绑定 Query /
    参数摘要、排序、快照、主体权限上下文和有效期，服务端校验；Cursor
    不是授权票据。
-   行列过滤在读取和聚合前实施；总行数、聚合和分组结果也可能泄露数据，需要同样约束。
-   超大查询不自动变为无限任务。仅契约声明 adaptive 时，可返回 Query
    Job；否则 `QUERY_BUDGET_EXCEEDED` 并提示缩小范围或使用专门导出能力。
-   精确十进制与超出 JS 安全整数范围的数据采用明确字符串编码；ID
    作为不透明字符串处理；不沿用草案中"所有数值都 numeric"的过宽表述。
-   日期型、本地排班时间与 UTC
    时间戳分别建模；业务时区固定，显示时区不改变业务期间。

### 9.3 数据不必经过模型

模型可获准启动计算但仅接收状态、质量结论和汇总。流水线输入、表格全量、二进制和中间数据由服务与
Worker 传递；不先送入模型再要求模型少展示。

内部 Agent 的服务结果在送入模型前经过 Model Delivery Guard。外部 Agent
的 API / CLI 返回本身就是潜在模型出口，因此默认执行 Agent
投影与模型边界检查；`--json`、`--raw`、导出或错误日志都不能旁路。

服务端只返回模型可见的结构化摘要和获准引用。仅有人工下载权限的文件可以发送到人工受控界面，不能把短期下载地址回传给
Agent。对外部运行端的数据边界承诺依赖受信运行端与部署治理；凭客户端声称"不会外传"不能获得额外数据。

### 9.4 文件与 Asset

上传、分片、校验、扫描、下载和预览沿用 Asset 服务。命令参数引用
`assetId + version`，不传服务器任意路径；资产就绪前不能作为正式处理输入。失败行报告、快照和导出也登记为受控产物，继承来源限制。

大文件二进制走资产通路，能力调用只返回必要元数据与引用。短期访问授权必须绑定操作、主体或受控会话、用途及有效期；不能把长期公共
URL 作为权限系统。签名 URL
在有效期内可能被转发，强撤权要求使用可在线校验的资产代理或等价机制，不能宣称已签发
URL 必然即时失效。

### 9.5 全局搜索提供方

全局搜索（Shell 9.7）不直接读各模块的表。每个模块实现 SearchProvider（契约 search-provider.schema.json）：

-   **登记**：哪些对象类型可被搜到（所属分组、名称文案键）、哪些操作可从搜索直接发起（文案键、站内路由、关键词、需要的功能或能力）；敏感字段不得进入索引。
-   **索引**：对象新建、改名、删除、换权限时发 outbox 事件，后台轻道几秒内更新 `search.search_doc`（契约 search-doc.schema.json），每晚全量对账；索引只存名称、别名、拼音与不超过 500 字的摘要，不是任何数据的正本，可由各模块重建。
-   **复核**：每个提供方提供 `check_visible` 能力；查询先按归属范围过滤，打分后前 50 条交所属模块复核，不返回被过滤的数量。点击结果和发起操作照常走第 5 节裁决。
-   **替换**：首期实现为 PostgreSQL（《后端详细设计 · 总图》9）；将来换专门搜索程序时 SearchProvider 与查询接口不变。语义检索沿用知识方案的 RetrievalProvider，首期不接入全局搜索。

## 10. API / SDK / CLI 接入约定

### 10.1 HTTP 与 SDK

  --------------------------------------------------------------------------------------------
  规则                                设计
  ----------------------------------- --------------------------------------------------------
  传输                                正式环境 HTTPS；同进程调用共享受控模块接口，不绕行 HTTP

  认证                                企业 OIDC / 平台身份接入；Cookie 会话的写请求实施 CSRF
                                      防护

  内容                                JSON 默认；上传下载与推送按各自通路

  成功响应                            `requestId + data`，可含受控 `warnings` / `meta`

  异步接收                            202 + invocationId / jobId / domainRunRef；提供状态地址

  错误响应                            第 12 节统一格式，不强制全部返回 HTTP 200

  分页                                有界 limit + 不透明 cursor，禁止默认全量

  超时                                网络调用期限与 Job 执行期限分离；断开连接不等于取消任务

  SDK 重试                            仅依错误恢复类别与幂等规则重试，写操作不自动更换幂等键

  URL 安全                            服务端返回的资源引用由 SDK 解析至批准服务；不执行任意
                                      URL / 命令
  --------------------------------------------------------------------------------------------

Python SDK 服务于内置 Agent 和平台脚本，TypeScript SDK
服务于门户及接入客户端。两者从同一 OpenAPI
契约生成传输层，再提供薄业务辅助层；类型提示不替代服务端验证。

### 10.2 一个统一 CLI

CLI 使用 `titanloom` 名称，首期以 Python 包实现，复用生成的 Python
SDK；符合现有 Python 基线，不额外引入常驻 Node
服务。交付经过企业批准的锁定依赖包 / 离线安装包，操作系统凭据存储适配在
Windows 与 Linux 分别验收。

  命令组                首期能力
  --------------------- --------------------------------------------------------
  `titanloom auth`           人工登录、登出、会话检查；Agent 执行入口不暴露人工凭证
  `titanloom capabilities`   search / describe
  `titanloom queries`        execute
  `titanloom pipelines`      run 已发布版本
  `titanloom commands`       inspect / submit / cancel 未接受命令
  `titanloom jobs`           get / wait / cancel
  `titanloom assets`         受权上传、查看产物；下载按人工 / Agent 权限分别处理
  `titanloom skills`         查看匹配版本与安装包信息，不运行任意在线安装脚本

推荐机器调用示例：

``` bash
titanloom capabilities search --query pipeline --format json
titanloom capabilities describe titanloom.data.pipeline.run --version 1.0.0 --format json
titanloom pipelines run --request-file run-request.json --dry-run --format json
titanloom commands submit cmd_001 --format json
titanloom jobs get job_001 --format json
titanloom jobs wait job_001 --timeout 60 --format json
```

`run-request.json` 对应第 6.1 节业务请求。生产使用时由 SDK / CLI
生成并持久保留该操作的幂等键和
commandId；上述命令只是调用设计示例，不代表客户端已安装。

### 10.3 CLI 机器可读行为

-   `--format json` 的 stdout 只输出一个 JSON 结果；日志与诊断写
    stderr，不混入进度条、颜色和欢迎语。
-   大输入采用 `--request-file` 或 stdin；不要把复杂 JSON、密钥或长 SQL
    拼进 Shell 命令。
-   CLI 不提供通用远程 `shell` / `eval` /
    任意数据库连接功能。运行已发布脚本使用工具中心能力和隔离 Worker。
-   `--dry-run`
    输出真实服务端预览，不能由本地猜测权限；预览仍受预算与数据访问约束。
-   非交互模式遇到确认要求返回 commandId
    和受控确认引用，不挂起等待终端输入，不提供 `--yes` 绕过权限确认。
-   人工确认在平台受控界面完成；`commands submit`
    只能提交已有有效确认或无需确认的命令。
-   网络失败后从本地操作记录恢复；本地记录只存必要 ID
    和状态，不存未加密令牌、原始明细或长期下载链接。
-   `jobs wait` 超时只停止等待，输出 `WAIT_TIMEOUT` 和
    jobId；不取消远端任务。`WAIT_TIMEOUT` 是 CLI 本地结果码，不是服务端错误码，不进入第 12 节错误分类与错误码注册表。Ctrl+C 默认同样只停止等待，取消需显式命令。
-   Agent 场景下禁止交互式登录回退成人工身份。会话过期返回
    `AUTHENTICATION_REQUIRED`，由受控授权流程恢复。

  退出码   含义
  -------- ---------------------------------------------------------
  0        当前 CLI 请求成功；202 受理仍可能返回 0，必须看响应状态
  2        本地参数 / 请求格式错误
  3        身份或授权失败
  4        需要人工确认
  5        状态、版本或幂等冲突
  6        等待超时 / 暂时不可用，附恢复类别
  7        已知远端任务失败或被取消
  8        执行结果待核对，禁止盲目重试

退出码只供脚本粗分类，不能替代结构化 error code 和 Job 状态；SDK / CLI
不解析本地化错误文字做业务判断。

### 10.4 接入端认证等级

内置 Agent 使用受控运行端；企业受管外部 CLI / GUI
可以按同一委托接入；不受管第三方 Agent
初期仅开放经审批的最小能力和数据投影。每个运行端登记维护方、版本、模型边界、网络出口与凭证隔离证据。

协议适配器收到调用时必须能够建立可信
InvocationContext。无法保留主体、执行者和委托关系的适配器不开放正式写入，不能用管理员服务账号代替所有调用者。

## 11. Skills 设计与发布

### 11.1 场景组织

Skill 按业务任务组织，优先复用能力目录，不为每个 API 创建一份重复说明。

  ------------------------------------------------------------------------------------------------------------
  Skill 名称                    场景                               主要依赖
  ----------------------------- ---------------------------------- -------------------------------------------
  `titanloom-capability-discovery`   查找合适能力与参数契约             能力目录

  `titanloom-query-analysis`         查询已发布数据并解释质量 / 新鲜度  Query、受控模型摘要

  `titanloom-pipeline-operation`     准备、触发、跟踪已发布流水线       命令协议、JobRun、PipelineRun

  `titanloom-import-inspection`      检查外来文件、导入草稿与错误报告   Asset、数据导入契约；待对应能力完成后启用
  ------------------------------------------------------------------------------------------------------------

首期前三个 Skill 随核心能力闭环交付；第四个按数据模块实现进度增加。Skill
存在不表示其依赖能力已经上线。

### 11.2 包格式与内容

使用 Agent Skills 的 `SKILL.md + references / scripts / assets`
组织形式，先加载简介，任务匹配后读取详细指引。`allowed-tools`
在公开规范中属于实验性字段，Titanloom 不把它当成服务端授权。\[R4\]

每个 Skill
的正文必须包含：适用目标、前置条件、能力发现方式、输入准备、确认条件、执行顺序、超时恢复、成功证据、错误分支和模型数据范围。附加平台清单维护
skillId、精确版本、内容摘要、批准发布者、依赖 capabilityId /
版本范围、适配 SDK / CLI 版本及语言版本。

本规范只定义 Skill 设计与交付要求，不创建或安装实际个人技能。

**`titanloom-pipeline-operation` 正文的核心规则：**

1.  先发现可用能力并核对所需契约版本，查找用户有权访问的已发布流水线。
2.  固定目标、期间、输入版本和业务时区；缺少会改变业务结果的参数时先澄清。
3.  准备命令，展示服务端影响预览。需要确认时等待受控确认，不能替用户确认。
4.  提交原 commandId；网络失败查询原命令，不创建新的等价写操作。
5.  跟踪 JobRun 和 PipelineRun；成功以验证后的领域结果与质量状态为准。
6.  对模型仅交付允许的摘要；错误报告和原始附件走受控引用。
7.  待核对、部分失败或质量阻断时如实报告，停止自动重复执行。

### 11.3 版本、可信来源与国际化

Skills
经审查、签名或受控发布清单分发；内容和附带脚本固定摘要。接入端验证发布者与依赖版本，不能因文件写着"官方"就信任。附带脚本按运行端隔离策略执行，禁止下载后直接使用生产凭据运行。

首期 zh-CN / en-US 使用同一能力 ID
和机器字段；说明和示例可以翻译，业务规则不维护两套。确认界面关键文案由平台受控模板生成，不允许
Skill
或插件覆盖。缺失翻译按声明回退，关键确认内容缺失时阻止该语言版本发布。

Skills
版本固定并不强制暴露所有依赖能力：运行时仍需按当前权限发现。受限资源信息不写入可公开分发的
Skill 包。

## 12. 统一错误与恢复语义

### 12.1 错误结构

``` json
{
  "requestId": "req_003",
  "error": {
    "code": "RESOURCE_VERSION_CONFLICT",
    "messageKey": "errors.resourceVersionConflict",
    "messageParams": {},
    "retryable": false,
    "recoveryAction": "refresh_and_prepare",
    "details": {"commandId": "cmd_001"}
  }
}
```

`details` 使用按错误码定义的
Schema，只含当前主体有权看到的信息。内部栈、SQL、路径、凭据、未授权字段名不返回给普通调用端。完整诊断在受限审计系统中按
requestId 关联。

### 12.2 错误分类

  -------------------------------------------------------------------------------------------
  HTTP                    code 示例                      恢复规则
  ----------------------- ------------------------------ ------------------------------------
  400 / 422               INVALID_REQUEST /              修正输入，不自动重试
                          INPUT_VALIDATION_FAILED        

  401                     AUTHENTICATION_REQUIRED /      受控刷新或重新授权，不换成人工身份
                          TOKEN_EXPIRED                  

  403                     ACCESS_DENIED /                停止调用，不寻找旁路
                          DELEGATION_REVOKED             

  404                     RESOURCE_NOT_FOUND             不区分不存在和无存在性知情权

  409                     CONFIRMATION_REQUIRED          完成受控确认后提交原命令

  409                     RESOURCE_VERSION_CONFLICT      重新读取、准备，必要时重新确认

  409                     IDEMPOTENCY_CONFLICT           检查调用意图，不覆盖原键

  409                     CAPABILITY_DISABLED /          停止或显式迁移，不自动改 latest
                          CONTRACT_VERSION_UNSUPPORTED   

  410                     COMMAND_EXPIRED /              查业务事实；必要时新建明确意图
                          RESULT_EXPIRED /               
                          IDEMPOTENCY_WINDOW_EXPIRED     

  413                     PAYLOAD_TOO_LARGE /            缩小请求，改用有界数据或资产通路
                          RESULT_TOO_LARGE               

  422                     QUERY_BUDGET_EXCEEDED          缩小范围或使用获授权异步能力

  429                     RATE_LIMITED /                 按 Retry-After 和剩余总预算退避
                          CAPACITY_EXCEEDED              

  503                     DEPENDENCY_UNAVAILABLE         仅按契约重试；写入不换 commandId

  504                     REQUEST_DEADLINE_EXCEEDED      查原执行记录，不能假定没有副作用
  -------------------------------------------------------------------------------------------

JobRun 读取接口可以返回 HTTP 200 且 `state=failed` /
`reconciling`；这是读取状态成功，不是任务成功。质量阻断、部分完成和下游失败以领域结果表达，不全部归类为网络错误。

所有重试同时受总时长、总次数、预算和幂等约束。`retryable=true`
表示协议允许按指定动作恢复，不是模型可以无上限重新提交。

## 13. 公共持久对象与实现映射

以下为逻辑表建议，工程阶段使用迁移定义精确字段与索引；不要求每个概念独立微服务。

  --------------------------------------------------------------------------------------------------------
  对象 / 表                  核心内容                                 关键约束
  -------------------------- ---------------------------------------- ------------------------------------
  `capability_versions`      描述符、Schema 摘要、实现绑定、状态      capabilityId + contractVersion
                                                                      唯一；版本内容不可变

  `agent_runtimes`           注册运行端、责任方、模型边界、状态       凭证绑定运行端；撤销可追踪

  `delegations`              主体、范围、用途、预算、有效期、版本     人工授权管理；状态更新可使下游失效

  `capability_commands`      固定输入、摘要、目标版本、状态、有效期   幂等作用域唯一；敏感输入加密 /
                                                                      受控存储

  `command_confirmations`    确认人、命令摘要、期限、消费绑定         一个有效消费绑定；确认不等于 ACL

  `capability_invocations`   接收事实、上下文、结果引用、验证结论     一个 commandId 至多一个正式调用接收

  `job_runs` /               状态、租约、心跳、检查点、错误和产物     状态版本 CAS；attempt
  `job_attempts`                                                      fencing；并发领取去重

  `outbox_events` /          可靠通知与投递状态                       eventId 唯一；重投不重复业务变更
  消费去重记录                                                        

  `audit_events`             主体、动作、版本、确认与执行证据         普通业务不可改写；保留与访问有策略

  `skill_versions`           技能包摘要、依赖、语言、发布状态         版本固定；安装不自动授予能力
  --------------------------------------------------------------------------------------------------------

原有三道门、ACL、资源关系、Asset、Dataset / Query、PipelineRun
和审批实例继续由既有模块拥有，不在这些表中复制第二份权限或业务事实。命令摘要用于校验，不能代替恢复所需的受控输入引用。

HTTP
接口、同进程调用和任务执行都通过受控服务入口。防止旁路的工程方式包括明确公共模块
API、限制数据库角色、审查跨模块依赖和契约测试；单靠目录规范不构成访问控制。

## 14. 性能、资源与运行配置

### 14.1 优化优先顺序

1.  限定结果量和模型可见数据，避免全量明细进入浏览器或模型。
2.  SQL / Polars 做确定性批处理；发布任务一次触发，避免模型逐行调工具。
3.  内部复用受控模块调用与连接池；长连接、分页和批处理按负载需要实施。
4.  业务提交、查询、数据计算、构建、媒体使用独立有界预算。
5.  按权限和数据版本缓存；复用计算不复用无权读取的结果。
6.  测量真实瓶颈后再扩充 Worker 或更换引擎，不以接入协议名称推断吞吐。

### 14.2 建议的首期配置起点

以下为待联调验证的工程起点，不是容量承诺；管理员可收紧，放宽须有压测与数据政策依据。共享服务器可用配额尚未落实，不能按物理总内存设置平台额度。

  -----------------------------------------------------------------------------------------------
  配置                    初始建议                   说明
  ----------------------- -------------------------- --------------------------------------------
  能力搜索分页            默认 20、最大 100 项       Schema 详情按需获取

  普通命令 JSON           最大 256 KiB               大参数 / 文件以受控资源引用传递

  Query 页面              默认 100、最大 1,000       行数与字节双重约束，可按 Query 收紧
                          行，同时不超过 2 MiB       

  模型单次结果投影        最多 200 行且 64 KiB       仍受模型 Token 总预算和敏感字段规则限制

  交互查询期限            10 秒起点                  超限取消或显式异步，不阻塞普通业务队列

  普通准备命令有效期      15 分钟                    高影响能力可更短

  确认有效期              最长不超过命令期限         实际执行期限写入确认绑定

  Agent 访问凭证          5 分钟起点                 长任务用受控续签，不能因短令牌过期丢失任务

  授权判定缓存            按人进程内缓存，最长       权限版本号 + 事件失效；高影响能力
                          60 秒陈旧（ADR-027）       执行前不用缓存，直接查库

  Worker 心跳 / 租约      5 秒 / 30 秒起点           独立监管，防止长阻塞任务饿死心跳

  运行中授权检查          最迟每 5                   无法满足的执行器不开放相应敏感任务
                          秒到达检查点，提交前必查   

  Job 状态轮询            2 秒起步、退避至 10 秒     遵守服务端 Retry-After；推送可减少轮询

  同一执行自动重试        默认最多 3                 不可重试操作为 1 次，受总截止时间约束
                          次尝试，指数退避带抖动     

  幂等完整记录            至少 7 天，且不短于任务 /  首次键接受窗口与清理规则见下文
                          恢复窗口                   
  -----------------------------------------------------------------------------------------------

为使旧键清理后的行为可实现，首期 `Idempotency-Key` 采用客户端生成的
UUIDv7：首次未命中记录时仅接受时间戳在过去 24 小时至未来 5
分钟内的键；客户端校准服务端时间。已存在的键按保留记录处理，不重新套首次年龄窗口。记录或
tombstone
清理后，旧键因超过首次接受窗口被拒绝，客户端必须查业务事实，不能自动换新键。保留期随允许的最长任务与恢复窗口扩大，运行中的关联记录不得清理。

CPU、进程数、线程数、数据库连接、队列长度、磁盘和日志容量必须形成部署
profile；未配置全局及工作空间预算的执行队列不启用。以上建议值需在目标机器验证，不能据此保证小规格验证环境支持完整并发负载。

### 14.3 观测与 SLO

至少记录目录查询、准备命令、授权检查、提交接收、排队、执行、结果交付各段耗时，以及查询
P95 /
P99、重复抑制数、确认过期数、重试数、待核对任务数、撤权传播延迟、取消完成延迟、CPU
/ 内存 / 临时磁盘峰值和模型输入量。

requestId → commandId → invocationId → jobId / pipelineRunId →
outputRefs
全链关联。日志默认记录摘要与引用，不记录令牌、全量业务数据或完整模型提示。

联调前登记真实数据集规模、列宽、文件大小、并发、缓存冷热、资源配额及目标延迟。验收报告区分"配置上限""目标
SLO"和"实测值"，不把配置数值写成已经实现的性能。

## 15. 首批能力与最小闭环

### 15.1 能力清单

  --------------------------------------------------------------------------------------------------
  capabilityId                          首期用途                Agent 初始状态
  ------------------------------------- ----------------------- ------------------------------------
  `titanloom.platform.capability.discover`   发现获准目录            需显式授权，目录权限不授予业务执行

  `titanloom.data.query.execute`             已发布数据查询          三道门通过后，可配置 allow

  `titanloom.data.pipeline.read`             已发布流水线元数据      读取范围、Schema 分别控制

  `titanloom.data.pipeline.run`              运行固定版本流水线      默认关闭；开放时支持 confirm / allow

  `titanloom.platform.job.read`              查询自身获授权任务      仍验证目标、委托、来源与结果范围

  `titanloom.platform.job.cancel`            停止有权管理的任务      与查看分开授权

  `titanloom.assets.asset.upload`            为获准任务上传文件      需 Asset 准入、配额和扫描

  `titanloom.assets.asset.preview`           预览获准产物            与下载及模型输入分别授权

  `titanloom.assets.asset.download`          下载获准产物            不继承人工下载许可
  --------------------------------------------------------------------------------------------------

公共 Job 操作先验证 jobId 所绑定的领域资源及原始执行范围，不允许拿到
jobId
就查看日志或取消任务。首期公共能力的默认关闭遵循总框架；表中的"可配置"不是预授予。

表单提交、考勤规则变更、工具发布、页面编辑 / 发布 / Take
等按所属子方案补充契约与验收后逐步开放，不因本规范列出接口机制就全部放行。

### 15.2 例：计算九月份工时效率

1.  用户提出目标，Agent 找到有权获知的已发布流水线和查询能力。
2.  解析"九月份"为明确年份、起止日期与 Asia/Shanghai
    业务时区；存在歧义时确认业务参数。
3.  服务端准备
    commandId，固定流水线版本、来源批次、水位、目标数据集和影响范围。
4.  按当前策略判断是否需要人工确认；需要时展示预览并等待受控确认。
5.  submit 接收命令，事务性生成 Invocation、根 JobRun 与 PipelineRun。
6.  Worker 重新鉴权，按节点执行 SQL / Polars；中间文件登记受控引用。
7.  数据模块校验质量和输出，满足发布条件后原子切换可见 Dataset
    版本；质量阻断时保留旧正式版本并报告失败原因。
8.  Agent
    查询权威状态和获准汇总，报告期间、数据版本、新鲜度、质量与产物入口。

如果第 5 步响应丢失，查原 commandId；如果第 6
步撤权，停止后续受限执行并重新判断交付；如果第 7
步质量阻断，不能说"报表已更新"。

### 15.3 例：外来稽查 Excel 与问题图片

资产服务接收 Excel / 图片并形成稳定 Asset
ID；数据处理导入草稿固定映射与错误报告；每条稽查问题使用稳定业务记录
ID，图片通过业务关联绑定该记录。文件名可辅助匹配，不能作为唯一事实主键。

本规范负责身份、命令、任务和产物引用；具体列映射、重复导入、问题记录修订及附件匹配规则由数据处理
/ 业务所有者设计。Agent
不得直接修改导入表后让看板旁路读取；正式展示通过发布 Dataset / Query
和受权 Asset 加载。

## 16. 验收用例与交付门槛

下表是后续工程测试规范，本次文档编制未执行平台测试。

  ---------------------------------------------------------------------------------------------------------------
  编号                    场景                                 必须验证的结果
  ----------------------- ------------------------------------ --------------------------------------------------
  A01                     网页、SDK、CLI 调用同一能力          相同业务约束与结果语义；身份差异带来明确权限差异

  A02                     伪造 actorType / projectId /         不改变身份或资源归属，不借其他项目绕过限制
                          agentTaskId                          

  A03                     三道门任意一门关闭                   发现 / 取数 / 执行 /
                                                               交付按各自权限拒绝，无先泄露后拒绝

  A04                     权限变更后复用目录、Query 或幂等缓存 重新鉴权，旧缓存不返回受限内容

  A05                     Agent 触发后台服务任务               委托与来源保留；Worker 不能变成无限系统身份

  A06                     Skills 声明额外权限或提示"忽略限制"  服务端权限不变；技能包不能改变授权

  A07                     输入额外字段、错误枚举、超大载荷     Schema / 大小校验明确拒绝，业务无副作用

  A08                     commandId 并发 submit 与 Broker 重投 一个正式接收和领域运行关联；允许多次去重投递

  A09                     同幂等键改参数 / 记录清理后重放旧键  冲突或窗口过期；不得当新操作静默执行

  A10                     确认后改目标、版本、输入或导出语义   原确认失效；不扩大原确认影响范围

  A11                     Agent 通过 CLI 自行确认              受控确认接口拒绝，普通聊天同意不可放行

  A12                     准备后资源修改、页锁失效、策略收紧   提交点拒绝；不能继续使用过期预览或锁

  A13                     outbox 提交后进程崩溃、发布重复消息  恢复入队；不丢持久接收，不重复业务提交

  A14                     Worker 失联，旧 Worker 后来恢复      fencing 拒绝旧写入；外部副作用走幂等或核对

  A15                     submit 超时、CLI wait 超时、用户     查回原运行；不误取消，不自动新建业务运行
                          Ctrl+C                               

  A16                     外部写入成功但响应丢失               reconciling，核对后形成证据；不盲目重试

  A17                     撤权与提交 / 下载 / 模型交付竞态     提交边界、检查周期和资产访问符合登记期限

  A18                     排队取消、运行取消、提交完成后取消   分别正确处理；清楚说明已提交或部分影响

  A19                     Source 对 Agent 关闭，经快照 / 导出  来源限制保留；无细粒度血缘时从严拒绝
                          / 聚合访问                           

  A20                     超大 Query、篡改 cursor、跨用户复用  有界返回、当前权限校验、无越界数据
                          cursor                               

  A21                     精确小数、长整数、跨月和时区         值与业务期间不漂移，前端不损失精度

  A22                     模型结果限制、日志 / 错误 / 产物引用 所有出口执行模型输入和资源检查

  A23                     任务内部成功但数据质量阻断 /         领域运行不标为发布成功，旧正式数据仍可用
                          发布失败                             

  A24                     技能、SDK 或能力版本不兼容           明确拒绝 / 迁移，排队任务不偷偷用 latest

  A25                     zh-CN / en-US 与导出重试             code、ID、参数相同；导出语言时区不漂移

  A26                     批任务占满额度                       签到 / 填报保持独立预算，超限明确拒绝或排队

  A27                     模型 / CLI / 可选适配器不可用        人工业务和已发布固定任务仍正常工作

  A28                     数据库与资产联合恢复                 命令、任务、产物引用可对账，无孤立成功记录

  A29                     Query 筛选使用未声明的 FieldRef、    参数错误或权限拒绝，不静默忽略筛选；"全部"只覆盖
                          调用方自拼相对日期区间、越权筛选值   权限范围；区间按左闭右开解释

  A30                     Dataset 回退或更正后代次通知重复、   代次单调递增；订阅方按代次去重并丢弃旧代次；
                          乱序或丢失                           响应 dataGeneration 与所读数据一致，丢失时由刷新补齐
  ---------------------------------------------------------------------------------------------------------------

上线必须交付：能力与 Schema 包、OpenAPI、生成 SDK、统一 CLI、对应 Skills
包、数据库迁移、授权集成、幂等与确认实现、Runner
实现、契约测试、恢复测试、离线交付清单、容量 profile
与运维手册。通过文档评审不替代这些工程验收。

## 17. 实施顺序与后续扩展

  -----------------------------------------------------------------------------------------------------------------------------
  阶段                    主要交付                                         完成条件
  ----------------------- ------------------------------------------------ ----------------------------------------------------
  P0 契约基础             能力描述符、Schema、错误、身份上下文、版本发布   选取 query.execute / pipeline.run 打通契约与生成 SDK

  P1 受控只读             授权发现、Query、模型结果投影、首个 Skill        三道门、来源限制、精度、分页和缓存用例通过

  P2 命令与执行           准备 / 确认 / submit、JobRun、最小 Runner、CLI   超时重复提交、撤权、取消、崩溃恢复用例通过

  P3 业务闭环             工时效率与外来 Excel / 图片链                    质量、发布、产物、审计证据可追踪

  P4 扩展能力             更多领域、标准队列、外部运行端                   复用同一契约，按真实并发和接入需求开启

  条件阶段                A2A 或其他 Interaction Adapter                   已有明确对接方、协议版本、信任范围、收益和验收计划
  -----------------------------------------------------------------------------------------------------------------------------

首期无需建设 MCP Server、A2A
服务或运行时自编码引擎。后续新增协议只实现映射与信任接入，不能带来第二套授权、业务规则或数据出口。

A2A 对接需补充外部 Agent 注册 / 信任、能力卡访问控制、远端任务与本地
AgentTask
映射、取消传播、重试去重、模型数据边界和多跳委托。不能把能力卡中的自我声明当作平台授权，也不能直接把远端任务
ID 当作本地 JobRun 主键。

## 18. V1.0 跨方案权威边界与状态对照

  ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  对象与行为                     权威来源                                                         本规范及后台使用方式
  ------------------------------ ---------------------------------------------------------------- ----------------------------------------------------------------------------------------------------------------
  CapabilityCommand / Invocation 公共命令与任务服务；本规范第 6---8 节给出设计语义                后台与 Shell 显示同一公共执行事实或受控投影，不另建状态机；领域服务通过稳定引用关联
  / JobRun / JobAttempt                                                                           

  PipelineRun / 质量结果 /       数据处理平台                                                     `domainRunRef` 指向领域运行；JobRun `succeeded` 不等于 PipelineRun 质量通过或 Dataset 发布
  发布状态                                                                                        

  AutomationRun / StepExecution  工具自动化平台                                                   AutomationRun 保留自动化业务语义；需要后台执行时关联 JobRun，Job 的重试或取消不自动改写 AutomationRun 终态
  / TriggerOccurrence                                                                             

  WorkflowInstance / HumanTask / 表单平台                                                   公共 Command / Job 只提供调用和执行机制，不取得审批决定、业务事实或修订所有权
  BusinessRecord / Revision                                                                       

  Attendance 业务事实 / 排班 /   考勤签到平台                                                     Agent、Automation 和 UI 均通过 Attendance Capability / Command 操作；跨域上下文不产生额外考勤权限
  规则版本 / 出勤结果                                                                             

  AgentTask                      智能管家领域                                                     AgentTask 表达目标、计划、上下文、协调和恢复；调用其他领域时保存目标资源与运行引用，不接管目标领域状态

  Page / Release /               数据可视化平台                                                   Release 保持不可变发布语义；播放/嵌入会话不是 JobRun，后台只消费必要运行投影
  PlaybackSession / EmbedSession                                                                  

  KnowledgeSpace / Document /    知识与文档平台                                                   Agent 可跨域核验，但知识对象及修订事实仍由知识领域拥有；公共风险语义复用本规范
  KnowledgeVersion / Issue /                                                                      
  Suggestion                                                                                      

  Dataset、Pipeline、字段血缘    数据处理平台                                                     后台以受控查询嵌入或跳转，`DependencyEdge` 仅表达跨资源治理级依赖

  PlatformAlertRule / PlatformAlertInstance  公共监控告警设施 / 后台治理                                          领域服务产生领域事实、事件或指标；告警确认、静默或解决不自动改变领域业务状态

  Notification                   公共通知能力                                                     负责送达与阅读状态；已读不等于业务已处理，也不代替领域 Command

  AuditEvent / Audit Record      公共审计能力                                                     记录主体、委托、能力、目标、确认、执行与结果证据；默认不作为业务状态所有者或通用业务触发入口

  权限与委托                     总框架及公共授权服务                                             准备、确认、提交及执行点复核；Shell、后台和领域投影不作最终授权依据

  Asset、Dataset / Query         所属公共资产服务和数据处理服务                                   能力消费者通过受控引用和查询接口使用，不复制权威内容

  Shell                          Shell / 门户与个人工作台                                         维护可重建的导航、偏好和聚合投影；不取得 HumanTask、PipelineRun、AutomationRun、AgentTask 等领域对象所有权
  聚合、搜索、最近任务与工作台                                                                    

  Contribution Evidence          各领域拥有原始贡献事实；未来跨域贡献视图若有真实消费者，仅为经授权、可重建的聚合投影   不预设公共 ContributionEvent / Contribution Graph 服务；不授予新访问权，不用于积分或绩效排名                                                                              
  ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

JobRun 设计状态以第 8.3
节为准：`queued`、`running`、`retry_wait`、`cancel_requested`、`reconciling`、`succeeded`、`failed`、`canceled`、`timed_out`。后台的"等待／运行／取消申请／待核对／终态"是这些状态的展示分组，不增加公共枚举。`JobAttempt`
表示一次领取与执行，显示时可简称 Attempt；它不是另一个独立 JobRun。精确
OpenAPI、JSON
Schema、迁移和状态映射测试仍须工程产出与验收，本表只冻结设计责任，不冒称接口已上线。

## 19. 参考依据

项目依据：

-   《Titanloom-总框架设计方案-V1.0.md》及其现行同步基线：平台总体边界、业务能力域、公共平台能力和依赖方向。
-   数据处理、表单平台、考勤签到、工具自动化、知识与文档、数据可视化等现行
    V1.0 领域方案：各领域对象、状态、运行与业务规则。
-   《Titanloom-Shell与门户及个人工作台子方案-V1.0.md》《Titanloom-后台治理中心子方案-V1.0.md》《Titanloom-插件与扩展体系子方案-V1.0.md》等现行公共平台方案：交互宿主、治理投影和扩展接入边界。

本规范只统一跨平台调用与公共执行语义；上述领域方案的内部对象和状态不会因为接入
Capability / Command / Job 机制而转移所有权。

外部格式与协议参考（本规范 V1.0 起始记录）：

-   [R1 OpenAPI Specification
    3.1.1](https://spec.openapis.org/oas/v3.1.1.html)：HTTP 契约与
    Schema 方言基础。
-   [R2 JSON Schema Draft
    2020-12](https://json-schema.org/draft/2020-12)：载荷类型与验证基础。
-   [R3 RFC 8693 --- OAuth 2.0 Token
    Exchange](https://www.rfc-editor.org/info/rfc8693/)：身份交换 /
    委托的标准参考，不替代 Titanloom 自身授权。
-   [R4 Agent Skills
    Specification](https://agentskills.io/specification)：技能包格式、渐进式披露与
    allowed-tools 的实验性状态。

接口路径、状态、配置起点、CLI 行为及数据模型是本文为 Titanloom
提出的设计，不是上述规范直接规定的产品行为。公开规范用于边界参考；不引用未核验的性能倍数或生态规模作为架构依据。
