# Titanloom · 表单平台子方案

> 文档状态：V1.0 架构基线｜修订日期：2026-10-06\
> 名称：本平台原名"填报与流程平台"，2026-10-04 起称"表单平台"（英文 Forms），文件名同步改为《Titanloom-表单平台子方案-V1.0.md》。这是一个表单工具平台：填报、导入与流程是它的功能，不是它的边界。开发项目 key 与文案命名空间仍为 `forms`，对象 Owner 不变。\
> 修订：2026-10-18 26.7 第 2、4 项结清，15.1 功能编号改为 forms.create / forms.publishAll（ADR-032，后端详细设计·表单）；2026-10-16 新增 15.1 功能开放（forms.create、forms.publishAll）；2026-10-04 模块更名为表单平台（见上）；2026-10-01 全文档边界统一，流程人工任务统一为 HumanTask，流程中的 Agent 节点改名 AgentCall（14.1），业务基表与人员主数据的归属改正（2），补隔离门禁 G-ISO 说明，新增 24 验收基线与 25 建设顺序；2026-10-02 新增 19.1 异常与恢复；2026-10-03 5.5 更正：Capture Host / Adapter 已在插件体系登记，宿主协议尚未发布；2026-10-05 新增第 26 节页面与交互（出厂与创建、填写方式、设计器两步、字段类型、计算公式、HTML 组件、记录页与记录的查看和修改），7.1–7.3、22、24（FW14–FW23）、25 同步；2026-10-06 26.5 补 HTML 组件运行出错进入统一报错卡、设计器声明可读视图与页面动作（ADR-024）。\
> 平台定位：Titanloom 的业务事实采集、业务交互与业务流转权威平台\
> 核心原则：业务事实只记录一次；采集入口允许差异；业务语义必须可解释、可映射、可关联；能力不设人为上限，资源必须有明确上限。

------------------------------------------------------------------------

## 1. 目标与边界

### 1.1 建设目标

表单平台不只是传统的"在线表单 + 审批"系统，而是 Titanloom
中负责人工及外部业务事实进入平台、形成权威业务记录并完成业务流转的统一入口。

平台重点解决： - 高频工作登记造成的重复操作与用户负担； -
Excel/CSV/复制粘贴等既有业务输入格式差异； -
页面快速采集、浏览器扩展、API、Agent、自动化等多入口统一； -
表单计算、校验、基表引用、层级联动和复杂业务界面； -
多阶段流程中时间、字段权限、修订、退回、再次确认等生命周期问题； -
最终业务事实以统一契约进入数据处理中心，参与关联、清洗、计算、语义建模和看板制作。

### 1.2 核心边界

表单平台负责： - Form / Quick Capture / Import / Paste / API /
Agent / Automation 输入； -
当前业务记录内的表达式、校验、Lookup、级联和即时计算； - Business
Command、BusinessRecord、Revision、DomainEvent、Provenance； -
Workflow、Task、业务事件时间和流程状态； - Schema Registry
与输入/业务契约。

数据处理平台负责： - 跨大量记录或 Dataset 的 JOIN； -
批量清洗、转换、窗口计算、聚合； - 历史重算、统计分析和指标生产； -
Semantic Layer 与 Published Dataset。

禁止 Form Runtime 演变为第二套 ETL；禁止数据处理平台静默改写权威
BusinessRecord。

------------------------------------------------------------------------

## 2. 总体架构

``` text
                         Titanloom 表单平台
                                  │
 ┌────────────────────────────────┼────────────────────────────────┐
 │                                │                                │
 ▼                                ▼                                ▼
采集体系                         业务事实体系                      流程体系
 │                                │                                │
Form                             BusinessRecord                   Workflow
Quick Capture                    Revision                         HumanTask
Excel / CSV                      DomainEvent                      BusinessCommand
Paste                            Provenance                       Gateway
API                              Attachment                       Timer/Event
Agent                            Business Time                    Delegation
Automation                       Concurrency                      ServiceTask
 │                                │                                │
 └────────────────────────────────┼────────────────────────────────┘
                                  ▼
                          Schema Registry
                                  │
          ┌───────────────────────┼────────────────────────┐
          ▼                       ▼                        ▼
   Expression Engine         Mapping Engine           Policy Engine
   Validation Engine         Lookup Engine            Event Engine
   Reactive Graph            Import Profile           Command Engine
          │                       │                        │
          └───────────────────────┼────────────────────────┘
                                  ▼
                         Capability / Data SDK
                                  │
             ┌────────────────────┼────────────────────┐
             ▼                    ▼                    ▼
        数据处理平台     业务基表(数据处理)/主数据(平台主数据服务)   Agent
             │
             ▼
 Dataset → Pipeline → Semantic Layer → 可视化控制台
```

跨模块主动调用遵循平台统一链路：调用者 → Capability / BusinessCommand →
表单平台领域 → 必要时公共 Job / Executor。WorkflowInstance / HumanTask
负责人工业务流转，JobRun / JobAttempt
只负责后台执行机制；执行层重试、失败或取消不得直接冒充审批、退回、撤回等业务结果。Shell
/ 门户只聚合待办、通知、深链接和运行引用，不取得
BusinessRecord、Revision、WorkflowInstance 或 HumanTask 所有权。

------------------------------------------------------------------------

## 3. 核心设计原则

1.  **业务事实只记录一次。**
2.  **能自动获得的信息不要求用户重复填写。**
3.  **允许输入格式差异化，不强迫部门统一 Excel 模板。**
4.  **差异在 Mapping / Import Profile / Adapter
    层消化，业务语义保持稳定。**
5.  **Form ≠ Data。表单只是业务事实的一种交互入口。**
6.  **BusinessRecord 是权威业务事实；Dataset 是分析和加工语义。**
7.  **页面、Excel、Capture、API、Agent、Automation 最终经过统一
    Capability /
    BusinessCommand、权限和校验边界；不同调用端不建立业务后门。**
8.  **隐藏/显示属于 Presentation；字段是否赋值属于 Value
    Lifecycle，两者分离。**
9.  **动态规则可以变化，已经发生的业务事实不能随当前规则变化。**
10. **业务动作形成版本边界，UI 每次输入不形成 Revision。**
11. **复杂能力允许扩展，但执行资源必须有预算。**
12. **Draft 不影响已发布 Release；运行实例绑定不可变 Release。**

