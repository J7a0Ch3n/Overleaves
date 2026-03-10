"""
本地存储模块：将 Overleaf 拉取的项目文件缓存到 ~/.overleaves/projects/<project_id>/
"""
import logging
from pathlib import Path
from typing import Union

logger = logging.getLogger(__name__)

# 缓存根目录
PROJECTS_DIR = Path.home() / ".overleaves" / "projects"


class LocalStorage:
    """管理 Overleaf 项目文件的本地缓存。"""

    def __init__(self):
        self._ensure_dir()

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _ensure_dir(self) -> None:
        """确保项目缓存根目录存在。"""
        PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

    def _project_dir(self, project_id: str) -> Path:
        return PROJECTS_DIR / project_id

    def _resolve_path(self, project_id: str, relative_path: str) -> Path:
        """将相对路径解析为绝对路径，同时确保父目录存在。"""
        target = self._project_dir(project_id) / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def save_file(self, project_id: str, relative_path: str, content: Union[str, bytes]) -> Path:
        """
        将文件内容保存到本地缓存。
        - content 为 str 时以 UTF-8 写入文本文件
        - content 为 bytes 时以二进制模式写入
        返回写入的绝对路径。
        """
        target = self._resolve_path(project_id, relative_path)
        if isinstance(content, str):
            target.write_text(content, encoding="utf-8")
        else:
            target.write_bytes(content)
        logger.debug("已缓存文件：%s", target)
        return target

    def read_file(self, project_id: str, relative_path: str) -> Union[str, bytes]:
        """
        从本地缓存读取文件内容。
        - .tex / .bib / .md 等文本文件返回 str（UTF-8）
        - 其余文件返回 bytes
        文件不存在时抛出 FileNotFoundError。
        """
        target = self._project_dir(project_id) / relative_path
        if not target.exists():
            raise FileNotFoundError(f"本地缓存中未找到文件：{target}")
        # 文本扩展名列表
        text_exts = {".tex", ".bib", ".txt", ".md", ".sty", ".cls", ".bst", ".cfg"}
        if target.suffix.lower() in text_exts:
            return target.read_text(encoding="utf-8")
        return target.read_bytes()

    def save_pdf(self, project_id: str, pdf_bytes: bytes) -> Path:
        """
        将编译产出的 PDF 保存到 <project_dir>/output.pdf。
        返回文件的绝对路径。
        """
        pdf_path = self._project_dir(project_id) / "output.pdf"
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_bytes(pdf_bytes)
        logger.info("PDF 已缓存：%s", pdf_path)
        return pdf_path

    def get_pdf_path(self, project_id: str) -> Path:
        """返回 PDF 的绝对路径（不检查是否存在）。"""
        return self._project_dir(project_id) / "output.pdf"

    def list_projects(self) -> list[str]:
        """列出所有已缓存的项目 ID（即 projects/ 下的子目录名）。"""
        if not PROJECTS_DIR.exists():
            return []
        return [d.name for d in PROJECTS_DIR.iterdir() if d.is_dir()]
