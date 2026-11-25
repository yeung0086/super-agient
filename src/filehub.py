# -*- coding: utf-8 -*-
"""Super-Agient 本地文件枢纽（filehub）。

职责：把用户上传的本地文件收进应用数据目录，并**在本机**解析成可注入上下文的
纯文本 / 结构化块，供内置技能与模型任务指令消费。

硬约束：
  - 只读写本机路径，不发起任何网络请求，不调用云端模型
  - 上传内容不出本机；解析结果只回传给本机前端
  - 文件名白名单清洗 + id 隔离，禁止路径穿越
  - 对无法可靠解析的格式（扫描版 PDF / 老式 .doc）明确说明，不伪造文本
"""

import base64
import hashlib
import json
import re
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

import v3_core as V3

HUB_TAG = "filehub-3.3.0"
MAX_UPLOAD = 25 * 1024 * 1024          # 单文件 25 MB
MAX_TEXT = 60000                        # 单文件解析文本上限（字符）
_LOCK = threading.Lock()

ALLOWED_EXT = {
    ".pdf", ".docx", ".xlsx", ".pptx", ".html", ".htm", ".md", ".markdown",
    ".txt", ".csv", ".json", ".log", ".xml", ".yaml", ".yml", ".srt", ".vtt",
    ".py", ".js", ".css", ".sql", ".ini", ".tsv",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff",
    # 老式二进制格式：接收但给出明确的转换建议
    ".doc", ".xls", ".ppt",
}
LEGACY_HINT = {
    ".doc": "旧版 Word 二进制格式，本机无法可靠解析，请另存为 .docx 后重新上传",
    ".xls": "旧版 Excel 二进制格式，请另存为 .xlsx 后重新上传",
    ".ppt": "旧版 PPT 二进制格式，请另存为 .pptx 后重新上传",
}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff"}


def root():
    p = V3.v3_root() / "uploads"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _index_path():
    return root() / "index.json"


def _load_index():
    p = _index_path()
    if not p.exists():
        return {}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save_index(d):
    _index_path().write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_name(s, fallback="文件"):
    s = re.sub(r"[\\/:*?\"<>|\r\n\t\x00-\x1f]", "_", str(s or ""))
    s = re.sub(r"\s+", " ", s).strip(" ._")
    return (s[:80] or fallback)


def decode_bytes(b):
    """编码容错：中文 Windows 常见 gbk/gb18030 也要能读。"""
    for enc in ("utf-8-sig", "utf-8", "gb18030", "cp936", "big5", "latin-1"):
        try:
            return b.decode(enc)
        except Exception:
            continue
    return b.decode("utf-8", "ignore")


# ─── 各格式本地解析 ──────────────────────────────────────
def _parse_pdf(path):
    """PyPDF2 文本层提取。图片型/扫描版 PDF 没有文本层，明确返回警告。"""
    from PyPDF2 import PdfReader
    reader = PdfReader(str(path))
    pages = []
    for i, page in enumerate(reader.pages, 1):
        try:
            t = page.extract_text() or ""
        except Exception as e:
            t = ""
            pages.append("[第 %d 页提取失败：%s]" % (i, str(e)[:80]))
            continue
        pages.append(t.strip())
    text = "\n\n".join("[第 %d 页]\n%s" % (i + 1, t) for i, t in enumerate(pages) if t)
    meta = {"pages": len(reader.pages)}
    warns = []
    if len(text.strip()) < 20:
        warns.append("未检测到可提取文本层：这份 PDF 很可能是扫描件或由图片拼成，本机没有 OCR 引擎。"
                     "建议改用文字版 PDF，或用 Word / HTML 作为源头重新生成。")
    return text, meta, warns


def _parse_docx(path):
    from docx import Document
    d = Document(str(path))
    parts, tables = [], 0
    for p in d.paragraphs:
        t = (p.text or "").strip()
        if t:
            style = (p.style.name if p.style else "") or ""
            if "Heading" in style or "标题" in style:
                parts.append("## " + t)
            else:
                parts.append(t)
    for tb in d.tables:
        rows = [[(c.text or "").strip() for c in r.cells] for r in tb.rows]
        if not rows:
            continue
        tables += 1
        parts.append("\n".join("| " + " | ".join(r) + " |" for r in rows))
    meta = {"paragraphs": len(d.paragraphs), "tables": tables}
    return "\n\n".join(parts), meta, []