------------------------------------------------------------------------

## 4. 采集体系

### 4.1 统一输入模型

``` text
Input Source
   ├─ Form
   ├─ Quick Capture
   ├─ Excel / CSV
   ├─ Paste
   ├─ API
   ├─ Agent
   └─ Automation
        ↓
InputPayload
        ↓
Mapping / Validation
        ↓
BusinessCommand
        ↓
BusinessRecord / DomainEvent
```

Submission 仅作为 Form Runtime
的交互记录，不作为平台所有输入方式的核心长期对象。

### 4.2 最小必要人工输入

系统优先自动取得：当前身份、组织、时间、上下文、上次选择、当前项目/任务、可推导字段。用户只填写业务无法可靠自动获得的信息。

支持： - 默认值与最近值； - 上下文继承； - 连续登记； - 批量登记； -
草稿； - 快捷键； - 一键重复上一条； - 批量粘贴； - Import Profile； -
Agent 辅助补全。

### 4.3 EntryProfile

同一 RecordType
可以具有多个交互入口：快速登记、完整表单、主管修订、Excel
导入、API、Agent 等。入口不同，但最终产生同一业务语义。

------------------------------------------------------------------------

## 5. Quick Capture 快捷采集体系

### 5.1 定位

Quick Capture 用于解决"每干一次活就需要重新进入平台登记"的高频摩擦。

### 5.2 三层模型

-   **Capture Host**：Browser Extension、Web Floating Widget、Desktop
    Companion、Embedded SDK 等；
-   **Capture Adapter**：识别允许页面和允许读取的上下文；
-   **Capture
    Action**：登记完成、工时、异常、数量、结果、备注等业务动作。

### 5.3 Trigger

支持
ManualClick、Hotkey、Selection、ValueChange、DOMChange、Clipboard、ExternalEvent、APIEvent
等触发器。

### 5.4 提交等级

-   L0 Prepare：准备数据，由用户完整确认；
-   L1 Confirm：信息已准备，只需一次确认；
-   L2 Auto
    Commit：低风险、高频、明确授权场景自动提交，并提供可追溯撤销/作废能力。

自动读取与自动写入必须分开授权。

### 5.5 安全边界

Capture Host / Adapter 已在插件体系第 2 节登记为宿主类型，但宿主协议尚未发布；浏览器扩展与 Desktop Companion 尚未登记。在插件体系发布对应宿主协议并通过验收前，以上均不属首期交付范围，首期入口为 Form、Excel / CSV、Paste 与 API。


Capture Context 永远视为不可信输入。必须经过 Adapter → Mapping →
Validation → BusinessCommand。禁止扩展直接写数据库。

Adapter
必须声明：允许域/页面、可提取字段、版本、来源定位。默认不保存完整网页；需要证据时显式配置
Text Snapshot、Screenshot、DOM Fragment 或 External Record ID。

------------------------------------------------------------------------

## 6. Excel / CSV / 粘贴导入

### 6.1 不强制统一模板

平台通过 Import Profile
将不同部门现有格式映射到业务字段，不要求用户重新整理成唯一标准 Excel。

### 6.2 Import Profile

保存： - 文件/Sheet 匹配规则； - 列到字段映射； - 类型转换； -
值映射； - Lookup； - 表达式； - 校验； - SchemaVersion； -
ProfileVersion。

### 6.3 部分成功

ImportBatch 支持
ACCEPTED、REJECTED、WARNING、PENDING_RESOLUTION。异常行可修复后单独
Retry，不要求重新导入整个文件。

### 6.4 来源追踪

保存
source_asset_id、import_profile_id/version、行号/Sheet、导入人、导入时间及生成
record_id，支持从看板指标追溯至 BusinessRecord、ImportBatch
和原文件位置。

### 6.5 表格粘贴

RepeatingGroup 和批量录入均支持 Excel 二维数据 Ctrl+C/Ctrl+V，并复用
Mapping Engine，不另造第二套映射体系。

------------------------------------------------------------------------

## 7. Form Runtime：可编程业务界面

### 7.1 字段类型

-   InputField
-   ReferenceField
-   LookupField
-   CascadeField
-   ComputedField
-   EventBoundField
-   HiddenField
-   CollectionField
-   RepeatingGroup
-   RecordCollection

设计器向表单设计者展示的字段类型按值的类型划分（文本、数字、日期、时间、选项、人员、引用基表、计算、明细表、附件、HTML 组件），与本节类型的对应见 26.3.1。

### 7.2 Presentation

支持
Heading、Text/Markdown、Divider、Alert、Section、Group、Grid、Tabs、Collapse、Card、Image、Link、Spacer、HTMLBlock
等。

Presentation State：Visible / Hidden / ReadOnly / Disabled / Masked。

Presentation 状态不决定字段是否被初始化或写入。

HTMLBlock 在设计器中统一为"HTML 组件"，可以只显示、保存一个值或只做交互逻辑，见 26.5。

### 7.3 Expression / Validation / Condition

三者严格分离： - Expression：计算一个值； - Validation：判断是否合法； -
Condition：决定显示、行为或流程分支。

示例：

``` text
duration = datetime_diff(end_time, start_time, "minutes")
valid = end_time > start_time
total = quantity * coefficient + project_coefficient
```

设计器中公式以字段显示名和本地化函数名呈现，保存时为字段 ID 与规范函数，见 26.4。

### 7.4 Lookup 与基表

表单不得直接 SQL 查询数据库。所有 Lookup 经 Data SDK / Query Capability
获取权威数据，并支持 effective_at 语义以取得业务发生时适用的历史值。

### 7.5 Reactive Dependency Graph

字段、Lookup、公式建立依赖图。上游字段变化时只重算受影响节点。发布前执行循环检测、复杂度检查、Lookup
数量检查；运行时限制执行时间、Lookup 次数、递归深度和结果大小。

### 7.6 计算结果策略

支持： - Derived：按需派生； - Materialized：计算后保存； - Snapshot
Derived：保存结果及当时依赖值、规则版本和数据快照引用。

------------------------------------------------------------------------

## 8. 高代码与扩展安全等级

### L0 Declarative

Expression、Validation、Condition、Lookup、Layout。默认能力。

### L1 Sandbox Script

