"""
设置面板：配置 Overleaf Cookie、项目 ID、LLM 参数
以 AlertDialog 弹窗形式展示，不依赖路由/View 系统。
"""
import flet as ft

from config.settings_manager import SettingsManager


class SettingsPanel:
    """
    设置面板，通过 show() 弹出 AlertDialog。
    关闭后从 page.overlay 移除，不改变路由。
    """

    def __init__(self, page: ft.Page, settings: SettingsManager):
        self._page = page
        self._settings = settings

    def show(self) -> None:
        """弹出设置 Dialog。"""
        self._build()

    # ------------------------------------------------------------------
    # 构建 UI
    # ------------------------------------------------------------------

    def _build(self) -> None:
        """构建设置 AlertDialog 并显示。"""
        # Overleaf Cookie（密码掩码）
        self._tf_cookie = ft.TextField(
            label="Overleaf Cookie",
            hint_text="从浏览器开发者工具复制完整 Cookie 字符串",
            password=True,
            can_reveal_password=True,
            value=self._settings.cookie,
        )

        # Overleaf 项目 ID
        self._tf_project_id = ft.TextField(
            label="Overleaf 项目 ID",
            hint_text="项目 URL 中的 project/<id> 部分",
            value=self._settings.project_id,
        )

        # LLM API Key（密码掩码）
        llm = self._settings.llm
        self._tf_llm_key = ft.TextField(
            label="LLM API Key",
            password=True,
            can_reveal_password=True,
            value=llm.get("api_key", ""),
        )

        # LLM Endpoint
        self._tf_llm_endpoint = ft.TextField(
            label="LLM API Endpoint",
            hint_text="例如：https://api.openai.com/v1",
            value=llm.get("endpoint", ""),
        )

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("设置"),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text("Overleaf 配置", style=ft.TextThemeStyle.TITLE_MEDIUM),
                        self._tf_cookie,
                        self._tf_project_id,
                        ft.Divider(),
                        ft.Text("LLM Agent 配置", style=ft.TextThemeStyle.TITLE_MEDIUM),
                        self._tf_llm_key,
                        self._tf_llm_endpoint,
                    ],
                    spacing=16,
                    scroll=ft.ScrollMode.AUTO,
                ),
                width=480,
                height=400,
                padding=ft.padding.only(top=8),
            ),
            actions=[
                ft.TextButton("取消", on_click=lambda _: self._close(dlg)),
                ft.ElevatedButton(
                    "保存",
                    icon=ft.Icons.SAVE,
                    on_click=lambda _: self._on_save(dlg),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self._dlg = dlg
        self._page.overlay.append(dlg)
        dlg.open = True
        self._page.update()

    # ------------------------------------------------------------------
    # 事件处理
    # ------------------------------------------------------------------

    def _close(self, dlg: ft.AlertDialog) -> None:
        """关闭并清理 Dialog。"""
        dlg.open = False
        if dlg in self._page.overlay:
            self._page.overlay.remove(dlg)
        self._page.update()

    def _on_save(self, dlg: ft.AlertDialog) -> None:
        """保存所有配置到 config.json 后关闭 Dialog。"""
        self._settings.cookie = self._tf_cookie.value or ""
        self._settings.project_id = self._tf_project_id.value or ""
        self._settings.llm = {
            "api_key": self._tf_llm_key.value or "",
            "endpoint": self._tf_llm_endpoint.value or "",
        }
        self._settings.save()
        self._close(dlg)
