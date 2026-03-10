"""
中间 TeX 内容面板：只读展示选中的 TeX 文件文本内容
"""
import flet as ft


class TexViewerPanel(ft.Column):
    """
    中间 TeX 内容只读展示面板。
    使用等宽字体 TextField（read_only=True）展示文件内容，支持垂直滚动。
    """

    def __init__(self):
        super().__init__(expand=True, spacing=0)
        self._current_filename: str = ""
        self._show_empty()

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def load_file(self, filename: str, content: str) -> None:
        """加载文件内容到面板。"""
        self._current_filename = filename
        self.controls = [
            # 标题栏
            ft.Container(
                content=ft.Text(
                    filename,
                    size=13,
                    weight=ft.FontWeight.BOLD,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
                padding=ft.padding.symmetric(horizontal=12, vertical=6),
                bgcolor=ft.Colors.SURFACE_VARIANT,
            ),
            # 内容区
            ft.Container(
                content=ft.TextField(
                    value=content,
                    read_only=True,
                    multiline=True,
                    min_lines=1,
                    expand=True,
                    border=ft.InputBorder.NONE,
                    text_style=ft.TextStyle(
                        font_family="Courier New",
                        size=13,
                    ),
                    bgcolor=ft.Colors.TRANSPARENT,
                ),
                expand=True,
                padding=ft.padding.symmetric(horizontal=8, vertical=4),
            ),
        ]
        self.update()

    def clear(self) -> None:
        """清空内容，回到空状态。"""
        self._current_filename = ""
        self._show_empty()
        self.update()

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _show_empty(self) -> None:
        self.controls = [
            ft.Container(
                content=ft.Text(
                    "请在左侧选择文件",
                    color=ft.Colors.GREY_500,
                    text_align=ft.TextAlign.CENTER,
                ),
                alignment=ft.alignment.center,
                expand=True,
                padding=20,
            )
        ]