（受隔离宿主门禁 G-ISO 约束，见《Titanloom-实施路线与首期工程基线》；门禁通过前不开放。）受限脚本，无直接网络、DOM、凭据和数据库权限；限制
CPU、内存、执行时间和结果大小；通过 Capability SDK 获取授权能力。

### L2 HTML Block

运行于 sandboxed iframe / 独立执行域，采用
CSP、消息来源与结构校验、CSS/DOM
隔离；不得直接获得主站凭据和数据库连接。

### L3 Plugin

需要复杂 UI、网络或平台能力时进入正式插件体系：注册 → 审核 → 授权 →
Release → Runtime。

------------------------------------------------------------------------

## 9. BusinessRecord 与 Schema Registry

### 9.1 BusinessRecord

核心字段：

``` text
record_id
record_type_id
schema_version
business_key
status
occurred_at
business_date
created_at
created_by
current_revision
data JSONB
```

### 9.2 PostgreSQL 存储策略

采用 **关系核心 + JSONB 动态业务字段 + 按需物化/投影**。

治理字段和高频公共关联键不应全部埋入 JSONB。Schema Registry 可以为高频
person_id、project_id、org_id、asset_id 等声明
searchable/indexed/materialized 策略，形成关系化投影。

禁止每创建一个 Form 就动态 CREATE TABLE。

### 9.3 Schema Registry

管理：RecordType、SchemaVersion、FieldDefinition、RelationDefinition、CollectionDefinition、ExpressionDefinition、ValidationDefinition、EventBinding、IndexPolicy、CompatibilityPolicy。

Schema Registry 管业务结构契约，不承担整个 Titanloom 的万能元数据存储职责。

### 9.4 Schema 演进

历史记录绑定产生它的 SchemaVersion。新增 optional
字段可标记兼容；字段删除、类型变化等 Breaking Change
必须执行依赖分析，检查 Form、Workflow、Import Profile、Capture
Adapter、Dataset Mapping、Dashboard 等影响。

------------------------------------------------------------------------

## 10. 子表、明细与子业务对象

### 10.1 三类集合

-   CollectionField：简单值集合；
-   RepeatingGroup：依附于父记录的结构化重复明细；
-   RecordCollection：具有独立业务生命的子 BusinessRecord 集合。

### 10.2 独立对象判断

当一行具有独立
ID、权限、状态、流程、负责人、附件、修订历史、关系、生命周期或统计口径时，应考虑建模为独立
BusinessRecord，而不是普通子表行。

### 10.3 父子关系与流程关系分离

Record Relationship ≠ Workflow
Relationship。父记录可以完成，而子问题继续整改；流程也可以通过条件等待所有子记录达到指定状态。

### 10.4 行级公式

RepeatingGroup 支持 currentRow、parent、collection 作用域，以及
SUM/FILTER
等集合计算。常用操作提供图形化配置，高级需求再进入表达式/脚本。

### 10.5 大明细性能

支持虚拟滚动、分页、服务端过滤/排序、增量加载、批量编辑、批量校验和批量提交。UI
一次渲染量与业务容量上限分离。

------------------------------------------------------------------------

## 11. 时间模型与事件绑定字段

### 11.1 时间语义

必须区分： - Business Time：occurred_at、business_date； - System
Time：recorded_at、created_at、updated_at； - Workflow/Event
Time：submitted_at、approved_at、returned_at 等； - Effective
Time：规则/基表/关系从何时开始生效。

### 11.2 EventBoundField

字段可绑定业务事件，而不是仅配置 `default = now()`。

例如：

``` text
borrowed_at = timestamp(BORROW_SUBMITTED)
returned_at = timestamp(RETURN_CONFIRMED)
```

### 11.3 值来源

Field Value
Source：Manual、Default、Initial、Expression、Lookup、Reference、Agent、SystemContext、EventBinding。

Write
Policy：WriteOnce、Replace、Append、FirstEvent、LatestEvent、ManualOverride。

### 11.4 借记示例

第一次登记：borrowed_at 由借用提交事件写入，returned_at 保持
NULL。归还待办生成、打开均不等于归还；只有 ConfirmReturn Command
成功后由服务端产生 RETURN_CONFIRMED，returned_at 绑定其权威事件时间。

### 11.5 业务日/班次

TimeContext 支持
timestamp、timezone、calendar_date、business_date、shift_id，以处理跨午夜和非自然日业务周期。

------------------------------------------------------------------------

## 12. Command、TaskView 与字段策略

### 12.1 不用一张 Form 硬撑整个流程

同一 BusinessRecord 可以使用 BorrowCreate、Approval、ReturnConfirm
等不同 TaskView/EntryProfile。

### 12.2 Field Policy

按 TaskView 声明
Visible、Hidden、ReadOnly、Editable、Optional、Required、Masked。

"必填"优先定义为 Command 前置条件，而不是字段永久 required。

### 12.3 Business Command

禁止所有动作都叫 Submit。使用
Create、Submit、Approve、Reject、ConfirmReturn、Withdraw、Void、Correct
等具有业务语义的 Command。

执行链：

``` text
Command
 → Authorization
 → Preconditions
 → Validation
 → Write Policy
 → Revision/Event
 → Workflow Transition
 → Audit
```

------------------------------------------------------------------------

## 13. Revision、草稿与并发

### 13.1 Revision 边界

Draft 内可持续修改；执行正式业务 Command 时形成
Revision。退回后重新提交形成新 Revision，保留旧值和差异。

### 13.2 撤销/作废

已形成正式事实后不使用物理 DELETE 表达业务撤销，应通过 VOID/CORRECT 等
Revision/Event 留痕。

### 13.3 并发控制

BusinessRecord 默认采用 Optimistic Concurrency Control。Command 携带
expected_revision；版本不一致返回
CONFLICT，并提供差异比较/重新应用。只有特殊场景使用独占锁。

------------------------------------------------------------------------

## 14. Workflow Engine

### 14.1 V1 基线节点

-   Start / End
-   HumanTask
-   AgentCall（向智能管家发起并等待一个 AgentTask；AgentTask 及其生命周期归智能管家，本节点只保存引用与业务结果）
-   ServiceTask
-   ExclusiveGateway
-   ParallelGateway
-   TimerWait
-   EventWait
-   SubProcess

支持提交、审批、退回、撤回、重新提交、确认、转办、加签/会签、超时、条件分支和并行。

V1 不实现完整 BPMN 2.0 引擎；通过 NodeType Plugin 保留未来扩展上限。

