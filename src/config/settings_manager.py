"""
配置管理模块：读写 ~/.overleaves/config.json
支持多项目配置，向后兼容旧版单项目配置。
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# 配置文件路径
CONFIG_DIR = Path.home() / ".overleaves"
CONFIG_FILE = CONFIG_DIR / "config.json"


class SettingsManager:
    """管理应用配置的持久化读写，支持多项目管理。"""

    def __init__(self):
        self._config: dict = {}
        self._ensure_dir()
        self._load()
        self._migrate_legacy()

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _ensure_dir(self) -> None:
        """确保配置目录存在。"""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    def _load(self) -> None:
        """从配置文件加载配置；文件不存在或格式损坏时降级为空配置。"""
        if not CONFIG_FILE.exists():
            self._config = {}
            return
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                self._config = json.load(f)
        except json.JSONDecodeError as e:
            logger.warning("配置文件格式错误，已使用空配置：%s", e)
            self._config = {}

    def _migrate_legacy(self) -> None:
        """将旧版单项目配置（cookie + project_id）迁移到多项目结构。"""
        old_project_id = self._config.get("project_id", "")
        old_cookie = self._config.get("cookie", "")
        if old_project_id and "projects" not in self._config:
            logger.info("检测到旧版配置，自动迁移到多项目结构")
            self._config.setdefault("projects", {})
            self._config["projects"][old_project_id] = {
                "cookie": old_cookie,
                "name": old_project_id,
            }
            self._config["current_project_id"] = old_project_id

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def get(self, key: str, default=None):
        """读取配置项。"""
        return self._config.get(key, default)

    def set(self, key: str, value) -> None:
        """设置配置项（内存中）。"""
        self._config[key] = value

    def save(self) -> None:
        """将当前配置持久化到 config.json（UTF-8 JSON）。"""
        self._ensure_dir()
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self._config, f, ensure_ascii=False, indent=2)
        logger.info("配置已保存到 %s", CONFIG_FILE)

    # 多项目管理 ------------------------------------------------------------------

    def add_project(self, project_id: str, cookie: str, name: str = "") -> None:
        """添加或更新一个项目配置。"""
        if not project_id or not project_id.strip():
            raise ValueError("项目 ID 不能为空")
        self._config.setdefault("projects", {})
        self._config["projects"][project_id] = {
            "cookie": cookie,
            "name": name or project_id,
        }
        logger.info("项目已添加/更新：%s", project_id)

    def switch_project(self, project_id: str) -> None:
        """切换当前活跃项目。"""
        projects = self._config.get("projects", {})
        if project_id not in projects:
            raise KeyError(f"项目 {project_id} 不存在于配置中")
        self._config["current_project_id"] = project_id
        logger.info("已切换到项目：%s", project_id)

    def list_project_ids(self) -> list:
        """列出所有已配置的项目 ID。"""
        return list(self._config.get("projects", {}).keys())

    def get_project_name(self, project_id: str) -> str:
        """获取项目显示名称。"""
        projects = self._config.get("projects", {})
        return projects.get(project_id, {}).get("name", project_id)

    # 快捷属性 ------------------------------------------------------------------

    @property
    def current_project_id(self) -> str:
        """当前活跃项目 ID。"""
        return self._config.get("current_project_id", self._config.get("project_id", ""))

    @current_project_id.setter
    def current_project_id(self, value: str) -> None:
        self._config["current_project_id"] = value

    @property
    def current_cookie(self) -> str:
        """当前活跃项目的 Cookie。"""
        pid = self.current_project_id
        projects = self._config.get("projects", {})
        if pid and pid in projects:
            return projects[pid].get("cookie", "")
        # 向后兼容
        return self._config.get("cookie", "")

    # 向后兼容属性（旧代码仍可使用）
    @property
    def cookie(self) -> str:
        return self.current_cookie

    @cookie.setter
    def cookie(self, value: str) -> None:
        # 向后兼容写法：更新当前项目的 cookie
        pid = self.current_project_id
        if pid:
            self._config.setdefault("projects", {})
            self._config["projects"].setdefault(pid, {})["cookie"] = value
        self._config["cookie"] = value

    @property
    def project_id(self) -> str:
        return self.current_project_id

    @project_id.setter
    def project_id(self, value: str) -> None:
        self._config["project_id"] = value
        self._config["current_project_id"] = value

    @property
    def llm(self) -> dict:
        return self._config.get("llm", {})

    @llm.setter
    def llm(self, value: dict) -> None:
        self._config["llm"] = value

    @property
    def is_corrupt(self) -> bool:
        """配置文件是否格式损坏（加载时发生过降级）。"""
        return hasattr(self, "_was_corrupt") and self._was_corrupt
