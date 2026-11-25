# -*- coding: utf-8 -*-
"""Super-Agient v3.3.0 内置 Agent 框架内核（本地 / 零 token / 零联网）。

把「常用 Agent 框架」做成**可执行**的本地实现并直接封装进应用，而不是只给模型写提示词：

  ToolRegistry  — 22 个内置技能自动映射为带参数模式的工具清单
  Planner       — 确定性目标分解（规则驱动，不调模型）
  Executor      — 统一执行 + 轨迹记录（thought / action / observation）
  Verifier      — 结果校验（文件是否落盘、字数、必需字段）
  Frameworks    — 6 种常用编排：react / plan_execute / reflexion /
                  pipeline / rag_local / map_reduce
  Memory        — 本地长期记忆（结构化事实，落盘 JSON）
  Compact       — 本地上下文窗口压缩（不调模型、不丢最近消息）

所有执行结果固定返回 modelCalls=0 / tokens=0 / networkCalls=0。
"""
from __future__ import annotations

import json
import re
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

import docgen
import filehub as FH
import office_skills as OS
import skillhub as SH
import v3_core as V3

ENGINE_TAG = "agent-framework-3.3.0"
MAX_STEPS = 12
MAX_GOAL = 1200
_LOCK = threading.Lock()
_LAST_TRACE = []          # 本次进程最近一次完整轨迹（供 /api/v3/agent/trace 查询）


def last_trace():
    """返回本次进程最近一次执行轨迹（不含内部结果对象）。"""
    return {"engine": ENGINE_TAG, "count": len(_LAST_TRACE),
            "trace": [dict(x) for x in _LAST_TRACE]}

FRAMEWORKS = [
    {"id": "react", "name": "ReAct", "order": 1,
     "desc": "推理 → 行动 → 观察循环；工具失败时自动换备选工具再试",
     "when": "目标不太明确、需要试错"},
    {"id": "plan_execute", "name": "Plan & Execute", "order": 2,
     "desc": "先生成完整计划，再按计划逐步执行并逐步校验",
     "when": "多步骤、步骤之间有依赖"},
    {"id": "reflexion", "name": "Reflexion", "order": 3,
     "desc": "执行 → 校验 → 反思失败原因 → 带修正重试一次",
     "when": "对结果可靠性要求高"},
    {"id": "pipeline", "name": "Pipeline", "order": 4,
     "desc": "用 → / 然后 / 接着 串联，上一步产物自动传给下一步",
     "when": "格式转换、连续加工"},
    {"id": "rag_local", "name": "Local RAG", "order": 5,
     "desc": "先检索本机文件库，再基于命中内容成文（检索也不出本机）",
     "when": "要参考已上传的资料写作"},
    {"id": "map_reduce", "name": "Map / Reduce", "order": 6,
     "desc": "多个文件分别处理，最后汇总合并成一份",
     "when": "批量资料汇总"},
]
FRAMEWORK_MAP = {f["id"]: f for f in FRAMEWORKS}

# 工具参数提示（供前端展示与模型理解，不是强校验）
TOOL_HINTS = {
    "text.gen": {"template": "模板 id", "prompt": "主题与参数"},
    "text.write": {"prompt": "主题与参数", "format": "docx/html/pdf/xlsx/pptx/md/txt/csv", "saveTo": "可选目录"},
    "doc.write": {"prompt": "主题", "saveTo": "可选目录"},
    "doc.md": {"markdown": "Markdown 原文", "title": "标题"},
    "html.write": {"prompt": "主题"}, "pdf.write": {"prompt": "主题"},
    "sheet.write": {"prompt": "主题"}, "slides.write": {"prompt": "主题"},
    "md.write": {"prompt": "主题"}, "txt.write": {"prompt": "主题"}, "csv.write": {"prompt": "主题"},
    "file.read": {"fileId": "上传文件 id 或 path"},
    "file.info": {"fileId": "上传文件 id 或 path"},
    "pdf.to_text": {"fileId": "PDF 文件 id"},
    "pdf.to_md": {"fileId": "PDF 文件 id"},
    "pdf.to_docx": {"fileId": "PDF 文件 id"},
    "pdf.to_html": {"fileId": "PDF 文件 id"},
    "doc.convert": {"fileId": "源文件 id", "format": "目标格式"},
    "doc.merge": {"fileIds": "至少 2 个文件 id", "format": "目标格式"},
    "sheet.from_text": {"fileId": "文本文件 id 或 text", "title": "表格名"},
    "file.save": {"text": "正文", "saveTo": "完整路径或目录"},
    "batch.convert": {"fileIds": "文件 id 数组", "format": "目标格式"},
}

