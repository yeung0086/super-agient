#!/usr/bin/env python3
"""
AI.Super-Agent EXE 启动器 v2.3.0：本地托管前端 + pywebview 窗口 + 浏览器回退。
v2.3.0（2026-11-12）在 v2.2.0 基础上并入融合能力：stdio MCP 桥（mcp_stdio.py）、
/api/skills 技能安装端点、前端讯飞星火双通道（OpenAI 兼容 + 原生 WebSocket）。
目录名 v2.2.0-wip 为保持既有文档与脚本绝对路径有效而保留，不代表版本号。

提供能力：
- 静态托管内嵌前端（webdist/）
- /api/config     GET/PUT   固定路径配置文件（跨重启持久化 API/MCP/主题/自定义技能/数据源）
- /api/fs         GET/POST  读写本地文件 + 列目录 + 删除（最高权限，不设安全限制）
- /api/websearch  GET       代理联网搜索（Bing 主用 + DuckDuckGo 兜底，避开前端 CORS）
- /api/data       POST      通用第三方数据 API 代理（东方财富/新闻/天气等，注入密钥、规避 CORS）
- /api/office/*   POST      办公软件操作（Word/Excel/PPT/PDF/文件搜索/日历提醒）
"""

import os
import re
import sys
import json
import socket
import threading
import time
import tempfile
import uuid
import urllib.request
import urllib.parse
import urllib.error
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# ─── 路径与版本 ──────────────────────────────────────────

def resource_path(rel: str) -> "Path":
    """获取打包后资源的绝对路径（兼容 PyInstaller _MEIPASS 与开发模式）。"""
    base = getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)
    return Path(base) / rel

APP_NAME = "AI.Super-Agent"      # 数据目录常量：保持不变，沿用既有 config.json / 会话 / 审计链
APP_VERSION = "3.3.0"
DISPLAY_NAME = "Super-Agient"    # 显示名（用户要求更名）
DEVELOPER = "yang"
LEGACY_NAME = "\u667a\u4e91"  # 智云


def _base_dir() -> "Path":
    """用户主目录下的应用数据根目录。"""
    env_dir = os.environ.get("AGENT_DATA_DIR")
    if env_dir:
        return Path(env_dir)
    return Path.home() / ".ai-super-agent"


def app_data_dir() -> "Path":
    return _base_dir() / APP_NAME


def legacy_data_dir() -> "Path":
    return _base_dir() / LEGACY_NAME


CONFIG_PATH = app_data_dir() / "config.json"
LEGACY_CONFIG_PATH = legacy_data_dir() / "config.json"


def load_config() -> dict:
    """加载配置，优先 APP_NAME 目录，回退 LEGACY_NAME。"""
    try:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        if LEGACY_CONFIG_PATH.exists():
            cfg = json.load(open(LEGACY_CONFIG_PATH, "r", encoding="utf-8"))
            save_config(cfg)  # 迁移到新路径
            return cfg
    except Exception:
        pass
    return {}


def save_config(obj: dict) -> bool:
    """持久化配置到固定路径。"""
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


# ─── 文件系统（最高权限） ────────────────────────────────

MAX_READ = 50 * 1024 * 1024  # 50MB（原 4MB → 提升至 50MB，覆盖大文档）


def _read_body(self) -> bytes:
    """读取 POST body（上限 48 MB，覆盖 25 MB 上传文件的 base64 体积）。"""
    cl = int(self.headers.get("Content-Length", 0) or 0)
    if cl > 48 * 1024 * 1024:
        return b""   # 上层解析会得到 400，避免异常中断连接
    return self.rfile.read(cl) if cl > 0 else b""


def handle_fs_get(self):
    """GET /api/fs?path=...&op=read|list|stat — 读文件 / 列目录 / 获取文件信息。"""
    q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
    path = q.get("path", [""])[0].strip()
    op = q.get("op", ["read"])[0]

    if op == "list" or (op == "read" and not path):
        d = path or os.getcwd()
        entries = []
        try:
            for name in sorted(os.listdir(d)):
                fp = os.path.join(d, name)
                try:
                    st = os.stat(fp)
                    entries.append({
                        "name": name,
                        "type": "dir" if os.path.isdir(fp) else "file",
                        "size": st.st_size,
                    })
                except Exception:
                    entries.append({"name": name, "type": "unknown", "size": 0})
        except Exception as e:
            send_json(self, {"error": "\u5217\u76ee\u5f55\u5931\u8d25\uff1a" + str(e)[:200]}, status=400)
            return
        send_json(self, {"dir": d, "entries": entries})
        return

    if op == "stat":
        if not path:
            send_json(self, {"error": "\u7f3a\u5c11 path \u53c2\u6570"}, status=400)
            return
        try:
            st = os.stat(path)
            send_json(self, {
                "path": path,
                "exists": True,
                "is_dir": os.path.isdir(path),
                "is_file": os.path.isfile(path),
                "size": st.st_size,
                "modified": st.st_mtime,
                "created": st.st_ctime,
            })
        except Exception as e:
            send_json(self, {"path": path, "exists": False, "error": str(e)[:200]}, status=200)
        return

    if op == "delete":
        if not path:
            send_json(self, {"error": "\u7f3a\u5c11 path \u53c2\u6570"}, status=400)
            return
        try:
            if os.path.isdir(path):
                import shutil
                shutil.rmtree(path)
            else:
                os.remove(path)
            send_json(self, {"ok": True, "deleted": path})
        except Exception as e:
            send_json(self, {"error": "\u5220\u9664\u5931\u8d25\uff1a" + str(e)[:200]}, status=400)
        return

    # op == "read"
    if not path:
        send_json(self, {"error": "\u7f3a\u5c11 path \u53c2\u6570"}, status=400)
        return
    try:
        size = os.path.getsize(path)
    except Exception:
        send_json(self, {"error": "\u6587\u4ef6\u4e0d\u5b58\u5728\uff1a" + path[:200]}, status=400)
        return
    if size > MAX_READ:
        send_json(self, {
            "error": f"\u6587\u4ef6\u8fc7\u5927\uff08{size} \u5b57\u8282 > {MAX_READ}\uff09\uff0c\u62d2\u7edd\u8bfb\u53d6"
        }, status=413)
        return
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        send_json(self, {"path": path, "size": size, "content": content})
    except Exception as e:
        send_json(self, {"error": "\u8bfb\u53d6\u5931\u8d25\uff1a" + str(e)[:200]}, status=400)


def handle_fs_post(self):
    """POST /api/fs?path=... — 写文件（创建/覆盖，自动创建父目录）。"""
    q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
    path = q.get("path", [""])[0].strip()
    if not path:
        send_json(self, {"error": "\u7f3a\u5c11 path \u53c2\u6570"}, status=400)
        return
    body = _read_body(self).decode("utf-8", "ignore")
    # v3.0：覆盖已有文件前自动留快照（可在「设置 → 诊断」一键回滚）
    try:
        if V3.v3_settings(load_config()).get("autoSnapshot") and os.path.isfile(path):
            with open(path, "r", encoding="utf-8", errors="replace") as f_old:
                V3.snapshot_save(path, f_old.read())
            V3.audit_append("local.snapshot", "写前快照 %s" % os.path.basename(path))
    except Exception:
        pass
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(body)
        send_json(self, {"ok": True, "path": path, "size": len(body.encode("utf-8"))})
    except Exception as e:
        send_json(self, {"error": "\u5199\u5165\u5931\u8d25\uff1a" + str(e)[:200]}, status=400)


# ─── 联网搜索（Bing + DDG 兜底） ─────────────────────────

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
HDRS = {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"}


def _get(url, timeout=15):
    req = urllib.request.Request(url, headers=dict(HDRS))
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "ignore")


def _post(url, data, timeout=15):
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=dict(HDRS))
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "ignore")


def _clean(s):
    s = re.sub(r"<[^>]+>", "", s)
    return s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'").strip()


def decode_uddg(href):
    m = re.search(r"uddg=([^&]+)", href)
    if m:
        u = urllib.parse.unquote(m.group(1))
        if u.startswith("http"):
            return u
    return ""


