# 下一件架构的活：每个模块能单独运行（`tl.py run <模块>`）

> 维护者 2026-10-25 定："所有功能拆开做：表单单独做，做好以后直接运行，运行没问题了再合并。" 选了：① 文件夹分开、能单独跑、底座共用（不拆仓库）；② 单独运行用**真底座 + 本机 PostgreSQL**；③ 审计放仓库 `review/<项目>/`。
> 文件夹与审计这两项架构已做（`projects/<项目>`、`review/`，见 plan/REVIEW.md）。本文件是剩下的"单独运行"，由 code 模式（写底座的会话）做。做完删掉本文件、在 HANDOFF.md 记一笔。

## 要做成什么样

```powershell
cd D:\05_project\02_Titanloom-dev\projects\forms      # 或 hq
uv run python ops/tools/tl.py run forms               # 起后端 + 前端，浏览器只看到表单
uv run python ops/tools/tl.py run forms --smoke       # 自动跑一遍，合并前的门禁
```

1. **后端只装这个模块**：`create_app(modules=["forms"])`（环境变量 `TITANLOOM_MODULES`）。底座（kernel、access、execution、facilities）和 shell（登录、导航）永远装；其余业务模块不装。
   - 约定：每个业务模块在 `api/routes.py` 给 `router: APIRouter` 和可选的 `install()`（登记能力、待办类型、文案、订阅）；`create_app` 只认这个约定，不 import 模块内部。模块清单从 `projects.yaml` 读，不另写一份。
2. **真底座 + 本机库**：启动前自动 `tl db upgrade`（底座 + 这个模块），再跑这个模块的造数据 `<模块>/dev/seed.py`（幂等，只用 `ops/synthetic-data` 的合成人设）。连接串读 `TITANLOOM_DB_URL`，没有就报清楚的错并提示跑 `ops/db/create.ps1`。
   - **底座的真实实现还没做**（现在只有接口 + 测试桩）。在真实实现出来之前，`run` 用测试桩，并且**不能静默**：控制台打一行醒目提示，页面顶上一条横幅"底座为测试桩，数据不落库"；`--bases=stub|real` 可显式指定，`real` 但没有真实实现时直接报错。真实实现出来后默认改为 real。
3. **前端只显示这个模块**：`VITE_TL_MODULES=forms`，导航只留这个模块（加首页占位），路由懒加载 `domains/forms`。每个 domain 的 `index.ts` 导出 `routes`。开发登录用现有 `devSession`（合成人设切换），只在开发模式出现。
4. **`--smoke`（合并门禁）**：
   - 随机端口起后端 → `/api/health` → 这个模块的 `<模块>/dev/smoke.py`（打开列表接口、走一条命令 `execution.run`、查一条审计）；
   - 构建只含这个模块的前端，用 playwright（高保真比对已有）打开它的主页面，截图存 `review/<项目>/run-<日期>.png`；
   - 结果写 `plan/.last-run-<模块>.json`（提交号、通过与否、耗时）；
   - `tl.py wp merge` 合入前检查：这个模块对当前分支头的 smoke 结果必须是通过，否则拒绝合入并提示先跑 `tl.py run <模块> --smoke`。
5. **规则同步**：AGENTS.md 加"每个阶段报告前跑 `tl.py run <模块> --smoke`，把输出贴进报告"；REVIEW.md 第 2 节把 smoke 列为必看证据；`review/README.md` 的格式里已经留了位置。

## 顺序
1. 先做"测试桩模式"的 run + `--smoke` + 合入前检查（小，马上能让考勤、表单 Agent 跑起来看）。
2. 再做底座真实实现（HANDOFF 第 3 节第 6 条），完成后 run 默认切到 real。

## 验收
- 只装 forms 时，`/api/openapi.json` 里没有 attendance 的接口；导航只有表单。
- 没设 `TITANLOOM_DB_URL` 时报清楚的错；测试桩模式页面上有横幅。
- 故意让 smoke 失败（例如 seed 抛错）→ `wp merge` 拒绝合入。
