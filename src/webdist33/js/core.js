/* Super-Agient v3.3 — 核心库
   React UMD + 零构建 ES Module。所有 Markdown 先转义再解析，杜绝模型输出注入。 */
const R = window.React;
export const h = R.createElement;
export const { useState, useEffect, useRef, useCallback, useMemo } = R;

export const APP = { name: 'Super-Agient', version: '3.3.0', developer: 'yang' };
export const LOCAL_BADGE = '云端调用 0 次 · token 0 · 联网 0';

/* ── 通用工具 ─────────────────────────────────────────── */
export const uid = () => 's' + Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
export const cls = (...a) => a.filter(Boolean).join(' ');
export const esc = (s) => String(s == null ? '' : s)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
export const fmtTime = (t) => {
  if (!t) return '';
  const d = new Date(t);
  if (isNaN(d.getTime())) return '';
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
};
export async function copyText(text) {
  try { await navigator.clipboard.writeText(text); return true; }
  catch (_) {
    try {
      const ta = document.createElement('textarea');
      ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
      document.body.appendChild(ta); ta.select(); document.execCommand('copy'); ta.remove();
      return true;
    } catch (e) { return false; }
  }
}

/* ── API 客户端 ───────────────────────────────────────── */
async function request(path, opts = {}) {
  const { method = 'GET', body, signal, timeout = 30000 } = opts;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeout);
  if (signal) signal.addEventListener('abort', () => ctrl.abort(), { once: true });
  try {
    const res = await fetch(path, {
      method, signal: ctrl.signal,
      headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const text = await res.text();
    let data;
    try { data = JSON.parse(text); } catch (_) { data = text; }
    if (!res.ok) {
      const msg = (data && (data.error || data.message)) || (typeof data === 'string' ? data.slice(0, 220) : '') || ('HTTP ' + res.status);
      const err = new Error(String(msg).slice(0, 260));
      err.status = res.status; throw err;
    }
    return data;
  } finally { clearTimeout(timer); }
}
export const api = {
  get: (p, o) => request(p, o),
  post: (p, body, o = {}) => request(p, { ...o, method: 'POST', body }),
  health: () => request('/api/v3/health'),
  config: () => request('/api/v3/config'),
  saveConfig: (c) => request('/api/v3/config', { method: 'POST', body: c }),
  providers: () => request('/api/v3/providers'),
  probe: (id) => request('/api/v3/probe?id=' + encodeURIComponent(id), { timeout: 45000 }),
  sessions: () => request('/api/v3/sessions'),
  session: (id) => request('/api/v3/sessions?id=' + encodeURIComponent(id)),
  saveSession: (s) => request('/api/v3/sessions', { method: 'POST', body: s }),
  delSession: (id) => request('/api/v3/sessions/delete', { method: 'POST', body: { id } }),
  audit: () => request('/api/v3/audit'),
  snapshots: () => request('/api/v3/snapshots'),
  restore: (id) => request('/api/v3/snapshots/restore', { method: 'POST', body: { id } }),
  diagnostics: () => request('/api/v3/diagnostics'),
  websearch: (q) => request('/api/websearch?q=' + encodeURIComponent(q)),
  skills: () => request('/api/skills'),
  /* v3.1 本地办公技能：以下请求全部只到本机后端，不经过云端模型 */
  skills3: () => request('/api/v3/skills'),
  skillsRun: (skill, params) => request('/api/v3/skills/run',
    { method: 'POST', body: { skill, params }, timeout: 180000 }),
  skillsGenerate: (template, prompt, args) => request('/api/v3/skills/generate',
    { method: 'POST', body: { template, prompt, args }, timeout: 60000 }),
  /* v3.3 本地文件枢纽 + 模型任务指令（全部只到本机后端） */
  files: () => request('/api/v3/files'),
  fileRead: (id, maxChars) => request('/api/v3/files/read?id=' + encodeURIComponent(id) +
    (maxChars ? '&maxChars=' + maxChars : ''), { timeout: 120000 }),
  fileInfo: (id) => request('/api/v3/files/info?id=' + encodeURIComponent(id)),
  fileUpload: (name, data, mime) => request('/api/v3/files/upload',
    { method: 'POST', body: { name, data, mime }, timeout: 180000 }),
  fileDelete: (id) => request('/api/v3/files/delete',
    { method: 'POST', body: { id }, timeout: 30000 }),
  tasks: () => request('/api/v3/tasks'),
  tasksExecute: (payload) => request('/api/v3/tasks/execute',
    { method: 'POST', body: payload, timeout: 180000 }),
  /* v3.3 内置 Agent 框架：全部只到本机后端，零 token、零联网 */
  agent: () => request('/api/v3/agent'),
  agentDescribe: () => request('/api/v3/agent/describe'),
  agentRun: (goal, framework, params) => request('/api/v3/agent/run',
    { method: 'POST', body: { goal, framework, params }, timeout: 180000 }),
  agentPlan: (goal, params) => request('/api/v3/agent/plan',
    { method: 'POST', body: { goal, params }, timeout: 60000 }),
  agentCompact: (messages, budget, keep) => request('/api/v3/agent/compact',
    { method: 'POST', body: { messages, budget: budget || 16000, keep: keep || 6 }, timeout: 60000 }),
  agentMemory: (action, payload) => request('/api/v3/agent/memory',
    { method: 'POST', body: { action, ...(payload || {}) }, timeout: 30000 }),
  agentMemories: () => request('/api/v3/agent/memory'),
  agentTrace: () => request('/api/v3/agent/trace'),
};

/* 流式对话：返回完整文本；onDelta 增量回调 */
export async function streamChat(payload, onDelta, signal) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 120000);
  if (signal) signal.addEventListener('abort', () => ctrl.abort(), { once: true });
  try {
    const res = await fetch('/api/v3/chat', {
      method: 'POST', signal: ctrl.signal,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...payload, stream: true }),
    });
    if (!res.ok) {
      const t = await res.text();
      let msg = t.slice(0, 240);
      try { const j = JSON.parse(t); msg = j.message || j.error || msg; } catch (_) {}
      const e = new Error(msg); e.status = res.status; throw e;
    }
    const reader = res.body.getReader();
    const dec = new TextDecoder('utf-8');
    let buf = '', full = '', done = false;
    while (!done) {
      const { value, done: end } = await reader.read();
      if (end) break;
      buf += dec.decode(value, { stream: true });
      const parts = buf.split('\n');
      buf = parts.pop() || '';
      for (const line of parts) {
        const s = line.trim();
        if (!s.startsWith('data:')) continue;
        const raw = s.slice(5).trim();
        if (raw === '[DONE]') { done = true; break; }
        try {
          const j = JSON.parse(raw);
          const d = (j.choices && j.choices[0] && j.choices[0].delta) || {};
          const piece = d.content || '';
          if (piece) { full += piece; onDelta && onDelta(piece, full); }
        } catch (_) {}
      }
    }
    if (!full) throw new Error('模型未返回正文（可尝试关闭思维链或更换模型）');
    return full;
  } finally { clearTimeout(timer); }
}

