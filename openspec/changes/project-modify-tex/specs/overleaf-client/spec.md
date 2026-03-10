# Delta Spec：Overleaf 客户端扩展（overleaf-client）

基准规范：`openspec/changes/overleaf-fetch-and-gui/specs/overleaf-client/spec.md`

---

## ADDED Requirements

### Requirement: 文档上传（推送修改）

`OverleafClient` SHALL 提供 `upload_file(project_id, doc_id, content)` 方法，  
通过 `POST /project/{project_id}/doc/{doc_id}` 将修改后的文档内容上传到 Overleaf。

请求 MUST 携带有效的 CSRF token（复用 `_extract_csrf_token()` 方法）。

上传失败时 SHALL 抛出对应异常（`OverleafAuthError`/`OverleafNetworkError`），不静默失败。

#### Scenario: 成功上传文档内容
```
Given 有效的 cookie、project_id、doc_id 和修改后的文本内容
When  调用 upload_file(project_id, doc_id, "修改后内容")
Then  请求成功（HTTP 200），Overleaf 服务器端文档内容更新
```

#### Scenario: CSRF token 获取失败
```
Given cookie 已失效
When  调用 upload_file()
Then  _extract_csrf_token() 返回空字符串
And   抛出 OverleafAuthError("无法获取 CSRF token，请检查 Cookie 是否有效")
```

---

### Requirement: entities 响应包含 doc_id

`get_entities()` 方法返回的实体列表 SHALL 透传 Overleaf 响应中的 `id` 字段（即 doc_id），  
供 GUI 层在推送时定位目标文档。

返回结构为：`[{"path": "/main.tex", "type": "doc", "id": "abc123doc"}, ...]`

#### Scenario: 获取含 doc_id 的实体列表
```
Given Overleaf /entities 响应中包含 id 字段
When  调用 get_entities(project_id)
Then  返回列表中每个实体携带 "id" 字段
```
