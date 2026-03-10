"""
主应用框架：三栏布局 + AppBar，直接挂载到 page（不依赖路由/View）
"""
import logging
import threading

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
        self._tex_viewer = TexViewerPanel()
        self._pdf_viewer = PdfViewerPanel()
        self._progress = ft.ProgressBar(visible=False, height=4)
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

    def build(self) -> None:
        """将整个 UI 挂载到 page。"""
        page = self._page
        page.appbar = ft.AppBar(
            title=ft.Text("Overleaves"),
            center_title=False,
            actions=[
                self._btn_fetch,
                self._btn_compile,
                ft.IconButton(
                    icon=ft.Icons.SETTINGS,
                    tooltip="设置",
                    on_click=self._on_open_settings,
                ),
                ft.Container(width=8),
            ],
        )

        # 三个面板直接作为 Row 的子项，expand 权重才被 Flutter 正确识别
        self._file_tree.expand = 2
        self._tex_viewer.expand = 3
        self._pdf_viewer.expand = 3

        three_cols = ft.Row(
            controls=[
                self._file_tree,
                ft.VerticalDivider(width=1),
                self._tex_viewer,
                ft.VerticalDivider(width=1),
                self._pdf_viewer,
            ],
            expand=True,
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        )

        root = ft.Column(
            controls=[self._progress, three_cols],
            expand=True,
            spacing=0,
        )

        page.add(root)

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
        self._page.update()

    async def _finish_loading_async(self) -> None:
        """
        后台线程任务完成后，通过 page.run_task() 调度到 asyncio 事件循环执行。
        page.update() 在事件循环线程中调用才能可靠触发 Flutter 重绘。
        直接在 threading.Thread 里调用 page.update() 无法保证唤醒事件循环。
        """
        self._progress.visible = False
        self._btn_fetch.disabled = False
        self._btn_compile.disabled = False
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

        # 在主线程立即显示加载状态，确保 UI 响应及时
        self._set_loading(True)

        def load_task():
            try:
                content = self._storage.read_file(project_id, rel_path)
                # trigger_update=False：不在此处调用 update()，
                # 由下方 _set_loading(False) 的 page.update() 一次性刷新
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
                # 通过事件循环调度 update，确保 Flutter 收到重绘信号
                self._page.run_task(self._finish_loading_async)

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
                # 获取文件列表（扁平结构）
                entities = client.get_entities(project_id)
                # 批量下载整个项目 ZIP
                zf = client.download_project_zip(project_id)
                # 从 ZIP 中提取并保存所有文件
                for zip_name in zf.namelist():
                    content = zf.read(zip_name)
                    self._storage.save_file(project_id, zip_name, content)
                zf.close()
                # 构建文件树（不触发中间 update，由 _set_loading(False) 统一刷新）
                tree = _build_tree_from_entities(entities)
                self._file_tree.load_tree(tree, trigger_update=False)
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