def parse_bing(html, limit=10):
    results = []
    for m in re.finditer(r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', html, re.S):
        url = m.group(1)
        title = _clean(m.group(2))
        if "bing.com" in url or "msn.com" in url or "go.microsoft.com" in url:
            continue
        if title and len(title) > 2 and url.startswith("http"):
            results.append({"title": title, "url": url})
            if len(results) >= limit:
                break
    return results


def parse_ddg(html, limit=10):
    results = []
    for i, m in enumerate(re.finditer(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.S)):
        href = m.group(1)
        title = _clean(m.group(2))
        url = decode_uddg(href) or href
        if title and url:
            results.append({"title": title, "url": url})
            if len(results) >= limit:
                break
    # lite 页面兜底
    if not results:
        for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*rel="nofollow"[^>]*>(.*?)</a>', html, re.S):
            url = m.group(1)
            title = _clean(m.group(2))
            if title and url.startswith("http"):
                results.append({"title": title, "url": url})
                if len(results) >= limit:
                    break
    return results


def bing_search(query, limit=10):
    return parse_bing(_get("https://www.bing.com/search?q=" + urllib.parse.quote(query) + "&count=" + str(limit)), limit)


def ddg_html(query, limit=10):
    return parse_ddg(_post("https://html.duckduckgo.com/html/", {"q": query}), limit)


def ddg_lite(query, limit=10):
    return parse_ddg(_post("https://lite.duckduckgo.com/lite/", {"q": query, "kl": "cn-zh"}), limit)


def websearch(query, limit=10):
    """Bing 主用 + DDG 兜底（多线程并发，取先到结果）。"""
    results = {}
    threads_done = {"bing": False, "ddg_html": False, "ddg_lite": False}

    def worker(name, fn):
        try:
            r = fn(query, limit)
            if r:
                results[name] = r
        except Exception:
            pass
        finally:
            threads_done[name] = True

    for name, fn in [("bing", bing_search), ("ddg_html", ddg_html), ("ddg_lite", ddg_lite)]:
        threading.Thread(target=worker, args=(name, fn), daemon=True).start()

    # 等待最多 8 秒
    deadline = time.time() + 8
    while time.time() < deadline:
        if results.get("bing") or (threads_done["bing"] and (results.get("ddg_html") or results.get("ddg_lite"))):
            break
        if all(threads_done.values()):
            break
        time.sleep(0.3)

    # 优先 Bing，其次 DDG
    for key in ("bing", "ddg_html", "ddg_lite"):
        if results.get(key):
            return results[key]
    return []


# ─── 数据源 API 代理 ──────────────────────────────────────

def data_fetch(spec):
    """
    通用数据 API 代理。
    spec: {url: "https://...?q={query}&limit={limit}", query: "...", params: {...}, headers: {...}, method: "GET|POST", body: ...}
    支持 {key} 占位符替换。
    """
    url = str(spec.get("url", "")).strip()
    if not url:
        return {"error": "missing url"}
    method = str(spec.get("method", "GET")).upper()
    headers = dict(HDRS)
    if isinstance(spec.get("headers"), dict):
        headers.update(spec["headers"])
    params = {}
    if isinstance(spec.get("params"), dict):
        params = dict(spec["params"])
    # 注入 query / 额外参数
    query = str(spec.get("query", ""))
    if query:
        params["query"] = query
    for k, v in spec.get("extra_params", {}).items():
        params[k] = v
    # 占位符替换
    for k, v in list(params.items()):
        url = url.replace("{" + k + "}", urllib.parse.quote(str(v)))
    # 超时
    timeout = int(spec.get("timeout", 15))
    # 重试
    retries = int(spec.get("retries", 1))
    for attempt in range(retries + 1):
        try:
            if method == "POST":
                body = spec.get("body", "")
                if isinstance(body, dict):
                    body = json.dumps(body)
                req = urllib.request.Request(url, data=body.encode("utf-8"), headers=headers)
            else:
                req = urllib.request.Request(url, headers=headers)
            resp = urllib.request.urlopen(req, timeout=timeout)
            ct = resp.headers.get("Content-Type", "")
            raw = resp.read()
            if "json" in ct.lower() or url.endswith(".json"):
                try:
                    return json.loads(raw.decode("utf-8", "ignore"))
                except Exception:
                    return {"raw": raw.decode("utf-8", "ignore")}
            return {"raw": raw.decode("utf-8", "ignore"), "content_type": ct}
        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode("utf-8", "ignore")
            except Exception:
                err_body = ""
            return {"error": f"HTTP {e.code} {e.reason}", "body": err_body[:500]}
        except Exception as e:
            if attempt < retries:
                time.sleep(1)
                continue
            return {"error": str(e)[:300]}


def handle_data_post(self):
    """POST /api/data — 代理第三方数据 API。"""
    raw = _read_body(self).decode("utf-8", "ignore")
    try:
        spec = json.loads(raw) if raw else {}
    except Exception:
        send_json(self, {"error": "invalid JSON"}, status=400)
        return
    send_json(self, data_fetch(spec))


# ─── 办公软件 API ────────────────────────────────────────

def _try_import(name):
    """惰性导入办公库，失败返回 None。兼容 PyInstaller 冻结环境。"""
    try:
        if name == "docx":
            import docx
            return docx
        elif name == "openpyxl":
            import openpyxl
            return openpyxl
        elif name == "pptx":
            import pptx
            return pptx
        elif name == "PyPDF2":
            import PyPDF2
            return PyPDF2
        else:
            import importlib
            return importlib.import_module(name)
    except Exception:
        return None


def handle_office_word(self):
    """POST /api/office/word — Word 文档操作。
    Body: {action: "create"|"read"|"add_heading"|"add_paragraph"|"add_table"|"list_headings", path: "...", content: "..."}
    """
    raw = _read_body(self).decode("utf-8", "ignore")
    try:
        req = json.loads(raw) if raw else {}
    except Exception:
        send_json(self, {"error": "invalid JSON"}, status=400)
        return

    docx = _try_import("docx")
    if not docx:
        send_json(self, {"error": "python-docx \u672a\u5b89\u88c5\uff0c\u8bf7\u8fd0\u884c pip install python-docx"}, status=500)
        return

    action = req.get("action", "")
    path = req.get("path", "")

    try:
        if action == "create":
            doc = docx.Document()
            # 可选：写入初始内容
            for para in req.get("paragraphs", []):
                doc.add_paragraph(para)
            doc.save(path)
            send_json(self, {"ok": True, "path": path, "message": "Word \u6587\u6863\u5df2\u521b\u5efa"})

        elif action == "read":
            if not os.path.exists(path):
                send_json(self, {"error": "\u6587\u4ef6\u4e0d\u5b58\u5728\uff1a" + path}, status=400)
                return
            doc = docx.Document(path)
            paragraphs = []
            for p in doc.paragraphs:
                paragraphs.append({
                    "text": p.text,
                    "style": p.style.name if p.style else "",
                })
            tables = []
            for t in doc.tables:
                rows = []
                for row in t.rows:
                    rows.append([cell.text for cell in row.cells])
                tables.append(rows)
            send_json(self, {
                "paragraphs": paragraphs,
                "tables": tables,
                "paragraph_count": len(paragraphs),
                "table_count": len(tables),
            })

        elif action == "add_heading":
            doc = docx.Document(path) if os.path.exists(path) else docx.Document()
            doc.add_heading(req.get("text", ""), level=int(req.get("level", 1)))
            doc.save(path)
            send_json(self, {"ok": True, "path": path})

        elif action == "add_paragraph":
            doc = docx.Document(path) if os.path.exists(path) else docx.Document()
            doc.add_paragraph(req.get("text", ""))
            doc.save(path)
            send_json(self, {"ok": True, "path": path})

        elif action == "add_table":
            doc = docx.Document(path) if os.path.exists(path) else docx.Document()
            rows = req.get("rows", 3)
            cols = req.get("cols", 3)
            data = req.get("data", [])
            table = doc.add_table(rows=rows, cols=cols, style="Table Grid")
            for i, row_data in enumerate(data):
                if i < rows:
                    for j, cell_text in enumerate(row_data):
                        if j < cols:
                            table.rows[i].cells[j].text = str(cell_text)
            doc.save(path)
            send_json(self, {"ok": True, "path": path})

        elif action == "list_headings":
            doc = docx.Document(path)
            headings = []
            for p in doc.paragraphs:
                if p.style and "Heading" in p.style.name:
                    headings.append({"text": p.text, "level": p.style.name})
            send_json(self, {"headings": headings})

        else:
            send_json(self, {"error": "\u672a\u77e5\u64cd\u4f5c\uff1a" + action}, status=400)

    except Exception as e:
        send_json(self, {"error": f"Word \u64cd\u4f5c\u5931\u8d25\uff1a{str(e)[:300]}"}, status=500)


def handle_office_excel(self):
    """POST /api/office/excel — Excel 操作。
    Body: {action: "create"|"read"|"write_cell"|"add_sheet"|"read_sheet"|"list_sheets", path: "...", sheet: "...", data: [[...]], cell: "A1", value: "..."}
    """
    raw = _read_body(self).decode("utf-8", "ignore")
    try:
        req = json.loads(raw) if raw else {}
    except Exception:
        send_json(self, {"error": "invalid JSON"}, status=400)
        return

    openpyxl = _try_import("openpyxl")
    if not openpyxl:
        send_json(self, {"error": "openpyxl \u672a\u5b89\u88c5"}, status=500)
        return

    action = req.get("action", "")
    path = req.get("path", "")

    try:
        if action == "create":
            wb = openpyxl.Workbook()
            if os.path.exists(path):
                wb = openpyxl.load_workbook(path)
            sheet_name = req.get("sheet", "Sheet1")
            if sheet_name not in wb.sheetnames:
                wb.create_sheet(sheet_name)
            wb.save(path)
            send_json(self, {"ok": True, "path": path, "sheets": wb.sheetnames})

        elif action == "read":
            wb = openpyxl.load_workbook(path, data_only=True)
            sheet_name = req.get("sheet", wb.sheetnames[0])
            ws = wb[sheet_name]
            data = []
            for row in ws.iter_rows(values_only=True):
                data.append(list(row))
            send_json(self, {
                "sheet": sheet_name,
                "rows": data,
                "row_count": len(data),
                "col_count": ws.max_column,
            })

        elif action == "read_sheet":
            wb = openpyxl.load_workbook(path, data_only=True)
            sheet_name = req.get("sheet", wb.sheetnames[0])
            ws = wb[sheet_name]
            data = []
            for row in ws.iter_rows(values_only=True):
                data.append(list(row))
            send_json(self, {"sheet": sheet_name, "rows": data, "max_row": ws.max_row, "max_col": ws.max_column})

        elif action == "list_sheets":
            wb = openpyxl.load_workbook(path, read_only=True)
            send_json(self, {"sheets": wb.sheetnames})

        elif action == "write_cell":
            wb = openpyxl.load_workbook(path) if os.path.exists(path) else openpyxl.Workbook()
            sheet_name = req.get("sheet", wb.sheetnames[0] if wb.sheetnames else "Sheet1")
            if sheet_name not in wb.sheetnames:
                wb.create_sheet(sheet_name)
            ws = wb[sheet_name]
            cell = req.get("cell", "A1")
            value = req.get("value", "")
            ws[cell] = value
            wb.save(path)
            send_json(self, {"ok": True, "path": path, "cell": cell, "value": value})

        elif action == "write_data":
            wb = openpyxl.load_workbook(path) if os.path.exists(path) else openpyxl.Workbook()
            sheet_name = req.get("sheet", wb.sheetnames[0] if wb.sheetnames else "Sheet1")
            if sheet_name not in wb.sheetnames:
                wb.create_sheet(sheet_name)
            ws = wb[sheet_name]
            data = req.get("data", [])
            for row_idx, row_data in enumerate(data, 1):
                for col_idx, val in enumerate(row_data, 1):
                    ws.cell(row=row_idx, column=col_idx, value=val)
            wb.save(path)
            send_json(self, {"ok": True, "path": path, "rows_written": len(data)})

        else:
            send_json(self, {"error": "\u672a\u77e5\u64cd\u4f5c\uff1a" + action}, status=400)

    except Exception as e:
        send_json(self, {"error": f"Excel \u64cd\u4f5c\u5931\u8d25\uff1a{str(e)[:300]}"}, status=500)


def handle_office_ppt(self):
    """POST /api/office/ppt — PPT 操作。
    Body: {action: "create"|"read"|"add_slide"|"add_text"|"add_title", path: "...", title: "...", content: "...", layout: 1}
    """
    raw = _read_body(self).decode("utf-8", "ignore")
    try:
        req = json.loads(raw) if raw else {}
    except Exception:
        send_json(self, {"error": "invalid JSON"}, status=400)
        return

    pptx = _try_import("pptx")
    if not pptx:
        send_json(self, {"error": "python-pptx \u672a\u5b89\u88c5"}, status=500)
        return

    action = req.get("action", "")
    path = req.get("path", "")

    try:
        if action == "create":
            prs = pptx.Presentation()
            prs.save(path)
            send_json(self, {"ok": True, "path": path, "message": "PPT \u5df2\u521b\u5efa"})

        elif action == "read":
            prs = pptx.Presentation(path)
            slides = []
            for i, slide in enumerate(prs.slides):
                texts = []
                for shape in slide.shapes:
                    if shape.has_text_frame:
                        for para in shape.text_frame.paragraphs:
                            texts.append(para.text)
                slides.append({"index": i, "texts": texts, "shape_count": len(slide.shapes)})
            send_json(self, {"slides": slides, "slide_count": len(slides)})

        elif action == "add_slide":
            prs = pptx.Presentation(path) if os.path.exists(path) else pptx.Presentation()
            layout_idx = int(req.get("layout", 1))
            layout = prs.slide_layouts[layout_idx] if layout_idx < len(prs.slide_layouts) else prs.slide_layouts[1]
            slide = prs.slides.add_slide(layout)
            title = req.get("title", "")
            if title and slide.shapes.title:
                slide.shapes.title.text = title
            content = req.get("content", "")
            if content:
                body_shape = slide.placeholders[1] if len(slide.placeholders) > 1 else None
                if body_shape:
                    body_shape.text = content
            prs.save(path)
            send_json(self, {"ok": True, "path": path, "slide_index": len(prs.slides) - 1})

        elif action == "add_text":
            prs = pptx.Presentation(path)
            slide_idx = int(req.get("slide_index", len(prs.slides) - 1))
            slide = prs.slides[slide_idx]
            text = req.get("text", "")
            left = pptx.util.Inches(req.get("left", 1))
            top = pptx.util.Inches(req.get("top", 2))
            width = pptx.util.Inches(req.get("width", 8))
            height = pptx.util.Inches(req.get("height", 1.5))
            txBox = slide.shapes.add_textbox(left, top, width, height)
            tf = txBox.text_frame
            tf.text = text
            prs.save(path)
            send_json(self, {"ok": True, "path": path})

        else:
            send_json(self, {"error": "\u672a\u77e5\u64cd\u4f5c\uff1a" + action}, status=400)

    except Exception as e:
        send_json(self, {"error": f"PPT \u64cd\u4f5c\u5931\u8d25\uff1a{str(e)[:300]}"}, status=500)


def handle_office_pdf(self):
    """POST /api/office/pdf — PDF 操作。
    Body: {action: "read"|"merge"|"split"|"info"|"extract_pages", path: "...", paths: [...], output: "...", pages: "1-3"}
    """
    raw = _read_body(self).decode("utf-8", "ignore")
    try:
        req = json.loads(raw) if raw else {}
    except Exception:
        send_json(self, {"error": "invalid JSON"}, status=400)
        return

    PyPDF2 = _try_import("PyPDF2")
    if not PyPDF2:
        send_json(self, {"error": "PyPDF2 \u672a\u5b89\u88c5"}, status=500)
        return

    action = req.get("action", "")

    try:
        if action == "read" or action == "info":
            path = req.get("path", "")
            reader = PyPDF2.PdfReader(path)
            pages = []
            page_range = req.get("pages")
            if page_range:
                # 解析 "1-3" 或 "1,3,5"
                if "-" in str(page_range):
                    parts = str(page_range).split("-")
                    start, end = int(parts[0]) - 1, int(parts[1])
                    indices = range(start, min(end, len(reader.pages)))
                else:
                    indices = [int(x) - 1 for x in str(page_range).split(",") if x.strip()]
            else:
                max_pages = int(req.get("max_pages", 20))
                indices = range(min(max_pages, len(reader.pages)))

            for i in indices:
                try:
                    text = reader.pages[i].extract_text() or ""
                    pages.append({"page": i + 1, "text": text[:2000]})
                except Exception:
                    pages.append({"page": i + 1, "text": "", "error": "extract failed"})

            send_json(self, {
                "page_count": len(reader.pages),
                "pages": pages,
                "metadata": dict(reader.metadata) if reader.metadata else {},
            })

        elif action == "merge":
            paths = req.get("paths", [])
            output = req.get("output", "")
            writer = PyPDF2.PdfWriter()
            for p in paths:
                reader = PyPDF2.PdfReader(p)
                for page in reader.pages:
                    writer.add_page(page)
            with open(output, "wb") as f:
                writer.write(f)
            send_json(self, {"ok": True, "output": output, "merged_count": len(paths)})

        elif action == "split":
            path = req.get("path", "")
            output_dir = req.get("output_dir", os.path.dirname(path) or ".")
            reader = PyPDF2.PdfReader(path)
            files = []
            for i, page in enumerate(reader.pages):
                writer = PyPDF2.PdfWriter()
                writer.add_page(page)
                out_path = os.path.join(output_dir, f"page_{i+1}.pdf")
                with open(out_path, "wb") as f:
                    writer.write(f)
                files.append(out_path)
            send_json(self, {"ok": True, "files": files, "count": len(files)})

        else:
            send_json(self, {"error": "\u672a\u77e5\u64cd\u4f5c\uff1a" + action}, status=400)

    except Exception as e:
        send_json(self, {"error": f"PDF \u64cd\u4f5c\u5931\u8d25\uff1a{str(e)[:300]}"}, status=500)


def handle_office_search(self):
    """POST /api/office/search — 文件搜索。
    Body: {dir: "...", pattern: "*.py", content: "keyword", recursive: true, limit: 50}
    """
    raw = _read_body(self).decode("utf-8", "ignore")
    try:
        req = json.loads(raw) if raw else {}
    except Exception:
        send_json(self, {"error": "invalid JSON"}, status=400)
        return

    search_dir = req.get("dir", os.getcwd())
    pattern = req.get("pattern", "*")
    content_kw = req.get("content", "")
    recursive = req.get("recursive", True)
    limit = int(req.get("limit", 50))

    try:
        results = []
        if recursive:
            for root, dirs, files in os.walk(search_dir):
                for name in files:
                    if len(results) >= limit:
                        break
                    import fnmatch
                    if fnmatch.fnmatch(name, pattern):
                        fp = os.path.join(root, name)
                        try:
                            st = os.stat(fp)
                            entry = {
                                "name": name,
                                "path": fp,
                                "size": st.st_size,
                                "modified": st.st_mtime,
                            }
                            # 内容搜索
                            if content_kw and st.st_size < MAX_READ:
                                try:
                                    with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                                        text = f.read()
                                    if content_kw.lower() in text.lower():
                                        entry["matched"] = True
                                    else:
                                        continue  # 不匹配则跳过
                                except Exception:
                                    pass
                            results.append(entry)
                        except Exception:
                            pass
                if len(results) >= limit:
                    break
        else:
            import fnmatch
            for name in os.listdir(search_dir):
                if len(results) >= limit:
                    break
                if fnmatch.fnmatch(name, pattern):
                    fp = os.path.join(search_dir, name)
                    if os.path.isfile(fp):
                        st = os.stat(fp)
                        results.append({"name": name, "path": fp, "size": st.st_size, "modified": st.st_mtime})

        send_json(self, {"dir": search_dir, "pattern": pattern, "results": results, "count": len(results)})

    except Exception as e:
        send_json(self, {"error": f"\u641c\u7d22\u5931\u8d25\uff1a{str(e)[:300]}"}, status=500)


def handle_office_calendar(self):
    """POST /api/office/calendar — 日历提醒。
    Body: {action: "add"|"list"|"remove"|"clear", id: "...", title: "...", time: "2026-01-01 09:00", remind_before: 10}
    """
    raw = _read_body(self).decode("utf-8", "ignore")
    try:
        req = json.loads(raw) if raw else {}
    except Exception:
        send_json(self, {"error": "invalid JSON"}, status=400)
        return

    cal_path = app_data_dir() / "reminders.json"

    def load_reminders():
        try:
            if cal_path.exists():
                return json.loads(cal_path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return []

    def save_reminders(data):
        cal_path.parent.mkdir(parents=True, exist_ok=True)
        cal_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    action = req.get("action", "")

    try:
        if action == "add":
            reminders = load_reminders()
            import time as _t
            item = {
                "id": req.get("id", f"rem_{int(_t.time())}"),
                "title": req.get("title", ""),
                "time": req.get("time", ""),
                "remind_before": int(req.get("remind_before", 10)),
                "created": _t.time(),
            }
            reminders.append(item)
            save_reminders(reminders)
            send_json(self, {"ok": True, "reminder": item})

        elif action == "list":
            reminders = load_reminders()
            # 按时间排序
            reminders.sort(key=lambda x: x.get("time", ""))
            send_json(self, {"reminders": reminders, "count": len(reminders)})

        elif action == "remove":
            reminders = load_reminders()
            rid = req.get("id", "")
            reminders = [r for r in reminders if r.get("id") != rid]
            save_reminders(reminders)
            send_json(self, {"ok": True, "removed": rid})

        elif action == "clear":
            save_reminders([])
            send_json(self, {"ok": True})

        else:
            send_json(self, {"error": "\u672a\u77e5\u64cd\u4f5c\uff1a" + action}, status=400)

    except Exception as e:
        send_json(self, {"error": f"\u65e5\u5386\u64cd\u4f5c\u5931\u8d25\uff1a{str(e)[:300]}"}, status=500)


# ─── HTTP 工具 ────────────────────────────────────────────

def send_json(self, obj, status=200):
    """发送 JSON 响应。"""
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    self.send_response(status)
    self.send_header("Content-Type", "application/json; charset=utf-8")
    self.send_header("Access-Control-Allow-Origin", "*")
    self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
    self.send_header("Access-Control-Allow-Headers", "Content-Type")
    self.end_headers()
    self.wfile.write(data)


# ─── 云端模型同源代理（v2.3.1） ─────────────────────────
# 前端把 baseUrl 填成相对路径 /api/chat，fetch 落在同源，不触发 CORS 预检。
# 讯飞 MaaS（Kong 网关）对 OPTIONS 返回 404 且不带任何 Access-Control-Allow-*，
# 浏览器直连必被拦；此路由在应用自身进程内转发，无需额外网关进程。
CHAT_UPSTREAM = "https://maas-api.cn-huabei-1.xf-yun.com/v1/chat/completions"
CHAT_DISABLE_THINKING = True  # Spark X2.5 默认开思维链（4~12s），关闭后 <1s，可过 8s 测试超时


def handle_chat_proxy(self):
    """POST /api/chat/chat/completions — 同源转发到云端 OpenAI 兼容端点。

    透传 Authorization 与上游状态码/正文；stream=true 时按 SSE 逐块转发，
    并在收到 data: [DONE] 后主动收尾（上游不会主动断开连接）。
    """
    raw = _read_body(self)
    try:
        body = json.loads(raw.decode("utf-8", "ignore")) if raw else {}
    except Exception:
        send_json(self, {"error": "invalid JSON"}, status=400)
        return
    if CHAT_DISABLE_THINKING and "enable_thinking" not in body and "thinking" not in body:
        body["enable_thinking"] = False
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    auth = self.headers.get("Authorization")
    if auth:
        headers["Authorization"] = auth
    req = urllib.request.Request(CHAT_UPSTREAM, data=payload, headers=headers, method="POST")
    try:
        upstream = urllib.request.urlopen(req, timeout=90)
    except urllib.error.HTTPError as e:
        data = e.read()
        self.send_response(e.code)
        self.send_header("Content-Type", e.headers.get("Content-Type", "application/json; charset=utf-8"))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)
        return
    except Exception as e:
        send_json(self, {"error": "上游连接失败: %s" % str(e)[:200]}, status=502)
        return
    try:
        if body.get("stream"):
            self.send_response(upstream.status)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            tail = b""
            while True:
                chunk = upstream.read1(4096) if hasattr(upstream, "read1") else upstream.read(4096)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
                tail = (tail + chunk)[-256:]
                if b"[DONE]" in tail:
                    break
        else:
            data = upstream.read()
            self.send_response(upstream.status)
            self.send_header("Content-Type", upstream.headers.get("Content-Type", "application/json; charset=utf-8"))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)
    except (BrokenPipeError, ConnectionResetError, OSError):
        pass
    finally:
        try:
            upstream.close()
        except Exception:
            pass


