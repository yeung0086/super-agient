/* Super-Agient v3.3 — 本地办公面板 / 导出 / 文件转换
   所有请求只到本机 /api/v3/skills* 与 /api/v3/files*，不经过云端模型。 */
import {
  h, useState, useEffect, cls, copyText, api, Icon,
  BrandMark, APP, LOCAL_BADGE,
} from './core.js';
import { Btn, IconButton, LocalBadge, FileCard } from './components.js';
import { SaveToField } from './files.js';

export function ExportMenu({ text, title, initialFormat, saveTo, onClose, onToast }) {
  const [fmt, setFmt] = useState(initialFormat || 'docx');
  const [busy, setBusy] = useState(false);
  const [file, setFile] = useState(null);
  const [err, setErr] = useState('');

  const doExport = async (f) => {
    setBusy(true); setErr('');
    try {
      const params = {
        markdown: text, title: title || '导出文档', format: f,
        filename: title || '导出文档',
      };
      if (saveTo) params.saveTo = saveTo;
      const r = await api.skillsRun('text.write', params);
      if (!r.ok) throw new Error(r.error || '导出失败');
      setFile(r);
      onToast && onToast('已导出 ' + f.toUpperCase() + '（零 token）');
    } catch (e) { setErr(String(e.message || e)); }
    finally { setBusy(false); }
  };

  return h('div', { className: 'modal-wrap', onClick: onClose },
    h('div', { className: 'modal office-modal', onClick: e => e.stopPropagation() },
      h('div', { className: 'office-head' },
        h(BrandMark, { size: 20 }),
        h('div', null, h('h3', null, '导出为办公文件'), h('p', null, '本机渲染，不调用模型、不联网')),
        h(IconButton, { icon: 'close', title: '关闭', onClick: onClose })),
      h(LocalBadge),
      h('div', { className: 'fmt-grid' },
        [['docx', 'Word', 'doc'], ['html', '网页', 'external'], ['pdf', 'PDF', 'file'],
         ['xlsx', 'Excel', 'database'], ['pptx', 'PPT', 'panel'], ['md', 'Markdown', 'save'],
         ['txt', '文本', 'save'], ['csv', 'CSV', 'database']].map(([id, label, icon]) =>
          h('button', { key: id, type: 'button', className: cls('fmt-btn', fmt === id && 'active'),
                        onClick: () => setFmt(id) },
            h(Icon, { name: icon, size: 15 }), label))),
      err && h('div', { className: 'office-err' }, err),
      file && h(FileCard, { file, onToast }),
      h('div', { className: 'btn-row', style: { justifyContent: 'flex-end', marginTop: 14 } },
        h(Btn, { onClick: onClose }, '关闭'),
        h(Btn, { variant: 'primary', disabled: busy, onClick: () => doExport(fmt) },
          busy ? '正在导出…' : '导出 ' + fmt.toUpperCase()))));
}