def _parse_xlsx(path):
    from openpyxl import load_workbook
    wb = load_workbook(str(path), read_only=True, data_only=True)
    parts, total = [], 0
    for ws in wb.worksheets:
        parts.append("## 工作表：" + ws.title)
        rows = []
        for row in ws.iter_rows(values_only=True):
            if row is None:
                continue
            cells = ["" if v is None else str(v) for v in row]
            if not any(c.strip() for c in cells):
                continue
            rows.append(cells)
            total += 1
            if len(rows) >= 400:
                parts.append("（本表只取前 400 行）")
                break
        if rows:
            parts.append("\n".join("| " + " | ".join(c) + " |" for c in rows))
    wb.close()
    return "\n\n".join(parts), {"sheets": len(wb.worksheets), "rows": total}, []


def _parse_pptx(path):
    from pptx import Presentation
    prs = Presentation(str(path))
    parts, shapes = [], 0
    for i, slide in enumerate(prs.slides, 1):
        buf = ["## 第 %d 页" % i]
        for sh in slide.shapes:
            if getattr(sh, "has_text_frame", False):
                t = (sh.text_frame.text or "").strip()
                if t:
                    buf.append(t)
                    shapes += 1
        parts.append("\n".join(buf))
    return "\n\n".join(parts), {"slides": len(prs.slides), "textShapes": shapes}, []


def _parse_html(path):
    raw = path.read_bytes()
    try:
        from lxml import html as LH
        doc = LH.fromstring(raw)
        for bad in doc.xpath("//script|//style|//noscript"):
            bad.getparent().remove(bad)
        text = doc.text_content()
        title = (doc.xpath("//title/text()") or [""])[0]
        if title.strip():
            text = "# " + title.strip() + "\n\n" + text
        meta = {"htmlTitle": title.strip()}
    except Exception:
        text = re.sub(r"<[^>]+>", " ", decode_bytes(raw))
        meta = {}
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text, meta, []


def _parse_image(path):
    from PIL import Image
    with Image.open(str(path)) as im:
        meta = {"width": im.width, "height": im.height, "mode": im.mode, "format": im.format}
    warns = ["图片文件已上传，本机未配置 OCR 引擎，无法提取图中文字；可读取尺寸与格式信息。"]
    return "", meta, warns


def parse(path, max_chars=MAX_TEXT):
    """统一解析入口 -> {text, meta, warnings, chars, hasText}"""
    ext = path.suffix.lower()
    warns = []
    if ext in LEGACY_HINT:
        return "", {"ext": ext}, [LEGACY_HINT[ext]]
    if ext in IMAGE_EXT:
        text, meta, w = _parse_image(path)
    elif ext == ".pdf":
        text, meta, w = _parse_pdf(path)
    elif ext == ".docx":
        text, meta, w = _parse_docx(path)
    elif ext == ".xlsx":
        text, meta, w = _parse_xlsx(path)
    elif ext == ".pptx":
        text, meta, w = _parse_pptx(path)
    elif ext in (".html", ".htm", ".xml"):
        text, meta, w = _parse_html(path)
    elif ext == ".csv" or ext == ".tsv":
        text, meta, w = decode_bytes(path.read_bytes()), {"delimiter": "," if ext == ".csv" else "\t"}, []
    elif ext == ".json":
        try:
            obj = json.loads(decode_bytes(path.read_bytes()))
            text = json.dumps(obj, ensure_ascii=False, indent=2)
            meta = {"jsonType": type(obj).__name__}
        except Exception as e:
            text, meta = decode_bytes(path.read_bytes()), {"jsonError": str(e)[:100]}
        w = []
    else:
        text, meta, w = decode_bytes(path.read_bytes()), {"ext": ext}, []
    warns += list(w or [])
    truncated = len(text) > max_chars
    if truncated:
        text = text[:max_chars] + "\n\n…（已截断，原文共 %d 字符）" % len(text)
        warns.append("解析文本超过 %d 字符，已截断注入；完整文件仍在本地。" % max_chars)
    return {"text": text, "meta": meta, "warnings": warns,
            "chars": len(text), "hasText": bool(text.strip()), "truncated": truncated}