/* ── Markdown（先转义，再解析；代码块独立保护） ─────────── */
function highlight(code) {
  // 先把 HTML 实体换成不含字母数字的控制标记，避免后续正则把 &#39; 里的 39 当数字高亮
  const map = [['&quot;', '\u0004'], ['&#39;', '\u0005'], ['&amp;', '\u0006'], ['&lt;', '\u0007'], ['&gt;', '\u0008']];
  let s = esc(code);
  for (const [e, m] of map) s = s.split(e).join(m);
  s = s.replace(/(\u0004[^\u0004]*\u0004|\u0005[^\u0005]*\u0005)/g, '<span class="tok-s">$1</span>');
  s = s.replace(/\b(\d+(?:\.\d+)?)\b/g, '<span class="tok-n">$1</span>');
  s = s.replace(/\b(const|let|var|function|return|if|else|for|while|import|export|from|async|await|def|None|True|False|null|true|false|new|try|catch|throw)\b/g, '<span class="tok-k">$1</span>');
  for (const [e, m] of map) s = s.split(m).join(e);
  return s;
}
function inline(s) {
  // s 已转义
  const codes = [];
  let out = s.replace(/`([^`]+)`/g, (_, c) => {
    codes.push('<code class="inline">' + c + '</code>');
    return '\u0001' + (codes.length - 1) + '\u0001';
  });
  out = out.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
    (_, t, u) => '<a href="' + u + '" target="_blank" rel="noopener noreferrer">' + t + '</a>');
  out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  out = out.replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>');
  out = out.replace(/\u0001(\d+)\u0001/g, (_, i) => codes[Number(i)]);
  return out;
}
export function renderMarkdown(raw) {
  const text = String(raw || '');
  const blocks = [];
  const withHoles = text.replace(/```([\w-]*)\n([\s\S]*?)```/g, (_, lang, code) => {
    blocks.push({ lang: lang || 'text', code });
    return '\u0002BLOCK' + (blocks.length - 1) + '\u0002';
  });
  const lines = withHoles.split('\n');
  let html = '', i = 0, list = null;
  const closeList = () => { if (list) { html += '</' + list + '>'; list = null; } };
  while (i < lines.length) {
    const line = lines[i];
    const hole = line.match(/^\u0002BLOCK(\d+)\u0002$/);
    if (hole) {
      closeList();
      const b = blocks[Number(hole[1])];
      html += '<div class="code-block">'
        + '<div class="code-head"><span>' + esc(b.lang) + '</span><button data-copy-code>复制</button></div>'
        + '<pre><code>' + highlight(b.code) + '</code></pre></div>';
      i++; continue;
    }
    if (!line.trim()) { closeList(); i++; continue; }
    if (/^\s*(-{3,}|\*{3,})\s*$/.test(line)) { closeList(); html += '<hr>'; i++; continue; }
    const hd = line.match(/^(#{1,3})\s+(.*)$/);
    if (hd) { closeList(); html += '<h' + hd[1].length + '>' + inline(esc(hd[2])) + '</h' + hd[1].length + '>'; i++; continue; }
    if (/^&gt;\s?/.test(line.trim())) {
      closeList();
      let q = [];
      while (i < lines.length && /^\s*&gt;\s?/.test(lines[i])) { q.push(lines[i].replace(/^\s*&gt;\s?/, '')); i++; }
      html += '<blockquote>' + inline(esc(q.join(' '))) + '</blockquote>'; continue;
    }
    const li = line.match(/^\s*([-*+]|\d+\.)\s+(.*)$/);
    if (li) {
      const tag = /\d/.test(li[1]) ? 'ol' : 'ul';
      if (list !== tag) { closeList(); html += '<' + tag + '>'; list = tag; }
      html += '<li>' + inline(esc(li[2])) + '</li>'; i++; continue;
    }
    if (line.includes('|') && i + 1 < lines.length && /^\s*\|?[\s:|-]+\|/.test(lines[i + 1])) {
      closeList();
      const cells = (s) => s.trim().replace(/^\||\|$/g, '').split('|').map(x => x.trim());
      const head = cells(line); i += 2;
      let t = '<table><thead><tr>' + head.map(x => '<th>' + inline(esc(x)) + '</th>').join('') + '</tr></thead><tbody>';
      while (i < lines.length && lines[i].includes('|') && lines[i].trim()) {
        t += '<tr>' + cells(lines[i]).map(x => '<td>' + inline(esc(x)) + '</td>').join('') + '</tr>'; i++;
      }
      html += t + '</tbody></table>'; continue;
    }
    closeList();
    let para = [line]; i++;
    while (i < lines.length && lines[i].trim() && !/^(#{1,3}\s|&gt;|\s*([-*+]|\d+\.)\s|\u0002BLOCK|\s*(-{3,}|\*{3,})\s*$)/.test(lines[i])) {
      para.push(lines[i]); i++;
    }
    html += '<p>' + inline(esc(para.join('\n'))).replace(/\n/g, '<br>') + '</p>';
  }
  closeList();
  return html;
}

/* ── 图标（内联 SVG，无外部依赖） ─────────────────────── */
const PATHS = {
  plus: 'M12 5v14M5 12h14',
  search: 'M21 21l-4.3-4.3M11 19a8 8 0 100-16 8 8 0 000 16z',
  settings: 'M12 15.5a3.5 3.5 0 100-7 3.5 3.5 0 000 7z|M19.4 15a1.7 1.7 0 00.3 1.9l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.7 1.7 0 00-1.9-.3 1.7 1.7 0 00-1 1.6v.2a2 2 0 11-4 0v-.1a1.7 1.7 0 00-1.1-1.6 1.7 1.7 0 00-1.9.3l-.1.1a2 2 0 11-2.8-2.8l.1-.1a1.7 1.7 0 00.3-1.9 1.7 1.7 0 00-1.6-1H2a2 2 0 110-4h.1a1.7 1.7 0 001.6-1.1 1.7 1.7 0 00-.3-1.9l-.1-.1a2 2 0 112.8-2.8l.1.1a1.7 1.7 0 001.9.3H9a1.7 1.7 0 001-1.6V2a2 2 0 114 0v.1a1.7 1.7 0 001 1.6 1.7 1.7 0 001.9-.3l.1-.1a2 2 0 112.8 2.8l-.1.1a1.7 1.7 0 00-.3 1.9V9a1.7 1.7 0 001.6 1h.2a2 2 0 110 4h-.1a1.7 1.7 0 00-1.6 1z',
  sun: 'M12 17a5 5 0 100-10 5 5 0 000 10z|M12 1v2M12 21v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M1 12h2M21 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4',
  moon: 'M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z',
  send: 'M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z',
  stop: 'M6 6h12v12H6z',
  copy: 'M20 9h-9a2 2 0 00-2 2v9a2 2 0 002 2h9a2 2 0 002-2v-9a2 2 0 00-2-2z|M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1',
  check: 'M20 6L9 17l-5-5',
  trash: 'M3 6h18M8 6V4a1 1 0 011-1h6a1 1 0 011 1v2M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6',
  edit: 'M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7|M18.5 2.5a2.1 2.1 0 013 3L12 15l-4 1 1-4 9.5-9.5z',
  refresh: 'M23 4v6h-6|M1 20v-6h6|M20.5 9A9 9 0 006 5.3L1 10|M1 14l5 4.7A9 9 0 0020.5 15',
  close: 'M18 6L6 18M6 6l12 12',
  menu: 'M3 12h18M3 6h18M3 18h18',
  chevron: 'M6 9l6 6 6-6',
  sparkle: 'M12 2l1.9 6.1L20 10l-6.1 1.9L12 18l-1.9-6.1L4 10l6.1-1.9L12 2z',
  user: 'M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2|M12 11a4 4 0 100-8 4 4 0 000 8z',
  globe: 'M12 22a10 10 0 100-20 10 10 0 000 20z|M2 12h20|M12 2a15 15 0 010 20 15 15 0 010-20z',
  shield: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z',
  database: 'M12 8c4.4 0 8-1.3 8-3s-3.6-3-8-3-8 1.3-8 3 3.6 3 8 3z|M20 5v14c0 1.7-3.6 3-8 3s-8-1.3-8-3V5|M20 12c0 1.7-3.6 3-8 3s-8-1.3-8-3',
  cpu: 'M4 4h16v16H4z|M9 9h6v6H9z|M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 14h3M1 9h3M1 14h3',
  activity: 'M22 12h-4l-3 9L9 3l-3 9H2',
  info: 'M12 22a10 10 0 100-20 10 10 0 000 20z|M12 16v-4M12 8h.01',
  file: 'M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z|M14 2v6h6',
  clock: 'M12 22a10 10 0 100-20 10 10 0 000 20z|M12 6v6l4 2',
  message: 'M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z',
  key: 'M21 2l-2 2m-7.6 7.6a5 5 0 11-7 7 5 5 0 017-7zm0 0L15.5 21|M19 8l3-3',
  alert: 'M12 9v4M12 17h.01|M10.3 3.9L1.8 18a2 2 0 001.7 3h17a2 2 0 001.7-3L14.7 3.9a2 2 0 00-3.4 0z',
  wrench: 'M14.7 6.3a4 4 0 105.4 5.4l-9.8 9.8a2 2 0 01-2.8-2.8l9.8-9.8z',
  save: 'M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z|M17 21v-8H7v8M7 3v5h8',
  panel: 'M3 4h18v16H3z|M9 4v16',
  external: 'M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6|M15 3h6v6M10 14L21 3',
  robot: 'M4 8h16v11a2 2 0 01-2 2H6a2 2 0 01-2-2V8z|M12 4v4M9 4h6|M2 12v3M22 12v3|M9.5 17h5',
  doc: 'M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z|M14 2v6h6|M8 13h8M8 17h6',
  bolt: 'M13 2L4 14h7l-1 8 9-12h-7l1-8z',
  download: 'M12 3v12M7 11l5 5 5-5|M4 19h16',
  layers: 'M12 2L2 7l10 5 10-5-10-5z|M2 12l10 5 10-5|M2 17l10 5 10-5',
  offline: 'M2 8a15 15 0 0120 0|M5 12a10 10 0 0114 0|M8.5 16a5 5 0 017 0|M12 20h.01|M3 3l18 18',
};
export function Icon({ name, size = 16, className = '', style }) {
  const d = PATHS[name] || PATHS.info;
  return h('svg', {
    width: size, height: size, viewBox: '0 0 24 24', fill: 'none',
    stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round',
    strokeLinejoin: 'round', className, style, 'aria-hidden': 'true',
  }, d.split('|').map((p, i) => h('path', { key: i, d: p })));
}
/* 机器人品牌标：与 EXE 图标 assets/robot.ico 同一造型，固定配色保证浅/深主题都清晰 */
const ROBOT_BG = '#b4663c', ROBOT_FACE = '#fdfbf7';
export const BrandMark = ({ size = 16 }) => h('svg', {
  width: size, height: size, viewBox: '0 0 24 24', fill: 'none', 'aria-hidden': 'true',
},
  h('rect', { x: 1.5, y: 1.5, width: 21, height: 21, rx: 5.5, fill: ROBOT_BG }),
  h('path', { d: 'M12 2.6v3.1', stroke: ROBOT_FACE, strokeWidth: 1.5, strokeLinecap: 'round' }),
  h('circle', { cx: 12, cy: 2.7, r: 1.05, fill: ROBOT_FACE }),
  h('rect', { x: 3.7, y: 10, width: 1.9, height: 4.2, rx: 0.9, fill: ROBOT_FACE }),
  h('rect', { x: 18.4, y: 10, width: 1.9, height: 4.2, rx: 0.9, fill: ROBOT_FACE }),
  h('rect', { x: 5.4, y: 5.9, width: 13.2, height: 12.1, rx: 3.3, fill: ROBOT_FACE }),
  h('circle', { cx: 9.3, cy: 10.9, r: 1.2, fill: ROBOT_BG }),
  h('circle', { cx: 14.7, cy: 10.9, r: 1.2, fill: ROBOT_BG }),
  h('path', { d: 'M9.4 14.1q2.6 2.1 5.2 0', stroke: ROBOT_BG, strokeWidth: 1.5,
              strokeLinecap: 'round', fill: 'none' }));

export const ROBOT_SVG_DATA = 'data:image/svg+xml,' + encodeURIComponent(
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">' +
  '<rect x="1.5" y="1.5" width="21" height="21" rx="5.5" fill="#b4663c"/>' +
  '<path d="M12 2.6v3.1" stroke="#fdfbf7" stroke-width="1.5" stroke-linecap="round"/>' +
  '<circle cx="12" cy="2.7" r="1.05" fill="#fdfbf7"/>' +
  '<rect x="3.7" y="10" width="1.9" height="4.2" rx=".9" fill="#fdfbf7"/>' +
  '<rect x="18.4" y="10" width="1.9" height="4.2" rx=".9" fill="#fdfbf7"/>' +
  '<rect x="5.4" y="5.9" width="13.2" height="12.1" rx="3.3" fill="#fdfbf7"/>' +
  '<circle cx="9.3" cy="10.9" r="1.2" fill="#b4663c"/>' +
  '<circle cx="14.7" cy="10.9" r="1.2" fill="#b4663c"/>' +
  '<path d="M9.4 14.1q2.6 2.1 5.2 0" stroke="#b4663c" stroke-width="1.5" fill="none" stroke-linecap="round"/>' +
  '</svg>');
