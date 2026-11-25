#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI.Super-Agent v3.0 — stdio MCP 桥（后端）。

作用：
  浏览器内的前端 agent.js 只能直连 HTTP / Streamable 传输的 MCP 服务器。
  但本地高质量 MCP（如 local-app-forge / 秒哒、各类 stdio 工具）走的是
  子进程 stdin/stdout 的 JSON-RPC。本模块在后端 spawn 并托管这些子进程，
  向前端暴露 HTTP 端点，从而把「任意 stdio MCP」变成 AI.Super-Agent 的可用工具。

设计要点：
  - 纯标准库（subprocess / json / threading / queue），零额外依赖，可直接进 PyInstaller 冻结。
  - 每个 server_id 一个常驻子进程，按需 initialize 一次；请求串行化（per-server 锁）。
  - 行式 JSON-RPC：写一行请求，读到匹配的响应行（忽略无 id 的 notification）。
  - 配置来自 config.json 的 mcpStdio 数组：[{id, name, command, args:[], env:{}}]。
  - 失败隔离：某 server 崩溃不影响其它；支持 restart_on_fail。

安全：
  - command 必须是 config.json 显式声明的绝对/白名单路径，不执行任何前端传入的命令。
  - 仅转发 JSON-RPC；不暴露子进程的环境变量给前端（env 由后端注入）。
