## ADDED Requirements

### Requirement: 设置页面入口
系统 SHALL 在主界面提供设置入口（菜单项或按钮），点击后跳转到设置页面。

#### Scenario: 点击设置入口跳转
- **WHEN** 用户点击设置入口
- **THEN** 系统 SHALL 导航到设置页面，并可通过返回操作回到主界面

---

### Requirement: 配置 Overleaf Cookie
系统 SHALL 在设置页面提供 Overleaf Cookie 输入框，用户可查看、修改并保存 Cookie 值；Cookie 在输入框中以密码掩码形式显示。

#### Scenario: 保存 Cookie 配置
- **WHEN** 用户在设置页面输入 Cookie 值并点击"保存"
- **THEN** 系统 SHALL 将 Cookie 持久化到 `~/.overleaves/config.json`，并在下次启动时自动加载

#### Scenario: Cookie 以密码形式显示
- **WHEN** 设置页面加载 Cookie 字段
- **THEN** Cookie 输入框 SHALL 以密码掩码（`*`）显示内容，防止屏幕截图泄露

#### Scenario: 配置文件不存在时显示空白
- **WHEN** 首次打开设置且 `~/.overleaves/config.json` 不存在
- **THEN** Cookie 输入框 SHALL 显示为空，不报错

---

### Requirement: 配置 Overleaf 项目 ID
系统 SHALL 在设置页面提供 Overleaf 项目 ID 输入框，用户可输入并保存目标项目 ID。

#### Scenario: 保存项目 ID
- **WHEN** 用户输入项目 ID 并保存
- **THEN** 系统 SHALL 将 `project_id` 写入 `~/.overleaves/config.json`

---

### Requirement: 配置 LLM Agent 参数
系统 SHALL 在设置页面提供 LLM 配置区域，包含 API Key 输入框（密码掩码）和 API 端点 URL 输入框。

#### Scenario: 保存 LLM 配置
- **WHEN** 用户填写 LLM API Key 和 endpoint 并点击"保存"
- **THEN** 系统 SHALL 将配置写入 `~/.overleaves/config.json` 的 `llm` 字段；API Key 以密码形式显示

---

### Requirement: 配置持久化与加载
系统 SHALL 在启动时自动从 `~/.overleaves/config.json` 加载所有设置，并在设置页面保存时更新文件；配置文件使用 UTF-8 编码的 JSON 格式。

#### Scenario: 启动时加载已有配置
- **WHEN** 应用启动且 `~/.overleaves/config.json` 存在且格式正确
- **THEN** 系统 SHALL 将文件中的配置值注入各模块，设置页面展示当前值

#### Scenario: 配置文件格式损坏时降级处理
- **WHEN** `~/.overleaves/config.json` 存在但 JSON 格式无效
- **THEN** 系统 SHALL 以空配置启动，并在界面提示"配置文件格式错误，已使用默认配置"