### 14.2 流程与业务对象分离

WorkflowInstance 不应成为 BusinessRecord
的内部状态机实现。业务对象与流程实例通过明确关系连接，允许同一记录触发不同流程或子记录拥有独立流程。

### 14.3 动态分支与办理人解析

流程可引用字段、基表和组织关系决定路径与办理人。动态 Assignment Rule
解析后必须保存 resolved_person 和 resolved_at
快照，避免未来组织变化污染历史。

### 14.4 Delegation / 代理

Task 同时记录
assigned_to、acting_by、delegation_id。实际执行人、原办理人和代理依据必须可审计。Agent
最小委托也复用该身份/委托模型。

### 14.5 批量办理

Task Center 支持批量批准、退回、分配、补字段。批量 Command
必须逐记录授权、逐记录校验并返回逐条结果；除业务明确要求外，不强制整批原子失败。

------------------------------------------------------------------------

## 15. 权限与治理

完整授权链：

``` text
Identity
 → Platform Capability
 → Resource Scope
 → Record Scope
 → Command Permission
 → Field Policy
```

Record Scope 支持本人、组织、项目、授权集合等范围规则。

平台权限/Capability
是权威授权层；数据库行级策略可作为纵深防御，但不得取代业务授权体系。

Agent、人、API、Automation 均不得绕过 Capability /
BusinessCommand、权限和 Data
SDK。跨领域调用必须按目标能力、目标资源和当前身份/委托重新鉴权；页面上下文、Workflow
Task 或 Agent 上下文均不传递为隐式权限。

### 15.1 功能开放

**功能开放登记（2026-10-13，后台治理 4.6、总框架 8.5.3）。** 本域登记的"新建 / 发起"类功能如下；谁有由平台管理 › 角色与授权 › 功能开放定，标"归部门 / 项目"的可被部门空间、跨部门项目往紧了收。"开了"= 能新建并能看、改、删自己建的，别人建的靠负责人分享。

-   `forms.create` 新建表单：影响中，出厂指定的人（表单管理员、部门负责人），归部门 / 项目。建出来是草稿，只有自己能看；发给别人填要再发布。
-   `forms.publishAll` 把表单发布给全员填：影响高，出厂指定的人，不能改成所有人，归部门 / 项目。只发给本部门或自己选的人不受这项限制。
-   管家"帮我建一张"先过 `forms.create`，本人没有就不能建，回复里给「申请」。


------------------------------------------------------------------------

## 16. Provenance、附件与审计

### 16.1 字段级 Provenance

字段来源可标记
USER、LOOKUP、EXPRESSION、CAPTURE、IMPORT、AGENT、EVENT、SYSTEM
等，并记录必要的规则版本、数据快照、Adapter/Profile 等引用。

### 16.2 附件

AttachmentRef 记录
asset_id、record_id、revision_id、field_id、purpose、uploaded_by、uploaded_at，使附件与当时业务状态和字段语义绑定。

### 16.3 Audit

必须可回答：谁在什么时候通过什么入口、以什么权限、执行什么
Command、改变了什么字段、依据什么规则/版本、产生了什么事件。

------------------------------------------------------------------------

## 17. Agent 接入

Agent 是平台管家，但不是数据库超级管理员。

允许 Agent：读取授权上下文、补全、核验、分类、生成
InputPayload、提出修订、执行被授权 Command；AgentTask
本身由智能管家领域拥有，表单平台只保存必要的关联引用、委托与业务结果。

禁止 Agent：旁路数据库、绕过 Capability、突破调用者/委托范围、修改不可变
Release、把凭据带入模型上下文。

Agent 生成的数据仍经过 Mapping / Validation / Command，并记录
Provenance。

------------------------------------------------------------------------

## 18. 与数据处理平台的数据契约

BusinessRecord 通过受控数据契约 / Data SDK
向数据处理平台提供授权数据，并通过 DomainEvent
表达已经发生的领域事实与变更语义。DomainEvent
不是跨域写接口，数据处理平台不得通过消费事件取得修改 BusinessRecord
的权力。数据处理平台形成 Dataset、Pipeline、Semantic Layer 和 Published
Dataset。

示例：

``` text
ProductionRecord ─┐
Attendance ────────┼→ Pipeline → Efficiency Dataset → Dashboard
Project Master ────┘
```

数据处理中心发现业务事实异常时，应形成可追踪的 ValidationResult / Issue
或通过受控 Capability / BusinessCommand 请求所属领域修订；不得静默
UPDATE 权威 BusinessRecord。是否进入 Workflow
由表单平台领域按业务规则决定，不由数据处理平台直接改写流程状态。

------------------------------------------------------------------------

## 19. Draft / Release 与运行稳定性

Form、Schema、Workflow、Import Profile、Capture Adapter、Expression
等可编辑定义必须经过：

``` text
Draft → Validate → Dependency Analysis → Test → Publish → Immutable Release
```

运行中的 FormInstance、WorkflowInstance、ImportBatch 等绑定对应
release_id。新 Release
默认不改变已经运行的实例，除非执行显式、可审计的迁移策略。

本节 Release
专指表单平台领域中可编辑定义经过发布边界形成的不可变运行定义；它不等同于
BusinessRecord 的 Revision，也不等同于公共 JobRun / JobAttempt
的执行状态。BusinessRecord 的正式业务变化继续通过 Revision / DomainEvent
表达。

------------------------------------------------------------------------

### 19.1 异常与恢复

| 情形 | 预期行为 |
| --- | --- |
| Command 提交后响应丢失 | 按 commandId 与幂等键查回原结果，不重复生成 Revision 与 DomainEvent |
| 并发修改 | expected_revision 不符返回 CONFLICT，提供差异与重新应用，不静默覆盖 |
| 导入部分失败 | ImportBatch 逐行状态保留，异常行可单独 Retry，不重导整份文件 |
| DomainEvent 投递失败或乱序 | 业务事务内写 outbox，至少一次投递，消费者按稳定 ID 幂等；数据处理不可用不阻断业务提交 |
| 流程实例遇到新 Release | 运行实例继续绑定原 release_id，迁移需显式、可审计 |
| JobRun 重试或取消 | 只影响执行机制，不改变审批、退回等业务结果 |
| 动态办理人解析后组织变化 | 以保存的 resolved_person 与 resolved_at 为准 |
| 撤权发生在任务等待期间 | 办理时重新鉴权，旧授权快照不继续使用 |

