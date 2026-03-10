# Tasks：多项目管理、界面优化、TeX 编辑与推送 ✅

## Task 1：多项目配置管理（config/settings_manager.py）✅

**目标**：扩展 `SettingsManager` 支持多项目配置存储，并向后兼容旧配置。

**影响范围**：`src/config/settings_manager.py`

**实施要点**：
- 新增属性：`current_project_id`、`projects`（dict）
- 新增方法：`add_project(project_id, cookie, name="")`、`switch_project(project_id)`、`current_cookie`（属性）
- 启动时迁移逻辑：若 `projects` 不存在但 `cookie`/`project_id` 存在，自动合并

**验收标准**：
- `SettingsManager` 可正确读写多项目配置
- 旧配置格式（只有 `cookie`/`project_id`）加载后自动迁移，不丢数据

**验证方法**：手动用旧配置文件启动应用，验证迁移结果；新建项目后保存配置文件检查结构

---

## Task 2：本地缓存元数据（storage/local_storage.py）

**目标**：`LocalStorage` 支持保存/读取项目元数据缓存（entities 列表），实现免网络加载文件树。

**影响范围**：`src/storage/local_storage.py`

**实施要点**：
- 新增 `save_project_meta(project_id, entities, name="")` 方法，写入 `project_meta.json`
- 新增 `load_project_meta(project_id)` 方法，返回 entities 列表（文件不存在返回 None）
- 新增 `project_exists(project_id)` 方法，检查项目缓存目录是否存在

**验收标准**：
- 拉取项目后可保存 meta；下次打开项目时从 meta 恢复文件树

**验证方法**：拉取一次项目，关闭应用后重新打开，检查是否自动加载文件树而无网络请求（通过日志验证）

---

## Task 3：Overleaf 客户端扩展（overleaf/client.py）

**目标**：新增 `upload_file` 方法支持推送文档内容；`get_entities` 透传 `id` 字段。

**影响范围**：`src/overleaf/client.py`

**实施要点**：
- 修改 `get_entities()` 返回值：保留原始响应中的 `id` 字段（若有）
- 新增 `upload_file(project_id, doc_id, content: str)` 方法：
  - 获取 CSRF token
  - POST 到 `/project/{project_id}/doc/{doc_id}`，body 为 `{"doc": content.split("\n")}`（Overleaf 分行存储）
  - 统一异常处理

**验收标准**：
- `get_entities` 返回包含 `id` 字段的实体列表
- `upload_file` 可成功向 Overleaf 推送内容，或在失败时抛出明确异常

**验证方法**：启动应用，执行拉取，检查日志中 entities 是否含 `id`；推送测试文档，在 Overleaf 网页端验证内容变更

---

## Task 4：局部刷新优化（gui/app.py）

**目标**：点击文件树节点仅更新中间栏，不触发全页重绘。

**影响范围**：`src/gui/app.py` 中的 `_on_file_select` 方法

**实施要点**：
- `_on_file_select` 中的 `_finish_loading_async` 改为：更新 `tex_viewer` 的 loading 状态后调用 `self._tex_viewer.update()` 而非 `page.update()`
- 注意：`_progress` 在主界面顶部，仍需单独更新（仅更新 progress bar 即可）

**验收标准**：
- 点击文件树切换文件，PDF 预览栏和文件树不发生闪烁或重绘（通过目视观察）

**验证方法**：目视测试，连续点击不同文件观察右栏 PDF 是否闪烁

---

## Task 5：三栏可拖拽与侧栏折叠（gui/app.py）

**目标**：三栏宽度可通过鼠标拖拽调整；左右侧栏可独立折叠/展开。

**影响范围**：`src/gui/app.py`（主要重构 `build()` 方法）

**实施要点**：
- 将三栏切换为 `width` 属性管理（不依赖 `expand`）
- 用 `ft.GestureDetector` 包裹分隔条，监听 `on_pan_update`，拖动时更新两侧栏宽度
- 宽度限制：最小 100px
- 在 AppBar 或面板标题行新增折叠按钮（`ft.IconButton`）：`CHEVRON_LEFT`/`CHEVRON_RIGHT` 图标，点击时 `visible=False/True` + 相应分隔条隐藏

**验收标准**：
- 可通过拖拽调整三栏宽度，拖拽平滑无跳变
- 可独立折叠/展开左栏和右栏

**验证方法**：手动拖拽测试；折叠后单击展开按钮恢复验证

