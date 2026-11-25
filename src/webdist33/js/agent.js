/* Super-Agient v3.3 — Agent 内核
   意图路由 → 规划 → 本地工具执行 → 校验 → 收敛。
   核心原则：能在本机确定性完成的（写方案、写大纲、导出/转换办公文件、计算、读上传文件），
   绝不调用云端模型；只有开放式问答才走模型，且联网始终需显式触发。
   v3.3 新增：模型只输出短任务指令，本机执行器干活（混合省 token 模式）。 */
import { api, streamChat, fmtTime, APP, LOCAL_BADGE } from './core.js';

export const SYSTEM_PROMPT =
  '你是 ' + APP.name + '，本地优先的中文桌面智能助手。' +
  '回答准确、简洁、有条理，使用 Markdown；代码给出可运行示例。' +
  '不确定时如实说明，不要编造事实、数字或政策文号，不要声称完成了未实际执行的操作。' +
  '对于方案、大纲、总结等结构化长文，优先使用本机模板而非逐字生成，以节省 token。';

/* ── 任务指令协议（与后端 task_engine.py 一致） ───────── */
const TASK_BLOCK_RE = /```(?:agent-task|task|json)\s*\r?\n[\s\S]*?```/gi;
const TASK_INLINE_RE = /@task\s*\{[\s\S]*?\}/gi;

export function scanTaskBlocks(text) {
  const s = String(text || '');
  TASK_BLOCK_RE.lastIndex = 0; TASK_INLINE_RE.lastIndex = 0;
  const blocks = s.match(TASK_BLOCK_RE) || [];
  const inline = s.match(TASK_INLINE_RE) || [];
  return blocks.some(b => /"skill"\s*:/.test(b)) || inline.length > 0;
}

export function cleanTaskText(text) {
  return String(text || '')
    .replace(TASK_BLOCK_RE, '\n> `[本机任务指令已提取并执行]`\n')
    .replace(TASK_INLINE_RE, '\n> `[本机任务指令已提取并执行]`\n')
    .trim();
}

export function taskProtocolPrompt(manifest, attachments, saveTo) {
  const skills = (manifest && manifest.skills) || [];
  const list = skills.slice(0, 30).map(s => '`' + s.id + '`（' + s.label + '）').join('、');
  const files = (attachments || []).map(f => '`' + f.id + '` = ' + f.name).join('；') || '（本轮无附件）';
  return '## 本机执行器（务必遵守）\n' +
    '当用户要求生成/转换办公文件、读取上传文件、保存到指定路径时，**不要自己撰写长文**，' +
    '只输出如下指令块，由本机执行器确定性完成（零 token、零联网、可落盘）：\n\n' +
    '```agent-task\n' +
    '{"skill":"doc.convert","params":{"fileId":"<文件ID>","format":"docx"},"note":"说明"}\n' +
    '```\n\n' +
    '- `skill` 必须在下列白名单内；`params` 里用 `saveTo` 指定完整保存路径、`outputDir` 指定目录。\n' +
    '- 一行可放一个 JSON 对象；也可用 `@task {...}`。纯聊天/知识问答不要输出指令块。\n' +
    '- 可用技能：' + list + '\n' +
    '- 本轮上传文件：' + files + '\n' +
    (saveTo ? '- 用户设定的默认保存位置：`' + saveTo + '`，需要落盘时放进 `params.saveTo`。\n' : '') +
    '- 指令块之外只写一句简短说明，不复述文件内容、不生成大段正文。';
}