# ══════════════════════════════════════════════════════════
# v3.0 路由分发层
#   /api/v3/* 为 V3 新增；/api/* 旧端点全部保留（office / fs / mcp / skills…）
#   统一模型网关在后端拿密钥，前端永不接触明文 API Key。
# ══════════════════════════════════════════════════════════

import v3_core as V3
import office_skills as OS
import docgen
import filehub
import skillhub as SH
import task_engine as TE
import agent_framework as AF

# 自定义保存路径的文件不位于默认输出目录，不能直接 /output/<name> 下载。
# 这里只登记「本次会话由本机技能刚刚生成」的文件路径，用一次性 token 换取下载，
# 绝不开放任意路径读取。进程重启后 token 失效，但文件仍在本机磁盘上。
_SAVED_FILES = {}
_SAVED_LOCK = threading.Lock()


def _register_saved(path):
    if not path:
        return None
    token = uuid.uuid4().hex[:16]
    with _SAVED_LOCK:
        _SAVED_FILES[token] = str(Path(path).resolve())
    return "/api/v3/files/download?token=" + token


def _v3_path(self):
    return urllib.parse.urlparse(self.path).path


def _v3_send_raw(self, resp, stream=False):
    """把上游响应原样写回前端（状态码 / Content-Type / SSE 增量）。"""
    try:
        self.send_response(getattr(resp, "status", 200))
        if stream:
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
        else:
            self.send_header("Content-Type",
                             resp.headers.get("Content-Type", "application/json; charset=utf-8"))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        if stream:
            tail = b""
            while True:
                chunk = resp.read1(4096) if hasattr(resp, "read1") else resp.read(4096)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
                tail = (tail + chunk)[-256:]
                if b"[DONE]" in tail:
                    break
        else:
            self.wfile.write(resp.read())
    except (BrokenPipeError, ConnectionResetError, OSError):
        pass
    finally:
        try:
            resp.close()
        except Exception:
            pass