## 20. 资源治理与性能基线

平台必须对以下能力设资源预算： - 表达式执行时间； - 脚本 CPU/内存； -
Lookup 次数； - 依赖图深度； - Import 行数/批次大小； - 单次批量 Command
数量； - RepeatingGroup 渲染窗口； - 附件大小与数量； - Capture
证据大小； - Workflow 并行任务数。

资源限制由后台治理中心统一配置、监控和审计；业务能力契约不因默认资源额度而人为封顶。

------------------------------------------------------------------------

## 21. V1 明确不做

-   完整 BPMN 2.0 实现；
-   任意代码直接访问数据库；
-   任意 HTML/脚本进入主站同权限 DOM；
-   所有动态字段自动建索引；
-   每个 Form 动态 CREATE TABLE；
-   Workflow 自建人员/组织主数据；
-   Form Runtime 承担大规模 ETL；
-   Capture 默认保存完整网页；
-   Agent 绕过 Business Command；
-   Hidden 自动等价于初始化；
-   默认值 `now()` 代替业务事件时间；
-   数据处理平台静默覆盖业务事实。

------------------------------------------------------------------------

## 22. 核心对象清单

``` text
RecordType
SchemaVersion
FieldDefinition
RelationDefinition
CollectionDefinition

FormSchema
FormRelease
EntryProfile
TaskView

InputPayload
ImportProfile
ImportBatch
MappingRule
CaptureAdapter
CaptureAction
CaptureContext

BusinessCommand
BusinessRecord
RecordRevision
DomainEvent
AttachmentRef
Provenance

ExpressionDefinition
ValidationDefinition
ConditionDefinition
LookupDefinition
EventBinding

WorkflowDefinition
WorkflowRelease
WorkflowInstance
HumanTask
Gateway
Delegation

ValidationResult
AuditRecord

ComponentDefinition
ComponentRelease
ComponentBinding
```

ComponentDefinition / ComponentRelease 是 HTML 组件的定义与不可变版本，ComponentBinding 是组件中绑定名到有序字段 ID 的对应（26.5）。表单中的分区、显示条件与标题属于 FormSchema，不另建对象。

公共能力直接引用 Titanloom 统一
Identity、Permission、Capability、Asset、Dataset、Query、JobRun /
JobAttempt、Audit、Notification、Plugin/Extension
契约，不在本子平台重复定义。WorkflowInstance /
HumanTask、BusinessRecord / RecordRevision 等领域对象仍由本平台拥有；公共
Job 只提供后台执行机制，不取得流程或业务事实状态所有权。

------------------------------------------------------------------------

## 23. 最终架构结论

表单平台不是为了让用户"填更多表"，而是为了以最低人工摩擦捕获真实业务事实，并保证这些事实在多入口、多阶段、多角色、多版本环境中仍然可解释、可追溯、可治理。

最终形成四条稳定主线：

1.  **入口自由**：Form、Capture、Excel、Paste、API、Agent、Automation
    均可进入；
2.  **事实稳定**：BusinessRecord、Revision、Event、Provenance
    保证业务事实不会因界面或规则变化失真；
3.  **流程解耦**：TaskView、Command、Workflow 负责业务流转，不把一张
    Form 当作整个流程；
4.  **分析统一**：业务事实经统一数据出口进入数据处理平台，再完成跨域关联、计算、语义建模和可视化。

该设计贯彻 Titanloom
的总体原则：**能力不设人为上限，资源必须有明确上限；架构面向未来，生产基线面向稳定。**

------------------------------------------------------------------------

## 24. 验收基线

下列场景用于工程验收；通过条件必须有自动化测试或可复现演练证据，不以截图代替。

| 编号 | 场景 | 通过条件 |
| --- | --- | --- |
| FW01 | 同一 Command 重复提交、响应丢失 | 同幂等键只产生一次 Revision 与一次 DomainEvent；超时后查回原 commandId |
| FW02 | 同一记录两人并发修改 | 后到者返回 CONFLICT 并给出差异，不静默覆盖 |
| FW03 | 退回后重新提交 | 形成新 Revision，旧值与差异保留；已确认事实不物理删除 |
| FW04 | 导入含错误行的 Excel | 合格行 ACCEPTED，异常行 REJECTED / PENDING_RESOLUTION 并可单独 Retry；可从记录追溯到文件、Sheet 与行号 |
| FW05 | 重复导入同一文件 | 按文件哈希与业务键去重，指标不被放大 |
| FW06 | 基表或 Schema 新版本发布 | 已运行实例与历史记录绑定原 Release / SchemaVersion，不被新规则改写 |
| FW07 | 审批人转办、代理办理 | HumanTask 记录 assigned_to、acting_by、delegation_id，撤权后后续办理被拒 |
| FW08 | 动态办理人解析 | 保存 resolved_person 与 resolved_at，组织调整不改变历史 |
| FW09 | 批量办理 | 逐条授权、逐条校验、逐条返回结果，不强制整批原子失败 |
| FW10 | 归还待办生成或打开 | returned_at 不变，仅 ConfirmReturn 成功后由 RETURN_CONFIRMED 写入 |
| FW11 | 表达式循环依赖、超预算 | 发布前被拒绝；运行时受时间、Lookup 次数、递归深度限制 |
| FW12 | 数据处理或模型不可用 | 填报、审批、导入照常提交；DomainEvent 经 outbox 后补投递 |
| FW13 | Agent 越权、不可信指令 | 服务端按调用者与委托拒绝；Provenance 记录 AGENT 来源 |
| FW14 | 分区显示条件不成立时提交 | 该分区字段不作为本次 Command 前置条件、不随本次 Command 写入；服务端独立评估条件，客户端伪造"可见"无效 |
| FW15 | 客户端提交篡改过的计算值 | 服务端按 Expression 重算并以重算值写入，客户端值不被采信 |
| FW16 | HTML 组件写入当前步骤只读或隐藏的字段 | 界面拒绝写入；绕过界面直接提交时服务端按 Field Policy 拒绝 |
| FW17 | HTML 组件发起网络请求或读取父页面 | 被 CSP 与 sandbox 阻止；组件只能经消息接口读到当前 TaskView 已下发的字段 |
| FW18 | 字段改名 | 公式、显示条件、分支条件与组件绑定保持有效，显示名随之更新 |
| FW19 | 组件库中的组件更新 | 已发布表单仍使用发布时冻结的 ComponentRelease，负责人升级并重新发布后才生效 |
| FW20 | 没有流程的表单提交 | 提交即生效，不生成 WorkflowInstance / HumanTask |
| FW21 | 记录可见范围为"只看自己的"时，直接按记录 ID 或改写查询请求 | 服务端按 Record Scope 拒绝；敏感字段在他人记录中不下发 |
| FW22 | 修改已生效记录 | 形成新 Revision 并保留修改前的值与理由；按表单设置重新发起审批或通知审批人；审批进行中的记录修改被拒绝 |
| FW23 | 无修改权限的人提交修改 | 服务端按 Correct Command 权限与"什么时候能改"前置条件拒绝 |

