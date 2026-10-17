# Titanloom

Titanloom 是一个面向企业场景设计的综合数据与业务平台，覆盖表单平台、考勤签到、工具自动化、数据处理、知识与文档、数据可视化，以及统一门户、后台治理、插件扩展、集成与消息通道和平台级 Agent。

**状态：M0 工程骨架（2026-10-17 起），尚无业务功能。** 当前内容是设计基线 V1.0：设计文档、契约 JSON Schema 草案及其测试。文中标为"拟定"的接口细节在 M0 / M1 编写契约时最终确认；待决事项及其默认做法见实施路线第 7 节。文档版本不代表软件发行版，也不表示性能已验收或安全已评审。

## 目录

| 路径 | 内容 |
| --- | --- |
| `docs/` | 总框架、公共规范（含工程质量与代码规范）、公共平台能力、各业务域子方案、架构决策记录、实施路线、变更记录 |
| `apps/api/` | 主程序与后台程序（FastAPI 模块化单体）；`titanloom/<模块>/` 各分 api · app · domain · store 四层，`kernel/` 是公共内核 |
| `apps/web/` | 门户与各领域前端（React + TypeScript + Vite） |
| `packages/contracts/` | 契约 JSON Schema、状态机、错误码注册表、示例与测试（原 `titanloom-contracts/`） |
| `i18n/` | 文案键清单与出厂默认文案，每个命名空间一个文件 |
| `ops/` | 合成数据、工具（`ops/tools/tl.py`）、部署与性能脚本 |
| `plan/` | 工作包、进度、代码地图 |
| `projects.yaml` | 开发项目清单：每个项目的目录、允许路径、必读 |

建议从 `docs/Titanloom-总框架设计方案-V1.0.md` 与 `docs/Titanloom-实施路线与首期工程基线-V1.0.md` 开始阅读；编写代码前请阅读 `docs/Titanloom-工程质量与代码规范-V1.0.md` 、`docs/Titanloom-开发项目划分与多Agent协作规范-V1.0.md`、`docs/Titanloom-后端详细设计-总图-V1.0.md` 与 `docs/Titanloom-国际化与本地化规范-V1.0.md`。

## 开发环境

需要 Python 3.12（用 [uv](https://docs.astral.sh/uv/) 管理）、Node 22 与 pnpm 9、PostgreSQL 16。

```
uv sync                                        # 后端依赖
uv run pytest                                  # 后端测试
uv run uvicorn titanloom.main:app --reload     # 启动空应用：http://127.0.0.1:8000/api/health
pnpm install && pnpm dev                       # 前端
uv run python ops/tools/tl.py check            # 全套检查
```

执行 Agent 的规则见 `AGENTS.md`。

## 运行契约测试

需要 Python 3 与 `jsonschema`：

```
pip install jsonschema
cd packages/contracts
for t in test_contracts*.py; do python3 "$t" || exit 1; done
```

## 许可证

本项目以 [Apache License 2.0](LICENSE) 发布。

Copyright 2026 Titanloom contributors

第三方组件及其许可证见 THIRD_PARTY_NOTICES.md。贡献方式见 CONTRIBUTING.md，安全问题的报告方式见 SECURITY.md。
