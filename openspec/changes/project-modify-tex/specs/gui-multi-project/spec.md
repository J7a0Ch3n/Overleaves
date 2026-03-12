# Delta Spec：多项目管理（gui-multi-project）

全新规范模块，无基准规范。

---

## ADDED Requirements

### Requirement: 多项目配置存储

`SettingsManager` SHALL 支持多项目配置，配置结构如下：
```json
{
  "current_project_id": "abc123",
  "cookie": "旧字段向后兼容",
  "projects": {
    "abc123": { "cookie": "xxx", "name": "My Thesis" },
    "def456": { "cookie": "yyy", "name": "Paper 2" }
  },
  "llm": {}
}
```

`current_project_id` 字段 SHALL 标识当前活跃项目，用于所有操作的默认上下文。

旧字段 `cookie` 和 `project_id` SHALL 保留（向后兼容读取），迁移时自动合并到 `projects` 字典。

#### Scenario: 读取当前项目 cookie
```
Given config.json 含 projects.abc123.cookie="xxx" 且 current_project_id="abc123"
When  应用启动或切换项目
Then  SettingsManager.current_cookie 返回 "xxx"
```

#### Scenario: 向后兼容旧配置
```
Given config.json 只有旧字段 cookie="old" 和 project_id="abc"
When  应用加载配置
Then  自动将 abc 加入 projects 字典（cookie=old），并设置 current_project_id="abc"
```

---

### Requirement: 项目列表元数据缓存

`LocalStorage` SHALL 支持在项目目录下保存项目元数据文件（`project_meta.json`），  
记录：`{"name": "项目名", "entities": [...原始entities列表...] }`。

启动时，若本地存在 `project_meta.json`，SHALL 自动从中加载文件树，无需网络请求。

#### Scenario: 从缓存自动加载文件树
```
Given ~/.overleaves/projects/abc123/project_meta.json 存在且含有效 entities
When  用户打开已有项目 abc123
Then  文件树从缓存中构建，无需后台网络请求
```
