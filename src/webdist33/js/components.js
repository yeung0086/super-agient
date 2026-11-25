/* Super-Agient v3.1 — UI 组件层（React UMD，零构建） */
import { h, useState, useEffect, useRef, cls, fmtTime, copyText, renderMarkdown,
         Icon, BrandMark, api, APP, LOCAL_BADGE } from './core.js';
import { COMMANDS } from './agent.js';

/* ── 本地能力展示（零 token / 零联网 / 执行计划 / 文件） ── */
export function LocalBadge({ stats, compact }) {
  const s = stats || {};
  return h('div', { className: cls('local-badge', compact && 'compact') },
    h(Icon, { name: 'offline', size: 13 }),
    h('span', null, compact ? LOCAL_BADGE :
      '云端调用 ' + (s.modelCalls || 0) + ' 次 · token ' + (s.tokens || 0) +
      ' · 联网 ' + (s.networkCalls || 0) + ' 次' + (s.ms ? ' · ' + s.ms + ' ms' : '')));
}

export function PlanCard({ steps, stats }) {
  if (!steps || !steps.length) return null;
  const done = steps.filter(s => s.status === 'done').length;
  return h('div', { className: 'plan-card' },
    h('div', { className: 'plan-head' },
      h(Icon, { name: 'layers', size: 14 }),
      h('strong', null, '本地执行计划'),
      h('span', { className: 'plan-count' }, done + '/' + steps.length + ' 步完成'),
      stats && h('span', { className: 'plan-ms' }, stats.ms + ' ms')),
    h('div', { className: 'plan-steps' },
      steps.map(s => h('div', { key: s.id, className: cls('plan-step', s.status === 'done' && 'done') },
        h('span', { className: 'plan-dot' }, s.status === 'done' ? '✓' : s.id),
        h('div', { className: 'plan-info' },
          h('div', { className: 'plan-title' }, s.title),
          h('div', { className: 'plan-tool' }, (s.tool || '本地') + (s.note ? ' · ' + s.note : ''))),
        s.ms ? h('span', { className: 'plan-time' }, s.ms + 'ms') : null))));
}

export function FileCard({ file, onToast }) {
  if (!file || file.ok === false) return null;
  const link = file.url || file.downloadUrl || '';
  const dest = file.savedTo || file.path || file.name || '';
  const outside = !!file.savedTo && file.inDefaultDir === false;
  return h('div', { className: 'file-card' },
    h('div', { className: 'file-icon' }, h(Icon, { name: 'doc', size: 20 })),
    h('div', { className: 'file-main' },
      h('div', { className: 'file-name' }, file.name || file.path),
      h('div', { className: 'file-sub' },
        String(file.format || '').toUpperCase() + ' · ' + Math.round((file.size || 0) / 1024) +
        ' KB · ' + (file.chars || 0) + ' 字 · 本地生成'),
      outside && h('div', { className: 'file-path', title: dest }, '📁 ' + dest)),
    h('div', { className: 'file-acts' },
      link && h('a', { className: 'btn primary file-dl', href: link, download: file.name || '' },
        h(Icon, { name: 'download', size: 13 }), ' 下载'),
      h(Btn, { onClick: async () => {
        const ok = await copyText(dest);
        onToast && onToast(ok ? '路径已复制' : '复制失败', !ok);
      } }, '复制路径')));
}

