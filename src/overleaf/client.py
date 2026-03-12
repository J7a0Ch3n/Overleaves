"""
Overleaf HTTP 客户端：基于 Cookie 的非官方 API 接入
当前适配新版 Overleaf：使用 /entities 获取文件列表，/download/zip 批量下载
"""
import html as _html
import io
import json as _json
import logging
import re
import threading as _threading
import time as _time

import zipfile
from pathlib import Path
from typing import Union

import requests
import websocket as _websocket
from bs4 import BeautifulSoup as _BS4

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

    def _get_root_folder_via_socketio(self, project_id: str) -> tuple:
        """
        通过 Socket.IO WebSocket 调用 joinProject 事件获取 rootFolder._id 和子目录结构。
        必须在握手 URL 中带 projectId 参数（Overleaf 要求）。
        Returns: (root_folder_id: str, root_folders: list)
        """
        BASE = BASE_URL  # https://www.overleaf.com

        # Step 1: Socket.IO 握手（带 projectId）
        ts = int(_time.time() * 1000)
        r = self._get(f"{BASE}/socket.io/1/?t={ts}&projectId={project_id}")
        sid = r.text.split(':')[0]
        logger.debug("socket.io session id: %s", sid)

        # 合并响应 Cookie（特别是 GCLB 负载均衡 Cookie）保证后续依赖相同后端
        orig_cookie = self._session.headers.get('Cookie', '')
        cookie_dict = {}
        for part in orig_cookie.split(';'):
            part = part.strip()
            if '=' in part:
                k, v = part.split('=', 1)
                cookie_dict[k.strip()] = v.strip()
        for k, v in r.cookies.items():
            cookie_dict[k] = v
        combined_cookie = '; '.join(f'{k}={v}' for k, v in cookie_dict.items())

        result: dict = {}
        done = _threading.Event()

        def _on_open(ws):
            _time.sleep(0.05)
            event = {'name': 'joinProject', 'args': [{'project_id': project_id}]}
            try:
                ws.send(f'5:1+::{_json.dumps(event)}')
                logger.debug("joinProject 已发送")
            except Exception as e:
                logger.debug("joinProject send 失败: %s", e)
                done.set()

        def _on_message(ws, msg):
            if msg == '2::':  # heartbeat
                try: ws.send('2::')
                except: pass
                return
            # joinProjectResponse 事件（type=5）
            if '"joinProjectResponse"' in msg or '"rootFolder"' in msg:
                try:
                    # 格式: 5:::{"name":"joinProjectResponse","args":[{...}]}
                    payload = _json.loads(msg[4:])  # 跳过 '5:::'
                    args = payload.get('args', [])
                    infos = args[0] if args else {}
                    # args[0] 可能是 {publicId, project} 格式
                    project_data = infos.get('project', infos)
                    rf = project_data.get('rootFolder', [{}])[0]
                    result['root_folder_id'] = rf.get('_id', '')
                    result['root_folders'] = rf.get('folders', [])
                    logger.debug("rootFolder._id 从 socketio 获取: %s", result['root_folder_id'])
                except Exception as e:
                    logger.debug("joinProjectResponse 解析失败: %s | msg[:200]=%s", e, msg[:200])
                finally:
                    done.set()
                return
            # ack 响应（type=6）
            if msg.startswith('6:::'):
                raw = msg[4:]
                if '+' in raw[:5]:
                    raw = raw.split('+', 1)[1]
                try:
                    data = _json.loads(raw)
                    if isinstance(data, list) and len(data) > 1 and isinstance(data[1], dict):
                        infos = data[1]
                        rf = infos.get('rootFolder', [{}])[0]
                        result['root_folder_id'] = rf.get('_id', '')
                        result['root_folders'] = rf.get('folders', [])
                        logger.debug("rootFolder._id 从 socketio ack: %s", result['root_folder_id'])
                except Exception as e:
                    logger.debug("socketio ack 解析失败: %s", e)
                done.set()
            elif '7:::' in msg or 'connectionRejected' in msg:
                logger.warning("socket.io 连接被拒: %s", msg[:100])
                done.set()

        def _on_error(ws, e):
            if not done.is_set():
                logger.debug("socket.io ws 错误: %s", str(e)[:80])

        def _on_close(ws, *a):
            done.set()

        ws_url = f"wss://www.overleaf.com/socket.io/1/websocket/{sid}"
        ws = _websocket.WebSocketApp(
            ws_url,
            header={'Cookie': combined_cookie, 'User-Agent': self._session.headers.get('User-Agent', 'Mozilla/5.0')},
            on_open=_on_open, on_message=_on_message,
            on_error=_on_error, on_close=_on_close)
        t = _threading.Thread(target=lambda: ws.run_forever(ping_interval=0), daemon=True)
        t.start()
        done.wait(timeout=12)
        try: ws.close()
        except: pass

        root_folder_id = result.get('root_folder_id', '')
        root_folders = result.get('root_folders', [])
        if not root_folder_id:
            logger.warning("socket.io joinProject 未能获取 rootFolder._id")
        return root_folder_id, root_folders

    def _get_project_meta(self, project_id: str) -> tuple:
        """
        提取上传所需的 CSRF token 和 rootFolder._id。
        - CSRF 从仪表板页 /project 取
        - rootFolder 通过 Socket.IO joinProject 获取（最可靠），HTML fallback
        Returns: (csrf: str, root_folder_id: str, root_folders: list)
        """
        # ① CSRF — BS4 解析 meta[name=ol-csrfToken]
        resp_dashboard = self._get(f"{BASE_URL}/project")
        resp_editor = self._get(f"{BASE_URL}/project/{project_id}")
        text = resp_editor.text

        csrf = ""
        for _src in [resp_dashboard.text, resp_editor.text]:
            _tag = _BS4(_src, "html.parser").find("meta", {"name": "ol-csrfToken"})
            if _tag and _tag.get("content"):
                csrf = _tag["content"]
                logger.debug("CSRF 提取成功: %s...", csrf[:12])
                break
        if not csrf:
            m = re.search(r'"csrfToken"\s*:\s*"([^"]+)"', text)
            if m:
                csrf = m.group(1)
        if not csrf:
            logger.warning("CSRF token 未找到，推送可能失败")

        # ② rootFolder._id — 优先 Socket.IO joinProject，HTML 兜底
        root_folder_id = ""
        root_folders: list = []

        # 主路径：Socket.IO，100% 可靠（Overleaf 官方客户端也用这种方式）
        try:
            root_folder_id, root_folders = self._get_root_folder_via_socketio(project_id)
        except Exception as e:
            logger.debug("socket.io 获取 rootFolder 失败: %s", e)

        # HTML 兜底（旧版 Overleaf 仍把 rootFolder 放在 meta 标签里）
        if not root_folder_id:
            _rf_tag = _BS4(text, "html.parser").find("meta", {"name": "ol-rootFolder"})
            if _rf_tag and _rf_tag.get("content"):
                try:
                    root = _json.loads(_html.unescape(_rf_tag["content"]))
                    if isinstance(root, list) and root:
                        root_folder_id = root[0].get("_id", "")
                        root_folders = root[0].get("folders", [])
                except Exception as e:
                    logger.debug("ol-rootFolder meta 解析失败: %s", e)

        if not root_folder_id:
            logger.warning("无法获取 rootFolder._id，以 project_id 作为 fallback")
            root_folder_id = project_id

        logger.debug("project_meta: csrf=%s, root_folder_id=%s",
                     csrf[:8] if csrf else "NONE", root_folder_id)
        return csrf, root_folder_id, root_folders

    def _find_folder_id(self, parent_parts: list, root_folder_id: str, root_folders: list) -> str:
        """
        在 rootFolder 的 folders 树中找到指定路径对应的 folder_id。
        parent_parts: 父目录路径分段列表（不含文件名），如 ["sections"] 或 ["a", "b"]。
        """
        if not parent_parts:
            return root_folder_id
        current_id = root_folder_id
        current_folders = root_folders
        for part in parent_parts:
            found = False
            for folder in current_folders:
                if folder.get("name", "").lower() == part.lower():
                    current_id = folder.get("_id", current_id)
                    current_folders = folder.get("folders", [])
                    found = True
                    break
            if not found:
                logger.warning("子文件夹 '%s' 在远程结构中未找到，使用父级 folder_id=%s", part, current_id)
                break
        return current_id

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
        # 兼容顶层为 list 或 dict{"entities":[...]} 两种格式
        if isinstance(data, list):
            entities = data
        else:
            entities = data.get("entities", [])
        # 规范化：Overleaf 使用 MongoDB ObjectId，字段名为 _id；统一映射为 id
        for e in entities:
            if "id" not in e and "_id" in e:
                e["id"] = e["_id"]
        if entities:
            logger.debug("entities sample[0] keys: %s, id=%s, path=%s",
                         list(entities[0].keys()),
                         entities[0].get("id", "(none)"),
                         entities[0].get("path", "(none)"))
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

    def upload_file(self, project_id: str, doc_id: str, content: str, rel_path: str = "") -> None:
        """
        将修改后的文档内容推送到 Overleaf。
        使用 POST /project/{id}/upload multipart 表单上传（与 olcli 相同策略）。
        上传同名文件至同一文件夹时会覆盖现有内容。

        doc_id: 保留兼容性参数（multipart 上传不依赖 doc_id）。
        rel_path: 文件相对路径，如 "main.tex" 或 "sections/intro.tex"。
        """
        csrf, root_folder_id, root_folders = self._get_project_meta(project_id)
        if not csrf:
            raise OverleafAuthError("无法获取 CSRF token，请检查 Cookie 是否有效")

        # 解析路径：提取文件名和父目录
        parts = rel_path.replace("\\", "/").split("/") if rel_path else ["file.tex"]
        file_name = parts[-1]
        parent_parts = parts[:-1]

        # 定位到正确的文件夹
        folder_id = self._find_folder_id(parent_parts, root_folder_id, root_folders)

        file_bytes = content.encode("utf-8")
        # 新版 Overleaf 使用 Uppy 上传库，文件名通过 multipart body 的 `name` 字段传递
        # folder_id 和 _csrf 仍在 URL query string；qquuid/qqfilename/qqtotalfilesize 已废弃
        params = {
            "folder_id": folder_id,
            "_csrf": csrf,
        }
        data = {
            "name": file_name,
            "relativePath": "null",  # Uppy 约定：不在子文件夹时传 "null" 字符串
        }
        files = {"qqfile": (file_name, io.BytesIO(file_bytes), "application/octet-stream")}

        url = f"{BASE_URL}/project/{project_id}/upload"
        logger.debug("upload: folder_id=%s, file=%s, size=%d", folder_id, file_name, len(file_bytes))
        try:
            # 新版 Overleaf (Uppy)：folder_id+_csrf 在 query string，name 在 multipart body
            resp = self._session.post(url, params=params, data=data, files=files, timeout=30)
        except requests.exceptions.ConnectionError as e:
            raise OverleafNetworkError(f"网络连接失败：{e}") from e
        except requests.exceptions.Timeout as e:
            raise OverleafNetworkError(f"请求超时：{e}") from e

        if resp.status_code in (401, 403):
            raise OverleafAuthError("上传被拒绝（403），Cookie 或 CSRF token 已失效")
        if resp.status_code == 404:
            raise OverleafNotFoundError(f"项目或文件夹不存在（project={project_id}, folder={folder_id}）")
        if resp.status_code not in (200, 204):
            raise OverleafNetworkError(
                f"上传失败（HTTP {resp.status_code}）：{resp.text[:300]}"
            )

        # 检查响应体中的 success 字段
        try:
            result = resp.json()
            if result.get("success") is False:
                raise OverleafNetworkError(f"Overleaf 服务器拒绝上传：{result}")
        except ValueError:
            pass  # 204 No Content 无响应体

        logger.info("文件上传成功：project=%s path=%s folder=%s（%d 字节）",
                    project_id, rel_path, folder_id, len(file_bytes))
