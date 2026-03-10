"""
设置页面：配置 Overleaf Cookie、项目 ID、LLM 参数
"""
import flet as ft

from config.settings_manager import SettingsManager


class SettingsPage(ft.View):
    """
    设置页面视图。
    通过 ft.Page.go("/settings") 进入，返回按钮回到主界面。
    """

    def __init__(self, page: ft.Page, settings: SettingsManager):
        super().__init__(route="/settings")
        self._page = page
        self._settings = settings
        self._build()

    # ------------------------------------------------------------------
    # 构建 UI
    # ------------------------------------------------------------------

    def _build(self) -> None:
        """构建设置页面所有控件。"""
        # Overleaf Cookie（密码掩码）
        self._tf_cookie = ft.TextField(
            label="Overleaf Cookie",
            hint_text="从浏览器开发者工具复制完整 Cookie 字符串",
            password=True,
            can_reveal_password=True,
            value=self._settings.cookie,
            expand=True,
        )

        # Overleaf 项目 ID
        self._tf_project_id = ft.TextField(
            label="Overleaf 项目 ID",
            hint_text="项目 URL 中的 project/<id> 部分",
            value=self._settings.project_id,
            expand=True,
        )

        # LLM API Key（密码掩码）
        llm = self._settings.llm
        self._tf_llm_key = ft.TextField(
            label="LLM API Key",
            password=True,
            can_reveal_password=True,
            value=llm.get("api_key", ""),
            expand=True,
        )

        # LLM Endpoint
        self._tf_llm_endpoint = ft.TextField(
            label="LLM API Endpoint",
            hint_text="例如：https://api.openai.com/v1",
            value=llm.get("endpoint", ""),
            expand=True,
        )

        # 保存状态提示
        self._snack = ft.SnackBar(content=ft.Text(""))

        self.appbar = ft.AppBar(
            leading=ft.IconButton(
                icon=ft.Icons.ARROW_BACK,
                tooltip="返回主界面",
                on_click=lambda _: self._page.go("/"),
            ),
            title=ft.Text("设置"),
        )

        self.controls = [
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text("Overleaf 配置", style=ft.TextThemeStyle.TITLE_MEDIUM),
                        self._tf_cookie,
                        self._tf_project_id,
                        ft.Divider(),
                        ft.Text("LLM Agent 配置", style=ft.TextThemeStyle.TITLE_MEDIUM),
                        self._tf_llm_key,
                        self._tf_llm_endpoint,
                        ft.Divider(),
                        ft.ElevatedButton(
                            text="保存配置",
                            icon=ft.Icons.SAVE,
                            on_click=self._on_save,
                        ),
                        self._snack,
                    ],
                    spacing=16,
                    scroll=ft.ScrollMode.AUTO,
                ),
                padding=24,
                expand=True,
            )
        ]

    # ------------------------------------------------------------------
    # 事件处理
    # ------------------------------------------------------------------

    def _on_save(self, _) -> None:
        """保存所有配置到 config.json。"""
        self._settings.cookie = self._tf_cookie.value or ""
        self._settings.project_id = self._tf_project_id.value or ""
        self._settings.llm = {
            "api_key": self._tf_llm_key.value or "",
            "endpoint": self._tf_llm_endpoint.value or "",
        }
        self._settings.save()

        self._snack.content = ft.Text("配置已保存")
        self._snack.open = True
        self._page.update()
