## 1. 项目初始化与环境配置

- [x] 1.1 创建 `src/` 目录结构：`main.py`、`overleaf/`、`storage/`、`gui/panels/`、`config/`，各包含 `__init__.py`
- [x] 1.2 创建 `requirements.txt`，列出 `flet`、`requests`、`pymupdf`（PyMuPDF）及版本约束
- [x] 1.3 执行 `pip install -r requirements.txt` 安装所有依赖，验证无冲突

## 2. 配置管理模块（config/settings_manager.py）

- [x] 2.1 实现 `SettingsManager` 类，从 `~/.overleaves/config.json` 读取配置（文件不存在时返回空配置）
- [x] 2.2 实现 `save()` 方法，将配置写入 `~/.overleaves/config.json`（UTF-8 JSON）
- [x] 2.3 实现配置文件格式损坏时的降级处理：捕获 `json.JSONDecodeError`，以空配置继续运行并记录警告日志

## 3. 本地存储模块（storage/local_storage.py）

- [x] 3.1 实现 `LocalStorage` 类，初始化时自动创建 `~/.overleaves/projects/` 目录
- [x] 3.2 实现 `save_file(project_id, relative_path, content)` 方法，支持 str（UTF-8）和 bytes 两种类型
- [x] 3.3 实现 `read_file(project_id, relative_path)` 方法，文件不存在时抛出 `FileNotFoundError`
- [x] 3.4 实现 `save_pdf(project_id, pdf_bytes)` 方法，保存到 `output.pdf`，返回绝对路径
- [x] 3.5 实现 `list_projects()` 方法，列出所有已缓存项目 ID

## 4. Overleaf HTTP 客户端（overleaf/client.py）

- [x] 4.1 定义自定义异常：`OverleafAuthError`、`OverleafNotFoundError`、`OverleafNetworkError`、`OverleafCompileTimeoutError`
- [x] 4.2 实现 `OverleafClient.__init__(cookie: str)`，Cookie 为空时抛出 `ValueError`；初始化 `requests.Session`，设置 Cookie Header，日志中 Cookie 值替换为 `[REDACTED]`
- [x] 4.3 实现 `get_file_tree(project_id)` 方法，GET 项目页面解析 `rootFolder` 数据，返回嵌套文件树结构；HTTP 401/302 时抛出 `OverleafAuthError`
- [x] 4.4 实现 `download_file(project_id, node)` 方法，区分 doc 类型（返回 str）和 file 类型（返回 bytes）；网络错误抛出 `OverleafNetworkError`
- [x] 4.5 实现 `compile_project(project_id)` 方法，POST 编译请求，超时 60s 抛出 `OverleafCompileTimeoutError`，返回编译状态和日志
- [x] 4.6 实现 `download_pdf(project_id, local_path)` 方法，GET 下载 PDF 到指定路径；404 时抛出 `OverleafNotFoundError`

## 5. GUI 设置页面（gui/settings.py）

- [x] 5.1 实现 `SettingsPage` Flet 视图，包含：Overleaf Cookie 输入框（password=True）、项目 ID 输入框、LLM API Key 输入框（password=True）、LLM endpoint 输入框
- [x] 5.2 实现“保存”按鈕点击逻辑，调用 `SettingsManager.save()` 持久化配置
- [x] 5.3 页面加载时从 `SettingsManager` 读取已有配置填充各输入框

## 6. GUI 文件树面板（gui/panels/file_tree.py）

- [x] 6.1 实现 `FileTreePanel`，接收文件树数据，渲染为可展开/折叠的层级列表
- [x] 6.2 实现文件节点点击回调，触发中间面板加载对应文件内容
- [x] 6.3 实现无数据状态：显示“请先拉取远程项目”提示

## 7. GUI TeX 内容面板（gui/panels/tex_viewer.py）

- [x] 7.1 实现 `TexViewerPanel`，使用等宽字体的 `ft.TextField(read_only=True, multiline=True)` 展示文件内容，支持垂直滚动
- [x] 7.2 实现无文件选中状态：显示“请在左侧选择文件”提示
- [x] 7.3 实现 `load_file(content: str)` 方法，更新面板内容

## 8. GUI PDF 预览面板（gui/panels/pdf_viewer.py）

- [x] 8.1 实现 `PdfViewerPanel`，接收 PDF 文件路径，使用 `pymupdf` 将所有页面渲染为 PNG 图片（base64 编码）
- [x] 8.2 用 `ft.Image(src_base64=...)` 列表展示各页，支持垂直滚动
- [x] 8.3 实现无 PDF 状态：显示“请先触发远程编译”提示
- [x] 8.4 实现 `reload(pdf_path)` 方法，重新加载新 PDF

## 9. GUI 主应用框架（gui/app.py & src/main.py）

- [x] 9.1 实现 `main.py`，初始化 Flet 应用，注册路由（`/` 主界面、`/settings` 设置页）
- [x] 9.2 实现主界面三栏布局（`ft.Row` + expand 属性），集成 `FileTreePanel`、`TexViewerPanel`、`PdfViewerPanel`
- [x] 9.3 实现 `ft.AppBar`，包含“拉取远程项目”按鈕、“远程编译并拉取 PDF 显示”按鈕、“设置”入口
- [x] 9.4 实现“拉取远程项目”点击逻辑：检查 Cookie/project_id 配置，后台线程拉取全部文件，完成后刷新文件树，显示/隐藏加载指示器，失败时弹出错误对话框
- [x] 9.5 实现“远程编译并拉取 PDF 显示”点击逻辑：后台线程触发编译、下载 PDF，完成后刷新 PDF 预览，失败时弹出错误信息

## 10. 打包与文档

- [ ] 10.1 创建 `overleaves.spec`（PyInstaller spec 文件），配置 `--onefile --windowed`，处理 pymupdf 的 binaries/datas
- [ ] 10.2 创建 `build.ps1`（Windows PowerShell 打包脚本），执行 `pyinstaller overleaves.spec`
- [ ] 10.3 更新 `README.md`：项目简介、安装依赖步骤（`pip install -r requirements.txt`）、运行方式（`python src/main.py`）、Windows exe 打包步骤（执行 `.\build.ps1`）
- [ ] 10.4 本地执行 `.\build.ps1` 验证打包成功，确认 `dist/overleaves.exe` 可启动