---

## Task 6：TeX 可编辑（gui/panels/tex_viewer.py）

**目标**：中间栏文本文件由只读变为可编辑，并暴露获取当前内容的方法。

**影响范围**：`src/gui/panels/tex_viewer.py`

**实施要点**：
- `_make_text_view()` 将 `TextField` 的 `read_only=False`
- 保存对 `TextField` 实例的引用（`self._text_field`），以便后续 `get_content()` 读取
- 新增 `get_content() -> str` 方法，返回当前 `_text_field.value`
- 新增 `get_current_filename() -> str` 方法，返回 `_current_filename`

**验收标准**：
- 用户可在中间栏直接编辑文本内容
- `get_content()` 可正确返回编辑后的内容

**验证方法**：选择 .tex 文件，在界面中修改内容，通过"推送修改"后验证本地缓存更新

---

## Task 7：多项目菜单 UI（gui/app.py）

**目标**：AppBar 新增"项目"菜单，支持"创建新项目"和"打开已有项目"。

**影响范围**：`src/gui/app.py`（AppBar 构建、Dialog 弹出逻辑）

**实施要点**：
- 新增 `_btn_project`: `ft.PopupMenuButton`，包含：
  - "创建新项目" → `_on_create_project()`：弹出 Dialog，含 Cookie（预填）、项目 ID、项目名输入框
  - "打开已有项目" 为动态生成的子项，列出 `_storage.list_projects()` 中的项目
- `_on_create_project` 保存后调用 `_settings.add_project()` + `_settings.switch_project()` + `_settings.save()`
- 打开已有项目：调用 `_switch_project(project_id)`，加载 meta 文件重建文件树
- 项目切换后更新 AppBar title（显示项目 ID 或项目名）

**验收标准**：
- 菜单正确显示所有本地缓存项目
- 切换项目后文件树更新，标题栏更新
- 创建新项目 Dialog 预填当前 cookie

**验证方法**：手动创建两个项目，切换验证文件树正确更新

---

## Task 8：推送修改按钮（gui/app.py）

**目标**：AppBar 新增"推送修改"按钮，将当前编辑内容上传到 Overleaf 并更新本地缓存。

**影响范围**：`src/gui/app.py`（新增按钮和事件处理逻辑）

**实施要点**：
- 新增 `_btn_push`: `ft.TextButton("推送修改", icon=ft.Icons.UPLOAD)`, 初始 `disabled=True`
- 选中文件后（且为文本类型时）启用该按钮
- `_on_push()` 逻辑：
  1. 获取 `_tex_viewer.get_current_filename()` 和 `_tex_viewer.get_content()`
  2. 从 entities meta 中查找对应文件的 `doc_id`
  3. 若无 doc_id（二进制文件等），弹出错误"此文件不支持推送"
  4. 后台线程调用 `OverleafClient(cookie).upload_file(project_id, doc_id, content)`
  5. 成功后更新本地缓存 `_storage.save_file(project_id, rel_path, content)`
  6. 显示成功/失败提示

**验收标准**：
- 推送成功后，Overleaf 网页端可看到内容变更
- 推送失败时显示明确错误信息，不崩溃

**验证方法**：修改 main.tex → 点击推送 → 在 Overleaf 网页端验证内容；断网时推送验证错误提示

---

## Task 9：Git 分步提交

**目标**：将上述所有变更按任务粒度拆分为可读的 git commit。

**影响范围**：整个 repo

**实施要点**（提交顺序）：
1. `feat(config): 扩展 SettingsManager 支持多项目配置与向后兼容迁移`
2. `feat(storage): LocalStorage 新增项目元数据缓存读写`
3. `feat(overleaf): get_entities 透传 doc_id；新增 upload_file 推送文档`
4. `fix(gui): 文件选择改为局部刷新，不触发全页重绘`
5. `feat(gui): 三栏分隔条支持鼠标拖拽调整宽度，侧栏可折叠`
6. `feat(tex-viewer): TeX 文件由只读改为可编辑，暴露 get_content()`
7. `feat(gui): 新增多项目菜单（创建/打开项目），切换自动加载缓存文件树`
8. `feat(gui): 新增推送修改按钮，编辑后可上传到 Overleaf 并更新本地缓存`

**验收标准**：每个 commit 消息清晰，单独可 revert

**验证方法**：`git log --oneline` 检查提交历史
