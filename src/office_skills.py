# -*- coding: utf-8 -*-
"""Super-Agient 本地智能办公技能框架（office_skills）。

一个技能 = 一个本地函数 + 一份能力声明。所有技能：
  local = True / modelCalls = 0 / tokens = 0 / networkCalls = 0
即：不调用云端模型、不消耗 token、不发起网络请求，全部在本机完成。

对外只有两个入口：
  manifest()                 -> 技能清单 + 长文模板清单（供前端渲染）
  run(skill, params)         -> 统一执行，返回结构化结果或落盘文件路径

输出文件默认写入 ~/.ai-super-agent/AI.Super-Agent/v3/output/，
文件名带日期与序号，绝不覆盖旧文件。文件名做白名单清洗，禁止路径穿越。
"""

import csv
import html
import json
import os
import re
from datetime import datetime
from pathlib import Path

import docgen
import v3_core as V3

FRAMEWORK_TAG = "office-skills-3.3.0"

FORMATS = {
    "docx": {"ext": ".docx", "label": "Word 文档", "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    "html": {"ext": ".html", "label": "网页（自包含，可打印）", "mime": "text/html; charset=utf-8"},
    "pdf":  {"ext": ".pdf",  "label": "PDF（本地绘制）", "mime": "application/pdf"},
    "xlsx": {"ext": ".xlsx", "label": "Excel 表格", "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    "pptx": {"ext": ".pptx", "label": "PPT 演示", "mime": "application/vnd.openxmlformats-officedocument.presentationml.presentation"},
    "md":   {"ext": ".md",   "label": "Markdown", "mime": "text/markdown; charset=utf-8"},
    "txt":  {"ext": ".txt",  "label": "纯文本", "mime": "text/plain; charset=utf-8"},
    "csv":  {"ext": ".csv",  "label": "CSV 表格", "mime": "text/csv; charset=utf-8"},
}

SKILLS = [
    {"id": "text.gen", "label": "本地长文生成", "desc": "按模板确定性生成方案 / 大纲 / 总结 / 纪要等，不落盘",
     "icon": "file", "outputs": ["md"], "local": True},
    {"id": "text.write", "label": "写方案并导出", "desc": "一步完成：本地生成长文 → 导出 Word / HTML / PDF / Excel / PPT",
     "icon": "sparkle", "outputs": list(FORMATS.keys()), "local": True},
    {"id": "doc.write", "label": "生成 Word", "desc": "把结构化文档或对话内容写成 .docx（含标题层级与表格）",
     "icon": "file", "outputs": ["docx"], "local": True},
    {"id": "doc.md", "label": "Markdown 转 Word", "desc": "把任意 Markdown 文本转成排版后的 .docx",
     "icon": "file", "outputs": ["docx"], "local": True},
    {"id": "html.write", "label": "生成 HTML", "desc": "输出自包含单页网页，无外部资源，可直接打印为 PDF",
     "icon": "external", "outputs": ["html"], "local": True},
    {"id": "pdf.write", "label": "生成 PDF", "desc": "用本机字体逐页绘制中文 PDF，无需云端转换",
     "icon": "file", "outputs": ["pdf"], "local": True},
    {"id": "sheet.write", "label": "生成 Excel", "desc": "二维数据写成 .xlsx，表头加粗、冻结首行、列宽自适应",
     "icon": "database", "outputs": ["xlsx"], "local": True},
    {"id": "slides.write", "label": "生成 PPT", "desc": "按章节自动生成封面与内容页",
     "icon": "panel", "outputs": ["pptx"], "local": True},
    {"id": "md.write", "label": "保存 Markdown", "desc": "原文落盘为 .md",
     "icon": "save", "outputs": ["md"], "local": True},
    {"id": "txt.write", "label": "保存纯文本", "desc": "去格式后落盘为 .txt",
     "icon": "save", "outputs": ["txt"], "local": True},
    {"id": "csv.write", "label": "生成 CSV", "desc": "把文档里的第一张表格导出为 UTF-8 BOM 的 .csv",
     "icon": "database", "outputs": ["csv"], "local": True},
]

SKILL_MAP = {s["id"]: s for s in SKILLS}


def manifest():
    return {
        "framework": FRAMEWORK_TAG,
        "engine": docgen.ENGINE_TAG,
        "skills": SKILLS,
        "templates": docgen.list_templates(),
        "formats": [{"id": k, **v} for k, v in FORMATS.items()],
        "fields": [{"key": k, "label": l, "default": d} for k, l, d in docgen.FIELDS],
        "local": True, "modelCalls": 0, "tokens": 0, "networkCalls": 0,
        "outputDir": str(output_dir()),
    }


# ─── 输出目录与命名 ──────────────────────────────────────
def output_dir(params=None):
    custom = (params or {}).get("outputDir")
    if custom:
        try:
            p = Path(custom).expanduser().resolve()
            p.mkdir(parents=True, exist_ok=True)
            return p
        except Exception:
            pass
    p = V3.v3_root() / "output"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _safe_name(s, fallback="文档"):
    s = re.sub(r"[\\/:*?\"<>|\r\n\t]", "_", str(s or ""))
    s = re.sub(r"\s+", " ", s).strip(" ._")
    return (s[:48] or fallback)


def _no_overwrite(p):
    """同名文件绝不覆盖，自动追加 _2 / _3 …"""
    if not p.exists():
        return p
    stem, suffix, parent = p.stem, (p.suffix or ""), p.parent
    n = 2
    while True:
        q = parent / ("%s_%d%s" % (stem, n, suffix))
        if not q.exists():
            return q
        n += 1


_URL_SCHEME = re.compile(r"^(?:https?|ftps?|file|sftp|ws|wss|data|javascript)://", re.I)


def is_remote_path(raw):
    """只拦真正的网络协议与 UNC；不能把 D:// 这类盘符路径误判成 URL。"""
    s = str(raw or "").strip().strip('"').strip("'")
    return bool(_URL_SCHEME.match(s)) or s.startswith("\\\\")


def save_path(save_to, fmt, suggested="文档", params=None):
    """把用户指定的保存位置解析成本机绝对路径。

    支持：完整文件路径 / 目录 / 相对路径（相对默认输出目录）。
    拒绝：http(s)/ftp/file/… 等 URL、UNC 网络路径（避免任何出域写入）。
    """
    raw = str(save_to or "").strip().strip('"').strip("'")
    if not raw:
        raise ValueError("保存路径为空")
    if is_remote_path(raw):
        raise ValueError("只支持本机磁盘路径，不接受 URL 或 UNC 网络路径：%s" % raw[:80])
    # Git Bash / 某些复制粘贴会把 D:\ 写成 D://，规范化为盘符路径而不是误判为 URL
    raw = re.sub(r"^([A-Za-z]):/{2,}", r"\1:\\", raw)
    ext = FORMATS.get(fmt, {}).get("ext", ".txt")
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = output_dir(params) / p
    looks_dir = raw.endswith(("/", "\\")) or (p.exists() and p.is_dir())
    if looks_dir:
        p = p / (_safe_name(suggested) + ext)
    elif not p.suffix:
        p = Path(str(p) + ext)
    p = p.resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    return _no_overwrite(p)


def _target(name, fmt, params=None):
    params = params or {}
    ext = FORMATS.get(fmt, {}).get("ext", ".txt")
    if params.get("saveTo"):
        return save_path(params["saveTo"], fmt, name or "文档", params)
    d = output_dir(params)
    stamp = datetime.now().strftime("%Y%m%d")
    base = "%s_%s_%s" % (_safe_name(name), "v33", stamp)
    p = d / (base + ext)
    n = 2
    while p.exists():          # 绝不覆盖旧文件
        p = d / ("%s_%d%s" % (base, n, ext))
        n += 1
    return p


# ─── 文档解析 ────────────────────────────────────────────
def _resolve_doc(params):
    """三种输入：doc 对象 / markdown 文本 / 模板 ID。"""
    doc = params.get("doc")
    if isinstance(doc, dict) and doc.get("sections"):
        if not doc.get("markdown"):
            doc["markdown"] = docgen.to_markdown(doc)
        return doc
    md = params.get("markdown") or params.get("text") or params.get("content")
    if md:
        return docgen.markdown_to_doc(md, params.get("title") or "")
    tpl = params.get("template") or "training_plan"
    args = docgen.parse_args(params.get("prompt") or params.get("topic") or "", params.get("args") or {})
    return docgen.generate(tpl, args)


def _doc_rows(doc):
    """取文档里的第一张表格；无表格时把章节标题做成清单。"""
    for s in doc.get("sections", []):
        for b in s.get("blocks", []):
            if b.get("type") == "table" and b.get("rows"):
                return b["rows"], doc.get("title", "表格")
    rows = [["序号", "章节"]]
    for i, s in enumerate(doc.get("sections", []), 1):
        rows.append([i, s.get("heading", "")])
    return rows, doc.get("title", "表格")


# ─── 各格式渲染 ──────────────────────────────────────────
def _set_cn(run, font="宋体", size=12, bold=False):
    from docx.shared import Pt
    run.font.name = font
    run.font.size = Pt(size)
    run.bold = bold
    try:
        from docx.oxml.ns import qn
        run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), font)
    except Exception:
        pass


