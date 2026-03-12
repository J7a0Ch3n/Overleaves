"""
主应用框架：三栏布局 + AppBar，直接挂载到 page（不依赖路由/View）
支持：多项目管理、三栏拖拽调整、侧栏折叠、TeX 编辑与推送、局部刷新。
"""
import logging
import threading
from pathlib import Path

import flet as ft

from config.settings_manager import SettingsManager
from gui.panels.file_tree import FileTreePanel
from gui.panels.pdf_viewer import PdfViewerPanel
from gui.panels.tex_viewer import TexViewerPanel
from overleaf.client import OverleafClient
from overleaf.exceptions import (
    OverleafAuthError,
    OverleafCompileTimeoutError,
    OverleafNetworkError,
    OverleafNotFoundError,
)
from storage.local_storage import LocalStorage

logger = logging.getLogger(__name__)


def _normalize_entities(entities: list) -> list:
    """
    规范化 entities 列表：将 Overleaf 的 MongoDB _id 字段统一映射为 id。
    供从本地缓存加载时使用（缓存可能是旧版本保存的，字段名不一致）。
    """
    for e in entities:
        if "id" not in e and "_id" in e:
            e["id"] = e["_id"]
    return entities


def _build_tree_from_entities(entities: list) -> list:
    """
    将 /entities 返回的扁平列表转换为文件树结构，供 FileTreePanel 显示。
    entity: {"path": "/folder/file.tex", "type": "doc"|"file"}
    节点携带 "path" 字段（去掉开头 /），供 _on_file_select 读取本地缓存使用。
    """
    root: list = []
    folders: dict = {}  # folder_path -> children list

    def get_or_create_folder(parts: list) -> list:
        """递归确保文件夹路径存在，返回该文件夹的 children 列表。"""
        if not parts:
            return root
        key = "/".join(parts)
        if key not in folders:
            parent = get_or_create_folder(parts[:-1])
            node = {"name": parts[-1], "type": "folder", "children": []}
            parent.append(node)
            folders[key] = node["children"]
        return folders[key]

    for entity in entities:
        raw_path = entity.get("path", "")
        entity_type = entity.get("type", "doc")
        # 去掉开头的 /
        rel_path = raw_path.lstrip("/")
        parts = rel_path.split("/")
        name = parts[-1]
        parent_parts = parts[:-1]
        parent_children = get_or_create_folder(parent_parts)
        parent_children.append({
            "name": name,
            "type": entity_type,
            "path": rel_path,  # 完整相对路径，供读取本地缓存
            "id": entity.get("id", ""),  # doc_id，供推送修改使用
        })

    return root


