"""
Overleaves 应用入口
"""
import logging
import sys
from pathlib import Path

# 确保 src/ 在导入路径中（开发时直接运行用）
sys.path.insert(0, str(Path(__file__).parent))

import flet as ft

from config.settings_manager import SettingsManager
from gui.app import OverleavesApp
from storage.local_storage import LocalStorage

# 配置日志（禁止输出 Cookie 等敏感信息）
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


def main(page: ft.Page) -> None:
    """Flet 应用入口函数。"""
    page.title = "Overleaves"
    page.window.width = 1280
    page.window.height = 800
    page.window.min_width = 900
    page.window.min_height = 600
    page.theme_mode = ft.ThemeMode.SYSTEM
    page.padding = 0

    # 初始化共享服务
    settings = SettingsManager()
    storage = LocalStorage()

    # 配置文件损坏时提示用户
    if settings.is_corrupt:
        page.overlay.append(
            ft.SnackBar(
                content=ft.Text("配置文件格式错误，已使用默认配置"),
                open=True,
            )
        )

    # 直接构建应用，不使用 ft.View 路由
    app = OverleavesApp(page, settings, storage)
    app.build()


if __name__ == "__main__":
    ft.run(main)