_SPLIT_RE = re.compile(r"→|->|然后|接着|随后|；|;|\bthen\b", re.I)
_PATH_KEYS = ("saveTo", "path", "outputDir", "filename")
# 需要「文件来源」的工具：多步框架会把上一步产物自动注入给它们
_SOURCE_SKILLS = {"doc.convert", "pdf.to_text", "pdf.to_md", "pdf.to_docx",
                  "pdf.to_html", "file.read", "file.info", "sheet.from_text"}
# 目标句里出现的具体格式词，优先级高于全局 format 参数
_FORMAT_WORDS = [("markdown", "md"), ("word", "docx"), ("docx", "docx"),
                 ("网页", "html"), ("html", "html"), ("pdf", "pdf"),
                 ("pptx", "pptx"), ("xlsx", "xlsx"), ("excel", "xlsx"),
                 ("csv", "csv"), ("文本", "txt"), ("txt", "txt"), ("md", "md")]


# ─── 工具注册表 ───────────────────────────────────────────
def tools():
    """22 个内置技能 → 工具清单。"""
    out = []
    for s in SH.ALL_SKILLS:
        sid = s.get("id")
        out.append({
            "id": sid,
            "name": s.get("label") or sid,
            "desc": s.get("desc") or s.get("detail") or "",
            "params": TOOL_HINTS.get(sid, {}),
            "local": True,
        })
    return out


def manifest():
    return {
        "engine": ENGINE_TAG, "local": True,
        "frameworks": FRAMEWORKS, "toolCount": len(tools()), "tools": tools(),
        "maxSteps": MAX_STEPS, "maxGoalChars": MAX_GOAL,
        "memory": {"items": len(memory_list()), "path": str(_mem_path())},
        "capabilities": ["工具注册表", "目标分解", "轨迹记录", "结果校验", "失败重试",
                         "本地检索", "批量汇总", "长期记忆", "上下文压缩"],
        "cost": {"modelCalls": 0, "tokens": 0, "networkCalls": 0},
    }


# ─── 本地长期记忆 ─────────────────────────────────────────
def _mem_path():
    return V3.v3_root() / "agent" / "memory.json"


def _mem_load():
    p = _mem_path()
    try:
        if p.is_file():
            d = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(d, dict) and isinstance(d.get("items"), list):
                return d
    except Exception:
        pass
    return {"items": [], "updated": ""}


def _mem_save(d):
    p = _mem_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def memory_list():
    with _LOCK:
        return list(_mem_load()["items"])


def memory_add(text, tag="note"):
    t = str(text or "").strip()
    if not t:
        raise ValueError("记忆内容不能为空")
    item = {"id": uuid.uuid4().hex[:10], "text": t[:600], "tag": str(tag or "note")[:24],
            "at": datetime.now().isoformat(timespec="seconds")}
    with _LOCK:
        d = _mem_load()
        d["items"] = [x for x in d["items"] if x.get("text") != t][-199:]
        d["items"].append(item)
        d["updated"] = item["at"]
        _mem_save(d)
    return {"ok": True, "item": item, "count": len(d["items"])}