def render_docx(doc, path):
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt

    d = Document()
    st = d.styles["Normal"]
    st.font.name = "宋体"
    st.font.size = Pt(12)
    try:
        from docx.oxml.ns import qn
        st.element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    except Exception:
        pass

    t = d.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _set_cn(t.add_run(doc.get("title") or "未命名文档"), "黑体", 18, True)
    meta_text = docgen.meta_line(doc.get("meta") or {}, ("org", "dept", "date"))
    if meta_text:
        p = d.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _set_cn(p.add_run(meta_text), "宋体", 10.5)

    for s in doc.get("sections", []):
        hp = d.add_paragraph()
        _set_cn(hp.add_run(s.get("heading") or ""), "黑体", 14, True)
        hp.paragraph_format.space_before = Pt(10)
        hp.paragraph_format.space_after = Pt(4)
        for b in s.get("blocks", []):
            if b["type"] == "p":
                p = d.add_paragraph()
                p.paragraph_format.first_line_indent = Pt(24)
                p.paragraph_format.line_spacing = 1.5
                for j, line in enumerate(str(b["text"]).split("\n")):
                    if j:
                        p.add_run("\n")
                    _set_cn(p.add_run(line), "宋体", 12)
            elif b["type"] == "bullets":
                for item in b["items"]:
                    p = d.add_paragraph(style="List Bullet")
                    _set_cn(p.add_run(str(item)), "宋体", 12)
            elif b["type"] == "table":
                rows = b["rows"]
                if not rows:
                    continue
                cols = max(len(r) for r in rows)
                t = d.add_table(rows=len(rows), cols=cols)
                t.style = "Table Grid"
                for i, row in enumerate(rows):
                    for j in range(cols):
                        cell = t.cell(i, j)
                        cell.text = ""
                        _set_cn(cell.paragraphs[0].add_run(str(row[j] if j < len(row) else "")),
                                "黑体" if i == 0 else "宋体", 10.5, i == 0)
                d.add_paragraph()
    d.save(str(path))
    return path


