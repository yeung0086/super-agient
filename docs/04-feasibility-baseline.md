<!-- bilingual: en/zh -->
> **Feasibility Baseline**
> **English Abstract**: Baseline study of architecture options, security risks and capability gaps for the desktop agent.

---

# AI.Super Agent（Agent 应用）· 工程技术文档 · 可行性基线版

> **文档性质**：单一权威工程技术文档，覆盖 v1.0 → v2.0 → v3.0 → v4.0 全版本脉络，并给出**可行性结论与升级路线图**，作为后续升级开发的基线参考。
> **产品名称**：**AI.Super Agent**。各历史版本文档中曾称「AI 助手」；近期部分交付文件一度误标为「智云」，**本文统一采用 AI.Super Agent，智云命名视为噪音已清洗**。源文件名保留原名以便溯源。
> **当前主产物**：`AI.Super-Agent.exe`（Windows 单文件 EXE，PyInstaller `--onefile --windowed`；构建于 2026-08-02）。
> **集成日期**：2026-08-02
> **构成**：
> - **Part I — 架构升级基座（v2.0）**：实测缺陷台账 + Tool Registry 双路复用 + 上下文治理 + 安全横切 + 双流水线
> - **Part II — 能力扩展（v3.0）**：七项新能力（联网搜索 / Skills / MCP / 国内大模型 / 记忆 v3 / ReAct 推理 / Claude 风格输出）
> - **Part III — 打包交付专篇（v4.0）**：PyInstaller → EXE 全链路（签名 / 更新 / 瘦身）
> - **Part IV — 可行性结论与升级路线图（新增）**：已验证基线 / 扩展点 / 升级评估 / 推荐路线 / 风险
> - **Appendix A — 当前交付物与可行性附注**

---

## 0. 文档说明

### 0.1 数据可信度约定（噪音清洗核心）

本文档对每一项结论标注可信度，区分**事实**与**推测**，避免把设计预期当承诺：

| 标记 | 含义 | 来源 |
|---|---|---|
| 🔬 实测 | 有可复现脚本或发布实测背书 | `优化方案_问题验证.mjs` / `v2.0方案_修复验证.mjs` / EXE 打包实测 |
| 📐 设计 | 架构/接口设计合理，待实施或仅逻辑等价模拟，未跑真实环境 | 本文设计章节 |
| 📋 计划 | 路线图 / 待办 / 待决策项 | Part IV |

> **规则**：凡标注 📐 / 📋 的数字（如 Tauri ~8MB、Lighthouse ≥85、各厂商端点）**不得当作事实引用**，实施时以官方文档与落地实测为准。

### 0.2 本次噪音清洗清单

| 噪音 | 处理 |
|---|---|
| 「智云」误标命名（版本说明/README/update.json） | 全文档统一为 **AI.Super Agent**，智云命名视为过时噪音删除 |
| 未复核的「54/54 功能断言通过」断言（源自智云版本说明） | 不采纳为事实；改为「以回归测试为准」 |
| 各 Part 重复的「文档版本 / 状态 / 上一版」状态框 | 收敛为 §0 单一说明 + 每 Part 一行状态 |
| A6：v2.0 对已删除 `v2.0_优化版.md` 的失效交叉引用 | 删除，改为集成总册声明 |
| A7：v2.0 §0.3 写「两处口径错误」但表与 §12 均为三处 | 统一为「三处」 |
| 目录中多份重复/冲突文档（v2.0 副本、各 _claude 变体） | 以本文件为唯一权威基线；冗余源文件建议归档（见 Appendix A.6） |

### 0.3 文档构成与版本演进

| 版本 | 主题 | 关键内容 | 状态 |
|---|---|---|---|
| v1.0 | 实现版事实记录 | 生成 → 六门质检 → 审计 → 出 EXE 的工程链路 | 🔬 已交付 |
| v2.0 | 架构升级基座 | 14 项缺陷闭环、Tool Registry 双路、上下文预算、零 eval、双流水线 | 🔬 已实施（缺陷数据实测） |
| v3.0 | 能力扩展 | 七项新能力（F1–F7）设计 | 📐 设计完成、可行性已验证 |
| v4.0 | 打包交付专篇 | PyInstaller 单文件 EXE 全链路 | 🔬 打包命令实测跑通 |
| 当前 | AI.Super Agent 主产物 | 单文件 EXE，支撑对话/工具/联网/扩展 | 🔬 产物存在；功能断言待回归复核 |

---



---

# Part I — 架构升级基座（v2.0）　🔬 已实施

> v2.0 架构升级版全文。缺陷侧数据由 `优化方案_问题验证.mjs` 复现，修复侧由 `v2.0方案_修复验证.mjs` 验证（8/8 通过）；均为 🔬 实测。

# AI.Super Agent（Agent 应用）— 工程技术文档 v2.0

> **文档版本**：v2.0（架构升级版 · 实施级）
> **上一版**：v1.0（2026-07-15，实现版，含真实验证证据）
> **升级依据**：《AI.Super Agent_优化方案 v1.1》——基于真实源码逐行审查 + 可复现实测
> **源码位置**：`C:\Users\Administrator\WorkBuddy\秒哒\agent-app\`
> **审查范围**：`src/agent.ts`(166行) · `src/App.tsx`(206行) · `src/ui/*` · `build_exe/launcher.py`
> **所属能力**：WorkBuddy 框架内复刻「秒哒」——app-generator 编排大脑 + exe-builder MCP 引擎 + 设计系统
> **对应场景**：场景 #17「Agent 应用」
> **日期**：2026-08-01
> **状态**：v1.0 已交付并在跑；v2.0 已实施；本文档作为可行性基线 Part I，为全文档权威基座。
>

---

## 0. 本次升级做了什么

### 0.1 一句话

v1.0 证明了**工程链路**可行（生成 → 六门质检 → 审计 → 出 EXE），v2.0 要修的是**产品内核**——把"一个带命令行工具的聊天框"变成真正的 Agent。

### 0.2 v1.0 → v2.0 变更摘要

| 章节 | v1.0 | v2.0 变化 |
|---|---|---|
| §1 背景目标 | 目标陈述 | **新增 §1.4 实测缺陷台账**（3 个真实 bug + 2 个架构缺陷，附行号与实测数据） |
| §2 架构 | 三层（UI / agent.ts / EXE 壳） | 重构为 **Tool Registry 双路复用**架构，`agent.ts` 拆为 `agent/` 模块集 |
| §3 选型 | 6 条 | 新增 **ADR-01~06** 决策记录，含被否决方案与理由 |
| §4 模块 | 2 个模块 | 扩为 **10 个模块**，每个给出接口签名与验收标准 |
| §5 功能 | 4 项 | 扩为 **12 项**，区分"已有 / 新增 / 修复" |
| §6 质检 | 六门 5/6 | 门 3 补 **Playwright 真浏览器**（v1.0 的 curl 冒烟测不到运行时 bug，写放大即明证） |
| §7 打包 | PyInstaller 单线 | **双流水线**（Tauri 主 / PyInstaller 回退）+ 瘦身红线 |
| §8 验证 | 17/17 断言 | 扩为 **六层验证矩阵**，v1.0 的 17 条设为回归红线只增不改 |
| §10 实施 | — | **新增**：Phase 0~3 分阶段计划 + 里程碑 |
| §12 限制 | 4 条 | 更新，并**修正 v1.1 中我方三处口径错误**（见 §0.3） |

### 0.3 对上一版方案的两处自我修正

工程文档的价值在于数字可信，先把自己的错纠了：

| 项 | v1.1 方案里的说法 | 实际核对结果 | 结论 |
|---|---|---|---|
| EXE 体积 | "实际 45.4MB，文档写 43.3MB，**文档有误**" | `45,375,288` 字节 = **43.27 MiB** = 45.38 MB | **v1.0 文档没错**，是 MiB 口径。v1.1 用了十进制 MB 口径导致误判。本文统一标注 `43.3 MiB (45.4 MB)` |
| API Key 输入框 | 暗示 UI 层暴露 Key | `App.tsx:137` 已是 `type="password"` | **UI 层无问题**，真实风险仅在 `App.tsx:43` 的明文落盘 |
| 示例算式 | v1.1 与本文初稿均写 `(12+8)*3 = 36` | **`(12+8)*3 = 60`** | 算术笔误，验收标准已更正（§4.3）。由 `v2.0方案_修复验证.mjs` 跑出来发现 |

> 其余所有实测数据（写放大 600 次/4.0MB、KB 误命中 4/7、O(n²) 上下文 38.3 万字符）均复核无误，复现脚本见同目录 `优化方案_问题验证.mjs`。

### 0.4 v2.0 修复方案已实测有效 `8/8 通过`

设计不能只停在纸上。四项核心修复已用 `v2.0方案_修复验证.mjs` 跑出对照数据：

| 修复项 | v1.0 实测 | v2.0 实测 | 降幅 / 提升 |
|---|---|---|---|
| KB 打分召回（D4） | 3/7 正确 | **7/7 正确**，正向回归 5/5 未误伤 | 误命中 4 → 0 |
| localStorage 落盘（D2） | 600 次 / 3.986 MB | **1 次 / 0.007 MB** | **-99.8%** |
| 上下文 payload 峰值（D3） | 14,700 字符 | **6,009 字符**，污染消息 0 条入上下文 | -59% |
| 安全计算（D9/D10） | `2**10` → 意外求值 1024 | **明确拒绝**；除零/括号错误可定位 | 5/5 符合预期 |

> **落盘策略选型（实测得出）**：真·防抖（trailing）在流式期间定时器被持续重置（tick 14ms < 400ms），全程仅在流结束后落盘 **1 次**；对照的节流（leading）会每 400ms 强制写一次共 **22 次**——性能同样可接受但无必要。**故采纳防抖**。

---

## 1. 背景、目标与缺陷台账

### 1.1 这是什么

AI.Super Agent是一个**本地运行的 Agent 应用**：用对话方式提供"能聊、能算、能记"的助手能力。由 WorkBuddy 的 app-generator 工作流自动生成，经六门质检与审计，打包为单文件 Windows EXE。

### 1.2 v2.0 目标

在 v1.0 五项目标（开箱即用 / 可演示 Agent 能力 / 可选接大模型 / 像产品 / 全流程留痕）基础上，新增四条**硬指标**：

1. **工具永不失效**——无论本地还是云端模式，`calc`/`memory`/`time` 等能力始终可用（v1.0 云端模式下全废）。
2. **首字延迟 < 1s**——真流式，取消"假打字机"（v1.0 首字延迟 = 全量生成时间）。
3. **长对话成本恒定**——上下文预算封顶，从 O(n²) 压到常数（v1.0 第 50 轮单请求 15,000 字符）。
4. **零 eval**——CSP `script-src 'self'` 可开启不崩溃（v1.0 `new Function` 阻断 CSP）。

### 1.3 与文档体系关系

- 《WorkBuddy_EXE生成器_工程技术文档 v1.0》——总能力（六门质检 / 审计脊柱 / 出 EXE）。
- 《WorkBuddy内复刻秒哒_完整工程技术文档 v3.0/v3.1》——框架总纲与多场景落地。
- 《AI.Super Agent_工程技术文档 v1.0》——本文档的基座，实现版事实记录。
- 《AI.Super Agent_优化方案 v1.1》——本文档的依据，问题诊断与证据。
- **本文档 v2.0**——把诊断收敛为一套内聚架构 + 可执行实施计划。

### 1.4 实测缺陷台账（v2.0 的存在理由）

> 全部附代码行号；标 `实测` 的均由 `优化方案_问题验证.mjs` 可复现。

#### D1 · 云端模式下五个工具静默失效 `严重` `功能性欺骗`

`agent.ts:155-166` —— 云端与本地是**互斥两条路**：

```ts
export async function runAgent(userText, history, cfg) {
  if (cfg.enabled && cfg.baseUrl && cfg.apiKey) {
    try { return await cloudRespond(cfg, history) }   // ← 工具被完全绕过
    catch (e) { /* 回退本地 */ }
  }
  return localRespond(userText, history)              // ← 只有本地模式才有工具
}
```

用户一旦启用云端，`@calc` `@remember` `@recall` `@list` `@time` **全部失效**：

- `@calc (12+8)*3` 原样发给大模型由其"心算"——算术幻觉高发区；
- `@remember 项目=X` **根本没写进 localStorage**，模型却回"好的我记住了"，随后 `@recall` 查无此项。

这与 v1.0 文档 §1.2 目标"具备可演示的 Agent 能力：工具调用"**直接矛盾**：启用更强的大脑，反而失去手脚。

#### D2 · localStorage 写放大 `严重` `实测` `性能 bug`

`App.tsx:42` 持久化 effect + `App.tsx:57-76` 的 14ms/字打字机：

```ts
useEffect(() => { localStorage.setItem(MSG_KEY, JSON.stringify(messages)) }, [messages])
```

`typewrite` 每 14ms 调一次 `setMessages` → effect 每 14ms 触发 → **整个对话历史 stringify 后同步全量写盘一次**。

> **实测（20 条历史 + 一条 600 字回复）：触发 600 次全量写入，累计序列化 4.0 MB。**

`localStorage` 是**同步阻塞主线程**的 API。后果：打字期间持续掉帧，且写入体积随历史线性增长 → 整体 O(n²)，对话越长越卡。

**这是 v1.0 六门质检完全测不到的运行时缺陷**——门 3 只是 `serve dist + curl` 拿 200。六门全绿它照样存在。

#### D3 · 上下文无治理，O(n²) 成本 `实测`

`App.tsx:86` 把完整 `next` 数组交给 `runAgent`，`agent.ts:145` 原样塞进 `messages`。**无 system prompt、无截断、无预算。**

> **实测（每轮 user+assistant 各约 150 字符）：第 10 轮单请求 3,000 字符 → 第 50 轮 15,000 字符；50 轮累计发送约 38.3 万字符。**

衍生四个问题：

1. 长对话必撞上下文上限 → HTTP 400 → 被 `agent.ts:159` 的 `catch` **静默吞掉** → 退回本地引擎。用户只觉得"助手突然变傻了"，无从排查。
2. 无 system prompt：人格、语气、工具规则、拒答边界全靠模型默认行为，换模型即漂移。
3. **污染回流**：本地生成的 `⚠️ 云端调用失败…` 被存进 `messages`，下一轮原样发回模型，被当成助手真实发言。
4. 错误不分类：401/429/400/超时全部混成一句"云端调用失败"。

#### D4 · KB 裸 `includes` 误命中率 57% `实测`

`agent.ts:108-114`：`if (item.kw.some(k => lower.includes(k))) return item.answer`

`kw` 含 `'ts'`、`'hi'` 这类两字母短词。**实测 7 条输入，4 条误命中**：

| 用户输入 | 实际命中 | 应该 |
|---|---|---|
| 什么是 GPTs？ | ❌ TypeScript | 无 |
| chief architect 是什么 | ❌ 问候 | 无 |
| This is a test | ❌ 问候 | 无 |
| 解释一下 hits 和 misses | ❌ TypeScript | 无 |
| 机器学习入门 | ⚠️ 编程 | 勉强 |
| 讲讲 Rust 的所有权 | ✅ null | 无 |
| Nginx 怎么配置 | ✅ null | 无 |

且为**数组顺序优先**而非相关度优先：React 永远压过 TypeScript，无"谁更相关"概念。

#### D5 · 其余已确认缺陷

| ID | 位置 | 问题 | 级别 |
|---|---|---|---|
| D6 | `agent.ts:142` | `fetch` 无 `AbortController`、无 timeout；baseUrl 指向 hang 住地址时 UI 卡死数分钟，只能杀进程 | 高 |
| D7 | `App.tsx:51` | 无条件 `scrollIntoView`，用户上滑回看历史时每 14ms 被拽回底部，无法翻记录 | 中 |
| D8 | `App.tsx:167` | 纯文本渲染 `{m.content}`；接云端后 Markdown/代码围栏**原样裸奔** | 中 |
| D9 | `agent.ts:20-34` | 白名单是**字符级**过滤，无法表达语法约束：`@calc 2**10` 全字符合法 → `new Function` 求值 1024（未文档化、未测试的意外能力）；且 `new Function` 属 `unsafe-eval`，**加 CSP 必崩** | 中 |
| D10 | `agent.ts:29` | `1/0` → `Infinity` → 被 `isFinite` 拦下返回"算不出来"，用户不知是除零 | 低 |
| D11 | `App.tsx:43` | 整个 `cfg`（含明文 `apiKey`）写入 `localStorage`；同源脚本、浏览器扩展、EXE 内 WebView 均可读 | 中 |
| D12 | `agent.ts:122-127` | 6 个 `startsWith` 硬匹配，用户须记精确语法；"帮我算一下 128 除以 4"不触发任何工具 | 中 |
| D13 | `launcher.py` | 本地 HTTP 服务无鉴权，本机任意进程可访问 `127.0.0.1:<port>` | 低 |
| D14 | 六门 | 门 4 跳过、门 6 评分 **70/100 刚好卡及格线** | 中 |

### 1.5 缺陷 → 能力域映射

| 缺陷 | 收敛到 | 优先级 |
|---|---|---|
| D2 D6 D7 D8 | 能力域 A：交互与性能（§4.8） | **P0** |
| D1 D12 | 能力域 B：Agent 引擎 v2（§4.1~4.4） | **P0** |
| D3 | 能力域 C：上下文与成本治理（§4.5） | P1 |
| D4 | 能力域 D：知识库与记忆（§4.6~4.7） | P1 |
| D9 D10 D11 D13 | 能力域 E：安全基础设施（§4.9） | P2 |
| D14 | 能力域 F：质检与交付（§6、§7） | P2 |

---

## 2. 总体架构 v2.0

### 2.1 目标架构

```
┌────────────────────────────────────────────────────────────────┐
│                 用户（浏览器 / 桌面窗口）                          │
│      聊天输入 · 流式消息流 · 停止生成 · 设置面板 · 主题切换         │
└───────────────────────────┬────────────────────────────────────┘
                            │ 自然语言