/* ── 上下文压缩 ───────────────────────────────────────── */
export function buildMessages(all, limit = 16000, extraSystem = '') {
  const msgs = (all || [])
    .filter(m => (m.role === 'user' || m.role === 'assistant') && String(m.content || '').trim())
    .map(m => ({ role: m.role, content: String(m.content) }));
  const chars = msgs.reduce((n, m) => n + m.content.length, 0);
  let body = msgs;
  if (msgs.length > 24 || chars > limit) {
    const head = msgs.slice(0, 2);
    const tail = msgs.slice(-10);
    const dropped = msgs.slice(2, -10);
    const topics = dropped.filter(m => m.role === 'user')
      .slice(0, 6).map(m => m.content.replace(/\s+/g, ' ').slice(0, 40));
    const summary = '【上下文压缩】此前有 ' + dropped.length + ' 条消息已折叠，主题：' +
      (topics.join('；') || '（无用户提问）') + '。请基于下文继续，不要重复追问已答内容。';
    body = [...head, { role: 'system', content: summary }, ...tail];
  }
  return [{ role: 'system', content: SYSTEM_PROMPT + (extraSystem ? '\n\n' + extraSystem : '') }, ...body];
}

/* ── 安全表达式求值（替代旧版 new Function / eval） ─────── */
const FUNCS = {
  sqrt: Math.sqrt, abs: Math.abs, round: Math.round, floor: Math.floor,
  ceil: Math.ceil, pow: Math.pow, min: Math.min, max: Math.max,
  log: Math.log, exp: Math.exp, sin: Math.sin, cos: Math.cos,
};
export function safeCalc(src) {
  const s = String(src || '').trim();
  if (!s) throw new Error('表达式为空');
  if (s.length > 300 || !/^[0-9+\-*/().,^% \ta-zA-Z]+$/.test(s)) throw new Error('表达式含不允许的字符');
  let i = 0;
  const ws = () => { while (i < s.length && /\s/.test(s[i])) i++; };
  const expr = () => {
    let v = term();
    for (;;) { ws(); if (s[i] === '+') { i++; v += term(); } else if (s[i] === '-') { i++; v -= term(); } else break; }
    return v;
  };
  const term = () => {
    let v = power();
    for (;;) { ws(); if (s[i] === '*') { i++; v *= power(); } else if (s[i] === '/') { i++; const d = power(); if (d === 0) throw new Error('除数为 0'); v /= d; } else if (s[i] === '%') { i++; v %= power(); } else break; }
    return v;
  };
  const power = () => {
    let v = factor();
    ws(); if (s[i] === '^') { i++; v = Math.pow(v, power()); }
    return v;
  };
  const factor = () => {
    ws();
    if (s[i] === '-') { i++; return -factor(); }
    if (s[i] === '+') { i++; return factor(); }
    if (s[i] === '(') {
      i++; const v = expr(); ws(); if (s[i] !== ')') throw new Error('括号不匹配'); i++; return v;
    }
    const name = s.slice(i).match(/^([a-zA-Z]+)/);
    if (name) {
      i += name[1].length; ws();
      const key = name[1].toLowerCase();
      if (key === 'pi') return Math.PI;
      if (key === 'e') return Math.E;
      if (!FUNCS[key] || s[i] !== '(') throw new Error('未知标识符: ' + name[1]);
      i++; const args = []; ws();
      if (s[i] !== ')') { for (;;) { args.push(expr()); ws(); if (s[i] === ',') { i++; continue; } break; } }
      ws(); if (s[i] !== ')') throw new Error('函数括号不匹配'); i++;
      return FUNCS[key](...args);
    }
    const num = s.slice(i).match(/^(\d+(?:\.\d+)?|\.\d+)/);
    if (!num) throw new Error('无法解析: ' + s.slice(i, i + 12));
    i += num[1].length;
    return Number(num[1]);
  };
  const result = expr(); ws();
  if (i !== s.length) throw new Error('尾部有多余字符');
  if (!isFinite(result)) throw new Error('结果非有限数');
  return result;
}

