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
        llm = self._settings.llm

        self._tf_cookie = ft.TextField(
            label="Overleaf Cookie",
            hint_text="从浏览器开发者工具复制完整 Cookie 字符串",
            password=True,
            can_reveal_password=True,
            value=self._settings.cookie,
        )
        self._tf_project_id = ft.TextField(
            label="Overleaf 项目 ID",
            hint_text="项目 URL 中的 project/<id> 部分",
            value=self._settings.project_id,
        )
        self._tf_llm_key = ft.TextField(
            label="LLM API Key",
            password=True,
            can_reveal_password=True,
            value=llm.get("api_key", ""),
        )
        self._tf_llm_endpoint = ft.TextField(
            label="LLM API Endpoint",
            hint_text="例如：https://api.openai.com/v1",
            value=llm.get("endpoint", ""),
        )

        # 先构建按钮，之后再赋值 self._dlg，回调用 self._dlg 而非 lambda 局部变量
        self._dlg = ft.AlertDialog(
            title=ft.Text("设置"),
            content=ft.Column(
                controls=[
                    ft.Text("Overleaf 配置", size=14, weight=ft.FontWeight.BOLD),
                    self._tf_cookie,
                    self._tf_project_id,
                    ft.Text("LLM Agent 配置", size=14, weight=ft.FontWeight.BOLD),
                    self._tf_llm_key,
                    self._tf_llm_endpoint,
                ],
                spacing=12,
                tight=True,
                scroll=ft.ScrollMode.AUTO,
                width=460,
            ),
            actions=[
                ft.TextButton("取消", on_click=self._on_cancel),
                ft.TextButton("保存", on_click=self._on_save),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self._page.show_dialog(self._dlg)

    # ------------------------------------------------------------------
    # 事件处理
    # ------------------------------------------------------------------

    def _on_cancel(self, e) -> None:
        self._close()

    def _on_save(self, e) -> None:
        """保存所有配置到 config.json 后关闭 Dialog。"""
        self._settings.cookie = self._tf_cookie.value or ""
        self._settings.project_id = self._tf_project_id.value or ""
        self._settings.llm = {
            "api_key": self._tf_llm_key.value or "",
            "endpoint": self._tf_llm_endpoint.value or "",
        }
        self._settings.save()
        self._close()

    def _close(self) -> None:
        self._page.pop_dialog()