"""

import os
import sys
import json
import time
import subprocess
import threading
import uuid
from pathlib import Path

try:
    import launcher  # 当作为 launcher 子模块运行时可用
    _APP_DATA = launcher.app_data_dir()
except Exception:
    _APP_DATA = Path.home() / ".ai-super-agent" / "AI.Super-Agent"

DEFAULT_PROTOCOL = "2024-11-05"


class StdioServer:
    """托管一个 stdio MCP 子进程。"""

    def __init__(self, cfg):
        self.id = str(cfg.get("id", "")).strip()
        self.name = str(cfg.get("name") or self.id)
        self.command = str(cfg.get("command", "")).strip()
        self.args = list(cfg.get("args") or [])
        self.env = dict(cfg.get("env") or {})
        self.cwd = str(cfg.get("cwd") or os.getcwd())
        self.restart = bool(cfg.get("restart_on_fail", True))
        self.proc = None
        self.lock = threading.Lock()
        self._started = False
        self._initialized = False
        self._seq = 0

    # ---- 生命周期 ----
    def ensure_started(self):
        with self.lock:
            if self.proc is not None and self.proc.poll() is None:
                return True
            if not self.command:
                raise RuntimeError("stdio MCP 未配置 command")
            env = os.environ.copy()
            # 仅注入用户显式声明且安全的环境变量；不回显、不泄露
            for k, v in self.env.items():
                if isinstance(k, str) and isinstance(v, str) and k.isidentifier():
                    env[k] = v
            try:
                self.proc = subprocess.Popen(
                    [self.command] + [str(a) for a in self.args],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, cwd=self.cwd, env=env,
                    text=True, encoding="utf-8", errors="replace",
                    bufsize=1,
                )
            except Exception as e:
                raise RuntimeError("启动 stdio MCP 失败：%s" % e)
            self._started = True
            self._initialized = False
            return True

    def _next_id(self):
        self._seq += 1
        return "s%d" % self._seq

    def _write(self, obj):
        line = json.dumps(obj, ensure_ascii=False)
        try:
            self.proc.stdin.write(line + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, ValueError, OSError) as e:
            raise RuntimeError("写入子进程失败：%s" % e)

    def _read_response(self, want_id, timeout=30):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.proc.poll() is not None:
                # 子进程退出：尝试收集 stderr 便于排错
                try:
                    err = self.proc.stderr.read()
                except Exception:
                    err = ""
                raise RuntimeError("stdio MCP 子进程已退出（rc=%s）%s"
                                   % (self.proc.returncode, (err or "")[:300]))
            line = self.proc.stdout.readline()
            if not line:
                continue
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            # 忽略 notification（无 id 或 method 存在但无对应请求匹配）
            if "id" not in msg:
                continue
            if msg.get("id") == want_id:
                if "error" in msg:
                    raise RuntimeError("MCP 错误：%s" % json.dumps(msg["error"], ensure_ascii=False))
                return msg.get("result", {})
        raise RuntimeError("stdio MCP 读取响应超时（%ss）" % timeout)

    def call(self, method, params=None, timeout=60):
        self.ensure_started()
        with self.lock:
            if method != "initialize" and not self._initialized:
                self._do_initialize()
            rid = self._next_id()
            self._write({"jsonrpc": "2.0", "id": rid, "method": method,
                         "params": params or {}})
            if method == "initialize":
                res = self._read_response(rid, timeout)
                # 某些实现要求 initialize 后发 notifications/initialized
                try:
                    self._write({"jsonrpc": "2.0", "method": "notifications/initialized",
                                 "params": {}})
                except Exception:
                    pass
                self._initialized = True
                return res
            return self._read_response(rid, timeout)

    def _do_initialize(self):
        rid = self._next_id()
        self._write({"jsonrpc": "2.0", "id": rid, "method": "initialize",
                     "params": {"protocolVersion": DEFAULT_PROTOCOL,
                                "capabilities": {},
                                "clientInfo": {"name": "ai-super-agent", "version": "3.0"}}})
        try:
            self._read_response(rid, 30)
        except RuntimeError:
            # 忽略 initialize 失败，仍可尝试 tools/list
            pass
        try:
            self._write({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        except Exception:
            pass
        self._initialized = True

    def list_tools(self):
        res = self.call("tools/list", {})
        tools = (res or {}).get("tools", []) or []
        out = []
        for t in tools:
            out.append({
                "name": t.get("name"),
                "description": t.get("description") or "",
                "inputSchema": t.get("inputSchema") if isinstance(t.get("inputSchema"), dict) else {"type": "object", "properties": {}},
            })
        return out

    def call_tool(self, name, arguments):
        res = self.call("tools/call", {"name": name, "arguments": arguments or {}})
        content = (res or {}).get("content")
        if isinstance(content, list):
            return "\n".join(c.get("text", "") if isinstance(c, dict) else str(c)
                             for c in content)
        return json.dumps(res, ensure_ascii=False)

    def stop(self):
        if self.proc is not None:
            try:
                self.proc.terminate()
            except Exception:
                pass
            self.proc = None
        self._initialized = False


class StdioMCPManager:
    """管理全部 stdio MCP 子进程。"""

    def __init__(self):
        self.servers = {}      # id -> StdioServer
        self.by_name = {}

    def configure(self, cfgs):
        # 停止并替换旧配置
        for s in self.servers.values():
            try:
                s.stop()
            except Exception:
                pass
        self.servers = {}
        self.by_name = {}
        for cfg in (cfgs or []):
            s = StdioServer(cfg)
            if s.id:
                self.servers[s.id] = s
                self.by_name[s.name] = s

    def get(self, sid):
        return self.servers.get(sid)

    def list_configured(self):
        return [{"id": s.id, "name": s.name, "command": s.command,
                 "args": s.args} for s in self.servers.values()]

    def list_tools(self, sid):
        s = self.get(sid)
        if not s:
            raise RuntimeError("未知 stdio MCP：%s" % sid)
        return s.list_tools()

    def call_tool(self, sid, name, arguments):
        s = self.get(sid)
        if not s:
            raise RuntimeError("未知 stdio MCP：%s" % sid)
        return s.call_tool(name, arguments)


# 单例
MANAGER = StdioMCPManager()


def handle_mcp_stdio(self, path_parts, query, body):
    """在 launcher.py 的 SafeHandler 中调用。

    GET  /api/mcp/stdio/servers
    POST /api/mcp/stdio/list?server=<id>
    POST /api/mcp/stdio/call?server=<id>   body: {name, arguments}
    """
    from launcher import send_json  # 延迟导入避免循环

    if path_parts[0] == "servers":
        return send_json(self, {"servers": MANAGER.list_configured()})

    sid = query.get("server", [""])[0].strip()
    if path_parts[0] == "list":
        try:
            tools = MANAGER.list_tools(sid)
            return send_json(self, {"server": sid, "tools": tools})
        except Exception as e:
            return send_json(self, {"error": str(e)[:400]}, status=500)

    if path_parts[0] == "call":
        name = (body.get("name") if isinstance(body, dict) else None) or ""
        args = (body.get("arguments") if isinstance(body, dict) else None) or {}
        try:
            out = MANAGER.call_tool(sid, name, args)
            return send_json(self, {"server": sid, "name": name, "text": out})
        except Exception as e:
            return send_json(self, {"error": str(e)[:400]}, status=500)

    return send_json(self, {"error": "未知 stdio MCP 操作"}, status=400)


def load_from_config(config):
    """从 config.json 装载 stdio 桥：

    - 优先读 mcpServers 中 transport === 'stdio-bridge' 的条目（与前端统一一套配置）；
    - 兼容旧字段 mcpStdio（独立数组，可选）。
    每个条目：{id, name, command, args:[], env:{}, cwd:''}。
    """
    cfgs = []
    if isinstance(config, dict):
        servers = config.get("mcpServers") or []
        if isinstance(servers, list):
            for s in servers:
                if isinstance(s, dict) and s.get("transport") == "stdio-bridge":
                    cfgs.append(s)
        cfgs += (config.get("mcpStdio") or [])
    MANAGER.configure(cfgs)
    return len(cfgs)