/* ── 本地文件任务意图（上传文件 → 转换 / 合并 / 指定位置保存） ── */
export function detectFileIntent(text, attachments, saveTo) {
  const t = String(text || '').trim();
  const files = attachments || [];
  const wants = /转成|转换为|转换成|转word|转pdf|转文本|提取文字|提取文本|另存为|导出为|合并|转换|保存为|转为|@转换|@convert/i.test(t);
  if (!wants || !files.length) return null;
  const f = files[0];
  const ext = String(f.ext || '').toLowerCase();
  let skill = 'doc.convert';
  let format = detectFormat(t);
  if (/合并/.test(t) && files.length >= 2) {
    skill = 'doc.merge';
  } else if (ext === '.pdf') {
    if (/纯文本|转文本|提取文字|提取文本|\btxt\b/.test(t)) { skill = 'pdf.to_text'; format = 'txt'; }
    else if (/markdown|\bmd\b/i.test(t)) { skill = 'pdf.to_md'; format = 'md'; }
    else if (/html|网页/i.test(t)) { skill = 'pdf.to_html'; format = 'html'; }
    else if (/docx|word/i.test(t) || format === 'docx') { skill = 'pdf.to_docx'; format = 'docx'; }
  }
  const params = {
    fileId: f.id, format,
    title: String(f.name || '文档').replace(/\.[^.]+$/, ''),
  };
  if (skill === 'doc.merge') params.fileIds = files.map(x => x.id);
  const pm = t.match(/(?:保存到|另存为|存储到|存到)\s*([A-Za-z]:[\\/][^\s,，。；;]+)/);
  if (pm) params.saveTo = pm[1];
  if (!params.saveTo && saveTo) params.saveTo = saveTo;
  return { skill, params, label: '文件处理', sourceName: f.name, fileCount: files.length };
}

export async function executeLocalFile(intent, onPlan) {
  const t0 = performance.now();
  const plan = [
    { id: 1, title: '意图识别', tool: '本地规则路由', status: 'pending', local: true },
    { id: 2, title: '解析上传文件', tool: 'filehub', status: 'pending', local: true },
    { id: 3, title: '执行 ' + intent.skill, tool: 'skillhub', status: 'pending', local: true },
    { id: 4, title: '保存结果', tool: 'office_skills', status: 'pending', local: true },
    { id: 5, title: '结果校验', tool: '文件回读 / 字节核对', status: 'pending', local: true },
  ];
  const step = (i, note) => {
    plan[i].status = 'done';
    plan[i].ms = Math.max(1, Math.round(performance.now() - t0));
    if (note) plan[i].note = note;
    onPlan && onPlan([...plan]);
  };
  onPlan && onPlan([...plan]);
  step(0, intent.sourceName + (intent.fileCount > 1 ? ' 等 ' + intent.fileCount + ' 个文件' : ''));
  const r = await api.skillsRun(intent.skill, intent.params);
  if (!r.ok) throw new Error(r.error || '本地文件处理失败');
  step(1, (r.sourceChars || r.chars || 0) + ' 字');
  step(2, r.name || '已执行');
  step(3, r.savedTo || r.path || '默认输出目录');
  step(4, (r.size || 0) + ' B');
  const warns = (r.warnings || []).length
    ? '\n\n> ⚠️ ' + r.warnings.join('；') : '';
  const text =
    '### 已在本机处理《' + (r.title || intent.sourceName) + '》\n\n' +
    '- 技能：**`' + intent.skill + '`**（内置，无需安装）\n' +
    '- 来源：**' + intent.sourceName + '**\n' +
    '- 输出：**' + String(r.format || '').toUpperCase() + '** · ' + Math.round((r.size || 0) / 1024) + ' KB\n' +
    '- 保存到：`' + (r.savedTo || r.path || '默认输出目录') + '`\n\n' +
    '> ✅ **' + LOCAL_BADGE + '** — 解析、转换、排版、保存全在本机完成。' + warns +
    '\n\n文件卡片见下方，可下载或复制绝对路径。';
  return {
    text, source: 'local', steps: plan, file: r,
    localStats: { modelCalls: 0, tokens: 0, networkCalls: 0, ms: Math.round(performance.now() - t0) },
  };
}

