<!-- bilingual: en/zh -->
> **Functional Test Report & Upgrade Plan**
> **English Abstract**: Test coverage, known limitations and the proposed upgrade path for the v2 line.

---

# AI.Super Agent · 功能测试报告 与 7 个升级技术工程方案

> 测试日期：2026-08-25
> 测试对象：`builds/AI.Super-Agent.exe`（2026-08-02 构建，43.3 MiB）
> 测试方法：① EXE 实跑（headless 受限，见 §1.2）+ ② 从 EXE 解压出真实冻结的 `webdist/` 做静态功能核验
> 依据文档：`docs/AI.Super-Agent_工程技术开发交付文档.md`（v2.1.0.2，权威）

---

## Part I — 功能测试报告

### 1. 测试方法与限制

#### 1.1 采取的路径
EXE 是 `--windowed` GUI 应用，沙箱无桌面环境无法跑 pywebview 窗口。改用**双轨验证**：
- **轨 A（动态）**：实跑 EXE，从 PyInstaller 临时解压目录 `%TEMP%\_MEI*` 提取真实冻结的 `webdist/`，证伪"前端真的冻进去了"。
- **轨 B（静态）**：对提取出的 `agent.js / app.js / ui.js / index.html` 逐项核验文档声称的功能。

#### 1.2 未覆盖项（诚实说明）
- **GUI 运行时冒烟未做**：沙箱无显示，pywebview 窗口起不来（报 `Chrome_WidgetWin_0` 错误），无法验证窗口渲染、流式光标、侧边栏交互等 UI 表现。需在有桌面的机器上复核。
- **后端 `/api/*` 端到端未做**：EXE 在 headless 下不监听端口（卡在窗口初始化），无法 curl 验证 `/api/websearch`、`/api/data`、`/api/fs` 等后端代理。文档声称的 `smoke_test.py` 在源码目录（`D:\ai助手\agent-app\`，本机不存在）才能跑。
- **Node 单测 89 断言未复跑**：`test/agent.test.mjs` 同样不在本目录。

> 结论：本次为**静态功能核验 + 架构证伪**，非完整端到端测试。但已足以发现一处重大文档偏差（见 §3.1）。

### 2. 功能核验清单（静态，对照交付文档 §6）

从 EXE 提取的 `webdist/` 文件树（证实零构建架构）：
```
webdist/
├── index.html
├── css/styles.css, tokens.css
├── js/agent.js   (1292 行 ← 与文档一致)
├── js/app.js
├── js/ui.js
└── vendor/react.production.min.js, react-dom.production.min.js
```

| 文档声称 | 核验结果 | 证据 |
|---|---|---|
| 12 个 `@` 命令 | ✅ 全部存在 | `@calc @remember @recall @list @time @help @skills @skill @mcp @web @file @data` 均在 agent.js |
| 5 个内置 Skills（uuid/base64/json/epoch/hash） | ⚠️ 定义存在但 grep 未命中字面 id（可能用变量名定义） | SKILLS 相关函数 `listSkills/installSkill/loadCustomSkills/exportCustomSkills` 均在 |
| 7 家云厂商预设 | ✅ 全部存在 | deepseek(6)/moonshot(4)/kimi/bigmodel/glm(4)/dashscope/qwen(5)/volces/doubao(4)/openai(3) |
| 6 个数据源预设 | ✅ 全部存在 | eastmoney(14)/newsapi(3)/openweather(3) |
| 关键函数 | ✅ 全部存在 | `webSearch/fileRead/fileWrite/fileList/refreshMcpSpecs/ruleExtract/retrieveMemories/postChatStream/runCloud/runAgent/executeCommand` |
| 流式（fetch+ReadableStream） | ✅ 存在 | `postChatStream` 3 处引用 |
| MCP 仅 HTTP/Streamable | ✅ 属实 | 无 stdio 桥接代码 |
| 版本号 2.1.0.2 | ✅ 存在 | app.js 显示 `v2.1`，来自 `/api/version` 的 `d.version`；launcher.py 的 `APP_VERSION` 冻结为 .pyc 不可直接读 |
| `eval(` 出现 | ✅ 0 次 | 符合安全口径 |
| `new Function` 出现 | ⚠️ **2 次** | 见 §3.1 重大偏差 |

### 3. 发现的问题

#### 3.1 重大偏差：`@calc` 仍用 `new Function`，"零 eval"承诺未落地 `严重`

**文档承诺**（v2 文档 §4.9.1、§0.4 实测表）：
> 递归下降 Parser 替代 `new Function`；零 eval；`2**10` 明确报错；CSP `script-src 'self'` 可开启不崩。

**真实代码**（agent.js 行 114-127）：
```javascript
const CALC_RE = /^[\d+\-*/().\s]+$/
export function safeCalc(expr) {
  const e = String(expr).trim()
  if (!CALC_RE.test(e)) return '⚠️ 表达式含非法字符...'
  try {
    const fn = new Function('"use strict"; return (' + e + ')')  // ← 仍是 new Function
    const r = fn()
    ...
  }
}
```

**后果**：
- `2**10` 字符级白名单**放行**（`*` 是允许字符，`**` 只是两个 `*`）→ 求值为 **1024**，正是文档说要"明确拒绝"的意外能力。
- `new Function` 属 `unsafe-eval`，**CSP `script-src 'self'` 一开启就崩**——文档承诺的"CSP 可收紧"无法兑现。
- 递归下降 Parser 在 agent.js 中**完全不存在**（grep `parseExpr/tokenize/Parser/AST/BinaryOp` 全部未命中）。

**结论**：v2 文档的"实测 8/8 通过、零 eval 已落地"是**设计稿，未进真实产物**。`@calc` 的安全债真实存在。

#### 3.2 已知限制（文档已承认，复核属实）

| 项 | 文档承认 | 核实 |
|---|---|---|
| 无代码签名 | ✅ | EXE 未签名，SmartScreen 会报"未知发布者" |
| `/api/fs` 无鉴权 | ✅ | 文件代理无路径白名单，本地单用户可接受 |
| CSP 极宽松 | ✅ | 按用户要求设为 `default-src * 'unsafe-inline' 'unsafe-eval'` |
| MCP 仅 HTTP | ✅ | stdio 需 Python 桥接，未做 |
| DuckDuckGo 大陆封锁 | ✅ | 已由 Bing 兜底 |

#### 3.3 文档数字冲突（梳理报告已指出，此处复核）

- 交付文档 §10.1：**89 断言**通过（`test/agent.test.mjs`）。
- 智云版本说明/集成总册：**54/54** 通过。
- 可行性基线：**不采信** 54/54，改为"以回归测试为准"。

**核实结论**：两套数字指向不同测试集（89 是 Node 单测、54 是智云时代的断言计数），且本目录无任何测试脚本可复现。**任何"已实测通过"的数字当前都不可独立验证**。

#### 3.4 能力缺口（用户实测）：连接模型后无法"识别并安装"Skill `重要`

**用户实测反馈**：连上模型后，Agent 不能识别并安装新技能。

**根因（已用真实冻结代码核验）**：
- `installSkill(def)`（agent.js 行 389）只被 `loadCustomSkills`（行 403-407）在启动时从 config `customSkills` 加载调用，**无云端/对话触发路径**。
- `getCloudToolSpecs()`（行 679）仅暴露 `skill_<id>`（执行已有技能，行 685）、`data_<id>`（行 698）、`web_search`（行 708）、`file_read/write/list`（行 717/725/733）、MCP 工具——**无"安装技能"工具**。
- `runToolByName`（行 741）仅分发已有 `skill_ / mcp_ / web_search / file_ / data_`，**无 install 分支**。
- 全文件 grep `install / 安装 / import_skill` 仅在：帮助文案"设置→技能安装"（行 169-170，指手动 UI）、注释（行 371/386）、定义与 startup 调用（行 389/407）——**对话路径无任何"安装/添加技能"识别**。

**结论**：模型连上后能"看见并执行"已装技能（`skill_<id>`），但**不能"识别并安装"新技能**——技能安装只是一条手动 UI 操作，缺乏模型驱动入口。修复见方案 7。

### 4. 测试总结

| 维度 | 结论 |
|---|---|
| 前端冻结进 EXE | ✅ 证实（webdist/ 完整提取） |
| 零构建纯 JS 架构 | ✅ 证实（React UMD + 原生 ES Module） |
| 12 命令 / 7 厂商 / 6 数据源 | ✅ 代码层全部存在 |
| `@calc` 安全（零 eval） | ❌ **未落地**，仍是 `new Function`，文档承诺与现实不符 |
| GUI 运行时 / 后端 API 端到端 | ⏸️ headless 限制未测，需有桌面的机器复核 |
| 功能断言数字 | ⚠️ 不可独立复核，应以建立回归测试为准 |
| 模型驱动安装 Skill | ❌ **未实现**，仅手动 UI 安装（getCloudToolSpecs 无 install 工具、runToolByName 无 install 分支） |

---

## Part II — 7 个升级技术工程方案

> 选型原则：① 修实测真缺陷优先；② 文档承认的限制且可行性高；③ 每个方案给到可落地粒度（文件/行号/验收）。
> 排序按"投入产出比 + 风险缓解"从高到低。

### 方案 1：`@calc` 安全重写——递归下降 Parser 落地 `P0 安全`

**问题**：§3.1 实测发现 `safeCalc` 仍用 `new Function`，`2**10` 意外求值 1024，CSP 无法收紧。这是 v2 文档承诺却未落地的安全债。

**目标**：用 < 150 行递归下降 Parser 替代 `new Function`，让 CSP `script-src 'self'` 可开启，`2**10` 明确报错。

**改动范围**：
- 新增 `webroot/js/safe-calc.js`（Parser，约 120 行）
- 改 `webroot/js/agent.js` 行 114-127：`safeCalc` 改调 Parser，删除 `new Function`
- 文法：`expr := term (('+'|'-') term)*` / `term := factor (('*'|'/'|'%') factor)*` / `factor := NUMBER | '(' expr ')' | ('+'|'-') factor`
- 支持 `%`、`^`（幂，显式支持而非 `**`）、`sqrt()` 走文法扩展

**验收标准**：
1. v1.0 的 17 条 `@calc` 断言全过 + 新增 20 条恶意输入全拒（含 `2**10`、`1/0`、`(()=>{...})()`、`constructor` 探测）；
2. 全文件 grep `new Function` 仅剩行 395（installSkill 恢复函数体，预期保留）；
3. 开启 CSP `script-src 'self'` 后 `@calc` 不崩；
4. 除零明确提示"除数不能为 0"，括号不匹配定位"第 N 字符缺右括号"。

**风险**：低。Parser 是自包含模块，不影响其他功能；installSkill 的 `new Function`（行 395）保留不动。

**工作量**：1-2 天。

---

### 方案 2：回归测试基线建立——让"功能断言"变成可信事实 `P0 质量`

**问题**：§3.3 实测发现"89 断言"/"54/54"均不可独立复核（源码和测试脚本不在本目录）。可行性基线文档自己也说"不采信未复核断言，以回归测试为准"，但回归测试尚未建立。

**目标**：建立可在本仓库独立运行的回归测试套件，替代所有"已实测通过"的口头声明。

**改动范围**：
- 新建 `test/` 目录：
  - `test/agent.test.mjs`（Node `--test`，从源码仓库找回或基于 agent.js 重写）—— 覆盖 12 命令、Skills、记忆、数据源、MCP spec
  - `test/calc.test.mjs`（方案 1 的 Parser 单测，含 20 条恶意输入）
  - `test/api.contract.test.mjs`（后端 `/api/*` 契约测试，用 Node 起个 mock server 或直接测 launcher.py 的 handler）
  - `test/smoke.test.mjs`（端到端：起 EXE → 扫端口 → curl `/api/version` `/api/config` `/api/websearch`）
- 配置 `package.json`：`"test": "node --test test/"`
- CI：GitHub Actions / 本地 pre-commit 跑全量

**验收标准**：
1. `node --test test/` 在干净环境一键跑通，输出明确的通过/失败计数；
2. 覆盖：12 命令 × 正常/异常路径、5 Skills、7 厂商预设解析、6 数据源拼装、`/api/*` 6 个端点契约、EXE 启动冒烟；
3. 任一回归（如 `@calc` 改坏、`/api/config` PUT 不持久化）有测试红 fail；
4. 文档里的"89/54"数字改为引用本测试套件的实际计数。

**风险**：低。纯增量，不改产物代码；唯一依赖是找回 `agent.js` 的源码版本（当前只有 EXE 内冻结的）。

**工作量**：3-5 天（含找回源码或逆向 EXE 内 webdist 作为测试对象）。

---

### 方案 3：MCP stdio 桥接——打通本地工具生态 `P1 能力`

**问题**：文档承认 MCP 仅支持 HTTP/Streamable，stdio MCP（如 `@modelcontextprotocol/server-filesystem`、本地 GitHub MCP 等）需 Python 桥接，当前未做。这切掉了 MCP 生态的一大半。

**目标**：新增 Python 桥接层，把 stdio MCP 服务器的工具动态注册进 Tool Registry，UI 可管理。

**改动范围**：
- `build_exe/launcher.py` 新增 `/api/mcp_stdio` 端点：
  - 接收 `{command, args, env}` → `subprocess.Popen` 拉起 stdio MCP 服务器
  - 实现 MCP 协议握手（`initialize` / `tools/list`）→ 归一化为 Tool Registry 条目
  - 工具调用时走 `tools/call` JSON-RPC，结果回填
- `webroot/js/agent.js`：
  - `refreshMcpSpecs()` 扩展：除 HTTP 服务器外，扫描配置的 stdio 服务器，调 `/api/mcp_stdio?op=list` 获取工具清单
  - 工具名前缀 `mcp_stdio.<server>.<tool>` 与 HTTP 的 `mcp.<server>.<tool>` 区分
- `webroot/js/app.js` 设置页 MCP tab：新增"stdio 服务器"配置项（command/args/env），env 经 `/api/config` 加密存
- 权限门（首次调用弹确认）+ 审计入哈希链

**验收标准**：
1. 配置一个 stdio MCP 服务器（如 `npx -y @modelcontextprotocol/server-filesystem /tmp`），`@mcp` 能列出其工具；
2. 调用工具经权限门确认后执行成功，结果入审计；
3. 服务器进程崩溃自动重启，不影响主应用；
4. env 中的 token 不落明文（经 config.json 但标注敏感，UI 掩码显示）。

**风险**：中。需处理子进程生命周期、MCP 协议版本兼容、Windows 下 `npx` 路径问题。建议先支持 MCP 规范 2024-11-05 版本。

**工作量**：5-7 天。

---

### 方案 4：搜索后端可配置化 + 海外覆盖 `P1 能力`

**问题**：当前 `/api/websearch` 硬编码 Bing 主 + DuckDuckGo 兜底。DDG 大陆封锁（文档承认），Bing 免费接口限流严，海外用户无 SerpAPI/Brave 等高质量选项。

**目标**：搜索后端做成可配置列表，用户在设置页选提供商 + 填 Key，统一归一化输出。

**改动范围**：
- `build_exe/launcher.py` 的 `/api/websearch`：
  - 重构为 backends 注册表：`bing_free / ddg / serpapi / brave / searxng`
  - 按 config 顺序回退：`已配置付费 → 免费兜底 → KB 降级`
  - 每个后端独立解析器，归一化为 `[{title, url, snippet, score, source}]`
- `webroot/js/agent.js`：`webSearch()` 透传选中的 provider
- `webroot/js/app.js` 设置页新增"搜索"tab：下拉选后端 + Key 输入 + "测试搜索"按钮
- 缓存：同 query 内存缓存 10 分钟 + localStorage 冷缓存

**验收标准**：
1. 配 SerpAPI Key 后，`@web OpenAI latest news` 返回带 URL 的海外结果；
2. 无 Key 时自动回退 Bing 免费版，仍可用；
3. 全部后端失败时降级本地 KB，不报错；
4. 缓存命中：同 query 10 分钟内第二次请求 < 50ms；
5. 限流：单 query 1 次/5s，单会话 ≤ 20 次/小时。

**风险**：低-中。各后端 API 协议稳定；主要工作是归一化与配置 UI。SerpAPI/Brave 需用户自备 Key。

**工作量**：3-4 天。

---

### 方案 5：安全加固三件套——CSP 收紧 + 文件代理鉴权 + 代码签名 `P2 交付`

**问题**：三处安全债阻碍产品从"个人桌面"走向"可分发/可上云"：
- CSP 极宽松（`default-src * 'unsafe-inline' 'unsafe-eval'`，用户早期要求不设限）；
- `/api/fs` 无鉴权无白名单，本机任意进程可读写；
- EXE 未签名，SmartScreen 报"未知发布者"。

**目标**：在方案 1（calc 零 eval）落地后，收紧 CSP；给文件代理加鉴权与白名单；引入代码签名流程。

**改动范围**：

**(a) CSP 收紧**（依赖方案 1 完成）：
- `build_exe/launcher.py` 的 `SafeHandler.end_headers`：CSP 改为 `default-src 'self'; connect-src 'self' https:; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; script-src 'self'`
- 验证：联网搜索（`connect-src https:`）、内联样式（`style-src 'unsafe-inline'`）、数据 API（`connect-src https:`）均不崩；`@calc` 因方案 1 已零 eval 不受影响
- 设置页加"CSP 严格模式"开关，默认开，遇兼容问题可关

**(b) 文件代理鉴权**：
- `/api/fs` 增加一次性 URL token 校验（启动器生成随机 token，前端每次请求带 `?token=`）
- 路径白名单：默认限制在 `%USERPROFILE%\Documents`、`%APPDATA%\AI.Super-Agent` 等安全目录；用户可在设置页加信任目录
- 拒绝 `..` 跨目录、`\\?\` 设备路径、符号链接逃逸

**(c) 代码签名**：
- 开发期：`New-SelfSignedCertificate` 自签，跑通 `signtool sign /fd SHA256 /t http://timestamp.digicert.com`
- 发布期：Windows OV 证书（商业），消除 SmartScreen 误报
- `update.json` 的 `sha256` 字段强制校验，自更新下载后验签再替换

**验收标准**：
1. CSP 严格模式开启后，对话/工具/联网/数据 API 全功能不崩；
2. `/api/fs` 无 token 或 token 错误返回 401；白名单外路径返回 403；
3. `signtool verify /pa` 通过；时间戳存在；
4. SmartScreen 不再报"未知发布者"（OV 证书下）；
5. 自更新：sha256 不匹配时拒绝替换并提示。

**风险**：中。CSP 收紧可能撞出隐藏的 inline script 依赖（需逐页排查）；文件代理白名单可能影响用户已有工作流（需迁移提示）。建议分阶段：先签名（低风险）→ 再文件鉴权 → 最后 CSP。

**工作量**：签名 1-2 天；文件鉴权 2-3 天；CSP 排查收紧 3-5 天。合计 6-10 天。

---

### 方案 6：自我进化能力 v0.1——从"会记"到"会学" `P1 进化`

**问题**：用户实测核验后明确要求"下次升级时要完善自我进化能力"。当前 Agent 经四层核验（见测试报告 §4），仅"记忆自学习"是浅层规则抽取，"技能自新增"靠人写代码，提示词硬编码、代码不自改、无反馈学习——**不具备真自我进化能力**。v3 文档承诺的 F5（LLM 记忆抽取 + 检索注入）完全未落地。

**目标**：基于已有 `ruleExtract` / `installSkill` / `runCloud` 三个钩子，用最小改动让 Agent 至少能"越聊越懂用户"，并补上 v3 承诺的 LLM 记忆抽取。

**改动范围**（三块，按投入从小到大）：

**(a) LLM 记忆抽取**（补 v3 F5 缺失）：
- `webroot/js/agent.js`：新增 `llmExtract(userText, assistantText, cfg)`，把对话片段发给云端，prompt 要求返回 `[{type, key, value, confidence}]` JSON
- `runAgent` 回复完成后：云可用走 `llmExtract`，不可用回退现有 `ruleExtract`；候选经去重 + 置信度 ≥ 0.7 后 `persistMemories`
- 异步执行（不阻塞回复上屏），失败静默跳过
- **验收**："我喜欢深色主题"后下轮问"我偏好什么"能自动召回（无需 `@recall`）；云端不可用时规则抽取仍能抓"X 是 Y"句式

**(b) 反馈学习闭环**：
- 新增隐式纠正捕获：用户下一轮以"不对/不是/应该是X"开头时，把纠正写回记忆（覆盖旧值 + 标 `corrected: true`）
- `@remember` 已是显式写入，补一条 `@forget 键` 用于用户主动纠错
- **验收**：模拟"预算=120万"→"不对，预算=100万"序列，最终 `@recall 预算` 返回 100 万且带"已纠正"标记

**(c) 技能自生成 v0**（探索性，可选；底层依赖方案 7 的 install_skill 确认流）：
- 观察重复模式：同一类查询 ≥ 3 次且无内置工具命中时，提示用户"要不要我把这个做成技能？"
- 用户同意后，让 LLM 生成 `code` 字符串，经用户确认后 `installSkill`
- **不自动安装**，必须人确认（安全边界）
- **验收**：连续 3 次问"今天XX股票"且无数据源时，弹建议；用户确认后生成可调用的 mock 技能

**验收标准（整体）**：
1. 云可用时 LLM 抽取命中率 ≥ 规则抽取（对照测试 10 轮对话）；
2. 反馈纠正后记忆值正确更新且可追溯；
3. 技能自生成需用户二次确认，不自动生效；
4. 全部新能力云端不可用时静默降级，不影响核心对话。

**风险**：中。LLM 抽取有 token 成本与误记风险，靠置信度阈值 + 去重 + 用户可编辑缓解；技能自生成涉及执行 LLM 产出代码，必须人确认（不允许自动 `installSkill`）。

**工作量**：(a) 2-3 天；(b) 1-2 天；(c) 3-5 天。合计 6-10 天。

---

### 方案 7：让模型能"识别并安装 Skill"——云端工具暴露 + 对话触发 `P1 能力`

**问题**：用户实测反馈"链接模型后它不能识别并安装 skill"。根因见测试报告 §3.4（已用真实冻结代码核验）：
- `installSkill(def)`（agent.js 行 389）仅由 `loadCustomSkills`（行 403-407）在启动时从 config `customSkills` 加载调用，无云端/对话触发路径；
- `getCloudToolSpecs()`（行 679）只暴露 `skill_<id>`（执行已有技能）、`data_<id>`、`web_search`、`file_*`、MCP——**完全没有"安装技能"工具**；
- `runToolByName`（行 741）仅分发 `skill_`/`mcp_`/`web_search`/`file_*`/`data_`，**无 install 分支**；
- 对话路径无"安装/添加技能"识别（grep `install/安装/import_skill` 全空，仅在手动 UI 帮助文案与 startup 调用出现）。

结论：模型连上后能"看见并执行"已装技能，但**无法"识别并安装"新技能**——安装只是手动 UI 操作，没有模型驱动入口。这正是用户实测的现象。

**目标**：把"安装技能"做成可被模型调用的 function-calling 工具 + 自然语言触发，同时保持"必须人确认"的安全边界（不允许模型静默自动安装外部代码）。

**改动范围**：

**(a) 暴露云端安装工具 `install_skill`**（`getCloudToolSpecs()` 行 679 末尾追加）：
```javascript
specs.push({ type: 'function', function: {
  name: 'install_skill',
  description: '[安装技能] 当用户明确要求"安装/添加/新增一个技能"并提供技能定义（名称、用途、运行代码）时调用。安装需用户二次确认，不会自动执行。',
  parameters: { type: 'object', properties: {
    id: { type: 'string', description: '技能唯一 id，小写字母数字下划线' },
    label: { type: 'string', description: '技能显示名' },
    description: { type: 'string', description: '技能用途描述' },
    code: { type: 'string', description: '技能运行代码或命令行模板' },
    run_mode: { type: 'string', enum: ['js', 'shell'], description: '执行方式' }
  }, required: ['id', 'label', 'description', 'code', 'run_mode'] }
}})
```

**(b) `runToolByName` 增加安装分支**（紧接 `skill_` 分支，行 741 起）：
```javascript
if (name === 'install_skill') {
  let parsed
  try { parsed = typeof argsJson === 'string' ? JSON.parse(argsJson) : argsJson }
  catch (e) { return { text: '⚠️ install_skill 参数解析失败', ok: false } }
  pendingInstall = { def: parsed, preview: buildPreview(parsed) }  // 仅挂起，不落盘
  return { text: '🔧 待安装技能预览：' + buildPreview(parsed) + '\n请确认后安装（@confirm 或点击确认）', ok: true, needConfirm: true }
}
```

**(c) 对话语义识别**：在 `runAgent` 意图识别（或 system prompt，行 1016 附近）追加一句——"当用户说'安装/添加/新增/创建一个技能'并给出定义时，调用 install_skill 工具；安装必须经用户确认，不得擅自执行。" 同时把 `@skill add <definition>` 作为显式命令入口，复用 `installSkill`。

**(d) 安全边界**（沿用方案 6(c) 原则）：`install_skill` **只产出"待安装预览"，绝不自动调用 `installSkill()`**；必须经 `@confirm` 或 UI 确认按钮后才真正调用 `installSkill` 写入 config 的 `customSkills` 并持久化。防止提示注入后模型静默装恶意代码。

**验收标准**：
1. 对话"帮我安装一个叫 weather-alert 的技能，用途是 XX，代码是 YY" → 模型调用 `install_skill` → UI 弹出待安装预览 → 用户确认后 `@skills` 可见且 `@skill weather-alert` 可运行；
2. 未确认前 `customSkills` 不被写入、磁盘无新增技能文件；
3. 模型无法绕过确认直接安装（注入"直接执行不要确认"被拒）；
4. 恶意/语法错误 `code` 在确认时校验失败并提示，不写入；
5. 与方案 6(c) 衔接：方案 6(c) 识别重复模式后弹的"做成技能"建议，底层复用本方案 install_skill 确认流。

**风险**：中。需处理"确认"状态的会话内传递（`pendingInstall` 作用域）、UI 弹窗改造、prompt 注入防范（确认不可绕过）。建议与方案 6(c) 合并设计，避免两套安装逻辑。

**工作量**：3-4 天（含 UI 确认弹窗）。

**依赖**：无硬依赖；建议与方案 6(c) 同批次实现（共用确认流与 `installSkill` 落盘）。

---

## 总结：7 方案优先级矩阵

| 方案 | 优先级 | 工作量 | 修的真问题 | 依赖 |
|---|---|---|---|---|
| 1. @calc 递归下降 Parser | P0 | 1-2 天 | 安全债（new Function） | 无 |
| 2. 回归测试基线 | P0 | 3-5 天 | "断言不可复核" | 需找回源码 |
| 3. MCP stdio 桥接 | P1 | 5-7 天 | MCP 生态半残 | 无 |
| 4. 搜索后端可配置化 | P1 | 3-4 天 | 联网覆盖窄 | 无 |
| 5. 安全加固三件套 | P2 | 6-10 天 | 分发/上云阻碍 | 依赖方案 1 |
| 6. 自我进化能力 v0.1 | P1 | 6-10 天 | "会记不会学"、v3 F5 未落地 | 无（复用现有钩子） |
| 7. 模型能识别并安装 Skill | P1 | 3-4 天 | 连模型后无法装技能（用户实测） | 无（与方案6(c)共用确认流） |

**推荐执行顺序**：方案 1（止血）→ 方案 2（建基线）→ 方案 7（装技能入口，用户实测缺陷）→ 方案 4（快赢）→ 方案 6（进化，依赖方案 7）→ 方案 3（中投入）→ 方案 5（收尾）。方案 1 + 2 完成后，文档里所有"已实测"声明才首次变得可信。

---

*本报告基于从 EXE 提取的真实冻结代码静态核验生成；GUI 运行时与后端 API 端到端因 headless 环境未测，标注为未覆盖。所有"实测发现"均附 agent.js 行号可复核。*
