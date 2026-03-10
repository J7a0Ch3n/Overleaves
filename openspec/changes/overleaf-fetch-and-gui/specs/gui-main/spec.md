## ADDED Requirements

### Requirement: 三栏主界面布局
系统 SHALL 以三列布局展示主界面：左侧文件树面板（宽度比约 2）、中间 TeX 内容面板（宽度比约 3）、右侧 PDF 预览面板（宽度比约 3），三列随窗口大小自适应。

#### Scenario: 启动时显示主界面
- **WHEN** 用户启动应用
- **THEN** 系统 SHALL 显示带三列布局的主窗口，各面板均可见且占据合理比例

---

### Requirement: 左侧文件树面板
系统 SHALL 在左侧面板中以层级树形结构展示当前已拉取项目的文件和文件夹，支持展开/折叠文件夹节点。

#### Scenario: 显示文件树
- **WHEN** 项目已成功拉取且文件树数据可用
- **THEN** 左侧面板 SHALL 展示以项目根目录为根节点的树形结构，文件夹可展开，文件显示图标和名称

#### Scenario: 点击文件加载内容
- **WHEN** 用户在文件树中点击一个 `.tex` 文件节点
- **THEN** 系统 SHALL 在中间面板加载并展示该文件的文本内容

#### Scenario: 无项目数据时显示提示
- **WHEN** 尚未拉取任何项目
- **THEN** 左侧面板 SHALL 显示提示文字"请先拉取远程项目"

---

### Requirement: 中间 TeX 内容面板
系统 SHALL 在中间面板以只读方式展示当前选中 TeX 文件的文本内容，并支持垂直滚动。

#### Scenario: 展示 TeX 文件内容
- **WHEN** 用户选中文件树中的某个 TeX 文件
- **THEN** 中间面板 SHALL 以等宽字体显示该文件全部文本内容，内容只读不可编辑

#### Scenario: 文件内容超长时可滚动
- **WHEN** 文件内容超过面板可见高度
- **THEN** 面板 SHALL 支持垂直滚动查看全部内容

#### Scenario: 无文件选中时显示提示
- **WHEN** 未选中任何文件
- **THEN** 中间面板 SHALL 显示提示文字"请在左侧选择文件"

---

### Requirement: 右侧 PDF 预览面板
系统 SHALL 在右侧面板展示编译产出的 PDF，以逐页图片方式渲染，支持垂直滚动浏览所有页面。

#### Scenario: 成功显示 PDF
- **WHEN** 编译已完成且本地存在 PDF 文件
- **THEN** 右侧面板 SHALL 将所有 PDF 页面渲染为图片并以垂直列表展示

#### Scenario: PDF 不存在时显示提示
- **WHEN** 本地无 PDF 文件
- **THEN** 右侧面板 SHALL 显示提示文字"请先触发远程编译"

---

### Requirement: 菜单操作——拉取远程项目
系统 SHALL 在应用菜单或工具栏中提供"拉取远程项目"操作，点击后触发文件拉取流程。

#### Scenario: 触发拉取操作
- **WHEN** 用户点击"拉取远程项目"并已配置有效 Cookie 及 project_id
- **THEN** 系统 SHALL 在后台线程中调用 Overleaf 客户端拉取全部文件，拉取完成后刷新左侧文件树

#### Scenario: 未配置 Cookie 时提示
- **WHEN** 用户点击"拉取远程项目"但未配置 Cookie
- **THEN** 系统 SHALL 弹出对话框提示"请先在设置中配置 Overleaf Cookie"

#### Scenario: 拉取失败时提示错误
- **WHEN** 拉取过程中发生网络错误或认证失败
- **THEN** 系统 SHALL 以对话框或状态栏显示具体错误信息，不崩溃

---

### Requirement: 菜单操作——远程编译并拉取 PDF
系统 SHALL 提供"远程编译并拉取 PDF 显示"操作，点击后触发编译、下载 PDF 并刷新右侧预览。

#### Scenario: 触发编译并显示 PDF
- **WHEN** 用户点击"远程编译并拉取 PDF 显示"且文件已拉取
- **THEN** 系统 SHALL 触发编译，等待结果，下载 PDF，并刷新右侧预览面板

#### Scenario: 编译失败时显示错误
- **WHEN** Overleaf 返回编译失败
- **THEN** 系统 SHALL 弹出对话框显示编译失败信息，右侧面板保持上次 PDF（若有）

---

### Requirement: 操作期间显示加载状态
系统 SHALL 在拉取或编译操作进行期间显示加载指示器，操作完成后自动隐藏。

#### Scenario: 拉取操作期间显示加载
- **WHEN** 拉取操作正在进行
- **THEN** 系统 SHALL 在界面上显示进度指示器（如 ProgressBar 或 ProgressRing），并禁用相关操作按钮

#### Scenario: 操作完成后恢复正常状态
- **WHEN** 拉取或编译操作完成（成功或失败）
- **THEN** 系统 SHALL 隐藏加载指示器，恢复操作按钮可用状态