/* 模型下发的任务指令：本机执行轨迹 + 文件回执 */
/* ── v3.3 内置 Agent 框架执行轨迹 ─────────────────────── */
export function AgentTraceCard({ result, onToast }) {
  if (!result || !result.trace) return null;
  const head = h('div', { className: 'at-head' },
    h(Icon, { name: 'robot', size: 14 }),
    h('strong', null, 'Agent · ' + (result.frameworkName || result.framework || '本机')),
    h('span', { className: 'at-count' },
      result.steps + ' 步 · 成功 ' + result.succeeded + ' · 失败 ' + result.failed),
    h('span', { className: 'at-ms' }, result.ms + ' ms'));
  const badge = h('div', { className: 'at-badge' },
    '工具注册表全本机执行 · 云端调用 0 次 · token 0 · 联网 0');
  const steps = h('div', { className: 'at-steps' },
    (result.trace || []).map((s, i) => h('div', {
      key: i, className: cls('at-step', s.ok && 'done', !s.ok && 'bad'),
    },
      h('span', { className: 'at-idx' }, String(s.i || i + 1)),
      h('div', { className: 'at-info' },
        h('div', { className: 'at-line' }, '思考：' + (s.thought || '—')),
        h('div', { className: 'at-line' }, '行动：', h('code', null, s.action || '?'),
          s.retried ? h('span', { className: 'at-retry' }, '重试') : null),
        h('div', { className: 'at-line obs' }, '观察：' + (s.observation || '—'))),
      h('span', { className: 'at-time' }, (s.ms || 0) + 'ms'))));
  const verify = (result.verification && !result.verification.ok)
    ? h('div', { className: 'warn-note' },
        '校验：' + (result.verification.issues || []).join('；'))
    : null;
  const files = (result.files || [])
    .filter(f => f && (f.url || f.downloadUrl || f.path))
    .map((f, i) => h(FileCard, { key: 'af' + i, file: f, onToast }));
  return h('div', { className: 'agent-trace' }, head, badge, steps, verify, files);
}

export function TaskCard({ result, onToast }) {
  if (!result || !result.steps) return null;
  return h('div', { className: 'task-card' },
    h('div', { className: 'task-head' },
      h(Icon, { name: 'layers', size: 14 }),
      h('strong', null, '本机任务执行'),
      h('span', { className: 'task-count' },
        result.tasks + ' 条 · 成功 ' + result.succeeded + ' · 失败 ' + result.failed),
      h('span', { className: 'task-ms' }, result.ms + ' ms')),
    h('div', { className: 'task-badge' },
      '执行阶段：云端调用 0 次 · token 0 · 联网 0（模型只输出了指令）'),
    h('div', { className: 'task-steps' },
      result.steps.map((s, i) => h('div', { key: i, className: cls('task-step', s.ok && 'done') },
        h('span', { className: 'task-dot' }, s.ok ? '✓' : '!'),
        h('div', { className: 'task-info' },
          h('div', { className: 'task-title' }, h('code', null, s.skill), s.note ? ' · ' + s.note : ''),
          h('div', { className: 'task-sub' },
            s.ok ? (s.savedTo || s.path || s.name || '已执行（未落盘）') : (s.error || '失败'))),
        h('span', { className: 'task-time' }, s.ms + 'ms')))),
    (result.parseErrors || []).map((e, i) => h('div', { key: 'e' + i, className: 'warn-note' }, e)),
    (result.files || []).filter(f => f && (f.url || f.downloadUrl || f.path)).map((f, i) =>
      h(FileCard, { key: 'f' + i, file: f, onToast })));
}

export function IconButton({ icon, title, onClick, disabled, danger, className = '', size = 16 }) {
  return h('button', {
    className: cls('icon-btn', danger && 'danger', className), title, onClick, disabled,
    type: 'button',
  }, h(Icon, { name: icon, size }));
}
export function Btn({ children, onClick, variant, disabled, className = '' }) {
  return h('button', {
    type: 'button', onClick, disabled,
    className: cls('btn', variant && variant, className),
  }, children);
}
export function Switch({ label, desc, checked, onChange }) {
  return h('div', { className: 'switch' },
    h('div', null,
      h('div', { className: 'sw-label' }, label),
      desc && h('div', { className: 'sw-desc' }, desc)),
    h('button', {
      type: 'button', className: cls('sw-toggle', checked && 'on'),
      'aria-label': label, 'aria-pressed': !!checked,
      onClick: () => onChange(!checked),
    }));
}

