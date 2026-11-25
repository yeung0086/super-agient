<!-- bilingual: en/zh -->
> **System Logic Specification**
> **English Abstract**: Authoritative overview of the local-first desktop agent: architecture, capability layers, version lineage and document hierarchy.

---

# AI.Super Agent · 系统逻辑说明（唯一现行逻辑文档）

> 梳理日期：2026-11-11 · 更新：2026-11-12（v2.3.0 融合能力并入） · 依据：本目录全部文档、二代源码与已验证的可运行成品 EXE
> 地位：**本文件是现行逻辑的唯一入口**。`docs/01`—`04` 是历史判断与一代权威文档，`docs/05` 是 v3.0 融合升级方案，`docs/archive/` 全部作废，两份 `plans/` 是 9 月升级设想，均不得当现行事实引用。

---

## 1. 一句话结论

这是一个**本地优先、单文件 EXE 的 Windows 桌面 Agent 应用**（AI.Super Agent，曾用名 AI 助手 / 智云）。它不是一个能编译的仓库，而是「文档 + 成品 EXE + 二代源码 + 一代技术文档与逆向材料」的组合体。

**2026-11-12 后的状态**：主线为 **v2.3.0**，成品 `builds/AI.Super-Agent_v2.3.0.exe`（24.86 MB，冒烟 16/16）。相对 v2.2.0 并入三项融合能力：**stdio MCP 桥**（把秒哒等本地 stdio MCP 托管为工具）、**讯飞星火双通道**（OpenAI 兼容 + 原生 WebSocket）、**Skill 安装**（`/api/skills` + `@install`）。v2.2.0 成品保留为回滚点。**一代 v2.1.0.2 实体已下线**：源码与成品 EXE 经备份后移入系统回收站，仅保留技术文档（`docs/03`、`docs/04`）与逆向材料（`reverse/` 三份）。

---

## 2. 它是怎么跑起来的（启动链）

```
双击 builds/AI.Super-Agent_v2.3.0.exe
  → PyInstaller 6.x --onefile --windowed 解包到临时目录（Python 3.13）
  → launcher.py 启动 ThreadingHTTPServer @ 127.0.0.1:随机端口
  → 静态托管内嵌前端 webdist/（React UMD + 原生 ES Module，零构建、零 CDN）
  → 从 config.json 装载 stdio MCP 桥（transport = "stdio-bridge" 的条目按需 spawn）  ← v2.3.0
  → pywebview 弹桌面窗口（缺 WebView2 自动回退默认浏览器）
  → 配置持久化到 %APPDATA%/AI.Super-Agent/config.json
```

- 后端只有 Python **标准库**（`http.server` / `urllib` / `threading` / `socket` / `subprocess`），没有 Web 框架。
- 前端不经过 Vite/TS 编译；React 以 UMD 全局 `React` + `h = React.createElement` 使用，第三方库本地内联，离线可用。
- 双轨推理：云端大模型（DeepSeek / Kimi / 智谱 GLM / 通义 / 豆包 / 讯飞星火 / OpenAI / Ollama，function calling 调工具）不可达时，自动降级到本地规则引擎。

---

## 3. 后端 API（`launcher.py` 的 `SafeHandler`）

| 端点 | 方法 | 作用 | 版本 |
|---|---|---|---|
| `/api/config` | GET / PUT | 读写固定路径配置（厂商 / Key / 模型 / MCP / 主题 / 自定义技能 / 数据源），跨重启持久化 | v2.2.0 |
| `/api/fs` | GET / POST | 本地文件读写、列目录、删除（**无鉴权、无路径白名单**） | v2.2.0 |
| `/api/websearch` | GET | 联网搜索代理，Bing 主用 + DuckDuckGo 兜底，绕开前端 CORS | v2.2.0 |
| `/api/data` | POST | 通用第三方数据 API 代理（东方财富 / 新闻 / 天气等），注入密钥、规避 CORS | v2.2.0 |
| `/api/version` | GET | 返回 `APP_VERSION` | v2.2.0 |
| `/api/office/*` | POST | Word / Excel / PPT / PDF / 文件搜索 / 日历提醒 | **v2.2.0 新增，一代无** |
| `/api/skills` | GET / POST | 列出 / 安装本地技能包（落盘到 `app_data/skills/` 并并入 `customSkills`） | **v2.3.0 新增** |
| `/api/mcp/stdio/servers` | GET | 已托管的 stdio MCP 服务器清单 | **v2.3.0 新增** |
| `/api/mcp/stdio/list?server=ID` | POST | 列出该 stdio MCP 的工具 | **v2.3.0 新增** |
| `/api/mcp/stdio/call?server=ID` | POST | 调用该 stdio MCP 的工具（body `{name, arguments}`） | **v2.3.0 新增** |

安全头与 4 MB 请求体上限在 `SafeHandler` 中统一处理；CSP 为宽松的 `default-src * 'unsafe-inline' 'unsafe-eval'`（与「零 eval」承诺冲突，见 §7）。

