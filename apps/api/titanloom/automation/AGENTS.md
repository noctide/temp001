# automation 模块 · 执行 Agent 说明

先读仓库根目录 `AGENTS.md`（唯一正本的规则），这里只写本模块的事。本文件由 `tl.py scaffold` 按 `projects.yaml` 生成，改清单请找架构。

- 开发项目：`automation`；分支名 `automation/<工作包编号>`
- 允许修改的路径（工作包可再收窄）：
- `apps/api/titanloom/automation/`
- `apps/web/src/domains/automation/`
- `i18n/automation.yaml`
- 必读（除共同必读外）：工具自动化、平台能力契约#6、平台能力契约#7、平台能力契约#8、集成与消息通道#4、ADR-016
- 共同必读：工程质量与代码规范全文；后端详细设计·总图全文；国际化规范 1–5、7–9；开发项目划分规范 1、2.2、5、6；总框架 4、5；能力契约 2、3、12。
- 本模块登记的业务参数、功能、页面声明写在 `manifest.yaml`；文案键写在 `i18n/` 下本模块的命名空间文件。
