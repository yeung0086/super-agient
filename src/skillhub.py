# -*- coding: utf-8 -*-
"""Super-Agient 内置技能总线（skillhub）。

把「本地长文 / 办公导出」与「文件解析 / 格式转换 / 指定位置保存」合并成一份
**直接封装在应用里**的技能清单，前端、模型任务指令、@ 命令都通过同一个入口调用。

全部技能：modelCalls = 0 / tokens = 0 / networkCalls = 0，只在本机执行。
"""

import json
import re
from pathlib import Path

import docgen
import filehub
import office_skills as OS
import v3_core as V3

HUB_TAG = "skillhub-3.3.0"

BUILTIN_SKILLS = [
    {"id": "file.read", "label": "读取本地文件", "desc": "把上传的 PDF/Word/Excel/PPT/网页/文本解析成纯文本，不落盘",
     "icon": "file", "outputs": ["md"], "local": True, "group": "文件"},
    {"id": "file.info", "label": "文件信息", "desc": "页数 / 工作表 / 幻灯片 / 图片尺寸 / 是否有文本层",
     "icon": "panel", "outputs": [], "local": True, "group": "文件"},
    {"id": "pdf.to_text", "label": "PDF 转文本", "desc": "提取 PDF 文本层，输出 UTF-8 .txt（扫描件会明确提示，不伪造）",
     "icon": "file", "outputs": ["txt"], "local": True, "group": "PDF"},
    {"id": "pdf.to_md", "label": "PDF 转 Markdown", "desc": "按页转成结构化 .md",
     "icon": "save", "outputs": ["md"], "local": True, "group": "PDF"},
    {"id": "pdf.to_docx", "label": "PDF 转 Word", "desc": "PDF 文本层 → 排版后的 .docx",
     "icon": "doc", "outputs": ["docx"], "local": True, "group": "PDF"},
    {"id": "pdf.to_html", "label": "PDF 转网页", "desc": "PDF 文本层 → 自包含单页 .html",
     "icon": "external", "outputs": ["html"], "local": True, "group": "PDF"},
    {"id": "doc.convert", "label": "文件格式转换", "desc": "任意已上传文件 → Word / HTML / PDF / Excel / PPT / MD / TXT / CSV",
     "icon": "refresh", "outputs": list(OS.FORMATS.keys()), "local": True, "group": "转换"},
    {"id": "doc.merge", "label": "多文件合并", "desc": "把多个上传文件的正文合并成一份文档并导出",
     "icon": "layers", "outputs": list(OS.FORMATS.keys()), "local": True, "group": "转换"},
    {"id": "sheet.from_text", "label": "文本转 Excel", "desc": "把按行/按列分隔的文本解析成 .xlsx 表格",
     "icon": "database", "outputs": ["xlsx"], "local": True, "group": "转换"},
    {"id": "file.save", "label": "保存到指定位置", "desc": "把任意文本直接写入用户指定的本机绝对路径/目录",
     "icon": "save", "outputs": ["txt", "md", "csv", "json", "html"], "local": True, "group": "保存"},
    {"id": "batch.convert", "label": "批量转换", "desc": "一次把多个文件转成同一格式，逐个返回落盘结果",
     "icon": "layers", "outputs": list(OS.FORMATS.keys()), "local": True, "group": "批量"},
]

BUILTIN_MAP = {s["id"]: s for s in BUILTIN_SKILLS}
ALL_SKILLS = list(OS.SKILLS) + BUILTIN_SKILLS
ALL_MAP = {s["id"]: s for s in ALL_SKILLS}


def manifest():
    m = OS.manifest()
    m["framework"] = HUB_TAG
    m["officeFramework"] = OS.FRAMEWORK_TAG
    m["skills"] = ALL_SKILLS
    m["builtinSkills"] = BUILTIN_SKILLS
    m["filehub"] = {"tag": filehub.HUB_TAG, "maxUpload": filehub.MAX_UPLOAD,
                    "allowedExt": sorted(filehub.ALLOWED_EXT), "root": str(filehub.root())}
    m["saveOptions"] = {
        "outputDir": "指定输出目录（自动创建）",
        "saveTo": "指定完整文件路径或目录；同名自动加序号，绝不覆盖",
        "reject": ["URL", "UNC 网络路径"],
    }
    m["taskProtocol"] = {
        "block": "```agent-task\n{...}\n```",
        "inline": "@task {...}",
        "schema": {"skill": "技能 id（必填，白名单校验）", "params": "参数对象", "note": "说明", "id": "可选"},
    }
    return m


def _ok(**kw):
    return {"ok": True, "modelCalls": 0, "tokens": 0, "networkCalls": 0, "local": True, **kw}


def _clean_title(name):
    """源文件常已带 _v33_20261115 版本戳，转换时剥掉，避免出现双重日期。"""
    stem = Path(str(name or "文档")).stem
    stem = re.sub(r"_v\d+(?:\.\d+)*_\d{8}(?:_\d+)?$", "", stem)
    return stem or "文档"


