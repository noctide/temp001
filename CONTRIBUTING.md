# 贡献指南

> 许可证以仓库根目录的 LICENSE 为准。

## 贡献者权利：DCO

本项目采用 Developer Certificate of Origin（DCO）。每个提交须带签署行：

```
git commit -s -m "说明"
```

这表示你声明：该贡献由你创作或你有权按本项目许可证提交，且你同意按 Apache-2.0 授权。不要提交：

- 任何企业的真实数据、模板原件、内部接口细节、凭据或内部文档；
- 你无权授权的第三方代码、素材、字体、模型权重。

测试数据一律使用合成数据。

## 提交前

- 新增依赖须写明许可证，并更新 THIRD_PARTY_NOTICES（发布时生成）。
- 契约与状态机变更须同步 packages/contracts 的 Schema 与测试，必要时新增 ADR。

## 提交前检查

仓库用 [pre-commit](https://pre-commit.com/) 在每次提交前做本地检查，配置见根目录 `.pre-commit-config.yaml`：密钥扫描（gitleaks）、去行尾空格、补文件末尾换行、拦截超过 1 MB 的大文件。

安装（需 Python 3；gitleaks 钩子由 pre-commit 用 Go 工具链编译，本机需有 Go）：

```
pip install pre-commit
pre-commit install
```

`pre-commit install` 会把钩子写进 `.git/hooks`，之后每次 `git commit` 自动先跑这些检查（首次会下载 / 编译钩子运行环境，需要联网）。

在本地跑一遍（只检查、不提交）：

```
pre-commit run --all-files
```

被拦下了怎么办：

- 看输出里是哪个检查失败、涉及哪个文件。
- 密钥扫描（gitleaks）：确认是不是真凭据。示例密钥、占位符也会被识别；确属误报不要硬绕过，联系维护者处理。真实凭据绝不能提交，已泄露的立即吊销并轮换。
- 去行尾空格 / 补末尾换行：钩子一般会自动修正，重新 `git add` 再提交即可。
- 大文件：超过 1 MB 的文件不要塞进仓库，放进制品仓库 / 对象存储，或用 Git LFS。

分支保护（必需检查通过才能合并、禁止强推与删除）由维护者在 GitHub 网页上设置（Settings › Branches），不在本仓库配置。
