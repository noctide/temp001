---
id: M1-facilities-real
project: facilities
title: 底座真实实现 · 公共设施（facilities）
status: 待派
agent: null
depends: [M1 底座接口与测试桩（已通过，review/arch/）]
size: 整个项目，分 5 个阶段
stage: 0
started: null
---
## 目标

把 `facilities.api`（审计、待办、通知、文案、文件引用）从测试桩换成真实实现。

## 必读（按顺序）

1. 仓库根 `AGENTS.md`、`apps/api/titanloom/facilities/AGENTS.md`
2. **《后端详细设计 · 公共设施》全文**（第 10 节是表、文件、审计、通知、待办的技术细节与验收要点）
3. `plan/REVIEW.md` 第 6 节、`review/arch/M1-底座审核记录.md` 第 4 步（R4-1 ~ R4-7：blob 层去重、幂等键与合并键分开、审计按对象归属判数据范围、待办按来源版本、通知存发送时的文字与语言包版本、摘要只收 sha256、重开不覆盖旧记录）——**真实实现要同一口径**；记录里"带到真实实现"的几条一并做（通知唯一约束放在幂等键上、合并另算等）
4. 现有代码：`facilities/api/`（接口、桩 `testing.py`）及其测试；`kernel/testing.py` 的 `track_rollback`
5. 契约：audit-event、todo-item、notification、notify-pref、asset-version、asset-ref；`test_contracts_part11.py`

## 三块底座共同的规矩（三份说明书一样）

- **接口不改**：`<底座>/api/__init__.py` 与 `types.py` 里的函数签名、数据类已审核定稿（plan/REVIEW.md 第 6 节）。真实实现只是另一个 provider。确实要改签名：停下，写进 `plan/progress/<编号>.md` 的"变更请求"。
- **同一批行为测试跑两遍**：把现在只测桩的测试，挪成"接口行为测试"，用参数化的 fixture `impl`（`stub` / `real`）各跑一遍（审核手册第 3 节第 3 条）。`real` 要连 PostgreSQL：读 `TITANLOOM_TEST_DB_URL`，没设就跳过。审核时一定会设。只给真实实现补的测试也放进来。
- **真实实现的装入点**：`titanloom/<底座>/api/real.py` 提供 `install(engine) -> Callable[[], None]`，装入 provider，返回"恢复原实现"的函数，形式和测试桩一样。`main.py` 里把 `--bases=real` 接上，是架构另开的小工作包，**不在本包里改 main.py**。
- **表**：只写在 `store/models.py`；迁移用 `uv run python ops/tools/tl.py db revision <底座> -m 说明` 生成，**不手写 SQL**；schema 就是模块名。
- **别的底座**：只经对方的 `api` 用，测试里用对方的测试桩（`access_stub` 等）。三块底座可以同时开工，互不等待。
- **阶段交付**：`tl check` 全过；带库测试在本机 PostgreSQL 上跑过，把输出贴进报告；A1 合入后再加 `tl.py run` 的冒烟检查（底座本身不单独运行，用表单模块 `--bases=real` 验）。

## 阶段

| 阶段 | 内容 | 验收 |
| --- | --- | --- |
| 1 | 表与迁移：audit_event（按月分区、只插入、prev_hash / hash）、audit_anchor、todo_type / todo_item / todo_assignee、notification、notify_pref、语言资源；文件的 asset / asset_version / blob / asset_ref | 迁移从空库成功；运行账号改、删审计被拒（权限层面） |
| 2 | 审计：事务内写入（以链尾锁串行化）、`audit_for`（按对象真实归属判数据范围）、体检校验全链 | 审计与业务同成同败；篡改一条后体检报链断；写入 ≥ 200 条 / 秒（实测记进证据） |
| 3 | 待办：按（类型, 来源, 来源版本）幂等、组待办先办先得、重开保留旧记录；待办事件经 `execution.api.emit_in_tx` 发出 | 组待办一人办完其余显示已由他处理；重开后旧的仍在 |
| 4 | 通知（幂等键唯一约束 + 5 分钟合并 + 收件人可见性筛选 + 存发送时文字与语言包版本）；文案（登记、按语言取、语言包版本） | 看不到对象的人收不到；5 分钟内同类合并；重投不加计数；改文案后旧通知不变 |
| 5 | 文件引用与下载授权（blob 去重 + 引用计数、跟随挂靠对象鉴权、隔离区不可下载）；`api/real.py` 的 `install(engine)` | 同字节两次上传一份 blob、两处引用各自鉴权；无匿名下载；全部行为测试 real 一侧通过 |

## 允许修改的路径

`apps/api/titanloom/facilities/`、`i18n/facilities.yaml`、`i18n/glossary.yaml`。

## 不做的事

- 分片上传、格式嗅探与检查、派生物、孤儿清理、夜间外发与集成通道、通知偏好页面、搜索：后续做（分片上传与检查随文件解析器的工作包一起）。
- 不改 main.py、kernel、契约、别的模块。

## 审核记录

（审核意见写在这里）