class OverleavesApp:
    """
    Overleaves 主应用。
    build() 方法将所有 UI 直接挂载到 page，不使用 ft.View 路由系统。
    """

    def __init__(self, page: ft.Page, settings: SettingsManager, storage: LocalStorage):
        self._page = page
        self._settings = settings
        self._storage = storage

        self._file_tree = FileTreePanel(on_file_select=self._on_file_select)
        self._tex_viewer = TexViewerPanel(on_change=self._on_content_change)
        self._pdf_viewer = PdfViewerPanel()
        self._progress = ft.ProgressBar(visible=False, height=4)

        # 三栏宽度状态（中间栏始终 expand）
        self._LEFT_WIDTH_DEFAULT = 220
        self._RIGHT_WIDTH_DEFAULT = 280
        self._MIN_WIDTH = 100
        self._left_width: float = self._LEFT_WIDTH_DEFAULT
        self._right_width: float = self._RIGHT_WIDTH_DEFAULT
        self._left_visible: bool = True
        self._right_visible: bool = True

        self._btn_fetch = ft.TextButton(
            "拉取远程项目",
            icon=ft.Icons.CLOUD_DOWNLOAD,
            on_click=self._on_fetch,
        )
        self._btn_compile = ft.TextButton(
            "远程编译并拉取 PDF",
            icon=ft.Icons.BUILD,
            on_click=self._on_compile,
        )
        self._btn_toggle_left = ft.IconButton(
            icon=ft.Icons.CHEVRON_LEFT,
            tooltip="隐藏/显示文件树",
            on_click=self._on_toggle_left,
        )
        self._btn_toggle_right = ft.IconButton(
            icon=ft.Icons.CHEVRON_RIGHT,
            tooltip="隐藏/显示 PDF 预览",
            on_click=self._on_toggle_right,
        )

        # 多项目管理
        self._current_entities: list = []  # 当前项目 entities（含 doc_id）
        self._current_doc_id: str = ""    # 当前打开文件的 doc_id，选文件时更新
        self._modified_files: dict[str, str] = {}  # 本次会话已修改的文件 {rel_path: content}
        self._project_title = ft.Text("Overleaves", weight=ft.FontWeight.BOLD)
        self._btn_project = ft.PopupMenuButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip="项目管理",
            items=self._build_project_menu_items(),
        )

        # 推送修改
        self._btn_push = ft.TextButton(
            "推送修改",
            icon=ft.Icons.UPLOAD,
            disabled=True,
            on_click=self._on_push,
        )
    def build(self) -> None:
        """将整个 UI 挂载到 page。"""
        page = self._page
        page.appbar = ft.AppBar(
            title=self._project_title,
            center_title=False,
            leading=self._btn_project,
            actions=[
                self._btn_toggle_left,
                self._btn_fetch,
                self._btn_compile,
                self._btn_push,
                ft.IconButton(
                    icon=ft.Icons.SETTINGS,
                    tooltip="设置",
                    on_click=self._on_open_settings,
                ),
                self._btn_toggle_right,
                ft.Container(width=8),
            ],
        )

        # 若已有活跃项目，启动时自动加载本地缓存文件树
        self._auto_load_cached_project()

        # 中间栏始终 expand 填充剩余空间；左右栏用 Container wrapper 控制宽度。
        # 拖拽时只更新 wrapper 的 width 属性（单个数字），比更新整棵控件树快得多。
        self._tex_viewer.expand = True
        self._file_tree.expand = True   # 让面板填充 wrapper 内部
        self._pdf_viewer.expand = True

        self._left_wrap = ft.Container(
            content=self._file_tree,
            width=self._left_width,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            # Flutter 端在两次 Python update() 之间自动插值，达到显示刷新率级别的丝滑度
            # duration 设为与 drag_interval 相同（都是 30ms）
            animate=ft.Animation(30, ft.AnimationCurve.LINEAR),
        )
        self._right_wrap = ft.Container(
            content=self._pdf_viewer,
            width=self._right_width,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            animate=ft.Animation(30, ft.AnimationCurve.LINEAR),
        )

        # 可拖拽左分隔条：Container 在 STRETCH Row 中无条件撑满行高
        self._left_divider = ft.GestureDetector(
            content=ft.Container(width=6, bgcolor=ft.Colors.GREY_400),
            mouse_cursor=ft.MouseCursor.RESIZE_COLUMN,
            on_pan_update=self._on_left_divider_drag,
            # Python 每 30ms 发一次目标宽度，Flutter 动画补帧到 60fps+
            drag_interval=30,
        )
        # 可拖拽右分隔条
        self._right_divider = ft.GestureDetector(
            content=ft.Container(width=6, bgcolor=ft.Colors.GREY_400),
            mouse_cursor=ft.MouseCursor.RESIZE_COLUMN,
            on_pan_update=self._on_right_divider_drag,
            drag_interval=30,
        )

        self._three_cols = ft.Row(
            controls=[
                self._left_wrap,
                self._left_divider,
                self._tex_viewer,
                self._right_divider,
                self._right_wrap,
            ],
            expand=True,
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        )

        root = ft.Column(
            controls=[self._progress, self._three_cols],
            expand=True,
            spacing=0,
        )

        page.add(root)

    # ------------------------------------------------------------------
    # 拖拽与折叠
    # ------------------------------------------------------------------

    def _on_left_divider_drag(self, e) -> None:
        """拖拽左分隔条：只更新 wrapper Container 的 width（单属性，最小序列化）。"""
        _delta = e.local_delta or e.global_delta
        dx = _delta.x if _delta else 0
        if not dx:
            return
        new_w = max(self._MIN_WIDTH, self._left_width + dx)
        if new_w == self._left_width:
            return
        self._left_width = new_w
        self._left_wrap.width = new_w
        self._left_wrap.update()  # 只序列化 Container.width 一个字段

    def _on_right_divider_drag(self, e) -> None:
        """拖拽右分隔条：只更新 wrapper Container 的 width（单属性，最小序列化）。"""
        _delta = e.local_delta or e.global_delta
        dx = _delta.x if _delta else 0
        if not dx:
            return
        new_w = max(self._MIN_WIDTH, self._right_width - dx)
        if new_w == self._right_width:
            return
        self._right_width = new_w
        self._right_wrap.width = new_w
        self._right_wrap.update()

    def _on_toggle_left(self, _) -> None:
        """切换左栏文件树的显示/隐藏。"""
        self._left_visible = not self._left_visible
        self._left_wrap.visible = self._left_visible
        self._left_divider.visible = self._left_visible
        self._btn_toggle_left.icon = (
            ft.Icons.CHEVRON_RIGHT if not self._left_visible else ft.Icons.CHEVRON_LEFT
        )
        self._page.update()

    def _on_toggle_right(self, _) -> None:
        """切换右栏 PDF 预览的显示/隐藏。"""
        self._right_visible = not self._right_visible
        self._right_wrap.visible = self._right_visible
        self._right_divider.visible = self._right_visible
        self._btn_toggle_right.icon = (
            ft.Icons.CHEVRON_LEFT if not self._right_visible else ft.Icons.CHEVRON_RIGHT
        )
        self._page.update()

    # ------------------------------------------------------------------
    # 多项目管理
    # ------------------------------------------------------------------

    def _build_project_menu_items(self) -> list:
        """构建项目菜单条目：创建新项目 + 所有缓存项目列表。"""
        items = [
            ft.PopupMenuItem(
                content=ft.Row(
                    [ft.Icon(ft.Icons.ADD, size=16), ft.Text("创建新项目")],
                    spacing=8,
                ),
                on_click=self._on_create_project,
            ),
            ft.PopupMenuItem(),  # 分隔线
        ]
        cached = self._storage.list_projects() if hasattr(self, "_storage") else []
        settings_projects = self._settings.list_project_ids() if hasattr(self, "_settings") else []
        # 合并两个来源，去重
        all_ids = list(dict.fromkeys(settings_projects + cached))
        for pid in all_ids:
            name = self._settings.get_project_name(pid)
            display = name if name != pid else pid
            # 使用默认参数绑定 pid，避免闭包捕获问题
            def make_handler(project_id):
                def handler(_):
                    self._on_open_project(project_id)
                return handler
            items.append(ft.PopupMenuItem(
                content=ft.Row(
                    [ft.Icon(ft.Icons.FOLDER, size=16), ft.Text(display)],
                    spacing=8,
                ),
                on_click=make_handler(pid),
            ))
        return items

    def _on_content_change(self, rel_path: str, content: str) -> None:
        """TexViewerPanel 回调：用户每次编辑时调用，跟踪"已修改文件"集合。"""
        prev_count = len(self._modified_files)
        self._modified_files[rel_path] = content
        new_count = len(self._modified_files)
        # 只在修改文件数变化时（首次修改某文件）更新按钮，避免每次按键都触发 IPC
        if new_count != prev_count:
            self._btn_push.text = f"推送修改 ({new_count})"
            self._btn_push.disabled = False
            self._btn_push.update()

    def _build_path_doc_id_map(self) -> dict[str, str]:
        """
        从 _current_entities 构建 rel_path → doc_id 映射。
        兼容 id 和 _id 两种字段名；只包含 type=='doc' 的可推送文件。
        """
        result: dict[str, str] = {}
        for entity in self._current_entities:
            path = entity.get("path", "").lstrip("/")
            doc_id = entity.get("id") or entity.get("_id", "")
            # 只有 doc 类型才能推送；file 类型（图片/PDF等）不可编辑推送
            if path and doc_id and entity.get("type", "doc") == "doc":
                result[path] = doc_id
        return result

    def _refresh_project_menu(self) -> None:
        """刷新项目菜单条目（切换/新建项目后调用）。"""
        self._btn_project.items = self._build_project_menu_items()
        self._btn_project.update()

    def _auto_load_cached_project(self) -> None:
        """启动时若有活跃项目且本地有缓存，自动加载文件树。"""
        pid = self._settings.current_project_id
        if not pid:
            return
        meta = self._storage.load_project_meta(pid)
        if meta:
            entities = _normalize_entities(meta.get("entities", []))
            self._current_entities = entities
            tree = _build_tree_from_entities(entities)
            self._file_tree.load_tree(tree, trigger_update=False)
            proj_name = meta.get("name", pid)
            self._project_title.value = f"Overleaves — {proj_name}"
            logger.info("已从缓存加载项目 %s 文件树", pid)

    def _on_create_project(self, _) -> None:
        """弹出"创建新项目"对话框。"""
        tf_cookie = ft.TextField(
            label="Overleaf Cookie",
            hint_text="从浏览器开发者工具复制完整 Cookie 字符串",
            password=True,
            can_reveal_password=True,
            value=self._settings.current_cookie,
        )
        tf_project_id = ft.TextField(
            label="Overleaf 项目 ID",
            hint_text="项目 URL 中的 project/<id> 部分",
        )
        tf_name = ft.TextField(
            label="项目名称（可选）",
            hint_text="留空则使用项目 ID",
        )

        def on_save(_):
            pid = tf_project_id.value.strip()
            cookie = tf_cookie.value.strip()
            if not pid:
                tf_project_id.error_text = "项目 ID 不能为空"
                dlg.update()
                return
            if not cookie:
                tf_cookie.error_text = "Cookie 不能为空"
                dlg.update()
                return
            name = tf_name.value.strip() or pid
            self._settings.add_project(pid, cookie, name)
            self._settings.switch_project(pid)
            self._settings.save()
            self._project_title.value = f"Overleaves — {name}"
            self._refresh_project_menu()
            dlg.open = False
            self._page.update()

        dlg = ft.AlertDialog(
            title=ft.Text("创建新项目"),
            content=ft.Column(
                controls=[tf_cookie, tf_project_id, tf_name],
                spacing=12,
                tight=True,
                width=460,
            ),
            actions=[
                ft.TextButton("取消", on_click=lambda _: self._close_dlg(dlg)),
                ft.TextButton("保存", on_click=on_save),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self._page.show_dialog(dlg)

    def _on_open_project(self, project_id: str) -> None:
        """切换到已有项目，从本地缓存加载文件树。"""
        try:
            self._settings.switch_project(project_id)
            self._settings.save()
        except KeyError:
            # 项目仅在缓存中，配置中未记录 cookie，仍可加载文件树
            self._settings.current_project_id = project_id
            self._settings.save()

        meta = self._storage.load_project_meta(project_id)
        if meta:
            entities = _normalize_entities(meta.get("entities", []))
            self._current_entities = entities
            self._modified_files.clear()
            tree = _build_tree_from_entities(entities)
            self._file_tree.load_tree(tree)
            name = meta.get("name", project_id)
            self._project_title.value = f"Overleaves — {name}"
            self._tex_viewer.clear()
            self._refresh_project_menu()
            self._page.update()
        else:
            self._show_error(
                "无本地缓存",
                f"项目 {project_id} 暂无本地缓存，请切换后手动拉取远程项目。"
            )
            self._project_title.value = f"Overleaves — {project_id}"
            self._refresh_project_menu()
            self._tex_viewer.clear()
            self._page.update()

    # ------------------------------------------------------------------
    # 设置页（用 BottomSheet / Dialog 弹出，不切换路由）
    # ------------------------------------------------------------------

    def _on_open_settings(self, _) -> None:
        from gui.settings import SettingsPanel
        SettingsPanel(self._page, self._settings).show()

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    def _set_loading(self, loading: bool) -> None:
        """在事件处理器线程（调用 run_task 之前）直接调用，用于立即显示加载状态。"""
        self._progress.visible = loading
        self._btn_fetch.disabled = loading
        self._btn_compile.disabled = loading
        self._btn_push.disabled = loading
        self._page.update()

    async def _finish_loading_async(self) -> None:
        """
        后台线程任务完成后，通过 page.run_task() 调度到 asyncio 事件循环执行。
        """
        self._progress.visible = False
        self._btn_fetch.disabled = False
        self._btn_compile.disabled = False
        count = len(self._modified_files)
        self._btn_push.text = f"推送修改 ({count})" if count else "推送修改"
        self._btn_push.disabled = count == 0
        self._page.update()

    async def _finish_file_loading_async(self) -> None:
        """
        文件选择加载完成后的刷新。
        run_task 只接受无参 coroutine function，is_text 通过 self._pending_is_text 传递。
        在 asyncio 线程中统一恢复所有按钮状态，page.update() 确保 Flutter 实际重绘。
        """
        self._progress.visible = False
        self._btn_fetch.disabled = False
        self._btn_compile.disabled = False
        count = len(self._modified_files)
        self._btn_push.text = f"推送修改 ({count})" if count else "推送修改"
        self._btn_push.disabled = count == 0
        self._page.update()

    def _show_error(self, title: str, message: str) -> None:
        dlg = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[ft.TextButton("确定", on_click=lambda _: self._close_dlg(dlg))],
        )
        self._page.overlay.append(dlg)
        dlg.open = True
        self._page.update()

    def _close_dlg(self, dlg: ft.AlertDialog) -> None:
        dlg.open = False
        self._page.update()

    # ------------------------------------------------------------------
    # 事件
    # ------------------------------------------------------------------

    def _on_file_select(self, node: dict) -> None:
        project_id = self._settings.project_id
        rel_path = node.get("path") or node.get("name", "")
        node_type = node.get("type", "doc")
        if node_type == "folder":
            return

        # 判断是否是可推送的文本文件（根据扩展名）
        _TEXT_EXTS = {".tex", ".bib", ".cls", ".sty", ".txt", ".md", ".cfg",
                      ".def", ".bbx", ".cbx", ".lbx", ".aux", ".log", ".out"}
        from pathlib import Path as _Path
        is_text = _Path(rel_path).suffix.lower() in _TEXT_EXTS

        # 在主线程立即显示加载状态，确保 UI 响应及时
        self._set_loading(True)

        # 记录当前文件的 doc_id（从文件树节点直接取，无需再搜索 entities）
        self._current_doc_id = node.get("id", "")
        # run_task 只能接受无参 coroutine function，通过实例变量传递 is_text
        self._pending_is_text = is_text

        def load_task():
            try:
                content = self._storage.read_file(project_id, rel_path)
                self._tex_viewer.load_file(rel_path, content, trigger_update=False)
            except FileNotFoundError:
                self._tex_viewer.load_file(
                    rel_path,
                    f"（文件 {rel_path} 暂无本地缓存，请先拉取项目）".encode(),
                    trigger_update=False,
                )
            except Exception as e:
                logger.error("加载文件失败：%s", e)
            finally:
                # run_task 需要 coroutine function（不能调用后传入 coroutine 对象）
                self._page.run_task(self._finish_file_loading_async)

        threading.Thread(target=load_task, daemon=True).start()

    def _on_fetch(self, _) -> None:
        cookie = self._settings.cookie
        project_id = self._settings.project_id
        if not cookie:
            self._show_error("未配置 Cookie", "请先在设置中配置 Overleaf Cookie")
            return
        if not project_id:
            self._show_error("未配置项目 ID", "请先在设置中配置 Overleaf 项目 ID")
            return

        # 在主线程立即显示加载状态
        self._set_loading(True)

        def fetch_task():
            try:
                client = OverleafClient(cookie)
                # 获取文件列表（扁平结构，含 doc_id）
                entities = client.get_entities(project_id)
                # 批量下载整个项目 ZIP
                zf = client.download_project_zip(project_id)
                # 从 ZIP 中提取并保存所有文件
                for zip_name in zf.namelist():
                    content = zf.read(zip_name)
                    self._storage.save_file(project_id, zip_name, content)
                zf.close()
                # 保存 entities 元数据到本地，供下次免网络加载
                self._current_entities = entities
                self._modified_files.clear()  # 拉取后服务器版本为最新，清空本地修改记录
                proj_name = self._settings.get_project_name(project_id)
                self._storage.save_project_meta(project_id, entities, proj_name)
                # 构建文件树（不触发中间 update，由 _set_loading(False) 统一刷新）
                tree = _build_tree_from_entities(entities)
                self._file_tree.load_tree(tree, trigger_update=False)
                self._project_title.value = f"Overleaves — {proj_name}"
            except OverleafAuthError as e:
                self._show_error("认证失败", str(e))
            except OverleafNetworkError as e:
                self._show_error("网络错误", str(e))
            except OverleafNotFoundError as e:
                self._show_error("项目不存在", str(e))
            except Exception as e:
                logger.error("拉取失败：%s", e)
                self._show_error("拉取失败", str(e))
            finally:
                self._page.run_task(self._finish_loading_async)

        threading.Thread(target=fetch_task, daemon=True).start()

    def _on_compile(self, _) -> None:
        cookie = self._settings.cookie
        project_id = self._settings.project_id
        if not cookie:
            self._show_error("未配置 Cookie", "请先在设置中配置 Overleaf Cookie")
            return
        if not project_id:
            self._show_error("未配置项目 ID", "请先在设置中配置 Overleaf 项目 ID")
            return

        # 在主线程立即显示加载状态
        self._set_loading(True)

        def compile_task():
            try:
                client = OverleafClient(cookie)
                result = client.compile_project(project_id)
                if result["status"] != "success":
                    self._show_error("编译失败", "Overleaf 编译失败，请检查 TeX 源文件")
                    return
                pdf_path = self._storage.get_pdf_path(project_id)
                client.download_pdf(project_id, pdf_path, pdf_url=result.get("pdf_url", ""))
                # 不触发中间 update，由 _set_loading(False) 统一刷新
                self._pdf_viewer.reload(pdf_path, trigger_update=False)
            except OverleafAuthError as e:
                self._show_error("认证失败", str(e))
            except OverleafCompileTimeoutError as e:
                self._show_error("编译超时", str(e))
            except OverleafNetworkError as e:
                self._show_error("网络错误", str(e))
            except OverleafNotFoundError as e:
                self._show_error("资源不存在", str(e))
            except Exception as e:
                logger.error("编译/PDF 失败：%s", e)
                self._show_error("操作失败", str(e))
            finally:
                self._page.run_task(self._finish_loading_async)

        threading.Thread(target=compile_task, daemon=True).start()

    def _on_push(self, _) -> None:
        """推送所有本次会话已修改的文件到 Overleaf，并更新本地缓存。"""
        cookie = self._settings.current_cookie
        project_id = self._settings.project_id
        if not cookie:
            self._show_error("未配置 Cookie", "请先创建或配置项目的 Cookie")
            return
        if not project_id:
            self._show_error("未配置项目 ID", "请先选择或创建项目")
            return

        if not self._modified_files:
            self._show_error("无修改内容", "尚未修改任何文件，无需推送。")
            return

        # 构建 path→doc_id 映射（兼容 id 和 _id 字段名）
        path_to_id = self._build_path_doc_id_map()

        # 检查是否所有修改文件都能找到 doc_id
        missing = [p for p in self._modified_files if not path_to_id.get(p)]
        if missing:
            self._show_error(
                "部分文件无法推送",
                "以下文件找不到 doc_id（可能为二进制附件，不支持推送）：\n"
                + "\n".join(missing)
                + "\n\n如确认为文本文件，请先重新拉取项目以刷新文件列表。"
            )
            return

        # 快照当前修改，避免后台线程执行期间被新修改覆盖
        files_to_push = dict(self._modified_files)
        self._set_loading(True)

        def push_task():
            success_paths: list[str] = []
            error_msgs: list[str] = []
            try:
                client = OverleafClient(cookie)
            except Exception as e:
                self._show_error("客户端初始化失败", str(e))
                self._page.run_task(self._finish_loading_async)
                return

            for rel_path, content in files_to_push.items():
                doc_id = path_to_id[rel_path]
                try:
                    client.upload_file(project_id, doc_id, content)
                    self._storage.save_file(project_id, rel_path, content)
                    success_paths.append(rel_path)
                    logger.info("推送成功：%s (doc_id=%s)", rel_path, doc_id)
                except Exception as e:
                    logger.error("推送失败：%s → %s", rel_path, e)
                    error_msgs.append(f"{rel_path}: {e}")

            # 清除已成功推送的文件记录
            for p in success_paths:
                self._modified_files.pop(p, None)

            if error_msgs:
                self._show_error(
                    "推送部分失败",
                    f"成功推送 {len(success_paths)} 个文件，"
                    f"失败 {len(error_msgs)} 个：\n" + "\n".join(error_msgs)
                )
            else:
                # run_task 不能传带参数的 coroutine 对象；用闭包包装为无参 async def
                n = len(success_paths)
                async def _notify():
                    await self._show_push_success_async(n)
                self._page.run_task(_notify)

            self._page.run_task(self._finish_loading_async)

        threading.Thread(target=push_task, daemon=True).start()

    async def _show_push_success_async(self, count: int = 1) -> None:
        """在 UI 线程中显示推送成功提示。"""
        snack = ft.SnackBar(
            content=ft.Text(f"推送成功！已上传 {count} 个文件到 Overleaf"),
            bgcolor=ft.Colors.GREEN_700,
        )
        self._page.overlay.append(snack)
        snack.open = True
        self._page.update()
