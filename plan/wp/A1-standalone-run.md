---
id: A1-standalone-run
project: arch
title: 架构工程 · 每个模块单独运行（tl.py run）与合并前门禁
status: 待派
agent: null
depends: []
size: 一个阶段（有草稿补丁，约 1000 行改动，大半已写好）
stage: 0
started: null
---
## 目标

维护者 2026-10-25 定："所有功能拆开做：表单单独做，做好以后直接运行，运行没问题了再合并。"已选：文件夹分开、能单独跑、底座共用（不拆仓库）；单独运行用真底座 + 本机 PostgreSQL（真实实现做出来之前先用测试桩，且必须明示）；审计证据放仓库 `review/<项目>/`。

文件夹与审计两项已经做完（`projects/<项目>`、`review/`）。本工作包做剩下的"单独运行"：

```powershell
uv run python ops/tools/tl.py here                 # 执行 Agent 打开项目文件夹后先跑：我是哪个项目、先做什么
uv run python ops/tools/tl.py run forms            # 起后端（只装 forms + 底座 + 外壳）和前端，浏览器只看到表单
uv run python ops/tools/tl.py run forms --smoke    # 自动检查；tl.py wp merge 合入前在正本上自动跑，不过就撤销合并
```

## 起点：草稿补丁

架构已经写了大半，放在 `plan/wp/A1-standalone-run.patch`。先在你的文件夹里应用：

```powershell
git merge local/integration
git apply plan/wp/A1-standalone-run.patch
```

补丁里有：
- `apps/api/titanloom/main.py`：`create_app(modules, bases)`（工厂方式，导入不装任何东西）；模块接入约定 `<模块>/api/routes.py`（`router`、`install()`）、`dev/seed.py`（`seed()`）、`dev/smoke.py`（`smoke(client)`）；底座测试桩装入与 `restore`；开发运行的合成人设登录（`?role=` / `X-TL-Role`）；`/api/platform/run-info`。
- `apps/api/titanloom/kernel/tests/test_app.py`：上面这些的测试（7 条）。
- `ops/tools/run.py`（新）与 `tl.py run` / `tl.py here`；`wp.py` 的 `here()`、`_run_gate()`（合入前门禁）、启动指令里加 smoke 要求。
- 前端：`shell/nav.ts` 的 `MODULE_NAV`、`navFor()`；`shell/runInfo.ts`（新）；`App.tsx` 按装了的模块裁导航、测试桩时显示横幅；`AppShell.tsx` 收 `nav`；`vite.config.ts` 代理端口读 `TL_API_PORT`；文案键 `shell.run.stubBanner`（已 `tl.py gen`）。
- `AGENTS.md`：打开文件夹先跑 `tl.py here`；每阶段交之前 `tl check` + `tl.py run <模块> --smoke`，两条输出都贴；模块接入约定。
- `pyproject.toml`：`ops/tools/**` 忽略 S603 / S607（工具要调 git、uv 等本机命令），顺带去掉了几处多余的 `noqa`。

架构在 VM 上验证过：后端 7 条测试过；10 个业务模块 `--smoke` 都过；前端 tsc 过、vitest 372 个过；`tl.py run forms` 实际起来，`/api/platform/run-info` 经前端代理返回 `{"modules":["forms"],"bases":"stub"}`。**没做的是浏览器截图**（VM 装不了浏览器）。

## 必须修的（补丁应用后 `tl check` 有两项不过）

1. **类型检查**：`kernel/tests/test_app.py` 第 77 行的 lambda 参数没标类型（pyright strict 3 处报错）。改成有类型的普通函数。
2. **模块边界**：`kernel/tests/test_app.py` 在 kernel 里，却 import 了 `titanloom.main`，而 main 又 import 了各底座的 `api.testing`，违反"kernel 不依赖模块"。把这个测试移出 kernel，比如移到 `apps/api/tests/test_main.py`，并确认 pytest 能收集到；然后看 import-linter 是否还对 `titanloom.main` 有意见，有就在 `ops/tools` 生成边界规则时把 `titanloom.main` 当作装配点放行（只放行 main，不放宽别的）。

## 还要做的

3. **在 Windows 上实跑一遍**：`tl.py run forms` 打开浏览器，确认导航只剩"首页、表单"，顶上有黄色横幅；`?role=zym` 换人；Ctrl+C 能把前后端都停掉（`serve()` 在 Windows 上用 `CTRL_BREAK_EVENT`，没实测过，停不干净就改成 `taskkill /T` 或 `CREATE_NEW_PROCESS_GROUP`）。截图存进 `review/arch/A1-run-forms.png`。
4. **合并门禁实测**：在临时分支里让某模块的 `dev/smoke.py` 抛错，`tl.py wp merge <编号> --keep` 应该拒绝并撤销合并；squash 收尾那条路径同样测一下。
5. **`tl.py here` 实测**：在 `projects\attendance`、`projects\forms` 里各跑一次（它们落后正本，应该先提示 merge）；在 hq 里跑应提示"不是工作区"。
6. `README.md` 的启动方式、`plan/REVIEW.md` 第 2 节第 5 条（单独运行）与实际命令一致。

## 不做的事

- 底座真实实现（另一件活）；真实实现出来后 `--bases` 默认改 real、run 之前自动 `tl db upgrade`，到时另开工作包。
- `--smoke` 里的 playwright 截图：等领域页面做出来再加。

## 验收

- `tl check` 全过（含类型、边界、前端）。
- 只装 forms 时 openapi 里没有别的业务模块的接口；导航只有首页和表单；测试桩模式页面有横幅。
- 故意让 smoke 失败 → `wp merge` 拒绝合入、hq 回到合并前的状态。
- 在 projects 里跑 `tl.py here` 给出正确提示。

## 审核记录

（架构审核意见写在这里）
