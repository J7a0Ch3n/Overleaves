"""
右侧 PDF 预览面板：将 PDF 各页渲染为图片后展示
"""
import base64
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

    def reload(self, pdf_path: str | Path) -> None:
        """加载并渲染指定路径的 PDF 文件。"""
        self._pdf_path = Path(pdf_path)
        self.controls.clear()

        if not self._pdf_path.exists():
            self._show_empty()
            self.update()
            return

        try:
            import fitz  # PyMuPDF
        except ImportError:
            self.controls = [ft.Text("PyMuPDF 未安装，无法预览 PDF", color=ft.Colors.RED)]
            self.update()
            return

        try:
            doc = fitz.open(str(self._pdf_path))
            for page_num in range(len(doc)):
                page = doc[page_num]
                # 按 2x 分辨率渲染（提高清晰度）
                mat = fitz.Matrix(2.0, 2.0)
                pix = page.get_pixmap(matrix=mat)
                png_bytes = pix.tobytes("png")
                b64 = base64.b64encode(png_bytes).decode("utf-8")

                self.controls.append(
                    ft.Container(
                        content=ft.Image(
                            src_base64=b64,
                            fit=ft.ImageFit.CONTAIN,
                            expand=True,
                        ),
                        margin=ft.margin.symmetric(vertical=2),
                        expand=True,
                    )
                )
            doc.close()
            logger.info("PDF 预览渲染完成，共 %d 页", len(doc))
        except Exception as e:
            logger.error("PDF 渲染失败：%s", e)
            self.controls = [
                ft.Text(f"PDF 预览失败：{e}", color=ft.Colors.RED)
            ]

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
                alignment=ft.alignment.center,
                expand=True,
                padding=20,
            )
        ]
