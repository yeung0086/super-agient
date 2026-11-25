/* Super-Agient v3.3 — 本地文件枢纽 / 模型任务指令 UI
   所有请求只到本机 /api/v3/files* 与 /api/v3/tasks*，不经过云端模型。 */
import {
  h, useState, useEffect, useRef, cls, copyText, api, Icon,
  BrandMark, APP, LOCAL_BADGE,
} from './core.js';
import { Btn, IconButton, FileCard, LocalBadge } from './components.js';

const MAX_FILE = 25 * 1024 * 1024;

/* ── 保存位置输入 ─────────────────────────────────────── */
export function SaveToField({ value, onChange, compact }) {
  return h('label', { className: cls('of-field', 'wide', compact && 'compact') },
    h('span', null, '保存位置（可选）'),
    h('input', {
      className: 'input', value: value || '',
      placeholder: '例如 D:\\AI资料\\培训方案.docx 或 D:\\AI资料\\',
      onChange: e => onChange(e.target.value),
    }),
    h('small', { className: 'field-tip' },
      '留空则存到默认输出目录；可写完整文件名或目录。同名自动加序号，绝不覆盖；不接受网络路径。'));
}

/* ── 附件条（上传 / 拖拽 / 芯片） ─────────────────────── */
export function AttachmentBar({ files, onUpload, onRemove, onOpenFiles, busy,
                                 contextOn, onToggleContext }) {
  const ref = useRef(null);
  const [drag, setDrag] = useState(false);
  const pick = (e) => {
    const fl = e.target.files;
    if (fl && fl.length) onUpload(fl);
    e.target.value = '';
  };
  return h('div', {
    className: cls('attach-bar', drag && 'dragging'),
    onDragOver: e => { e.preventDefault(); setDrag(true); },
    onDragLeave: e => { e.preventDefault(); setDrag(false); },
    onDrop: e => {
      e.preventDefault(); setDrag(false);
      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) onUpload(e.dataTransfer.files);
    },
  },
    h('input', { ref, type: 'file', multiple: true, style: { display: 'none' }, onChange: pick }),
    h('button', { type: 'button', className: 'attach-btn', disabled: busy,
                  onClick: () => ref.current && ref.current.click() },
      h(Icon, { name: 'plus', size: 13 }), ' 上传本地文件'),
    h('button', { type: 'button', className: 'attach-btn ghost', onClick: onOpenFiles },
      h(Icon, { name: 'file', size: 13 }), ' 文件库'),
    (files || []).map(f => h('span', { key: f.id, className: 'attach-chip', title: f.name },
      h(Icon, { name: 'doc', size: 12 }),
      h('span', { className: 'chip-name' }, f.name),
      h('button', { type: 'button', title: '移除附件', onClick: () => onRemove(f.id) }, '×'))),
    h('label', { className: 'attach-toggle',
                 title: '关闭后，走云端问答时不会发送文件摘要；本地转换/解析不受影响' },
      h('input', { type: 'checkbox', checked: !!contextOn,
                   onChange: e => onToggleContext && onToggleContext(e.target.checked) }),
      h('span', null, '摘要随对话发送')),
    (files || []).length === 0 &&
      h('span', { className: 'attach-tip' },
        drag ? '松开即可上传' : '可拖拽文件到此处 · PDF / Word / Excel / PPT / 网页 / 文本 · 单文件 ≤25 MB · 仅存本机'));
}