def _v3_send_error(self, code, text):
    self.send_response(code)
    self.send_header("Content-Type", "application/json; charset=utf-8")
    self.send_header("Access-Control-Allow-Origin", "*")
    self.end_headers()
    try:
        self.wfile.write(text.encode("utf-8", "replace"))
    except Exception:
        pass


_V3_ROUTE = {"mode": "proxy", "since": 0.0}
_PROXY_COOLDOWN = 60.0   # 走直连超过 60 秒后，重新试探代理是否恢复


def _v3_open_upstream(provider, body, api_key, timeout=None):
    """打开上游连接（自适应代理 / 直连）。

    本机代理偶发对 CONNECT 隧道返回 502 或长时间挂起（已实测）；直连可达但慢约 20s。
    策略：优先上次成功的通路；失败立即切另一条；HTTP 真实错误直接上抛不重试；
    走直连超过冷却时间后回探一次代理，恢复快通路。
    """
    base = str(provider.get("baseUrl") or "").rstrip("/")
    if not base:
        raise ValueError("provider.baseUrl 为空")
    url = base + "/chat/completions"
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if provider.get("authMode") != "none" and api_key:
        headers["Authorization"] = "Bearer " + str(api_key)
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")

    preferred = _V3_ROUTE["mode"]
    if preferred == "direct" and (time.time() - _V3_ROUTE["since"]) > _PROXY_COOLDOWN:
        preferred = "proxy"
    order = [preferred] + [m for m in ("proxy", "direct") if m != preferred]
    last_err = None
    for mode in order:
        opener = (urllib.request.build_opener() if mode == "proxy"
                  else urllib.request.build_opener(urllib.request.ProxyHandler({})))
        tmo = timeout or (14 if mode == "proxy" else 38)
        try:
            resp = opener.open(req, timeout=tmo)
            _V3_ROUTE.update({"mode": mode, "since": time.time()})
            return resp
        except urllib.error.HTTPError:
            raise
        except Exception as e:
            last_err = e
            continue
    raise last_err