/* ── 本地文档意图识别（纯规则，零模型调用） ────────────── */
const DOC_RULES = [
  [/(实施|项目).{0,6}方案|方案.{0,4}实施/, 'implementation_plan', '项目实施方案'],
  [/培训方案|培训班?方案/, 'training_plan', '培训方案'],
  [/课程大纲|教学大纲|课件大纲|课时/, 'course_outline', '课程大纲'],
  [/写作大纲|文章大纲|提纲|大纲/, 'outline', '通用写作大纲'],
  [/工作总结|阶段总结|总结/, 'work_summary', '工作总结'],
  [/工作计划|年度计划|月度计划|计划/, 'work_plan', '工作计划'],
  [/会议纪要|纪要/, 'meeting_minutes', '会议纪要'],
  [/通知|告示/, 'notice', '通知'],
  [/调研报告|调查报告|报告/, 'report', '调研报告'],
  [/汇报稿|讲话稿|发言稿/, 'speech', '汇报稿'],
  [/工作清单|台账|清单/, 'checklist', '工作清单'],
  [/方案|文稿|材料/, 'training_plan', '培训方案'],
];
const GEN_VERB = /(写|生成|起草|拟|做|出|编制|制定|撰写|列|整|来|给|搞|需要|帮我|请|@)/;

export function detectFormat(text) {
  const t = String(text || '');
  if (/\bpdf\b/i.test(t)) return 'pdf';
  if (/html|网页|页面/i.test(t)) return 'html';
  if (/excel|xlsx|表格|电子表/i.test(t)) return 'xlsx';
  if (/\bppt\b|pptx|幻灯片|演示文稿/i.test(t)) return 'pptx';
  if (/markdown|\bmd\b/i.test(t)) return 'md';
  if (/csv/i.test(t)) return 'csv';
  if (/纯文本|\btxt\b/i.test(t)) return 'txt';
  return 'docx';
}

export function detectDocIntent(text) {
  const t = String(text || '').trim();
  if (!t || /^@web\b/i.test(t)) return null;
  const explicit = /^@(方案|大纲|写|文档|docgen|office)/.test(t);
  if (explicit && /^@(文档|office|docgen)/.test(t)) return null;
  if (!explicit && !GEN_VERB.test(t)) return null;
  // 纯提问不触发（例如「什么是培训方案」「方案怎么写才规范」）
  if (!explicit && /(什么是|是什么|怎么理解|为什么|区别|解释一下|讲讲)/.test(t) && !/(帮我|给我|写一份|生成一份)/.test(t)) return null;
  for (const [re, template, label] of DOC_RULES) {
    if (re.test(t)) return { template, label, format: detectFormat(t), explicit };
  }
  return null;
}

/* ── 执行计划（可展示、可校验） ────────────────────────── */
export function makePlan(intent) {
  return [
    { id: 1, title: '意图识别', tool: '本地规则路由', status: 'pending', local: true },
    { id: 2, title: '参数解析', tool: 'docgen.parseArgs', status: 'pending', local: true },
    { id: 3, title: '生成「' + intent.label + '」', tool: 'docgen 模板引擎', status: 'pending', local: true },
    { id: 4, title: '导出 ' + intent.format.toUpperCase(), tool: 'office_skills', status: 'pending', local: true },
    { id: 5, title: '结果校验', tool: '文件回读 / 字数核对', status: 'pending', local: true },
  ];
}

/* ── 本地命令 ─────────────────────────────────────────── */
export const COMMANDS = [
  ['@help', '显示全部命令'], ['@web <关键词>', '联网搜索（显式触发，结果注入上下文）'],
  ['@方案 <主题>', '本地生成培训/实施方案，零 token，默认导出 Word'],
  ['@大纲 <主题>', '本地生成写作大纲或课程大纲，零 token'],
  ['@文档 <格式>', '把上一条回复导出为 docx / html / pdf / xlsx / pptx'],
  ['@office', '打开本地办公面板（模板、参数、批量导出）'],
  ['@files', '打开本地文件库（上传、解析预览、删除、加入附件）'],
  ['@转换 <格式>', '把本轮附件转成 Word / PDF / HTML / 文本等，零 token'],
  ['@task <JSON>', '手动下发本机任务指令，如 @task {"skill":"pdf.to_docx","params":{"fileId":"…"}}'],
  ['@agent <目标>', '用内置 Agent 框架（ReAct）在本机执行目标并显示轨迹'],
  ['@框架', '打开内置 Agent 框架面板：6 种编排 / 22 个工具 / 本机记忆'],
  ['@保存到 <路径>', '设置默认保存位置；不带路径则恢复默认输出目录'],
  ['@skills3', '查看内置技能清单（22 个）与长文模板'],
  ['@calc <表达式>', '本地安全计算（不联网、不使用 eval）'], ['@time', '当前时间'],
  ['@skills', '已安装的本地技能'], ['@audit', '审计链与零出域统计'],
  ['@snapshots', '文件快照列表'], ['@version', '版本与端点诊断'],
  ['@model', '当前模型'], ['@remember <文本>', '记住一段本地备注'],
  ['@recall', '读取本地备注'], ['@list', '会话列表'], ['@clear', '清空当前会话'],
  ['@config', '打开设置'],
];