---

## 4. 前端结构与能力

| 文件 | v2.3.0（现行主线） | 职责 |
|---|---|---|
| `js/agent.js` | **1743 行 / 84 KB** | Agent 引擎：`@` 命令、记忆、Skills、MCP（HTTP + stdio 桥）、云端工具规格、流式响应、`@office`、`@install` |
| `js/app.js` | 50.9 KB | React 组件与 UI 编排（含讯飞字段、MCP 三通道表单） |
| `js/ui.js` | 10.3 KB | Markdown / 工具卡片 / 菜单 |
| `js/providers/iflytek.js` | **168 行 / 8 KB** | 讯飞星火原生 WebSocket 适配器（v2.3.0 新增，纯 JS HMAC-SHA256） |
| `css/styles.css` `tokens.css` | 24.3 / 2.2 KB | 样式与设计令牌 |
| `vendor/react*.js` | 138 KB | React / ReactDOM UMD，本地内联 |

命令：`@calc` `@remember` `@recall` `@list` `@time` `@web` `@skills` `@skill` `@mcp` `@help`，v2.2.0 增 `@office` 系，v2.3.0 增 `@install`。

---

## 5. 一代已下线，二代为唯一主线（本次整理核心结论）

| 证据 | v2.1.0.2（已下线，仅留文档） | v2.3.0（现行主线，可运行） |
|---|---|---|
| 源码目录 | `src/v2.1.0.2-frozen/` **已于 2026-11-11 删除** | `src/v2.2.0-wip/launcher.py`（1126 行）+ `mcp_stdio.py`（288 行） |
| 启动器源码 | 仅 `reverse/launcher_dis.txt` 反汇编（7629 行） | 完整 `launcher.py` |
| 前端引擎 | 无（仅文档描述） | `webdist/`（agent.js 1743 行 + providers/iflytek.js 168 行） |
| 成品 EXE | 已下线，备份于 `D:\_workbuddy_清理备份_20261111\AI助手_一代下线_20261111\`，可回收站还原 | `builds/AI.Super-Agent_v2.3.0.exe`（24.86 MB，冒烟 16/16），v2.2.0 保留为回滚点 |
| 版本号 | 反汇编 / launcher.pyc 内含 `2.1.0.2` | `launcher.py` 明写 `APP_VERSION = "2.3.0"` |

> 结论：当前工程以 v2.2.0 为唯一主线。**一代的迭代价值仅保留在文档与逆向材料中**——若需恢复一代，从回收站或备份目录取回实体后参照 `docs/03`、`docs/04` 与 `reverse/` 三份材料继续。两代 UI 骨架（index.html / ui.js / css / React vendor）相同，差异只在引擎与编排（office 能力）。

---

## 6. 文档体系与权威判定

| 层 | 文件 | 定性 |
|---|---|---|
| 现行 | `README.md`、本文件 | 唯一权威入口与逻辑 |
| 融合方案 | `05-AI助手v3.0融合升级技术文档_2026-11-12.md` | 秒哒对比、stdio 桥、讯飞双通道、模型矩阵、v3.0 路线与风险 |
| 一代权威工程文档 | `03-development-delivery-v2.1.0.2.md`、`04-feasibility-baseline.md` | 描述一代真实产物，迭代升级一代时的主要参考 |
| 历史判断（8-25） | `01-project-review.md`、`02-test-report-and-upgrade.md` | 结论仍有效，但「源码不在本目录 / 无法复核」已被 11-11 整理推翻 |
| 本次下线记录 | `一代下线记录_2026-11-11.txt` | 删除清单 / 哈希 / 备份 / 回收站还原 / 迭代指引 |
| 升级设想（9-27） | `plans/` 两份 HTML | 针对 1292 行 `agent.js` 的分析与方案，**未实施** |
| 作废 | `archive/` 7 份 | 智云命名、Vite+TS 架构、`54/54` 声明，与真实产物冲突 |

早期 v1—v4 文档通篇写 Vite + React + TypeScript（`src/agent.ts`），**与真实的零构建纯 JS 产物不符**；照着改 `src/` 不会生效。

---

## 7. 已知问题与诚实边界

1. `@calc` 仍用 `new Function`（v2.2.0 agent.js 中段），文档承诺的「递归下降 Parser / 零 eval」**从未落地**；`2**10` 会被字符白名单放行求值为 1024。
2. 技能安装**已有两条路径**（v2.3.0）：UI/`@install` 命令 → `POST /api/skills` 落盘；但**模型仍不会自己"识别并安装"**——没有"从对话里自动装技能"的分支，安装是显式动作。
3. 功能断言数字（54/54、89 断言）指向不同测试集，且目录内**无任何测试脚本**可复现，一律不得当事实引用。
4. `/api/fs` 无鉴权、EXE 无代码签名、CSP 极宽松——均为已知限制；**MCP 已支持 HTTP + stdio 桥**（v2.3.0），但仍缺 SSE/Streamable 完整实现与工具级开关。
5. GUI 端到端与真实模型对话质量**仍未验证**；现有结论来自静态代码核验 + 本地 HTTP 冒烟（源码 18/18、打包产物 16/16）。
6. **一代 v2.1.0.2 实体已于 2026-11-11 下线**，当前工程不含任何一代可运行实体。

---

## 8. 变更记录

### 2026-11-12（v2.3.0 融合升级）

- **stdio MCP 桥**：新增 `mcp_stdio.py`（288 行）——托管 stdio 子进程、行式 JSON-RPC、per-server 串行锁、崩溃隔离；`launcher.py` 加 3 条路由（`servers` / `list` / `call`）与启动装载。实测把秒哒 local-app-forge 作为子进程驱动：8 工具可列、`forge_plan`/`generate`/`qa` 可调。
- **讯飞双通道**：`agent.js` 加 `spark` 预设（OpenAI 兼容，支持 tools）与 `iflytek` 原生分支；新增 `providers/iflytek.js`（纯 JS SHA-256/HMAC-SHA256、APPID+APIKey+APISecret、流式 `onDelta`、domain 映射；**无 function calling**）。设置面板补 APPID/Secret 字段。
- **Skill 安装**：`/api/skills` GET/POST + `@install` 命令 + 启动 `loadLocalSkills()` 扫描；技能落盘到 `app_data/skills/`。
- **打包与验证**：版本升 `2.3.0`；`build.spec` 显式 `hiddenimports: ['mcp_stdio']`；新增 `tools/smoke_exe.py`（16 项，检查冻结模块、provider 进包与「EXE→stdio 桥→秒哒」整链）。结果：秒哒自测 37/37、桥 5/5、后端适配 5/5、源码冒烟 18/18、产物冒烟 16/16。产物 `builds/AI.Super-Agent_v2.3.0.exe`（24.86 MB），v2.2.0 保留回滚。

### 2026-11-11（整理与一代下线）

- **验证二代**：`tools/smoke_v2.2.0.py` 源码冒烟 16/16（服务起得来、8 个前端资源齐全、`/api/version`=2.2.0、`/api/office/*` 路由在、目录穿越被拦）；在隔离 venv（Python 3.13 + PyInstaller 6.22.3 + 全套依赖）实际打包出 `builds/AI.Super-Agent_v2.2.0.exe`，并对打包产物再次冒烟 7/7。
- **修复 build.spec**：原 spec 用 PyInstaller 4.x 旧 API（`block_cipher` / `cipher=` / `a.zipped_data` / `win_no_prefer_redirects` / `win_private_assemblies`），在 6.x 下直接 TypeError 无法打包；已改为 6.x 兼容写法（office / GUI 依赖改为可选，缺库也可打包、运行时降级），并实测通过。
- **删除一代实体**：`src/v2.1.0.2-frozen/`（9 文件）+ `builds/AI.Super-Agent.exe`（一代）。删除前全量备份到 `D:\_workbuddy_清理备份_20261111\AI助手_一代下线_20261111\`（10 文件、哈希已校验），再经系统回收站删除（可还原）。**逆向三份按用户要求全留**（`reverse/launcher.pyc`、`launcher_dis.txt`、`PYZ模块清单.txt`）。
- **补工具与记录**：新增 `tools/smoke_v2.2.0.py`（运行时冒烟）、`docs/一代下线记录_2026-11-11.txt`（下线清单与迭代指引）；`tools/verify.py` 改为「二代主线 + 一代归档」校验。

---

## 9. 整理后结构

```
AI助手/
├── README.md                  唯一权威入口
├── MANIFEST.md                逐文件清单与来源
├── docs/                      00 逻辑 / 01-04 历史 / 05 融合方案 / 一代下线记录 / plans / archive
├── src/
│   └── v2.2.0-wip/            现行主线（launcher.py + mcp_stdio.py + webdist/，已验证可打包）
├── builds/                    v2.3.0 现行成品 + v2.2.0 回滚点
├── reverse/                   反汇编、字节码、PYZ 模块清单（一代逆向材料，三份全留）
└── tools/                    verify.py（体检）/ smoke_v2.2.0.py（源码冒烟）/ smoke_exe.py（产物冒烟）
```

体检：`python tools/verify.py`。改源码后验证能起服务：`python tools/smoke_v2.2.0.py`；打包后验证产物：`python tools/smoke_exe.py`。重新打包用 `src/v2.2.0-wip/build.spec`（要求 Python 3.13 + PyInstaller 6.x + docx/openpyxl/pptx/PyPDF2/Pillow/webview 等依赖；装依赖时若遇 `IncompleteRead`，加 `--no-cache-dir`）。

---

*本说明只依据本机文件实际内容核对生成；凡「实测通过」类数字均标注为本次冒烟结果。未上传任何本地内容、未将本地内容作为联网检索词。*
