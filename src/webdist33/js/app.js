/* Super-Agient v3.3 — 根组件 / 启动入口 */
import { h, useState, useEffect, useRef, useCallback, uid, cls, copyText, api, Icon, APP } from './core.js';
import { runAgent, runLocalCommand, scanTaskBlocks, cleanTaskText } from './agent.js';
import {
  Sidebar, TopBar, Welcome, MessageItem, Composer, ModelMenu,
  ConfirmDialog, Toasts, IconButton,
} from './components.js';
import { Settings } from './settings.js';
import { OfficePanel, ExportMenu } from './office.js';
import {
  AttachmentBar, FilesPanel, TaskCard, SaveToField, uploadFileList,
} from './files.js';
import { AgentPanel } from './agentpanel.js';
import { ContextBar, CONTEXT_BUDGET } from './context.js';

const R = window.React;
const REACT_DOM = window.ReactDOM;

export function App() {
  const [config, setConfig] = useState(null);
  const [providers, setProviders] = useState([]);
  const [health, setHealth] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [activeId, setActiveId] = useState('');
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [query, setQuery] = useState('');
  const [busy, setBusy] = useState(false);
  const [theme, setTheme] = useState('light');
  const [sidebarClosed, setSidebarClosed] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [modelMenu, setModelMenu] = useState(false);
  const [officeOpen, setOfficeOpen] = useState(false);
  const [exportMsg, setExportMsg] = useState(null);
  const [allowNetwork, setAllowNetwork] = useState(false);
  const [toasts, setToasts] = useState([]);
  const [confirm, setConfirm] = useState(null);
  const [loadError, setLoadError] = useState('');
  /* v3.3：本地附件、文件库、技能清单、保存位置、任务指令结果 */
  const [attachments, setAttachments] = useState([]);
  const [filesOpen, setFilesOpen] = useState(false);
  const [manifest, setManifest] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [saveTo, setSaveTo] = useState(() => localStorage.getItem('asa.v3.saveTo') || '');
  const [attachContext, setAttachContext] = useState(() => localStorage.getItem('asa.v3.attachContext') !== '0');
  const [convertReq, setConvertReq] = useState(null);
  /* v3.3：内置 Agent 框架面板 + 上下文窗口压缩状态 */
  const [agentOpen, setAgentOpen] = useState(false);
  const [hasCompressed, setHasCompressed] = useState(false);
  const abortRef = useRef(null);
  const streamRef = useRef('');
  const msgEndRef = useRef(null);
  const saveTimer = useRef(null);

  const toast = useCallback((text, err) => {
    const id = uid();
    setToasts(t => [...t, { id, text, err: !!err }]);
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 2900);
  }, []);

  const refreshSessions = useCallback(async () => {
    try { const d = await api.sessions(); setSessions(d.sessions || []); } catch (_) {}
  }, []);

  const refreshAll = useCallback(async () => {
    try {
      const [c, p, hd, s, mf] = await Promise.all([
        api.config(), api.providers(), api.health(), api.sessions(),
        api.skills3().catch(() => null),
      ]);
      setConfig(c); setProviders(p.providers || []); setHealth(hd); setSessions(s.sessions || []);
      if (mf) setManifest(mf);
      const t = (c.v3 && c.v3.theme) || localStorage.getItem('asa.v3.theme') || 'light';
      setTheme(t);
      document.documentElement.setAttribute('data-theme', t);
      setLoadError('');
      return { c, s };
    } catch (e) {
      setLoadError('无法读取本地服务：' + (e.message || e));
      return null;
    }
  }, []);

  useEffect(() => { refreshAll(); }, [refreshAll]);
  useEffect(() => {
    const t = setInterval(() => { api.health().then(setHealth).catch(() => {}); }, 60000);
    return () => clearInterval(t);
  }, []);
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') { setSettingsOpen(false); setModelMenu(false); setConfirm(null); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);
  useEffect(() => {
    if (msgEndRef.current) msgEndRef.current.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages]);

  // 会话自动持久化（防抖；空会话不落盘）
  useEffect(() => {
    if (!activeId || !messages.length) return;
    clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(async () => {
      try { await api.saveSession({ id: activeId, messages: messages.map(m => ({
        id: m.id, role: m.role, content: m.content, at: m.at,
        local: !!m.local, source: m.source || '',
        plan: m.plan || null, file: m.file || null, localStats: m.localStats || null,
        taskResult: m.taskResult || null,
        agentResult: m.agentResult || null,
      })) }); refreshSessions(); } catch (_) {}
    }, 550);
    return () => clearTimeout(saveTimer.current);
  }, [messages, activeId, refreshSessions]);

  const v3 = (config && config.v3) || {};
  const cfg = (config && config.cfg) || {};
  const activeProvider = v3.activeProvider || 'spark-maas';
  const currentProvider = providers.find(p => p.id === activeProvider) || {};
  const currentTitle = (sessions.find(s => s.id === activeId) || {}).title || '新对话';

  const setThemePersist = async (t) => {
    setTheme(t);
    document.documentElement.setAttribute('data-theme', t);
    localStorage.setItem('asa.v3.theme', t);
    setConfig(c => c ? { ...c, v3: { ...(c.v3 || {}), theme: t } } : c);
    try { await api.saveConfig({ v3: { theme: t } }); } catch (_) {}
  };

  const setSaveToPersist = (v) => {
    setSaveTo(v);
    localStorage.setItem('asa.v3.saveTo', v || '');
  };

  const doUpload = async (fileList) => {
    if (uploading) return;
    setUploading(true);
    try {
      const out = await uploadFileList(fileList, (m) => toast(m));
      if (out.files.length) {
        setAttachments(a => {
          const ids = new Set(a.map(x => x.id));
          return [...a, ...out.files.filter(f => !ids.has(f.id))];
        });
        toast('已上传 ' + out.files.length + ' 个文件（仅存本机）');
      }
      (out.errors || []).forEach(e => toast(e, true));
    } catch (e) { toast('上传失败：' + (e.message || e), true); }
    finally { setUploading(false); }
  };
  const removeAttach = (id) => setAttachments(a => a.filter(x => x.id !== id));

  const newSession = () => { setActiveId(''); setMessages([]); setInput(''); setQuery(''); setAttachments([]); };
  const selectSession = async (id) => {
    if (busy) { toast('请等待当前生成结束'); return; }
    try {
      const d = await api.session(id);
      setActiveId(id); setMessages((d && d.messages) || []);
    } catch (e) { toast('读取会话失败：' + e.message, true); }
  };
  const deleteSession = (id) => {
    const s = sessions.find(x => x.id === id);
    setConfirm({
      title: '删除这个对话？',
      message: '「' + (s ? s.title : id) + '」将从本机删除，不可恢复。',
      confirmText: '删除',
      action: async () => {
        try {
          await api.delSession(id);
          if (id === activeId) newSession();
          refreshSessions(); toast('已删除');
        } catch (e) { toast('删除失败：' + e.message, true); }
      },
    });
  };
  const clearSessions = async () => {
    for (const s of sessions) { try { await api.delSession(s.id); } catch (_) {} }
    newSession(); refreshSessions(); toast('已清空全部会话');
  };

  const saveConfig = async (draft) => {
    const res = await api.saveConfig(draft);
    setConfig(res.config || draft);
    const [p, hd] = await Promise.all([api.providers(), api.health()]);
    setProviders(p.providers || []); setHealth(hd);
    return res;
  };
  const pickProvider = async (id) => {
    try {
      await api.saveConfig({ v3: { activeProvider: id } });
      setConfig(c => c ? { ...c, v3: { ...(c.v3 || {}), activeProvider: id } } : c);
      const p = await api.providers(); setProviders(p.providers || []);
      toast('已切换到 ' + ((p.providers || []).find(x => x.id === id) || {}).label);
    } catch (e) { toast('切换失败：' + e.message, true); }
  };

  /* 本地上下文窗口压缩：旧消息合成摘要，保留最近 6 条，零 token */
  const compactContext = async () => {
    if (busy || uploading) return;
    if (messages.length < 5) { toast('当前上下文还很短，无需压缩'); return; }
    try {
      const r = await api.agentCompact(messages, CONTEXT_BUDGET, 6);
      if (!r.compacted) { toast('仍在预算内，无需压缩'); return; }
      setMessages(r.messages || messages);
      setHasCompressed(true);
      toast('已本地压缩 ' + r.removed + ' 条旧消息 · 省下 ' +
        Math.max(0, r.beforeChars - r.afterChars) + ' 字（零 token）');
    } catch (e) { toast('压缩失败：' + (e.message || e), true); }
  };

  const generate = async (conversation, sid) => {
    setBusy(true);
    const aiId = uid();
    streamRef.current = '';
    setMessages(m => [...m, { id: aiId, role: 'assistant', content: '', at: Date.now(), streaming: true }]);
    const patchLast = (patch) => setMessages(m => m.map(x => x.id === aiId ? { ...x, ...patch } : x));
    const lastUser = [...conversation].reverse().find(m => m.role === 'user') || {};
    const lastAssistant = [...conversation].reverse()
      .find(m => m.role === 'assistant' && String(m.content || '').trim()) || {};
    const local = await runLocalCommand(lastUser.content, {
      sessions, modelLabel: currentProvider.label || activeProvider,
      baseUrl: currentProvider.baseUrl, model: currentProvider.model,
      lastAssistant: lastAssistant.content || '', format: 'docx',
      attachments, saveTo, manifest,
    });

    if (local.handled) {
      if (local.action === 'clear') {
        setMessages([]); setActiveId(''); setBusy(false); toast('已清空当前会话');
        return;
      }
      if (local.action === 'settings') setSettingsOpen(true);
      if (local.action === 'office') {
        setOfficeOpen(true);
        local.text = '已打开**本地智能办公**面板：选模板 → 填主题与参数 → 选格式导出。\n\n' +
          '写方案、写大纲、生成 Word / HTML / PDF / Excel / PPT 全部在本机完成，' +
          '**云端调用 0 次 · token 0 · 联网 0**。';
      }
      if (local.action === 'files') setFilesOpen(true);
      if (local.action === 'agentPanel') {
        setAgentOpen(true);
        local.text = '已打开**内置 Agent 框架**面板：6 种编排框架、' +
          (manifest && manifest.skills ? manifest.skills.length : 22) +
          ' 个本机工具、本机长期记忆与执行轨迹。\n\n' +
          '全部在本机执行，**云端调用 0 次 · token 0 · 联网 0**。';
      }
      if (local.action === 'agent' && local.goal) {
        try {
          const args = { format: 'docx' };
          if (saveTo) args.saveTo = saveTo;
          if (attachments.length) {
            args.fileId = attachments[0].id;
            args.fileIds = attachments.map(a => a.id);
          }
          const ar = await api.agentRun(local.goal, 'react', args);
          local.text = ar.summary;
          local.agentResult = ar;
          local.localStats = { modelCalls: 0, tokens: 0, networkCalls: 0, ms: ar.ms };
          toast('Agent 执行 ' + ar.steps + ' 步 · 成功 ' + ar.succeeded + ' 条（零 token）', !ar.ok);
        } catch (e) {
          local.text = 'Agent 执行失败：' + (e.message || e);
          local.isError = true;
        }
      }
      if (local.action === 'saveTo') {
        setSaveToPersist(local.saveTo || '');
        toast(local.saveTo ? '已设置默认保存位置' : '已恢复默认输出目录');
      }
      if (local.action === 'tasks' && local.taskText) {
        try {
          const defs = {};
          if (saveTo) defs.saveTo = saveTo;
          if (attachments.length) defs.fileId = attachments[0].id;
          const tr = await api.tasksExecute({ text: local.taskText, defaults: defs });
          local.text = tr.summary;
          local.taskResult = tr;
          local.localStats = { modelCalls: 0, tokens: 0, networkCalls: 0, ms: tr.ms };
          toast('已执行 ' + tr.tasks + ' 条本机任务（零 token）', tr.failed > 0);
        } catch (e) {
          local.text = '任务执行失败：' + (e.message || e);
          local.isError = true;
        }
      }
      if (local.action === 'export') {
        if (!local.lastAssistant) {
          toast('没有可导出的上一条回复，请先生成内容', true);
          local.text = '没有找到可导出的上一条回复。可以先写一份方案，或输入 `@office` 从模板生成。';
          local.isError = true;
        } else {
          setExportMsg({ text: local.lastAssistant, title: '对话导出', format: local.format || 'docx' });
          local.text = '已打开**导出窗口**：可把上一条回复保存为 Word / HTML / PDF / Excel / PPT / Markdown，全部本地渲染，不消耗 token。';
        }
      }
      patchLast({ content: local.text || '（已执行）', streaming: false, local: true,
                  isError: !!local.isError, source: 'local',
                  taskResult: local.taskResult || null, localStats: local.localStats || null,
                  agentResult: local.agentResult || null });
      setBusy(false);
      return;
    }

    const ctrl = new AbortController();
    abortRef.current = ctrl;
    try {
      const res = await runAgent({
        messages: conversation,
        provider: activeProvider,
        model: currentProvider.model,
        allowNetwork,
        maxSteps: v3.maxSteps || 6,
        signal: ctrl.signal,
        attachments, saveTo, manifest, attachContext,
        onPlan: (p) => patchLast({ plan: p }),
        onDelta: (_, full) => { streamRef.current = full; patchLast({ content: full }); },
      });
      if (res.source === 'aborted') {
        patchLast({ content: (streamRef.current || '') + '\n\n*（已中止生成）*', streaming: false, source: 'aborted' });
      } else {
        let finalText = res.text;
        let taskResult = res.taskResult || null;
        let localStats = res.localStats || null;
        // 模型只输出指令块，重活交回本机执行器（混合省 token 模式）
        if (res.source === 'cloud' && scanTaskBlocks(res.text)) {
          try {
            const defs = {};
            if (saveTo) defs.saveTo = saveTo;
            if (attachments.length) defs.fileId = attachments[0].id;
            const tr = await api.tasksExecute({ text: res.text, defaults: defs });
            taskResult = tr;
            finalText = cleanTaskText(res.text) + '\n\n' + tr.summary;
            localStats = { modelCalls: 0, tokens: 0, networkCalls: 0, ms: tr.ms };
            toast('模型下发 ' + tr.tasks + ' 条指令 → 已在本机执行', tr.failed > 0);
          } catch (e) { toast('任务指令执行失败：' + (e.message || e), true); }
        }
        patchLast({
          content: finalText, streaming: false, source: res.source,
          isError: res.source === 'fallback',
          local: res.source === 'local',
          plan: res.steps || null, file: res.file || null,
          taskResult, localStats,
        });
        if (res.source === 'local') toast('已本地生成（零 token · 零联网）');
        if (res.source === 'fallback') toast('模型调用失败，已明确降级', true);
      }
    } catch (e) {
      patchLast({ content: '生成失败：' + (e.message || e), streaming: false, isError: true, source: 'error' });
      toast('生成失败', true);
    } finally {
      setBusy(false); abortRef.current = null;
      // 会话 id 在首条消息时确定
      if (sid) setActiveId(sid);
    }
  };

  const send = async (overrideText) => {
    const text = (typeof overrideText === 'string' ? overrideText : input).trim();
    if (!text || busy) return;
    const sid = activeId || uid();
    const userMsg = { id: uid(), role: 'user', content: text, at: Date.now() };
    const conversation = [...messages, userMsg];
    setMessages(conversation);
    setActiveId(sid);
    setInput('');
    await generate(conversation, sid);
  };

  const retry = (msgId) => {
    if (busy) return;
    const idx = messages.findIndex(m => m.id === msgId);
    if (idx < 0) return;
    const conversation = messages.slice(0, idx);
    setMessages(conversation);
    const sid = activeId || uid();
    generate(conversation, sid);
  };
  const editUser = (text) => {
    if (busy) return;
    const idx = messages.map(m => m.content).lastIndexOf(text);
    if (idx >= 0) setMessages(messages.slice(0, idx));
    setInput(text);
  };
  const copy = async (text) => {
    const ok = await copyText(text);
    toast(ok ? '已复制' : '复制失败', !ok);
  };
  const stop = () => { if (abortRef.current) { abortRef.current.abort(); toast('正在停止…'); } };

  if (loadError) {
    return h('div', { style: { padding: 40, fontFamily: 'var(--font-sans)', color: 'var(--text)' } },
      h('h2', null, '启动失败'),
      h('p', null, loadError),
      h('p', null, '请确认是通过 Super-Agient_v3.3.0.exe 启动的本地窗口，而不是直接打开 HTML 文件。'),
      h('button', { className: 'btn', onClick: refreshAll }, '重试'));
  }
  if (!config) {
    return h('div', { style: { padding: 40, color: 'var(--text-soft)' } }, '正在加载本地服务…');
  }

  return h('div', { className: cls('app', sidebarClosed && 'sidebar-closed') },
    h(Sidebar, {
      sessions, activeId, onNew: newSession, onSelect: selectSession, onDelete: deleteSession,
      onSettings: () => setSettingsOpen(true), health, theme,
      onTheme: () => setThemePersist(theme === 'dark' ? 'light' : 'dark'),
      onClose: () => setSidebarClosed(true), query, onQuery: setQuery,
    }),
    h('main', { className: 'main' },
      h(TopBar, {
        title: currentTitle, providerLabel: currentProvider.label || activeProvider,
        model: currentProvider.model, onModel: () => setModelMenu(true),
        onSettings: () => setSettingsOpen(true), onOffice: () => setOfficeOpen(true),
        onMenu: () => setSidebarClosed(false), sidebarClosed, busy,
      }),
      h(ContextBar, {
        messages, onCompact: compactContext,
        onOpenAgent: () => setAgentOpen(true),
        busy: busy || uploading, hasCompressed,
      }),
      h('div', { className: 'messages' },
        messages.length === 0
          ? h(Welcome, { onPick: (p) => send(p), onSettings: () => setSettingsOpen(true),
                         hasKey: !!(health && health.hasApiKey) })
          : h('div', { className: 'msg-inner' },
              messages.map(m => h(MessageItem, {
                key: m.id, m, streaming: !!m.streaming,
                onCopy: copy, onRetry: retry, onEdit: editUser, onToast: toast,
                onExport: (msg) => setExportMsg({
                  text: (msg.file && msg.file.markdown) || msg.content || '',
                  title: (msg.file && msg.file.title) || '对话导出',
                }),
              })),
              h('div', { ref: msgEndRef, style: { height: 1 } })),
      ),
      h('div', { className: 'composer-zone' },
        h(AttachmentBar, {
          files: attachments, onUpload: doUpload, onRemove: removeAttach,
          onOpenFiles: () => setFilesOpen(true), busy: busy || uploading,
          contextOn: attachContext,
          onToggleContext: (v) => {
            setAttachContext(v);
            localStorage.setItem('asa.v3.attachContext', v ? '1' : '0');
          },
        }),
        h(SaveToField, { value: saveTo, onChange: setSaveToPersist, compact: true })),
      h(Composer, {
        value: input, onChange: setInput, onSend: send, onStop: stop, busy: busy || uploading,
        allowNetwork, onNetwork: () => setAllowNetwork(v => !v),
        hint: uploading ? '正在上传本地文件…' :
          (allowNetwork ? '本轮允许联网检索（用户显式开启）' : undefined),
      })),
    modelMenu && h(ModelMenu, {
      providers, active: activeProvider, onPick: pickProvider,
      onClose: () => setModelMenu(false), onSettings: () => setSettingsOpen(true),
    }),
    settingsOpen && h(Settings, {
      config, providers, health, theme, onTheme: setThemePersist,
      onClose: () => setSettingsOpen(false), onSave: saveConfig,
      onToast: toast, onClearSessions: clearSessions,
    }),
    officeOpen && h(OfficePanel, {
      onClose: () => { setOfficeOpen(false); setConvertReq(null); }, onToast: toast,
      onInsert: (md) => { setInput(String(md || '').slice(0, 1500)); toast('已插入到输入框'); },
      saveTo, onSaveTo: setSaveToPersist, attachments, convertReq,
    }),
    filesOpen && h(FilesPanel, {
      onClose: () => setFilesOpen(false), onToast: toast,
      onAttach: (f) => setAttachments(a => a.some(x => x.id === f.id) ? a : [...a, f]),
      onConvert: (p) => { setFilesOpen(false); setConvertReq(p); setOfficeOpen(true); },
    }),
    agentOpen && h(AgentPanel, {
      onClose: () => setAgentOpen(false), onToast: toast,
      onInsert: (md) => { setInput(String(md || '').slice(0, 1500)); toast('已插入到输入框'); },
      saveTo, onSaveTo: setSaveToPersist, attachments,
    }),
    exportMsg && h(ExportMenu, {
      text: exportMsg.text, title: exportMsg.title,
      initialFormat: exportMsg.format || 'docx', saveTo,
      onClose: () => setExportMsg(null), onToast: toast,
    }),
    confirm && h(ConfirmDialog, {
      title: confirm.title, message: confirm.message, confirmText: confirm.confirmText,
      onCancel: () => setConfirm(null),
      onConfirm: async () => { const fn = confirm.action; setConfirm(null); if (fn) await fn(); },
    }),
    h(Toasts, { items: toasts }));
}

const rootEl = document.getElementById('root');
if (REACT_DOM && REACT_DOM.createRoot) REACT_DOM.createRoot(rootEl).render(h(App));
else if (REACT_DOM) REACT_DOM.render(h(App), rootEl);
else rootEl.textContent = 'React 运行时未加载';
