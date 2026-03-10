## Why

Overleaves 是一款跨平台论文写作 agent 工具，目前尚无任何代码实现。用户需要能够从 Overleaf 平台拉取项目文件、在本地 GUI 中查看和编辑 TeX 文件、触发远程编译并预览 PDF，这是整个 agent 工具的基础功能入口，必须首先完成。

## What Changes

- **新增** 基于 Cookie 的 Overleaf 项目拉取模块（仿照 olcli 实现）
- **新增** Overleaf 远程编译触发 + PDF 下载模块
- **新增** Flet 三栏 GUI 主界面（文件树 / TeX 内容 / PDF 预览）
- **新增** 菜单功能："拉取远程项目"、"远程编译并拉取 PDF 显示"
- **新增** 设置页面：支持配置 Overleaf Cookie 和 LLM agent 参数
- **新增** Python 项目初始化：依赖管理（requirements.txt）、打包为 exe（PyInstaller）
- **新增** README：项目说明 + Windows exe 编译步骤

## Capabilities

### New Capabilities

- `overleaf-client`：基于 Cookie 的 Overleaf HTTP 客户端，支持项目文件列表获取、单文件内容下载、触发编译、下载编译产出 PDF
- `local-storage`：将拉取到的项目文件和 PDF 缓存到本地，维护项目文件树结构
- `gui-main`：Flet 三栏主界面，左侧文件树、中间 TeX 内容展示、右侧 PDF 预览
- `gui-settings`：设置页面，支持持久化保存 Overleaf Cookie、LLM API 配置等参数
- `project-packaging`：Python 项目结构、依赖安装、PyInstaller 打包 exe

### Modified Capabilities

（无，当前为全新项目，无已有 spec）

## Impact

- **代码**：全新项目，从零创建 `src/` 目录及所有模块
- **依赖**：flet、requests、httpx（或 requests）、pymupdf（PDF 渲染）、pyinstaller（打包）
- **平台**：主要在 Windows 上开发和测试，Flet 本身支持 macOS/Linux 跨平台
- **外部系统**：依赖 Overleaf 平台的 HTTP API（非官方，基于 Cookie session）

---

## 澄清问题清单

### 阻断级

无阻断级问题。

### 非阻断级

| # | 问题 | 默认决策 | 理由 |
|---|------|----------|------|
| 1 | PDF 渲染库选型 | 使用 `pymupdf`（fitz）将 PDF 页渲染为图片后在 Flet Image 控件中展示 | flet 当前无原生 PDF 控件，pymupdf 性能好且跨平台 |
| 2 | TeX 文件内容展示是否只读 | 第一阶段只读（只显示内容），编辑功能后续迭代 | 符合本次"拉取与预览"范围，降低复杂度 |
| 3 | Cookie 存储方式 | 明文保存到用户本地 `~/.overleaves/config.json`，日志中脱敏 | 简单可行，后续可升级为系统密钥环 |
| 4 | 项目文件本地缓存路径 | `~/.overleaves/projects/<project_id>/` | 与配置目录统一，便于清理 |
| 5 | exe 打包工具 | PyInstaller（`--onefile`） | 最成熟的 Python Windows 打包方案 |

## 决策记录

- **PDF 渲染**：pymupdf 渲染为图片 → Flet Image 展示（非原生 PDF 组件）
- **第一阶段 TeX 只读**：不实现编辑器功能，只做内容展示
- **Cookie 明文存储**：`~/.overleaves/config.json`，禁止写入日志
- **本地缓存**：`~/.overleaves/projects/<project_id>/`
- **打包**：PyInstaller `--onefile`
