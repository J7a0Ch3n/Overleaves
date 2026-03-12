# 变更提案：多项目管理、界面拖拽调整、TeX 编辑与推送、局部刷新优化

## 背景与动机

当前 Overleaves 已完成论文内容拉取功能及基础 GUI，但存在以下不足：
1. 每次启动都需要手动重新拉取项目，本地缓存未被自动加载
2. 只支持单一项目，无法管理多个 Overleaf 项目
3. 三栏宽度固定，无法根据工作需要调整布局
4. TeX 文件只读展示，无法在应用内编辑并推送修改
5. 点击文件树时整个页面重新渲染，响应体验差

## 目标与范围

### 目标（可验证行为）
- 多项目管理：左上角"项目"菜单支持"创建新项目"（录入 Cookie 和项目 ID）和"打开已有项目"（列表选择本地缓存项目）
- 自动加载本地缓存：打开已有项目时，若本地已缓存文件，自动加载文件树，无需手动拉取
- 可拖拽三栏：用户可通过鼠标拖拉调整文件树/中间/PDF 三栏宽度
- 可隐藏侧栏：按钮可独立隐藏/显示左栏文件树和右栏 PDF 预览
- TeX 可编辑：中间栏文本文件变为可编辑状态，支持修改内容
- 推送修改：新增"推送修改"菜单/按钮，将修改后的文件通过 Overleaf API 推送回服务器
- 局部刷新：点击文件树节点只更新中间栏，不重绘整个页面

### 非目标（本次不做）
- LLM Agent 写作辅助功能（属于下一阶段）
- 版本历史/Diff 对比
- 多用户协作
- 离线编译

## 用户故事

1. **管理多项目**：用户点击"项目"菜单 → "打开已有项目" → 从缓存列表选择 → 自动加载文件树，无需重新拉取
2. **换项目工作**：用户点击"项目" → "创建新项目" → 填入新 Cookie 和项目 ID → 保存并拉取
3. **调整界面布局**：用户拖动分隔条改变三栏宽度；或点击隐藏按钮折叠文件树专注编辑
4. **编辑并推送**：用户在中间栏修改 TeX 内容 → 点击"推送修改" → 文件上传到 Overleaf

## 与现有系统的关系

参考：
- `openspec/changes/overleaf-fetch-and-gui/specs/gui-main/spec.md`（主界面布局规范）
- `openspec/changes/overleaf-fetch-and-gui/specs/overleaf-client/spec.md`（客户端能力规范）
- `openspec/changes/overleaf-fetch-and-gui/specs/local-storage/spec.md`（本地存储规范）
- `openspec/changes/overleaf-fetch-and-gui/specs/gui-settings/spec.md`（设置页规范）

## 主要方案

### 1. 多项目管理

**设计**：在 AppBar 最左侧新增"项目"下拉菜单（`ft.PopupMenuButton`），替代原设置中的 cookie/project_id 输入。

- **创建新项目**：弹出 Dialog，含 Cookie 输入框（预填当前 cookie）、项目 ID 输入框，保存后将新项目写入配置（`projects` 字典）并切换当前活跃项目
- **打开已有项目**：动态列出 `LocalStorage.list_projects()` 中的缓存项目条目，选择后切换 `current_project_id`，若本地有缓存则自动加载文件树
- **配置结构变更**：`config.json` 增加 `projects` 字典（key=project_id, value={cookie, name}）和 `current_project_id` 字段；保留 `cookie`/`project_id` 向后兼容

### 2. 可拖拽三栏

**方案**：Flet 暂不原生支持拖拽分割线，采用以下策略：
- 使用带 `on_hover`/`on_pan_start`/`on_pan_update` 的 `ft.GestureDetector` 包裹分隔符
- 三栏用 `width` 属性替代 `expand`，拖动时更新宽度并调用 `page.update()`
- 侧栏隐藏/显示：`ft.IconButton` 触发 `visible=False/True` + 分隔符同步隐藏

### 3. TeX 可编辑 + 推送

- `TexViewerPanel._make_text_view()` 中 `read_only=False`（文本文件）
- 新增 `TexViewerPanel.get_content() -> str` 方法获取当前编辑内容
- `OverleafClient` 新增 `upload_file(project_id, doc_id, content)` 方法：通过 Overleaf 未公开 API `POST /project/{id}/doc/{doc_id}` 更新文档内容
- 由于 Overleaf 文档更新需要 `doc_id`（不同于文件路径），需在拉取文件树时同时保存 path→doc_id 的映射
- AppBar 新增"推送修改"按钮，触发后获取当前文件内容和 doc_id，调用 upload_file

### 4. 局部刷新

- 文件树点击回调 `_on_file_select` 直接调用 `self._tex_viewer.update()`，不调用 `self._page.update()`
- Flet 控件调用 `.update()` 只更新该控件子树，不触发全页重绘

## 风险清单

| 风险 | 级别 | 缓解措施 |
|------|------|----------|
| Overleaf upload API 非官方，可能变化或受 CSRF 保护 | 中 | 复用现有 CSRF token 提取逻辑；失败时显示友好错误 |
| Flet 拖拽 GestureDetector 在不同平台行为差异 | 中 | 以 Windows 为主测试；记录 macOS/Linux 已知限制 |
| doc_id 映射需从 entities API 中解析 | 低 | 检查 `/entities` 响应格式是否含 doc_id；备选方案从项目页 HTML 提取 |
| 三栏 width 模式与现有 expand 模式切换 | 低 | 重构 build() 方法，统一用显式 width 管理 |

## 澄清问题清单

### 阻断级
1. **Overleaf doc 更新 API**：`/project/{id}/doc/{doc_id}` 接口格式需要验证。若该接口不可用，推送功能无法实现。  
   **默认决策**：先实现 API 调用，若失败给出明确错误提示"推送功能暂不支持"，不阻断其他功能。

### 非阻断级

| # | 问题 | 默认决策 | 理由 |
|---|------|----------|------|
| 1 | entities API 是否返回 doc_id | 通过 debug 日志记录实际响应结构，动态适配 | 不同版本 Overleaf 格式略有差异 |
| 2 | 拖拽分隔条的最小/最大宽度限制 | 最小 100px，最大为总宽度-200px | 防止面板被完全压缩导致 UI 崩溃 |
| 3 | 多项目 cookie 是否共用 | 每个项目独立保存 cookie，创建时预填当前 cookie | 用户用同一账号操作多项目时更方便 |
| 4 | 隐藏侧栏的宽度 | 隐藏时宽度设为 0，按钮保留在原位置 | 简单实现，按钮始终可见 |
| 5 | 推送后是否自动刷新本地缓存 | 推送后同步更新本地缓存文件 | 保持本地与远程一致 |

## 决策记录

- **多项目配置**：`config.json` 新增 `projects` 字典 + `current_project_id`，保留旧字段向后兼容
- **拖拽方案**：GestureDetector + 显式 width 属性（非 expand），测试平台以 Windows 为主
- **推送 API**：使用 `POST /project/{id}/doc/{doc_id}`，携带 CSRF token
- **doc_id 来源**：从 `/entities` 响应中提取（若有），或从项目页 HTML 中解析
- **局部刷新**：调用 `tex_viewer.update()` 而非 `page.update()`