export function OfficePanel({ onClose, onToast, onInsert, saveTo, onSaveTo, attachments, convertReq }) {
  const [mf, setMf] = useState(null);
  const [tpl, setTpl] = useState('training_plan');
  const [prompt, setPrompt] = useState('');
  const [args, setArgs] = useState({});
  const [fmt, setFmt] = useState('docx');
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState(null);
  const [file, setFile] = useState(null);
  const [err, setErr] = useState('');
  const [tab, setTab] = useState(convertReq ? 'files' : 'write');

  useEffect(() => {
    api.skills3().then(setMf).catch(e => setErr('读取本地技能清单失败：' + (e.message || e)));
  }, []);

  const templates = (mf && mf.templates) || [];
  const formats = (mf && mf.formats) || [];
  const fields = (mf && mf.fields) || [];
  const current = templates.find(t => t.id === tpl) || {};

  const buildParams = (f) => ({
    template: tpl, prompt, args, format: f || fmt,
    // 文件名由后端使用清洗后的文档标题生成
    ...(saveTo ? { saveTo } : {}),
  });

  const doPreview = async () => {
    setBusy(true); setErr(''); setFile(null);
    try {
      const r = await api.skillsGenerate(tpl, prompt, args);
      if (!r.ok || !r.doc) throw new Error(r.error || '生成失败');
      setPreview(r.doc);
      onToast && onToast('已本地生成 ' + r.doc.chars + ' 字（零 token）');
    } catch (e) { setErr(String(e.message || e)); }
    finally { setBusy(false); }
  };

  const doExport = async (f) => {
    setBusy(true); setErr('');
    try {
      const r = await api.skillsRun('text.write', buildParams(f));
      if (!r.ok) throw new Error(r.error || '导出失败');
      setFile(r);
      setPreview({ title: r.title, markdown: r.markdown, chars: r.chars });
      onToast && onToast('已导出 ' + (f || fmt).toUpperCase() + '（零 token）');
    } catch (e) { setErr(String(e.message || e)); }
    finally { setBusy(false); }
  };

  const fieldInput = (f) => h('label', { key: f.key, className: 'of-field' },
    h('span', null, f.label),
    h('input', { className: 'input', value: args[f.key] || '', placeholder: f.default || '留空则用占位符',
                 onChange: e => setArgs(a => ({ ...a, [f.key]: e.target.value })) }));

  return h('div', { className: 'modal-wrap', onClick: onClose },
    h('div', { className: 'modal office-panel', onClick: e => e.stopPropagation() },
      h('div', { className: 'office-head' },
        h(BrandMark, { size: 22 }),
        h('div', null,
          h('h3', null, '本地智能办公'),
          h('p', null, APP.name + ' · ' + (mf ? mf.skills.length : '—') + ' 个本地技能 · ' +
            (mf ? mf.templates.length : '—') + ' 个长文模板 · 全部在本机执行')),
        h(IconButton, { icon: 'close', title: '关闭', onClick: onClose })),
      h(LocalBadge),

      h('div', { className: 'office-tabs' },
        [['write', '写方案 / 大纲'], ['files', '文件转换'], ['skills', '内置技能']].map(([id, label]) =>
          h('button', { key: id, type: 'button', className: cls('office-tab', tab === id && 'active'),
                        onClick: () => setTab(id) }, label))),

      tab === 'files'
        ? h(FileConvertPane, { formats, attachments, saveTo, onSaveTo, convertReq, onToast })
        : tab === 'skills'
        ? h('div', { className: 'office-body' },
            h('h4', null, '本地技能（' + (mf ? mf.skills.length : 0) + '）'),
            h('div', { className: 'skill-list' },
              (mf ? mf.skills : []).map(s => h('div', { key: s.id, className: 'skill-row' },
                h(Icon, { name: s.icon || 'bolt', size: 14 }),
                h('div', null,
                  h('div', { className: 'sk-name' }, s.label, ' ', h('code', null, s.id)),
                  h('div', { className: 'sk-desc' }, s.desc))))),
            h('h4', null, '长文模板（' + templates.length + '）'),
            h('div', { className: 'skill-list' },
              templates.map(t => h('div', { key: t.id, className: 'skill-row' },
                h(Icon, { name: 'doc', size: 14 }),
                h('div', null,
                  h('div', { className: 'sk-name' }, t.label, ' ', h('span', { className: 'pill' }, t.cat)),
                  h('div', { className: 'sk-desc' }, t.desc))))))
        : h('div', { className: 'office-body' },
            h('div', { className: 'of-left' },
              h('h4', null, '① 选择模板'),
              h('div', { className: 'tpl-list' },
                templates.map(t => h('button', { key: t.id, type: 'button',
                  className: cls('tpl-btn', tpl === t.id && 'active'),
                  onClick: () => { setTpl(t.id); setPreview(null); setFile(null); } },
                  h('strong', null, t.label),
                  h('span', null, t.cat + ' · ' + t.sections + ' 章')))),
              h('h4', null, '② 主题与参数'),
              h('textarea', { className: 'input', rows: 3, value: prompt,
                placeholder: '例如：家政服务技能培训 单位=示范中心 人数=30 课时=240',
                onChange: e => setPrompt(e.target.value) }),
              h('div', { className: 'of-fields' }, fields.filter(f => f.key !== 'topic').map(fieldInput)),
              h('div', { className: 'note' }, '留空的字段一律渲染成【待填：…】，不会编造单位、人名、文号或数字。')),
            h('div', { className: 'of-right' },
              h('h4', null, '③ 输出格式'),
              h('div', { className: 'fmt-grid' },
                formats.map(f => h('button', { key: f.id, type: 'button',
                  className: cls('fmt-btn', fmt === f.id && 'active'),
                  onClick: () => setFmt(f.id) }, f.id.toUpperCase()))),
              h(SaveToField, { value: saveTo || '', onChange: onSaveTo || (() => {}), compact: true }),
              h('div', { className: 'btn-row' },
                h(Btn, { disabled: busy, onClick: doPreview }, '本地预览'),
                h(Btn, { variant: 'primary', disabled: busy, onClick: () => doExport(fmt) },
                  busy ? '处理中…' : '生成并导出 ' + fmt.toUpperCase())),
              err && h('div', { className: 'office-err' }, err),
              file && h(FileCard, { file, onToast }),
              preview && h('div', { className: 'preview-box' },
                h('div', { className: 'preview-head' },
                  h('strong', null, preview.title || '预览'),
                  h('span', null, (preview.chars || 0) + ' 字'),
                  h(Btn, { onClick: async () => {
                    const ok = await copyText(preview.markdown || '');
                    onToast && onToast(ok ? '全文已复制' : '复制失败', !ok);
                  } }, '复制全文'),
                  onInsert && h(Btn, { onClick: () => { onInsert(preview.markdown || ''); onClose(); } }, '插入对话')),
                h('pre', { className: 'preview-text' }, (preview.markdown || '').slice(0, 6000))))),
      h('div', { className: 'office-foot' },
        h('span', null, saveTo ? '保存位置：' + saveTo : '输出目录：' + (mf ? mf.outputDir : '本机应用数据目录')),
        h('span', null, '文件名带日期与序号，绝不覆盖旧文件'))));
}