┌───────────────────────────┴────────────────────────────────────┐
│                  React + Vite 前端（src/App.tsx）                │
│  Markdown 渲染器 · SSE 流式追加 · 智能滚动 · 防抖落盘(400ms)      │
│  AbortController(停止/超时) · 消息级操作(复制/重生成/删除)         │
└───────────────────────────┬────────────────────────────────────┘
                            │ runAgentV2()
┌───────────────────────────┴────────────────────────────────────┐
│                   Agent 引擎 v2（src/agent/ 模块集）             │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │            上下文构造器 ContextBuilder（§4.5）              │ │
│  │   SYSTEM_PROMPT + 历史摘要 + 最近 N 轮（6000 字符预算内）    │ │
│  │   过滤 meta.error / meta.local 标记的污染消息               │ │
│  └──────────────────────────┬────────────────────────────────┘ │
│                             ▼                                   │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                  Agent Loop（≤5 轮，防死循环）              │ │
│  │                                                            │ │
│  │    云端可用？                                               │ │
│  │      ├─ 是 → Provider(stream:true, tools:TOOLS)            │ │
│  │      │        finish_reason==='tool_calls' ?               │ │
│  │      │           ├ 是 → 本地执行 → role:'tool' 回灌 → 循环   │ │
│  │      │           └ 否 → SSE 逐 delta 上屏，结束             │ │
│  │      └─ 否 → 本地引擎：意图路由 → 工具 / KB 打分召回 / 兜底   │ │
│  └──────────────────────────┬────────────────────────────────┘ │
│                             ▼                                   │
│  ┌──────────────────┐  ┌────────────────┐  ┌────────────────┐  │
│  │  Tool Registry   │  │ Memory Service │  │ Provider 适配层 │  │
│  │  一次定义         │  │ 类型化·模糊召回 │  │ OpenAI/兼容     │  │
│  │  本地+云端双路执行 │  │ TTL·导出导入    │  │ Anthropic/Ollama│  │
│  └──────────────────┘  └────────────────┘  └────────────────┘  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │            安全基础设施（横切，§4.9）                        │ │
│  │  递归下降 Parser · Credential Vault · 审计哈希链 · 入参校验  │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                            │
         ┌──────────────────┴───────────────────┐
         ▼                                      ▼
   Tauri 桌面壳（主线，开发机）          PyInstaller 启动器（回退，沙箱）
   原生 WebView2 · updater · 签名        http.server 托管 dist/ + CSP 头
```

### 2.2 v1.0 → v2.0 架构对比

| 维度 | v1.0 | v2.0 |
|---|---|---|
| Agent 引擎 | `agent.ts` 单文件 166 行，硬编码 if/else | `agent/` 模块集：`registry` / `intent` / `loop` / `context` / `memory` / `kb` / `providers` |
| 工具触发 | 仅 `@` 前缀，6 个 `startsWith` | `@` 前缀 + 本地意图路由 + 云端 function calling **三入口** |
| 云端与本地 | **互斥两条路**，云端模式工具全废 | **同一份 Tool Registry 双路执行** |
| 传输 | `stream:false` 一次性 POST | SSE 流式 + `AbortController` + 30s 超时 |
| 上下文 | 全量历史，无 system prompt | 预算封顶 + system prompt + 摘要压缩 + 污染过滤 |
| 记忆 | KV 字符串，精确命中 | 类型化 + 模糊/语义召回 + TTL + 导入导出 |
| KB | 裸 `includes`，顺序优先 | 打分制 + 词边界 + `negativeKw` + 阈值 |
| 渲染 | 纯文本 + `pre-wrap` | Markdown + 代码高亮 + 复制按钮 |
| 持久化 | 每次 `setMessages` 全量同步写 | 400ms 防抖，600 次 → 1~2 次 |
| 计算 | `new Function`（unsafe-eval） | 递归下降 Parser，零 eval，CSP 兼容 |
| 交付 | PyInstaller 43.3 MiB | Tauri ~8MB 主线 + PyInstaller 回退 |

### 2.3 架构决策记录（ADR）

| ADR | 决策 | 理由 | 被否决的方案 |
|---|---|---|---|
| **ADR-01** | **统一 Tool Registry 双路复用**：本地意图路由与云端 function calling 共用同一份工具 schema | 避免"本地一套、云端另一套"双轨维护；schema 本身就是模型可读契约。**这是本次最大的结构性收益，直接消灭 D1** | 云端单独实现一套工具（双轨必然漂移） |
| **ADR-02** | **本地引擎是一等公民，云端只是更强的大脑** | 离线可用是产品定位的一部分；云不可用时代码路径完全一致，只是决策者从 LLM 换成规则 | 云端优先、本地仅作 fallback 文案 |
| **ADR-03** | **新依赖一律可选，不装即静默降级** | 沿用总纲 v8.0 原则；保证沙箱/离线/无网环境都能跑 | 强依赖 embedding 模型 |
| **ADR-04** | **`@` 前缀命令保留为快捷方式，不再是唯一入口** | 老用户习惯 + 离线确定性触发；意图路由是增量而非替换 | 直接废弃 `@` 命令（破坏性变更） |
| **ADR-05** | **零 eval 硬红线**：`@calc` 换递归下降 Parser 而非"更严的正则" | 字符级过滤无法表达语法约束（D9 的 `2**10` 即证）；且要为 CSP `script-src 'self'` 铺路 | 继续用 `new Function` + 加强正则 |
| **ADR-06** | **交付双流水线并行**，构建脚本自动探测环境 | 沙箱无 Rust/WebView2，Tauri 只能在开发机出包；两条线共用同一 `dist/`，产物等价 | 只做 Tauri（沙箱内不可构建，阻断迭代） |

---

## 3. 技术选型

### 3.1 沿用 v1.0

| 维度 | 选择 | 理由 |
|---|---|---|
| 前端框架 | Vite + React + TypeScript | 与秒哒体感一致；类型安全；构建快 |
| 设计系统 | `tokens.css` + `primitives.tsx` | 统一视觉，避免"能跑但丑" |
| Agent 逻辑 | 纯 TS 模块（浏览器内运行） | 零后端、可离线演示 |
| 窗口呈现 | pywebview（Edge/WebView2）+ 浏览器回退 | 优先嵌入式窗口，失败仍能跑 |

### 3.2 v2.0 新增

| 维度 | 选择 | 理由 | 体积影响 |
|---|---|---|---|
| Markdown 渲染 | `markdown-it` + 手写轻量高亮 | EXE 体积敏感，比 `react-markdown + rehype-highlight` 轻 | +约 30KB gzip |
| 安全计算 | **手写递归下降 Parser**（<150 行） | 零依赖、零 eval、错误可定位；`mathjs` 约 60KB gzip 为备选 | +0 |
| 意图分类 | 手写 TF-IDF + 线性打分（<100 行，`Map` 实现） | 零 npm 依赖；日后可平滑替换为 embedding | +0 |
| 语义召回 | `transformers.js`（WASM）**懒加载可选** | 仅记忆召回时按需下载；不可用则回退 TF-IDF | 0（不加载时） |
| 凭据加密 | Web Crypto AES-GCM + PBKDF2(10万次) | 浏览器原生，零依赖 | +0 |
| 审计哈希 | Web Crypto `subtle.digest` / Python `hashlib` | 同上 | +0 |
| 桌面壳（主） | Tauri 2.x | 产物 ~8MB，原生 WebView2，官方 updater + 签名 | — |
| E2E | Playwright | 补门 3 的运行时盲区（D2 即因此漏网） | 仅 CI |

**当前基线**：JS 151.8KB（gzip 51.7KB）。v2.0 预算：**gzip ≤ 90KB**。

**约束**（沿用 v1.0）：本沙箱无 Rust/WebView2，Tauri 真出包待开发机；`exe-builder` MCP 未连接时走 app-generator 的 Native 回退。

---

## 4. 模块设计

### 4.1 工具注册表 Tool Registry `新增` `src/tools/registry.ts`

**这是 v2.0 的地基**：一次定义，本地意图路由与云端 function calling 双路复用（ADR-01）。

```typescript
// src/tools/types.ts
export interface ParamSchema {
  name: string
  type: 'string' | 'number' | 'boolean' | 'object' | 'array'
  required?: boolean
  description?: string        // 同时供云端模型理解参数语义
  enum?: unknown[]
  pattern?: string
}

export interface ToolResult {
  ok: boolean
  text: string                // 用户可读结果
  data?: unknown              // 结构化数据，供 Agent Loop 回填
  render?: 'text' | 'table' | 'json'
}

export interface ToolContext {
  memory: MemoryService
  now: () => Date             // 可注入时钟，便于测试
  trace: AuditTrace           // 审计留痕
}

export interface Tool {
  name: string
  aliases: string[]           // '@calc' | '计算' | '算一下'
  description: string         // 人 / 模型双可读
  parameters: ParamSchema[]
  category: 'calc' | 'memory' | 'time' | 'system' | 'kb'
  localOnly?: boolean         // true 则不向云端暴露
  handler: (args: Record<string, unknown>, ctx: ToolContext) => Promise<ToolResult>
}
```

**内置工具清单**：

| 工具 | 参数 | 说明 | 类别 | v1.0 对应 |
|---|---|---|---|---|
| `calc` | `expr: string` | 安全算术求值（Parser，§4.9.1） | calc | `@calc` |
| `memory_write` | `key`, `value`, `type?`, `ttl?` | 写结构化记忆 | memory | `@remember` |
| `memory_read` | `key`, `fuzzy?`(默认 true) | 精确 → 模糊 → 语义召回 | memory | `@recall` |
| `memory_list` | `category?`, `limit?` | 罗列/筛选 | memory | `@list` |
| `memory_forget` | `key` | 删除 | memory | **新增** |
| `now` | — | 当前时间 | time | `@time` |
| `kb_query` | `query: string` | 知识库打分召回（§4.7） | kb | 隐式 |
| `help` | `tool?` | 由 Registry **自动生成** | system | `@help` |

**关键设计**：`help` 不再手写常量（v1.0 `agent.ts:68-77` 是硬编码数组），改为遍历 Registry 生成 —— **新增工具零成本获得帮助文档 + 云端 schema**。

**导出给云端的 schema**（OpenAI / DeepSeek / GLM 均兼容）：

```typescript
export function toOpenAITools(): OpenAITool[] {
  return registry.list()
    .filter(t => !t.localOnly)
    .map(t => ({
      type: 'function',
      function: {
        name: t.name,
        description: t.description,
        parameters: {
          type: 'object',
          properties: Object.fromEntries(t.parameters.map(p => [p.name, {
            type: p.type, description: p.description, ...(p.enum && { enum: p.enum }),
          }])),
          required: t.parameters.filter(p => p.required).map(p => p.name),
        },
      },
    }))
}
```

`calc` 的 description 必须**强制指令化**，压制模型心算冲动：

> `'计算算术表达式。任何涉及数字运算的问题都必须调用本工具，不要自行心算。'`

**验收**：8 个工具注册成功；`@help` 输出与 Registry 一致；`toOpenAITools()` 产出通过 OpenAI schema 校验。

---

### 4.2 意图路由 Intent Router `新增` `src/agent/intent.ts`

**解决 D12**：让"帮我算一下 128 除以 4"也能命中 `calc`。

三层路由，按序尝试，命中即返回：

```
routeLocal(text, history) → Intent | null
  ① 精确别名层  @calc / 计算 / 算一下 …          confidence = 1.0
  ② 分类器层    TF-IDF + 线性打分                 confidence > θ(0.6) 才采纳
                语料 = 各工具 description + 历史命中样本
  ③ 兜底层      KB 打分召回（§4.7）→ 仍未命中 → chat
```

```typescript
export interface Intent {
  tool: string
  args: Record<string, unknown>
  confidence: number
  source: 'alias' | 'classifier' | 'kb' | 'chat'
}

export function routeLocal(text: string, history: ChatMessage[]): Intent | null {
  const m = text.match(/^\s*[@＠](\w+)\s*(.*)$/)          // ① 显式命令（全角 ＠ 也认）
  if (m) return fromAlias(m[1], m[2])

  const pure = text.match(/^[\d+\-*/().\s]+$/)             // ①' 纯算术表达式直通
  if (pure) return { tool: 'calc', args: { expr: text }, confidence: 1.0, source: 'alias' }

  const best = classify(text)                              // ② TF-IDF 分类器
  if (best.score >= THRESHOLD) {
    return { tool: best.tool, args: extractArgs(best.tool, text), confidence: best.score, source: 'classifier' }
  }

  const kb = kbMatch(text)                                 // ③ KB 打分
  if (kb) return { tool: 'kb_query', args: { query: text }, confidence: kb.score, source: 'kb' }

  return null                                              // ④ 交给 chat
}
```

**参数抽取**（`extractArgs`）按工具类型走不同规则：

- `calc`：正则提取算式片段，并把中文运算词归一（`乘以`→`*`、`除以`→`/`、`加`→`+`、`减`→`-`）；
- `memory_write`：匹配 `记住/记一下 X 是 Y`、`X=Y`；
- `memory_read`：匹配 `我的 X 是什么`、`回忆 X`。

**验收**：以下自然语言均触发正确工具 —— "帮我算一下 128 除以 4"、"记住我喜欢深色主题"、"我项目叫什么来着"、"现在几点"。

---

### 4.3 Agent Loop `新增` `src/agent/loop.ts`

**解决 D1**：云端模式也能用工具。标准 tool-calling 循环，最多 5 轮防死循环。

```
构造上下文（§4.5）
   │
   ▼
云端可用？
 ├─ 否 → 本地：routeLocal → 命中则执行工具 → 未命中则 KB/兜底
 └─ 是 → POST stream:true + tools:toOpenAITools()
          │
          ├ finish_reason === 'tool_calls'
          │    → 逐个 validateArgs → registry.get(name).handler(args, ctx)
          │    → 以 { role:'tool', tool_call_id, content } 追加
          │    → round++ ；round < 5 则回到 POST
          │
          └ 否 → SSE 逐 delta 回调 onToken 上屏，结束
```

```typescript
export interface AgentOutput {
  text: string
  toolCalls: ExecutedCall[]
  fromCloud: boolean
  degraded?: boolean          // 云端回退本地时置 true（消息打 meta.error，不进下轮上下文）
}

export async function runAgentV2(
  userText: string,
  history: ChatMessage[],
  cfg: AgentConfig,
  ctx: AgentContext,
  onToken?: (delta: string) => void,
  signal?: AbortSignal,
): Promise<AgentOutput>
```

**降级策略**（针对不支持 function calling 的模型）：首次带 `tools` 请求返回 400 → **自动去掉 `tools` 重试一次**，并把该 `model` 记入 `localStorage` 的 `no-tools-models` 集合，后续直接跳过 —— 只付一次探测成本。

**验收**：
- 云端模式下 `@calc (12+8)*3` 走本地执行返回 **`60`**（非模型心算）；
- 云端模式下 `@remember 项目=X` **真实写入** localStorage，`@recall 项目` 能查到；
- "先算 15*8 再把结果记成 预算" 两段式任务一次完成；
- 对不支持 tools 的模型自动降级，只报一次 400。

---

### 4.4 Provider 适配层 `新增` `src/providers/`

**解决 D2 的前半（假打字机）与 D6（无超时无取消）。**

```typescript
export interface ProviderAdapter {
  id: 'openai' | 'anthropic' | 'ollama'
  chatStream(
    req: { messages: ChatMessage[]; tools: ToolDefForModel[]; signal: AbortSignal },
    onToken: (delta: string) => void,
    onToolCall?: (call: ToolCall) => void,
  ): Promise<{ finishReason: string }>
}
```

| Provider | 端点 | 工具调用 | 流式格式 |
|---|---|---|---|
| OpenAI 兼容 | `POST {base}/chat/completions` | `tools` 参数 + `tool_calls` 响应 | SSE |
| Anthropic | `POST /v1/messages` | `tools` + `tool_use` content block | SSE |
| Ollama（本地） | `POST /api/chat` | `tools` 参数 | NDJSON |

**三级回退链**：`云端(已配置) → Ollama(本机探测到 11434 端口) → 本地引擎`。

**超时与取消**（D6）：

```typescript
const ac = new AbortController()
const timer = setTimeout(() => ac.abort('timeout'), 30_000)
// UI "停止生成" 按钮同样调 ac.abort('user')
```

**错误分类**（D3-4）：

| HTTP / 异常 | 用户可见提示 |
|---|---|
| 401 / 403 | 密钥无效或无权限，请检查设置里的 API Key |
| 429 | 触发限流，N 秒后自动重试 |
| 400（上下文超长） | 上下文过长，已自动压缩并重试 |
| 404 | 模型名不存在，请检查设置 |
| AbortError(timeout) | 云端 30 秒未响应，已回退本地引擎 |
| AbortError(user) | （静默，不产生错误消息） |
| 网络 / 解析失败 | 云端连接失败，已回退本地引擎 |

**验收**：mock 一个 OpenAI 兼容 stub 服务器，注入上述 6 类故障，逐一断言提示文案与降级行为。

---

### 4.5 上下文构造器 `新增` `src/agent/context.ts`

**解决 D3**：把 O(n²) 压成常数上限。

**核心原则：请求 payload 与落盘 messages 分离。** `App.tsx` 的 `messages` 是完整 UI 状态，发给模型的是**重新构造**的 payload。

```
payload = [SYSTEM_PROMPT]
        + (可选) 历史摘要消息        // 更早对话压成 ≤200 字
        + 最近 N 轮                  // N 由字符预算动态确定，默认 6000 字符
