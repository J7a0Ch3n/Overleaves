# Overleaves

Overleaves 是一款跨平台论文写作 Agent 工具，仿照 [olcli](https://github.com/aloth/olcli) 拉取 Overleaf 项目内容，通过 Agent 功能协助用户进行论文写作、内容修改、格式调整等操作，最终将修改结果推送回 Overleaf 项目。

## 功能特性

- **拉取远程项目**：基于 Cookie 认证，从 Overleaf 拉取项目文件树和所有文件
- **三栏 GUI 界面**：左侧文件树 / 中间 TeX 内容只读展示 / 右侧 PDF 预览
- **远程编译**：触发 Overleaf 编译器，下载并预览编译产出 PDF（基于 PyMuPDF 渲染）
- **设置管理**：配置 Overleaf Cookie、项目 ID、LLM Agent 参数，持久化保存
- **跨平台**：基于 Flet（Flutter），支持 Windows / macOS / Linux

## 项目结构

```
overleaves/
├── src/
│   ├── main.py                  # Flet 应用入口
│   ├── overleaf/
│   │   ├── client.py            # Overleaf HTTP 客户端
│   │   └── exceptions.py        # 自定义异常
│   ├── storage/
│   │   └── local_storage.py     # 本地文件缓存
│   ├── gui/
│   │   ├── app.py               # 主界面框架
│   │   ├── settings.py          # 设置页面
│   │   └── panels/
│   │       ├── file_tree.py     # 文件树面板
│   │       ├── tex_viewer.py    # TeX 内容面板
│   │       └── pdf_viewer.py    # PDF 预览面板
│   └── config/
│       └── settings_manager.py  # 配置读写
├── requirements.txt
├── overleaves.spec              # PyInstaller 配置
├── build.ps1                    # Windows 打包脚本
└── README.md
```

## 快速开始

### 环境要求

- Python 3.10+
- Windows / macOS / Linux

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行（开发模式）

```bash
python src/main.py
```

### 配置说明

1. 启动后点击右上角 **设置** 图标
2. 填写 **Overleaf Cookie**：
   - 在浏览器中登录 Overleaf
   - 打开开发者工具（F12）→ Network → 任意请求 → Request Headers → Cookie
   - 复制完整 Cookie 字符串粘贴到设置框
3. 填写 **Overleaf 项目 ID**：项目 URL 中 `https://www.overleaf.com/project/<项目ID>` 的 `<项目ID>` 部分
4. 点击 **保存配置**

配置保存在 `~/.overleaves/config.json`，拉取的项目缓存在 `~/.overleaves/projects/<project_id>/`。

### 使用说明

1. 配置好 Cookie 和项目 ID 后，点击 **拉取远程项目**，等待文件树加载
2. 点击左侧文件树中的 `.tex` 文件，中间面板展示文件内容
3. 点击 **远程编译并拉取 PDF 显示**，触发 Overleaf 编译并在右侧预览 PDF

## 打包为 Windows exe

> 在 Windows PowerShell 中执行，需已安装 Python 和依赖

### 方式一（推荐）：使用打包脚本

```powershell
.\build.ps1
```

脚本会自动：
1. 安装/检查依赖
2. 清理旧的 `dist/` 和 `build/` 目录
3. 调用 PyInstaller 打包
4. 输出 `dist\overleaves.exe`（单文件，无需额外 Python 环境）

### 方式二：手动执行

```powershell
pip install -r requirements.txt
pyinstaller overleaves.spec --noconfirm
```

打包完成后，`dist\overleaves.exe` 即为可独立运行的应用程序。

### 常见问题

**Q：打包后运行提示 DLL 缺失**  
A：部分系统需要安装 [Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe)

**Q：Cookie 失效后如何更新**  
A：重新在浏览器复制 Cookie，在设置页面更新并保存即可

## 安全说明

- Cookie 以明文存储在 `~/.overleaves/config.json`，请妥善保管该文件
- 日志中 Cookie 值一律脱敏为 `[REDACTED]`，不会泄露到日志文件

## 开发计划

- [ ] TeX 文件编辑功能
- [ ] LLM Agent 集成（论文写作、修改建议）
- [ ] 修改推送回 Overleaf
- [ ] 多项目管理

## License

MIT

