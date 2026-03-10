"""
主应用框架：Flet 应用路由、三栏布局、菜单操作
"""
import logging
import threading
from pathlib import Path

import flet as ft

from config.settings_manager import SettingsManager
from gui.panels.file_tree import FileTreePanel
from gui.panels.pdf_viewer import PdfViewerPanel
from gui.panels.tex_viewer import TexViewerPanel
from gui.settings import SettingsPage
from overleaf.client import OverleafClient
from overleaf.exceptions import (
    OverleafAuthError,
    OverleafCompileTimeoutError,
    OverleafNetworkError,
    OverleafNotFoundError,
)
from storage.local_storage import LocalStorage

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# 辅助：递归收集文件树所有节点
# ------------------------------------------------------------------

def _flatten_tree(nodes: list, prefix: str = "") -> list[tuple[str, dict]]:
    """递归展开文件树，返回 (relative_path, node) 二元组列表。"""
    result = []
    for node in nodes:
        name = node.get("name", "")
        node_type = node.get("type", "doc")
        rel_path = f"{prefix}{name}" if not prefix else f"{prefix}/{name}"

        if node_type == "folder":
            children = (
                node.get("children", [])
                or node.get("docs", [])
                + node.get("fileRefs", [])
                + node.get("folders", [])
            )
            result.extend(_flatten_tree(children, rel_path))
        else:
            result.append((rel_path, node))
    return result


# ------------------------------------------------------------------
# 主视图
# ------------------------------------------------------------------

class MainView(ft.View):
    """主界面：三栏布局 + AppBar 操作菜单。"""

    def __init__(self, page: ft.Page, settings: SettingsManager, storage: LocalStorage):
        super().__init__(route="/", padding=0)
        self._page = page
        self._settings = settings
        self._storage = storage
        self._file_tree_data: list = []
        self._loading = False

        # 三个面板
        self._file_tree = FileTreePanel(on_file_select=self._on_file_select)
        self._tex_viewer = TexViewerPanel()
        self._pdf_viewer = PdfViewerPanel()

        # 加载指示器 + 操作按钮
        self._progress = ft.ProgressBar(visible=False)
        self._btn_fetch = ft.TextButton(
            text="拉取远程项目",
            icon=ft.Icons.CLOUD_DOWNLOAD,
            on_click=self._on_fetch,
        )
        self._btn_compile = ft.TextButton(
            text="远程编译并拉取 PDF",
            icon=ft.Icons.BUILD,
            on_click=self._on_compile,
        )

        self._build()

    def _build(self) -> None:
        self.appbar = ft.AppBar(
            title=ft.Text("Overleaves"),
            center_title=False,
            actions=[
                self._btn_fetch,
                self._btn_compile,
                ft.IconButton(
                    icon=ft.Icons.SETTINGS,
                    tooltip="设置",
                    on_click=lambda _: self._page.go("/settings"),
                ),
                ft.Container(width=8),
            ],
        )

        # 三栏布局：用显式 Column(expand=True) 作根容器，确保 Row 能获得垂直空间
        # 面板直接放入 Row（不套 Container），expand=N 才会被 Flutter 正确识别
        self._file_tree.expand = 2
        self._tex_viewer.expand = 3
        self._pdf_viewer.expand = 3

        self.controls = [
            ft.Column(
                controls=[
                    self._progress,
                    ft.Row(
                        controls=[
                            self._file_tree,
                            ft.VerticalDivider(width=1, color=ft.Colors.OUTLINE_VARIANT),
                            self._tex_viewer,
                            ft.VerticalDivider(width=1, color=ft.Colors.OUTLINE_VARIANT),
                            self._pdf_viewer,
                        ],
                        expand=True,
                        spacing=0,
                        vertical_alignment=ft.CrossAxisAlignment.STRETCH,
                    ),
                ],
                expand=True,
                spacing=0,
            )
        ]

    # ------------------------------------------------------------------
    # 事件处理
    # ------------------------------------------------------------------

    def _set_loading(self, loading: bool) -> None:
        """显示/隐藏加载指示器，禁用/启用操作按钮。"""
        self._loading = loading
        self._progress.visible = loading
        self._btn_fetch.disabled = loading
        self._btn_compile.disabled = loading
        self._page.update()

    def _show_error(self, title: str, message: str) -> None:
        """弹出错误对话框。"""
        dlg = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[ft.TextButton("确定", on_click=lambda _: self._close_dialog(dlg))],
        )
        self._page.overlay.append(dlg)
        dlg.open = True
        self._page.update()

    def _close_dialog(self, dlg: ft.AlertDialog) -> None:
        dlg.open = False
        self._page.update()

    def _on_file_select(self, node: dict) -> None:
        """用户点击文件树中的文件节点。"""
        project_id = self._settings.project_id
        name = node.get("name", "")
        node_type = node.get("type", "doc")

        if node_type != "doc":
            return  # 第一阶段只展示 TeX 文本文件

        # 尝试从本地缓存读取
        try:
            content = self._storage.read_file(project_id, name)
            if isinstance(content, bytes):
                content = content.decode("utf-8", errors="replace")
            self._tex_viewer.load_file(name, content)
        except FileNotFoundError:
            self._tex_viewer.load_file(name, f"（文件 {name} 暂无本地缓存，请先拉取项目）")

    def _on_fetch(self, _) -> None:
        """拉取远程项目按钮。"""
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
                # 递归下载所有文件
                file_list = _flatten_tree(root_folder)
                for rel_path, node in file_list:
                    try:
                        content = client.download_file(project_id, node)
                        self._storage.save_file(project_id, rel_path, content)
                    except Exception as e:
                        logger.warning("跳过文件 %s：%s", rel_path, e)

                self._file_tree_data = root_folder
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
        """远程编译并拉取 PDF 按钮。"""
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

                # 下载 PDF 到本地缓存
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
                logger.error("编译或下载 PDF 失败：%s", e)
                self._show_error("操作失败", str(e))
            finally:
                self._set_loading(False)

        threading.Thread(target=compile_task, daemon=True).start()
