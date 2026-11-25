# -*- coding: utf-8 -*-
"""AI.Super-Agent v3.0 内核基础设施（纯标准库，零出域）。

提供六组能力，供 launcher3.py 的 HTTP 路由调用：
  1. 会话持久化   sessions/<id>.json，可列表 / 读取 / 保存 / 删除 / 重命名
  2. Provider 注册表 内置预设 + 用户自定义，统一描述模型接入
  3. 脱敏配置     前端永不拿到完整 API Key；写入时占位符保留原值
  4. 审计哈希链   chain.jsonl，每条含前序哈希，可校验；统计本地/联网次数
  5. 文件快照     写文件前留档，可一键回滚
  6. 健康检查     只读本地状态，不主动联网

隐私约束：审计只记类型、摘要与长度，不记会话正文、不记密钥。
"""

import hashlib
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

V3_TAG = "3.0.0"
SAFE_ID = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")
MASK = "__V3_MASKED__"

# ─── 路径 ────────────────────────────────────────────────

def v3_root() -> Path:
    base = os.environ.get("AGENT_DATA_DIR")
    root = Path(base) if base else (Path.home() / ".ai-super-agent")
    return root / "AI.Super-Agent" / "v3"


def _sub(name: str) -> Path:
    p = v3_root() / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe(sid: str) -> bool:
    return bool(SAFE_ID.match(str(sid or "")))


