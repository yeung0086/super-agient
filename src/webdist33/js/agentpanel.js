/* Super-Agient v3.3 — 内置 Agent 框架面板
   6 种常用编排 + 22 个工具 + 本地记忆 + 执行轨迹，全部封装在应用内、只到本机后端。 */
import {
  h, useState, useEffect, cls, api, Icon, BrandMark, APP, LOCAL_BADGE,
} from './core.js';
import { Btn, IconButton, LocalBadge, AgentTraceCard } from './components.js';
import { SaveToField } from './files.js';

const FORMATS = ['docx', 'html', 'pdf', 'xlsx', 'pptx', 'md', 'txt', 'csv'];

export function AgentPanel({ onClose, onToast, onInsert, saveTo, onSaveTo, attachments }) {
  const [mf, setMf] = useState(null);
  const [fw, setFw] = useState('react');
  const [goal, setGoal] = useState('');
  const [fmt, setFmt] = useState('docx');
  const [outDir, setOutDir] = useState(saveTo || '');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [planText, setPlanText] = useState('');
  const [err, setErr] = useState('');
  const [memText, setMemText] = useState('');
  const [memories, setMemories] = useState([]);

  const refreshMem = () => api.agentMemories()
    .then(r => setMemories(r.items || [])).catch(() => {});
  useEffect(() => {
    api.agent().then(setMf).catch(e => setErr('读取 Agent 清单失败：' + (e.message || e)));
    refreshMem();
  }, []);

  const frameworks = (mf && mf.frameworks) || [];
  const toolCount = mf ? mf.toolCount : 22;

  const buildParams = () => {
    const p = { format: fmt };
    if (outDir) p.saveTo = outDir;
    if (attachments && attachments.length) {
      p.fileId = attachments[0].id;
      p.fileIds = attachments.map(a => a.id);
    }
    return p;
  };

  const doRun = async () => {
    if (!goal.trim()) { setErr('请先写下要完成的目标'); return; }
    setBusy(true); setErr(''); setPlanText(''); setResult(null);
    try {
      const r = await api.agentRun(goal.trim(), fw, buildParams());
      setResult(r);
      onToast && onToast('Agent 执行 ' + r.steps + ' 步，成功 ' + r.succeeded + ' 条（零 token）', !r.ok);
    } catch (e) { setErr(String(e.message || e)); }
    finally { setBusy(false); }
  };

  const doPlan = async () => {
    if (!goal.trim()) { setErr('请先写下要完成的目标'); return; }
    setBusy(true); setErr('');
    try {
      const r = await api.agentPlan(goal.trim(), buildParams());
      setPlanText(r.steps.map((s, i) =>
        (i + 1) + '. ' + s.skill + ' — ' + (s.thought || s.note || '')).join('\n'));
      setResult(null);
    } catch (e) { setErr(String(e.message || e)); }
    finally { setBusy(false); }
  };

  const addMem = async () => {
    if (!memText.trim()) return;
    try {
      await api.agentMemory('add', { text: memText.trim(), tag: 'user' });
      setMemText(''); refreshMem(); onToast && onToast('已记到本机记忆');
    } catch (e) { setErr(String(e.message || e)); }
  };
  const delMem = async (id) => {
    try { await api.agentMemory('delete', { id }); refreshMem(); }
    catch (e) { setErr(String(e.message || e)); }
  };

  const fwCards = h('div', { className: 'fw-grid' },
    frameworks.length === 0
      ? h('div', { className: 'empty-note' }, '正在读取内置框架清单…')
      : null,
    frameworks.map(f => h('button', {
      key: f.id, type: 'button',
      className: cls('fw-card', fw === f.id && 'active'),
      onClick: () => setFw(f.id),
    },
      h('div', { className: 'fw-name' }, f.name),
      h('div', { className: 'fw-desc' }, f.desc),
      h('div', { className: 'fw-when' }, '适用：' + f.when))));

  const fmtButtons = h('div', { className: 'fmt-grid compact' },
    FORMATS.map(f => h('button', {
      key: f, type: 'button', className: cls('fmt-btn', fmt === f && 'active'),
      onClick: () => setFmt(f),
    }, f.toUpperCase())));

  const memItems = h('div', { className: 'mem-list' },
    memories.length === 0
      ? h('div', { className: 'mem-empty' }, '暂无本机记忆')
      : memories.slice(-8).reverse().map(m => h('div', { key: m.id, className: 'mem-row' },
          h('span', null, m.text),
          h('button', { type: 'button', className: 'mem-del', title: '删除',
                        onClick: () => delMem(m.id) }, '×'))));

  const left = h('div', { className: 'ag-left' },
    h('h4', null, '① 选择编排框架'),
    fwCards,
    h('h4', null, '② 目标（可写一句中文）'),
    h('textarea', {
      className: 'input', rows: 3, value: goal,
      placeholder: '例如：写一份家政服务培训方案 → 导出为 PDF\n或：根据已上传资料写一份资料汇编',
      onChange: e => setGoal(e.target.value),
    }),
    h('div', { className: 'note' },
      '用 → 或「然后」串联多步；Pipeline 会把上一步产物自动传给下一步。' +
      '规划与执行都在本机，不调用模型、不联网。'),
    h('h4', null, '③ 本机长期记忆'),
    h('div', { className: 'mem-add' },
      h('input', { className: 'input', value: memText, placeholder: '记一条偏好或事实，只存本机',
                   onChange: e => setMemText(e.target.value) }),
      h(Btn, { onClick: addMem }, '记下')),
    memItems);

  const right = h('div', { className: 'ag-right' },
    h('h4', null, '④ 参数'),
    fmtButtons,
    h(SaveToField, { value: outDir, onChange: (v) => {
      setOutDir(v); if (onSaveTo) onSaveTo(v);
    }, compact: true }),
    h('div', { className: 'ag-attach' },
      h(Icon, { name: 'offline', size: 13 }),
      attachments && attachments.length
        ? '已带入 ' + attachments.length + ' 个本机附件：' + attachments.map(a => a.name).join('、')
        : '未带入附件；Map/Reduce 与本地检索会自动使用文件库'),
    h('div', { className: 'btn-row' },
      h(Btn, { disabled: busy, onClick: doPlan }, '只看计划'),
      h(Btn, { variant: 'primary', disabled: busy, onClick: doRun },
        busy ? '执行中…' : '运行 ' + (frameworks.find(f => f.id === fw) || {}).name),
      result && onInsert && h(Btn, { onClick: () => {
        onInsert(result.summary || ''); onClose();
      } }, '插入对话')),
    err && h('div', { className: 'office-err' }, err),
    planText && h('div', { className: 'ag-plan' },
      h('div', { className: 'ag-plan-head' }, '本机规划（不执行）'),
      h('pre', null, planText)),
    result && h(AgentTraceCard, { result, onToast }),
    result && h('details', { className: 'ag-summary' },
      h('summary', null, '查看完整执行摘要'),
      h('pre', null, result.summary || '')));

  return h('div', { className: 'modal-wrap', onClick: onClose },
    h('div', { className: 'modal office-panel agent-panel', onClick: e => e.stopPropagation() },
      h('div', { className: 'office-head' },
        h(BrandMark, { size: 22 }),
        h('div', null,
          h('h3', null, '内置 Agent 框架'),
          h('p', null, APP.name + ' · ' + (frameworks.length || 6) + ' 种编排 · ' +
            toolCount + ' 个本机工具 · 零 token')),
        h(IconButton, { icon: 'close', title: '关闭', onClick: onClose })),
      h(LocalBadge),
      h('div', { className: 'agent-body' }, left, right)));
}
