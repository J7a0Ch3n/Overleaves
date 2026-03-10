"""
中间文件查看/编辑面板：支持 TeX/文本文件可编辑展示，以及 PNG/JPG/PDF 图片预览
"""
import logging
from pathlib import Path

import flet as ft

logger = logging.getLogger(__name__)

# 文本类扩展名（以文本方式展示）
_TEXT_EXTS = {".tex", ".bib", ".cls", ".sty", ".txt", ".md", ".cfg", ".def",
              ".bbx", ".cbx", ".lbx", ".aux", ".log", ".out"}
# 图片类扩展名（以图片方式展示）
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg"}


class TexViewerPanel(ft.Column):
    """
    中间文件查看/编辑面板。
    - 文本文件（.tex/.bib 等）：等宽字体可编辑 TextField
    - 图片文件（.png/.jpg 等）：ft.Image 展示
    - PDF 文件：用 PyMuPDF 渲染所有页面为图片展示
    - 其他：显示提示信息
    """

    def __init__(self):
        super().__init__(expand=True, spacing=0, scroll=ft.ScrollMode.AUTO)
        self._current_filename: str = ""
        self._text_field: ft.TextField | None = None  # 当前可编辑文本域引用
        self._show_empty()

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def get_content(self) -> str:
        """获取当前编辑区域的文本内容；非文本文件或无文件时返回空字符串。"""
        if self._text_field is not None:
            return self._text_field.value or ""
        return ""

    def get_current_filename(self) -> str:
        """获取当前加载的文件名（相对路径）。"""
        return self._current_filename

    def load_file(self, filename: str, content, *, trigger_update: bool = True) -> None:
        """
        加载文件内容到面板。
        content 为 str（文本）或 bytes（二进制），面板自动选择展示方式。
        trigger_update=False 时仅更新控件状态，不调用 update()，
        由调用方统一执行 page.update()（避免后台线程连续触发两次更新丢失）。
        """
        self._current_filename = filename
        self._text_field = None  # 重置文本域引用
        ext = Path(filename).suffix.lower()

        self.controls = [self._make_title_bar(filename)]

        if ext in _TEXT_EXTS:
            if isinstance(content, bytes):
                content = content.decode("utf-8", errors="replace")
            self.controls.append(self._make_text_view(content))
        elif ext in _IMAGE_EXTS:
            if isinstance(content, bytes):
                self.controls.append(self._make_image_view_bytes(content))
            else:
                self.controls.append(ft.Text("图片内容无效", color=ft.Colors.RED))
        elif ext == ".pdf":
            self.controls.extend(self._make_pdf_views(content if isinstance(content, bytes) else content.encode()))
        else:
            # 尝试作为文本展示，失败则提示
            if isinstance(content, bytes):
                try:
                    content = content.decode("utf-8")
                except UnicodeDecodeError:
                    self.controls.append(
                        ft.Container(
                            content=ft.Text(f"暂不支持预览 {ext} 文件", color=ft.Colors.GREY_500),
                            alignment=ft.Alignment(0, 0),
                            expand=True,
                        )
                    )
                    if trigger_update:
                        self.update()
                    return
            self.controls.append(self._make_text_view(content))

        if trigger_update:
            self.update()

    def clear(self) -> None:
        """清空内容，回到空状态。"""
        self._current_filename = ""
        self._show_empty()
        self.update()

    # ------------------------------------------------------------------
    # 内部构建
    # ------------------------------------------------------------------

    def _show_empty(self) -> None:
        self.controls = [
            ft.Container(
                content=ft.Text(
                    "请在左侧选择文件",
                    color=ft.Colors.GREY_500,
                    text_align=ft.TextAlign.CENTER,
                ),
                alignment=ft.Alignment(0, 0),
                expand=True,
                padding=20,
            )
        ]

    def _make_title_bar(self, filename: str) -> ft.Control:
        return ft.Container(
            content=ft.Text(
                filename,
                size=13,
                weight=ft.FontWeight.BOLD,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
            padding=ft.padding.symmetric(horizontal=12, vertical=6),
            bgcolor=ft.Colors.SURFACE_CONTAINER,
        )

    def _make_text_view(self, content: str) -> ft.Control:
        # 超过 100KB 的文本截断显示，避免 TextField 渲染卡顿
        MAX_CHARS = 100_000
        if len(content) > MAX_CHARS:
            content = content[:MAX_CHARS] + f"\n\n... （文件过大，仅显示前 {MAX_CHARS} 字符）"
        self._text_field = ft.TextField(
            value=content,
            read_only=False,
            multiline=True,
            min_lines=1,
            expand=True,
            border=ft.InputBorder.NONE,
            text_style=ft.TextStyle(font_family="Courier New", size=13),
            bgcolor=ft.Colors.TRANSPARENT,
        )
        return ft.Container(
            content=self._text_field,
            expand=True,
            padding=ft.padding.symmetric(horizontal=8, vertical=4),
        )

    def _make_image_view_bytes(self, data: bytes) -> ft.Control:
        return ft.Container(
            content=ft.Image(
                src=data,
                fit=ft.BoxFit.CONTAIN,
                expand=True,
            ),
            expand=True,
            padding=8,
        )

    def _make_pdf_views(self, data: bytes) -> list:
        try:
            import fitz
        except ImportError:
            return [ft.Text("PyMuPDF 未安装，无法预览 PDF", color=ft.Colors.RED)]
        try:
            doc = fitz.open(stream=data, filetype="pdf")
            views = []
            for i in range(len(doc)):
                pix = doc[i].get_pixmap(matrix=fitz.Matrix(1.2, 1.2))
                png_bytes = pix.tobytes("png")
                views.append(
                    ft.Container(
                        content=ft.Image(src=png_bytes, fit=ft.BoxFit.CONTAIN, expand=True),
                        expand=True,
                        margin=ft.margin.symmetric(vertical=2),
                        padding=4,
                    )
                )
            doc.close()
            return views
        except Exception as e:
            logger.error("PDF 渲染失败：%s", e)
            return [ft.Text(f"PDF 预览失败：{e}", color=ft.Colors.RED)]