/* ── 侧边栏 ───────────────────────────────────────────── */
export function Sidebar({ sessions, activeId, onNew, onSelect, onDelete, onSettings,
                          health, theme, onTheme, onClose, query, onQuery }) {
  const filtered = (sessions || []).filter(s => !query || (s.title || '').toLowerCase().includes(query.toLowerCase()));
  const ok = !!(health && health.hasApiKey);
  return h('aside', { className: 'sidebar' },
    h('div', { className: 'sb-head' },
      h('div', { className: 'brand' },
        h('div', { className: 'brand-mark' }, h(BrandMark, { size: 16 })),
        h('span', { className: 'brand-name' }, APP.name),
        h('span', { className: 'brand-ver' }, 'v' + APP.version)),
      h(IconButton, { icon: 'panel', title: '收起侧边栏', onClick: onClose })),

    h('div', { className: 'sb-new' },
      h('button', { type: 'button', className: 'btn-new', onClick: onNew },
        h(Icon, { name: 'plus', size: 15 }), '新建对话')),

    h('div', { className: 'sb-search' },
      h('div', { className: 'search-wrap' },
        h(Icon, { name: 'search', size: 14 }),
        h('input', {
          className: 'input', placeholder: '搜索对话', value: query,
          onChange: e => onQuery(e.target.value),
        }))),

    h('div', { className: 'sb-list' },
      h('div', { className: 'sb-group' }, '最近对话'),
      filtered.length ? filtered.map(s => h('div', {
        key: s.id, className: cls('session-item', s.id === activeId && 'active'),
        onClick: () => onSelect(s.id), role: 'button', tabIndex: 0,
      },
        h(Icon, { name: 'message', size: 14 }),
        h('span', { className: 's-title' }, s.title || '新对话'),
        h('button', {
          type: 'button', className: 's-del', title: '删除对话',
          onClick: e => { e.stopPropagation(); onDelete(s.id); },
        }, h(Icon, { name: 'trash', size: 13 }))))
        : h('div', { className: 'sb-empty' }, query ? '没有匹配的对话' : '还没有对话，点上方新建'),
    ),

    h('div', { className: 'sb-foot' },
      h('div', { className: 'status-card' },
        h('div', { className: 'status-row' },
          h('span', { className: cls('status-dot', !ok && 'off') }),
          h('span', null, ok ? '模型已配置' : '尚未配置密钥')),
        h('div', { className: 'status-sub' }, health ? (health.providerLabel || '') + ' · ' + (health.model || '') : '正在读取状态…'),
        h('div', { className: 'status-sub' }, health ? '会话 ' + health.sessions + ' 条 · 审计 ' + ((health.audit && health.audit.total) || 0) + ' 条' : '')),
      h('div', { className: 'sb-user' },
        h('div', { className: 'avatar' }, '本'),
        h('span', { className: 'u-name' }, '本地工作区'),
        h(IconButton, { icon: theme === 'dark' ? 'sun' : 'moon', title: '切换主题', onClick: onTheme, size: 15 }),
        h(IconButton, { icon: 'settings', title: '设置', onClick: onSettings, size: 15 })),
      h('div', { className: 'sb-links' }, '办公本地化 · 零 token · 默认零出域 · @help 查看命令')));
}

/* ── 顶栏 ─────────────────────────────────────────────── */
export function TopBar({ title, providerLabel, model, onModel, onSettings, onOffice, onMenu, sidebarClosed, busy }) {
  return h('header', { className: 'topbar' },
    sidebarClosed && h(IconButton, { icon: 'menu', title: '展开侧边栏', onClick: onMenu }),
    h('h1', null, title || '新对话'),
    h('div', { className: 'top-actions' },
      busy && h('span', { className: 'pill' }, '生成中'),
      h('button', { type: 'button', className: 'office-entry', onClick: onOffice, title: '本地智能办公（零 token）' },
        h(Icon, { name: 'doc', size: 14 }), h('span', null, '本地办公')),
      h('button', { type: 'button', className: 'model-pick', onClick: onModel, title: '切换模型' },
        h(Icon, { name: 'sparkle', size: 14 }),
        h('span', { className: 'mp-label' }, providerLabel || '未选择模型'),
        h(Icon, { name: 'chevron', size: 13 })),
      h(IconButton, { icon: 'settings', title: '设置', onClick: onSettings || onModel, size: 15 })));
}