def memory_delete(mid):
    with _LOCK:
        d = _mem_load()
        before = len(d["items"])
        d["items"] = [x for x in d["items"] if x.get("id") != mid]
        _mem_save(d)
    return {"ok": True, "removed": before - len(d["items"]), "count": len(d["items"])}


def memory_clear():
    with _LOCK:
        _mem_save({"items": [], "updated": datetime.now().isoformat(timespec="seconds")})
    return {"ok": True, "count": 0}


def memory_recall(query="", limit=5):
    q = str(query or "").strip().lower()
    items = memory_list()
    if q:
        items = [x for x in items if q in x.get("text", "").lower() or q in x.get("tag", "").lower()] or items
    return list(reversed(items))[:max(1, min(limit, 20))]


# ─── 上下文窗口压缩 ───────────────────────────────────────
def compact(messages, budget=16000, keep=6):
    """本地压缩：旧消息合成一条摘要，保留最近 keep 条原文；零 token、零联网。"""
    msgs = [m for m in (messages or []) if isinstance(m, dict)]
    before = sum(len(str(m.get("content") or "")) for m in msgs)
    if len(msgs) <= keep + 1 and before <= int(budget) * 0.8:
        return {"compacted": False, "messages": msgs, "removed": 0,
                "beforeChars": before, "afterChars": before, "budget": int(budget),
                "summary": "", "modelCalls": 0, "tokens": 0, "networkCalls": 0, "local": True}
    head, tail = msgs[:-keep], msgs[-keep:]
    lines = ["### 上下文压缩摘要（本地生成，未调用模型）", ""]
    for m in head[-30:]:
        role = "用户" if m.get("role") == "user" else "助手"
        txt = re.sub(r"\s+", " ", str(m.get("content") or "")).strip()[:130]
        if txt:
            lines.append("- **%s**：%s…" % (role, txt))
    summary = "\n".join(lines)
    note = {"id": "compact-" + uuid.uuid4().hex[:8], "role": "assistant",
            "content": summary, "compacted": True, "local": True,
            "source": "local", "at": int(time.time() * 1000)}
    out = [note] + tail
    after = sum(len(str(m.get("content") or "")) for m in out)
    V3.audit_append("local.agent.compact", "本地压缩上下文窗口",
                    {"removed": len(head), "before": before, "after": after})
    return {"compacted": True, "messages": out, "removed": len(head),
            "beforeChars": before, "afterChars": after, "budget": int(budget),
            "summary": summary, "modelCalls": 0, "tokens": 0, "networkCalls": 0, "local": True}


# ─── 目标分解（规则驱动，不调模型） ───────────────────────
def _base_params(p):
    b = {}
    for k in ("fileId", "fileIds", "path", "text", "title", "template", "markdown", "maxChars"):
        if p.get(k) not in (None, "", []):
            b[k] = p[k]
    for k in ("saveTo", "outputDir", "filename"):
        if p.get(k):
            b[k] = p[k]
    return b