## 25. 建设顺序与完成标准

阶段编号以《Titanloom-实施路线与首期工程基线》的 M 序列为准，本节只声明本领域内部顺序。

- **阶段一（对应 M2）**：RecordType / Schema Registry、Form Runtime 的 L0 能力（Expression / Validation / Condition / Lookup）、BusinessCommand、BusinessRecord / Revision、乐观并发、草稿、Excel / CSV / 粘贴导入与 Import Profile、HumanTask 与最小 Workflow（Start / End / HumanTask / 排他网关 / 退回 / 重新提交）、附件经 Asset、Provenance 与 Audit、受控数据出口与 DomainEvent（outbox）；第 26 节的表单列表与新建、填一条 / 连续登记 / 批量、设计器两步（本阶段已有的节点）、计算公式、记录页与记录的查看和修改设置。
- **阶段二**：并行网关、TimerWait / EventWait、SubProcess、转办 / 加签 / 会签、批量办理、RepeatingGroup 大明细性能、EventBoundField 完整语义、AgentCall 节点；HTML 组件第一步（平台内置的官方组件，26.5）。
- **阶段三**：L1 脚本（待 G-ISO）、L2 HTML Block（含 HTML 组件第二步：手写与管家生成，26.5）、Quick Capture 与 Capture Host（待插件宿主协议）、NodeType Plugin。

完成标准：第 24 节 FW01–FW23 中已开放能力对应的条目通过；总框架 15.3 中与填报相关的场景通过；本方案不代表软件已实现。

------------------------------------------------------------------------

## 26. 页面与交互

本节记录前端设计评审中确定的用户流程与设计器模型，并说明它们与前文对象的对应。界面上的叫法面向表单设计者和填写人；括号中的对象名是本方案的权威模型。示例均为合成数据。

### 26.1 出厂与创建

-   平台出厂不带任何表单。表单由有创建权限的人新建并发布后，才出现在可以填写的人的表单列表里。创建权限默认给表单管理员与部门负责人（待确认，见 26.7）；没有权限的成员可以向表单负责人或管理员提出需求。
-   新建表单的开始方式：从 Excel 开始（逐列识别字段类型，可带入已有行，并同时生成 Import Profile，见 6.2）；从示例开始；让智能管家起草（结果是 Draft，须人确认，Provenance 记 AGENT）；空白；复制已有表单。开始方式只在新建页出现。
-   Draft 只有作者可见。发布前执行检查（26.3.4），发布形成 FormRelease 与 WorkflowRelease（19），并登记受控数据出口（18）。运行中的记录继续按原 Release 走完，新提交的记录用新 Release。
-   每张表单有一位负责人，可以转交。停用不删除：历史记录、待办与数据出口保留。
-   表单列表按分类分组：能填写的人看到"填写"；负责人另外看到发布状态、本月提交数，以及记录、编辑、谁能填、复制、转交、停用等操作。每张表单的记录在记录页查看（26.6）。

### 26.2 填写方式

负责人在设计器"设置"中为表单开放以下填写方式，每种对应一个 EntryProfile（4.3）：

-   **填一条**：常规表单。右侧显示还差几项与随分支变化的流程；被退回后修改重新提交形成新 Revision（13.1）；并发冲突时逐项选择保留哪一方（13.3）。
-   **连续登记**：适合工时一类高频登记。指定的字段（如日期、部门）沿用到下一条，一行录入、快捷键提交，当天已登记的条目可以撤回（Withdraw / Void，13.2）。不显示"距截止还差几小时"一类倒计时提示。
-   **批量**：粘贴或上传表格，逐行检查，在格子里直接修改，只提交通过检查的行；逐条执行 Command、逐条返回结果（6.3、6.5、14.5）。

审批是表单自带的流程，可以没有。没有流程的表单提交即生效，不生成 WorkflowInstance / HumanTask（FW20）。

### 26.3 设计器：表单设计 → 流程配置

设计器分两步，顶部以步骤条切换：① 表单设计，② 流程配置。不另设单独的"字段"页。设计器只在电脑上编辑，手机上提示到电脑上编辑。

| 设计器里 | 对应对象 |
| --- | --- |
| 字段 | FieldDefinition，属于 RecordType / SchemaVersion，不属于任何流程步骤 |
| 表单的分区、排列、标题、分区显示条件 | FormSchema 的 Presentation 与 ConditionDefinition |
| 发起人对每个字段：必填 / 选填 / 不显示（流程中再填） | 发起 TaskView（Create / Submit）的 Field Policy |
| 流程画布 | WorkflowDefinition |
| 每一步对每个字段：隐藏 / 只读 / 可填 / 必填 | 该步 TaskView 的 Field Policy；必填是该步 Command 的前置条件（12.2） |
| 画布左侧固定的"发起人提交" | Start 节点；画布上不让用户另放"开始" |

#### 26.3.1 字段类型

原则：**字段类型按值的类型划分，外观、行数、格式等属于设置**。不因为输入框高矮或是否带格式而另设类型。