def _v3_chat_with(self, incoming):
    """统一模型网关实现（body 由 dispatch_v3 统一解析后传入）。"""
    cfg = load_config()
    settings = V3.v3_settings(cfg)
    provider = V3.resolve_provider(cfg, incoming.get("provider"))
    fallback_id = settings.get("fallbackProvider") or "off"

    body = {
        "model": incoming.get("model") or provider.get("model") or (cfg.get("cfg") or {}).get("model") or "gpt-4o-mini",
        "messages": incoming.get("messages") or [],
        "temperature": incoming.get("temperature", 0.7),
        "stream": bool(incoming.get("stream")),
    }
    if incoming.get("tools"):
        body["tools"] = incoming["tools"]
        body["tool_choice"] = "auto"
    extra = dict(provider.get("extra") or {})
    if settings.get("disableThinking") and "enable_thinking" not in extra:
        extra["enable_thinking"] = False
    for k, v in incoming.get("extra", {}).items():
        extra[k] = v
    for k, v in extra.items():
        if k not in body:
            body[k] = v

    api_key = provider.get("apiKey") or (cfg.get("cfg") or {}).get("apiKey") or ""
    t0 = time.time()

    def attempt(prov, payload, key):
        return _v3_open_upstream(prov, payload, key)

    resp = None
    used = provider
    last_error = None
    try:
        resp = attempt(provider, body, api_key)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        # 能力探测：上游不支持 tools 时自动去掉 tools 重试一次并记住结果
        if body.get("tools") and e.code in (400, 404, 422):
            V3.save_probe(provider.get("id", "?"),
                          {"tools": False, "stream": True, "reason": "upstream rejected tools", "http": e.code})
            retry_body = {k: v for k, v in body.items() if k not in ("tools", "tool_choice")}
            try:
                resp = attempt(provider, retry_body, api_key)
                body = retry_body
            except Exception as e2:
                last_error = (getattr(e2, "code", 502), detail)
        else:
            last_error = (e.code, detail)
    except Exception as e:
        last_error = (502, "上游连接失败: %s" % str(e)[:180])

    # 降级链：主 provider 失败 → 备用 provider（若已配置）
    if resp is None and fallback_id not in ("off", "", provider.get("id")):
        fb = V3.resolve_provider(cfg, fallback_id)
        if fb.get("id") != provider.get("id") and str(fb.get("baseUrl") or "").startswith("http"):
            try:
                fb_body = dict(body)
                fb_body["model"] = fb.get("model") or fb_body["model"]
                resp = attempt(fb, fb_body, fb.get("apiKey") or api_key)
                used = fb
                body = fb_body
                last_error = None
            except Exception as e:
                last_error = (getattr(e, "code", 502), str(e)[:180])

    if resp is None:
        code, detail = last_error or (502, "未知错误")
        V3.audit_append("net.chat.error", "模型调用失败 %s" % provider.get("id"),
                        {"http": code, "ms": int((time.time() - t0) * 1000)})
        _v3_send_error(self, code if isinstance(code, int) and 400 <= code < 600 else 502, detail)
        return

    V3.audit_append("net.chat", "模型调用 %s / %s" % (used.get("id"), body.get("model")),
                    {"msgs": len(body.get("messages") or []),
                     "chars": sum(len(str(m.get("content") or "")) for m in body.get("messages") or []),
                     "stream": bool(body.get("stream")),
                     "ms": int((time.time() - t0) * 1000),
                     "fallback": used.get("id") != provider.get("id")})
    _v3_send_raw(self, resp, stream=bool(body.get("stream")))