def _read_json(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(p: Path, obj) -> bool:
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


# ─── 1. 会话持久化 ───────────────────────────────────────

def list_sessions() -> list:
    out = []
    for p in sorted(_sub("sessions").glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        d = _read_json(p)
        if isinstance(d, dict) and d.get("id"):
            out.append({"id": d["id"], "title": d.get("title") or "新对话",
                        "updatedAt": d.get("updatedAt") or "",
                        "count": len(d.get("messages") or []),
                        "preview": _preview(d.get("messages") or [])})
    return out


def _preview(messages) -> str:
    for m in reversed(messages or []):
        if m.get("role") == "user":
            return str(m.get("content") or "")[:60]
    return ""


def read_session(sid: str):
    if not _safe(sid):
        return None
    return _read_json(_sub("sessions") / (sid + ".json"))


def write_session(sid: str, payload: dict):
    if not _safe(sid):
        return {"ok": False, "error": "会话 id 非法"}
    p = _sub("sessions") / (sid + ".json")
    old = _read_json(p, {}) or {}
    messages = payload.get("messages")
    if messages is None:
        messages = old.get("messages") or []
    title = payload.get("title") or old.get("title") or "新对话"
    # 首条用户消息自动生成标题
    if title == "新对话" and messages:
        for m in messages:
            if m.get("role") == "user" and str(m.get("content") or "").strip():
                title = str(m["content"]).strip().replace("\n", " ")[:28]
                break
    data = {"id": sid, "title": title, "updatedAt": _now(),
            "createdAt": old.get("createdAt") or _now(),
            "provider": payload.get("provider") or old.get("provider") or "",
            "messages": messages}
    if not _write_json(p, data):
        return {"ok": False, "error": "写入失败"}
    return {"ok": True, "session": {k: v for k, v in data.items() if k != "messages"},
            "count": len(messages)}


def delete_session(sid: str) -> bool:
    if not _safe(sid):
        return False
    p = _sub("sessions") / (sid + ".json")
    try:
        if p.exists():
            p.unlink()
        return True
    except Exception:
        return False


# ─── 2. Provider 注册表 ──────────────────────────────────

BUILTIN_PROVIDERS = [
    {"id": "spark-maas", "label": "讯飞星辰 MaaS · Spark X2.5", "vendor": "讯飞",
     "baseUrl": "https://maas-api.cn-huabei-1.xf-yun.com/v1", "model": "spark-x2.5-1.7b",
     "protocol": "openai", "authMode": "bearer", "builtin": True,
     "caps": {"stream": True, "tools": False, "reasoning": True},
     "extra": {"enable_thinking": False},
     "hint": "示例预设；请自行申请账号并填写 Key 后使用"},
    {"id": "deepseek", "label": "DeepSeek", "vendor": "DeepSeek",
     "baseUrl": "https://api.deepseek.com/v1", "model": "deepseek-chat",
     "protocol": "openai", "authMode": "bearer", "builtin": True,
     "caps": {"stream": True, "tools": True, "reasoning": False}, "extra": {},
     "hint": "自带 CORS，浏览器可直连（历史版本即用此项）"},
    {"id": "moonshot", "label": "Kimi / Moonshot", "vendor": "月之暗面",
     "baseUrl": "https://api.moonshot.cn/v1", "model": "moonshot-v1-8k",
     "protocol": "openai", "authMode": "bearer", "builtin": True,
     "caps": {"stream": True, "tools": True, "reasoning": False}, "extra": {}, "hint": "长文本"},
    {"id": "zhipu", "label": "智谱 GLM", "vendor": "智谱",
     "baseUrl": "https://open.bigmodel.cn/api/paas/v4", "model": "glm-4-flash",
     "protocol": "openai", "authMode": "bearer", "builtin": True,
     "caps": {"stream": True, "tools": True, "reasoning": False}, "extra": {}, "hint": ""},
    {"id": "qwen", "label": "阿里通义千问", "vendor": "阿里",
     "baseUrl": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus",
     "protocol": "openai", "authMode": "bearer", "builtin": True,
     "caps": {"stream": True, "tools": True, "reasoning": False}, "extra": {}, "hint": ""},
    {"id": "doubao", "label": "火山方舟 · 豆包", "vendor": "字节",
     "baseUrl": "https://ark.cn-beijing.volces.com/api/v3", "model": "",
     "protocol": "openai", "authMode": "bearer", "builtin": True,
     "caps": {"stream": True, "tools": True, "reasoning": False}, "extra": {},
     "hint": "model 需填控制台的 Endpoint ID（ep-...）或方舟 API Key 对应的模型"},
    {"id": "spark-open", "label": "讯飞星火（开放平台）", "vendor": "讯飞",
     "baseUrl": "https://spark-api-open.xf-yun.com/v1", "model": "generalv3.5",
     "protocol": "openai", "authMode": "bearer", "builtin": True,
     "caps": {"stream": True, "tools": True, "reasoning": False}, "extra": {},
     "hint": "与星辰 MaaS 是两套独立凭据，不可混用"},
    {"id": "local-bridge", "label": "本地桥 8787（Claude Desktop 共用）", "vendor": "本机",
     "baseUrl": "http://127.0.0.1:8787/v1", "model": "spark-x2.5-1.7b",
     "protocol": "openai", "authMode": "bearer", "builtin": True,
     "caps": {"stream": True, "tools": False, "reasoning": True}, "extra": {},
     "hint": "依赖本机网关进程；V3 默认不用它"},
    {"id": "ollama", "label": "Ollama（本地离线）", "vendor": "本机",
     "baseUrl": "http://127.0.0.1:11434/v1", "model": "qwen2.5:7b",
     "protocol": "openai", "authMode": "none", "builtin": True,
     "caps": {"stream": True, "tools": False, "reasoning": False}, "extra": {},
     "hint": "完全离线，涉密场景首选；需本机已启动 Ollama"},
]


def v3_settings(cfg: dict) -> dict:
    s = cfg.get("v3") if isinstance(cfg, dict) else None
    if not isinstance(s, dict):
        s = {}
    defaults = {
        "activeProvider": "deepseek",
        "fallbackProvider": "off",
        "theme": "light",
        "disableThinking": True,
        "maxSteps": 6,
        "contextLimit": 16000,
        "customProviders": [],
        "overrides": {},
        "autoSnapshot": True,
    }
    for k, v in defaults.items():
        s.setdefault(k, v)
    return s


def all_providers(cfg: dict) -> list:
    """内置预设 + 用户在设置面板的覆盖值 + 自定义 Provider。

    overrides 只允许改 baseUrl / model / label / extra，密钥统一存 cfg.apiKey，
    避免密钥散落在多个字段里。
    """
    s = v3_settings(cfg)
    overrides = s.get("overrides") if isinstance(s.get("overrides"), dict) else {}
    out = []
    for p in BUILTIN_PROVIDERS:
        q = dict(p)
        ov = overrides.get(p.get("id"))
        if isinstance(ov, dict):
            for k in ("baseUrl", "model", "label", "extra"):
                if k in ov:
                    q[k] = ov[k]
        out.append(q)
    for p in s.get("customProviders") or []:
        if isinstance(p, dict) and p.get("id"):
            item = dict(p)
            item["builtin"] = False
            out.append(item)
    return out


def resolve_provider(cfg: dict, pid: str = None) -> dict:
    s = v3_settings(cfg)
    target = pid or s.get("activeProvider") or "spark-maas"
    for p in all_providers(cfg):
        if p.get("id") == target:
            return p
    return dict(BUILTIN_PROVIDERS[0])


def probe_result_path() -> Path:
    return _sub("probe") / "caps.json"


def get_probes() -> dict:
    return _read_json(probe_result_path(), {}) or {}


def save_probe(pid: str, result: dict) -> bool:
    d = get_probes()
    d[pid] = dict(result, at=_now())
    return _write_json(probe_result_path(), d)


# ─── 3. 脱敏配置 ─────────────────────────────────────────

def _mask(value) -> str:
    s = str(value or "")
    return ("***" + s[-6:]) if len(s) > 10 else ("" if not s else "***")


def sanitize_config(cfg: dict) -> dict:
    """返回给前端的配置：所有密钥字段只留末 6 位与 hasKey 标记。"""
    out = json.loads(json.dumps(cfg, ensure_ascii=False))
    c = out.setdefault("cfg", {})
    if c.get("apiKey"):
        c["apiKey"] = MASK
    c["apiKeyMasked"] = _mask((cfg.get("cfg") or {}).get("apiKey"))
    c["hasApiKey"] = bool((cfg.get("cfg") or {}).get("apiKey"))
    s = out.setdefault("v3", v3_settings(cfg))
    for p in s.get("customProviders") or []:
        if isinstance(p, dict) and p.get("apiKey"):
            p["apiKey"] = MASK
            p["hasApiKey"] = True
    return out


def merge_config(old: dict, incoming: dict) -> dict:
    """保存前端提交的配置：MASK 占位符表示「保持原值」，避免误清空密钥。"""
    merged = json.loads(json.dumps(old, ensure_ascii=False))
    for k, v in (incoming or {}).items():
        if k == "cfg" and isinstance(v, dict):
            c = merged.setdefault("cfg", {})
            for ck, cv in v.items():
                if ck == "apiKey" and cv == MASK:
                    continue
                c[ck] = cv
        elif k == "v3" and isinstance(v, dict):
            s = merged.setdefault("v3", v3_settings(old))
            old_custom = {p.get("id"): p for p in (s.get("customProviders") or []) if isinstance(p, dict)}
            for sk, sv in v.items():
                if sk == "customProviders" and isinstance(sv, list):
                    fixed = []
                    for p in sv:
                        if not isinstance(p, dict):
                            continue
                        q = dict(p)
                        if q.get("apiKey") == MASK:
                            q["apiKey"] = (old_custom.get(q.get("id")) or {}).get("apiKey", "")
                        fixed.append(q)
                    s[sk] = fixed
                else:
                    s[sk] = sv
        else:
            merged[k] = v
    return merged


# ─── 4. 审计哈希链 ───────────────────────────────────────

def _chain_file() -> Path:
    return _sub("audit") / "chain.jsonl"


def _last_hash() -> str:
    p = _chain_file()
    if not p.exists():
        return "0" * 64
    try:
        lines = [x for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
        if not lines:
            return "0" * 64
        return (json.loads(lines[-1]) or {}).get("hash", "0" * 64)
    except Exception:
        return "0" * 64


def audit_append(kind: str, summary: str, meta: dict = None) -> dict:
    prev = _last_hash()
    rec = {"ts": _now(), "kind": kind, "summary": str(summary or "")[:180],
           "meta": meta or {}, "prev": prev}
    payload = json.dumps(rec, ensure_ascii=False, sort_keys=True)
    rec["hash"] = hashlib.sha256((prev + payload).encode("utf-8")).hexdigest()
    try:
        with _chain_file().open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass
    return rec


def audit_records() -> list:
    p = _chain_file()
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def audit_verify() -> dict:
    recs = audit_records()
    prev = "0" * 64
    broken = 0
    for r in recs:
        body = {k: v for k, v in r.items() if k != "hash"}
        calc = hashlib.sha256((prev + json.dumps(body, ensure_ascii=False, sort_keys=True))
                              .encode("utf-8")).hexdigest()
        if r.get("prev") != prev or r.get("hash") != calc:
            broken += 1
        prev = r.get("hash", prev)
    return {"total": len(recs), "broken": broken, "valid": broken == 0,
            "last": prev[:16]}


def audit_stats() -> dict:
    recs = audit_records()
    kinds = {}
    for r in recs:
        kinds[r.get("kind", "?")] = kinds.get(r.get("kind", "?"), 0) + 1
    local = sum(v for k, v in kinds.items() if k.startswith("local"))
    network = sum(v for k, v in kinds.items() if k.startswith("net"))
    return {"total": len(recs), "kinds": kinds, "localCalls": local,
            "networkCalls": network, "verify": audit_verify()}


# ─── 5. 文件快照 ─────────────────────────────────────────

def snapshot_save(target: str, content: str = "") -> dict:
    sid = "%d-%s" % (int(time.time() * 1000), hashlib.sha1(str(target).encode()).hexdigest()[:8])
    rec = {"id": sid, "target": str(target), "at": _now(),
           "sha256": hashlib.sha256((content or "").encode("utf-8", "replace")).hexdigest(),
           "size": len(content or "")}
    p = _sub("snapshots") / (sid + ".json")
    p.write_text(json.dumps({"meta": rec, "content": content or ""}, ensure_ascii=False),
                 encoding="utf-8")
    return rec


def snapshot_list() -> list:
    out = []
    for p in sorted(_sub("snapshots").glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        d = _read_json(p, {}) or {}
        if isinstance(d.get("meta"), dict):
            out.append(d["meta"])
    return out[:80]


def snapshot_restore(sid: str) -> dict:
    if not _safe(sid):
        return {"ok": False, "error": "快照 id 非法"}
    p = _sub("snapshots") / (sid + ".json")
    d = _read_json(p)
    if not isinstance(d, dict) or not d.get("meta"):
        return {"ok": False, "error": "快照不存在"}
    target = Path(d["meta"]["target"])
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(d.get("content") or "", encoding="utf-8")
        audit_append("local.snapshot.restore", "回滚文件 %s" % target.name, {"id": sid})
        return {"ok": True, "target": str(target), "size": len(d.get("content") or "")}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


# ─── 6. 健康检查 ─────────────────────────────────────────

def health(cfg: dict) -> dict:
    """只读本地状态，绝不主动联网（零出域原则）。"""
    s = v3_settings(cfg)
    c = cfg.get("cfg") or {}
    prov = resolve_provider(cfg, s.get("activeProvider"))
    writable = True
    try:
        _sub("sessions")
    except Exception:
        writable = False
    return {
        "version": V3_TAG,
        "time": _now(),
        "storage": str(v3_root()),
        "writable": writable,
        "activeProvider": prov.get("id"),
        "providerLabel": prov.get("label"),
        "model": prov.get("model") or c.get("model"),
        "hasApiKey": bool(c.get("apiKey")) or prov.get("authMode") == "none",
        "sessions": len(list_sessions()),
        "audit": audit_stats(),
        "probes": get_probes(),
        "networkTest": "skipped (zero-egress default; use /api/v3/probe explicitly)",
    }
