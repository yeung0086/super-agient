<!-- bilingual: en/zh -->
> **Development Delivery Document v2.1.0.2**
> **English Abstract**: Engineering specification of the first-generation product: modules, API contracts, configuration and delivery status.

---

# AI.Super-Agent 工程技术开发文档（基础可行性版）

> 版本基线：**v2.1.0.2**　|　生成日期：2026-08-01　|　形态：Windows 单文件 EXE（PyInstaller 6.20.0 `--onefile --windowed`）
> 本文档由项目迭代历史「去噪」整理而成，面向**后续升级开发**，提供架构、模块、扩展点、构建验证与可行性路线，不含调试过程噪音。

---

## 1. 文档目的与适用范围

- **目的**：为后续升级（新增能力、替换后端、重构 UI、接入新数据源等）提供一份可信、结构化、可直接开工的基础文档。
- **适用对象**：负责维护 / 升级本应用的开发者。
- **基线代码位置**：`D:\ai助手\agent-app\`（源码）；交付物在 `C:\Users\Administrator\Desktop\软件开发工程\量化系统\`。
- **文档性质**：可行性 + 技术基线。不替代需求文档，但是升级前的「地形图」。

---

## 2. 系统概览

AI.Super-Agent 是一个**本地优先、注重隐私**的桌面 Agent 应用：

- 前端为零构建静态站点（React UMD + 原生 ES Module），由 Python 标准库 `http.server` 在 `127.0.0.1` 随机端口本地托管；
- 用 `pywebview` 弹出桌面窗口；若系统缺 WebView2 则自动回退浏览器；
- 内置「本地引擎（规则 + 知识库 + 记忆）」与「云端大模型（function calling 调用工具）」双轨，云端不可达自动降级到本地；
- 提供 Skills、MCP 客户端、联网搜索、本地文件读写、可配置数据源 API（东方财富 / 新闻 / 天气等）等扩展能力。

### 2.1 架构图（逻辑）

```
┌──────────────────────────────────────────────────────────────┐
│                        用户（Windows 桌面）                    │
└───────────────────────────┬──────────────────────────────────┘
                            │ 双击 AI.Super-Agent.exe
                            ▼
