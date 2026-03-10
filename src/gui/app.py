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


def _flatten_tree(nodes: list, prefix: str = "") -> list:
    """递归展开文件树，返回 [(relative_path, node), ...] 列表。"""
    result = []
    for node in nodes:
        name = node.get("name", "")
        node_type = node.get("type", "doc")
        rel_path = name if not prefix else f"{prefix}/{name}"
        if node_type == "folder":
            children = (
                node.get("children", [])
                or node.get("docs", []) + node.get("fileRefs", []) + node.get("folders", [])
            )
            result.extend(_flatten_tree(children, rel_path))
        else:
            result.append((rel_path, node))
    return result


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
        self._progress.visible = loading
        self._btn_fetch.disabled = loading
        self._btn_compile.disabled = loading
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
        name = node.get("name", "")
        if node.get("type", "doc") != "doc":
            return
        try:
            content = self._storage.read_file(project_id, name)
            if isinstance(content, bytes):
                content = content.decode("utf-8", errors="replace")
            self._tex_viewer.load_file(name, content)
        except FileNotFoundError:
            self._tex_viewer.load_file(name, f"（文件 {name} 暂无本地缓存，请先拉取项目）")

    def _on_fetch(self, _) -> None:
        cookie = self._settings.cookie
        project_id = self._settings.project_id
        if not cookie:
            self._show_error("未配置 Cookie", "请先在设置中配置 Overleaf Cookie")
            return
        if not project_id:
            self._show_error("未配置项目 ID", "请先在设置中配置 Overleaf 项目 ID")
            return

        def fetch_task():
            try:
                self._set_loading(True)
                client = OverleafClient(cookie)
                root_folder = client.get_file_tree(project_id)
                for rel_path, node in _flatten_tree(root_folder):
                    try:
                        self._storage.save_file(project_id, rel_path, client.download_file(project_id, node))
                    except Exception as e:
                        logger.warning("跳过 %s：%s", rel_path, e)
                self._file_tree.load_tree(root_folder)
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
                self._set_loading(False)

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

        def compile_task():
            try:
                self._set_loading(True)
                client = OverleafClient(cookie)
                result = client.compile_project(project_id)
                if result["status"] != "success":
                    self._show_error("编译失败", "Overleaf 编译失败，请检查 TeX 源文件")
                    return
                pdf_path = self._storage.get_pdf_path(project_id)
                client.download_pdf(project_id, pdf_path)
                self._pdf_viewer.reload(pdf_path)
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
                self._set_loading(False)

        threading.Thread(target=compile_task, daemon=True).start()
