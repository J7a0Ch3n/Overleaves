# Delta Spec：GUI 主界面（gui-main）

基准规范：`openspec/changes/overleaf-fetch-and-gui/specs/gui-main/spec.md`

---

## ADDED Requirements

### Requirement: 多项目菜单

GUI 主界面 AppBar SHALL 在最左侧提供"项目"下拉菜单，包含以下菜单项：
- "创建新项目"：弹出 Dialog 录入 Cookie 和项目 ID
- "打开已有项目"（子菜单）：动态列出所有本地缓存项目，点击后切换当前项目

#### Scenario: 打开已有项目并自动加载文件树
```
Given 本地缓存目录 ~/.overleaves/projects/ 下有项目 abc123
When  用户点击"项目" → "打开已有项目" → 选择 abc123
Then  文件树面板自动渲染缓存中的文件列表，无需用户手动点击"拉取远程项目"
```

#### Scenario: 创建新项目时预填 Cookie
```
Given 当前已配置 cookie="xxx"
When  用户点击"项目" → "创建新项目"
Then  弹出 Dialog 的 Cookie 输入框预填 "xxx"，用户可直接修改项目 ID 后保存
```

---

### Requirement: 可拖拽三栏宽度

三栏分隔条 SHALL 支持鼠标拖动以调整相邻两列宽度，拖动期间面板实时响应。

每栏宽度 SHALL 有最小宽度限制（不小于 100px），防止面板被完全压缩。

#### Scenario: 拖动分隔条调整宽度
```
Given 用户打开主界面，三栏以默认宽度显示
When  用户按住左侧分隔条向右拖动 100px
Then  文件树面板宽度增加约 100px，中间栏宽度相应减少
```

---

### Requirement: 可折叠侧栏

AppBar 或侧栏旁 SHALL 提供按钮以独立隐藏/显示左栏文件树和右栏 PDF 预览。

#### Scenario: 隐藏文件树
```
Given 文件树面板当前可见
When  用户点击"隐藏文件树"按钮
Then  文件树面板隐藏（宽度为 0），中间栏可用宽度扩展
And   按钮变为"显示文件树"，点击后恢复
```

---

### Requirement: TeX 文件可编辑

中间栏对文本类文件（.tex/.bib 等）SHALL 以可编辑 TextField 展示，用户可直接修改内容。

#### Scenario: 编辑 TeX 文件
```
Given 用户从文件树选择 main.tex
When  中间栏加载文件内容
Then  内容显示在可编辑的 TextField（read_only=False）中，用户可键入修改
```

---

### Requirement: 推送修改按钮

AppBar SHALL 提供"推送修改"按钮，点击后将当前中间栏编辑内容上传到 Overleaf。

#### Scenario: 成功推送修改
```
Given 用户已修改 main.tex 内容
When  用户点击"推送修改"
Then  修改内容通过 OverleafClient.upload_file() 上传
And   本地缓存同步更新
And   成功后显示提示"推送成功"
```

#### Scenario: 无文件时禁用推送
```
Given 用户未选择任何文件
When  界面加载
Then  "推送修改"按钮处于禁用状态（disabled=True）
```

---

## MODIFIED Requirements

### Requirement: 局部刷新文件选择（修改既有需求）

原规范：点击文件树节点时调用 `page.update()` 刷新整个页面。  
修改为：点击文件树节点 SHALL 仅调用 `tex_viewer.update()` 更新中间栏，不触发全页重绘。

#### Scenario: 局部刷新验证
```
Given 用户已加载项目文件树
When  用户点击文件树中的 chapter1.tex
Then  中间栏更新显示 chapter1.tex 内容
And   右栏 PDF 预览、左栏文件树不发生任何重绘/闪烁
```
