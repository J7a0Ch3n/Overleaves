"""
Overleaf HTTP 客户端：基于 Cookie 的非官方 API 接入
参考：https://github.com/aloth/olcli
"""
import json
import logging
import re
import time
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
        """从项目页面提取 CSRF token（_csrf 字段）。"""
        resp = self._get(f"{BASE_URL}/project/{project_id}")
        # 尝试从 HTML meta 或 script 中提取 csrfToken
        match = re.search(r'"csrfToken"\s*:\s*"([^"]+)"', resp.text)
        if match:
            return match.group(1)
        match = re.search(r'_csrf["\s:=]+(["\'])([a-zA-Z0-9\-_]+)\1', resp.text)
        if match:
            return match.group(2)
        return ""

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def get_file_tree(self, project_id: str) -> dict:
        """
        获取项目文件树。
        返回 Overleaf rootFolder 结构的嵌套字典列表。
        """
        url = f"{BASE_URL}/project/{project_id}"
        resp = self._get(url)

        # 从 HTML 中解析 window.data 里的 rootFolder
        # Overleaf 将项目数据嵌入在 <script> 标签中
        match = re.search(r"window\.data\s*=\s*(\{.*?\});\s*</script>", resp.text, re.DOTALL)
        if not match:
            # 尝试另一种格式
            match = re.search(r'"rootFolder"\s*:\s*(\[.*?\])\s*[,}]', resp.text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass
            raise OverleafNotFoundError(
                f"无法解析项目 {project_id} 的文件树，可能项目不存在或 Cookie 失效"
            )

        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError as e:
            raise OverleafNotFoundError(f"项目数据解析失败：{e}") from e

        root_folder = data.get("rootFolder", [])
        logger.info("成功获取项目 %s 文件树", project_id)
        return root_folder

    def download_file(self, project_id: str, node: dict) -> Union[str, bytes]:
        """
        根据文件节点下载文件内容。
        - type='doc'（TeX 源码等）：返回 str
        - type='file'（图片等二进制）：返回 bytes
        """
        node_type = node.get("type", "doc")
        node_id = node["_id"]

        if node_type == "doc":
            url = f"{BASE_URL}/project/{project_id}/doc/{node_id}/raw"
            resp = self._get(url)
            logger.debug("下载 doc: %s", node.get("name", node_id))
            return resp.text
        else:
            url = f"{BASE_URL}/project/{project_id}/file/{node_id}"
            resp = self._get(url)
            logger.debug("下载 file: %s", node.get("name", node_id))
            return resp.content

    def compile_project(self, project_id: str) -> dict:
        """
        触发 Overleaf 远程编译。
        等待编译完成（轮询），超时 60s 抛出 OverleafCompileTimeoutError。
        返回：{"status": "success"/"error", "output_files": [...], "logs": "..."}
        """
        csrf = self._extract_csrf_token(project_id)
        url = f"{BASE_URL}/project/{project_id}/compile"
        payload = {
            "rootResourcePath": "main.tex",
            "draft": False,
            "check": "silent",
            "incrementalCompilesEnabled": True,
        }
        headers = {}
        if csrf:
            headers["X-Csrf-Token"] = csrf

        resp = self._post(url, json=payload, headers=headers, timeout=COMPILE_TIMEOUT)

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
        logs = result.get("outputFiles", "")

        logger.info("项目 %s 编译结果：%s", project_id, status)
        return {
            "status": status,
            "output_files": output_files,
            "logs": str(logs),
        }

    def download_pdf(self, project_id: str, local_path: Union[str, Path]) -> Path:
        """
        下载编译产出的 PDF 到 local_path。
        返回写入的文件路径。
        """
        local_path = Path(local_path)
        url = f"{BASE_URL}/project/{project_id}/output/output.pdf"
        resp = self._get(url, stream=True)

        if resp.status_code == 404:
            raise OverleafNotFoundError(
                "PDF 不存在，请先触发远程编译"
            )

        local_path.parent.mkdir(parents=True, exist_ok=True)
        with open(local_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        logger.info("PDF 已下载到：%s", local_path)
        return local_path