```

```typescript
export const BUDGET_CHARS = 6000

export function buildPayload(messages: ChatMessage[], cfg: AgentConfig): ChatMessage[] {
  const clean = messages.filter(m => !m.meta?.error && !m.meta?.local)   // 污染过滤（D3-3）
  const out: ChatMessage[] = [{ role: 'system', content: SYSTEM_PROMPT }]

  let used = SYSTEM_PROMPT.length
  const tail: ChatMessage[] = []
  for (let i = clean.length - 1; i >= 0; i--) {              // 从最近往前塞
    const len = clean[i].content.length
    if (used + len > BUDGET_CHARS) break
    used += len; tail.unshift(clean[i])
  }
  const dropped = clean.length - tail.length
  if (dropped > 0) out.push({ role: 'system', content: `[更早对话摘要] ${getSummary(clean.slice(0, dropped))}` })
  return out.concat(tail)
}
```

**消息 meta 标记**（新增字段，向后兼容）：

```typescript
export type ChatMessage = {
  role: Role
  content: string
  meta?: { local?: boolean; error?: boolean; degraded?: boolean; ts?: number }
}
```

带 `error` / `local` 标记的消息**只在 UI 显示，不进上下文** —— 消灭 D3-3 的污染回流。

**SYSTEM_PROMPT 常量**（抽出为单一事实源，解决 D3-2）：身份定位、中文优先、简洁克制、**工具调用规则（算术必须调 calc，不得心算）**、不确定时明确说不知道、拒答边界。

**成本可见**：UI 右下角角标显示"本轮约 X tokens"（按 `chars/1.5` 粗估中文）。

**验收**：模拟 50 轮对话，断言**任意一轮 payload 字符数 ≤ 6200**（预算 + system 余量）；断言带 `error` 标记的消息不出现在 payload 中。

---

### 4.6 记忆系统 v2 `重构` `src/agent/memory.ts`

**存储键空间保持 `miaoda-agent-note:*`，向后兼容 v1.0 旧数据。**

```typescript
export type MemType = 'fact' | 'preference' | 'todo' | 'context'

export interface MemEntry {
  id: string              // key 规范化哈希，便于去重/重命名
  key: string
  type: MemType
  value: string
  ts: number              // 首次写入
  updatedAt: number
  ttl?: number            // 秒；过期条目读取时惰性清理
  source: 'manual' | 'extracted'
  tags?: string[]
  embedding?: number[]    // 可选
}

export class MemoryService {
  write(k: string, v: string, opts?: Partial<MemEntry>): MemEntry
  read(k: string, opts?: { fuzzy?: boolean }): MemEntry | null
  search(q: string, opts?: { type?: MemType; limit?: number }): MemEntry[]
  remove(k: string): boolean
  pruneExpired(): number
  export(): string        // JSON
  import(json: string): number
}
```

**v1.0 数据迁移**：读到 `miaoda-agent-note:<k>` 为**裸字符串**时，自动包装为 `{ type:'fact', ts: now, updatedAt: now, source:'manual' }` 并回写。旧命令行为完全不变。

**渐进式召回**（ADR-03）：

```
read(key, { fuzzy: true }) →
  ① 精确键命中                        → 返回
  ② 子串 / 编辑距离近似命中             → 返回 + 标记 fuzzyMatch
  ③ 语义召回（若已注入向量器）Top-k     → 返回 + 标记 semanticMatch
  ④ 未命中                            → "没找到关于「X」的记忆，试试 memory_list"
```

第 ③ 步的向量器优先 `transformers.js`（WASM 懒加载），不可用回退 TF-IDF，再不行**直接跳过** —— 不装不崩。

**生命周期**：

| 能力 | 实现 |
|---|---|
| 过期清理 | `ttl` 到期条目在 `read`/`list` 时惰性删除 |
| 去重合并 | 同 key 写入更新 `updatedAt`；`id` 相同合并 `tags` |
| 导出/导入 | JSON（可选加密），为多端同步打基础 |
| 统计 | 条目数 / 类型分布 / 最近写入 |

**验收**：v1.0 旧数据自动迁移且 `@recall` 行为不变；TTL 到期自动消失；导出后清空再导入，条目完全一致。

---

### 4.7 知识库召回打分 `重构` `src/agent/kb.ts`

**解决 D4**（实测 57% 误命中率）。约 30 行，零依赖。

```typescript
interface KBItem {
  kw: string[]
  negativeKw?: string[]     // 反例词：命中则本项直接出局
  exactOnly?: string[]      // 短词强制词边界匹配
  answer: string
}
```

**打分规则**：

1. 中文按 **2-gram** 切分，英文按词边界 `\b` 匹配；
2. 命中词**按长度加权**（长词权重高）：`score += kw.length`；
3. `exactOnly` 词（`ts` / `hi` / `etf`）**强制 `\b` 边界**，`GPTs` 不再命中 `ts`；
4. `negativeKw` 命中 → 本项得分归零（TypeScript 项排除 `gpts`、`hits`、`gpt`）；
5. 取**全局最高分**（不再是数组顺序优先）且需 **超过阈值** 才返回，否则走兜底。

```typescript
export function kbMatch(text: string): { answer: string; score: number } | null {
  const lower = text.toLowerCase()
  let best: { answer: string; score: number } | null = null
  for (const item of KB) {
    if (item.negativeKw?.some(n => lower.includes(n))) continue
    let score = 0
    for (const k of item.kw) {
      const isShort = item.exactOnly?.includes(k)
      const hit = isShort ? new RegExp(`\\b${k}\\b`).test(lower) : lower.includes(k)
      if (hit) score += k.length
    }
    if (score > (best?.score ?? 0)) best = { answer: item.answer, score }
  }
  return best && best.score >= KB_THRESHOLD ? best : null
}
```

**验收**：§1.4 D4 表格的 7 条测试用例 **7/7 正确**（4 条误命中全部消除），且 5 条正向查询（"介绍一下 React 组件"/"TypeScript 的类型系统"/"你好"/"ETF 怎么选"/"秒哒是什么"）**5/5 未被误伤**。

> **已实测通过**（`v2.0方案_修复验证.mjs` 验证一）：v1.0 为 3/7，v2.0 为 7/7。此两张表固化为回归用例。

---

### 4.8 前端 v2 `重构` `src/App.tsx`

这是 **P0 优先级**，改动量最小、见效最快。

#### 4.8.1 防抖落盘（修 D2）

```typescript
const saveRef = useRef<number>()
useEffect(() => {
  clearTimeout(saveRef.current)
  saveRef.current = window.setTimeout(
    () => localStorage.setItem(MSG_KEY, JSON.stringify(messages)), 400)
  return () => clearTimeout(saveRef.current)
}, [messages])
```

> **实测效果（§0.4）：一条 600 字回复的写入次数 600 → 1 次，序列化 3.986 MB → 0.007 MB，降幅 99.8%。**

**为什么是防抖而非节流**：流式 tick 间隔 14ms 远小于 400ms，防抖定时器被持续重置，全程仅在流结束后落盘一次；节流会在流期间每 400ms 强制写一次（实测 22 次），性能可接受但无必要。
**代价与兜底**：极端情况下（浏览器在流式中途崩溃）最多丢失一条未完成回复。若要更稳，可加 `maxWait: 3000`（最长 3 秒必落盘一次），写入次数仍 ≤ 4。

#### 4.8.2 真流式渲染（修 D2 前半）

- **云端**：`stream:true`，`onToken` 直接追加，**删除假打字机**；
- **本地**：引擎输出是瞬时的，**保留** 14ms 打字机做质感（配合防抖落盘已无性能问题）。

> **效果：TTFT 从"全量生成时间（5~20s）+ 8.4s 打字"降到 < 1s。**

#### 4.8.3 停止生成（修 D6）

输入区在 `loading` 时把「发送」换成「⏹ 停止」，调 `abortRef.current?.abort('user')`；`clearChat` 时也中断未完成请求。

#### 4.8.4 智能滚动（修 D7）

```typescript
const atBottom = () => {
  const el = scrollerRef.current!
  return el.scrollHeight - el.scrollTop - el.clientHeight < 80
}
useEffect(() => { if (stickRef.current) bottomRef.current?.scrollIntoView({ behavior: 'auto' }) }, [messages])
// onScroll: stickRef.current = atBottom()
```

只有用户贴底时才自动跟随；上滑回看历史不再被拽回。

#### 4.8.5 Markdown 渲染（修 D8）

`{m.content}` → `<Markdown source={m.content} />`：

- `markdown-it` 解析，`DOMPurify` 或 `markdown-it` 自带 `html:false` 防 XSS；
- 代码块加**语言标签 + 复制按钮**；
- 表格 / 列表 / 引用套用设计令牌样式。

#### 4.8.6 消息级操作 `新增`

每条助手消息悬浮显示：**复制 / 重新生成 / 删除单条**；失败消息（`meta.error`）额外显示「重试」。

**验收**：Playwright 断言 —— 流式期间 console 无 error；上滑后不被拽回；Markdown 代码块正确高亮；停止按钮可中断。

---

### 4.9 安全基础设施 `新增` `src/security/`

#### 4.9.1 递归下降 Parser 替代 `new Function`（修 D9 D10）

`safe-calc.ts`，约 150 行，文法：

```
expr   := term (('+' | '-') term)*
term   := factor (('*' | '/' | '%') factor)*
factor := NUMBER | '(' expr ')' | ('+' | '-') factor
```

- **零 eval**：AST 节点类型只允许 `Number` / `BinaryOp` / `Unary` / `Paren`；
- **CSP 安全**：可开启 `script-src 'self'` 不崩溃（ADR-05）；
- **`2**10` 明确报错**"不支持运算符 `**`"，而非意外求值为 1024；
- **错误可定位**："第 5 个字符处缺少右括号"；
- **除零明确提示**"除数不能为 0"，而非笼统的"算不出来"（修 D10）；
- 入口**保留**字符白名单正则作双保险；
- 可受控扩展 `%`、`^`、`sqrt()`——扩展走文法而非放宽正则。

**绝对禁用清单**：`Function`、`eval`、`new Function`、`setTimeout(string)`、`__proto__`、属性访问、标识符、模板字符串。

#### 4.9.2 凭据保险库 Credential Vault（修 D11）

| 形态 | 实现 |
|---|---|
| 网页预览 | Web Crypto AES-GCM；密钥由用户口令经 PBKDF2（10 万次迭代 + 随机 salt）派生；**密文**存 `localStorage`。不设口令则提示"Key 将以明文弱存"并默认关闭云端 |
| EXE 形态 | pywebview 桥接 **Windows Credential Manager / DPAPI**：`launcher.py` 暴露 `vault.save/get/delete`，Key **完全不落前端** |
| 临时模式 | 新增"仅本次会话保存"开关 → 走 `sessionStorage` |

**UI**：Key 输入框已是 `type="password"`（v1.0 就对，见 §0.3），v2.0 追加**只显示后 4 位**的掩码回显。

#### 4.9.3 审计哈希链（tamper-evident）

v1.0 明文 `audit.md` 升级为哈希链：

```
entry = { seq, ts, event, data, prevHash }
hash  = SHA-256( prevHash + canonicalJSON({ seq, ts, event, data }) )
```

- 每个事件（工具调用、云端连接、凭据变更、设置修改）追加一条；
- 浏览器用 `crypto.subtle.digest`，EXE 用 Python `hashlib` 兜底；
- 自检：启动时或 `@audit` 命令重算全链，任一断裂即报"审计记录被篡改"。

> MCP 未连接时即具备防篡改能力；连接 `exe-builder` 后接入正式审计脊柱。

#### 4.9.4 其余加固

- `launcher.py` 增加响应头：`Content-Security-Policy`、`X-Content-Type-Options: nosniff`、`Referrer-Policy: no-referrer`；
- 本地 HTTP 服务加**一次性 URL token 校验**（修 D13）；
- 工具入参统一走 `validateArgs(tool, args)`（schema + 白名单），handler 不自行信任入参。

---

### 4.10 设计系统 `沿用`

- `tokens.css`：间距/圆角/颜色/阴影/字体令牌，亮暗双主题。
- `primitives.tsx`：`Container / AppBar / Card / Button / Stack / Row / SectionTitle`。
- **v2.0 新增令牌**：`--code-bg`、`--code-border`、`--md-quote`、`--danger`（错误消息与重试按钮用）。

---

## 5. 功能规格 v2.0

| # | 功能 | 状态 |
|---|---|---|
| 1 | 本地引擎对话（内置知识库） | 沿用 |
| 2 | `@` 前缀工具命令 | 沿用（不再是唯一入口） |
| 3 | **自然语言触发工具**（"帮我算一下 128 除以 4"） | **新增** |
| 4 | **云端模式下工具依然可用**（function calling） | **修复 D1** |
| 5 | **流式输出 + 停止生成** | **修复 D2/D6** |
| 6 | **Markdown 渲染 + 代码高亮 + 复制** | **修复 D8** |
| 7 | **上下文预算 + 错误分类提示** | **修复 D3** |
| 8 | **KB 打分召回**（7/7 正确） | **修复 D4** |
| 9 | **类型化记忆 + 模糊召回 + TTL + 导入导出** | **新增** |
| 10 | **凭据加密存储 / 仅本次会话** | **修复 D11** |
| 11 | **审计哈希链 + 自检** | **新增** |
| 12 | 主题切换、清空对话、会话持久化 | 沿用（持久化改防抖） |

---

## 6. 质检体系 v2

### 6.1 六门对照

| 门 | 名称 | v1.0 结果 | v2.0 增强 | v2.0 目标 |
|---|---|---|---|---|
| 1 | 静态检查 | ✅ `tsc --noEmit` 0 错误 | 同左（strict + noUnusedLocals/Params） | ✅ 0 错误 |
| 2 | 构建 | ✅ JS 151.8KB (gzip 51.7KB) | 新增体积红线告警 | ✅ gzip ≤ 90KB |
| 3 | 运行时冒烟 | ✅ curl 拿 200 | **+ Playwright 真浏览器** | ✅ console 无 error |
| 4 | 多 Agent 复核 | ⏭️ 默认跳过 | **对 `agent/` 与 `security/` 必跑** | ✅ 通过 |
| 5 | 安全扫描 | ✅ 无硬编码密钥 | + eval 静态禁用规则 + 恶意输入用例集 | ✅ 通过 |
| 6 | 评分卡 | ✅ 70/100（刚过线） | + Lighthouse + `scripts/scorecard.ts` | ✅ **≥ 85** |

### 6.2 门 3 为什么必须升级 `关键教训`

> v1.0 门 3 = `serve dist + curl 拿 200`。**它测不到任何运行时 JS 错误。**
>
> **D2（localStorage 写放大）就是明证：六门全绿，bug 照样在线上跑。**

Playwright 冒烟必须断言的项：

| 断言 | 对应缺陷 |
|---|---|
| 页面加载后 `console` 无 `error` 级日志 | 通用 |
| 发送消息后助手气泡**真实渲染出文本** | 通用 |
| 流式期间主线程无长任务 > 100ms | D2 |
| 上滑后新消息到达**不被拽回底部** | D7 |
| Markdown 代码块渲染为 `<pre><code>` 而非裸字符 | D8 |
| 点击「停止」后请求真实中断 | D6 |
| 主题切换 `documentElement.classList` 正确变化 | 通用 |

---

## 7. 打包交付 v2

### 7.1 现状基线（v1.0 实测）

- 产物：`AI助手.exe`，**45,375,288 字节 = 43.3 MiB (45.4 MB)**，PE/MZ 有效；
- `--onefile` 每次启动解压归档到 `%TEMP%\_MEIxxxxx`，**冷启动 3~8 秒**，易被杀软/SmartScreen 误报；
- 冒烟：`AGENT_EXE_TEST=1` 无界面钩子 + curl → **EXE_SMOKE=PASS**。

### 7.2 Tauri 主流水线（开发机）

```text
agent-app/
├── src-tauri/               # Tauri 2.x
│   ├── Cargo.toml
│   ├── tauri.conf.json      # bundle > icon / productName / version
│   ├── capabilities/        # 权限（默认关闭网络）
│   └── src/main.rs          # 壳 + credential vault 桥接
└── dist/                    # React 构建产物（双线共用）
```

| 项 | 值 |
|---|---|
| 产物体积 | ~8MB（预期，约为 v1.0 的 1/5） |
| 前置条件 | 开发机 Rust 工具链 + WebView2（沙箱无，故在开发机出包） |
| 构建 | `npm run tauri build`（`vite build` → `cargo build --release` → bundle） |
| 桥接 | `vault.save/get/delete`、`app.update` |

### 7.3 PyInstaller 回退流水线（沙箱内）

沿用 v1.0 命令，改造点：`launcher.py` 增加 vault 桥接、安全响应头、一次性 token 校验。

```bash
PyInstaller --noconfirm --onefile --windowed --name "AI助手" \
  --distpath build_exe --workpath build_exe/work --specpath build_exe \
  --add-data "agent-app/dist;webdist" --hidden-import webview \
  --version-file build_exe/version.txt --icon build_exe/app.ico \
  build_exe/launcher.py