# ─── 文件来源解析 ────────────────────────────────────────
def _source(params):
    """从 fileId（上传）或 path（本机绝对路径）取文本。返回 (名称, 文本, 警告, 元信息)。"""
    fid = params.get("fileId") or params.get("id")
    if fid:
        p, rec = filehub.get_path(fid)
        name = rec["name"]
    else:
        raw = str(params.get("path") or "").strip().strip('"')
        if not raw:
            raise ValueError("缺少 fileId 或 path：请先上传文件，或给出本机绝对路径")
        if OS.is_remote_path(raw):
            raise ValueError("只支持本机磁盘路径，不接受 URL / UNC 网络路径")
        p = Path(raw).expanduser()
        if not p.is_file():
            raise ValueError("文件不存在：%s" % raw)
        if p.stat().st_size > filehub.MAX_UPLOAD:
            raise ValueError("文件超过 %d MB 上限" % (filehub.MAX_UPLOAD // 1024 // 1024))
        name = p.name
    d = filehub.parse(p, max_chars=int(params.get("maxChars") or filehub.MAX_TEXT))
    if not d["hasText"]:
        hint = "；".join(d["warnings"]) or "该文件没有可提取文本"
        raise ValueError("无法提取文本：%s" % hint)
    return name, d["text"], d["warnings"], d["meta"]


def _to_markdown(text, title, ext=""):
    """把解析出的纯文本整理成 docgen 能吃的 Markdown。"""
    t = str(text or "").strip()
    if not t:
        return "# " + title + "\n\n（无可提取文本）\n"
    # PDF 分页标记 -> 二级标题
    t = re.sub(r"\[第\s*(\d+)\s*页\]", r"## 第 \1 页", t)
    has_md = bool(re.search(r"^\s*#{1,6}\s|^\s*[-*]\s|^\s*\|", t, flags=re.M))
    if has_md:
        if not re.match(r"^\s*#\s", t):
            t = "# " + title + "\n\n" + t
        return t
    paras = [x.strip() for x in re.split(r"\n\s*\n", t) if x.strip()]
    if not paras:
        paras = [t]
    return "# " + title + "\n\n" + "\n\n".join(paras[:400]) + "\n"


def _export_doc(text, title, fmt, params, warnings=None, extra=None):
    md = _to_markdown(text, title)
    doc = docgen.markdown_to_doc(md, title)
    pp = dict(params or {})
    pp.setdefault("filename", title)
    res = OS.export(doc, fmt, pp)
    res.update({"skill": pp.get("_skill") or "doc.convert", "title": title,
                "markdown": md, "warnings": warnings or [], "sourceChars": len(text)})
    if extra:
        res.update(extra)
    return res


# ─── 内置技能实现 ────────────────────────────────────────
def _s_file_read(params):
    name, text, warns, meta = _source(params)
    return _ok(skill="file.read", name=name, text=text, meta=meta,
               warnings=warns, chars=len(text), path=None)


def _s_file_info(params):
    fid = params.get("fileId") or params.get("id")
    if fid:
        return filehub.info(fid)
    p = Path(str(params.get("path") or "")).expanduser()
    if not p.is_file():
        raise ValueError("文件不存在：%s" % p)
    d = filehub.parse(p, max_chars=200)
    return _ok(skill="file.info", name=p.name, size=p.stat().st_size, ext=p.suffix.lower(),
               meta=d["meta"], warnings=d["warnings"], hasText=d["hasText"], path=str(p))


def _s_pdf(params, fmt):
    name, text, warns, meta = _source(params)
    ext = Path(name).suffix.lower()
    if ext != ".pdf":
        warns = list(warns) + ["来源不是 PDF（%s），已按普通文件转换" % ext]
    title = params.get("title") or (_clean_title(name) + "（PDF 提取）")
    pp = dict(params or {})
    pp["_skill"] = {"txt": "pdf.to_text", "md": "pdf.to_md", "docx": "pdf.to_docx",
                    "html": "pdf.to_html"}.get(fmt, "pdf.to_text")
    res = _export_doc(text, title, fmt, pp, warns, {"sourceFile": name, "sourceMeta": meta})
    res["skill"] = pp["_skill"]
    return res


def _s_convert(params):
    name, text, warns, meta = _source(params)
    fmt = str(params.get("format") or "docx").lower()
    title = params.get("title") or _clean_title(name)
    pp = dict(params or {})
    pp["_skill"] = "doc.convert"
    res = _export_doc(text, title, fmt, pp, warns, {"sourceFile": name, "sourceMeta": meta})
    res["skill"] = "doc.convert"
    return res


def _s_merge(params):
    ids = params.get("fileIds") or []
    if not isinstance(ids, list) or len(ids) < 2:
        raise ValueError("doc.merge 需要 fileIds 数组且至少 2 个文件")
    chunks, warns, names = [], [], []
    for fid in ids[:12]:
        name, text, w, _ = _source({"fileId": fid})
        names.append(name)
        chunks.append("## " + Path(name).stem + "\n\n" + text[:12000])
        warns += w
    title = params.get("title") or "多文件合并文档"
    md = "# " + title + "\n\n" + "\n\n".join(chunks) + "\n"
    doc = docgen.markdown_to_doc(md, title)
    pp = dict(params or {})
    pp.setdefault("filename", title)
    res = OS.export(doc, str(params.get("format") or "docx").lower(), pp)
    res.update({"skill": "doc.merge", "title": title, "markdown": md,
                "warnings": warns, "sourceFiles": names})
    return res


def _s_sheet(params):
    text = params.get("text") or ""
    if not text and (params.get("fileId") or params.get("path")):
        _, text, warns, _ = _source(params)
    else:
        warns = []
    rows = []
    for line in str(text).splitlines()[:600]:
        line = line.strip()
        if not line or set(line) <= set("|-: "):
            continue
        if "|" in line:
            cells = [c.strip() for c in line.strip("|").split("|")]
        elif "\t" in line:
            cells = [c.strip() for c in line.split("\t")]
        else:
            cells = [line]
        rows.append(cells)
    if not rows:
        raise ValueError("没有可转成表格的文本行")
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    title = params.get("title") or "文本转表格"
    pp = dict(params or {})
    pp.setdefault("filename", title)
    p = OS._target(title, "xlsx", pp)
    OS.render_xlsx(rows, p, title)
    d = OS.output_dir().resolve()
    in_def = p.parent.resolve() == d
    return _ok(skill="sheet.from_text", path=str(p), name=p.name, format="xlsx",
               size=p.stat().st_size, rows=len(rows), cols=width, title=title,
               warnings=warns, dir=str(p.parent), savedTo=str(p), inDefaultDir=in_def,
               url=("/api/v3/output/" + p.name) if in_def else None)


def _s_save(params):
    text = params.get("text") or params.get("markdown") or params.get("content")
    if text is None:
        raise ValueError("file.save 需要 text / markdown / content")
    raw = params.get("saveTo") or params.get("filename")
    if not raw:
        raise ValueError("file.save 需要 saveTo（完整路径）或 filename")
    fmt = str(params.get("format") or "txt").lower()
    p = OS.save_path(raw, fmt, params.get("title") or "文本", params)
    ext = p.suffix.lower()
    if ext == ".json":
        try:
            body = json.dumps(text if not isinstance(text, str) else json.loads(text),
                              ensure_ascii=False, indent=2)
        except Exception:
            body = str(text)
    else:
        body = str(text)
    p.write_text(body, encoding="utf-8-sig" if ext == ".csv" else "utf-8")
    d = OS.output_dir().resolve()
    in_def = p.parent.resolve() == d
    return _ok(skill="file.save", path=str(p), name=p.name, format=ext.lstrip(".") or fmt,
               size=p.stat().st_size, chars=len(body), dir=str(p.parent), savedTo=str(p),
               inDefaultDir=in_def, url=("/api/v3/output/" + p.name) if in_def else None)


def _s_batch(params):
    ids = params.get("fileIds") or []
    if not isinstance(ids, list) or not ids:
        raise ValueError("batch.convert 需要 fileIds 数组")
    fmt = str(params.get("format") or "docx").lower()
    results = []
    for fid in ids[:20]:
        one = dict(params or {})
        one["fileId"] = fid
        one.pop("fileIds", None)
        try:
            r = _s_convert(one)
            results.append({"fileId": fid, "ok": True, "name": r.get("name"),
                            "path": r.get("path"), "size": r.get("size")})
        except Exception as e:
            results.append({"fileId": fid, "ok": False, "error": str(e)[:180]})
    return _ok(skill="batch.convert", format=fmt, results=results,
               total=len(results), succeeded=sum(1 for x in results if x["ok"]),
               path=None)


_DISPATCH = {
    "file.read": _s_file_read,
    "file.info": _s_file_info,
    "pdf.to_text": lambda p: _s_pdf(p, "txt"),
    "pdf.to_md": lambda p: _s_pdf(p, "md"),
    "pdf.to_docx": lambda p: _s_pdf(p, "docx"),
    "pdf.to_html": lambda p: _s_pdf(p, "html"),
    "doc.convert": _s_convert,
    "doc.merge": _s_merge,
    "sheet.from_text": _s_sheet,
    "file.save": _s_save,
    "batch.convert": _s_batch,
}


def run(skill, params=None):
    params = dict(params or {})
    skill = str(skill or "").strip()
    if skill in OS.SKILL_MAP:
        return OS.run(skill, params)
    if skill in _DISPATCH:
        res = _DISPATCH[skill](params)
        V3.audit_append("local.skill", "内置技能 %s" % skill,
                        {"chars": res.get("chars") or res.get("sourceChars") or 0,
                         "fmt": res.get("format") or ""})
        return res
    raise ValueError("未知技能：%s（可用：%s）" % (skill, ", ".join(sorted(ALL_MAP))[:300]))


def skill_ids():
    return sorted(ALL_MAP.keys())
