/* Super-Agient v3.1 — 设置抽屉（5 个页签，全部可操作） */
import { h, useState, useEffect, cls, fmtTime, Icon, api } from './core.js';
import { Btn, IconButton, Switch, ConfirmDialog } from './components.js';
import { COMMANDS } from './agent.js';

const TABS = [
  ['general', '常规', 'settings'],
  ['model', '模型', 'cpu'],
  ['tools', '工具与技能', 'wrench'],
  ['diagnostics', '诊断', 'activity'],
  ['about', '关于', 'info'],
];

export function Settings({ config, providers, health, theme, onTheme, onClose, onSave, onToast, onClearSessions }) {
  const [tab, setTab] = useState('model');
  const [draft, setDraft] = useState(() => JSON.parse(JSON.stringify(config || { cfg: {}, v3: {} })));
  const [keyInput, setKeyInput] = useState('');
  const [probing, setProbing] = useState(false);
  const [probe, setProbe] = useState(null);
  const [diag, setDiag] = useState(null);
  const [skills, setSkills] = useState(null);
  const [mcp, setMcp] = useState({ name: '', transport: 'stdio-bridge', target: '' });
  const [confirm, setConfirm] = useState(null);

  useEffect(() => {
    if (config) setDraft(JSON.parse(JSON.stringify(config)));
  }, [config]);

  useEffect(() => {
    if (tab !== 'diagnostics' && tab !== 'tools') return;
    let alive = true;
    (async () => {
      try {
        const [a, s, d, hh] = await Promise.all([api.audit(), api.snapshots(), api.diagnostics(), api.health()]);
        if (alive) setDiag({ audit: a, snapshots: s, diagnostics: d, health: hh });
      } catch (e) { if (alive) setDiag({ error: String(e.message || e) }); }
      try { const sk = await api.skills(); if (alive) setSkills(sk.skills || []); }
      catch (_) { if (alive) setSkills([]); }
    })();
    return () => { alive = false; };
  }, [tab]);

  const cfg = draft.cfg || {};
  const v3 = draft.v3 || {};
  const active = v3.activeProvider || 'spark-maas';
  const prov = (providers || []).find(p => p.id === active) || {};
  const ov = (v3.overrides && v3.overrides[active]) || {};

  const patchV3 = (k, value) => setDraft(d => ({ ...d, v3: { ...(d.v3 || {}), [k]: value } }));
  const patchCfg = (k, value) => setDraft(d => ({ ...d, cfg: { ...(d.cfg || {}), [k]: value } }));
  const override = (field, value) => setDraft(d => {
    const v = d.v3 || {}, os = v.overrides || {};
    return { ...d, v3: { ...v, overrides: { ...os, [active]: { ...(os[active] || {}), [field]: value } } } };
  });

  const save = async (silent) => {
    const d = JSON.parse(JSON.stringify(draft));
    if (keyInput.trim()) d.cfg.apiKey = keyInput.trim();
    try {
      await onSave(d);
      setKeyInput('');
      if (!silent) onToast('设置已保存');
      return true;
    } catch (e) { onToast('保存失败：' + (e.message || e), true); return false; }
  };

  const test = async () => {
    setProbing(true); setProbe(null);
    const ok = await save(true);
    if (!ok) { setProbing(false); return; }
    try {
      const r = await api.probe(active);
      setProbe(r.result || r);
      onToast(r.result && r.result.ok ? '连接正常' : '连接失败，请看诊断信息', !(r.result && r.result.ok));
    } catch (e) {
      setProbe({ ok: false, detail: String(e.message || e) });
      onToast('测试失败：' + (e.message || e), true);
    } finally { setProbing(false); }
  };

  const addMcp = () => {
    if (!mcp.name.trim() || !mcp.target.trim()) { onToast('请填写名称与目标', true); return; }
    const item = { id: 'mcp-' + Date.now().toString(36), name: mcp.name.trim(), transport: mcp.transport };
    if (mcp.transport === 'stdio-bridge') { item.command = 'python'; item.args = [mcp.target.trim()]; }
    else { item.url = mcp.target.trim(); }
    patchCfg('mcpServers', [...(cfg.mcpServers || []), item]);
    setMcp({ name: '', transport: 'stdio-bridge', target: '' });
    onToast('已加入列表，点「保存设置」生效');
  };

  /* ── 各页签 ─────────────────────────────────────────── */
  const panelGeneral = () => h('div', null,
    h('h3', null, '外观'),
    h('p', { className: 'desc' }, '暖色系双主题，跟随 Claude Desktop 的视觉语言。'),
    h('div', { className: 'btn-row', style: { marginBottom: 18 } },
      h(Btn, { variant: theme === 'light' ? 'primary' : undefined, onClick: () => onTheme('light') }, '浅色'),
      h(Btn, { variant: theme === 'dark' ? 'primary' : undefined, onClick: () => onTheme('dark') }, '深色')),
    h('h3', null, '生成行为'),
    h(Switch, { label: '关闭思维链', desc: '讯飞 Spark X2.5 开启后响应 4~12 秒；关闭后通常 1 秒内返回',
      checked: v3.disableThinking !== false, onChange: x => patchV3('disableThinking', x) }),
    h(Switch, { label: '写文件前自动快照', desc: '覆盖本地文件前留档，可在「诊断」里一键回滚',
      checked: v3.autoSnapshot !== false, onChange: x => patchV3('autoSnapshot', x) }),
    h('div', { className: 'row', style: { marginTop: 16 } },
      h('div', { className: 'field' },
        h('label', null, '上下文上限（字符）'),
        h('input', { className: 'input', type: 'number', min: 4000, max: 120000, value: v3.contextLimit || 16000,
          onChange: e => patchV3('contextLimit', Number(e.target.value) || 16000) }),
        h('div', { className: 'hint' }, '超过阈值自动压缩：保留开头、最近 10 条与主题摘要')),
      h('div', { className: 'field' },
        h('label', null, '工具循环上限'),
        h('input', { className: 'input', type: 'number', min: 1, max: 20, value: v3.maxSteps || 6,
          onChange: e => patchV3('maxSteps', Number(e.target.value) || 6) }),
        h('div', { className: 'hint' }, '单轮任务最多执行多少步工具调用'))),
    h('h3', null, '数据'),
    h('p', { className: 'desc' }, '会话保存在本机 ' + (health && health.storage ? health.storage : 'v3 数据目录') + '，不上传。'),
    h(Btn, { onClick: () => setConfirm({
      title: '清空所有会话？', message: '将删除本机全部会话记录（配置、密钥与审计链保留）。此操作不可撤销。',
      confirmText: '确认清空', action: onClearSessions,
    }) }, '清空所有会话'),
    h('div', { className: 'btn-row', style: { marginTop: 26 } },
      h(Btn, { variant: 'primary', onClick: () => save(false) }, '保存设置')));

  const panelModel = () => h('div', null,
    h('h3', null, '选择 Provider'),
    h('p', { className: 'desc' }, '后端统一转发，浏览器不直连云端，因此不受 CORS 限制。'),
    h('div', { style: { maxHeight: 210, overflowY: 'auto', marginBottom: 18 } },
      (providers || []).map(p => h('button', {
        key: p.id, type: 'button', className: cls('provider-row', p.id === active && 'active'),
        style: { width: '100%', textAlign: 'left' }, onClick: () => patchV3('activeProvider', p.id),
      },
        h('div', { className: 'pr-top' },
          h('span', { className: 'pr-name' }, p.label || p.id),
          p.id === active && h('span', { className: 'pill' }, '当前')),
        h('div', { className: 'pr-url' }, (p.model || '未设模型') + ' · ' + (p.baseUrl || '')),
        p.hint && h('div', { className: 'hint' }, p.hint)))),
    h('h3', null, '当前 Provider 参数'),
    h('div', { className: 'field' },
      h('label', null, 'API Base URL'),
      h('input', { className: 'input', value: ov.baseUrl !== undefined ? ov.baseUrl : (prov.baseUrl || ''),
        onChange: e => override('baseUrl', e.target.value) }),
      h('div', { className: 'hint' }, 'OpenAI 兼容地址，后端会自动拼 /chat/completions')),
    h('div', { className: 'field' },
      h('label', null, '模型 ID'),
      h('input', { className: 'input', value: ov.model !== undefined ? ov.model : (prov.model || ''),
        onChange: e => override('model', e.target.value) })),
    h('div', { className: 'field' },
      h('label', null, 'API Key'),
      h('input', { className: 'input', type: 'password', value: keyInput,
        placeholder: (cfg.apiKeyMasked || '未设置') + '（留空表示不修改）',
        onChange: e => setKeyInput(e.target.value) }),
      h('div', { className: 'hint' }, '密钥只存本机配置文件，页面永远只拿到脱敏占位符；留空即保持原值。')),
    h('div', { className: 'field' },
      h('label', null, '备用 Provider（主用失败时自动降级）'),
      h('select', { className: 'input', value: v3.fallbackProvider || 'off',
        onChange: e => patchV3('fallbackProvider', e.target.value) },
        h('option', { value: 'off' }, '不启用（失败时明确报错）'),
        (providers || []).filter(p => p.id !== active).map(p => h('option', { key: p.id, value: p.id }, p.label || p.id)))),
    h('div', { className: 'btn-row' },
      h(Btn, { variant: 'primary', onClick: () => save(false) }, '保存设置'),
      h(Btn, { onClick: test, disabled: probing }, probing ? '测试中…' : '测试连接')),
    probe && h('div', { className: cls('note', !probe.ok) },
      probe.ok ? '连接正常 · HTTP ' + probe.http + ' · ' + probe.ms + ' ms' + (probe.note ? ' · ' + probe.note : '')
               : '连接失败 · HTTP ' + (probe.http || 0) + ' · ' + (probe.detail || '未知错误')),
    h('div', { className: 'note' },
      '本机代理偶发 502，后端会自动在「代理 → 直连」之间切换并记住可用通路；直连较慢（十几秒），可在「诊断」里查看审计记录确认走了哪条。'));

  const panelTools = () => h('div', null,
    h('h3', null, 'MCP 服务'),
    h('p', { className: 'desc' }, '支持 stdio 桥（本地子进程）、HTTP 与 Streamable。命令只来自本机配置，前端无法注入。'),
    (cfg.mcpServers || []).length
      ? (cfg.mcpServers || []).map(s => h('div', { key: s.id, className: 'provider-row' },
          h('div', { className: 'pr-top' },
            h('span', { className: 'pr-name' }, s.name || s.id),
            h(IconButton, { icon: 'trash', size: 14, danger: true, title: '移除',
              onClick: () => patchCfg('mcpServers', (cfg.mcpServers || []).filter(x => x.id !== s.id)) })),
          h('div', { className: 'pr-url' }, s.transport + ' · ' + (s.url || (s.command || '') + ' ' + (s.args || []).join(' ')))))
      : h('p', { className: 'desc' }, '（尚未添加）'),
    h('div', { className: 'row' },
      h('div', { className: 'field' },
        h('label', null, '名称'),
        h('input', { className: 'input', value: mcp.name, placeholder: '例如 秒哒',
          onChange: e => setMcp({ ...mcp, name: e.target.value }) })),
      h('div', { className: 'field' },
        h('label', null, '传输'),
        h('select', { className: 'input', value: mcp.transport, onChange: e => setMcp({ ...mcp, transport: e.target.value }) },
          h('option', { value: 'stdio-bridge' }, 'stdio 桥'),
          h('option', { value: 'http' }, 'HTTP'),
          h('option', { value: 'streamable' }, 'Streamable')))),
    h('div', { className: 'field' },
      h('label', null, mcp.transport === 'stdio-bridge' ? 'server.py 绝对路径' : '服务 URL'),
      h('input', { className: 'input', value: mcp.target,
        placeholder: mcp.transport === 'stdio-bridge' ? 'D:\\...\\server.py' : 'http://127.0.0.1:PORT/mcp',
        onChange: e => setMcp({ ...mcp, target: e.target.value }) })),
    h(Btn, { onClick: addMcp }, '添加'),
    h('h3', null, '本地技能'),
    h('p', { className: 'desc' }, '技能包位于 app_data/skills/，通过 @install 或 /api/skills 安装。'),
    skills === null ? h('p', { className: 'desc' }, '读取中…')
      : skills.length ? skills.map(s => h('div', { key: s.id, className: 'provider-row' },
          h('div', { className: 'pr-top' }, h('span', { className: 'pr-name' }, s.label || s.id)),
          h('div', { className: 'pr-url' }, s.description || s.file || '')))
        : h('p', { className: 'desc' }, '（未安装技能包）'),
    h('h3', null, '可用命令'),
    h('div', { className: 'log' }, COMMANDS.map(([c, d]) => c.padEnd(22, ' ') + d).join('\n')),
    h('div', { className: 'btn-row', style: { marginTop: 18 } },
      h(Btn, { variant: 'primary', onClick: () => save(false) }, '保存设置')));

  const kv = (k, v) => h('div', { className: 'kv' }, h('span', { className: 'k' }, k), h('span', { className: 'v' }, v));
  const panelDiagnostics = () => h('div', null,
    h('h3', null, '运行状态'),
    diag && diag.error && h('div', { className: 'note' }, '读取失败：' + diag.error),
    diag && diag.health && h('div', null,
      kv('版本', diag.health.version || ''), kv('当前 Provider', diag.health.activeProvider || ''),
      kv('模型', diag.health.model || ''), kv('密钥', diag.health.hasApiKey ? '已配置' : '未配置'),
      kv('存储可写', diag.health.writable ? '是' : '否')),
    h('h3', null, '审计链 / 零出域'),
    diag && diag.audit && h('div', null,
      kv('记录总数', diag.audit.stats.total), kv('本地调用', diag.audit.stats.localCalls),
      kv('联网调用', diag.audit.stats.networkCalls),
      kv('哈希链校验', diag.audit.stats.verify.valid ? '通过' : '断裂 ' + diag.audit.stats.verify.broken + ' 条'),
      h('div', { className: 'log', style: { marginTop: 12 } },
        (diag.audit.records || []).slice(-12).map(r => r.ts + '  ' + r.kind + '  ' + r.summary).join('\n') || '（暂无记录）')),
    h('h3', null, '文件快照'),
    diag && diag.snapshots && (diag.snapshots.snapshots || []).length
      ? (diag.snapshots.snapshots || []).slice(0, 12).map(s => h('div', { key: s.id, className: 'provider-row' },
          h('div', { className: 'pr-top' },
            h('span', { className: 'pr-name' }, s.target),
            h(Btn, { onClick: () => setConfirm({
              title: '回滚该文件？', message: '将用快照内容覆盖 ' + s.target + '，当前内容会被替换。',
              confirmText: '确认回滚', action: async () => {
                try { const r = await api.restore(s.id); onToast(r.ok ? '已回滚' : ('失败：' + r.error), !r.ok); }
                catch (e) { onToast('回滚失败：' + e.message, true); }
              },
            }) }, '回滚')),
          h('div', { className: 'pr-url' }, fmtTime(s.at) + ' · ' + s.size + ' B')))
      : h('p', { className: 'desc' }, '（暂无快照；通过应用写文件会自动留档）'),
    h('h3', null, '端点清单'),
    diag && diag.diagnostics && h('div', { className: 'log' },
      diag.diagnostics.endpoints.join('\n') + '\n\n旧端点（兼容）：\n' + diag.diagnostics.legacy.join('\n')));

  const panelAbout = () => h('div', null,
    h('h3', null, 'Super-Agient v3.3.0'),
    h('p', { className: 'desc' }, '本地智能办公助手 · 开发者：yang。界面按 Claude Desktop 形态重做，' +
      '后端为纯标准库 HTTP + pywebview 外壳；v3.3 内置 Agent 框架（6 种常用编排）、' +
      '重绘上下文窗口并加入本地长期记忆。'),
    h('div', { className: 'note' },
      '最大优势是省：22 个技能 + 6 种 Agent 框架全部封装在应用内。' +
      '写方案、写大纲、PDF 转文本/Word、文件互转、保存到指定位置、上下文压缩全部由本机完成，' +
      '执行阶段云端调用 0 次、token 0、联网 0。' +
      '模型只负责听懂意图并下发短指令，重活交给本机执行器。'),
    h('h3', null, '内置 Agent 框架'),
    h('div', { className: 'log' },
      'ReAct（推理→行动→观察，失败自动换工具）\n' +
      'Plan & Execute（先出计划再逐步执行）\n' +
      'Reflexion（执行→校验→反思→带修正重试一次）\n' +
      'Pipeline（用 → 串联，上一步产物传给下一步）\n' +
      'Local RAG（先检索本机文件库再成文）\n' +
      'Map / Reduce（多文件分别处理再汇总）\n' +
      '工具注册表：22 个内置技能自动映射 · 每步留 thought/action/observation 轨迹'),
    h('h3', null, '分层'),
    h('div', { className: 'log' },
      'Shell（pywebview / 机器人图标）→ UI（React UMD 零构建 + 统一上下文栅格）\n' +
      '→ Agent Framework（工具注册表 / 规划器 / 执行器 / 校验器 / 记忆 / 压缩）\n' +
      '→ Agent Core（意图路由 / 执行计划 / 明确降级）\n' +
      '→ Skill Hub（22 个内置技能：docgen 长文 + office_skills 八格式 + filehub 解析）\n' +
      '→ Task Engine（模型指令白名单校验 → 本地执行 → 轨迹回执）\n' +
      '→ Storage（会话 / 审计链 / 快照 / 上传文件 / 输出文件 / agent_memory.json）'),
    h('h3', null, '隐私边界'),
    h('div', { className: 'log' },
      '· 密钥只存本机 config.json，页面只拿到脱敏占位符\n' +
      '· 默认零出域：仅 @web、联网按钮、模型调用与显式探测会联网\n' +
      '· 本地办公生成的内容完全不出本机；可保存到用户指定的本机目录\n' +
      '· 上传文件只存本机；走云端问答时仅发送前 1500 字摘要，可在输入区关闭该开关\n' +
      '· 上下文窗口压缩只在本机做，旧消息合成摘要、最近 6 条保留原文，不调用模型\n' +
      '· 本机长期记忆落在 agent_memory.json，不上传、不作联网检索关键词\n' +
      '· 未填字段一律渲染成【待填：…】，绝不编造单位、人名、文号与数字\n' +
      '· 审计链只记类型/摘要/长度，不记正文、不记密钥\n' +
      '· 破坏性操作（删会话、回滚文件）一律二次确认\n' +
      '· 未完成的改进：密钥仍是明文落盘，DPAPI 加密留待后续版本'),
    h('h3', null, '快捷键与命令'),
    h('div', { className: 'log' },
      'Enter        发送\nShift+Enter  换行\nEsc          关闭面板\n' +
      '@office      本地办公面板\n@files       本地文件库\n@方案 / @大纲  本地生成长文\n' +
      '@转换 pdf    把附件转成目标格式\n@task {...}   手动下发本机任务指令\n' +
      '@agent <目标> 用内置 Agent 框架执行并显示轨迹\n@框架       打开 Agent 框架面板（6 种编排）\n' +
      '@保存到 D:\\ 设置默认保存位置\n@skills3     技能与模板清单\n@help        全部命令'),
    h('h3', null, '回滚'),
    h('p', { className: 'desc' }, 'v3.2.0 / v3.1.0 / v3.0.0 / v2.3.1 / v2.3.0 的 EXE 与源码完整保留在 builds/ 与 src/，随时可换回。' +
      'v3.3.0 使用独立源码目录 src/v3.3.0/ 与前端 webdist33/，但 APP_NAME 保持不变，' +
      '因此共用同一 config.json、会话与审计链，不需要迁移数据。'));

  const PANELS = { general: panelGeneral, model: panelModel, tools: panelTools,
                   diagnostics: panelDiagnostics, about: panelAbout };

  const head = h('div', { className: 'drawer-head' },
    h(Icon, { name: 'settings', size: 18 }),
    h('h2', null, '设置'),
    h(IconButton, { icon: 'close', title: '关闭', onClick: onClose }));

  const tabsNav = h('nav', { className: 'tabs' },
    TABS.map(([id, label, icon]) => h('button', {
      key: id, type: 'button', className: cls('tab', tab === id && 'active'), onClick: () => setTab(id),
    }, h(Icon, { name: icon, size: 13, style: { verticalAlign: '-2px', marginRight: 6 } }), label)));

  const body = h('div', { className: 'drawer-body' },
    tabsNav,
    h('div', { className: 'panel' }, (PANELS[tab] || panelAbout)()));

  const dialog = confirm && h(ConfirmDialog, {
    title: confirm.title, message: confirm.message, confirmText: confirm.confirmText,
    onCancel: () => setConfirm(null),
    onConfirm: async () => { const fn = confirm.action; setConfirm(null); if (fn) await fn(); },
  });

  return h('div', { className: 'overlay', onClick: onClose },
    h('div', { className: 'drawer', onClick: e => e.stopPropagation() }, head, body),
    dialog);
}