| 设计器类型 | 设置 | 对应 |
| --- | --- | --- |
| 文本 | 一行 / 多行；允许格式（加粗、列表、链接、图片，默认关）；最多字数；格式要求（手机号、邮箱、编号规则等） | InputField（文本）；允许格式时值为安全子集的富文本，导出到表格时只保留文字 |
| 数字 | 单位、小数位、范围 | InputField（数值） |
| 日期、时间 | 自动记下时间：不自动 / 提交时 / 某一步完成时 | InputField；自动记下时为 EventBoundField（11.2），如借出时间 = 提交事件，归还时间 = 确认归还完成事件 |
| 选项 | 选项清单 | InputField（枚举），可作分支与显示条件 |
| 人员 | 默认本人等 | ReferenceField（人员主数据），可决定办理人 |
| 引用基表 | 基表、下拉显示列、只列出（过滤）、选中后带出的列 | LookupField，经 Data SDK 读取（7.4）；带出值随记录保存为快照，Provenance 记 LOOKUP |
| 计算 | 公式、单位、小数位 | ComputedField（26.4） |
| 明细表 | 列 | RepeatingGroup（10） |
| 附件 | 数量、大小 | AttachmentRef（16.2） |
| HTML 组件 | 代码、绑定 | 见 26.5 |

#### 26.3.2 显示条件与流程分支分开

-   分区可以设"如果某字段满足某条件才显示"。这是 Condition（Presentation），只决定显示；流程往哪走由流程画布中的分支决定（ExclusiveGateway）。两者在设计器中分开配置，可以引用同一个字段。
-   显示条件同时在服务端评估，不依赖客户端是否显示（原则 8）。条件不成立时，该分区的字段不作为本次 Command 的前置条件，也不随本次 Command 写入；填写人改选之前已填的值只保留在草稿中（待确认，见 26.7；验收 FW14）。
-   设计器可以按"发起人"或任一步骤的视角预览表单，看到的字段与该 TaskView 一致。

#### 26.3.3 流程节点与办理人

| 画布节点 | 说明 | 对应 |
| --- | --- | --- |
| 分支 | 如果 / 否则如果 / 否则，从上往下判断、只走一条；按选项字段可一键生成每个选项一条路，选项全部覆盖时不出现"否则" | ExclusiveGateway |
| 并行 | 同时走几条路线，全部完成后在下一步汇合 | ParallelGateway |
| 审批 | 同意 / 退回（退回须写意见），可转交、加签，多人时或签 / 会签 / 依次 | HumanTask（Approve / Reject） |
| 办理 | 由指定的人做完一件事，可填部分字段，按钮名可改；选"发起人自己"即发起人回填（如借用后的归还登记） | HumanTask，完成动作为具名 Command（如 ConfirmReturn，12.3） |
| 抄送 | 只通知，不进待办、不用处理 | Notification，不生成 HumanTask |
| 等待 | 等固定时长，或等到某个日期字段 | TimerWait |
| 自动操作 | 让其他平台做一件事，如更新物品台账状态 | ServiceTask，经目标领域 Capability；重试或失败不改变审批结果（2） |
| 结束 | 进入数据出口，通知指定的人 | End |

-   **谁来处理**：个人（发起人自己 / 指定人）、分组（组内都能看到这条待办，第一个办理的人认领）、按关系（发起人的部门负责人等）、按表单字段（表单里选的人）。找不到人时转给表单负责人或跳过。解析结果保存 resolved_person 与 resolved_at（14.3）。
-   **期限**：不设，或固定时长，或到某个日期字段；可设提醒；超时后只提醒、转给表单负责人，审批还可设自动同意。
-   **"这一步时记录显示为"**（如待审批、借出中）：由当前流程位置派生的显示标签，用于列表与详情，不另建状态机（14.2）。
-   节点只在画布上显示标题和一行摘要；期限、退回、转交等收在面板的可展开小节中。

#### 26.3.4 发布前检查

设计器持续检查并在顶部提示问题数，发布时必须为零：节点没连上或走不到结束；分支条件没填完或有出口没连；没选办理人；某个字段在发起和每一步都看不到或都不能填；显示条件、分支条件、公式或组件引用的字段不存在；公式语法错误、循环依赖或超预算（7.5）；组件的绑定没选字段；管家生成的组件或标题还没确认。

### 26.4 计算公式

-   设计器中公式写作 `天数差(「结束日期」, 「开始日期」) + 1` 这样的形式：字段用「显示名」引用，函数用本地化名称。保存时是字段 ID 与规范函数名（ExpressionDefinition）；字段改名后公式仍有效，显示名随之更新（FW18）。
-   值的语义：日期按天、时间按小时参与运算，两个日期相减得到相差天数。
-   首批函数：天数差；工作日数（含首尾，按考勤工作日历计算，没有日历时按周一至周五）；小时差（结束早于开始时按跨夜计算）；求和（明细表某列或多个字段）；如果；四舍五入。单位与小数位是显示属性，不改变保存值。
-   浏览器中的计算只用于即时显示。Command 执行时服务端按同一 ExpressionDefinition 重算，客户端提交的计算值不被采信（7.6，FW15）。
-   设计器提供试算：修改示例值即时看到结果；公式错误时指出具体原因（找不到字段、括号不完整、引用了自己等），并列入发布前检查。

### 26.5 HTML 组件

**定位。** HTML 组件是表单设计者为表单写的界面与交互，例如签名板、星级评分、实时汇总提示、规则说明、填写校验提示、随填写内容变化的表单标题。填写人从不编写 HTML；填写人需要写带格式的内容时，用"文本"的"允许格式"。

**只有一种组件。** 组件是否保存值、是否显示内容、是否会拦截提交，由代码使用的接口自动判断，并在设计器中写明"它会：……"，不要求设计者预先选择类别。对应关系：

-   只显示：Presentation 中的 HTMLBlock（7.2）。
-   保存一个值：带自定义渲染的 InputField，值类型在组件上声明；图片一类的值存为 Asset，经 AttachmentRef 关联，不把图片数据写入 JSONB。
-   只做逻辑：填写时不显示，字段变化时运行，结果作为交互提示（见下文"拦截提交"）。
-   表单标题也可以用 HTML 组件编写，只读数据，不能写字段。

**绑定（ComponentBinding）。** 组件代码通过"绑定名"引用字段，例如 `form.get('日期')`。一个绑定名可以按顺序绑定任意多个字段，例如"日期先后校验"把开始日期、结束日期、返岗日期依次绑在"日期"上，依次检查后一个不早于前一个。绑定保存为字段 ID，字段改名不影响；代码中出现尚未绑定、也不是字段名的名字时，设计器自动列出等待选择字段。组件库中的组件因此可以在不同表单复用。

