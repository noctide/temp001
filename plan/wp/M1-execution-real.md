---
id: M1-execution-real
project: execution
title: 底座真实实现 · 命令与任务（execution）+ 后台程序
status: 待派
agent: null
depends: [M1 底座接口与测试桩（已通过，review/arch/）]
size: 整个项目，分 5 个阶段
stage: 0
started: null
---
## 目标

把 `execution.api` 从测试桩换成真实实现：命令与防重复落库、发件箱、后台任务的持久队列与 Runner（租约、心跳、fencing）、定时、核对。M1 出口里"重复命令、响应丢失、进程中断后无重复副作用""周期任务重启后不重复触发""JobRun 成功不等于领域成功"由本包负责。

## 必读（按顺序）

1. 仓库根 `AGENTS.md`、`apps/api/titanloom/execution/AGENTS.md`
2. **《后端详细设计 · 命令与任务》全文**（第 14 节是表、轮转、子进程、核对、定时、验收要点）
3. `plan/REVIEW.md` 第 6 节（execution 已确认的接口决定）、`review/arch/M1-底座审核记录.md`（桩审出的坑：未提交事件不能投递、没登记版本校验器要报错……）
4. 现有代码：`execution/api/`（接口、桩 `testing.py`）及其测试；`kernel/db.py`、`kernel/idem.py`、`kernel/ids.py`
5. 契约：command、invocation、confirmation、idempotency-record、execution-binding、job-run、job-attempt、schedule-rule、trigger-occurrence、outbox-event、reconcile-case；`state-machines.json`；`test_contracts_part10.py`

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
| 1 | 表与迁移（第 14 节全部表）；`register_binding` / `version_validator` 等登记 | 迁移从空库成功；再 revision 为空 |
| 2 | `prepare` / `confirm` / `submit` / `run` / `cancel` 落库：防重复（同键同摘要返回原命令、不同摘要冲突）、确认一次性、版本校验；`enqueue_in_tx` / `emit_in_tx` 在调用方事务里写 job_run、outbox_event | 并发两次 submit 只产生一个调用（真库两个连接实测）；准备后版本变化提交被拒；管家不能确认 |
| 3 | 发件箱投递与 `subscribe`：只投递已提交的，consumed_event 去重，至少一次；`redeliver` 在真实一侧用"重置游标"实现 | 重投不重复处理；回滚的事件不投递 |
| 4 | 后台程序：`titanloom/execution/runner/` 里的领取循环（轻道 / 重道、`FOR UPDATE SKIP LOCKED`、按范围轮转、排队上限、租约 30 秒、心跳 5 秒、fencing token、重道子进程限额）、取消、重试（3 次）、核对（reconciling → 人工）；`get_job` | 旧 fencing token 写入被拒；原进程存活不回收租约；重道无饥饿；超排队上限明确拒绝；不确定不自动重发 |
| 5 | 定时：`schedule` 系列 + 控制服务（业务时区、每 15 秒检查、错过不补跑并记账、同一计划时刻只放一件）；`api/real.py` 的 `install(engine)` | 重启后不重复触发；全部行为测试 real 一侧通过 |

## 允许修改的路径

`apps/api/titanloom/execution/`、`i18n/execution.yaml`。<!-- allow: apps/api/titanloom/runner.py -->
`apps/api/titanloom/runner.py` 也可以改：只改成调用 `titanloom.execution.runner` 的入口，逻辑放在 execution 里。

## 不做的事

- 运行中心页面与 `/api/admin/runs` 等管理接口（后台 P2 的事）。
- 不改 main.py、kernel、契约、别的模块。

## 审核记录

（审核意见写在这里）
