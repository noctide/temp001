---
id: M1-access-real
project: access
title: 底座真实实现 · 身份与权限（access）
status: 待派
agent: null
depends: [M1 底座接口与测试桩（已通过，review/arch/）]
size: 整个项目，分 5 个阶段
stage: 0
started: null
---
## 目标

把 `access.api` 现有的接口（whoami、check、filter、members、memberships、register；`Decision.require`、`sql.to_sqlalchemy`）从测试桩换成**存在 PostgreSQL 里的真实实现**，让各模块单独运行时能用真数据。M1 出口里"撤权后同一调用被拒"由本包负责。

## 必读（按顺序）

1. 仓库根 `AGENTS.md`、`apps/api/titanloom/access/AGENTS.md`
2. **《后端详细设计 · 身份与权限》全文**（第 12 节是表和验收要点）
3. `plan/REVIEW.md` 第 6 节（access 已确认的接口决定）、`review/arch/M1-底座审核记录.md`（桩审出的坑：NULL 与拒绝、遮挡列取并集……真实实现要同一口径）
4. 现有代码：`access/api/`（接口、桩 `testing.py`、`sql.py`）及其测试
5. 契约：`access-decision`、`access-filter`、`grant`、`feature-layer`、`delegation`；`test_contracts_part9.py`

## 三块底座共同的规矩（三份说明书一样）

- **接口不改**：`<底座>/api/__init__.py` 与 `types.py` 里的函数签名、数据类已审核定稿（plan/REVIEW.md 第 6 节）。真实实现只是另一个 provider。确实要改签名：停下，写进 `plan/progress/<编号>.md` 的"变更请求"。
- **同一批行为测试跑两遍**：把现在只测桩的测试，挪成"接口行为测试"，用参数化的 fixture `impl`（`stub` / `real`）各跑一遍（审核手册第 3 节第 3 条）。`real` 要连 PostgreSQL：读 `TITANLOOM_TEST_DB_URL`，没设就跳过。审核时一定会设。只给真实实现补的测试也放进来。
- **真实实现的装入点**：`titanloom/<底座>/api/real.py` 提供 `install(engine) -> Callable[[], None]`，装入 provider，返回"恢复原实现"的函数，形式和测试桩一样。`main.py` 里把 `--bases=real` 接上，是架构另开的小工作包，**不在本包里改 main.py**。
- **表**：只写在 `store/models.py`；迁移用 `uv run python ops/tools/tl.py db revision <底座> -m 说明` 生成，**不手写 SQL**；schema 就是模块名。
- **别的底座**：只经对方的 `api` 用，测试里用对方的测试桩（`access_stub` 等）。三块底座可以同时开工，互不等待。
- **阶段交付**：`tl check` 全过；带库测试在本机 PostgreSQL 上跑过，把输出贴进报告；A1 合入后再加 `tl.py run` 的冒烟检查（底座本身不单独运行，用表单模块 `--bases=real` 验）。

## 阶段（每阶段做完报告一次，审核通过后合入，再做下一阶段）

| 阶段 | 内容 | 验收 |
| --- | --- | --- |
| 1 | 表与迁移：person、employment、org_unit（含 tree_version、有效期）、account、session、capability、role / role_version / role_cell、grant、feature / feature_layer、delegation、policy_revision（只做这几组；人事同步、复核、交接、应急、申请审批的表不做）。`dev/seed.py`：和测试桩 `InMemoryAccess.demo()` 同一份合成小组织 | 迁移从空库一路 upgrade 成功；再 revision 一次是空迁移；种子可重复执行 |
| 2 | `check` / `require`：按设计第 5 节顺序（身份 → 功能开放 → 基础授权 → 管家三道门 → 数据范围）；行为测试改为桩与真实各跑一遍 | 拒绝优先、无允许即拒、管家 ⊆ 本人、功能开放 = 平台 ∩ 层；错误码映射照 REVIEW 第 6 节 |
| 3 | `filter` 与 `to_sqlalchemy` 在真库上；`whoami`、`members`、`memberships`（兼岗、按日期）、`register`（能力、功能、权限字段、可遮挡列） | 属性测试：同一主体与样本数据，filter 查出的行 = 逐条 check 允许的行（含 NULL 字段）；filter 遮挡列 ⊇ 每行 check 的遮挡列 |
| 4 | 撤权与缓存：policy_revision 递增、进程内 LRU（上限 2000 人），撤权 60 秒内判定变化；登录与会话（Argon2id 参数照第 12 节、会话 id 只存哈希、失败计数与锁定）；开发登录（合成人设）保留且只在开发运行开启 | 撤权后同一调用被拒；离职停用后会话全部失效；锁定后 ACCOUNT_LOCKED |
| 5 | `api/real.py` 的 `install(engine)`；性能实测（命中 P95 < 1 ms、未命中 < 15 ms，写进 review 证据） | 用 `install` 装上后，全部行为测试 real 一侧通过 |

## 允许修改的路径

`apps/api/titanloom/access/`、`i18n/access.yaml`（见 projects.yaml）。

## 不做的事

- 人事同步、待核对、复核活动、交接、应急、申请与批准、explain / who_can / find_people / write_grant（以后随后台治理做，那时一次定签名）。
- 管理页面与 HTTP 管理接口（后台 P1 的事）。
- 不改 main.py、kernel、契约、别的模块。

## 审核记录

（审核意见写在这里）
