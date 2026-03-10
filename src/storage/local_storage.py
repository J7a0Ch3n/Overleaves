"""
本地存储模块：将 Overleaf 拉取的项目文件缓存到 ~/.overleaves/projects/<project_id>/
支持保存/加载项目元数据（entities 列表），实现免网络加载文件树。
"""
import json
import logging
from pathlib import Path
from typing import Optional, Union

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

    def read_file(self, project_id: str, relative_path: str) -> bytes:
        """
        从本地缓存读取文件内容，统一返回 bytes。
        文件不存在时抛出 FileNotFoundError。
        """
        target = self._project_dir(project_id) / relative_path
        if not target.exists():
            raise FileNotFoundError(f"本地缓存中未找到文件：{target}")
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

    def project_exists(self, project_id: str) -> bool:
        """检查项目缓存目录是否存在。"""
        return self._project_dir(project_id).exists()

    def save_project_meta(self, project_id: str, entities: list, name: str = "") -> None:
        """
        保存项目元数据（entities 列表和项目名称）到 project_meta.json。
        用于启动时免网络自动加载文件树。
        """
        meta = {"name": name or project_id, "entities": entities}
        meta_path = self._project_dir(project_id) / "project_meta.json"
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("项目元数据已保存：%s（共 %d 个文件）", project_id, len(entities))

    def load_project_meta(self, project_id: str) -> Optional[dict]:
        """
        从缓存加载项目元数据。
        返回 {"name": ..., "entities": [...]} 字典；缓存不存在时返回 None。
        """
        meta_path = self._project_dir(project_id) / "project_meta.json"
        if not meta_path.exists():
            return None
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            logger.info("从缓存加载项目元数据：%s（共 %d 个文件）",
                        project_id, len(data.get("entities", [])))
            return data
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("项目元数据损坏，忽略缓存：%s", e)
            return None