**接口。** 组件只能通过消息接口与页面交换数据：读取 `get` / `list` / `label` / `labels` / `all`，写入 `set` / `setValue`，订阅 `on('change')`，提示 `error`。

**运行与权限。**

-   组件运行在独立 Origin 的 sandboxed iframe 中，CSP 禁止网络与外部资源；页面校验消息来源与结构，组件取不到主站凭据，也访问不到父页面（8 L2，21；FW17）。
-   **可读范围是页面内的全部数据**，即当前用户在当前 TaskView 下已经下发到页面的字段。被 Field Policy 隐藏的字段服务端不下发，组件同样读不到。
-   **写入受当前步骤的 Field Policy 限制**：只读、隐藏、计算和自动记下时间的字段写不进去。服务端执行 Command 时再按 Field Policy 校验；组件写入的值与用户输入同等对待，Provenance 记录组件与其版本（FW16）。
-   **拦截提交只作用于填写界面**，属于交互提示，不是权威校验。需要成为 Command 前置条件的规则，必须用 L0 Validation（或 G-ISO 之后的 L1 脚本）表达；设计器在组件使用拦截时提示这一点。
-   组件代码随 FormRelease 冻结为 ComponentRelease。组件库中的组件更新不影响已发布表单，须由负责人升级并重新发布（FW19）。

**编写。** 组件可以手写，也可以让智能管家按一句描述生成。管家生成的组件在设计者确认前不能发布（26.3.4），Provenance 记 AGENT。编辑器提供实时预览、"这一页的数据"示例值与读写记录，并按代码自动列出组件读写的字段。

**运行出错。** 组件在预览、试填或填写中运行出错时，进入统一报错卡（Shell 9.5），报错带组件引用与出错行。设计者可让管家分析（智能管家 19.6）：管家定位到组件和行，设计者有编辑权限时可在草稿里修改（组件代码属于表单配置），改完重新运行确认不再报错；填写人遇到时按配置问题上报给表单负责人。表单设计器声明可读视图与页面动作（字段、分区、流程步骤可被管家查看与在草稿里修改，ADR-024）。

**开放顺序。**

1.  第一步只提供平台内置、经过审查的官方组件，如签名板、星级评分、日期先后校验、实时汇总、规则说明、标题横幅。这些组件是平台自己的前端实现，不执行用户代码，放在阶段二（25）。
2.  第二步开放手写与管家生成，前提是插件体系第 2 节登记的 HTML Block 宿主协议发布并通过验收，放在阶段三（25）。组件库的提交与审核流程在第二步之前确定。

### 26.6 记录页与记录的查看、修改

表单收上来的全部记录在表单平台的记录页中逐条列出、查询和处理；跨表单、跨领域的关联与分析在数据处理平台进行，记录页提供跳转。记录页直接查询 BusinessRecord，按下列设置裁剪，不经数据处理同步。

每张表单在设计器"设置"中配置以下四项，新建表单时取默认值：

| 设置 | 选项 | 默认 | 对应 |
| --- | --- | --- | --- |
| 谁能看记录 | 只看自己的 / 本部门 / 所有能填的人 / 指定人或分组；另可勾选在他人记录中不显示的敏感字段 | 所有能填的人 | Record Scope（15）；敏感字段为查看用 TaskView 的 Field Policy（Hidden / Masked） |
| 谁能改已提交的记录 | 提交人和负责人 / 只有负责人 / 所有能看的人（协作） | 提交人和负责人 | Correct Command 的权限（12.3、15）；负责人始终可改，故不设"只有提交人" |
| 什么时候能改 | 提交后随时 / 只在生效前 / 提交后 N 天内 | 提交后随时 | Correct Command 的前置条件；限制只对负责人以外的人生效 |
| 有流程的表单改了已生效的记录 | 重新走流程 / 直接生效并通知提交人和处理过的人 | 重新走流程 | 修改后发起新的 WorkflowInstance，或只发通知；表单没有流程时不出现 |

-   表单负责人对本表单的全部记录可以修改、退回（写意见）、作废（写理由，可恢复）、催办、转交当前步骤，不受上表"谁能改""什么时候能改"限制。
-   能看到不止自己记录的人，在记录页自己切换"全部 / 我提交的"，页面记住上次选择；看不到别人记录的人只有"我提交的"。
-   查看记录时能看到哪些字段，由查看设置决定，不沿用流程中某一步的办理权限：办理权限管"办理这一步时看到什么"，查看设置管"翻记录时看到什么"。无权查看的字段整列不显示，不显示为空值。
-   别人的记录默认只读；字段可以进一步限制谁能改（如检验结果只允许质检员更正）。
-   审批进行中的记录不能直接修改，须先撤回（负责人为"收回"），当前处理人的待办随之撤销，保存后从头重新走流程；此项不开放设置，避免审批人看到的内容在审批中被替换。
-   每次修改是一次 Correct，形成新 Revision，记录修改人、时间、理由（每次必填）以及修改前后的值（13.1）；记录页显示修改次数并可对比各版本。两人同时修改同一记录时，后保存者得到冲突提示与差异，不静默覆盖（13.3）。作废使用 Void，不物理删除（13.2）。

-   记录页列表：一条记录一行，明细子表默认折叠（显示"N 项 · M 项不合格"，点开展开），可切换为明细逐行（主字段每行重复，便于按明细筛选与导出）。流程中的记录显示当前步骤、处理人和到达时间，不显示"已停留时长"。
-   首期筛选为状态标签、常用字段筛选、搜索与列设置；保存视图、任意条件组合放到后续阶段。导出范围等于当前筛选结果与显示的列，明细子表放在单独工作表，超过 5000 行后台生成并在待办中提醒下载。

### 26.7 待确认事项

以下几项按原型的做法写入；2026-10-18 维护者确认其中第 2、4 项（ADR-032）：显示条件不成立的分区不保存其值；HTML 组件读页面全部已下发数据、写入受本步字段权限限制。其余待确认：

-   创建表单权限的默认人群：表单管理员与部门负责人。
-   显示条件不成立的分区：提交时不保存其中的值，已填的值只留在草稿中（26.3.2）。
-   流程画布左侧固定"发起人提交"作为起点（Start）的表现方式。
-   HTML 组件的写入受当前步骤 Field Policy 限制。维护者的要求是组件可以使用页面内的全部数据；写入限制是为保持 Field Policy 有效而加的约束。
-   组件库的审核人与审核流程。
