# -*- coding: utf-8 -*-
"""Super-Agient 任务指令协议（task_engine）。

解决「大模型分配任务指令后就能干活」：
  模型不再亲自写几千字文档，只输出一个很短的结构化指令块；
  本机执行器解析 → 白名单校验 → 调用内置技能 → 落盘并返回可校验的执行轨迹。

这就是混合省 token 模式：云端只负责「听懂意图 + 派活」，本地负责「生成 + 排版 + 保存」。
执行器本身不调用云端模型、不联网、不消耗 token。
"""

import json
import re
import time
from datetime import datetime

import skillhub
import v3_core as V3

ENGINE_TAG = "task-engine-3.3.0"
MAX_TASKS = 20
MAX_PARAMS_BYTES = 200 * 1024

BLOCK_RE = re.compile(r"```(?:agent-task|task|json)\s*\r?\n([\s\S]*?)```", re.I)
INLINE_RE = re.compile(r"@task\s*(\{[\s\S]*?\})(?=\s|$)", re.I)
FENCE_LANG_NONE = re.compile(r"```\s*\r?\n([\s\S]*?)```")


def protocol_prompt(skills=None):
    """注入给模型的系统提示：告诉它有哪些本地技能、如何派活。"""
    skills = skills or skillhub.BUILTIN_SKILLS + skillhub.OS.SKILLS
    lines = ["- `%s` — %s" % (s["id"], s["label"]) for s in skills[:40]]
    return (
        "## 本机执行器（重要）\n"
        "你连接着一个**本机办公执行器**。当用户要求写方案、写大纲、生成或转换办公文件、"
        "读取上传文件、保存到指定路径时，**不要自己撰写长文**，只输出一条结构化任务指令，"
        "由本机执行器确定性完成（零 token、零联网、可落盘到用户指定目录）。\n\n"
        "输出格式（唯一被识别的格式）：\n"
        "```agent-task\n"
        '{"skill":"doc.convert","params":{"fileId":"<文件ID>","format":"docx","saveTo":"D:\\\\输出\\\\文件.docx"},"note":"把上传的 PDF 转成 Word"}\n'
        "```\n\n"
        "规则：\n"
        "1. `skill` 必须是下列白名单之一，`params` 为参数对象；一次可输出多个指令（每行一个 JSON）。\n"
        "2. 用户给了保存位置时，把完整路径放进 `params.saveTo` 或 `params.outputDir`。\n"
        "3. 涉及用户上传的文件时，用 `params.fileId`（前端会给出文件 ID）。\n"
        "4. 指令块之外可以写一句简短说明，但不要复述文件内容、不要生成大段正文。\n"
        "5. 纯聊天、解释概念、回答知识问题时**不要**输出指令块，正常回答即可。\n\n"
        "可用技能：\n" + "\n".join(lines) + "\n\n"
        "技能清单也可以通过本机 `/api/v3/skills` 获取完整定义。"
    )


def _try_json(s):
    s = str(s or "").strip()
    if not s or s[0] not in "[{":
        return None
    try:
        return json.loads(s)
    except Exception:
        return None


def _flatten(obj):
    """把单个对象 / 数组 / {"tasks":[...]} 统一成任务列表。"""
    if obj is None:
        return []
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        if isinstance(obj.get("tasks"), list):
            return [x for x in obj["tasks"] if isinstance(x, dict)]
        if "skill" in obj:
            return [obj]
    return []