_CSS = """
:root{--ink:#23201d;--soft:#6b635a;--line:#e6ded2;--accent:#b4663c;--paper:#fdfbf7}
*{box-sizing:border-box}
body{margin:0;background:#f2eee7;color:var(--ink);font-family:"Microsoft YaHei","PingFang SC","Source Han Sans SC",sans-serif;line-height:1.85}
.page{max-width:820px;margin:32px auto;padding:56px 64px;background:var(--paper);box-shadow:0 2px 24px rgba(0,0,0,.08);border-radius:6px}
.brand{display:flex;align-items:center;gap:10px;color:var(--soft);font-size:13px;letter-spacing:.06em;border-bottom:1px solid var(--line);padding-bottom:14px;margin-bottom:34px}
h1{font-size:28px;line-height:1.45;margin:0 0 12px;text-align:center;letter-spacing:.02em}
.meta{text-align:center;color:var(--soft);font-size:13px;margin-bottom:38px}
h2{font-size:19px;margin:34px 0 14px;padding-left:12px;border-left:4px solid var(--accent);line-height:1.5}
p{margin:0 0 12px;text-indent:2em;text-align:justify}
ul{margin:0 0 16px;padding-left:26px}li{margin:5px 0}
table{width:100%;border-collapse:collapse;margin:16px 0 22px;font-size:14px}
th,td{border:1px solid var(--line);padding:9px 11px;text-align:left;vertical-align:top}
th{background:#f5efe5;font-weight:600}
.foot{margin-top:48px;padding-top:14px;border-top:1px solid var(--line);color:var(--soft);font-size:12px;display:flex;justify-content:space-between}
.tools{max-width:820px;margin:20px auto 0;display:flex;gap:10px;justify-content:flex-end}
button{font:inherit;padding:8px 16px;border:1px solid var(--line);background:#fff;border-radius:6px;cursor:pointer;color:var(--ink)}
button:hover{border-color:var(--accent);color:var(--accent)}
@media print{body{background:#fff}.page{box-shadow:none;margin:0;padding:0;max-width:none}.tools{display:none}@page{margin:20mm 18mm}}
"""