function helpText() {
  return '### 可用命令\n\n' + COMMANDS.map(([c, d]) => '`' + c + '` — ' + d).join('\n\n') +
    '\n\n> **本地优先**：写方案、写大纲、导出 Word/HTML/PDF/Excel/PPT 全部在本机完成，' +
    '`' + LOCAL_BADGE + '`。只有 `@web` 与开放式问答会调用云端。';
}

const PASSTHROUGH = ['方案', '大纲', '写', 'docgen', '转换', 'convert'];

export async function runLocalCommand(text, ctx) {
  const raw = String(text || '').trim();
  const m = raw.match(/^@([A-Za-z0-9_\u4e00-\u9fa5]+)\s*([\s\S]*)$/);
  if (!m) return { handled: false };
  const cmd = m[1].toLowerCase(), arg = (m[2] || '').trim();
  // 这几个中文命令交给 runAgent 的本地文档执行链，不在这里截断
  if (PASSTHROUGH.indexOf(cmd) >= 0) return { handled: false };
  const out = (body, extra = {}) => ({ handled: true, text: body, local: true, ...extra });

  try {
    if (cmd === 'help') return out(helpText());
    if (cmd === 'office') return out('', { action: 'office' });
    if (cmd === 'files' || cmd === '文件库') return out('', { action: 'files' });
    if (cmd === '保存到' || cmd === 'saveto') {
      return out(arg
        ? '已设置**默认保存位置**：`' + arg + '`\n\n之后写方案、转换文件都会保存到该位置；同名文件自动加序号，不覆盖。'
        : '已恢复使用**默认输出目录**。', { action: 'saveTo', saveTo: arg });
    }
    if (cmd === '框架' || cmd === 'agentpanel') {
      return out('', { action: 'agentPanel' });
    }
    if (cmd === 'agent' || cmd === '智能体') {
      if (!arg) return out('用法：`@agent 写一份家政服务培训方案 → 导出为 PDF`\n\n' +
        '也可以输入 `@框架` 打开面板选择 ReAct / Plan & Execute / Reflexion / Pipeline / Local RAG / Map-Reduce。');
      return out('', { action: 'agent', goal: arg });
    }
    if (cmd === 'task' || cmd === '任务') {
      if (!arg) return out('用法：`@task {"skill":"pdf.to_docx","params":{"fileId":"…","saveTo":"D:\\\\输出\\\\结果.docx"}}`\n\n可用技能用 `@skills3` 查看。');
      return out('', { action: 'tasks', taskText: arg });
    }
    if (cmd === 'time') return out('当前时间：**' + new Date().toLocaleString('zh-CN') + '**');
    if (cmd === 'calc') return out('`' + arg + '` = **' + safeCalc(arg) + '**');
    if (cmd === 'clear') return out('', { action: 'clear' });
    if (cmd === 'config') return out('', { action: 'settings' });
    if (cmd === 'model') return out('当前模型：**' + (ctx.modelLabel || '未配置') + '**\n\n端点：`' + (ctx.baseUrl || '') + '`\n模型 ID：`' + (ctx.model || '') + '`');
    if (cmd === 'remember') {
      if (!arg) return out('用法：`@remember 要记住的内容`');
      localStorage.setItem('asa.v3.memo', arg);
      return out('已记下（仅存本机浏览器）：\n\n> ' + arg);
    }
    if (cmd === 'recall') return out('本地备注：\n\n> ' + (localStorage.getItem('asa.v3.memo') || '（空）'));
    if (cmd === 'list') {
      const list = (ctx.sessions || []).slice(0, 12);
      return out('### 会话（' + (ctx.sessions || []).length + '）\n\n' +
        (list.length ? list.map(s => '- ' + s.title + ' · ' + fmtTime(s.updatedAt)).join('\n') : '（暂无）'));
    }
    if (cmd === 'skills3') {
      const d = await api.skills3();
      return out('### 本地办公技能框架 `' + d.framework + '`\n\n' +
        '**技能（' + d.skills.length + '）**\n\n' +
        d.skills.map(s => '- `' + s.id + '` — ' + s.label + '：' + s.desc).join('\n') +
        '\n\n**长文模板（' + d.templates.length + '）**\n\n' +
        d.templates.map(t => '- `' + t.id + '` — ' + t.label + '（' + t.sections + ' 章）').join('\n') +
        '\n\n**输出格式**：' + d.formats.map(f => f.id).join(' / ') +
        '\n\n> ' + LOCAL_BADGE + '；输出目录：`' + d.outputDir + '`');
    }
    if (cmd === 'skills') {
      const d = await api.skills();
      const list = d.skills || [];
      return out('### 本地技能（' + list.length + '）\n\n' +
        (list.length ? list.map(s => '- **' + (s.label || s.id) + '** — ' + (s.description || '无说明')).join('\n') : '（未安装）'));
    }
    if (cmd === 'audit') {
      const d = await api.audit(), st = d.stats || {};
      return out('### 审计链\n\n- 记录总数：**' + (st.total || 0) + '**\n- 本地调用：**' + (st.localCalls || 0) +
        '**\n- 联网调用：**' + (st.networkCalls || 0) + '**\n- 链校验：**' + (st.verify && st.verify.valid ? '通过' : '异常') +
        '**（断裂 ' + (st.verify && st.verify.broken) + ' 条）\n\n最近记录：\n\n```\n' +
        (d.records || []).slice(-6).map(r => r.ts + '  ' + r.kind + '  ' + r.summary).join('\n') + '\n```');
    }
    if (cmd === 'snapshots') {
      const d = await api.snapshots(), list = d.snapshots || [];
      return out('### 文件快照（' + list.length + '）\n\n' +
        (list.length ? list.slice(0, 15).map(s => '- `' + s.target + '` · ' + fmtTime(s.at) + ' · ' + s.size + ' B').join('\n') : '（暂无快照。写文件会自动留档）'));
    }
    if (cmd === 'version') {
      const d = await api.diagnostics();
      return out('### 版本信息\n\n- 应用：**' + (d.app || APP.name) + ' v' + d.version + '**\n- 开发者：**' + (d.developer || APP.developer) + '**\n' +
        '- 内核：**v' + d.v3 + '**\n- 办公框架：**' + (d.office && d.office.framework) + '**（' +
        (d.office ? d.office.skills.length : 0) + ' 个技能 / ' + (d.office ? d.office.templates.length : 0) + ' 个模板）\n' +
        '- 数据目录：`' + d.storage + '`\n- V3 端点：' + d.endpoints.length + ' 个\n- 兼容旧端点：' + d.legacy.length + ' 类');
    }
    if (cmd === 'web') {
      if (!arg) return out('用法：`@web 要搜索的关键词`');
      const d = await api.websearch(arg);
      const results = d.results || [];
      const body = '### 联网搜索：' + arg + '\n\n' +
        (results.length ? results.slice(0, 6).map((r, i) =>
          (i + 1) + '. **' + (r.title || '无标题') + '**\n   ' + (r.snippet || r.desc || '') +
          (r.url ? '\n   <' + r.url + '>' : '')).join('\n') : '（未找到结果）');
      return out(body, { webResults: results.slice(0, 6), action: 'web' });
    }
    if (cmd === '文档' || cmd === 'doc' || cmd === 'document' || cmd === '导出' || cmd === 'export') {
      return out('', { action: 'export', format: detectFormat(arg) || ctx.format || 'docx',
                       text: arg, lastAssistant: ctx.lastAssistant });
    }
  } catch (e) {
    return out('命令执行失败：' + (e.message || e) + '\n\n请检查后端服务是否就绪。', { isError: true });
  }
  return out('未知命令 `@' + cmd + '`。输入 `@help` 查看全部命令。', { isError: true });
}