# ─── 上传与管理 ──────────────────────────────────────────
def upload(name, data_b64, mime=""):
    """接收前端 base64（避免 multipart 解析依赖），落盘并登记。"""
    name = safe_name(name)
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise ValueError("不支持的文件类型 %s；允许：%s" % (ext or "(无扩展名)", ", ".join(sorted(ALLOWED_EXT))))
    try:
        raw = base64.b64decode(data_b64, validate=True)
    except Exception:
        raise ValueError("文件数据不是合法 base64")
    if not raw:
        raise ValueError("文件内容为空")
    if len(raw) > MAX_UPLOAD:
        raise ValueError("文件超过 %d MB 上限" % (MAX_UPLOAD // 1024 // 1024))
    fid = datetime.now().strftime("%Y%m%d") + "_" + uuid.uuid4().hex[:10]
    p = root() / (fid + "_" + name)
    p.write_bytes(raw)
    rec = {
        "id": fid, "name": name, "ext": ext, "size": len(raw), "mime": mime or "",
        "path": str(p), "sha256": hashlib.sha256(raw).hexdigest()[:24],
        "at": datetime.now().isoformat(timespec="seconds"),
        "stamp": int(time.time()),
    }
    with _LOCK:
        idx = _load_index()
        idx[fid] = rec
        _save_index(idx)
    rec.pop("path", None)
    return {"ok": True, "file": rec, "modelCalls": 0, "tokens": 0, "networkCalls": 0, "local": True}


def list_files():
    with _LOCK:
        idx = _load_index()
    out = []
    for fid, r in idx.items():
        p = Path(r.get("path", ""))
        if not p.is_file():
            continue
        o = {k: v for k, v in r.items() if k != "path"}
        o["id"] = fid
        out.append(o)
    out.sort(key=lambda x: x.get("stamp", 0), reverse=True)
    return {"files": out, "count": len(out), "root": str(root()), "maxUpload": MAX_UPLOAD,
            "allowedExt": sorted(ALLOWED_EXT), "local": True}


def get_path(fid):
    with _LOCK:
        r = _load_index().get(str(fid))
    if not r:
        raise ValueError("文件不存在或已被删除：%s" % fid)
    p = Path(r["path"])
    if not p.is_file():
        raise ValueError("文件实体已丢失：%s" % r.get("name"))
    return p, r


def read(fid, max_chars=MAX_TEXT):
    p, r = get_path(fid)
    d = parse(p, max_chars=max_chars)
    return {"ok": True, "id": str(fid), "name": r["name"], "ext": r["ext"], "size": r["size"],
            "text": d["text"], "meta": d["meta"], "warnings": d["warnings"],
            "chars": d["chars"], "hasText": d["hasText"], "truncated": d["truncated"],
            "modelCalls": 0, "tokens": 0, "networkCalls": 0, "local": True}


def info(fid):
    p, r = get_path(fid)
    d = parse(p, max_chars=200)
    return {"ok": True, "id": str(fid), "name": r["name"], "ext": r["ext"], "size": p.stat().st_size,
            "sha256": r.get("sha256"), "at": r.get("at"), "meta": d["meta"],
            "warnings": d["warnings"], "hasText": d["hasText"], "local": True}


def delete(fid):
    with _LOCK:
        idx = _load_index()
        r = idx.pop(str(fid), None)
        _save_index(idx)
    if not r:
        return {"ok": False, "error": "文件不存在"}
    try:
        p = Path(r["path"])
        if p.is_file():
            p.unlink()
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}
    return {"ok": True, "deleted": str(fid), "name": r.get("name"), "local": True}


def brief(fid, limit=4000):
    """给上下文注入用的短摘要：文件头 + 截断正文，不把整份文件塞进 prompt。"""
    try:
        p, r = get_path(fid)
        d = parse(p, max_chars=limit)
    except Exception as e:
        return {"id": fid, "text": "[文件不可读：%s]" % str(e)[:100], "warnings": []}
    head = "【本地文件 %s｜%s｜%d 字节】" % (r["name"], r["ext"], r["size"])
    return {"id": str(fid), "name": r["name"], "text": head + "\n" + d["text"][:limit],
            "warnings": d["warnings"], "chars": d["chars"]}