_ROBOT_SVG = (
    '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#b4663c" '
    'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">'
    '<rect x="4" y="8" width="16" height="12" rx="3"/><path d="M12 4v4M9 4h6"/>'
    '<circle cx="9" cy="14" r="1.2" fill="#b4663c" stroke="none"/>'
    '<circle cx="15" cy="14" r="1.2" fill="#b4663c" stroke="none"/>'
    '<path d="M9.5 17.2h5M1.5 12v3M22.5 12v3"/></svg>'
)


def render_html(doc, path):
    e = html.escape
    parts = ['<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width,initial-scale=1">',
             '<title>%s</title><style>%s</style></head><body>' % (e(doc.get("title", "文档")), _CSS),
             '<div class="tools"><button onclick="window.print()">打印 / 另存为 PDF</button>',
             '<button onclick="window.close()">关闭</button></div>',
             '<article class="page">',
             '<div class="brand">%s <span>Super-Agient · 本地生成 · 零 token · 零联网</span></div>' % _ROBOT_SVG,
             '<h1>%s</h1>' % e(doc.get("title", "")),
             '<div class="meta">%s</div>' % e(docgen.meta_line(doc.get("meta") or {}, ("org", "dept", "date")))]
    for s in doc.get("sections", []):
        parts.append('<h2>%s</h2>' % e(s.get("heading", "")))
        for b in s.get("blocks", []):
            if b["type"] == "p":
                parts.append('<p>%s</p>' % e(b["text"]).replace("\n", "<br>"))
            elif b["type"] == "bullets":
                parts.append("<ul>" + "".join("<li>%s</li>" % e(x) for x in b["items"]) + "</ul>")
            elif b["type"] == "table":
                rows = b["rows"]
                parts.append("<table><thead><tr>" + "".join("<th>%s</th>" % e(c) for c in rows[0]) + "</tr></thead><tbody>")
                for r in rows[1:]:
                    parts.append("<tr>" + "".join("<td>%s</td>" % e(c) for c in r) + "</tr>")
                parts.append("</tbody></table>")
    parts.append('<div class="foot"><span>Super-Agient · 本机生成</span><span>本文件完全在本机生成，未经云端处理</span></div>')
    parts.append('</article></body></html>')
    path.write_text("\n".join(parts), encoding="utf-8")
    return path


_CN_FONTS = [
    Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "msyh.ttc",
    Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "msyhbd.ttc",
    Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "simhei.ttf",
    Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "simsun.ttc",
    Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "simkai.ttf",
    Path("/System/Library/Fonts/PingFang.ttc"),
    Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
]


def _pick_font():
    for p in _CN_FONTS:
        if p.exists():
            return p
    return None


