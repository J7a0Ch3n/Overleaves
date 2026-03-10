"""
左侧文件树面板：展示 Overleaf 项目文件/文件夹层级结构
"""
from typing import Callable, Optional

import flet as ft


class FileTreePanel(ft.Column):
    """
    左侧文件树面板。
    接收 rootFolder（Overleaf 文件树列表）并渲染为可展开的树形控件。
    """

    def __init__(self, on_file_select: Optional[Callable[[dict], None]] = None):
        """
        Args:
            on_file_select: 点击文件节点时的回调，传入节点 dict
        """
        super().__init__(expand=True, scroll=ft.ScrollMode.AUTO, spacing=0)
        self._on_file_select = on_file_select
        self._show_empty()

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def load_tree(self, root_folder: list) -> None:
        """加载并渲染文件树。"""
        self.controls.clear()
        if not root_folder:
            self._show_empty()
            return
        for node in root_folder:
            self.controls.append(self._build_node(node, depth=0))
        self.update()

    def clear(self) -> None:
        """清空文件树，回到空状态提示。"""
        self.controls.clear()
        self._show_empty()
        self.update()

    # ------------------------------------------------------------------
    # 内部构建
    # ------------------------------------------------------------------

    def _show_empty(self) -> None:
        self.controls = [
            ft.Container(
                content=ft.Text(
                    "请先拉取远程项目",
                    color=ft.Colors.GREY_500,
                    text_align=ft.TextAlign.CENTER,
                ),
                alignment=ft.Alignment(0, 0),
                expand=True,
                padding=20,
            )
        ]

    def _build_node(self, node: dict, depth: int) -> ft.Control:
        """递归构建文件/文件夹节点控件。"""
        node_type = node.get("type", "doc")
        name = node.get("name", "未命名")

        if node_type == "folder":
            return self._build_folder(node, name, depth)
        else:
            return self._build_file(node, name, depth)

    def _build_file(self, node: dict, name: str, depth: int) -> ft.Control:
        """构建文件叶节点。"""
        # 根据扩展名选图标
        icon = ft.Icons.DESCRIPTION
        if name.endswith(".pdf"):
            icon = ft.Icons.PICTURE_AS_PDF
        elif name.endswith((".png", ".jpg", ".jpeg", ".gif", ".eps")):
            icon = ft.Icons.IMAGE
        elif name.endswith(".bib"):
            icon = ft.Icons.BOOK

        def on_click(_):
            if self._on_file_select:
                self._on_file_select(node)

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(icon, size=16, color=ft.Colors.BLUE_GREY_400),
                    ft.Text(name, size=13, overflow=ft.TextOverflow.ELLIPSIS, expand=True),
                ],
                spacing=6,
            ),
            padding=ft.padding.only(left=depth * 16 + 8, top=4, bottom=4, right=8),
            on_click=on_click,
            border_radius=4,
            ink=True,
        )

    def _build_folder(self, node: dict, name: str, depth: int) -> ft.Control:
        """构建可展开/折叠的文件夹节点。"""
        children = node.get("children", []) or node.get("folders", []) + node.get("docs", []) + node.get("fileRefs", [])

        # 用 ExpansionTile 实现展开折叠
        child_controls = [self._build_node(child, depth + 1) for child in children]

        return ft.ExpansionTile(
            title=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.FOLDER, size=16, color=ft.Colors.AMBER_600),
                    ft.Text(name, size=13, overflow=ft.TextOverflow.ELLIPSIS, expand=True),
                ],
                spacing=6,
            ),
            controls=child_controls,
            tile_padding=ft.padding.only(left=depth * 16 + 4),
            initially_expanded=(depth == 0),
        )
