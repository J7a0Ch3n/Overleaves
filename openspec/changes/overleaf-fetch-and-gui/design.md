## Context

当前 Overleaves 项目为空仓库，无任何代码实现。本次设计目标是从零建立整个工具的基础骨架：

- **外部依赖**：Overleaf 平台的非官方 HTTP API（基于浏览器 Cookie session，参考 olcli 实现）
- **约束**：
  - Overleaf 无官方开放 API，只能逆向浏览器 HTTP 请求
  - PDF 在 Flet 中无原生支持，需借助第三方渲染
  - 主要在 Windows 开发，需打包为独立 exe

## Goals / Non-Goals

**Goals:**
- 实现基于 Cookie 的 Overleaf 项目文件拉取（文件列表 + 文件内容下载）
- 实现 Overleaf 远程编译触发 + PDF 下载
- 实现 Flet 三栏主界面（文件树 / TeX 只读展示 / PDF 预览）
- 实现设置页面（Cookie、LLM 配置持久化）
- 完成 Python 项目结构、依赖管理、PyInstaller 打包配置
- 编写 README（含 exe 编译步骤）

**Non-Goals:**
- TeX 文件编辑功能（只读展示，编辑留后续迭代）
- LLM agent 实际调用（设置页面保存配置即可，agent 功能后续迭代）
- 多平台同步测试（macOS/Linux 兼容性留后续）
- 官方 Overleaf API 对接

## Decisions

### 1. 目录结构

```
overleaves/
├── src/
│   ├── main.py                  # Flet 应用入口
│   ├── overleaf/
│   │   ├── client.py            # Overleaf HTTP 客户端（Cookie auth）
│   │   └── compiler.py          # 触发编译 + 下载 PDF
│   ├── storage/
│   │   └── local_storage.py     # 本地文件缓存（~/.overleaves/projects/）
│   ├── gui/
│   │   ├── app.py               # 主应用框架（路由、布局）
│   │   ├── panels/
│   │   │   ├── file_tree.py     # 左侧文件树面板
│   │   │   ├── tex_viewer.py    # 中间 TeX 内容面板
│   │   │   └── pdf_viewer.py    # 右侧 PDF 预览面板
│   │   └── settings.py          # 设置页面
│   └── config/
│       └── settings_manager.py  # 配置读写（~/.overleaves/config.json）
├── requirements.txt
├── build.ps1                    # Windows exe 打包脚本
└── README.md
```

**选择理由**：按功能领域分层，`overleaf/` 专注 HTTP 交互，`gui/` 专注界面，`storage/` 专注本地数据，`config/` 管理配置，边界清晰，便于后续扩展 agent 模块。

---

### 2. Overleaf 客户端实现方案

**选择**：`requests` 库 + Session（携带 Cookie）

**替代方案**：`httpx`（异步），但 Flet 本身使用 `asyncio`，如引入 httpx 异步需要额外的线程调度适配。为降低初期复杂度，使用 `requests` 在独立线程中运行（Flet `threading` 调用），后续可迁移到 httpx。

**Overleaf API 端点**（参考 olcli）：
| 操作 | 方法 | 路径 |
|------|------|------|
| 获取项目列表 | GET | `/api/v1/project` （实际为 `/project`，解析 HTML 或 JSON） |
| 获取文件树 | GET | `/project/<id>` → 解析 `window.data` 中的 `rootFolder` |
| 下载单文件 | GET | `/project/<id>/file/<file_id>` 或 `/project/<id>/doc/<doc_id>/raw` |
| 触发编译 | POST | `/project/<id>/compile` |
| 下载 PDF | GET | `/project/<id>/output/output.pdf` |

---

### 3. PDF 渲染方案

**选择**：`pymupdf`（PyMuPDF，`import fitz`）将 PDF 各页渲染为 PNG 图片，Flet `Image` 控件展示

**替代方案**：调用系统 PDF 阅读器（`subprocess`），但无法嵌入 GUI，用户体验割裂。

**实现思路**：
- 打开 PDF 文件，遍历页面，按当前面板宽度缩放渲染为 `bytes`
- 以 `base64` 或临时文件方式传入 Flet `Image(src_base64=...)`
- 支持上下翻页（第一阶段只显示第一页或全页滚动）

---

### 4. 配置持久化

**选择**：`~/.overleaves/config.json`，使用 Python 标准库 `json` 读写

**安全约束**：Cookie 值不写入任何日志（日志中以 `[REDACTED]` 替代）

---

### 5. GUI 框架与布局

**Flet 布局方案**：
- `ft.Row` 包裹三个 `ft.Column`，使用 `expand` 属性按比例分配宽度（2:3:3 或可拖拽）
- 菜单使用 `ft.AppBar` + 按钮或 `ft.PopupMenuButton`
- 设置页通过路由 `page.go("/settings")` 切换

---

### 6. 打包方案

**选择**：PyInstaller + `--onefile --windowed`

**spec 文件**：提供 `overleaves.spec` 以精确控制打包资源

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| Overleaf 非官方 API 随时可能变更 | 将所有 API 端点集中在 `client.py`，便于定点修复 |
| Cookie 过期导致请求失败 | 捕获 401/302 响应，显示明确错误信息，引导用户更新 Cookie |
| pymupdf 在 PyInstaller 打包时可能缺失动态库 | 在 `overleaves.spec` 中手动指定 `fitz` 的 binaries 和 datas |
| Flet 大文本展示性能 | 第一阶段 TeX 文件以 `TextField(read_only=True)` 展示，内容超大时分页加载 |
| Windows 路径编码问题 | 统一使用 `pathlib.Path` 处理路径，避免字符串拼接 |

## Open Questions

（无，已通过 proposal 决策记录覆盖所有非阻断级问题）