def render_pdf(doc, path):
    """用 PIL + 本机中文字体逐页绘制；不依赖云端转换、不依赖 Word。"""
    from PIL import Image, ImageDraw, ImageFont
    fp = _pick_font()
    if not fp:
        raise RuntimeError("未找到本机中文字体，无法生成中文 PDF；请改用 HTML 或 Word 格式")
    W, H = 1240, 1754          # A4 @150dpi
    L, R, TOP, BOT = 110, 110, 120, 110
    f_title = ImageFont.truetype(str(fp), 40)
    f_h = ImageFont.truetype(str(fp), 28)
    f_body = ImageFont.truetype(str(fp), 22)
    f_small = ImageFont.truetype(str(fp), 18)

    def wrap(text, font, width):
        out, line = [], ""
        for ch in str(text):
            if ch == "\n":
                out.append(line)
                line = ""
                continue
            if font.getlength(line + ch) > width:
                out.append(line)
                line = ch
            else:
                line += ch
        if line:
            out.append(line)
        return out or [""]

    pages, img, dr, y = [], None, None, 0

    def newpage():
        nonlocal img, dr, y
        img = Image.new("RGB", (W, H), "white")
        dr = ImageDraw.Draw(img)
        y = TOP
        pages.append(img)

    def need(h):
        nonlocal y
        if y + h > H - BOT:
            newpage()

    def put(lines, font, fill=(35, 32, 29), gap=8, indent=0):
        nonlocal y
        for ln in lines:
            need(38)
            dr.text((L + indent, y), ln, font=font, fill=fill)
            y += font.size + gap

    newpage()
    tl = wrap(doc.get("title", "文档"), f_title, W - L - R)
    for ln in tl:
        dr.text((L, y), ln, font=f_title, fill=(35, 32, 29))
        y += 54
    y += 16
    meta_text = docgen.meta_line(doc.get("meta") or {}, ("org", "dept", "date"))
    if meta_text:
        put(wrap(meta_text, f_small, W - L - R), f_small, (110, 99, 90), 6)
    y += 22
    dr.line((L, y, W - R, y), fill=(230, 222, 210), width=2)
    y += 26

    for s in doc.get("sections", []):
        need(120)
        y += 10
        dr.rectangle((L, y + 2, L + 5, y + 30), fill=(180, 102, 60))
        put(wrap(s.get("heading", ""), f_h, W - L - R - 20), f_h, (35, 32, 29), 10, 16)
        y += 8
        for b in s.get("blocks", []):
            if b["type"] == "p":
                put(wrap(b["text"], f_body, W - L - R), f_body, gap=10)
                y += 6
            elif b["type"] == "bullets":
                for item in b["items"]:
                    lines = wrap("• " + str(item), f_body, W - L - R - 26)
                    put(lines, f_body, gap=8, indent=18)
                y += 6
            elif b["type"] == "table":
                rows = b["rows"]
                if not rows:
                    continue
                cols = max(len(r) for r in rows)
                cw = (W - L - R) // max(cols, 1)
                for ri, row in enumerate(rows):
                    cell_lines = [wrap(str(row[j] if j < len(row) else ""), f_small, cw - 16)
                                  for j in range(cols)]
                    rh = max(len(x) for x in cell_lines) * (f_small.size + 5) + 14
                    need(rh + 6)
                    x0, y0 = L, y
                    for j in range(cols):
                        dr.rectangle((x0, y0, x0 + cw, y0 + rh), outline=(215, 206, 194), width=1)
                        if ri == 0:
                            dr.rectangle((x0 + 1, y0 + 1, x0 + cw - 1, y0 + rh - 1), fill=(245, 239, 229))
                        for k, ln in enumerate(cell_lines[j]):
                            dr.text((x0 + 8, y0 + 7 + k * (f_small.size + 5)), ln,
                                    font=f_small, fill=(35, 32, 29))
                        x0 += cw
                    y += rh
                y += 14
    for i, _ in enumerate(pages):
        dr = ImageDraw.Draw(pages[i])
        dr.text((W - R - 90, H - 60), "%d / %d" % (i + 1, len(pages)), font=f_small, fill=(150, 140, 130))
        dr.text((L, H - 60), "Super-Agient · 本地生成", font=f_small, fill=(150, 140, 130))
    pages[0].save(str(path), "PDF", resolution=150.0, save_all=True,
                  append_images=pages[1:] if len(pages) > 1 else [])
    return path, len(pages)


def render_xlsx(rows, path, title="表格"):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    r = [list(x) for x in (rows or [])] or [["（空）"]]
    cols = max(len(x) for x in r)
    for i, row in enumerate(r, 1):
        for j in range(cols):
            ws.cell(row=i, column=j + 1, value=str(row[j] if j < len(row) else ""))
            c = ws.cell(row=i, column=j + 1)
            c.alignment = Alignment(vertical="center", wrap_text=True)
            if i == 1:
                c.font = Font(bold=True, color="FFFFFF")
                c.fill = PatternFill("solid", fgColor="B4663C")
    for j in range(cols):
        width = min(42, max(12, max(len(str(x[j] if j < len(x) else "")) for x in r[:20]) + 4))
        ws.column_dimensions[get_column_letter(j + 1)].width = width
    ws.freeze_panes = "A2"
    wb.save(str(path))
    return path