/* ── 欢迎页 ───────────────────────────────────────────── */
const SUGGESTIONS = [
  { t: '写一份培训方案', d: '本地模板生成 · 零 token · 直接导出 Word', icon: 'doc',
    p: '帮我写一份家政服务技能培训方案，单位=示范中心' },
  { t: '列一个写作大纲', d: '三级层次骨架，不用模型也能成稿', icon: 'layers',
    p: '@大纲 乡村振兴工作总结' },
  { t: '生成 HTML / PDF', d: '把内容变成本地办公文件', icon: 'download', p: '@office' },
  { t: '看看本地能做什么', d: '办公技能清单与全部命令', icon: 'wrench', p: '@help' },
];
export function Welcome({ onPick, onSettings, hasKey }) {
  return h('div', { className: 'welcome' },
    h('div', { className: 'w-mark' }, h(BrandMark, { size: 30 })),
    h('h2', null, '有什么可以帮你？'),
    h('p', { className: 'lead' }, APP.name + ' · 本地智能办公助手' +
      '。写方案、写大纲、导出办公文件都在本机完成，不消耗 token。'),
    h('div', { className: 'welcome-badge' },
      h(Icon, { name: 'offline', size: 14 }), LOCAL_BADGE),
    h('div', { className: 'cards' },
      SUGGESTIONS.map((s, i) => h('button', {
        key: i, type: 'button', className: 'card', onClick: () => onPick(s.p),
      },
        h('div', { className: 'c-title' }, h(Icon, { name: s.icon, size: 14 }), s.t),
        h('div', { className: 'c-desc' }, s.d)))),
    h('div', { className: 'w-tip' },
      !hasKey && h('div', null, '尚未检测到 API Key：本地办公功能仍可正常使用；开放式问答需在设置里填写密钥。'),
      h('div', null, '默认不联网：只有 @web 或点「联网」按钮才会发起检索；模型问答才会消耗 token。'),
      h('div', null, '快捷键：Enter 发送 · Shift+Enter 换行 · Esc 关闭面板')));
}

/* ── 消息 ─────────────────────────────────────────────── */
export function MessageItem({ m, streaming, onCopy, onRetry, onEdit, onToast, onExport }) {
  const isUser = m.role === 'user';
  const onClick = (e) => {
    const btn = e.target.closest && e.target.closest('[data-copy-code]');
    if (btn) {
      const block = btn.closest('.code-block');
      const code = block && block.querySelector('code');
      if (code) copyText(code.textContent).then(ok => onToast(ok ? '代码已复制' : '复制失败', !ok));
    }
  };
  const html = renderMarkdown(m.content || '') + (streaming && !isUser ? '<span class="cursor"></span>' : '');
  return h('div', { className: cls('msg', isUser && 'msg-user') },
    h('div', { className: cls('msg-avatar', isUser ? 'me' : 'ai') },
      h(Icon, { name: isUser ? 'user' : 'robot', size: 15 })),
    h('div', { className: 'msg-body' },
      !isUser && h('div', { className: 'msg-meta' },
        h('span', { className: 'who' }, APP.name),
        m.local && h('span', { className: 'badge-local' }, '本地命令'),
        m.source === 'local' && h('span', { className: 'badge-local' }, '本地生成 · 零 token'),
        m.source === 'fallback' && h('span', { className: 'badge-local' }, '已降级'),
        m.at && h('span', null, fmtTime(m.at))),
      m.localStats && h(LocalBadge, { stats: m.localStats }),
      (streaming && !isUser && !m.content)
        ? h('div', { className: 'dots' }, h('i'), h('i'), h('i'))
        : h('div', {
            className: cls('md', m.isError && 'msg-error'),
            onClick, dangerouslySetInnerHTML: { __html: html },
          }),
      m.plan && h(PlanCard, { steps: m.plan, stats: m.localStats }),
      m.taskResult && h(TaskCard, { result: m.taskResult, onToast }),
      m.agentResult && h(AgentTraceCard, { result: m.agentResult, onToast }),
      m.file && h(FileCard, { file: m.file, onToast }),
      !streaming && h('div', { className: 'msg-actions' },
        h(IconButton, { icon: 'copy', title: '复制', size: 14, onClick: () => onCopy(m.content || '') }),
        !isUser && onExport && h(IconButton, { icon: 'download', title: '导出为 Word / HTML / PDF…',
          size: 14, onClick: () => onExport(m) }),
        !isUser && h(IconButton, { icon: 'refresh', title: '重新生成', size: 14, onClick: () => onRetry(m.id) }),
        isUser && h(IconButton, { icon: 'edit', title: '编辑并重发', size: 14, onClick: () => onEdit(m.content || '') }))));
}

