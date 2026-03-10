## ADDED Requirements

### Requirement: 初始化本地缓存目录
系统 SHALL 在首次使用时自动创建本地缓存根目录 `~/.overleaves/`，包含 `projects/` 子目录，目录不存在时自动创建，已存在时不报错。

#### Scenario: 首次运行自动创建目录
- **WHEN** `LocalStorage` 初始化时 `~/.overleaves/projects/` 不存在
- **THEN** 系统 SHALL 自动创建该目录及所有父目录

---

### Requirement: 保存项目文件到本地
系统 SHALL 将从 Overleaf 拉取的文件保存到 `~/.overleaves/projects/<project_id>/` 目录下，按原始文件树结构组织子目录和文件。

#### Scenario: 保存 TeX 文本文件
- **WHEN** 调用 `save_file(project_id, relative_path, content: str)`
- **THEN** 系统 SHALL 将内容以 UTF-8 编码写入对应路径，不存在的父目录自动创建

#### Scenario: 保存二进制文件
- **WHEN** 调用 `save_file(project_id, relative_path, content: bytes)`
- **THEN** 系统 SHALL 将内容以二进制模式写入对应路径

---

### Requirement: 读取本地缓存文件内容
系统 SHALL 支持从本地缓存目录按路径读取文件内容，供 GUI 展示。

#### Scenario: 文件已缓存时读取成功
- **WHEN** 调用 `read_file(project_id, relative_path)`，文件在本地存在
- **THEN** 系统 SHALL 返回文件的文本字符串（UTF-8）或字节内容

#### Scenario: 文件不存在时抛出错误
- **WHEN** 调用 `read_file(project_id, relative_path)`，文件不在本地缓存
- **THEN** 系统 SHALL 抛出 `FileNotFoundError` 并提示文件路径

---

### Requirement: 保存 PDF 到本地缓存
系统 SHALL 将下载的 PDF 保存到 `~/.overleaves/projects/<project_id>/output.pdf`。

#### Scenario: 成功保存 PDF
- **WHEN** 调用 `save_pdf(project_id, pdf_bytes: bytes)`
- **THEN** 系统 SHALL 将字节内容写入 `~/.overleaves/projects/<project_id>/output.pdf`，返回文件绝对路径

---

### Requirement: 列出本地已缓存项目
系统 SHALL 支持枚举 `~/.overleaves/projects/` 下所有已缓存的项目 ID。

#### Scenario: 列出缓存项目
- **WHEN** 调用 `list_projects()`
- **THEN** 系统 SHALL 返回 `~/.overleaves/projects/` 下所有子目录名称列表，若为空则返回空列表