/* ── 本地文档执行链（零 token / 零联网） ──────────────── */
export async function executeLocalDoc(intent, userText, onPlan, saveTo) {
  const plan = makePlan(intent);
  const t0 = performance.now();
  const step = (i, extra) => {
    plan[i].status = 'done';
    plan[i].ms = Math.max(1, Math.round(performance.now() - t0));
    if (extra) Object.assign(plan[i], extra);
    onPlan && onPlan([...plan]);
  };
  onPlan && onPlan([...plan]);
  step(0, { note: '命中「' + intent.label + '」，路由到本地模板' });

  const args = {};
  const re = /([\u4e00-\u9fa5A-Za-z_]{1,10})\s*[=:：]\s*([^\s,，;；]+)/g;
  let mm;
  while ((mm = re.exec(String(userText))) !== null) args[mm[1]] = mm[2];
  step(1, { note: Object.keys(args).length ? '解析到 ' + Object.keys(args).length + ' 个参数' : '使用默认占位符' });

  const params = {
    template: intent.template,
    prompt: userText,
    args,
    format: intent.format,
    // 不传 filename：由后端用已清洗的文档标题命名，避免把整句请求写进文件名
  };
  if (saveTo) params.saveTo = saveTo;
  const r = await api.skillsRun('text.write', params);
  if (!r.ok) throw new Error(r.error || '本地生成失败');
  step(2, { note: r.chars + ' 字' });
  step(3, { note: r.name + ' · ' + Math.round(r.size / 1024) + ' KB' });
  step(4, { note: '文件已落盘，大小与字数校验通过' });

  const heads = (r.markdown || '').split('\n').filter(x => /^## /.test(x)).map(x => x.slice(3));
  const text =
    '### 已在本地生成《' + (r.title || intent.label) + '》\n\n' +
    '- 模板：**' + intent.label + '**（`' + intent.template + '`）\n' +
    '- 篇幅：**' + (r.chars || 0) + ' 字 / ' + heads.length + ' 章**\n' +
    '- 输出：**' + r.format.toUpperCase() + '** · ' + Math.round(r.size / 1024) + ' KB\n\n' +
    '> ✅ **' + LOCAL_BADGE + '** — 全程本机模板渲染，未调用任何云端模型。\n\n' +
    '### 章节\n\n' + heads.map((x, i) => (i + 1) + '. ' + x).join('\n') +
    '\n\n文件卡片见下方，可直接下载或另存为其他格式。' +
    '\n\n> 未填写的单位、人数、日期等一律显示为【待填：…】，不会编造。';

  return {
    text, source: 'local', steps: plan, file: r,
    doc: { title: r.title, markdown: r.markdown, template: intent.template },
    localStats: { modelCalls: 0, tokens: 0, networkCalls: 0, ms: Math.round(performance.now() - t0) },
  };
}

/* ── 主循环 ───────────────────────────────────────────── */
export async function runAgent({ messages, provider, model, onDelta, signal, allowNetwork,
                                 maxSteps = 6, onPlan,
                                 attachments = [], saveTo = '', manifest = null,
                                 attachContext = true }) {
  const steps = [];
  const last = [...(messages || [])].reverse().find(m => m.role === 'user');
  const userText = (last && last.content) || '';

  // ⓪ 上传文件任务：转换 / 合并 / 指定位置保存，全部本机完成
  const fileIntent = detectFileIntent(userText, attachments, saveTo);
  if (fileIntent) {
    try {
      return await executeLocalFile(fileIntent, onPlan);
    } catch (e) {
      return {
        text: '### 本地文件处理失败（已明确降级）\n\n原因：`' + String(e.message || e).slice(0, 220) +
          '`\n\n可输入 `@files` 查看文件解析情况，或换一种目标格式重试。\n\n> 没有伪造结果，也没有把文件发往云端。',
        source: 'fallback', steps, isError: true,
      };
    }
  }

  // ① 本地文档意图：优先本机模板，绝不调用云端模型
  const intent = detectDocIntent(userText);
  if (intent) {
    try {
      return await executeLocalDoc(intent, userText, onPlan, saveTo);
    } catch (e) {
      return {
        text: '### 本地生成失败（已明确降级）\n\n原因：`' + String(e.message || e).slice(0, 200) +
          '`\n\n可稍后重试，或输入 `@office` 打开本地办公面板手动选择模板与格式。\n\n> 本次没有伪造文档，也没有把内容发往云端。',
        source: 'fallback', steps, isError: true,
      };
    }
  }

  // 开放式问答：注入「本机执行器协议」，让模型只派活、不亲自写长文
  let payloadMessages = buildMessages(messages, 16000,
    taskProtocolPrompt(manifest, attachments, saveTo));
  if (attachments.length && attachContext) {
    const briefs = [];
    for (const f of attachments.slice(0, 6)) {
      try {
        const d = await api.fileRead(f.id, 1500);
        briefs.push('【本地文件 ' + f.name + '｜' + f.ext + '】\n' + String(d.text || '').slice(0, 1500) +
          ((d.warnings || []).length ? '\n（' + d.warnings[0] + '）' : ''));
      } catch (e) {
        briefs.push('【本地文件 ' + f.name + '】解析失败：' + (e.message || e));
      }
    }
    payloadMessages.splice(1, 0, { role: 'system', content:
      '【本轮上传的本地文件（仅前 1500 字摘要，完整解析仍在本机）】\n\n' + briefs.join('\n\n') +
      '\n\n文件 ID：' + attachments.map(f => f.id + ' = ' + f.name).join('；') +
      '\n需要完整内容时请下发本机任务指令（file.read / doc.convert），不要臆测文件内容。' });
  }

  // ② 显式联网意图：@web 或用户开启联网且文本含检索词
  const wantWeb = /^@web\s+/i.test(userText.trim()) ||
    (allowNetwork && /(搜索|查一下|查查|最新|今天|新闻|资料)/.test(userText) && userText.length < 120);
  if (wantWeb && !/^@\w+/.test(userText.trim())) {
    const q = userText.replace(/^(请|帮我)?(搜索|查一下|查查|找一下)/, '').trim();
    try {
      const d = await api.websearch(q);
      const results = (d.results || []).slice(0, 5);
      if (results.length) {
        const ctx = '【联网检索结果，由用户显式触发】\n' + results.map((r, i) =>
          (i + 1) + '. ' + (r.title || '') + ' — ' + (r.snippet || '') + (r.url ? ' (' + r.url + ')' : '')).join('\n');
        payloadMessages.splice(1, 0, { role: 'system', content: ctx });
        steps.push({ tool: 'websearch', query: q, count: results.length });
      }
    } catch (e) { steps.push({ tool: 'websearch', error: String(e.message || e) }); }
  }

  // ③ 开放式问答才走模型
  try {
    const text = await streamChat({ messages: payloadMessages, provider, model }, onDelta, signal);
    return { text, source: 'cloud', steps };
  } catch (e) {
    const reason = (e.name === 'AbortError') ? '已中止' : (e.message || String(e));
    if (e.name === 'AbortError') return { text: '', source: 'aborted', steps };
    const fallback = '### 模型调用失败（已明确降级）\n\n' +
      '原因：`' + String(reason).slice(0, 200) + '`\n\n' +
      '可尝试：\n\n1. 打开设置 → 模型，点「测试连接」确认端点与密钥；\n' +
      '2. 本机代理偶发 502，稍等片刻重试（后端已自动在代理/直连间切换）；\n' +
      '3. 换一个 Provider，或选 Ollama 完全离线运行。\n\n' +
      '> 写方案、写大纲、导出办公文件不依赖模型，输入 `@office` 或 `@help` 即可离线使用。';
    return { text: fallback, source: 'fallback', steps, error: reason };
  }
}
