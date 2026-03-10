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
