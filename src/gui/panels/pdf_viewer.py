"""
右侧 PDF 预览面板：将 PDF 各页渲染为图片后展示
"""
import logging
from pathlib import Path
from typing import Optional

import flet as ft

logger = logging.getLogger(__name__)


class PdfViewerPanel(ft.Column):
    """
    右侧 PDF 预览面板。
    使用 pymupdf（fitz）将 PDF 各页渲染为 PNG，以 base64 图片列表展示。
    """

    def __init__(self):
        super().__init__(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=4,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self._pdf_path: Optional[Path] = None
        self._show_empty()

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def reload(self, pdf_path: str | Path, *, trigger_update: bool = True) -> None:
        """加载并渲染指定路径的 PDF 文件。
        trigger_update=False 时仅更新控件状态，不调用 update()，
        由调用方统一执行 page.update()（避免后台线程连续触发两次更新丢失）。
        """
        self._pdf_path = Path(pdf_path)
        self.controls.clear()

        if not self._pdf_path.exists():
            self._show_empty()
            if trigger_update:
                self.update()
            return

        try:
            import fitz  # PyMuPDF
        except ImportError:
            self.controls = [ft.Text("PyMuPDF 未安装，无法预览 PDF", color=ft.Colors.RED)]
            if trigger_update:
                self.update()
            return

        try:
            doc = fitz.open(str(self._pdf_path))
            page_count = len(doc)
            mat = fitz.Matrix(1.5, 1.5)
            for page_num in range(page_count):
                png_bytes = doc[page_num].get_pixmap(matrix=mat).tobytes("png")
                self.controls.append(
                    ft.Container(
                        content=ft.Image(
                            src=png_bytes,
                            fit=ft.BoxFit.CONTAIN,
                            expand=True,
                        ),
                        margin=ft.margin.symmetric(vertical=2),
                        expand=True,
                    )
                )
            doc.close()
            logger.info("PDF 预览渲染完成，共 %d 页", page_count)
        except Exception as e:
            logger.error("PDF 渲染失败：%s", e)
            self.controls = [
                ft.Text(f"PDF 预览失败：{e}", color=ft.Colors.RED)
            ]

        if trigger_update:
            self.update()

    def clear(self) -> None:
        """清空 PDF 预览，回到空状态。"""
        self._pdf_path = None
        self.controls.clear()
        self._show_empty()
        self.update()

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _show_empty(self) -> None:
        self.controls = [
            ft.Container(
                content=ft.Text(
                    "请先触发远程编译",
                    color=ft.Colors.GREY_500,
                    text_align=ft.TextAlign.CENTER,
                ),
                alignment=ft.Alignment(0, 0),
                expand=True,
                padding=20,
            )
        ]