def _intent(seg, p):
    """把一句中文目标映射为 1 个可执行的工具调用。"""
    s = seg.strip()
    low = s.lower()
    fmt = str(p.get("format") or "").lower()
    b = _base_params(p)

    def step(skill, extra=None, thought=""):
        q = dict(b)
        q.update(extra or {})
        return {"skill": skill, "params": q,
                "thought": thought or ("规则路由 → `%s`" % skill), "note": s[:60]}

    if not s:
        return step("text.write", {"prompt": "工作文档", "format": fmt or "docx"}, "空目标 → 默认生成本地文档")

    if "合并" in s or "汇总" in s:
        ids = p.get("fileIds") or ([p["fileId"]] if p.get("fileId") else [])
        return step("doc.merge", {"fileIds": ids, "format": fmt or "docx"}, "识别到合并意图")
    if "批量" in s or "多个文件" in s:
        return step("batch.convert", {"fileIds": p.get("fileIds") or ([p["fileId"]] if p.get("fileId") else []),
                                     "format": fmt or "docx"}, "识别到批量转换意图")
    if any(k in s for k in ("表格", "课时", "excel", "台账")):
        q = {"title": p.get("title") or "文本转表格"}
        if not p.get("text") and not p.get("fileId"):
            q["text"] = s
        return step("sheet.from_text", q, "识别到表格生成意图")
    if "pdf" in low and any(k in s for k in ("转", "提取", "文本", "word", "网页", "markdown")):
        if "word" in low or "docx" in fmt:
            sk = "pdf.to_docx"
        elif "网页" in s or fmt == "html":
            sk = "pdf.to_html"
        elif "markdown" in low or fmt == "md":
            sk = "pdf.to_md"
        elif "文本" in s or "提取" in s or fmt == "txt":
            sk = "pdf.to_text"
        else:
            sk = "pdf.to_docx"
        return step(sk, {}, "识别到 PDF 转换意图 → %s" % sk)
    if any(k in s for k in ("保存", "写入", "存到", "另存")):
        q = {"text": p.get("text") or s, "saveTo": p.get("saveTo") or p.get("outputDir") or ""}
        if not q["saveTo"]:
            q["saveTo"] = str(OS.output_dir() / "agent_output.txt")
        return step("file.save", q, "识别到指定位置写入意图")
    if "信息" in s or "元信息" in s:
        return step("file.info", {}, "识别到文件信息查询意图")
    if "读取" in s or "查看内容" in s or "提取文字" in s:
        return step("file.read", {}, "识别到读取解析意图")
    if any(k in s for k in ("转换", "转成", "导出为", "格式", "转为")):
        f2 = ""
        for token, val in _FORMAT_WORDS:
            if token in low:
                f2 = val
                break
        return step("doc.convert", {"format": f2 or fmt or "docx"},
                    "识别到格式转换意图 → %s" % (f2 or fmt or "docx"))
    # 默认：本地长文生成 + 导出
    q = {"prompt": s, "format": fmt or "docx"}
    if p.get("template"):
        q["template"] = p["template"]
    return step("text.write", q, "识别到写作意图 → 本地模板引擎")


def plan(goal, params=None):
    """只规划不执行，供前端展示计划。"""
    g = str(goal or "")[:MAX_GOAL]
    p = dict(params or {})
    segs = [x.strip() for x in _SPLIT_RE.split(g) if x.strip()] or [g or "工作文档"]
    steps = [_intent(x, p) for x in segs[:MAX_STEPS]]
    return {"ok": True, "goal": g, "steps": steps, "count": len(steps),
            "planner": "local-rule-planner", "modelCalls": 0, "tokens": 0,
            "networkCalls": 0, "local": True}


def _fallback_for(step):
    """ReAct 失败时的备选工具。"""
    sk = step["skill"]
    return {
        "doc.convert": "text.write", "pdf.to_docx": "doc.convert",
        "pdf.to_text": "doc.convert", "pdf.to_md": "doc.convert",
        "pdf.to_html": "doc.convert", "sheet.from_text": "text.write",
        "doc.merge": "batch.convert", "batch.convert": "doc.convert",
        "file.read": "file.info", "file.info": "file.read",
    }.get(sk)


# ─── 执行器 ───────────────────────────────────────────────
def _safe_params(params):
    p = dict(params or {})
    for k, v in list(p.items()):
        if k in _PATH_KEYS and isinstance(v, str) and v.strip() and OS.is_remote_path(v):
            raise ValueError("%s 不接受 URL / UNC 网络路径：%s" % (k, v[:80]))
    return p


def _observe(skill, res):
    if not isinstance(res, dict):
        return "工具返回非结构化结果"
    if res.get("error"):
        return "工具报错：%s" % str(res["error"])[:120]
    if res.get("path"):
        n = res.get("name") or Path(res["path"]).name
        sz = res.get("size") or 0
        return "已落盘 `%s`（%s B）" % (n, sz)
    if res.get("chars"):
        return "返回文本 %d 字" % res["chars"]
    if res.get("succeeded") is not None:
        return "批量完成 %s/%s" % (res.get("succeeded"), res.get("total"))
    if res.get("doc"):
        return "生成结构化文档 %d 字" % len(str(res["doc"].get("markdown") or ""))
    return "工具执行完成"