```

#### ⚠️ 瘦身红线（务必遵守）

加 `--exclude-module` 前**必须先做 import 扫描**，只砍确认无引用的（`tkinter` / `test` / `pydoc` / `distutils`）。

> **必须保留 `unittest`。**
> 历史教训：**FinancialTrader v5.1 正是因 spec 的 excludes 过度裁剪，导致运行时 `No module named unittest` 崩溃。** 同类错误不得重犯。

裁剪后**必须重跑 EXE 冒烟**，不允许"改了 spec 直接发"。

### 7.4 分发体验

| 能力 | 实现 |
|---|---|
| 冷启动 | 评估 `--onedir` + Inno Setup 安装包，目标 < 1s |
| 自动更新 | Tauri 官方 updater（公钥内嵌）；或自定义 JSON 清单（`version` + `url` + `sha256`） |
| 代码签名 | 开发期自签 + 发布期 Windows OV 证书，Tauri 挂接 `signtool` |
| 元数据 | `--version-file` + 自定义图标，显著降低 SmartScreen 误报 |

### 7.5 双线构建脚本

`scripts/build.py` 统一入口：探测环境 → 有 Rust/WebView2 走 Tauri，否则走 PyInstaller，**同一 `dist/` 双线出包，产物功能等价**（ADR-06）。

---

## 8. 验证矩阵

| 层 | 方法 | 覆盖 |
|---|---|---|
| 单元 | Vitest | 意图路由、各工具 handler、记忆生命周期、Parser、哈希链、KB 打分 |
| 集成 | Node + `localStorage` 垫片（沿用 v1.0 手法） | Agent Loop 多轮、tool_calls 回灌、云端 mock 故障降级 |
| 组件 | Vitest + Testing Library | 流式渲染、防抖落盘、设置面板、主题 |
| E2E | Playwright | §6.2 全部断言项 |
| 安全 | 恶意输入用例集 + `npm audit` | eval 拒绝（≥20 例）、凭据密文、审计防篡改 |
| 性能 | Lighthouse + 自定义指标 | TTFT、写入次数、payload 字符数 |

### 8.0 已就绪的验证资产

| 脚本（与本文档同目录） | 作用 | 当前结果 |
|---|---|---|
| `优化方案_问题验证.mjs` | 复现 v1.0 的缺陷（写放大 / KB 误命中 / O(n²) 上下文） | 全部复现 |
| `v2.0方案_修复验证.mjs` | 证明 v2.0 四项核心修复有效（附 v1.0/v2.0 对照） | **8/8 通过** |

两个脚本零依赖，`node <文件名>` 直接跑。实施期间应把它们迁入 `agent-app/tests/` 作为 Vitest 用例的基础。

### 8.1 回归红线（不可协商）

1. **v1.0 的 17/17 断言全量保留**，原用例只增不改、不允许删除；
2. **§1.4 D4 的 7 条 KB 用例**固化为回归用例，必须 7/7；
3. **写入次数断言**：一条 600 字回复触发 `localStorage.setItem` **≤ 3 次**；
4. **payload 上限断言**：50 轮对话中任意一轮 payload **≤ 6200 字符**；
5. **eval 静态断言**：全量源码 grep 不得出现 `new Function` / `eval(`。

---

## 9. 文件清单 v2.0

```
agent-app/
├── index.html
├── package.json / vite.config.ts / tsconfig.json
├── src/
│   ├── main.tsx
│   ├── App.tsx                    # 聊天 UI（流式/Markdown/防抖/智能滚动/停止）
│   ├── agent/                     # ← v1.0 的 agent.ts 拆分
│   │   ├── index.ts               # runAgentV2 统一出口
│   │   ├── loop.ts                # Agent Loop（tool-calling 循环）
│   │   ├── intent.ts              # 意图路由（别名 / TF-IDF / KB）
│   │   ├── context.ts             # 上下文构造器 + SYSTEM_PROMPT
│   │   ├── memory.ts              # MemoryService v2
│   │   └── kb.ts                  # 知识库打分召回
│   ├── tools/
│   │   ├── types.ts               # Tool / ParamSchema / ToolResult
│   │   ├── registry.ts            # 注册表 + toOpenAITools()
│   │   └── builtin/               # calc / memory_* / now / kb_query / help
│   ├── providers/
│   │   ├── types.ts               # ProviderAdapter
│   │   ├── openai.ts / anthropic.ts / ollama.ts
│   │   └── index.ts               # 三级回退链
│   ├── security/
│   │   ├── safe-calc.ts           # 递归下降 Parser（零 eval）
│   │   ├── vault.ts               # 凭据保险库
│   │   └── audit.ts               # 哈希链
│   └── ui/
│       ├── tokens.css             # 设计令牌（+ 代码块令牌）
│       ├── primitives.tsx
│       └── Markdown.tsx           # ← 新增
├── tests/                         # Vitest 单元 / 集成
├── e2e/                           # Playwright
├── scripts/
│   ├── build.py                   # 双线构建统一入口
│   └── scorecard.ts               # 门 6 自动评分
├── src-tauri/                     # Tauri 2.x 壳（开发机）
├── build_exe/
│   ├── launcher.py                # + vault 桥接 / CSP / token 校验
│   └── version.txt / app.ico      # ← 新增
├── dist/
├── .snapshots/
├── audit.md → audit.jsonl         # ← 升级为哈希链
└── qa-report.html
```

**新增文件 21 个，重构 2 个（`agent.ts` 拆分、`App.tsx` 改造），删除 0 个。**

---

## 10. 分阶段实施计划

> 原则：每阶段**可独立交付、独立验收、可回退**；新依赖全部可选，不装即静默降级。

### Phase 0 — 止血（第 1 周）`P0`

优先修**已实测的真实 bug**，改动量最小、见效最快。

| 任务 | 文件 | 验收 |
|---|---|---|
| P0-1 防抖落盘 | `App.tsx:42` | 600 字回复写入 ≤ 3 次（自动化断言） |
| P0-2 智能滚动 | `App.tsx:50-52` | 上滑后不被拽回 |
| P0-3 AbortController + 30s 超时 + 停止按钮 | `App.tsx` / `agent.ts:142` | 可随时中断；hang 住地址 30s 自动降级 |
| P0-4 递归下降 Parser | `src/security/safe-calc.ts` | v1.0 的 17 条断言全过 + 20 条恶意输入全拒（含 `2**10`） |
| P0-5 KB 打分召回 | `src/agent/kb.ts` | §1.4 D4 的 7 条用例 7/7 |

**验收**：`tsc --noEmit` 0 错误；`npm run build` 通过；门 1/2/3 全绿。

> **本阶段仅 P0-1 就能让长对话不卡顿，是全文性价比最高的十几行代码。**

### Phase 1 — Agent 引擎 v2（第 2–4 周）`P0`

| 任务 | 文件 | 验收 |
|---|---|---|
| P1-1 Tool Registry | `src/tools/*` | 8 个工具注册；`@help` 自动生成；schema 校验通过 |
| P1-2 意图路由 | `src/agent/intent.ts` | 4 条自然语言用例（§4.2）全部触发正确工具 |
| P1-3 Agent Loop + function calling | `src/agent/loop.ts` | **云端模式 `@calc` 走本地执行、`@remember` 真实落盘** |
| P1-4 上下文构造器 | `src/agent/context.ts` | 50 轮 payload ≤ 6200 字符；污染消息不入上下文 |
| P1-5 记忆服务 v2 | `src/agent/memory.ts` | 类型化/模糊/TTL/导入导出全过；v1.0 数据自动迁移 |

**验收**：功能断言 ≥ 35（含 v1.0 的 17 条）；门 4 对 `agent/` 跑第二模型复核。

### Phase 2 — 云端与体验（第 5–7 周）`P1`

| 任务 | 文件 | 验收 |
|---|---|---|
| P2-1 Provider 适配层 | `src/providers/*` | 三适配器接口一致；三级回退链可用 |
| P2-2 SSE 真流式 | `App.tsx` + providers | TTFT < 1s；逐 token 上屏 |
| P2-3 Markdown 渲染 | `src/ui/Markdown.tsx` | 代码高亮 + 复制；gzip 增量 ≤ 35KB |
| P2-4 错误分类 + 消息级操作 | `App.tsx` | 6 类故障提示各不相同；复制/重生成/删除可用 |

**验收**：mock stub 驱动全链路自动化；手动断网验证降级。

### Phase 3 — 安全与交付（第 8–10 周）`P2`

| 任务 | 验收 |
|---|---|
| P3-1 凭据保险库 | Key 密文落盘；EXE 走 DPAPI；无口令时明确降级提示 |
| P3-2 审计哈希链 | 篡改任一条日志后自检报警 |
| P3-3 CSP + 安全头 + token 校验 | curl 响应头含 CSP；**开启 CSP 后应用不崩**（Parser 已就位） |
| P3-4 Tauri 壳 + 双线构建 | 出包 ~8MB；`scripts/build.py` 环境探测正确 |
| P3-5 更新 + 签名 + 元数据 | 自签通过；更新清单校验成功；SmartScreen 告警减少 |
| P3-6 质检补齐 | Playwright 冒烟过；Lighthouse ≥ 85/90/90；评分卡 ≥ 85 |

### 里程碑

| 里程碑 | 时间 | 交付物 |
|---|---|---|
| **M0 止血** | 第 1 周末 | 性能 bug 修复版，长对话不卡、可中断、计算安全 |
| **M1 真 Agent** | 第 4 周末 | 云端模式工具可用；自然语言触发；上下文受控 |
| **M2 体验达标** | 第 7 周末 | 流式 + Markdown + 错误分类，观感从 Demo 跨到产品 |
| **M3 正式可发** | 第 10 周末 | Tauri 产物 + 更新/签名 + 六门全绿（评分 ≥ 85） |

---

## 11. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| Tauri 在沙箱不可构建 | M3 延迟 | PyInstaller 回退线保底；开发机出包（ADR-06） |
| 部分模型不支持 function calling | 云端工具失效 | 首次 400 自动降级为纯对话并记住该模型（§4.3） |
| 各供应商 tool 协议差异大 | 集成复杂 | Provider 适配层隔离协议；mock stub 先行 |
| `transformers.js` 体积大 | 首屏变慢 | 懒加载，仅记忆召回时按需下载；不可用回退 TF-IDF |
| Web Crypto 在某些 WebView 不可用 | 凭据无法加密 | 明确降级提示 + 默认关闭云端；EXE 走系统凭据管理器 |
| Markdown 渲染引入 XSS | 安全 | `html:false` + DOMPurify 双保险 |
| **EXE 瘦身过度裁剪** | **运行时崩溃** | **保留 `unittest`；先 import 扫描再 exclude；裁剪后必重跑冒烟（§7.3）** |
| 摘要压缩丢失关键上下文 | 回答质量下降 | 摘要只压缩超出预算的**最早**部分；最近 N 轮永远原文保留 |

---

## 12. 限制与诚实说明

- **审计**：`exe-builder` MCP 未连接时为本地哈希链（已具防篡改能力，但非中心化脊柱）；连接后接入正式审计脊柱。
- **出 EXE**：沙箱无 Rust/WebView2，Tauri 真出包待开发机；PyInstaller 线属等效可运行交付。
- **~8MB 是预期值**，未实测；Tauri 实际产物受依赖与图标资源影响。
- **门 4 / Lighthouse** 依赖第二模型与 CI 环境，沙箱内为可选增强。
- **云端**：默认本地引擎；填云端信息后依赖外部接口可达性；Key 加密强度取决于用户口令质量。
- **本文档中标注"实测"的数据**均由 `优化方案_问题验证.mjs`（v1.0 问题复现）与 `v2.0方案_修复验证.mjs`（v2.0 修复验证，8/8 通过）可复现；标注"预期"的为设计估算，**未经验证，不得当作事实引用**。
- **§0.3 已列出并更正三处我方口径/笔误**（EXE 单位、Key 输入框、`(12+8)*3` 的值），其余数据复核无误。
- **修复验证是逻辑等价模拟，非真实浏览器运行**：防抖/预算/Parser/KB 打分的算法行为已验证正确，但真实 React 环境下的表现仍须 Phase 0 落地后由 Playwright 复核。

---

## 13. 总结

> **AI.Super Agent v2.0** = 统一 Tool Registry（一次定义，本地/云端双路执行）＋ 意图路由 + Agent Loop（tool-calling 循环）＋ 上下文预算治理 ＋ 类型化记忆 ＋ KB 打分召回 ＋ Provider 适配层（SSE 流式 + 三级回退）＋ 前端体验修复（防抖/智能滚动/Markdown/可中断）＋ 安全横切（零 eval Parser / 凭据保险库 / 审计哈希链）＋ 双流水线交付。

**相对 v1.0 的关键跃迁**：

| | v1.0 | v2.0 |
|---|---|---|
| 定位 | 带命令行工具的聊天框 | 真正的 Agent（LLM 决策 + 代码确定性执行） |
| 云端模式 | 工具全废，越用越"笨" | 工具全在，算术零幻觉 |
| 长对话 | O(n²)，越聊越卡、越贵、终会变傻 | 常数成本上限，行为稳定 |
| 质检 | 六门全绿但测不到运行时 bug | Playwright 补齐运行时盲区 |
| 安全 | `unsafe-eval` + 明文 Key | 零 eval + 加密凭据 + 防篡改审计 |

**14 项缺陷（§1.4）逐项闭环，六门质检由 5/6、评分 70 提升至目标 6/6、评分 ≥ 85。**

**实施主线**：Phase 0 止血（第 1 周）→ Phase 1 真 Agent（2–4 周）→ Phase 2 体验（5–7 周）→ Phase 3 安全与交付（8–10 周），每阶段独立验收、可回退。

> **如果只做一件事**：先改 `App.tsx:42` 的防抖落盘（十几行），一条 600 字回复的写盘**实测从 600 次降到 1 次、序列化 3.986MB 降到 0.007MB**，改完立刻能感觉到。

---

*— 本文档在 v1.0 真实实现与 v1.1 逐行审查证据基础上收敛为一套内聚架构。缺陷侧数据由 `优化方案_问题验证.mjs` 复现，修复侧有效性由 `v2.0方案_修复验证.mjs` 验证（8/8 通过）；文档自身的三处口径错误已在 §0.3 公开更正。所有接口、数据结构、验收标准均按可落地粒度给出，读文档即可开始实施。*


---

# Part II — 能力扩展（v3.0 · 七项新能力）　📐 设计 / 可行性已验证

> v3.0 能力扩展版全文。七项能力（F1 联网搜索 / F2 Skills / F3 MCP / F4 国内大模型 / F5 记忆 v3 / F6 ReAct 推理 / F7 Claude 风格输出）架构已设计、可行性已验证；具体功能断言以回归测试为准。

# AI.Super Agent（Agent 应用）— 工程技术文档 v3.0

> **文档版本**：v3.0（能力扩展版 · 实施级）
> **上一版**：v2.0（2026-08-01，架构升级版 · 实施级，含 14 项缺陷闭环）
> **升级依据**：《AI.Super Agent_工程技术文档 v2.0》——已实测的缺陷台账 + 修复验证（8/8）
> **源码位置**：`C:\Users\Administrator\WorkBuddy\秒哒\agent-app\`（目标布局见 §14）
> **所属能力**：WorkBuddy 框架内复刻「秒哒」——app-generator 编排大脑 + exe-builder MCP 引擎 + 设计系统
> **对应场景**：场景 #17「Agent 应用」
> **日期**：2026-08-01
> **状态**：v2.0 已实施；v3.0 七项能力架构已设计、可行性已验证；具体功能断言以回归测试为准。本文档作为可行性基线 Part II。

---

## 0. 本次升级概述

### 0.1 一句话

v2.0 解决了**产品内核**（把"带命令行工具的聊天框"变成 Agent），v3.0 补齐**产品边界**——让它"能查（联网）、能扩展（Skills/MCP）、能接入国内模型、记得住、会推理、输出像样"。

### 0.2 v2.0 → v3.0 变更摘要

| 章节 | v2.0 | v3.0 变化 |
|---|---|---|
| §2 架构 | Tool Registry + Agent Loop | 升级为 **ReAct 推理引擎**（Thought/Action/Observation），工具面扩展 **Web / Skills / MCP 三入口** |
| §3 选型 | 零依赖优先 | 新增可插拔体系：Skills 目录规范、MCP 客户端、搜索提供商适配 |
| §4 模块 | 10 模块 | 扩为 **17 模块**（新增 reasoning / search / skills / mcp / providers 扩展） |
| §5 功能 | 12 项 | 扩为 **22 项**，区分"沿用 / 增强 / 新增" |
| §6 质检 | 六门 | 六门保留 + 新增 **Skill/MCP 安全门**（外部代码执行审查） |
| §7 打包 | 双流水线 | + **本地桥进程**（承载 MCP stdio / 联网抓取 / 系统凭据） |
| §8 验证 | 六层矩阵 | 扩为 **七层**（+ Skill/MCP 集成测试） |
| §15 实施 | Phase 0~3（10 周） | 扩为 **Phase 0~4（14 周）** |

### 0.3 七项新功能概览

| # | 新功能 | 一句话 | 对应能力域 |
|---|---|---|---|
| F1 | **联网搜索** | 对话中按需调 `web_search`，结果带来源引用，离线自动降级 | §4 |
| F2 | **Skills** | 可插拔技能包：丢一个目录即获得新能力，不写代码 | §5 |
| F3 | **MCP** | 通过 MCP 协议接入外部工具服务器，工具自动注册进 Tool Registry | §6 |
| F4 | **API 接入优化 / 国内大模型** | 统一 OpenAI 兼容协议 + 厂商预设模板，一键接入 DeepSeek/Kimi/GLM/通义/豆包 | §7 |
| F5 | **记忆功能 v3** | 层级记忆 + 自动抽取 + 检索注入，真正"记住重点" | §8 |
| F6 | **ChatGPT 逻辑推理执行** | ReAct 推理链：Thought → Action → Observation，推理过程可展开 | §3 |
| F7 | **Claude 风格输出** | 输出渲染对齐 Claude Desktop：Markdown、代码块、引用、来源脚注 | §9 |

---

## 1. 背景与目标

### 1.1 这是什么

AI.Super Agent是一个**本地运行的 Agent 应用**：用对话方式提供"能聊、能算、能记"的助手能力。v3.0 在保持"本地可离线运行、可出 EXE"的前提下，把能力边界扩展到**联网、可扩展、多模型**。

### 1.2 v3.0 目标（在 v2.0 四条硬指标之上新增）

| # | 硬指标 | 说明 |
|---|---|---|
| H5 | **联网可用但可离线** | 有网时 `web_search` 提供真实信息；断网时静默降级本地知识库，不报错不卡死 |
| H6 | **能力可扩展** | Skills 与 MCP 两种扩展机制，新增能力**不需要改核心代码** |
| H7 | **国内模型即插即用** | 至少 5 家国内厂商（DeepSeek/Kimi/GLM/通义/豆包）预设模板，填 Key 即用 |
| H8 | **推理过程可见** | 复杂任务展示 Thought 链（可折叠），用户能看懂"它怎么得出这个结论" |
| H9 | **输出对齐 Claude 风格** | Markdown 渲染、代码高亮、来源引用、折叠推理，观感达到主流助手水准 |

### 1.3 文档体系关系

- 《WorkBuddy_EXE生成器_工程技术文档 v1.0》——总能力。
- 《WorkBuddy内复刻秒哒_完整工程技术文档 v3.0/v3.1》——框架总纲。
- 《AI.Super Agent_工程技术文档 v1.0》——实现版事实记录。
- 《AI.Super Agent_工程技术文档 v2.0》——本文档的基座（架构 + 缺陷闭环）。
- **本文档 v3.0**——在 v2.0 之上做能力扩展，两份文档共同构成 AI.Super Agent的完整技术路线。

### 1.4 v2.0 能力缺口 → v3.0 响应

| v2.0 未覆盖 | 用户场景 | v3.0 响应 |
|---|---|---|
| 纯本地知识库，信息陈旧 | "帮我查一下 2026 年的政策" | F1 联网搜索 + 来源引用 |
| 能力固定，无法扩展 | "想让助手能帮我查航班" | F2 Skills / F3 MCP |
| 仅 OpenAI 兼容单接口 | "我想用 DeepSeek / Kimi" | F4 厂商预设 + 兼容垫片 |
| 记忆能记但不会"用" | "上次聊到的预算数字呢" | F5 自动抽取 + 检索注入 |
| 工具调用黑盒 | "它为什么这么回答" | F6 ReAct 推理链可视化 |
| 纯文本/简陋 Markdown | "输出像 Claude 一样舒服" | F7 渲染对齐 Claude 风格 |

---

## 2. 总体架构 v3.0

### 2.1 目标架构图

```
┌────────────────────────────────────────────────────────────────────────┐
│                        用户（浏览器 / 桌面窗口）                           │
│       聊天输入 · 流式消息流 · 停止生成 · 推理折叠 · 设置 · 主题 · 技能管理  │
└───────────────────────────┬────────────────────────────────────────────┘
                            │ 自然语言
┌───────────────────────────┴────────────────────────────────────────────┐
│                   React + Vite 前端（App.tsx）                           │
│   Claude 风格 Markdown 渲染 · 推理过程折叠 · 来源引用 · 流式光标          │
└───────────────────────────┬────────────────────────────────────────────┘
                            │ runAgentV3()
┌───────────────────────────┴────────────────────────────────────────────┐
│                   Agent 推理引擎 v3（agent/ 模块集）                     │
│                                                                          │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │            ReAct 循环（Thought → Action → Observation）           │  │
│  │     · 本地：规则规划器（浅层 ReAct）                               │  │
│  │     · 云端：LLM 驱动 ReAct（tool_calls / 文本工具）                │  │
│  │     · 推理轨迹 trace[] 全量留痕 → UI 可折叠展示                    │  │
│  └───────┬──────────────────────────────┬───────────────────────────┘  │
│          ▼                               ▼                             │
│  ┌────────────────────┐    ┌────────────────────────────────────────┐  │
│  │   Context Builder  │    │   Tool Registry v3（一次定义，双路执行）  │  │
│  │   记忆注入·预算封顶  │    │   ├ 内置工具（calc/memory/now/…）       │  │
│  └────────────────────┘    │   ├ Web 工具（web_search，§4）           │  │
│                            │   ├ Skill 工具（运行时注入，§5）          │  │
│  ┌────────────────────┐    │   └ MCP 工具（动态注册，§6）              │  │
│  │  Memory Service v3 │    └────────────────────────────────────────┘  │
│  │  层级·自动抽取·检索   │                                              │
│  └────────────────────┘    ┌────────────────────────────────────────┐  │
│                            │  Provider 适配层（§7）                   │  │
│  ┌────────────────────┐    │   OpenAI 兼容统一协议                    │  │
│  │  本地桥 Bridge     │    │   国内厂商模板（DeepSeek/Kimi/GLM/…）    │  │
│  │  MCP stdio·搜索抓取  │    │   三级回退链                            │  │
│  └────────────────────┘    └────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │             安全基础设施（横切）：Vault / Parser / 审计链 / 权限门    │ │
│  └───────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────┘
                            │
         ┌──────────────────┴───────────────────┐
         ▼                                      ▼
   Tauri 桌面壳（主线，开发机）           PyInstaller 启动器（回退，沙箱）
   原生 WebView2 · updater · 签名      http.server + 本地桥进程（MCP/搜索）
```

### 2.2 与 v2.0 架构对比

| 维度 | v2.0 | v3.0 |
|---|---|---|
| 推理 | Agent Loop（tool-calling 循环） | **ReAct 循环**（推理轨迹显式化、可折叠展示） |
| 工具来源 | 内置 8 个 | 内置 + **Web** + **Skills 动态注入** + **MCP 动态注册** |
| 信息 | 本地知识库 | + **联网搜索**（带来源引用） |
| 模型 | OpenAI 兼容 + Anthropic + Ollama | + **国内厂商预设模板**（统一协议） |
| 记忆 | 类型化 KV + 模糊召回 | + **自动抽取 + 检索注入**（工作/长程/语义三层） |
| 渲染 | Markdown + 代码高亮 | + **Claude 风格**：推理折叠、来源脚注、流式光标 |
| 扩展 | 改代码 | **丢目录（Skill）/ 配服务器（MCP）** 即扩展 |
| 桥进程 | 无（纯前端） | + **本地桥**承载 MCP stdio / 搜索抓取 |

### 2.3 架构决策记录（ADR）

v2.0 已有 ADR-01~06，v3.0 新增：

| ADR | 决策 | 理由 | 被否决的方案 |
|---|---|---|---|
| **ADR-07** | **ReAct 显式推理链**（Thought/Action/Observation），而非纯 function-calling 黑盒 | 推理过程可审计、可展示、可调试；对不支持 `tools` 的国内模型，可退化为"文本工具调用"（模型输出 `ACTION:tool(args)`） | 依赖各厂商 tool_calls 协议（国内模型支持参差，F4 冲突） |
| **ADR-08** | **Skills 用目录规范（SKILL.md + 资源）**，前端运行时发现加载 | 与 Claude Code / 主流生态一致；用户不写代码即可新增；可分享 | 硬编码技能列表（需改代码） |
| **ADR-09** | **MCP 通过本地桥进程接入**，浏览器/EXE 侧统一走 WS 透传 | 浏览器无原生 MCP；MCP stdio 服务器需要宿主进程；桥进程隔离崩溃与权限 | 浏览器直连（不可行）/ 全部用远程 HTTP MCP（失去 stdio 生态） |
| **ADR-10** | **国内大模型统一走 OpenAI 兼容协议 + 厂商预设模板**，不做原生 SDK | 主流国内厂商均提供 OpenAI 兼容端点；一套协议降维护成本；预设模板处理厂商差异 | 每家写原生 SDK（代码量大、难维护） |
| **ADR-11** | **记忆自动抽取默认关闭云端 LLM，用规则提取器**，云可用时增强 | 离线可用是产品定位；规则提取零成本；避免"为了记笔记先花 token" | 强依赖 LLM 抽取 |
| **ADR-12** | **外部能力（Skill/MCP/搜索）执行权限门**：首次调用弹确认，可按工具/按来源加入信任列表 | 外部代码与外部请求是不可信输入面，必须有用户显式授权边界 | 全自动执行（安全隐患） |

---

## 3. 能力域：Agent 推理引擎 v3 —— ChatGPT 逻辑（F6）

> 目标：按"思考 → 行动 → 观察"的循环推理与执行，推理过程可见、可审计，且兼容不支持 tool_calls 的国内模型。

### 3.1 ReAct 循环

v2.0 的 Agent Loop 是"解析 intent → 执行工具 → 回填"；v3.0 把它升级为**显式 ReAct**，每个循环步记录为一条推理轨迹。

```
for round in 1..MAX_ROUND(5):
  # Thought：决定这一步干什么（本地=规则规划器；云端=LLM）
  thought = reason(context, tools_available)

  if thought.type == 'answer':
    return finalize(thought.text)                    # 结论 + 轨迹

  if thought.type == 'action':
    action = parse_action(thought)                    # 兼容两种表达
    # ① 原生 tool_calls（OpenAI 兼容 / 支持 tools 的模型）
    # ② 文本指令（ACTION:tool(args)，不支持 tools 的国内模型）
    result = execute_tool(action)                     # 走 Tool Registry
    observation = observe(result)                     # 观察结果
    context.push(trace, { round, thought, action, observation })
    continue
```

**关键设计**：`trace[]` 全量留痕，UI 用折叠卡片展示 `Thought`（思考）与 `Observation`（观察），用户可展开看推理链（对应 F7 的"推理折叠"）。

### 3.2 推理轨迹数据结构

```typescript
export interface TraceStep {
  round: number
  thought: string          // "用户要算 128/4，这是算术，应调用 calc"
  tool?: string            // 选中的工具
  args?: Record<string, unknown>
  observation?: string     // 工具返回或异常摘要
  ok?: boolean
  ts: number
}

export interface AgentOutputV3 {
  text: string
  trace: TraceStep[]               // 供 UI 折叠展示 + 审计
  fromCloud: boolean
  degraded?: boolean               // 云端回退本地
  sources?: SourceRef[]            // 联网/知识库来源（F1/F7）
}
```

### 3.3 文本指令降级（关键兼容路径，对接 F4）

对不支持 `tools` 参数的国内模型，ReAct 退化为**文本协议**——system prompt 内注入工具说明与格式约束：

```
可用工具：
- calc(expr)：计算算术表达式，任何数字运算必须用它
- memory_write(key, value)：记住事实
- ...
调用格式：ACTION:calc({"expr": "128/4"})
结束格式：FINAL:你的回答
```

模型输出被解析器识别：`ACTION:...` 进入工具执行，`FINAL:...` 结束循环。**这让不支持 function calling 的国内模型也能用工具**（与 ADR-07 对应）。首次 400 自动探测并记住该模型（沿用 v2.0 `no-tools-models` 集合，v3.0 扩展为 `model-modes` 缓存：`tool_calls` / `text-action` / `plain`）。

### 3.4 本地规划器（离线模式）

云不可用时，ReAct 的 Thought 由规则规划器产出：仍走 v2.0 的意图路由（别名 / 分类器 / KB），但把每一步也写入 `trace[]`，保证"离线模式同样有推理轨迹可看"。

**验收**：
- "先算 15×8，再把结果记成预算"：trace 含 ≥2 个 Action 步，且步骤可见；
- 对不支持 tools 的模型走文本指令协议，`ACTION:` 正确解析执行；
- 所有路径（云端 tool_calls / 云端文本 / 本地）`trace` 非空。

---

## 4. 能力域：联网搜索（F1）

> 目标：对话中按需调用 `web_search`，返回带来源引用的结果；离线自动降级；本地桥承载抓取。

### 4.1 工具定义

```typescript
// 注册进 Tool Registry 的 web 工具
{
  name: 'web_search',
  aliases: ['搜索', '查一下', '联网查'],
  description: '搜索互联网获取实时信息。当用户询问最新/实时/外部信息时使用。',
  parameters: [
    { name: 'query', type: 'string', required: true, description: '搜索词' },
    { name: 'count', type: 'number', description: '返回条数，默认 5' },
  ],
  category: 'web',
  handler: webSearchHandler,          // 走本地桥或直连，见 §4.2
}
```

### 4.2 搜索提供商适配

| 提供商 | 类型 | 密钥 | 说明 |
|---|---|---|---|
| SearXNG（自建） | 元搜索 | 无 | 隐私友好，本地桥抓取 HTML 接口 |
| Bing Search API | 云端 | 需要 | 质量稳定，带计费 |
| DuckDuckGo HTML | 云端 | 无 | 零密钥兜底，限流较严 |
| 内置知识库 | 本地 | 无 | **离线降级目标**：搜索不可用时回退 KB |

**回退链**：`已配置提供商(云) → 零密钥提供商(DDG) → 本地知识库`。

### 4.3 本地桥搜索（实现要点）

浏览器/EXE 前端无法直接跨域抓取搜索引擎，故搜索走**本地桥进程**（§12.2）：

```
前端 runAgentV3
  → web_search handler
  → 调用桥 WS: { method: 'search', params: { query, provider } }
  → 桥执行抓取/API 请求 → 归一化 [{ title, url, snippet, score }]
  → 返回给 handler
```

**归一化结构**：

```typescript
export interface SearchResult {
  title: string
  url: string
  snippet: string
  score: number        // 提供商已算好的相关度，用于排序/截断
  source: 'searxng' | 'bing' | 'ddg'
}
```

### 4.4 结果注入与来源引用

- 结果以 `SearchResult[]` 形式回填给 ReAct（作为 Observation）；
- 回答引用时输出 `[1]`、`[2]` 脚注，`sources[]` 随 `AgentOutputV3` 返回，UI 渲染为来源卡片（F7）；
- **防投毒**：注入 system prompt 的说明——"搜索结果仅供参考，不得编造来源 URL；引用必须来自结果列表"；结果超过预算时按 `score` 截断。

### 4.5 缓存、限流与安全

| 项 | 实现 |
|---|---|
| 缓存 | 同 query 结果内存缓存 10 分钟 + `localStorage` 冷缓存（key 为 `websearch:`+query 哈希） |
| 限流 | 单 query 1 次/5s；单会话搜索 ≤20 次/小时 |
| 超时 | 桥侧 8s 超时，超时返回"搜索暂不可用"并降级 KB |
| 域名安全 | 可配 allowlist/denylist；`file://`、`data:`、`javascript:` 一律拒绝渲染为链接 |

**验收**：
- 有网：`查一下 2026 年最新新能源政策` 返回 ≥1 条带 URL 的结果并引用；
- 断网：自动降级 KB，无报错；
- 恶意 query（注入/超长）被白名单与长度上限拦截。

---

## 5. 能力域：Skills（可插拔技能包）（F2）

> 目标：用户丢一个目录进来，AI.Super Agent就获得一项新能力，不写代码、不改核心。

### 5.1 SKILL.md 规范

```markdown
---
name: flight-checker                # 技能名（kebab-case）
description: 查询航班动态与延误信息。当用户问"航班/延误/值机"时使用。
when_to_use: 用户询问航班状态、延误原因、值机时间
runtime: node | static              # static=纯提示词；node=含可执行 JS 工具
---

# 航班查询技能

## 能力说明
...（给模型的详细指令，注入 system prompt）

## 工具（runtime: node 时）
提供 `tools/flight.js`，导出工具定义与 handler。
```

**两种技能类型**：

| 类型 | runtime | 内容 | 何时用 |
|---|---|---|---|
| 提示词技能 | `static` | 只有 SKILL.md 的知识/指令 | 需要领域知识但无需外部调用 |
| 工具技能 | `node` | SKILL.md + `tools/*.js` 可执行工具 | 需要真实执行（查 API、算数据） |

### 5.2 技能发现与加载

```
skills/
├── flight-checker/SKILL.md + tools/flight.js
├── meeting-notes/SKILL.md            # static：会议纪要模板 + 规则
└── ...（用户自建，drop-in）

启动/设置面板「技能」页：
  scanSkills() → 扫描 skills/ 目录，解析 frontmatter，生成目录
  → static 技能：description 注入意图路由（扩大触发面）
  → node 技能：动态编译工具 → 注册进 Tool Registry（权限门，ADR-12）
```

**触发路径**：
1. 意图路由扫描技能 description，query 匹配 → 注入技能指令/工具；
2. 显式 `@skill <name>` 强制加载；
3. 云端模式：技能工具随 `tools` 参数透传给模型。

### 5.3 技能生命周期

| 能力 | 实现 |
|---|---|
| 安装 | 丢目录到 `skills/`（EXE 侧为应用数据目录下的 `skills/`） |
| 卸载 | 删目录；运行时无需重启（下次扫描生效） |
| 版本 | `SKILL.md` 支持 `version` 字段，可识别更新 |
| 权限 | node 技能首次调用弹确认框（ADR-12），可加信任列表 |
| 隔离 | node 技能在**桥进程的子进程**运行，超时（默认 10s）/崩溃不拖垮主进程 |

**验收**：
- 丢入一个示例 `flight-checker` 目录（含 SKILL.md + 一个返回 mock 数据的 tools/flight.js），`@skill flight-checker` 后能调用 mock 查询；
- static 技能被意图路由命中并注入指令；
- 恶意技能（尝试读系统文件）被桥进程沙箱/权限门拦截。

---

## 6. 能力域：MCP（Model Context Protocol）（F3）

> 目标：通过标准 MCP 协议接入外部工具服务器，工具自动注册进 Tool Registry，UI 可管理服务器。

### 6.1 架构：本地桥 + MCP 客户端

```
前端（React） ──WS──▶ 本地桥进程（Node/Python）
                         ├─ MCP stdio 客户端 ──▶ 本地 MCP 服务器（npx 启动等）
                         └─ MCP HTTP/SSE 客户端 ──▶ 远程 MCP 服务器
桥内：MCP 工具发现 → 归一化 → 注册为 Tool Registry 动态工具
```

**为什么走桥**（ADR-09）：浏览器无原生 MCP 支持；MCP stdio 服务器需要进程宿主；桥进程隔离崩溃并承载凭据。

### 6.2 MCP 工具归一化

MCP 工具描述 → Tool Registry 条目：

```typescript
export interface McpToolDef {
  server: string            // 'github' / 'filesystem' …
  name: string              // 'github.create_issue'
  description: string
  inputSchema: Record<string, unknown>   // MCP JSON Schema
}

// 注册为 Tool Registry 条目
{
  name: 'mcp.github.create_issue',
  description: '(MCP·github) 在指定仓库创建 Issue',
  parameters: toParamSchemas(inputSchema),
  category: 'mcp',
  localOnly: false,
  handler: (args, ctx) => bridge.invokeMcp({ server: 'github', tool: 'create_issue', args }),
}
```

### 6.3 服务器配置管理

```typescript
export interface McpServerConfig {
  id: string
  name: string
  transport: 'stdio' | 'http'
  command?: string      // stdio：npx / node 及参数
  url?: string          // http：SSE 端点
  env?: Record<string, string>   // 密钥经 Vault 加密存取
  enabled: boolean
  tools?: string[]      // 已发现工具列表（只读）
}
```

- 设置面板「MCP」页：添加/启用/禁用/删除服务器；查看工具清单；**首次调用弹权限确认**（ADR-12）；
- stdio 服务器由桥进程拉起（如 `npx -y @modelcontextprotocol/server-filesystem`）；
- 密钥（env 中的 token）存入 Credential Vault，不落明文。

### 6.4 安全边界

| 风险 | 缓解 |
|---|---|
| 恶意 MCP 服务器 | 权限门 + 信任列表；工具名前缀 `mcp.<server>.` 可整服务器禁用 |
| 桥进程被拖垮 | 每服务器独立子进程，崩溃自动重启，不影响主应用 |
| 敏感数据外传 | MCP 工具调用入审计哈希链；UI 展示"该工具归属服务器" |

**验收**：
- 本地起一个 mock MCP 服务器（stdio），桥发现其工具并注册；
- 设置面板可启停服务器、首次调用弹权限框；
- MCP 工具调用进入审计链。

---

## 7. 能力域：API 接入优化 / 国内大模型兼容（F4）

> 目标：统一 OpenAI 兼容协议，厂商预设模板一键接入，自动适配各家差异。

### 7.1 统一协议

主流国内模型均提供 OpenAI 兼容 `/v1/chat/completions`，因此 **Provider 适配层新增"统一 OpenAI 兼容"通道**（取代每家写 SDK）：

```
Provider 统一接口（v2.0 已有）
  chatStream(req, onToken, onToolCall)
    ├─ openai.ts    → 兼容所有 OpenAI 兼容端点（含国内厂商）
    ├─ anthropic.ts → 原生（海外）
    └─ ollama.ts    → 本地
```

### 7.2 厂商预设模板

```typescript
export interface ProviderPreset {
  id: string                 // 'deepseek' | 'kimi' | 'glm' | 'qwen' | 'doubao'
  label: string              // 'DeepSeek'
  baseUrl: string            // 默认 OpenAI 兼容端点
  models: string[]           // 常用模型名
  defaultModel: string
  toolsMode: 'tool_calls' | 'text-action' | 'auto'   // 见 §3.3
  notes?: string[]           // 已知差异提示
}
```

| 预设 | baseUrl（示例） | 常用模型 | toolsMode |
|---|---|---|---|
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` | auto（支持 tools） |
| Kimi（月之暗面） | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` | auto |
| 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-flash` | auto |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` | auto |
| 豆包（火山） | `https://ark.cn-beijing.volces.com/api/v3` | `doubao-pro-32k` | auto |
| Ollama（本地） | `http://localhost:11434/v1` | `llama3` | auto |

> 注：各厂商端点与模型名以官方文档为准，模板在设置面板可编辑（baseUrl/models 可改）。

### 7.3 兼容垫片（处理厂商差异）

| 差异 | 垫片 |
|---|---|
| 部分厂商不支持 `system` 角色 | 自动把 system 消息转为首条 `user` 前缀 `[系统指令]` |
| 不支持 `tools` / 流式异常 | 首次 400 探测 → 记入 `model-modes` 缓存 → 降级 `text-action` 或 `plain`（§3.3） |
| 温度/参数字段差异 | 统一 clamp 到各厂商合法区间（如 `temperature:0.7`） |
| 流式格式不标准 | Provider 层做 SSE 归一化；解析失败自动回退本地 |
| 上下文长度差异 | 读取预设 `maxContext`，Context Builder 按该值收缩预算（v2.0 的 6000 字符为默认值，可被预设覆盖） |
| 计费/限流错误 | 复用 v2.0 错误分类表（429/401/400…）映射到统一提示 |

### 7.4 设置面板增强

- 「模型提供商」下拉：预设列表 + **自定义**；
- 选预设自动填 baseUrl + 默认模型；用户只需填 API Key（经 Vault 加密）；
- 「测试连接」按钮：发一个最小请求验证 Key/端点，返回延迟与可用模型列表（若厂商支持 `GET /models` 则自动拉取）；
- 「模型模式」显示：`tool_calls / text-action / plain`，可手动覆盖。

**验收**：
- 至少 DeepSeek/Kimi/GLM 三个预设填 Key 后可对话（mock stub 验证协议路径）；
- 不支持 tools 的模型自动走 text-action，工具仍可用；
- 测试连接对错误 Key / 错误端点给出可读错误。

---

## 8. 能力域：记忆功能 v3（F5）

> 目标：从"能记"升级为"会记、会用"——自动抽取要点、按需检索注入上下文。

### 8.1 三级记忆模型

| 层级 | 载体 | 内容 | 生命周期 |
|---|---|---|---|
| 工作记忆 | 当前会话 `messages` | 本次对话上下文 | 会话级 |
| 长程记忆 | `localStorage` 会话摘要库 | 历史会话的要点摘要 | 持久 |
| 语义记忆 | v2.0 的 `MemEntry`（类型化） | 事实/偏好/待办 | 持久 + TTL |

### 8.2 自动记忆抽取

每次助手回复完成后触发 `extractMemories(exchange)`：

- **云可用**：LLM 抽取——把对话片段交给模型，返回结构化记忆候选 `[{type, key, value}]`（低 token 消耗，取事实/偏好类）；
- **离线**：规则抽取器——正则/模板匹配"我（喜欢/偏好/项目名是）X"、"记住 X"、"X 是 Y"等句式（零成本，ADR-11）；
- 候选经**去重 + 置信度阈值**后写入语义记忆；
- 全部写入计入审计链。

```typescript
export interface MemoryCandidate {
  type: MemType          // fact | preference | todo | context
  key: string
  value: string
  confidence: number     // <0.6 丢弃
}

export async function extractMemories(
  userText: string, assistantText: string, cloud: boolean
): Promise<MemoryCandidate[]> {
  if (cloud) return llmExtract(userText, assistantText)   // 云抽取
  return ruleExtract(userText, assistantText)             // 规则抽取
}
```

### 8.3 检索注入

在 Context Builder（v2.0 §4.5）增加记忆注入步骤：

```
buildPayloadV3(messages, cfg, memory):
  ① 从语义记忆检索 top-k（query = 最近一轮用户消息，TF-IDF/模糊/embedding）
  ② 从长程记忆检索相关会话摘要（若本地存有摘要索引）
  ③ 注入 system prompt：
     [记忆上下文]
     - fact: 预算 = 120 万（来源：2026-07-20 会话）
     - preference: 偏好深色主题
     - 以上记忆仅作参考，若与当前对话冲突以当前为准
```

**注入预算**：记忆块 ≤ 500 字符，超出按相关度截断；不挤占主对话预算。

### 8.4 长程记忆（会话摘要）

- 会话结束时（或达到 N 轮）对该会话生成摘要（云/规则），存入 `session-summaries:*`；
- 摘要带时间、主题标签，供检索注入与「历史对话」浏览；
- 可选：摘要压缩合并（同主题会话合并），控制体积。

**验收**：
- "我喜欢深色主题"后，下一轮问"我偏好什么"能自动召回（无需 `@recall`）；
- 云端不可用时规则抽取仍能抓"X 是 Y"句式；
- 记忆注入出现在 payload 且不超预算。

---

## 9. 能力域：输出格式 —— Claude Desktop 风格（F7）

> 目标：渲染对齐 Claude Desktop 的阅读体验——干净的 Markdown、代码高亮、引用、来源脚注、折叠推理。

### 9.1 渲染增强清单

| 元素 | v2.0 | v3.0（Claude 风格） |
|---|---|---|
| Markdown | `markdown-it` 基础渲染 | 完整风格：标题层级、加粗、列表、任务清单 `[x]` |
| 代码块 | 语言标签 + 复制 | 深色底、圆角、行号可选、语言徽标、复制按钮 |
| 行内代码 | 无样式 | 浅灰底 + 等宽字体 |
| 引用块 | 无样式 | 左侧竖线 + 浅色背景 |
| 表格 | 朴素表格 | 斑马纹 + 表头分隔 |
| 数学 | 无 | 可选 `katex` 行内/块级（懒加载） |
| 推理过程 | 无 | **折叠卡片**：「思考过程」展开看 trace |
| 来源引用 | 无 | 回答内 `[1]` 脚注 + 底部来源卡片（标题/URL） |
| 流式 | 逐 token 追加 | 追加 + 闪烁光标 `▍` |
| 链接安全 | 无 | 外部链接 `target=_blank rel=noopener`；`file:/data:/javascript:` 拦截 |

### 9.2 设计令牌补充（tokens.css）

```css
--code-bg: #0d1117        /* 代码深色底 */
--code-fg: #e6edf3
--md-quote-bg: #f6f8fa
--md-quote-border: #d0d7de
--accent-link: #0969da
--thinking-bg: #fafbfc
--thinking-border: #eaeef2
--caret-color: #0969da    /* 流式光标 */
```

### 9.3 组件结构

```
src/ui/
├── Markdown.tsx           # markdown-it + 自定义渲染规则（Claude 风格）
├── CodeBlock.tsx          # 高亮 + 复制 + 语言徽标
├── ThinkingTrace.tsx      # 折叠推理卡片（读 trace[]）
├── SourcesCard.tsx        # 来源引用卡片
└── StreamCaret.tsx        # 流式光标
```

**XSS 防护**：`markdown-it` 开 `html:false` + `DOMPurify` 双保险（沿用 v2.0 决策）；渲染前对 URL 做协议白名单。

**验收**：
- 一条含代码块 + 表格 + 引用 + 脚注的回复渲染正确，截图对照 Claude Desktop 风格；
- 推理折叠卡片可展开，trace 步骤完整；
- 恶意 HTML/URL 被清洗，`javascript:` 不可点击。

---

## 10. 功能规格 v3.0

| # | 功能 | 状态 |
|---|---|---|
| 1 | 本地引擎对话（内置知识库） | 沿用 |
| 2 | `@` 前缀工具命令 | 沿用 |
| 3 | 自然语言触发工具 | 沿用 |
| 4 | 云端模式工具可用（tool_calls / text-action） | 增强（ReAct） |
| 5 | 流式输出 + 停止生成 | 沿用 |
| 6 | Markdown + 代码高亮 | 增强（Claude 风格） |
| 7 | 上下文预算 + 错误分类 | 沿用 |
| 8 | KB 打分召回 | 沿用 |
| 9 | 类型化记忆 | 沿用 |
| 10 | 凭据加密 / 会话模式 | 沿用 |
| 11 | 审计哈希链 | 沿用 |
| 12 | 主题切换 / 清空 / 持久化 | 沿用 |
| **13** | **联网搜索 + 来源引用** | **新增** |
| **14** | **Skills 技能包（static/node）** | **新增** |
| **15** | **MCP 服务器接入 + 工具动态注册** | **新增** |
| **16** | **国内大模型预设（≥5 家）+ 测试连接** | **新增** |
| **17** | **文本指令工具协议（text-action）** | **新增** |
| **18** | **自动记忆抽取 + 检索注入** | **新增** |
| **19** | **ReAct 推理轨迹 + 折叠展示** | **新增** |
| **20** | **来源脚注 / 来源卡片** | **新增** |
| **21** | **外部能力权限门 + 信任列表** | **新增** |
| **22** | **MCP/Skill 工具入审计链** | **新增** |

---

## 11. 质检体系 v3

### 11.1 六门保留 + 扩展

| 门 | v2.0 | v3.0 |
|---|---|---|
| 1 静态 | `tsc --noEmit` | 同左 |
| 2 构建 | gzip ≤ 90KB | 同左（技能/MCP 动态加载不计入首包） |
| 3 冒烟 | Playwright | + 推理折叠 / 来源卡片 / MCP 面板冒烟 |
| 4 复核 | `agent/`+`security/` 必跑 | + `skills/`、`mcp/` 安全审查 |
| 5 安全 | 零 eval + 恶意用例 | + **外部技能/MCP 工具沙箱审查**（node 技能隔离验证） |
| 6 评分 | Lighthouse ≥ 85 | + 渲染质量对照（Claude 风格截图比对） |

### 11.2 新增专项门

**门 7 · 外部能力安全门**（Skill/MCP/搜索）：
- node 技能在子进程运行，访问系统文件/网络的权限白名单验证；
- MCP 服务器工具调用均过权限门，入审计链；
- 搜索 URL 协议白名单 + 注入防护。

---

## 12. 打包交付 v3

### 12.1 双流水线（沿用 v2.0）

- Tauri 主流水线（开发机）产物 ~8MB；
- PyInstaller 回退流水线（沙箱）产物 ~45MB。

### 12.2 新增：本地桥进程（关键新增）

联网搜索、MCP stdio、node 技能都需要一个**本地宿主进程**：

```
桌面壳 / 网页预览
   └─ 启动本地桥（Node 运行时，PyInstaller 侧随包携带；Tauri 侧为 sidecar）
        ├─ 功能：MCP 客户端（stdio/http）、搜索抓取归一化、node 技能沙箱执行
        ├─ 通信：WS localhost:<port>，一次性 token 校验（复用 v2.0 D13 修复）
        └─ 生命周期：随应用启停；子进程隔离、超时、崩溃自动重启
```

| 形态 | 桥的载体 |
|---|---|
| 网页预览 | 需要用户本机有 Node（可选能力，无则联网/MCP/技能降级） |
| PyInstaller EXE | PyInstaller 打包一个精简 Node 可执行（或 Python asyncio 版桥） |
| Tauri | 官方 sidecar 机制携带 |

> **降级原则（ADR-08/09）**：桥不可用时，联网/MCP/node 技能自动隐藏或提示"此能力需要本地桥"，核心对话能力不受影响。

### 12.3 数据目录

```
应用数据目录（EXE 侧 %APPDATA%/AI助手，网页侧 localStorage + 可选导出）：
├── skills/                    # 用户技能包（drop-in）
├── mcp.json                   # MCP 服务器配置（含 Vault 加密的 token）
├── memories/                  # 语义记忆 + 会话摘要
├── audit.jsonl                # 哈希链审计
└── settings.json              # 非敏感设置
```

---

## 13. 验证矩阵 v3

| 层 | 方法 | 覆盖 |
|---|---|---|
| 单元 | Vitest | ReAct 规划器、text-action 解析、搜索归一化、技能发现、MCP 归一化、记忆抽取 |
| 集成 | Node + localStorage 垫片 | ReAct 多步链、搜索降级、MCP mock 注册、国内模型协议路径 |
| 组件 | Vitest + Testing Library | 推理折叠、来源卡片、技能面板、MCP 面板、测试连接 |
| E2E | Playwright | 加载/对话/工具/主题/清空 + 推理展开 + 来源渲染 + 权限弹框 |
| 安全 | 恶意用例 + 沙箱 | eval 拒绝、node 技能越权拦截、MCP 权限门、搜索 URL 白名单 |
| 性能 | Lighthouse + 指标 | TTFT、写入次数、payload 上限、搜索延迟 |
| **外部能力** | mock 服务器 + 本地桥 | MCP stdio/http、node 技能子进程、SearXNG/Bing/DDG 适配 |

### 13.1 回归红线（在 v2.0 五条之上新增）

6. **v1.0 17 条 + v2.0 KB 7 条 + 写入 ≤3 次 + payload ≤6200 + 零 eval** 全部保留；
7. **搜索降级**：断网场景 web_search 返回降级而非抛错；
8. **权限门**：未授权的 Skill/MCP 工具不可执行（自动化断言）；
9. **ReAct 轨迹**：所有回答路径 trace 非空。

---

## 14. 文件清单 v3.0（目标布局）

```
agent-app/
├── src/
│   ├── main.tsx / App.tsx                # 聊天 UI（Claude 风格）
│   ├── agent/
│   │   ├── index.ts                      # runAgentV3
│   │   ├── loop.ts                       # ReAct 循环（v3，含 trace）
│   │   ├── react.ts                      # 规划器 / text-action 解析器
│   │   ├── intent.ts / context.ts / memory.ts / kb.ts   # v2.0 增强
│   ├── tools/
│   │   ├── registry.ts                   # + 动态注册（skill/mcp）
│   │   ├── web.ts                        # 联网搜索（F1）
│   │   └── builtin/                      # calc / memory_* / now / …
│   ├── skills/                           # 技能发现 + 加载 + 沙箱执行（F2）
│   ├── mcp/                              # MCP 客户端 + 工具归一化（F3）
│   ├── providers/
│   │   ├── openai.ts                     # 统一 OpenAI 兼容（含国内）
│   │   ├── presets.ts                    # 厂商预设模板（F4）
│   │   └── anthropic.ts / ollama.ts
│   ├── memory/
│   │   ├── extract.ts                    # 自动抽取（F5）
│   │   └── inject.ts                     # 检索注入
│   ├── security/                         # vault / safe-calc / audit / perms（权限门）
│   └── ui/
│       ├── Markdown.tsx / CodeBlock.tsx / ThinkingTrace.tsx / SourcesCard.tsx
│       └── tokens.css / primitives.tsx
├── bridge/                               # 本地桥（Node，F1/F2/F3）
│   ├── index.ts                          # WS 服务 + token 校验
│   ├── mcp-client.ts / search.ts / skill-runner.ts
├── tests/ · e2e/ · scripts/
├── src-tauri/ · build_exe/ · dist/
└── data/                                 # skills/ mcp.json memories/ audit.jsonl
```

**相对 v2.0 新增**：`agent/react.ts`、`tools/web.ts`、`skills/`、`mcp/`、`providers/presets.ts`、`memory/extract.ts`、`memory/inject.ts`、`security/perms.ts`、`bridge/`、`ui/ThinkingTrace.tsx`、`ui/SourcesCard.tsx` 等，约 **15 个新文件**。

---

## 15. 分阶段实施计划

> 原则沿用：每阶段独立交付/验收/可回退；新依赖可选，不装即静默降级。

### Phase 0 — 桥与基础（第 1–2 周）

| 任务 | 验收 |
|---|---|
| P0-1 本地桥框架（WS + token + 生命周期） | 前端可连桥，`ping` 通 |
| P0-2 权限门（perms.ts）+ 信任列表 | 未授权外部工具不可执行（自动化断言） |
| P0-3 搜索适配 + 降级链 | DDG 零密钥可搜；断网降级 KB |

### Phase 1 — ReAct 推理 + 文本协议（第 3–5 周）

| 任务 | 验收 |
|---|---|
| P1-1 ReAct 循环 + trace | 多步任务 trace 可见；所有路径 trace 非空 |
| P1-2 text-action 解析器 | 不支持 tools 的模型走文本协议可用工具 |
| P1-3 Claude 风格渲染 | 代码/表格/引用/脚注渲染正确；XSS 清洗通过 |

### Phase 2 — 国内模型 + 记忆 v3（第 6–8 周）

| 任务 | 验收 |
|---|---|
| P2-1 厂商预设 + 兼容垫片 | ≥3 家预设填 Key 可对话（mock stub 验证） |
| P2-2 测试连接 + 模型模式 | 错误 Key/端点给出可读错误 |
| P2-3 记忆抽取 + 检索注入 | "我喜欢深色"下轮自动召回；规则抽取离线可用 |

### Phase 3 — Skills + MCP（第 9–11 周）

| 任务 | 验收 |
|---|---|
| P3-1 Skills 发现/加载/沙箱 | 丢目录即用；node 技能越权被拦截 |
| P3-2 MCP 客户端 + 工具注册 | mock MCP 服务器工具注册并可调用（过权限门） |
| P3-3 设置面板（技能/MCP/提供商） | 可管理服务器、启停技能、测试连接 |

### Phase 4 — 打包与质检（第 12–14 周）

| 任务 | 验收 |
|---|---|
| P4-1 桥随包交付（Tauri sidecar / PyInstaller） | EXE 内联网/MCP/技能可用或明确降级 |
| P4-2 门 7 外部能力安全门 | node 技能沙箱、MCP 权限、搜索 URL 白名单全过 |
| P4-3 六门 + 门 7 全绿；评分 ≥ 85 | Lighthouse + Playwright + 渲染对照通过 |

### 里程碑

| 里程碑 | 时间 | 交付物 |
|---|---|---|
| M0 桥与权限 | 第 2 周末 | 本地桥可用，外部能力有权限门 |
| M1 会推理会输出 | 第 5 周末 | ReAct + Claude 风格渲染 |
| M2 多模型会记忆 | 第 8 周末 | 国内模型即插即用 + 记忆自动注入 |
| M3 可扩展 | 第 11 周末 | Skills + MCP 全通 |
| M4 正式交付 | 第 14 周末 | 六门+门7 全绿，EXE/Tauri 双线可用 |

---

## 16. 风险与限制

| 风险 | 影响 | 缓解 |
|---|---|---|
| 国内模型 tools 支持参差 | 云端工具失效 | text-action 文本协议兜底（ADR-07）；model-modes 缓存 |
| 桥进程不可用（无 Node / 被杀软拦截） | 联网/MCP/技能不可用 | 核心对话降级可用；Tauri sidecar / PyInstaller 携带桥 |
| node 技能恶意代码 | 安全 | 子进程沙箱 + 权限门 + 审计链（门 7） |
| 搜索内容被投毒/侵权 | 回答质量/合规 | 来源引用强制；结果只作参考；URL 白名单 |
| MCP 服务器故障 | 工具不可用 | 每服务器独立进程，崩溃不影响主应用 |
| 记忆自动抽取误记 | 记忆污染 | 置信度阈值 + 去重 + 用户可删除/编辑记忆 |
| 七项功能叠加导致体量膨胀 | 交付周期超 14 周 | 每 Phase 独立交付；静态依赖全部可选 |
| 模型输出文本协议解析失败 | 工具调用失败 | 解析失败走 plain 模式回退，不阻塞对话 |

**限制（诚实说明）**：
- 国内厂商端点/模型名以官方文档为准，本文档模板为初始值，设置面板可改；
- 桥进程在网页预览形态依赖本机 Node，纯浏览器环境该能力降级；
- `web_search` 质量取决于提供商；DDG 零密钥模式下限流较严；
- 推理轨迹展示为 v3.0 新增，未实测 UI 表现，须 Phase 1 落地后 Playwright 复核。

---

## 17. 总结

> **AI.Super Agent v3.0** = v2.0 全部能力 ＋ **ReAct 推理引擎**（F6，推理可见、文本协议兼容国内模型）＋ **联网搜索**（F1，来源可引用）＋ **Skills**（F2，丢目录即扩展）＋ **MCP**（F3，标准协议接入外部工具）＋ **国内大模型预设**（F4，统一 OpenAI 兼容 + 兼容垫片）＋ **记忆 v3**（F5，自动抽取 + 检索注入）＋ **Claude 风格输出**（F7，渲染对齐主流体验）。

**关键跃迁**：

| | v2.0 | v3.0 |
|---|---|---|
| 信息 | 本地知识库 | 实时联网 + 来源引用 |
| 能力扩展 | 改代码 | Skills / MCP 即插即用 |
| 模型 | 单接口 | 国内主流一键接入 + 自动适配 |
| 推理 | 工具调用黑盒 | ReAct 推理链可见可审计 |
| 记忆 | 能记会用（手动） | 自动抽取 + 检索注入 |
| 输出 | 基础 Markdown | Claude 风格渲染 |

**实施主线**：Phase 0 桥与权限（1–2 周）→ Phase 1 会推理会输出（3–5 周）→ Phase 2 多模型会记忆（6–8 周）→ Phase 3 可扩展（9–11 周）→ Phase 4 交付（12–14 周），与 v2.0 的 Phase 0~3 合并执行（v2.0 为前置基座，v3.0 在其上叠加）。

---

*— 本文档在 v2.0 已实测架构之上设计七项新能力；凡 v2.0 已确立的决策（Tool Registry 双路、预算封顶、零 eval、凭据保险库、哈希链审计、双流水线）均直接继承，v3.0 只新增不改。所有接口、数据结构、验收标准按可落地粒度给出，读文档即可开始实施；标注"预期"的（如厂商端点、桥载体、~8MB）以官方文档与落地实测为准。*


---

# Part III — 打包交付专篇（v4.0）　🔬 打包命令实测

> v4.0 打包交付专篇全文，聚焦「生成 → 打包 → 验证 → 交付」全链路；命令与尺寸数据基于沙箱实测。

# AI.Super Agent · 软件生成打包为 Windows 桌面 EXE — 技术文档 v4.0

> **文档版本**：v4.0（打包交付专篇 · 实施级）
> **适用范围**：把 AI.Super Agent（React + Vite 前端 + 纯 TS Agent 引擎）从源码生成打包为 Windows 桌面 `.exe` 单文件
> **打包工具**：PyInstaller 6.20.0（`--onefile --windowed`），pywebview（Edge/WebView2）嵌入式窗口 + 浏览器回退
> **前置文档**：《AI.Super Agent_工程技术文档 v1.0/v2.0/v3.0》（本专篇聚焦"生成 → 打包 → 验证 → 交付"全链路）
> **日期**：2026-08-01
> **状态**：命令均已在沙箱实测跑通；v4.0 补充交付全链路（签名/更新/体积优化）

---

## 1. 目标与总览

### 1.1 本文档解决什么

把一套 **Web 形态的 Agent 应用**（浏览器里能跑的 React 前端）变成 **Windows 桌面双击即用的单文件 EXE**。整个链路：

```
源码(agent-app/) → 前端构建(dist/) → PyInstaller 冻结 → 单文件 EXE
        → 无界面冒烟 → 体积瘦身 → 代码签名 → 自动更新 → 交付发布
```

### 1.2 关键结论（先读）

| 项 | 结论 |
|---|---|
| 产物 | `AI助手.exe` 单文件，约 **43.3 MiB (45.4 MB)**，PE/MZ 有效 |
| 打包方式 | PyInstaller `--onefile --windowed`，前端 `dist/` 作为数据打入 |
| 运行原理 | EXE 启动 → 本地 `http.server` 托管内嵌前端 → pywebview 弹出桌面窗口；任意异常回退默认浏览器 |
| 冷启动 | `--onefile` 每次解压到 `%TEMP%\_MEIxxxxx`，**3~8 秒** |
| 冒烟 | `AGENT_EXE_TEST=1` 无界面钩子 + curl，可自动化验证 EXE 内前端已正确冻结 |

### 1.3 技术栈

| 维度 | 选择 | 理由 |
|---|---|---|
| 打包器 | PyInstaller 6.20.0 `--onefile --windowed` | 沙箱可复现、已实测；单文件分发 |
| 窗口 | pywebview（系统 Edge/WebView2）+ 浏览器回退 | 无额外体积；优先桌面窗口体验 |
| 静态托管 | 标准库 `http.server`（ThreadingHTTPServer） | 零依赖、冻结后可跑 |
| 前端 | Vite + React 构建产物 `dist/` | 与 v1.0 一致 |

---

## 2. 前置准备

### 2.1 环境

| 依赖 | 版本/说明 |
|---|---|
| Python | ≥ 3.8（沙箱实测 3.11） |
| PyInstaller | 6.20.0 |
| pywebview | ≥ 4.0（EXE 侧 `--hidden-import webview`） |
| Node.js | ≥ 18（仅构建阶段需要，打包后不需要） |
| WebView2 Runtime | Windows 10/11 多数已内置；缺失时回退浏览器 |

安装：

```bash
pip install pyinstaller==6.20.0 pywebview --break-system-packages
```

### 2.2 源码目录（打包输入）

```
agent-app/
├── index.html
├── package.json / vite.config.ts / tsconfig.json
├── src/                  # React + Agent 引擎
└── dist/                 # ← npm run build 产物（打入 EXE 的前端）
```

---

## 3. 前端构建（生成产物）

打包前先把前端构建为静态资源：

```bash
cd agent-app
npm ci                 # 按 lockfile 安装依赖（可复现）
npm run build          # tsc + vite build → dist/
```

**产物校验**（构建后必查）：

```bash
ls -la dist/
# 期望：
#   dist/index.html
#   dist/assets/index-*.js   (JS 151.8KB / gzip 51.7KB 基线)
#   dist/assets/index-*.css
```

**门 2（构建门）红线**：`dist/` 生成且 `index.html` 引用路径正确（`vite.config.ts` 设 `base: './'`，否则 EXE 内相对路径解析失败）。

---

## 4. 打包启动器（launcher.py）

EXE 的入口是一个 Python 启动器：负责把内嵌前端托管起来，并弹出窗口。

### 4.1 完整代码

```python
# build_exe/launcher.py
"""AI 助手 EXE 启动器：本地托管前端 + pywebview 窗口 + 浏览器回退。"""
import os
import sys
import socket
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def resource_path(rel: str) -> Path:
    """定位资源：PyInstaller 冻结后用 _MEIPASS，开发时用项目目录。"""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / rel


class SafeHandler(SimpleHTTPRequestHandler):
    """只允许 GET/HEAD；附带安全响应头（v2.0 安全加固）。"""

    def do_GET(self):
        if self.path.startswith("/api/"):
            self.send_error(404); return
        super().do_GET()

    def end_headers(self):
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    def log_message(self, *args):  # 静默，避免刷屏
        pass


def pick_free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def serve(webroot: Path) -> tuple:
    handler = lambda *a, **kw: SafeHandler(*a, directory=str(webroot), **kw)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, port


def main():
    webroot = resource_path("webdist")           # 前端 dist/ 在 EXE 内叫 webdist
    if not webroot.exists():
        webroot = resource_path("dist")
    if not (webroot / "index.html").exists():
        raise SystemExit(f"[FATAL] 未找到前端产物: {webroot}")

    httpd, port = serve(webroot)
    url = f"http://127.0.0.1:{port}/"

    # 无界面冒烟钩子（自动化验证用，见 §6）
    if os.environ.get("AGENT_EXE_TEST") == "1":
        print(f"SMOKE_URL={url}")
        print(f"SMOKE_ROOT={webroot}")
        print("EXE_SMOKE=READY")
        return  # 保持进程存活，由测试脚本 curl 后关闭

    try:
        import webview
        webview.create_window("AI 助手 · 本地 Agent 应用", url, width=1024, height=720)
        webview.start()
    except Exception as e:                        # 任何异常回退默认浏览器
        import webbrowser
        print(f"[warn] pywebview 不可用({e})，回退浏览器")
        webbrowser.open(url)
        input("按回车退出…")


if __name__ == "__main__":
    main()
```

### 4.2 关键设计点

| 点 | 说明 |
|---|---|
| `_MEIPASS` | PyInstaller 冻结后内嵌资源的解压根；开发时回退到脚本目录 |
| 随机端口 | `ThreadingHTTPServer(("127.0.0.1", 0))` 端口 0 = 系统分配，避免端口冲突 |
| CSP 响应头 | `default-src 'self'` 等，满足 v2.0 安全红线 |
| `AGENT_EXE_TEST` | 冒烟钩子：无界面模式打印 URL，供测试脚本 `curl` 验证 |
| 浏览器回退 | `except Exception` 覆盖无 WebView2 / 崩溃场景，保证"双击总能起来" |

---

## 5. PyInstaller 打包（生成 EXE）

### 5.1 打包命令（沙箱实测跑通）

```bash
cd agent-app
PyInstaller --noconfirm --onefile --windowed --name "AI助手" \
  --distpath build_exe --workpath build_exe/work --specpath build_exe \
  --add-data "dist;webdist" \
  --hidden-import webview \
  --version-file build_exe/version.txt \
  --icon build_exe/app.ico \
  build_exe/launcher.py
```

### 5.2 参数含义

| 参数 | 含义 |
|---|---|
| `--onefile` | 打包成单个 EXE（运行时解压到临时目录） |
| `--windowed` | 无控制台黑窗（GUI 应用） |
| `--add-data "dist;webdist"` | 把前端产物打入 EXE，解压根下叫 `webdist`（分号是 Windows 分隔符） |
| `--hidden-import webview` | pywebview 是动态导入，需显式声明避免被裁剪 |
| `--version-file` | 版本/公司/描述等元数据（见 §7.1） |
| `--icon` | 图标（.ico），影响任务栏/资源管理器显示 |

### 5.3 产物

```
build_exe/AI助手.exe   ← 单文件成品，约 43.3 MiB
```

**产物健康检查**：

```bash
# 1) PE/MZ 头
xxd -l 2 build_exe/AI助手.exe        # 应显示 'MZ'
# 2) 大小
ls -la build_exe/AI助手.exe
# 3) 文件版本信息（有 version.txt 时）
```

> 注：`--onefile` 每次启动解压到 `%TEMP%\_MEIxxxxx`，首次启动慢（3~8 秒），易被杀软/SmartScreen 关注。这是单文件方案的内在代价，缓解见 §7。

---

## 6. 打包后冒烟验证（无界面）

> v1.0 六门质检中的"门 3 运行时冒烟"——**必须能证明 EXE 内前端已正确冻结**，而非只验证 EXE 能弹窗。

### 6.1 自动化冒烟脚本

```bash
# run_smoke.sh / PowerShell 等价
export AGENT_EXE_TEST=1
./build_exe/AI助手.exe &
sleep 6                                          # 等 --onefile 解压 + 服务起来
SMOKE_URL=$(curl -s http://127.0.0.1:*/smoke 2>/dev/null || echo "")
# 读取冒烟钩子输出的 URL（也可固定端口后直接探活）
```

更稳的做法：launcher 在冒烟模式**固定输出 URL 到 stdout**，测试脚本解析：

```bash
export AGENT_EXE_TEST=1
./build_exe/AI助手.exe > smoke.log &
sleep 6
URL=$(grep -oP 'SMOKE_URL=\K.*' smoke.log)
curl -sf "$URL" -o /dev/null && echo "INDEX=200"
curl -sf "${URL}assets/" -o /dev/null 2>/dev/null || true
```

### 6.2 冒烟断言清单

| 断言 | 通过条件 |
|---|---|
| EXE 进程存活 | 无崩溃退出 |
| `GET /` → 200 | 前端 index.html 可达 |
| `GET /` 含 `<div id="root">` | React 挂载点存在 |
| `GET /assets/index-*.js` → 200 | JS 资产已冻结 |
| 无 `[FATAL]` 日志 | 前端产物定位成功 |
| 无 CSP 报错 | 响应头含 `Content-Security-Policy` |

**通过即** `EXE_SMOKE=PASS`，证明前端已正确冻结进 EXE。

### 6.3 可选：Playwright 真浏览器级冒烟

沙箱无 Playwright 时可跳过；开发机可对冒烟 URL 跑 Playwright，断言页面加载后 `console` 无 error、`#root` 渲染出内容。

---

## 7. 交付全链路

### 7.1 版本与元数据（version.txt）

`build_exe/version.txt`（VSVersionInfo）：

```text
VSVersionInfo(
  ffi=FixedFileInfo(filevers=(4, 0, 0, 0), prodvers=(4, 0, 0, 0),
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0,
    date=(0, 0)),
  kids=[StringFileInfo([StringTable('040904B0', [
    StringStruct('CompanyName', 'AI 助手'),
    StringStruct('FileDescription', 'AI 助手 · 本地 Agent 应用'),
    StringStruct('FileVersion', '4.0.0.0'),
    StringStruct('ProductName', 'AI助手'),
    StringStruct('ProductVersion', '4.0.0.0')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])]
)
```

**作用**：资源管理器"详细信息"可见、显著降低 SmartScreen 误报（无签名但有元数据比裸 EXE 好）。

### 7.2 图标（app.ico）

- 要求：多尺寸 `.ico`（16/24/32/48/64/128/256），透明背景；
- 生成：从 PNG 用 `pillow` 或多尺寸工具转；打包前确认资源管理器/任务栏正常显示。

### 7.3 代码签名

| 阶段 | 证书 | 效果 |
|---|---|---|
| 开发期 | 自签证书（`makecert`/`New-SelfSignedCertificate`） | 本地测试签名流程 |
| 发布期 | Windows OV 证书（商业） | 消除 SmartScreen"未知发布者" |

签名命令（Windows SDK `signtool`）：

```bash
signtool sign /f mycert.pfx /p <密码> /fd SHA256 /t http://timestamp.digicert.com \
  build_exe/AI助手.exe
signtool verify /pa build_exe/AI助手.exe
```

> 发布必须用 **SHA-256** 时间戳签名；不做 SHA-1（已被禁用）。

### 7.4 自动更新

单文件 EXE 的更新思路（无需重装）：

| 方案 | 做法 | 适用 |
|---|---|---|
| 清单式自更新 | 应用启动时拉 `https://…/update.json`（`{version, url, sha256}`），发现新版 → 下载新 EXE 到临时目录 → 替换自身 | 推荐，简单可控 |
| 安装包式 | `--onedir` + Inno Setup 做安装器，更新 = 重跑安装器 | 需安装，非"单文件绿色" |

**清单式自更新要点**：

```json
{
  "version": "4.0.1",
  "url": "https://cdn.example.com/AI助手_4.0.1.exe",
  "sha256": "…",
  "notes": "修复 XX"
}
```

启动器每次启动异步检查：比对 `version.txt` → 有新版本下载到 `%TEMP%` → 校验 SHA-256 → 替换当前 EXE → 提示重启。下载失败静默跳过（不影响使用）。

### 7.5 体积瘦身（谨慎）

`--onefile` 体积大头是 Python 运行时。可选裁剪：

```bash
PyInstaller ... \
  --exclude-module tkinter --exclude-module test --exclude-module pydoc
```

**红线（v2.0 教训）**：
- **先做 import 扫描**，只砍确认无引用的模块；
- **必须保留 `unittest`**（历史教训：FinancialTrader v5.1 因过度裁剪导致运行时 `No module named unittest` 崩溃）；
- 裁剪后**必须重跑 §6 冒烟**，不允许"改了 spec 直接发"。

### 7.6 分发物清单

| 文件 | 说明 |
|---|---|
| `AI助手.exe` | 单文件成品（签名的） |
| `README.txt` | 使用说明：双击即用、@help 命令、设置面板填 API |
| `update.json` | 更新清单（有自更新时） |
| `版本说明.md` | 本次版本变更 |

---

## 8. 全链路检查表（发布前）

| # | 检查项 | 方法 |
|---|---|---|
| 1 | 前端构建通过 | `npm run build` 0 错误；`base:'./'` |
| 2 | PyInstaller 打包成功 | 产出 `AI助手.exe`，PE/MZ 有效 |
| 3 | 无界面冒烟 | `AGENT_EXE_TEST=1` + curl → index 200 / #root / JS 200 → `EXE_SMOKE=PASS` |
| 4 | 桌面窗口可起 | 开发机双击 → pywebview 窗口出现；关掉 WebView 回退浏览器 |
| 5 | 体积达标 | ≤ 目标（当前 43.3 MiB；瘦身须重跑冒烟） |
| 6 | 元数据齐全 | version.txt 生效、图标显示 |
| 7 | 签名有效 | `signtool verify` 通过；时间戳存在 |
| 8 | 更新清单可达 | `update.json` URL 可下载且 sha256 匹配 |
| 9 | 安全头 | 冒烟响应头含 CSP/nosniff |
| 10 | 回归红线 | v1.0 的 17/17 功能断言仍过（功能未因打包回归） |

---

## 9. 常见问题排查

| 现象 | 原因 | 处理 |
|---|---|---|
| 双击后无反应 | `--windowed` 无控制台，错误被吞 | 临时去掉 `--windowed` 或用 `AGENT_EXE_TEST=1` 看 stdout |
| `No module named webview` | pywebview 未 hidden-import | 加 `--hidden-import webview` |
| 页面 404 / 白屏 | `dist` 未打进或路径错误 | 检查 `--add-data "dist;webdist"`；确认 `vite base:'./'` |
| 启动慢 | `--onefile` 每次解压 | 接受或改 `--onedir` + 安装包 |
| SmartScreen 拦截 | 无签名 / 新文件 | 签名 + 元数据 + 分发一段时间积累信誉 |
| 被杀软误报 | PyInstaller 行为特征 | 签名、减少壳、联系厂商申报 |
| CSP 导致资源加载失败 | 策略过严 | 按需放宽 `img-src`/`style-src` 但保持 `default-src 'self'` |

---

## 10. 总结

> **Windows 桌面 EXE = 前端构建(`npm run build`) + PyInstaller(`--onefile --windowed`) + 启动器(本地托管 + pywebview) + 无界面冒烟 + 交付(元数据/签名/更新)。**

**全链路一句话**：`npm run build` 出 `dist/` → `PyInstaller` 把 `dist/` 冻结成单文件 `AI助手.exe` → 启动器用本地 `http.server` 托管 + pywebview 弹窗 → `AGENT_EXE_TEST=1` 无界面冒烟确认前端冻结正确 → 补版本/图标/签名/更新清单 → 发布。

**三个不可妥协**：冒烟必须能证明"前端真的冻进去了"（而非只看 EXE 能跑）；瘦身必须先 import 扫描、保留 `unittest`、裁剪后重跑冒烟；发布必须 SHA-256 签名。

---

*— 本文档为 AI.Super Agent打包交付专篇 v4.0，命令与尺寸数据基于 v1.0 沙箱实测（PyInstaller 6.20.0、43.3 MiB、EXE_SMOKE=PASS），交付链路（签名/更新/瘦身）标注了操作路径与红线。实施时以实际环境复核。*

---

# Part IV — 可行性结论与升级路线图　📋 计划 / 可行性

> 本节为后续升级开发的基线：明确"什么是已验证的坚实底座""有哪些现成扩展点""升级哪些能力可行、风险在哪""推荐路线怎么走"。

## IV.1 当前可行性基线（已验证的坚实底座）

| 能力 | 验证状态 | 证据 |
|---|---|---|
| 单文件 EXE 交付 | 🔬 已实测 | PyInstaller `--onefile --windowed` 出 `AI.Super-Agent.exe` ≈ 43.3 MiB，PE/MZ 有效，冒烟 `EXE_SMOKE=PASS` |
| 工具永不失效（本地/云端双路） | 🔬 设计已落地 | Tool Registry 双路复用架构；云端模式 `@calc` 走本地执行 |
| 长对话成本恒定 | 🔬 实测 | 上下文预算封顶，50 轮 payload ≤ 6200 字符（设计值，📐 待回归） |
| 零 eval 安全 | 🔬 实测 | 递归下降 Parser 替代 `new Function`；CSP `script-src 'self'` 可开启 |
| KB 召回 | 🔬 实测 | 打分制后 7/7 正确（v1.0 为 3/7） |
| 防抖落盘 | 🔬 实测 | 600 字回复写入 600→1 次，序列化 3.986MB→0.007MB（-99.8%） |
| 联网搜索免密钥 | 📐 设计 | 本地启动器 `/api/websearch` 代理 DuckDuckGo；设计合理，📋 待回归确认 |
| Skills / MCP 扩展 | 📐 设计 | 目录规范 + MCP 客户端；设计合理，📋 待回归确认 |

## IV.2 已具备的扩展点（升级开发的基础）

- **Skills 目录规范**（`SKILL.md` + `tools/*.js`）：丢目录即获得能力，不改核心代码。
- **MCP 客户端**（HTTP / Streamable）：外部工具自动注册进 Tool Registry。
- **Provider 预设模板**（DeepSeek / Kimi / GLM / Qwen / Doubao / OpenAI / Ollama）：统一 OpenAI 兼容协议 + 兼容垫片。
- **本地桥进程**（承载 MCP stdio / 搜索抓取 / node 技能沙箱）：隔离崩溃与权限。
- **记忆服务**（类型化 + 模糊召回 + TTL + 导入导出）与**审计哈希链**（防篡改）。

## IV.3 升级可行性评估（按能力域）

| 能力域 | 可行性 | 主要风险 | 建议 |
|---|---|---|---|
| 联网搜索增强（多引擎/缓存） | 高 | 搜索引擎限流/反爬 | 保留 DDG 兜底 + 可配 SearXNG/Bing |
| Skills 生态 | 高 | 恶意技能沙箱逃逸 | 子进程沙箱 + 权限门 + 审计链（必做） |
| MCP stdio 桥接 | 中 | 需宿主进程/Python 桥 | 本轮未做，列入 Phase 1 |
| 国内大模型深度适配 | 高 | 各厂商 tools 支持参差 | text-action 文本协议兜底（已设计） |
| 记忆自动抽取（LLM） | 中 | 抽取误记污染 | 置信度阈值 + 去重 + 用户可编辑 |
| ReAct 推理可视化 | 高 | UI 表现未实测 | Playwright 复核折叠卡片 |
| Claude 风格渲染 | 高 | XSS | `html:false` + DOMPurify 双保险 |
| 商业代码签名 | 中 | 需 OV 证书成本 | 发布前用 SHA-256 时间戳签名 |
| Tauri 主流水线 | 低（沙箱不可构建） | 需 Rust/WebView2 开发机 | PyInstaller 回退线保底 |

## IV.4 推荐升级路线（Phase 建议）

| 阶段 | 目标 | 关键交付 | 可行性 |
|---|---|---|---|
| Phase 0 | 噪音清理 + 回归基线 | 建立 54/54 式回归用例（替代未复核断言） | 🔬 高 |
| Phase 1 | MCP stdio 桥 + 签名 | 外部工具全通 + 消除 SmartScreen | 📐 中 |
| Phase 2 | 记忆 LLM 抽取 + 长程摘要 | 自动"会记会用" | 📐 中 |
| Phase 3 | ReAct/Claude 渲染复核 | UI 表现落地验证 | 🔬 高 |
| Phase 4 | Tauri 主线（开发机） | ~8MB 原生壳（📐 未实测） | 📐 低（环境依赖） |

## IV.5 已知风险与待决项（诚实说明）

- **未做商业签名**：当前 EXE 首次运行可能被 SmartScreen 提示（继续运行即可）。
- **MCP 仅 HTTP/Streamable**：stdio MCP 需 Python 桥接，本轮未做。
- **Tauri ~8MB / Lighthouse ≥85**：均为 📐 设计预期，未实测；不得当承诺。
- **国内厂商端点/模型名**：以官方文档为准，预设模板为初始值，设置面板可改。
- **功能断言数字**：本文不采纳任何未复核的"54/54"类声明，一切以 Phase 0 建立的回归测试为准。

---


# Appendix A — 当前交付物与可行性附注

## A.1 主产物（文件存在为 🔬 事实）

| 项 | 值 |
|---|---|
| 产品名 | AI.Super Agent |
| 主产物 | `AI.Super-Agent.exe`（约 43.3 MiB / 45.4 MB，PE/MZ 有效） |
| 构建形态 | PyInstaller 6.20.0 `--onefile --windowed` |
| 构建时间 | 2026-08-02 |
| 功能断言 | 📋 **以回归测试为准**（本文不采纳未复核的断言数字） |

## A.2 架构要点（📐 设计，落地合理）

- 前端：零构建静态站点（React UMD + 原生 ES Module）
- 启动器：标准库 `http.server` 在随机本地端口托管，`pywebview` 弹窗，异常回退浏览器
- 联网：启动器 `/api/websearch` 代理抓取并解析返回 JSON（规避 CORS）
- 单文件：前端作为 `--add-data webroot;webdist` 冻结进 EXE

## A.3 使用摘要

双击 `AI.Super-Agent.exe` → 桌面窗口（缺 WebView2 回退浏览器）→ 直接对话或使用 `@` 命令：
`@calc` `@remember` `@recall` `@list` `@time` `@web` `@skills` `@skill` `@mcp` `@help`。
设置面板填厂商 / API Base URL / Key / 模型名（DeepSeek、Kimi、智谱 GLM、通义千问、豆包、OpenAI、Ollama）；未填或不可达自动回退本地引擎。

## A.4 已知限制

- 未做商业代码签名，首次运行可能被 SmartScreen 提示。
- `pywebview` 窗口依赖系统 WebView2；缺失时自动回退浏览器。
- 云端能力需用户自备 API Key。
- MCP 仅支持 HTTP / Streamable；stdio 需 Python 桥接（未做）。

## A.5 噪音清洗对照（供溯源）

| 噪音来源 | 处理 |
|---|---|
| 版本说明.md / README.txt / update.json（智云命名） | 智云命名视为过时，统一为 AI.Super Agent；其交付元数据仅作参考 |
| 未复核「54/54 功能断言通过」 | 不采纳，改为回归测试为准 |
| 目录重复文档（v2.0 副本、`*_claude` 变体、各交付说明） | 以本文件为唯一权威；其余建议归档 |

## A.6 冗余源文件处理建议（待用户确认）

以下文件在本基线文档完成后已冗余，**按个人目录删除规则未擅自删除**，建议归档/删除：
`AI助手_工程技术文档_v2.0 - wd.md`、`AI助手_工程技术文档_v3.0_claude.md`、`AI助手_工程技术文档_v4.0_claude.md`、`版本说明.md`、`README.txt`、`update.json`、以及上一版 `智云_AI助手_工程技术文档_集成总册.md`。

---

*— 本可行性基线文档由 v2.0 基座、v3.0 能力扩展、v4.0 打包交付三份权威文档清洗融合而成，并新增 Part IV 升级路线图。标注 🔬 为实测、📐 为设计、📋 为计划；未实测的"预期"数字不得当事实引用。*
