/* Super-Agient v3.3 — 上下文窗口条（重绘）
   把「当前会话占用多少上下文」变成可见、可操作的一行，与消息 / 输入区共用同一栅格。
   压缩走 /api/v3/agent/compact，纯本地、零 token、零联网。 */
import { h, cls, Icon, APP } from './core.js';

export const CONTEXT_BUDGET = 16000;

export function contextUsage(messages) {
  const list = Array.isArray(messages) ? messages : [];
  let chars = 0;
  for (const m of list) chars += String((m && m.content) || '').length;
  return { chars, count: list.length, pct: Math.min(100, Math.round(chars / CONTEXT_BUDGET * 100)) };
}

export function ContextBar({ messages, onCompact, onOpenAgent, busy, hasCompressed }) {
  const u = contextUsage(messages);
  const level = u.pct >= 85 ? 'high' : (u.pct >= 60 ? 'mid' : 'low');
  if (!u.count) return null;
  return h('div', { className: 'context-rail' },
    h('div', { className: 'context-bar' },
      h('div', { className: 'ctx-label', title: '上下文窗口：发送给模型的会话字符预算' },
        h(Icon, { name: 'layers', size: 13 }),
        h('span', null, '上下文窗口')),
      h('div', { className: 'ctx-track', title: '已用 ' + u.chars + ' / ' + CONTEXT_BUDGET + ' 字符' },
        h('div', { className: 'ctx-fill ' + level, style: { width: Math.max(2, u.pct) + '%' } })),
      h('div', { className: 'ctx-figure' },
        h('span', { className: 'ctx-num' }, u.chars.toLocaleString()),
        h('span', { className: 'ctx-of' }, ' / ' + CONTEXT_BUDGET.toLocaleString()),
        h('span', { className: 'ctx-pct' }, u.pct + '%')),
      h('span', { className: 'ctx-count' }, u.count + ' 条'),
      hasCompressed && h('span', { className: 'ctx-chip' }, '已压缩'),
      h('button', {
        type: 'button', className: cls('ctx-btn', busy && 'disabled'), disabled: !!busy,
        title: '把较早的消息合成一条本地摘要，保留最近 6 条原文（不调用模型）',
        onClick: onCompact,
      }, h(Icon, { name: 'wrench', size: 12 }), '压缩'),
      h('button', {
        type: 'button', className: 'ctx-btn primary', title: '打开内置 Agent 框架面板',
        onClick: onOpenAgent,
      }, h(Icon, { name: 'robot', size: 12 }), 'Agent')));
}