def _exec_step(step, ctx, index, framework):
    t0 = time.time()
    skill = str(step.get("skill") or "")
    if skill not in SH.ALL_MAP:
        raise ValueError("工具不在白名单：%s" % skill[:60])
    p = _safe_params(step.get("params"))
    # 多步编排：上一步产物自动注入给下一步需要文件来源的工具
    if (skill in _SOURCE_SKILLS and ctx.get("lastPath")
            and not (p.get("fileId") or p.get("path") or p.get("fileIds"))):
        p["path"] = ctx["lastPath"]
    res = SH.run(skill, p)
    obs = _observe(skill, res)
    if isinstance(res, dict):
        if res.get("path"):
            ctx["lastPath"] = res["path"]
        if res.get("text"):
            ctx["lastText"] = str(res["text"])[:20000]
        if res.get("markdown"):
            ctx["lastText"] = str(res["markdown"])[:20000]
    return {
        "i": index, "framework": framework, "thought": step.get("thought") or "",
        "action": skill, "params": {k: (str(v)[:60] if isinstance(v, (str, list, dict)) else v)
                                    for k, v in p.items()},
        "observation": obs, "ok": not (isinstance(res, dict) and res.get("ok") is False),
        "ms": max(1, int((time.time() - t0) * 1000)),
        "file": ({k: res.get(k) for k in ("name", "path", "size", "format", "url", "savedTo", "dir")}
                 if isinstance(res, dict) and res.get("path") else None),
        "_res": res,
    }


def _verify(trace):
    issues = []
    for s in trace:
        if not s.get("ok"):
            issues.append("第 %d 步 %s 未成功" % (s["i"], s["action"]))
            continue
        f = s.get("file")
        if f and f.get("path"):
            p = Path(f["path"])
            if not p.is_file() or p.stat().st_size <= 0:
                issues.append("第 %d 步产物未落盘或为空：%s" % (s["i"], f.get("name")))
    return {"ok": not issues, "checked": len(trace), "issues": issues[:8]}


# ─── 本地检索（Local RAG） ────────────────────────────────
def _local_retrieve(goal, limit=3):
    words = [w for w in re.split(r"[\s,，。、；;：:！!？?/]+", str(goal or "")) if len(w) >= 2][:8]
    hits = []
    for f in FH.list_files().get("files", [])[:60]:
        name = str(f.get("name") or "")
        score = sum(1 for w in words if w.lower() in name.lower())
        if score:
            hits.append((score, f))
    if not hits:
        hits = [(0, f) for f in FH.list_files().get("files", [])[:limit]]
    hits.sort(key=lambda x: x[0], reverse=True)
    out = []
    for score, f in hits[:limit]:
        try:
            r = FH.read(f["id"], 3000)
            text = str(r.get("text") or "")
        except Exception:
            text = ""
        out.append({"id": f["id"], "name": f.get("name"), "score": score,
                    "chars": len(text), "excerpt": text[:400]})
    return out