┌──────────────────────────────────────────────────────────────┐
│  AI.Super-Agent.exe（PyInstaller 单文件）                      │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ launcher.py（Python 标准库）                               │ │
│  │  • ThreadingHTTPServer @127.0.0.1:随机端口                │ │
│  │  • SafeHandler：/api/* 本地代理                           │ │
│  │      ├─ /api/config   配置读写（持久化）                  │ │
│  │      ├─ /api/fs        本地文件读写/列目录                │ │
│  │      ├─ /api/websearch 联网搜索（Bing 主+DDG 兜底）       │ │
│  │      ├─ /api/data      通用第三方数据 API 代理            │ │
│  │      └─ /api/version   版本号                             │ │
│  │  • 配置 dir：%APPDATA%/AI.Super-Agent/config.json         │ │
│  └─────────────────────────────────────────────────────────┘ │
│                            │ 托管                              │
│                            ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ webdist/（冻结的前端，源自 webroot/）                     │ │
│  │  index.html                                              │ │
│  │  css/styles.css                                          │ │
│  │  js/agent.js  ← Agent 引擎（纯 JS，无框架运行时依赖）     │ │
│  │  js/app.js    ← React 组件/UI 编排                        │ │
│  │  js/ui.js     ← 通用 UI 组件（Markdown/工具卡片/菜单）    │ │
│  │  vendor/      ← React UMD 等第三方（本地内联，免联网）    │ │
│  └─────────────────────────────────────────────────────────┘ │
│                            │ 弹窗                              │
│                            ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ pywebview（→ 系统 WebView2） 或 回退默认浏览器            │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
         │                          │
   云端大模型 API（可选）      第三方数据 API（可选，经 /api/data 代理）
```

---

## 3. 技术栈

| 层 | 技术 | 说明 |
|---|---|---|
| 前端框架 | React 18（UMD 全局 `React` + `h = React.createElement`） | 不引入打包器；用原生 ES Module（`type="module"`） |
| 前端语言 | 纯 JavaScript（ES2020+） | 无 TypeScript 运行时（仓库含 `src/` TS 源码但**未参与构建**） |
| 后端 | Python 3.13（标准库） | `http.server`、`urllib`、`threading`，零第三方 Web 依赖 |
| 窗口 | `pywebview` | 依赖系统 WebView2；缺失回退浏览器 |
| 打包 | PyInstaller 6.20.0 | `--onefile --windowed`，前端以 `--add-data webroot;webdist` 冻结 |
| 测试 | Node 22（`node --test`）、Python `unittest`/`urllib` | 单测 + 冒烟 |
| 持久化 | 本地 JSON 文件 | `%APPDATA%/AI.Super-Agent/config.json` |

> **重要约束**：前端**零构建**。所有 `js/*.js` 通过 `<script type="module">` 直接加载，修改即生效（开发时把 `webroot` 当静态目录起一个 HTTP 服务即可预览）。源码仓库里的 `src/*.tsx` 是「参考/归档」性质，**不是构建入口**，升级时不要误改 `src/` 而忽略了真正生效的 `webroot/js/`。

---

## 4. 目录结构与关键文件

```
D:\ai助手\agent-app\
├─ webroot/                      # 真正生效的前端（构建冻结源）
│  ├─ index.html                 # 入口，<title>AI.Super-Agent</title>
│  ├─ css/styles.css             # 全部样式（含响应式 @media max-width:900px）
│  └─ js/
│     ├─ agent.js   (1292 行)     # Agent 引擎：命令/记忆/Skills/MCP/数据API/云端/流式
│     ├─ app.js     (775 行)      # React 组件：侧边栏/设置页/对话流/右键菜单/版本
│     └─ ui.js      (314 行)      # 通用组件：Markdown/ToolCard/ContextMenu/copyText
├─ build_exe/
│  ├─ launcher.py                # 后端 + 打包入口（最关键文件）
│  ├─ version.txt                # 版本信息资源（filevers/ProductVersion）
│  ├─ smoke_test.py              # 端到端冒烟（AGENT_EXE_TEST=1 起服务后 urllib 校验）
│  ├─ verify_data_proxy.py       # 数据代理连通性验证（针对可达 host）
│  ├─ README.txt / 版本说明.md / update.json  # 用户文档
│  └─ _distNN/                   # 历次构建产物（交付用 _dist14 → AI.Super-Agent.exe）
├─ test/
│  └─ agent.test.mjs             # Node 单测（89 断言，覆盖引擎全链路）
└─ src/ (tsx)                    # 参考源码，非构建入口（勿误改）
```

---

## 5. 后端模块（launcher.py）

### 5.1 启动与窗口
- `resource_path(rel)`：PyInstaller 冻结后用 `sys._MEIPASS`，开发时回退脚本目录；前端目录固定为 `webdist`（构建时 `webroot` → `webdist`）。
- `serve(webroot)`：`ThreadingHTTPServer(("127.0.0.1", 0))`，端口随机。
- `main()`：先 `serve`；若环境变量 `AGENT_EXE_TEST=1` 则把 URL 写入 `AGENT_EXE_SMOKE_FILE` 后进入空转（供冒烟测试探测）；否则 `webview.create_window("AI.Super-Agent v{APP_VERSION}", ...)` 并 `webview.start()`；任何异常回退 `webbrowser.open(url)`。

### 5.2 配置持久化
- 路径：`CONFIG_PATH = %APPDATA%/AI.Super-Agent/config.json`。
- `load_config()`：新目录优先；**首次运行自动迁移旧版「智云」目录的 config.json**（更名不丢配置）。
- `save_config(obj)`：原子性不强，但够用。
- HTTP：`GET /api/config` 读、`PUT /api/config` 写（注意 `do_PUT = do_POST`，前端用 PUT 语义）。

### 5.3 本地文件代理 `/api/fs`
- `GET ?op=list&path=...`：列目录；`GET ?path=...`：读文件（**单文件上限 4MB**，超限 413）。
- `POST ?path=...`：body 为原始内容，写入文件（父目录自动创建）。
- 用户明确要求「不设安全限制」，故无路径白名单；升级若面向多用户需补鉴权。

### 5.4 联网搜索 `/api/websearch?q=`
- `websearch(query)`：**Bing 主用 + DuckDuckGo HTML/Lite 兜底**（DuckDuckGo 在中国大陆被封锁，故 Bing 优先）。
- 三后端并行线程，总硬上限 **15s**，任一成功即按优先级（bing→ddg_html→ddg_lite）返回。
- 解析器：`parse_bing()`（解析 `b_algo` 结果块）、`parse_ddg()`（DDG html/lite 两种结构）。
- 错误可诊断：全失败时返回各后端具体原因（超时/被反爬），而非笼统「未知错误」。
- 设计备注：百度（返回验证页）、搜狗（JS 渲染、服务端无结果）不可靠，未纳入；如需更稳可接入 SerpAPI / Brave / Bing API 作为可配置后端。

### 5.5 数据源 API 通用代理 `/api/data`（POST）
- 前端把**完整接口规范** POST 给后端，后端注入密钥后代理请求，规避浏览器 CORS 与密钥暴露。
- `data_fetch(spec)` 字段：`baseUrl / method / query(已编码) / authType(none|query|header|bearer) / authParam / apiKey / headers(JSON 字符串或 dict)`。
- 鉴权注入：
  - `query`：`baseUrl?authParam=apiKey`（URL 参数）
  - `header`：`headers[authParam] = apiKey`
  - `bearer`：`Authorization: Bearer apiKey`
- 重试：**连接层异常重试 3 次**（0.6/1.2/1.8s 退避）；HTTPError（401/404 等）**不重试**直接返回。
- 返回：JSON 内容识别后 `{url, data}`，否则 `{url, text(前 20k)}`，或 `{error}`。

### 5.6 版本端点 `/api/version`
- `GET` 返回 `{"version": APP_VERSION}`，供前端「关于」页与诊断使用。

### 5.7 安全头
- `SafeHandler.end_headers` 注入极宽松 CSP（`default-src * 'unsafe-inline' 'unsafe-eval' data: blob:; connect-src *; ...`），用户要求「不设安全限制」。升级若上云需收紧。

---

## 6. 前端引擎（agent.js）

纯 JS Agent 引擎，**所有能力以函数导出**，便于单测（见第 10 节）。

### 6.1 命令与调度
- `executeCommand(text, store)` / `executeCommandAsync(text, store)`：解析 `@` 命令。
- 命令清单：`@calc @remember @recall @list @time @help @skills @skill @mcp @web @file @data`。

### 6.2 记忆系统
- `ruleExtract(user, assistant)`：从对话抽取事实候选；`persistMemories()` 写入；`retrieveMemories(query, topK)`：检索；`memoryContextBlock()`：注入系统提示。
- 存储：内存 Map + `localStorage` + 远程 config（经 `/api/config`）。

### 6.3 Skills（本地技能）
- `SKILLS` 内置：uuid / base64 / json / epoch / hash。
- `listSkills() / installSkill(def) / loadCustomSkills(list) / exportCustomSkills()`：支持运行时安装/导出自定义技能（`bodyOf()` 存原函数体字符串，`new Function` 恢复，规避 `toString()` 换行问题）。
- 云端暴露为 `skill_<id>` 工具。

### 6.4 MCP 客户端
- 仅支持 **HTTP / Streamable** 传输（`describeMcpServers` / `refreshMcpSpecs`）。
- `_mcpSpecsCache`：缓存 spec 避免每轮对话网络探测（降延迟）。
- `refreshMcpSpecs()` 在初始化时调用；工具随 MCP 服务器动态出现。
- **限制**：stdio MCP 需 Python 桥接，当前未做。

### 6.5 数据源 API（对应后端 §5.5）
- `DATA_API_PRESETS`（6 个内置预设）：
  1. `eastmoney` 东方财富·行情（`push2…/ulist.np/get`，带 `Referer` 头，secid 查行情）
  2. `eastmoney_search` 代码搜索（`searchapi.eastmoney.com`）
  3. `eastmoney_rank` 涨幅榜（`clist/get`）
  4. `eastmoney_trends` 分时（`stock/trends2/get`）
  5. `newsapi` 新闻（需 apiKey，query 鉴权）
  6. `openweather` 天气（需 apiKey，query 鉴权）
- `buildDataQuery(api, query, params)`：把模板里 `{query}` / `{参数名}` 替换为 URL 编码值。
- `dataApiCall(id, query, params)`：查已配置 API → 拼装 spec → `POST /api/data` → 取 `data`/`text`。
- 云端暴露为 `data_<id>` 工具（每个已配置数据源一个）。

### 6.6 云端大模型接入
- `PROVIDER_PRESETS`：DeepSeek / Kimi / 智谱 GLM / 通义 Qwen / 豆包 / OpenAI /  – 含预设 Base URL 与模型列表。
- `baseUrlFor(cfg)`：按需补 `/v1`（仅调用时归一化，不篡改用户配置）。
- `callCloud(cfg, messages, systemContent)`：纯聊天；`runCloud()`：带 tools 的 function calling，失败时**自动以纯聊天重试一次**，仍失败才降级本地。
- `getCloudToolSpecs()`：汇总所有云端工具——`skill_*`、`data_*`、MCP 缓存工具、`web_search`、`file_read/write/list`。
- `runToolByName(name, argsJson)`：本地分发云端工具调用。

### 6.7 流式与响应体验优化
- `postChatStream(cfg, sys, messages, tools, onDelta)`：基于 `fetch` + `ReadableStream` 的流式增量渲染。
- `runCloud()`：每轮先 `resetStream()`（清空再渲染），工具调用前 `onToken('', {status:'⚙ 正在调用工具…'})`。
- `runAgent(text, history, cfg, store, onToken)`：统一入口，本地/云端分流，`onToken(delta, meta)` 的 `meta.reset` / `meta.status` 由 UI 处理。

### 6.8 联网与文件工具
- `webSearch(query)`：`fetch('/api/websearch?q=...')`。
- `fileRead/fileWrite/fileList(path[, content])`：经 `/api/fs`。

---

## 7. 前端 UI（app.js / ui.js）

- **侧边栏**：`sbSection(key, icon, title, count, body, badge)` 可折叠卡片（品牌头 + 新对话/设置 + 快捷指令 + 数据 + 技能 + MCP + 连接状态灯）；状态 `sbOpen`。
- **设置页 tabs**：`model`（厂商/Key/模型）、`about`（版本/能力说明）、`data`（数据源 API）、`skills`（技能）、`mcp`（MCP 服务器）。
- **右键菜单**：`ui.js` 的 `ContextMenu`；输入区右键提供 剪切/复制/粘贴/全选/撤销/清空输入（`pasteIntoFocused()` 保持焦点）。
- **版本可见性**：挂载时 `fetch('/api/version')` → `appVersion` state → 「关于」页与窗口标题均显示 `v2.1.0.2`，便于确认运行的是哪个构建。
- **样式**：`styles.css` 含卡片/标签/图标按钮动画、`.stream-status` 脉冲、响应式 `@media (max-width:900px)`。

---

## 8. 配置 Schema（%APPDATA%/AI.Super-Agent/config.json）

```jsonc
{
  "baseUrl": "https://api.deepseek.com/v1",   // 厂商 API Base（可含 /v1）
  "apiKey": "sk-xxx",                          // 云端 Key（自填，不外传）
  "model": "deepseek-chat",                   // 模型名
  "theme": "light",                           // light | dark
  "customSkills": [ { "id": "...", "label": "...", "code": "return ..." } ],
  "mcpServers": [ { "name": "...", "url": "https://...", "headers": "{}" } ],
  "dataApis": [                               // 已配置的数据源 API（来自预设或自定义）
    { "id": "eastmoney", "label": "东方财富·行情", "baseUrl": "...", "method": "GET",
      "authType": "none", "params": "secids={query}&...", "headers": "{\"Referer\":\"...\"}" }
  ]
}
```
> 旧版「智云」配置首次启动自动迁移；字段缺失时引擎有合理默认。

---

## 9. 构建与打包流水线

### 9.1 命令（每次用**全新**目录，避免覆盖锁）
```bat
cd build_exe
python -m PyInstaller ^
  --onefile --windowed ^
  --name "AI.Super-Agent" ^
  --distpath "..\..\build_exe\_distNN" ^
  --workpath "..\..\build_exe\_workNN" ^
  --specpath "..\..\build_exe\_specNN" ^
  --add-data "..\..\webroot;webdist" ^
  --hidden-import webview ^
  --version-file "..\..\build_exe\version.txt" ^
  --icon "..\..\build_exe\app.ico" ^
  "..\..\build_exe\launcher.py"
```
**铁律**（沙箱实测踩坑）：
1. **每次用全新、不存在的 `_distNN/_specNN/_workNN`**——PyInstaller 覆盖旧 exe 时若被占用会构建失败。
2. `--add-data/--version-file/--icon` 一律用**绝对路径**（相对路径会按 specpath 解析导致路径翻倍）。
3. 单文件 exe 在 `--windowed` 下**无控制台 stdout**；冒烟靠「启动器把 URL 写文件」探测，而非读 stdout。

### 9.2 版本管理
- `version.txt`：`filevers` / `FileVersion` / `ProductVersion` 三者同步（如 `(2,1,0,2)` / `2.1.0.2`）。
- `launcher.py` 顶部 `APP_VERSION` 与 `version.txt` 保持一致（窗口标题与 `/api/version` 取自前者）。
- 交付前计算 SHA256 写入 `update.json`，便于校验完整性。

### 9.3 交付
- 成品：`量化系统\AI.Super-Agent.exe` + `README.txt` + `版本说明.md` + `update.json`。
- 复制前若遇「Device or resource busy」：先 `taskkill /F /IM "AI.Super-Agent.exe"` 清掉残留进程（运行中 exe 会锁住自身映像），再复制。

---

## 10. 测试与验证

### 10.1 单元测试（Node）
- `test/agent.test.mjs`，`node --test`，**89 断言全通过**。
- 覆盖：命令分发、记忆抽取/检索、Skills（含自定义安装/导出/恢复）、MCP spec、云端 function calling、数据源 API（`DATA_API_PRESETS` / `buildDataQuery` / `dataApiCall` / `data_<id>` 工具 / 未配置报错）。
- 运行：`node --test test/agent.test.mjs`。

### 10.2 冒烟测试（端到端）
- `build_exe/smoke_test.py`：设 `AGENT_EXE_TEST=1` + `AGENT_EXE_SMOKE_FILE` 启动 exe → 等待 URL 文件 → `urllib` 校验：
  - 静态资源（`/`, `index.html`, `css`, 各 `js`）均 200；
  - `/api/config` PUT/GET 持久化；`/api/fs` 读写/列目录；
  - `/api/websearch` 返回真实结果（Bing，~1s）；
  - `/api/data` 缺失 baseUrl 报错、openweather 假 key 401、可达 host 返回真实数据（代理链路通）；
  - `/api/version` 返回正确版本。
- `verify_data_proxy.py`：对 `api.github.com` 等可达 host 实测 `/api/data` 代理（header 鉴权注入 + JSON 解析），证明代理端到端可用。

### 10.3 已验证结论
- 数据代理端到端可用（ sandbox 实测 github 返回真实数据）。
- 联网搜索 Bing 后端在沙箱/国内可达环境可用；DuckDuckGo 在大陆被封锁（已由 Bing 兜底）。
- **环境限制**：沙箱出网对 `push2.eastmoney.com`、DuckDuckGo 等会随机/持续丢弃连接——属网络封锁，非代码缺陷；生产机正常网络下东方财富经 3 次重试可通。

---

## 11. 已知限制与风险

| 项 | 说明 | 影响 |
|---|---|---|
| 无代码签名 | 未做商业签名，SmartScreen 报「未知发布者」 | 用户需手动放行 |
| WebView2 依赖 | 窗口依赖系统 WebView2（Win10/11 普遍内置） | 缺失时回退浏览器 |
| DuckDuckGo 封锁 | 大陆网络不可达 | 已由 Bing 主用兜底 |
| 东方财富波动 | 免费接口随机丢连接 | 已 3 次重试缓解，仍建议控频 |
| MCP 仅 HTTP | stdio MCP 未支持 | 需 Python 桥接（待做） |
| 前端零构建 | 无 TS 类型检查、无打包优化 | 改 `webroot/js` 即生效，但需人工保证质量 |
| 文件代理无鉴权 | `/api/fs` 不设路径白名单 | 本地单用户可接受；多用户需补 |
| CSP 极宽松 | 按用户要求不设限制 | 上云前必须收紧 |

---

## 12. 升级开发路线与可行性评估

以下方向均**技术可行**，按投入从小到大排序：

| 方向 | 可行性 | 主要工作 | 备注 |
|---|---|---|---|
| 新增搜索后端（SerpAPI/Brave/Bing API） | 高 | 扩展 `websearch()` 的 `backends` 列表 + 解析器；在设置暴露 Key | 解决国内/海外统一覆盖 |
| 数据源 API 增加预设 | 高 | 在 `DATA_API_PRESETS` 加项，或用户 UI 自定义 | 已有完整框架 |
| Skills 扩展/市场 | 高 | `SKILLS` 增项 / 自定义技能导入导出已具备 | 可做技能市场 |
| 云端流式稳定化 | 高 | 完善 `postChatStream` 的 SSE/增量协议 | 已部分实现 |
| MCP stdio 支持 | 中 | 加 Python 子进程桥接 stdio↔HTTP | 需新增桥接层 |
| 主题/响应式增强 | 高 | 改 `styles.css` / `app.js` | 现有结构已支持 |
| 配置数据库化 | 中 | config.json → SQLite/LevelDB | 当前 JSON 够用，按需 |
| 插件/扩展系统 | 中 | 基于 Skills + 数据源 + MCP 组合 | 架构已具雏形 |
| 多平台（macOS/Linux） | 中 | pywebview 跨平台，但打包/签名/路径需适配 | 后端 Python 跨平台性好 |
| 上云/多租户 | 低-中 | 收紧 CSP、加鉴权、文件代理隔离 | 当前偏本地单用户 |

### 12.1 升级时的「不变契约」
- 前端入口永远是 `webroot/index.html` + `webroot/js/*.js`；改完即生效（零构建）。
- 后端入口永远是 `build_exe/launcher.py`；`/api/*` 是前后端契约，扩展功能优先走新增 `/api/xxx` 而非改旧接口。
- 版本号三处同步：入口 `APP_VERSION` + `version.txt` + 交付 `update.json` 的 `sha256`。
- 每次交付用**全新构建目录**并跑 `smoke_test.py` 全绿，再复制（先 `taskkill` 清锁）。

### 12.2 建议的下一步（按价值）
1. **搜索后端可配置化**（接 SerpAPI/Brave）——直接提升联网可靠性与海外覆盖。
2. **MCP stdio 桥接**——打通本地工具生态。
3. **CS安全与多用户隔离**——若要从「个人桌面」走向「团队/云」，必须先收紧 CSP 与文件代理鉴权。
4. **单测补「集成层」**——当前单测偏引擎逻辑，建议增加前端组件与 `/api/*` 的契约测试。

---

## 13. 附录

### 13.1 命令速查
| 命令 | 作用 |
|---|---|
| `@calc <表达式>` | 算术 |
| `@remember 键=值` / `@recall 键` / `@list` | 记忆 |
| `@time` | 时间 |
| `@skills` / `@skill <id> <参数>` | 技能 |
| `@mcp` | MCP 工具查看/调用 |
| `@web <关键词>` | 联网搜索 |
| `@file read/write/list <路径>` | 本地文件 |
| `@data <id> <查询>` | 调用已配置数据源 API |
| `@help` | 命令清单 |

### 13.2 后端 API 速查
| 方法 | 路径 | 说明 |
|---|---|---|
| GET/PUT | `/api/config` | 配置读写 |
| GET | `/api/fs?op=list&path=` / `/api/fs?path=` | 列目录 / 读文件 |
| POST | `/api/fs?path=` | 写文件（body 为内容） |
| GET | `/api/websearch?q=` | 联网搜索 |
| POST | `/api/data` | 第三方数据 API 代理（完整 spec） |
| GET | `/api/version` | 版本号 |

### 13.3 构建/测试命令
```bat
:: 单测
node --test test/agent.test.mjs
:: 冒烟（需先构建出 exe）
python build_exe/smoke_test.py
:: 构建（见 §9.1，目录每次换新）
python -m PyInstaller ...（§9.1 完整参数）
```