def _v3_probe(self, query):
    """GET /api/v3/probe?id=... — 显式能力探测（用户触发才联网）。"""
    pid = (query.get("id") or [""])[0]
    cfg = load_config()
    p = V3.resolve_provider(cfg, pid)
    api_key = p.get("apiKey") or (cfg.get("cfg") or {}).get("apiKey") or ""
    probe = {"model": p.get("model") or "gpt-4o-mini",
             "messages": [{"role": "user", "content": "ping"}], "stream": False,
             "max_tokens": 16}
    t0 = time.time()
    try:
        r = _v3_open_upstream(p, probe, api_key, timeout=25)
        data = r.read()
        r.close()
        result = {"ok": True, "http": 200, "ms": int((time.time() - t0) * 1000),
                  "model": p.get("model"), "tools": None,
                  "note": "对话可用；tools 能力在首次实际调用时探测"}
    except urllib.error.HTTPError as e:
        result = {"ok": False, "http": e.code, "ms": int((time.time() - t0) * 1000),
                  "detail": e.read().decode("utf-8", "replace")[:220]}
    except Exception as e:
        result = {"ok": False, "http": 0, "ms": int((time.time() - t0) * 1000),
                  "detail": str(e)[:220]}
    V3.save_probe(p.get("id", "?"), result)
    V3.audit_append("net.probe", "能力探测 %s" % p.get("id"), {"http": result.get("http")})
    send_json(self, {"provider": p.get("id"), "result": result})


def _v3_serve_output(self, name):
    """GET /api/v3/output/<文件名> — 下载本地生成的文件（仅限输出目录内）。"""
    name = os.path.basename(urllib.parse.unquote(name or ""))
    root = OS.output_dir()
    p = (root / name).resolve()
    if not name or root.resolve() not in p.parents or not p.is_file():
        send_json(self, {"error": "文件不存在"}, status=404)
        return
    ext = p.suffix.lower()
    mime = next((v["mime"] for v in OS.FORMATS.values() if v["ext"] == ext),
                "application/octet-stream")
    try:
        data = p.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition",
                         "attachment; filename*=UTF-8''" + urllib.parse.quote(name))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)
    except (BrokenPipeError, ConnectionResetError, OSError):
        pass


def _v3_download_file(self, token="", fid=""):
    """下载：本次会话生成的文件（token）或已上传的文件（id）。不开放任意路径读取。"""
    name = ""
    if token:
        with _SAVED_LOCK:
            raw = _SAVED_FILES.get(token)
    elif fid:
        try:
            p, rec = filehub.get_path(fid)
            raw, name = str(p), rec["name"]
        except Exception as e:
            send_json(self, {"error": str(e)[:180]}, status=404)
            return
    else:
        raw = None
    if not raw:
        send_json(self, {"error": "下载凭证无效或已过期（文件仍保存在本机磁盘）"}, status=404)
        return
    p = Path(raw)
    if not p.is_file():
        send_json(self, {"error": "文件实体不存在"}, status=404)
        return
    name = name or p.name
    ext = p.suffix.lower()
    mime = next((v["mime"] for v in OS.FORMATS.values() if v["ext"] == ext),
                "application/octet-stream")
    try:
        data = p.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition",
                         "attachment; filename*=UTF-8''" + urllib.parse.quote(name))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)
    except (BrokenPipeError, ConnectionResetError, OSError):
        pass