/* ── 文件库面板 ───────────────────────────────────────── */
export function FilesPanel({ onClose, onToast, onAttach, onConvert }) {
  const [list, setList] = useState([]);
  const [meta, setMeta] = useState(null);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  const reload = () => api.files().then(d => { setList(d.files || []); setMeta(d); })
    .catch(e => setErr('读取文件库失败：' + (e.message || e)));
  useEffect(() => { reload(); }, []);

  const doPreview = async (f) => {
    setBusy(true); setErr(''); setPreview(null);
    try {
      const r = await api.fileRead(f.id, 4000);
      setPreview(r);
      if ((r.warnings || []).length) onToast && onToast(r.warnings[0], true);
    } catch (e) { setErr(String(e.message || e)); }
    finally { setBusy(false); }
  };
  const doDelete = async (f) => {
    try {
      await api.fileDelete(f.id);
      if (preview && preview.id === f.id) setPreview(null);
      reload(); onToast && onToast('已删除 ' + f.name);
    } catch (e) { setErr(String(e.message || e)); }
  };

  return h('div', { className: 'modal-wrap', onClick: onClose },
    h('div', { className: 'modal office-panel files-panel', onClick: e => e.stopPropagation() },
      h('div', { className: 'office-head' },
        h(BrandMark, { size: 22 }),
        h('div', null, h('h3', null, '本地文件库'),
          h('p', null, '上传的文件只存本机；解析在本机完成，可注入对话或直接交给本地技能')),
        h(IconButton, { icon: 'close', title: '关闭', onClick: onClose })),
      h(LocalBadge),
      h('div', { className: 'files-meta' },
        h('span', null, (list.length || 0) + ' 个文件'),
        meta && h('span', null, '目录：' + meta.root),
        h('span', null, '单文件 ≤25 MB')),
      err && h('div', { className: 'office-err' }, err),
      h('div', { className: 'files-grid' },
        h('div', { className: 'files-list' },
          list.length === 0 && h('div', { className: 'empty-note' },
            '还没有文件。点输入框上方的「上传本地文件」，或把文件拖进输入区。'),
          list.map(f => h('div', { key: f.id, className: cls('file-row', preview && preview.id === f.id && 'active') },
            h(Icon, { name: 'doc', size: 15 }),
            h('div', { className: 'fr-main' },
              h('div', { className: 'fr-name' }, f.name),
              h('div', { className: 'fr-sub' }, f.ext + ' · ' + Math.round(f.size / 1024) + ' KB · ' + (f.at || '').slice(0, 16))),
            h('div', { className: 'fr-acts' },
              h(IconButton, { icon: 'search', title: '解析预览', size: 14, onClick: () => doPreview(f) }),
              h(IconButton, { icon: 'plus', title: '加入本轮附件', size: 14,
                onClick: () => { onAttach && onAttach(f); onToast && onToast('已加入附件：' + f.name); } }),
              h(IconButton, { icon: 'trash', title: '删除', size: 14, danger: true,
                onClick: () => doDelete(f) }))))),
        h('div', { className: 'files-preview' },
          preview
            ? h('div', null,
                h('h4', null, preview.name),
                h('div', { className: 'pv-meta' },
                  preview.chars + ' 字 · ' + JSON.stringify(preview.meta || {})),
                (preview.warnings || []).map((w, i) => h('div', { key: i, className: 'warn-note' }, w)),
                h('pre', { className: 'pv-text' }, preview.text || '（无可提取文本）'),
                h('div', { className: 'btn-row' },
                  h(Btn, { onClick: () => onConvert && onConvert(preview) }, '转换为办公文件'),
                  h(Btn, { variant: 'primary', onClick: async () => {
                    const ok = await copyText(preview.text || '');
                    onToast && onToast(ok ? '解析文本已复制' : '复制失败', !ok);
                  } }, '复制解析文本')))
            : h('div', { className: 'empty-note' }, '点左侧放大镜图标，查看本机解析出来的文本与元信息。'))),
      h('div', { className: 'btn-row', style: { justifyContent: 'flex-end', marginTop: 12 } },
        h(Btn, { onClick: onClose }, '关闭'))));
}

/* TaskCard 定义在 components.js（与 FileCard / LocalBadge 同层），此处转出避免循环依赖 */
export { TaskCard } from './components.js';

/* ── 上传工具：File → base64 → 本机后端 ───────────────── */
export async function uploadFileList(fileList, onProgress) {
  const out = [], errors = [];
  for (const f of Array.from(fileList || [])) {
    if (f.size > MAX_FILE) { errors.push(f.name + '：超过 25 MB'); continue; }
    try {
      const data = await new Promise((res, rej) => {
        const rd = new FileReader();
        rd.onload = () => res(String(rd.result || '').split(',')[1] || '');
        rd.onerror = () => rej(new Error('读取失败'));
        rd.readAsDataURL(f);
      });
      onProgress && onProgress('正在上传 ' + f.name + '…');
      const r = await api.fileUpload(f.name, data, f.type || '');
      if (!r.ok) throw new Error(r.error || '上传失败');
      out.push(r.file);
    } catch (e) { errors.push(f.name + '：' + (e.message || e)); }
  }
  return { files: out, errors };
}