def parse(text):
    """从模型回复中提取任务指令。返回 (tasks, errors)。"""
    src = str(text or "")
    found, errors = [], []

    for m in BLOCK_RE.finditer(src):
        body = m.group(1).strip()
        obj = _try_json(body)
        if obj is None:
            # 兼容「一行一个 JSON 对象」
            for line in body.splitlines():
                o = _try_json(line)
                if o is not None:
                    found += _flatten(o)
                elif line.strip().startswith("{"):
                    errors.append("指令行不是合法 JSON：%s" % line.strip()[:80])
        else:
            found += _flatten(obj)

    for m in INLINE_RE.finditer(src):
        o = _try_json(m.group(1))
        if o is not None:
            found += _flatten(o)

    # 整段就是一个 JSON（模型没加代码块）
    if not found:
        o = _try_json(src)
        if o is not None:
            found += _flatten(o)

    # 去重（同一 skill + 同一 params 只留一条）
    seen, uniq = set(), []
    for t in found:
        key = json.dumps({"s": t.get("skill"), "p": t.get("params") or {}},
                         ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(t)
    return uniq[:MAX_TASKS], errors


def strip_blocks(text):
    """把回复里的任务块替换成占位，避免把 JSON 原文当正文展示。"""
    def rep(m):
        body = m.group(1).strip()
        return "\n> `[本机任务指令已提取并执行]`\n" if _try_json(body) is not None or "skill" in body else m.group(0)
    out = BLOCK_RE.sub(rep, str(text or ""))
    out = INLINE_RE.sub("\n> `[本机任务指令已提取并执行]`\n", out)
    return out


def validate(task):
    """白名单 + 体积 + 危险字段校验。返回 (规范化任务, 错误文本)。"""
    if not isinstance(task, dict):
        return None, "任务不是对象"
    skill = str(task.get("skill") or "").strip()
    if not skill:
        return None, "缺少 skill"
    if skill not in skillhub.ALL_MAP:
        return None, "技能不在白名单：%s" % skill
    params = task.get("params") or {}
    if not isinstance(params, dict):
        return None, "params 必须是对象"
    if len(json.dumps(params, ensure_ascii=False).encode("utf-8")) > MAX_PARAMS_BYTES:
        return None, "params 体积过大"
    ids = params.get("fileIds")
    if isinstance(ids, list) and len(ids) > 20:
        return None, "fileIds 超过 20 个"
    for k in ("saveTo", "path", "outputDir"):
        v = str(params.get(k) or "")
        if v and skillhub.OS.is_remote_path(v):
            return None, "%s 不接受 URL / UNC 网络路径" % k
    norm = {"skill": skill, "params": params,
            "note": str(task.get("note") or "")[:160],
            "id": str(task.get("id") or "")[:40]}
    return norm, None


def execute(text=None, tasks=None, defaults=None):
    """执行任务列表，返回带执行轨迹的结构化结果。"""
    t0 = time.time()
    errors = []
    if tasks is None:
        tasks, errors = parse(text or "")
    elif not isinstance(tasks, list):
        tasks, errors = [], ["tasks 必须是数组"]
    defaults = defaults or {}

    steps, files = [], []
    for i, raw in enumerate(tasks[:MAX_TASKS], 1):
        norm, err = validate(raw)
        if err:
            steps.append({"id": "t%d" % i, "skill": str((raw or {}).get("skill") or "?"),
                          "ok": False, "error": err, "ms": 0})
            continue
        params = dict(defaults)
        params.update(norm["params"])
        st = time.time()
        try:
            r = skillhub.run(norm["skill"], params)
            ok = bool(r.get("ok", True))
            item = {"id": norm["id"] or ("t%d" % i), "skill": norm["skill"],
                    "note": norm["note"], "ok": ok,
                    "ms": max(1, int((time.time() - st) * 1000)),
                    "name": r.get("name"), "path": r.get("path") or r.get("savedTo"),
                    "savedTo": r.get("savedTo"), "size": r.get("size"),
                    "format": r.get("format"), "url": r.get("url"),
                    "chars": r.get("chars") or r.get("sourceChars") or 0,
                    "warnings": r.get("warnings") or []}
            if r.get("url") or r.get("path"):
                files.append({k: r.get(k) for k in
                              ("name", "path", "savedTo", "size", "format", "url", "dir", "chars")})
            steps.append(item)
        except Exception as e:
            steps.append({"id": norm["id"] or ("t%d" % i), "skill": norm["skill"],
                          "note": norm["note"], "ok": False,
                          "error": str(e)[:220], "ms": max(1, int((time.time() - st) * 1000))})

    ok_n = sum(1 for s in steps if s["ok"])
    bad_n = len(steps) - ok_n
    summary_lines = [
        "### 本机任务执行结果", "",
        "- 指令：**%d** 条 · 成功 **%d** · 失败 **%d**" % (len(steps), ok_n, bad_n),
        "- 耗时：**%d ms**" % int((time.time() - t0) * 1000),
        "- **云端调用 0 次 · token 0 · 联网 0**（模型只输出了指令，生成与保存全在本机）", "",
    ]
    for s in steps:
        if s["ok"]:
            dest = s.get("savedTo") or s.get("path") or s.get("name") or "（未落盘）"
            summary_lines.append("- ✅ `%s` → **%s**（%s，%d ms）" %
                                 (s["skill"], dest, ("%d B" % s["size"]) if s.get("size") else "已执行", s["ms"]))
        else:
            summary_lines.append("- ❌ `%s` 失败：%s" % (s["skill"], s.get("error")))
    for e in errors[:5]:
        summary_lines.append("- ⚠️ " + e)
    if not steps and not errors:
        summary_lines.append("（未识别到任务指令。可用 `@task {...}` 手动下发，或检查指令块格式。）")

    V3.audit_append("local.task", "任务指令执行 %d 条" % len(steps),
                    {"ok": ok_n, "failed": bad_n, "ms": int((time.time() - t0) * 1000)})
    return {
        "ok": bad_n == 0, "engine": ENGINE_TAG, "tasks": len(steps),
        "succeeded": ok_n, "failed": bad_n, "steps": steps, "files": files,
        "parseErrors": errors, "summary": "\n".join(summary_lines),
        "ms": int((time.time() - t0) * 1000),
        "modelCalls": 0, "tokens": 0, "networkCalls": 0, "local": True,
        "at": datetime.now().isoformat(timespec="seconds"),
    }


def describe():
    return {
        "engine": ENGINE_TAG, "version": "1.0", "maxTasks": MAX_TASKS,
        "block": "```agent-task\n{...}\n```", "inline": "@task {...}",
        "skills": skillhub.skill_ids(),
        "schema": {"skill": "必填，白名单技能 id", "params": "参数对象",
                   "note": "可选说明", "id": "可选编号"},
        "safety": ["技能白名单", "params 体积上限 200 KB", "拒绝 URL / UNC 路径",
                   "同名文件不覆盖", "失败不伪造结果"],
        "local": True,
    }
