# shared/base（架构独占）

前端的公共基础：请求客户端、生成的常量与类型（`@titanloom/reg`）、格式化（Intl）、令牌。领域目录不得自带同类实现（开发项目划分规范 5.5）。
Shell 项目的公共组件（没有权限与申请、统一报错卡、选取器、Markdown / Mermaid、确认卡）放在 `apps/web/src/shared/` 其余位置，由 shell 工作包按架构给的接口写。
