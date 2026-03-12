"""
Overleaf HTTP 客户端：基于 Cookie 的非官方 API 接入
当前适配新版 Overleaf：使用 /entities 获取文件列表，/download/zip 批量下载
"""
import io
import logging
import re
import zipfile
from pathlib import Path
from typing import Union

import requests

from .exceptions import (
    OverleafAuthError,
    OverleafCompileTimeoutError,
    OverleafNetworkError,
    OverleafNotFoundError,
)

logger = logging.getLogger(__name__)

# Overleaf 基础 URL
BASE_URL = "https://www.overleaf.com"

# 编译超时（秒）
COMPILE_TIMEOUT = 60


class OverleafClient:
    """
    基于 Cookie Session 的 Overleaf HTTP 客户端。
    Cookie 值在日志中一律替换为 [REDACTED]。
    """

    def __init__(self, cookie: str):
        if not cookie or not cookie.strip():
            raise ValueError("Cookie 不能为空")

        self._session = requests.Session()
        self._session.headers.update(
            {
                "Cookie": cookie,
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Referer": BASE_URL,
            }
        )
        logger.info("OverleafClient 初始化，Cookie=[REDACTED]")

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    def _get(self, url: str, **kwargs) -> requests.Response:
        """执行 GET 请求，统一处理网络错误和认证失败。"""
        try:
            resp = self._session.get(url, **kwargs)
        except requests.exceptions.ConnectionError as e:
            raise OverleafNetworkError(f"网络连接失败：{e}") from e
        except requests.exceptions.Timeout as e:
            raise OverleafNetworkError(f"请求超时：{e}") from e

        if resp.status_code in (401, 403):
            raise OverleafAuthError(
                "Cookie 已失效或无权限，请在设置中更新 Overleaf Cookie"
            )
        if resp.status_code == 404:
            raise OverleafNotFoundError(f"资源不存在：{url}")
        if resp.url and "/login" in resp.url and resp.status_code == 200:
            # 发生了重定向到登录页
            raise OverleafAuthError(
                "Cookie 已失效，已被重定向到登录页，请更新 Overleaf Cookie"
            )
        return resp

    def _post(self, url: str, **kwargs) -> requests.Response:
        """执行 POST 请求，统一处理网络错误。"""
        try:
            resp = self._session.post(url, **kwargs)
        except requests.exceptions.ConnectionError as e:
            raise OverleafNetworkError(f"网络连接失败：{e}") from e
        except requests.exceptions.Timeout as e:
            raise OverleafNetworkError(f"请求超时：{e}") from e

        if resp.status_code in (401, 403):
            raise OverleafAuthError(
                "Cookie 已失效或无权限，请在设置中更新 Overleaf Cookie"
            )
        return resp

    def _extract_csrf_token(self, project_id: str) -> str:
        """从项目页面 meta[name=ol-csrfToken] 提取 CSRF token。"""
        resp = self._get(f"{BASE_URL}/project/{project_id}")
        m = re.search(r'<meta\s+name=["\']ol-csrfToken["\']\s+content=["\']([^"\']+)', resp.text)
        if m:
            return m.group(1)
        # 兜底：旧格式
        m2 = re.search(r'"csrfToken"\s*:\s*"([^"]+)"', resp.text)
        if m2:
            return m2.group(1)
        return ""

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def get_entities(self, project_id: str) -> list:
        """
        获取项目文件列表（扑平结构）。
        返回：[{"path": "/main.tex", "type": "doc"}, ...]
        path 以 / 开头，type 为 'doc'（文本）或 'file'（二进制）
        """
        url = f"{BASE_URL}/project/{project_id}/entities"
        resp = self._get(url, headers={"Accept": "application/json"})
        if resp.status_code != 200:
            raise OverleafNotFoundError(
                f"无法获取项目 {project_id} 的文件列表（HTTP {resp.status_code}）"
            )
        try:
            data = resp.json()
        except Exception as e:
            raise OverleafNetworkError(f"响应解析失败：{e}") from e
        entities = data.get("entities", [])
        # Overleaf 使用 MongoDB ObjectId，字段名为 _id 而非 id
        # 规范化为 id，确保后续推送逻辑可以统一使用 entity["id"]
        for e in entities:
            if "id" not in e and "_id" in e:
                e["id"] = e["_id"]
        logger.info("成功获取项目 %s 文件列表，共 %d 个文件", project_id, len(entities))
        return entities

    def download_project_zip(self, project_id: str) -> zipfile.ZipFile:
        """
        下载整个项目为 ZIP。
        返回可直接操作的 zipfile.ZipFile 对象。
        """
        url = f"{BASE_URL}/project/{project_id}/download/zip"
        resp = self._get(url, timeout=120)
        if resp.status_code != 200:
            raise OverleafNetworkError(
                f"下载 ZIP 失败（HTTP {resp.status_code}）"
            )
        try:
            zf = zipfile.ZipFile(io.BytesIO(resp.content))
        except zipfile.BadZipFile as e:
            raise OverleafNetworkError(f"ZIP 文件损坏：{e}") from e
        logger.info("项目 %s ZIP 下载完成，共 %d 个文件", project_id, len(zf.namelist()))
        return zf

    def compile_project(self, project_id: str) -> dict:
        """
        触发 Overleaf 远程编译。
        返回：{"status": "success"/"error", "pdf_url": "...", "output_files": [...]}
        pdf_url 为编译响应中 outputFiles 里 pdf 文件的完整 URL。
        """
        csrf = self._extract_csrf_token(project_id)
        if not csrf:
            raise OverleafAuthError("无法获取 CSRF token，请检查 Cookie 是否有效")

        url = f"{BASE_URL}/project/{project_id}/compile"
        payload = {
            "rootResourcePath": "main.tex",
            "draft": False,
            "check": "silent",
            "incrementalCompilesEnabled": True,
        }
        headers = {"X-Csrf-Token": csrf}

        resp = self._post(url, json=payload, headers=headers, timeout=COMPILE_TIMEOUT)

        if resp.status_code == 403:
            raise OverleafAuthError("编译请求被拒绝（403），CSRF token 可能已过期")
        if resp.status_code == 408 or resp.elapsed.total_seconds() >= COMPILE_TIMEOUT:
            raise OverleafCompileTimeoutError(
                f"编译请求超过 {COMPILE_TIMEOUT} 秒未返回，请稍后重试"
            )

        try:
            result = resp.json()
        except Exception as e:
            raise OverleafNetworkError(f"编译响应解析失败：{e}") from e

        status = result.get("status", "error")
        output_files = result.get("outputFiles", [])

        # 找到 PDF 文件的 URL（Overleaf 在 outputFiles 里提供完整 URL）
        pdf_url = ""
        for f in output_files:
            if f.get("path", "").endswith(".pdf") or f.get("type") == "pdf":
                pdf_url = f.get("url", "")
                break

        logger.info("项目 %s 编译结果：%s，pdf_url=%s", project_id, status, pdf_url[:60] if pdf_url else "(none)")
        return {
            "status": status,
            "pdf_url": pdf_url,
            "output_files": output_files,
        }

    def download_pdf(self, project_id: str, local_path, pdf_url: str = "") -> Path:
        """
        下载编译产出的 PDF 到 local_path。
        pdf_url: compile_project() 返回的 pdf_url（优先使用）。
        返回写入的文件路径。
        """
        local_path = Path(local_path)

        if pdf_url:
            # Overleaf 返回的 outputFiles url 可能是绝对或相对路径
            if pdf_url.startswith("http"):
                url = pdf_url
            else:
                url = BASE_URL + pdf_url
        else:
            url = f"{BASE_URL}/project/{project_id}/output/output.pdf"

        resp = self._get(url, stream=True)

        if resp.status_code == 404:
            raise OverleafNotFoundError("PDF 不存在，请先触发远程编译")
        if resp.status_code != 200:
            raise OverleafNetworkError(f"PDF 下载失败（HTTP {resp.status_code}）")

        local_path.parent.mkdir(parents=True, exist_ok=True)
        with open(local_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        logger.info("PDF 已下载到：%s", local_path)
        return local_path

    def upload_file(self, project_id: str, doc_id: str, content: str) -> None:
        """
        将修改后的文档内容推送到 Overleaf。
        使用 POST /project/{project_id}/doc/{doc_id} 更新文档内容。
        Overleaf 内部以行列表存储文档，发送时按换行符拆分。
        """
        csrf = self._extract_csrf_token(project_id)
        if not csrf:
            raise OverleafAuthError("无法获取 CSRF token，请检查 Cookie 是否有效")

        url = f"{BASE_URL}/project/{project_id}/doc/{doc_id}"
        # Overleaf 以行列表格式存储文档内容
        lines = content.split("\n")
        payload = {"doc": lines, "source": "editor", "version": 0, "ranges": []}
        headers = {"X-Csrf-Token": csrf, "Content-Type": "application/json"}

        resp = self._post(url, json=payload, headers=headers, timeout=30)

        if resp.status_code == 403:
            raise OverleafAuthError("推送被拒绝（403），CSRF token 可能已过期")
        if resp.status_code == 404:
            raise OverleafNotFoundError(f"文档不存在（doc_id={doc_id}），无法推送")
        if resp.status_code not in (200, 204):
            raise OverleafNetworkError(
                f"推送失败（HTTP {resp.status_code}）：{resp.text[:200]}"
            )
        logger.info("文档推送成功：project=%s doc=%s（%d 行）", project_id, doc_id, len(lines))