def dispatch_v3(self, method):
    """统一分发 /api/v3/*；返回 True 表示已处理，False 交回旧路由。"""
    path = _v3_path(self)
    if not path.startswith("/api/v3/"):
        return False
    q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
    cfg = load_config()

    if method == "GET":
        # ── v3.3 内置 Agent 框架 ──────────────────────────
        if path == "/api/v3/agent":
            send_json(self, AF.manifest())
            return True
        if path == "/api/v3/agent/trace":
            send_json(self, AF.last_trace())
            return True
        if path == "/api/v3/agent/memory":
            send_json(self, {"ok": True, "items": AF.memory_list(),
                             "count": len(AF.memory_list()), "local": True})
            return True
        if path == "/api/v3/agent/describe":
            send_json(self, AF.describe())
            return True
        if path == "/api/v3/skills":
            send_json(self, SH.manifest())
            return True
        if path == "/api/v3/tasks":
            send_json(self, TE.describe())
            return True
        if path == "/api/v3/files":
            send_json(self, filehub.list_files())
            return True
        if path in ("/api/v3/files/read", "/api/v3/files/info"):
            fid = (q.get("id") or [""])[0]
            try:
                if path.endswith("/read"):
                    send_json(self, filehub.read(fid, int((q.get("maxChars") or ["60000"])[0])))
                else:
                    send_json(self, filehub.info(fid))
            except Exception as e:
                send_json(self, {"error": str(e)[:220]}, status=400)
            return True
        if path == "/api/v3/files/download":
            _v3_download_file(self, token=(q.get("token") or [""])[0],
                              fid=(q.get("id") or [""])[0])
            return True
        if path.startswith("/api/v3/output/"):
            _v3_serve_output(self, path[len("/api/v3/output/"):])
            return True
        if path == "/api/v3/health":
            hd = V3.health(cfg)
            hd.update({"app": DISPLAY_NAME, "developer": DEVELOPER,
                       "officeFramework": SH.HUB_TAG,
                       "localSkills": len(SH.ALL_SKILLS),
                       "builtinSkills": len(SH.BUILTIN_SKILLS),
                       "docTemplates": len(docgen.TEMPLATES),
                       "uploads": filehub.list_files()["count"],
                       "taskEngine": TE.ENGINE_TAG,
                       "agentEngine": AF.ENGINE_TAG,
                       "agentFrameworks": len(AF.FRAMEWORKS),
                       "agentTools": len(AF.tools()),
                       "agentMemory": len(AF.memory_list())})
            send_json(self, hd)
            return True
        if path == "/api/v3/config":
            send_json(self, V3.sanitize_config(cfg))
            return True
        if path == "/api/v3/providers":
            s = V3.v3_settings(cfg)
            send_json(self, {"providers": V3.all_providers(cfg),
                             "active": s.get("activeProvider"),
                             "fallback": s.get("fallbackProvider"),
                             "probes": V3.get_probes(), "version": V3.V3_TAG})
            return True
        if path == "/api/v3/probe":
            _v3_probe(self, q)
            return True
        if path == "/api/v3/sessions":
            sid = (q.get("id") or [""])[0]
            if sid:
                d = V3.read_session(sid)
                send_json(self, d or {"error": "会话不存在"}, status=200 if d else 404)
            else:
                send_json(self, {"sessions": V3.list_sessions()})
            return True
        if path == "/api/v3/audit":
            send_json(self, {"stats": V3.audit_stats(), "records": V3.audit_records()[-60:]})
            return True
        if path == "/api/v3/snapshots":
            send_json(self, {"snapshots": V3.snapshot_list()})
            return True
        if path == "/api/v3/diagnostics":
            send_json(self, {"version": APP_VERSION, "v3": V3.V3_TAG,
                             "app": DISPLAY_NAME, "developer": DEVELOPER,
                             "storage": str(V3.v3_root()),
                             "office": SH.manifest(),
                             "tasks": TE.describe(),
                             "files": {"root": str(filehub.root()), "count": filehub.list_files()["count"]},
                             "endpoints": ["/api/v3/health", "/api/v3/config", "/api/v3/providers",
                                           "/api/v3/probe", "/api/v3/sessions", "/api/v3/chat",
                                           "/api/v3/audit", "/api/v3/snapshots",
                                           "/api/v3/skills", "/api/v3/skills/run",
                                           "/api/v3/skills/generate", "/api/v3/output/*",
                                           "/api/v3/files", "/api/v3/files/upload",
                                           "/api/v3/files/read", "/api/v3/files/info",
                                           "/api/v3/files/delete", "/api/v3/files/download",
                                           "/api/v3/tasks", "/api/v3/tasks/execute",
                                           "/api/v3/agent", "/api/v3/agent/run",
                                           "/api/v3/agent/plan", "/api/v3/agent/compact",
                                           "/api/v3/agent/memory", "/api/v3/agent/trace"],
                             "legacy": ["/api/config", "/api/fs", "/api/websearch", "/api/data",
                                        "/api/office/*", "/api/skills", "/api/mcp/stdio/*"]})
            return True
        send_json(self, {"error": "未知 v3 端点: %s" % path}, status=404)
        return True

    # POST
    raw = _read_body(self)
    try:
        payload = json.loads(raw.decode("utf-8", "ignore")) if raw else {}
    except Exception:
        send_json(self, {"error": "invalid JSON"}, status=400)
        return True
    # ── v3.3 内置 Agent 框架：执行 / 计划 / 上下文压缩 / 记忆 ──
    if path == "/api/v3/agent/run":
        try:
            res = AF.run(goal=payload.get("goal") or payload.get("text") or "",
                         framework=payload.get("framework") or "react",
                         params=payload.get("params") or {})
            for f in res.get("files", []):
                if isinstance(f, dict) and f.get("path") and not f.get("url"):
                    f["downloadUrl"] = _register_saved(f["path"])
            send_json(self, res)
        except Exception as e:
            send_json(self, {"ok": False, "error": str(e)[:300]}, status=400)
        return True
    if path == "/api/v3/agent/plan":
        try:
            send_json(self, AF.plan(payload.get("goal") or payload.get("text") or "",
                                    payload.get("params") or {}))
        except Exception as e:
            send_json(self, {"ok": False, "error": str(e)[:300]}, status=400)
        return True
    if path == "/api/v3/agent/compact":
        try:
            send_json(self, AF.compact(payload.get("messages") or [],
                                       int(payload.get("budget") or 16000),
                                       int(payload.get("keep") or 6)))
        except Exception as e:
            send_json(self, {"ok": False, "error": str(e)[:300]}, status=400)
        return True
    if path == "/api/v3/agent/memory":
        try:
            act = str(payload.get("action") or "add")
            if act == "add":
                res = AF.memory_add(payload.get("text") or "", payload.get("tag") or "note")
            elif act == "delete":
                res = AF.memory_delete(payload.get("id") or "")
            elif act == "clear":
                res = AF.memory_clear()
            else:
                raise ValueError("未知记忆操作：%s" % act)
            send_json(self, res)
        except Exception as e:
            send_json(self, {"ok": False, "error": str(e)[:300]}, status=400)
        return True
    if path in ("/api/v3/skills/run", "/api/v3/skills/generate"):
        t0 = time.time()
        try:
            if path.endswith("/generate"):
                tpl = str(payload.get("template") or "training_plan")
                args = docgen.parse_args(payload.get("prompt") or "", payload.get("args") or {})
                res = {"ok": True, "doc": docgen.generate(tpl, args), "path": None,
                       "local": True, "modelCalls": 0, "tokens": 0, "networkCalls": 0}
            else:
                res = SH.run(str(payload.get("skill") or ""), payload.get("params") or {})
        except Exception as e:
            send_json(self, {"ok": False, "error": str(e)[:300]},
                      status=400)
            return True
        V3.audit_append("local.skill",
                        "本地办公技能 %s" % (payload.get("skill") or "text.gen"),
                        {"ms": int((time.time() - t0) * 1000),
                         "chars": res.get("chars") or 0,
                         "fmt": res.get("format") or ""})
        # 保存到自定义目录时注册一次性下载凭证，并把绝对路径回给前端
        if isinstance(res, dict):
            if res.get("path") and not res.get("url"):
                res["downloadUrl"] = _register_saved(res.get("path"))
                res["savedTo"] = res.get("savedTo") or res["path"]
            for item in (res.get("results") or []):
                if isinstance(item, dict) and item.get("path"):
                    item["downloadUrl"] = _register_saved(item["path"])
        send_json(self, res)
        return True
    # ── v3.3 新增：本地文件上传 / 删除 ─────────────────────
    if path == "/api/v3/files/upload":
        try:
            res = filehub.upload(payload.get("name") or "",
                                 payload.get("data") or payload.get("dataBase64") or "",
                                 payload.get("mime") or "")
            V3.audit_append("local.file.upload", "上传本地文件 %s" % res["file"]["name"],
                            {"size": res["file"]["size"], "ext": res["file"]["ext"]})
            send_json(self, res)
        except Exception as e:
            send_json(self, {"ok": False, "error": str(e)[:220]}, status=400)
        return True
    if path == "/api/v3/files/delete":
        try:
            res = filehub.delete(str(payload.get("id") or ""))
            V3.audit_append("local.file.delete", "删除上传文件 %s" % payload.get("id"))
            send_json(self, res)
        except Exception as e:
            send_json(self, {"ok": False, "error": str(e)[:220]}, status=400)
        return True
    # ── v3.3 新增：模型下发的任务指令 ──────────────────────
    if path == "/api/v3/tasks/execute":
        try:
            res = TE.execute(text=payload.get("text"), tasks=payload.get("tasks"),
                             defaults=payload.get("defaults") or {})
            for f in res.get("files", []):
                if isinstance(f, dict) and f.get("path") and not f.get("url"):
                    f["downloadUrl"] = _register_saved(f["path"])
            send_json(self, res)
        except Exception as e:
            send_json(self, {"ok": False, "error": str(e)[:300]}, status=400)
        return True
    if path == "/api/v3/config":
        merged = V3.merge_config(cfg, payload)
        ok = save_config(merged)
        V3.audit_append("local.config", "更新配置", {"keys": sorted(list((payload or {}).keys()))[:8]})
        send_json(self, {"ok": ok, "config": V3.sanitize_config(merged)})
        return True
    if path == "/api/v3/sessions":
        sid = str(payload.get("id") or "").strip()
        if not sid:
            send_json(self, {"ok": False, "error": "缺少会话 id"}, status=400)
            return True
        send_json(self, V3.write_session(sid, payload))
        return True
    if path == "/api/v3/sessions/delete":
        V3.audit_append("local.session.delete", "删除会话 %s" % payload.get("id"))
        send_json(self, {"ok": V3.delete_session(str(payload.get("id") or ""))})
        return True
    if path == "/api/v3/snapshots/restore":
        send_json(self, V3.snapshot_restore(str(payload.get("id") or "")))
        return True
    if path == "/api/v3/chat":
        # 已读过 body，交给 _v3_chat 会得到空 body；改为直接复用已解析对象
        _v3_chat_with(self, payload)
        return True
    send_json(self, {"error": "未知 v3 端点: %s" % path}, status=404)
    return True


