## ADDED Requirements

### Requirement: 基于 Cookie 初始化客户端
系统 SHALL 允许调用方传入 Overleaf Cookie 字符串，初始化一个带持久 session 的 HTTP 客户端，所有后续请求均携带该 Cookie。

#### Scenario: Cookie 有效时初始化成功
- **WHEN** 调用方传入非空 Cookie 字符串并实例化 `OverleafClient`
- **THEN** 客户端 SHALL 创建携带该 Cookie 的 `requests.Session`，并可立即发起请求

#### Scenario: Cookie 为空时拒绝初始化
- **WHEN** 调用方传入空字符串或 None 作为 Cookie
- **THEN** 系统 SHALL 抛出 `ValueError` 并提示 "Cookie 不能为空"

---

### Requirement: 获取项目文件树
系统 SHALL 向 Overleaf 请求指定项目的完整文件树，返回包含文件夹和文件节点的结构化数据。

#### Scenario: 成功获取文件树
- **WHEN** 提供有效 `project_id` 并调用 `get_file_tree(project_id)`
- **THEN** 系统 SHALL 返回一个嵌套字典/列表结构，每个节点包含 `id`、`name`、`type`（`"doc"` / `"file"` / `"folder"`）字段

#### Scenario: 项目不存在或无权限
- **WHEN** `project_id` 对应项目不存在或 Cookie 无权访问
- **THEN** 系统 SHALL 抛出 `OverleafAuthError` 或 `OverleafNotFoundError`，并附带明确错误信息

---

### Requirement: 下载单个文件内容
系统 SHALL 根据文件节点信息从 Overleaf 下载文件的原始字节内容。

#### Scenario: 下载 doc 类型文件（TeX 源码）
- **WHEN** 传入 `type="doc"` 的文件节点，调用 `download_file(project_id, node)`
- **THEN** 系统 SHALL 返回该文件的 UTF-8 文本内容字符串

#### Scenario: 下载 binary 类型文件（图片等）
- **WHEN** 传入 `type="file"` 的文件节点，调用 `download_file(project_id, node)`
- **THEN** 系统 SHALL 返回该文件的原始 `bytes`

#### Scenario: 网络请求失败
- **WHEN** 请求过程中发生网络超时或连接错误
- **THEN** 系统 SHALL 抛出 `OverleafNetworkError` 并记录日志（不含 Cookie 值）

---

### Requirement: 触发远程编译
系统 SHALL 向 Overleaf 提交编译请求，等待编译完成（或超时），返回编译结果状态。

#### Scenario: 编译成功
- **WHEN** 调用 `compile_project(project_id)` 且 Overleaf 返回编译成功状态
- **THEN** 系统 SHALL 返回 `{"status": "success", "output_files": [...]}`

#### Scenario: 编译失败（TeX 错误）
- **WHEN** Overleaf 返回编译失败状态
- **THEN** 系统 SHALL 返回 `{"status": "error", "logs": "<编译日志>"}` 并记录日志

#### Scenario: 编译超时
- **WHEN** 编译请求超过 60 秒未返回结果
- **THEN** 系统 SHALL 抛出 `OverleafCompileTimeoutError`

---

### Requirement: 下载编译产出 PDF
系统 SHALL 在编译成功后，将 Overleaf 生成的 PDF 文件下载到指定本地路径。

#### Scenario: 成功下载 PDF
- **WHEN** 编译状态为 success 并调用 `download_pdf(project_id, local_path)`
- **THEN** 系统 SHALL 将 PDF 内容写入 `local_path`，返回该路径

#### Scenario: PDF 不存在
- **WHEN** Overleaf 返回 404（PDF 尚未生成）
- **THEN** 系统 SHALL 抛出 `OverleafNotFoundError` 并提示用户先触发编译

---

### Requirement: 日志脱敏
系统 MUST 在所有日志输出中将 Cookie 值替换为 `[REDACTED]`，禁止明文记录任何认证凭据。

#### Scenario: 请求日志不含 Cookie
- **WHEN** 客户端发起任意 HTTP 请求并记录请求日志
- **THEN** 日志中 MUST NOT 包含 Cookie 的原始值，Cookie 字段 SHALL 显示为 `[REDACTED]`