/* ── 文件转换页签：上传文件 → 选格式 → 指定位置保存 ────── */
export function FileConvertPane({ formats, attachments, saveTo, onSaveTo, convertReq, onToast }) {
  const [list, setList] = useState([]);
  const [fid, setFid] = useState('');
  const [fmt, setFmt] = useState('docx');
  const [busy, setBusy] = useState(false);
  const [file, setFile] = useState(null);
  const [err, setErr] = useState('');

  useEffect(() => {
    api.files().then(d => setList(d.files || [])).catch(e => setErr('读取文件库失败：' + (e.message || e)));
  }, []);
  useEffect(() => {
    if (convertReq && convertReq.id) setFid(convertReq.id);
  }, [convertReq]);
  useEffect(() => {
    if (!fid && list.length) setFid(list[0].id);
  }, [list, fid]);

  const current = list.find(f => f.id === fid) || {};
  const isPdf = String(current.ext || '').toLowerCase() === '.pdf';

  const doConvert = async () => {
    if (!fid) { setErr('请先上传或选择一个文件'); return; }
    setBusy(true); setErr(''); setFile(null);
    try {
      let skill = 'doc.convert';
      if (isPdf) {
        skill = { docx: 'pdf.to_docx', txt: 'pdf.to_text', md: 'pdf.to_md', html: 'pdf.to_html' }[fmt] || 'doc.convert';
      }
      const params = { fileId: fid, format: fmt };
      if (saveTo) params.saveTo = saveTo;
      const r = await api.skillsRun(skill, params);
      if (!r.ok) throw new Error(r.error || '转换失败');
      setFile(r);
      onToast && onToast('已转换为 ' + fmt.toUpperCase() + '（零 token）');
      if ((r.warnings || []).length) setErr(r.warnings.join('；'));
    } catch (e) { setErr(String(e.message || e)); }
    finally { setBusy(false); }
  };

  const fileButtons = list.map(f => h('button', {
    key: f.id, type: 'button',
    className: cls('tpl-btn', fid === f.id && 'active'),
    onClick: () => setFid(f.id),
  },
    h('strong', null, f.name),
    h('span', null, f.ext + ' · ' + Math.round(f.size / 1024) + ' KB')));

  const fmtButtons = (formats || []).map(f => h('button', {
    key: f.id, type: 'button',
    className: cls('fmt-btn', fmt === f.id && 'active'),
    onClick: () => setFmt(f.id),
  }, f.id.toUpperCase()));

  const leftPane = h('div', { className: 'of-left' },
    h('h4', null, '① 选择本机文件'),
    list.length === 0 && h('div', { className: 'empty-note' },
      '文件库为空。关闭面板后，用输入框上方的「上传本地文件」添加。'),
    h('div', { className: 'tpl-list' }, fileButtons),
    h('div', { className: 'note' },
      'PDF / Word / Excel / PPT / 网页 / 文本在本机解析；扫描版 PDF 无文本层会明确提示，不伪造内容。'));

  const rightPane = h('div', { className: 'of-right' },
    h('h4', null, '② 目标格式'),
    h('div', { className: 'fmt-grid' }, fmtButtons),
    h('h4', null, '③ 保存位置'),
    h(SaveToField, { value: saveTo || '', onChange: onSaveTo || (() => {}), compact: true }),
    h('div', { className: 'btn-row' },
      h(Btn, { variant: 'primary', disabled: busy || !fid, onClick: doConvert },
        busy ? '转换中…' : '转换并保存 ' + fmt.toUpperCase())),
    err && h('div', { className: 'office-err' }, err),
    file && h(FileCard, { file, onToast }));

  return h('div', { className: 'office-body convert-body' }, leftPane, rightPane);
}