# ─── 主入口 ───────────────────────────────────────────────
def run(goal=None, framework="react", params=None):
    """执行一个目标，返回完整轨迹与产物。全程本机，不调用模型、不联网。"""
    t0 = time.time()
    fw = str(framework or "react").strip().lower()
    if fw not in FRAMEWORK_MAP:
        raise ValueError("未知框架：%s（可用：%s）" % (fw, ", ".join(FRAMEWORK_MAP)))
    g = str(goal or "")[:MAX_GOAL].strip()
    if not g:
        raise ValueError("请给出要完成的目标")
    p = dict(params or {})
    ctx = {"lastPath": None, "lastText": ""}
    trace, files, notes = [], [], []

    if fw == "pipeline":
        segs = [x.strip() for x in _SPLIT_RE.split(g) if x.strip()] or [g]
        raw_steps = [_intent(x, p) for x in segs[:MAX_STEPS]]
        notes.append("流水线拆成 %d 段，上一步产物自动作为下一步输入" % len(raw_steps))
    elif fw == "rag_local":
        hits = _local_retrieve(g, int(p.get("topK") or 3))
        notes.append("本地文件库命中 %d 份：%s" %
                     (len(hits), "、".join(str(h["name"]) for h in hits) or "（库为空，将用目标文本成文）"))
        body = "\n\n".join("### %s\n%s" % (h["name"], h["excerpt"] or "（该文件无可提取文本）")
                           for h in hits)
        title = "本地资料汇编"
        md = "# %s\n\n## 检索目标\n\n%s\n\n## 本机命中资料（%d 份）\n\n%s\n" % (
            title, g[:300], len(hits), body[:6000])
        q = dict(p)
        q.pop("prompt", None)
        q["markdown"] = md
        q["title"] = title
        q.setdefault("format", p.get("format") or "docx")
        raw_steps = [{"skill": "text.write", "params": q,
                      "thought": "检索本机文件库 → 组装命中资料 → 导出汇编文档（不伪造生成内容）",
                      "note": "本地检索成文"}]
    elif fw == "map_reduce":
        ids = p.get("fileIds") or ([p["fileId"]] if p.get("fileId") else [])
        if not ids:
            raise ValueError("map_reduce 需要 fileIds 数组（先在文件库上传文件）")
        raw_steps = []
        for fid in ids[:MAX_STEPS - 1]:
            q = dict(p); q["fileId"] = fid; q.pop("fileIds", None)
            q.setdefault("format", p.get("format") or "md")
            raw_steps.append({"skill": "doc.convert", "params": q,
                              "thought": "Map：逐个文件提取文本", "note": str(fid)[:40]})
        q = dict(p); q["fileIds"] = ids; q.setdefault("format", "docx")
        raw_steps.append({"skill": "doc.merge", "params": q,
                          "thought": "Reduce：汇总为一份文档", "note": "汇总合并"})
        notes.append("Map %d 份 → Reduce 1 份" % len(ids))
    else:
        raw_steps = plan(g, p)["steps"]

    # Reflexion / Plan-Execute 先展示计划
    if fw in ("plan_execute", "reflexion"):
        notes.append("预生成计划 %d 步：%s" % (len(raw_steps), " → ".join(s["skill"] for s in raw_steps)))

    i = 0
    for st in raw_steps[:MAX_STEPS]:
        i += 1
        try:
            item = _exec_step(st, ctx, i, fw)
        except Exception as e:
            item = {"i": i, "framework": fw, "thought": st.get("thought") or "",
                    "action": st.get("skill") or "?", "params": {}, "observation": "失败：%s" % str(e)[:160],
                    "ok": False, "ms": 1, "file": None, "_res": {}}
        # ReAct：观察失败 → 换备选工具再试
        if not item["ok"] and fw == "react":
            alt = _fallback_for({"skill": item["action"]})
            if alt:
                try:
                    alt_step = {"skill": alt, "params": dict(st.get("params") or {}),
                                "thought": "观察：%s → 改用备选工具 `%s`" % (item["observation"][:60], alt)}
                    alt_step["params"].setdefault("prompt", g[:300])
                    item2 = _exec_step(alt_step, ctx, i, fw)
                    trace.append({**item, "retried": False})
                    item = {**item2, "retried": True}
                except Exception as e:
                    item["observation"] += "；备选工具也失败：%s" % str(e)[:100]
        # Reflexion：校验失败 → 反思并重试一次
        if not item["ok"] and fw == "reflexion":
            refl = "反思：%s。可能原因：缺少 fileId / 参数不完整 / 目标格式不支持。" % item["observation"][:80]
            q = dict(st.get("params") or {})
            q.setdefault("prompt", g[:300])
            q.setdefault("format", "docx")
            try:
                item2 = _exec_step({"skill": st["skill"], "params": q,
                                    "thought": refl + " 带补全参数重试一次"}, ctx, i, fw)
                trace.append({**item, "reflection": refl})
                item = {**item2, "retried": True, "reflection": refl}
            except Exception as e:
                item["observation"] += "；重试失败：%s" % str(e)[:100]
        trace.append(item)
        if item.get("file") and item["file"].get("path"):
            files.append(item["file"])

    clean_trace = [{k: v for k, v in x.items() if k != "_res"} for x in trace]
    global _LAST_TRACE
    _LAST_TRACE = clean_trace
    ver = _verify(clean_trace)
    ok_n = sum(1 for x in clean_trace if x.get("ok"))
    mem = memory_recall(g, 3)
    ms = max(1, int((time.time() - t0) * 1000))

    lines = [
        "### 本机 Agent 执行结果 · %s" % FRAMEWORK_MAP[fw]["name"], "",
        "- 目标：**%s**" % g[:120],
        "- 框架：`%s` · 步骤 **%d** 条 · 成功 **%d** · 失败 **%d**" %
        (fw, len(clean_trace), ok_n, len(clean_trace) - ok_n),
        "- 耗时：**%d ms** · 校验：**%s**" % (ms, "通过" if ver["ok"] else "有问题"),
        "- **云端调用 0 次 · token 0 · 联网 0**（全部由本机工具注册表执行）", "",
    ]
    for n in notes:
        lines.append("> " + n)
    if notes:
        lines.append("")
    for s in clean_trace:
        mark = "✅" if s.get("ok") else "❌"
        extra = " · 重试" if s.get("retried") else ""
        lines.append("%s **%d. %s**%s — %s（%d ms）" %
                     (mark, s["i"], s["action"], extra, s["observation"], s["ms"]))
        if s.get("thought"):
            lines.append("   - 思考：%s" % s["thought"][:120])
    if files:
        lines += ["", "**产物**："]
        for f in files[:10]:
            lines.append("- `%s` — %s" % (f.get("name") or Path(f["path"]).name, f.get("path")))
    if ver["issues"]:
        lines += ["", "**校验问题**："] + ["- " + x for x in ver["issues"]]
    if mem:
        lines += ["", "**关联记忆**："] + ["- " + x["text"][:90] for x in mem]

    V3.audit_append("local.agent", "Agent 框架 %s 执行 %d 步" % (fw, len(clean_trace)),
                    {"ok": ok_n, "failed": len(clean_trace) - ok_n, "ms": ms, "framework": fw})
    return {
        "ok": ver["ok"] and ok_n == len(clean_trace), "engine": ENGINE_TAG,
        "framework": fw, "frameworkName": FRAMEWORK_MAP[fw]["name"],
        "goal": g, "steps": len(clean_trace), "succeeded": ok_n,
        "failed": len(clean_trace) - ok_n, "trace": clean_trace,
        "files": files, "verification": ver, "notes": notes,
        "memoryUsed": [x["text"][:90] for x in mem], "summary": "\n".join(lines),
        "ms": ms, "at": datetime.now().isoformat(timespec="seconds"),
        "modelCalls": 0, "tokens": 0, "networkCalls": 0, "local": True,
    }


def describe():
    return {
        "engine": ENGINE_TAG, "frameworks": [f["id"] for f in FRAMEWORKS],
        "tools": len(tools()), "maxSteps": MAX_STEPS,
        "endpoints": ["/api/v3/agent", "/api/v3/agent/run", "/api/v3/agent/plan",
                      "/api/v3/agent/compact", "/api/v3/agent/memory", "/api/v3/agent/trace"],
        "cost": {"modelCalls": 0, "tokens": 0, "networkCalls": 0},
    }
