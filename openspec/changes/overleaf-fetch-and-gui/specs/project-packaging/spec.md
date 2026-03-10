## ADDED Requirements

### Requirement: Python 项目目录结构
系统 SHALL 按 design.md 定义的目录结构组织代码，`src/` 中包含 `main.py`、`overleaf/`、`storage/`、`gui/`、`config/` 子包，各子包含 `__init__.py`。

#### Scenario: 目录结构符合规范
- **WHEN** 代码仓库初始化完成
- **THEN** `src/` 下 SHALL 存在 `main.py` 以及 `overleaf/`、`storage/`、`gui/panels/`、`config/` 目录，各目录含 `__init__.py`

---

### Requirement: 依赖管理（requirements.txt）
系统 SHALL 提供 `requirements.txt` 文件，列出所有运行时依赖及推荐版本，包含 `flet`、`requests`、`pymupdf`。

#### Scenario: 依赖可通过 pip 安装
- **WHEN** 执行 `pip install -r requirements.txt`
- **THEN** 所有依赖 SHALL 成功安装，无冲突报错

---

### Requirement: PyInstaller 打包为 exe
系统 SHALL 提供 `build.ps1`（Windows PowerShell 脚本）和 `overleaves.spec`（PyInstaller spec 文件），执行后产出单文件 exe（`--onefile --windowed`）。

#### Scenario: 执行打包脚本成功
- **WHEN** 在 Windows 上执行 `.\build.ps1`
- **THEN** `dist/overleaves.exe` SHALL 生成，可独立运行，无需额外 Python 环境

#### Scenario: exe 运行后显示主界面
- **WHEN** 双击 `dist/overleaves.exe`
- **THEN** 应用 SHALL 启动并正确显示三栏主界面

---

### Requirement: README 文档
系统 SHALL 提供 `README.md`，包含：项目简介、安装依赖步骤、运行方式、Windows exe 打包步骤（含截图或命令示例）。

#### Scenario: README 包含 exe 打包说明
- **WHEN** 用户查看 `README.md`
- **THEN** README SHALL 包含"如何打包为 exe"章节，步骤完整可操作，执行后能产出可用 exe