def render_pptx(doc, path):
    from pptx import Presentation
    from pptx.util import Inches, Pt

    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    cover = prs.slides.add_slide(prs.slide_layouts[6])
    tb = cover.shapes.add_textbox(Inches(1), Inches(2.5), Inches(11.3), Inches(1.4))
    p = tb.text_frame.paragraphs[0]
    p.text = doc.get("title", "演示文稿")
    p.font.size, p.font.bold = Pt(38), True
    sub = cover.shapes.add_textbox(Inches(1), Inches(4.1), Inches(11.3), Inches(0.7))
    sub.text_frame.paragraphs[0].text = "Super-Agient · 本地生成 · 零 token · 零联网"
    sub.text_frame.paragraphs[0].font.size = Pt(16)

    for s in doc.get("sections", [])[:14]:
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        box = slide.shapes.add_textbox(Inches(0.9), Inches(0.6), Inches(11.6), Inches(0.9))
        box.text_frame.paragraphs[0].text = s.get("heading", "")
        box.text_frame.paragraphs[0].font.size = Pt(28)
        box.text_frame.paragraphs[0].font.bold = True
        body = slide.shapes.add_textbox(Inches(1.0), Inches(1.7), Inches(11.4), Inches(5.2))
        tf = body.text_frame
        tf.word_wrap = True
        lines = []
        for b in s.get("blocks", []):
            if b["type"] == "p":
                lines.append(str(b["text"])[:160])
            elif b["type"] == "bullets":
                lines += ["• " + str(x)[:120] for x in b["items"][:5]]
            elif b["type"] == "table":
                lines += [" | ".join(str(c) for c in row)[:120] for row in b["rows"][:5]]
        for i, ln in enumerate(lines[:9]):
            para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            para.text = ln
            para.font.size = Pt(18)
            para.space_after = Pt(10)
    prs.save(str(path))
    return path, len(prs.slides._sldIdLst)


def render_csv(rows, path):
    with open(str(path), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        for r in rows or []:
            w.writerow([str(c) for c in r])
    return path


# ─── 统一导出 ────────────────────────────────────────────
def export(doc, fmt, params=None):
    fmt = str(fmt or "docx").lower()
    if fmt not in FORMATS:
        raise ValueError("不支持的格式: %s（可用：%s）" % (fmt, ", ".join(FORMATS)))
    params = params or {}
    p = _target(params.get("filename") or doc.get("title") or "文档", fmt, params)
    extra = {}
    if fmt == "docx":
        render_docx(doc, p)
    elif fmt == "html":
        render_html(doc, p)
    elif fmt == "pdf":
        _, pages = render_pdf(doc, p)
        extra["pages"] = pages
    elif fmt == "xlsx":
        rows, _ = _doc_rows(doc)
        render_xlsx(params.get("rows") or rows, p, doc.get("title", ""))
    elif fmt == "pptx":
        _, n = render_pptx(doc, p)
        extra["slides"] = n
    elif fmt == "csv":
        rows, _ = _doc_rows(doc)
        render_csv(params.get("rows") or rows, p)
    elif fmt == "md":
        p.write_text(doc.get("markdown") or docgen.to_markdown(doc), encoding="utf-8")
    elif fmt == "txt":
        md = doc.get("markdown") or docgen.to_markdown(doc)
        txt = re.sub(r"^#{1,6}\s*", "", md, flags=re.M)
        txt = re.sub(r"\*\*|`|^>\s?", "", txt, flags=re.M)
        p.write_text(txt, encoding="utf-8")
    default_dir = output_dir().resolve()
    in_default = p.parent.resolve() == default_dir
    return {
        "ok": True, "path": str(p), "name": p.name, "format": fmt,
        "size": p.stat().st_size, "chars": doc.get("chars") or len(doc.get("markdown") or ""),
        "url": ("/api/v3/output/" + p.name) if in_default else None,
        "dir": str(p.parent), "savedTo": str(p), "inDefaultDir": in_default,
        "modelCalls": 0, "tokens": 0, "networkCalls": 0, "local": True,
        **extra,
    }


# ─── 技能执行入口 ────────────────────────────────────────
def run(skill, params=None):
    params = dict(params or {})
    if skill not in SKILL_MAP:
        raise ValueError("未知技能: %s" % skill)

    if skill == "text.gen":
        tpl = params.get("template") or "training_plan"
        args = docgen.parse_args(params.get("prompt") or params.get("topic") or "",
                                 params.get("args") or {})
        doc = docgen.generate(tpl, args)
        return {"ok": True, "skill": skill, "doc": doc, "path": None,
                "modelCalls": 0, "tokens": 0, "networkCalls": 0, "local": True}

    doc = _resolve_doc(params)
    fmt_map = {
        "doc.write": "docx", "doc.md": "docx", "html.write": "html",
        "pdf.write": "pdf", "sheet.write": "xlsx", "slides.write": "pptx",
        "md.write": "md", "txt.write": "txt", "csv.write": "csv",
        "text.write": params.get("format") or "docx",
    }
    fmt = fmt_map[skill]
    if skill == "doc.md" and params.get("markdown"):
        doc = docgen.markdown_to_doc(params["markdown"], params.get("title") or "")
    res = export(doc, fmt, params)
    res["skill"] = skill
    res["title"] = doc.get("title", "")
    res["markdown"] = doc.get("markdown", "")
    res["template"] = doc.get("template", "")
    return res