class SafeHandler(SimpleHTTPRequestHandler):
    """GET/POST；宽松 CSP；/api/v3/* 为 v3.0 内核，/api/* 旧端点全部保留。"""

    def do_GET(self):
        if dispatch_v3(self, "GET"):
            return
        if self.path.startswith("/api/config"):
            send_json(self, load_config())
            return
        if self.path.startswith("/api/mcp/stdio/"):
            self._handle_mcp_stdio()
            return
        if self.path.startswith("/api/skills"):
            self._handle_skills()
            return
        if self.path.startswith("/api/websearch"):
            self.handle_websearch()
            return
        if self.path.startswith("/api/version"):
            send_json(self, {"version": APP_VERSION})
            return
        if self.path.startswith("/api/fs"):
            handle_fs_get(self)
            return
        super().do_GET()

    def do_POST(self):
        try:
            if dispatch_v3(self, "POST"):
                return
            if self.path.startswith("/api/chat/"):
                handle_chat_proxy(self)
                return
            if self.path.startswith("/api/config"):
                raw = _read_body(self).decode("utf-8", "ignore")
                obj = json.loads(raw) if raw else {}
                ok = save_config(obj)
                send_json(self, {"ok": ok})
                return
            if self.path.startswith("/api/fs"):
                handle_fs_post(self)
                return
            if self.path.startswith("/api/data"):
                handle_data_post(self)
                return
            if self.path.startswith("/api/office/word"):
                handle_office_word(self)
                return
            if self.path.startswith("/api/office/excel"):
                handle_office_excel(self)
                return
            if self.path.startswith("/api/office/ppt"):
                handle_office_ppt(self)
                return
            if self.path.startswith("/api/office/pdf"):
                handle_office_pdf(self)
                return
            if self.path.startswith("/api/office/search"):
                handle_office_search(self)
                return
            if self.path.startswith("/api/office/calendar"):
                handle_office_calendar(self)
                return
            if self.path.startswith("/api/mcp/stdio/"):
                self._handle_mcp_stdio()
                return
            if self.path.startswith("/api/skills"):
                self._handle_skills()
                return
            self.send_error(405)
        except Exception as e:
            send_json(self, {"error": str(e)[:200]}, status=400)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    do_PUT = do_POST

    def handle_websearch(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("q", [""])[0]
        send_json(self, {"query": q, "results": websearch(q)})

    def _handle_skills(self):
        """技能安装与发现（v3.0）。

        GET  /api/skills          列出 app_data/skills/ 下的本地技能包
        POST /api/skills          安装：body {id,label,description,code} → 写文件并入 config.customSkills
        """
        skills_dir = app_data_dir() / "skills"
        if self.command == "GET":
            items = []
            try:
                if skills_dir.exists():
                    for fp in sorted(skills_dir.glob("*.json")):
                        try:
                            obj = json.loads(fp.read_text(encoding="utf-8"))
                            items.append({"id": obj.get("id"), "label": obj.get("label"),
                                          "description": obj.get("description"), "file": str(fp)})
                        except Exception:
                            pass
            except Exception:
                pass
            send_json(self, {"skills": items, "dir": str(skills_dir)})
            return
        # POST：安装
        raw = _read_body(self).decode("utf-8", "ignore")
        try:
            man = json.loads(raw) if raw else {}
        except Exception:
            send_json(self, {"error": "invalid JSON"}, status=400)
            return
        sid = str(man.get("id", "")).strip()
        if not sid or not re.match(r"^[\w一-龥\-]+$", sid):
            send_json(self, {"error": "技能 id 非法（字母/数字/中文/下划线/连字符）"}, status=400)
            return
        if not man.get("code") and not man.get("run"):
            send_json(self, {"error": "技能缺少 code（JS 函数体字符串）"}, status=400)
            return
        try:
            skills_dir.mkdir(parents=True, exist_ok=True)
            pkg = {"id": sid, "label": man.get("label") or sid,
                   "description": man.get("description") or "", "code": man.get("code") or ""}
            (skills_dir / (sid + ".json")).write_text(
                json.dumps(pkg, ensure_ascii=False, indent=2), encoding="utf-8")
            # 并入 config.customSkills，跨重启持久化
            cfg = load_config()
            custom = cfg.get("customSkills") or []
            custom = [c for c in custom if (c.get("id") != sid)] if isinstance(custom, list) else []
            custom.append(pkg)
            cfg["customSkills"] = custom
            save_config(cfg)
            send_json(self, {"ok": True, "id": sid, "label": pkg["label"],
                             "note": "已写入本地技能目录并入配置；前端执行 @skills 可见，重启后自动加载。"})
        except Exception as e:
            send_json(self, {"error": "安装失败：" + str(e)[:200]}, status=500)

    def _handle_mcp_stdio(self):
        """stdio MCP 桥：把本地子进程型 MCP 暴露给前端。

        路由：/api/mcp/stdio/servers | /list?server=ID | /call?server=ID
        """
        try:
            from mcp_stdio import handle_mcp_stdio as _h
        except Exception as e:
            send_json(self, {"error": "mcp_stdio 模块未就绪：%s" % e}, status=500)
            return
        # 注意：必须先剥掉查询串再切片，否则 "list?server=x" 无法匹配 "list"
        _path = urllib.parse.urlparse(self.path).path
        path_parts = _path[len("/api/mcp/stdio/"):].split("/")
        path_parts = [p for p in path_parts if p]
        if not path_parts:
            path_parts = ["servers"]
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        body = {}
        if self.command == "POST":
            raw = _read_body(self).decode("utf-8", "ignore")
            if raw:
                try:
                    body = json.loads(raw)
                except Exception:
                    send_json(self, {"error": "invalid JSON"}, status=400)
                    return
        _h(self, path_parts, query, body)

    def end_headers(self):
        self.send_header("Content-Security-Policy",
                         "default-src * 'unsafe-inline' 'unsafe-eval' data: blob:; "
                         "connect-src *; img-src * data: blob:; "
                         "style-src * 'unsafe-inline'; font-src * data:;")
        super().end_headers()

    def log_message(self, format, *args):
        pass  # 静默日志


def pick_free_port() -> int:
    """选取一个空闲端口。"""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def serve(webroot):
    """启动 HTTP 服务，返回 (httpd, port)。"""
    def handler(*a, **kw):
        return SafeHandler(*a, directory=str(webroot), **kw)

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, port


def main():
    webroot = resource_path("webdist33")
    if not webroot.exists():
        webroot = resource_path("webdist31")
    if not webroot.exists():
        webroot = resource_path("webdist3")
    if not webroot.exists():
        webroot = resource_path("dist")
    if not (webroot / "index.html").exists():
        raise SystemExit(f"[FATAL] \u672a\u627e\u5230\u524d\u7aef\u4ea7\u7269: {webroot}")

    httpd, port = serve(webroot)
    url = f"http://127.0.0.1:{port}/"

    # v3.0：装载 stdio MCP 桥（本地子进程型 MCP，如 local-app-forge / 秒哒）
    try:
        from mcp_stdio import load_from_config as _load_stdio
        _n = _load_stdio(load_config())
        if _n:
            print(f"[mcp-stdio] 已托管 {_n} 个 stdio MCP 服务器")
    except Exception as e:
        print(f"[warn] mcp_stdio 装载失败：{e}")

    # EXE smoke test 模式
    if os.environ.get("AGENT_EXE_TEST") == "1":
        smoke_file = os.environ.get("AGENT_EXE_SMOKE_FILE") or os.path.join(tempfile.gettempdir(), "agent_smoke_url.txt")
        with open(smoke_file, "w", encoding="utf-8") as f:
            f.write(url)
        print(f"SMOKE_URL={url}")
        print(f"SMOKE_ROOT={webroot}")
        print("EXE_SMOKE=READY")
        while True:
            time.sleep(1)

    # pywebview 窗口
    try:
        import importlib
        webview = importlib.import_module("webview")
        webview.create_window(f"{DISPLAY_NAME} v{APP_VERSION}",
                              url, width=1320, height=860, min_size=(1000, 680))
        webview.start()
    except KeyboardInterrupt:
        return
    except Exception as e:
        import webbrowser
        print(f"[warn] pywebview \u4e0d\u53ef\u7528({e})\uff0c\u56de\u9000\u6d4f\u89c8\u5668")
        webbrowser.open(url)
        input("\u6309\u56de\u8f66\u9000\u51fa\u2026")


if __name__ == "__main__":
    main()
