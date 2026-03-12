"""
诊断脚本：检查 Overleaf 项目页面的 CSRF 和 rootFolder 格式
用法：python debug_upload.py <project_id>
Cookie 从 src/config/settings_manager.py 读取（与主程序相同）
"""
import re
import sys
import html as _html
import json as _json
import os

from bs4 import BeautifulSoup as _BS4

# 把 src 加进 path，重用配置管理器
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from config.settings_manager import SettingsManager
import requests

BASE_URL = "https://www.overleaf.com"

def main():
    if len(sys.argv) < 2:
        print("用法: python debug_upload.py <project_id>")
        sys.exit(1)

    project_id = sys.argv[1]
    settings = SettingsManager()
    cookie = settings.get("cookie", "")
    if not cookie:
        print("错误：未找到 Cookie，请先在设置中填写")
        sys.exit(1)

    session = requests.Session()
    session.headers.update({
        "Cookie": cookie,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,*/*",
    })

    # ── 1. 仪表板页 /project ──────────────────────────────────────────────
    print("\n=== GET /project (仪表板) ===")
    r = session.get(f"{BASE_URL}/project", timeout=15)
    print(f"HTTP {r.status_code}, 长度 {len(r.text)} chars")
    _check_page(r.text, "dashboard")

    # ── 2. 项目编辑器页 /project/{id} ────────────────────────────────────
    print(f"\n=== GET /project/{project_id} (编辑器) ===")
    r2 = session.get(f"{BASE_URL}/project/{project_id}", timeout=15)
    print(f"HTTP {r2.status_code}, 长度 {len(r2.text)} chars")
    _check_page(r2.text, "editor")

    # 把完整 HTML 写到文件供人工检查
    out_path = f"debug_editor_page_{project_id[:8]}.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(r2.text)
    print(f"\n编辑器页 HTML 已保存到 {out_path}，可用浏览器打开或文本搜索 rootFolder/csrfToken")


def _check_page(text: str, label: str):
    soup = _BS4(text, "html.parser")

    # CSRF
    print(f"\n[{label}] CSRF：")
    tag = soup.find("meta", {"name": "ol-csrfToken"})
    if tag and tag.get("content"):
        print(f"  ✓ meta[ol-csrfToken] = {tag['content'][:30]}...")
    else:
        print("  ✗ 未找到 meta[ol-csrfToken]")
        m = re.search(r'"csrfToken"\s*:\s*"([^"]+)"', text)
        if m:
            print(f"  ✓ JS 变量 csrfToken = {m.group(1)[:30]}...")
        else:
            print("  ✗ 也未找到 JS 变量 csrfToken")

    # rootFolder
    print(f"\n[{label}] rootFolder：")
    rf_tag = soup.find("meta", {"name": "ol-rootFolder"})
    if rf_tag and rf_tag.get("content"):
        raw = rf_tag["content"]
        print(f"  ✓ meta[ol-rootFolder] content（前120字）: {raw[:120]}")
        try:
            parsed = _json.loads(_html.unescape(raw))
            print(f"  ✓ JSON 解析成功，_id = {parsed[0].get('_id','?')}, folders={len(parsed[0].get('folders',[]))}")
        except Exception as e:
            print(f"  ✗ JSON 解析失败: {e}")
    else:
        print("  ✗ 未找到 meta[ol-rootFolder]")
        # 搜索包含 rootFolder 的行
        for i, line in enumerate(text.splitlines()):
            if "rootFolder" in line:
                print(f"  [行{i+1}] {line.strip()[:150]}")
        # regex 直接找 _id
        m = re.search(r'"rootFolder"\s*:\s*\[\s*\{\s*"_id"\s*:\s*"([a-f0-9]{24})"', text)
        if m:
            print(f"  ✓ regex 匹配到 _id = {m.group(1)}")
        else:
            print("  ✗ regex 也未匹配到 _id（数据可能由 JS 动态加载，不在 HTML 中）")


if __name__ == "__main__":
    main()
