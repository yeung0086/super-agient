# Super-Agient

> A local-first, privacy-oriented Windows desktop agent, packaged as a single-file executable (PyInstaller).
> Former names: AI Assistant → Zhiyun → AI.Super Agent → **Super-Agient**.

[中文](#中文说明) · [English](#english)

---

## English

### What it is

A **local-first desktop agent** with 22 built-in skills: long-form writing (proposals, outlines, meeting minutes, research reports), document generation in 8 formats, and parsing/conversion of PDF, DOCX, XLSX, PPTX, HTML and text files.
It also supports **task execution**: the model emits a short JSON instruction and a local whitelist executor performs it, with the full execution trace shown in the UI.
Most capabilities require **no network and no API key** — zero tokens, zero cost.

### Key features

- **Zero-cost local generation**: 11 long-form templates and 8 export formats, fully deterministic and offline.
- **File hub**: upload and parse PDF / DOCX / XLSX / PPTX / web pages / plain text; convert without uploading.
- **Task executor**: `@task {"skill":"file.save",...}` — whitelist validation plus a visible execution trace.
- **Multi-provider architecture**: one OpenAI-compatible layer for several vendors; keys are stored locally only and masked in the UI.
- **stdio MCP bridge**: a Python backend spawns child processes and exposes them over HTTP.
- **Audit trail and snapshots**: sessions, configuration and changes are traceable and reversible.

### Tech stack

Python 3.13 · PyInstaller · zero-build React (UMD) · native WebSocket · stdio MCP · Windows WebView2

### Layout

```
src/     Mainline v3.3.0 sources (launcher33.py, v3_core.py, agent_framework.py,
         filehub.py, skillhub.py, task_engine.py, office_skills.py, docgen.py,
         mcp_stdio.py) and the webdist33 frontend
docs/    00-08 current technical documents (bilingual abstracts; Chinese body)
```

### Quick start

```bash
python src/launcher33.py          # development mode
pyinstaller src/build33.spec      # build a single-file EXE
```

> **Cloud models**: all provider presets are examples only. You must obtain your own account and API key to use any cloud model. Without a key, all local skills, conversions and task execution still work.
> By default no document content leaves your machine.

### License

MIT

---

<a id="中文说明"></a>
## 中文说明

### 是什么

一个**本地优先**的桌面智能体：22 个内置技能（文本/方案/大纲/办公文档生成、PDF/DOCX/XLSX/PPTX 解析与互转、文件保存到指定目录），支持模型下发短 JSON 指令 → 本机白名单执行，界面展示完整执行轨迹。
无网络、无模型调用时也能完成绝大多数写作与格式转换任务（零 token、零费用）。

### 核心特性

- **本机零消耗生成**：方案、大纲、会议纪要、调研报告等 11 类长文模板 + 8 种格式导出，全部本机确定性完成
- **文件枢纽**：PDF / DOCX / XLSX / PPTX / 网页 / 文本上传解析，转换不联网
- **任务执行器**：`@task {"skill":"file.save",...}` 白名单校验 + 执行轨迹展示
- **多 Provider 架构**：OpenAI 兼容协议统一接入多家厂商；密钥只存本机、前端脱敏
- **stdio MCP 桥**：Python 后端 spawn 子进程，HTTP 端点暴露
- **审计链与快照**：会话、配置、变更全程可追溯，支持快照回滚

### 技术栈

Python 3.13 · PyInstaller · React UMD（零构建）· 原生 WebSocket · stdio MCP · Windows WebView2

### 运行

```bash
python src/launcher33.py          # 开发模式
pyinstaller src/build33.spec      # 打包单文件 EXE
```

> **关于云端模型**：源码中的 Provider 预设仅为样例。任何云端能力都需要**使用者自行申请账号并填写自己的 API Key**；未配置时所有本机技能、文件转换与任务执行依旧可用。
> 内置技能与长文模板默认零出域，不上传任何文档内容。

### 许可

MIT