/* ── 输入区 ───────────────────────────────────────────── */
export function Composer({ value, onChange, onSend, onStop, busy, allowNetwork, onNetwork, hint }) {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 180) + 'px';
  }, [value]);
  const keyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault(); if (!busy) onSend();
    }
  };
  return h('div', { className: 'composer-wrap' },
    h('div', { className: 'composer-inner' },
      h('div', { className: 'composer' },
        h('textarea', {
          ref, value, rows: 1, placeholder: '写方案、写大纲、导出 Word… 或输入 @help 查看命令',
          onChange: e => onChange(e.target.value), onKeyDown: keyDown,
        }),
        h('div', { className: 'composer-bar' },
          h('button', {
            type: 'button', className: cls('model-pick', allowNetwork && 'active'),
            title: '允许本轮联网检索（默认关闭）',
            onClick: onNetwork, style: { padding: '4px 8px', borderColor: allowNetwork ? 'var(--accent)' : undefined },
          }, h(Icon, { name: 'globe', size: 13 }), h('span', null, allowNetwork ? '联网开' : '联网关')),
          h('span', { className: 'composer-hint' }, hint || (busy ? '正在生成…' : 'Enter 发送 · Shift+Enter 换行')),
          h('button', {
            type: 'button', className: cls('btn-send', busy && 'btn-stop'),
            title: busy ? '停止生成' : '发送', onClick: busy ? onStop : onSend,
          }, h(Icon, { name: busy ? 'stop' : 'send', size: 15 })))),
      h('div', { className: 'composer-foot' }, APP.name + ' v' + APP.version +
        ' · 本地办公零 token；模型生成内容请自行核实；密钥不明文出现在页面')));
}

/* ── 模型快捷菜单 ─────────────────────────────────────── */
export function ModelMenu({ providers, active, onPick, onClose, onSettings }) {
  return h('div', { className: 'modal-wrap', onClick: onClose },
    h('div', { className: 'modal', style: { width: 'min(480px, 92vw)' }, onClick: e => e.stopPropagation() },
      h('h3', null, '选择模型'),
      h('p', null, '切换后立即生效；密钥统一在设置里管理，切换不会覆盖。'),
      h('div', { style: { maxHeight: 330, overflowY: 'auto', marginBottom: 14 } },
        (providers || []).map(p => h('button', {
          key: p.id, type: 'button',
          className: cls('provider-row', p.id === active && 'active'),
          style: { width: '100%', textAlign: 'left' },
          onClick: () => { onPick(p.id); onClose(); },
        },
          h('div', { className: 'pr-top' },
            h('span', { className: 'pr-name' }, p.label || p.id),
            p.id === active && h('span', { className: 'pill' }, '当前')),
          h('div', { className: 'pr-url' }, (p.model || '未设模型') + ' · ' + (p.baseUrl || ''))))),
      h('div', { className: 'btn-row', style: { justifyContent: 'flex-end' } },
        h(Btn, { onClick: onClose }, '关闭'),
        h(Btn, { variant: 'primary', onClick: () => { onClose(); onSettings(); } }, '模型设置'))));
}

/* ── 确认框 / Toast ───────────────────────────────────── */
export function ConfirmDialog({ title, message, confirmText = '确认', onConfirm, onCancel, danger }) {
  return h('div', { className: 'modal-wrap', onClick: onCancel },
    h('div', { className: 'modal', onClick: e => e.stopPropagation() },
      h('h3', null, title),
      h('p', null, message),
      h('div', { className: 'btn-row' },
        h(Btn, { onClick: onCancel }, '取消'),
        h(Btn, { variant: 'primary', onClick: onConfirm }, confirmText))));
}
export function Toasts({ items }) {
  return h('div', { className: 'toast-stack' },
    (items || []).map(t => h('div', { key: t.id, className: cls('toast', t.err && 'err') }, t.text)));
}
