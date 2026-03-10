"""
配置管理模块：读写 ~/.overleaves/config.json
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# 配置文件路径
CONFIG_DIR = Path.home() / ".overleaves"
CONFIG_FILE = CONFIG_DIR / "config.json"


class SettingsManager:
    """管理应用配置的持久化读写。"""

    def __init__(self):
        self._config: dict = {}
        self._ensure_dir()
        self._load()

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
            return
        # 向后兼容：旧格式只有顶层 cookie + project_id，迁移到 projects 结构
        self._migrate_legacy_format()

    def _migrate_legacy_format(self) -> None:
        """将旧式的顶层 cookie/project_id 字段迁移到 projects 嵌套结构。"""
        old_cookie = self._config.get("cookie", "")
        old_project_id = self._config.get("project_id", "")
        if old_cookie and old_project_id and "projects" not in self._config:
            self._config.setdefault("projects", {})[old_project_id] = {
                "cookie": old_cookie,
                "name": "",
            }
            self._config.setdefault("last_project_id", old_project_id)
            logger.info("已将旧格式配置迁移到 projects 结构，project_id=%s", old_project_id)

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

    # 快捷属性 ------------------------------------------------------------------

    @property
    def cookie(self) -> str:
        return self._config.get("cookie", "")

    @cookie.setter
    def cookie(self, value: str) -> None:
        self._config["cookie"] = value

    @property
    def project_id(self) -> str:
        return self._config.get("project_id", "")

    @project_id.setter
    def project_id(self, value: str) -> None:
        self._config["project_id"] = value

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

    # 多项目管理 ------------------------------------------------------------------

    def get_projects(self) -> dict:
        """返回所有已保存的项目配置，结构为 {project_id: {cookie, name}}。"""
        return self._config.get("projects", {})

    def add_project(self, project_id: str, cookie: str, name: str = "") -> None:
        """添加或更新一个项目配置（仅写内存，需调用 save() 持久化）。"""
        self._config.setdefault("projects", {})[project_id] = {
            "cookie": cookie,
            "name": name,
        }

    def remove_project(self, project_id: str) -> None:
        """删除一个项目配置（仅写内存，需调用 save() 持久化）。"""
        self._config.get("projects", {}).pop(project_id, None)
        if self._config.get("last_project_id") == project_id:
            self._config.pop("last_project_id", None)

    @property
    def active_project_id(self) -> str:
        """当前活动项目 ID；若无则返回空串。"""
        return self._config.get("last_project_id", self._config.get("project_id", ""))

    @active_project_id.setter
    def active_project_id(self, project_id: str) -> None:
        """切换活动项目，同步更新顶层 cookie/project_id 保持向后兼容。"""
        self._config["last_project_id"] = project_id
        self._config["project_id"] = project_id
        project_cfg = self._config.get("projects", {}).get(project_id, {})
        cookie = project_cfg.get("cookie", "")
        if cookie:
            self._config["cookie"] = cookie
        logger.info("已切换活动项目：%s", project_id)
