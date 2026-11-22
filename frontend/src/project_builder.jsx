import React, {useState} from 'react';
import {AlertTriangle, CheckCircle2, Eye, FolderTree, Rocket, Sparkles, X} from 'lucide-react';
import {ModalShell} from './ui.jsx';
import {
  AUTONOMY_OPTIONS, EMPTY_FORM, MAX_IDEA, STACK_OPTIONS, buildRequestBody, ideaProblem, stageSummary,
} from './project_builder.js';

const API = import.meta.env.VITE_API_URL || '';

async function call(body) {
  const response = await fetch(`${API}/api/sdlc/project-builder`, {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(data.detail) ? data.detail.map(item => item.msg).join('؛ ') : data.detail;
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return data;
}

/** "I want project X": describe it, preview the plan, and Taskloom creates folders, prompts, files and repositories. */
export default function ProjectBuilder({onCreated}) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [plan, setPlan] = useState(null);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const set = patch => { setForm(current => ({...current, ...patch})); setPlan(null); };
  const problem = ideaProblem(form.idea);

  const close = () => { if (busy) return; setOpen(false); setForm(EMPTY_FORM); setPlan(null); setResult(null); setError(''); };

  const run = async (kind) => {
    setBusy(kind); setError('');
    try {
      const data = await call(buildRequestBody(form, kind === 'preview'));
      if (kind === 'preview') setPlan(data);
      else { setResult(data); onCreated?.(data.project.id); }
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy('');
    }
  };

  return (
    <>
      <button type="button" className="sdlc-btn sdlc-btn-secondary" onClick={() => setOpen(true)}>
        <Sparkles size={16} /> ساخت خودکار پروژه
      </button>
      {open && (
        <ModalShell label="ساخت خودکار پروژه" onClose={close}>
          <div className="sdlc-project-form sdlc-builder">
            <div className="sdlc-form-header">
              <h3><Sparkles size={18} /> ساخت خودکار پروژه</h3>
              <button type="button" className="sdlc-form-close" onClick={close} aria-label="بستن"><X size={20} /></button>
            </div>

            {result ? (
              <div className="sdlc-form-body">
                <div className="sdlc-builder-done" role="status">
                  <CheckCircle2 size={22} />
                  <div>
                    <strong>پروژهٔ «{result.project.name}» آماده است.</strong>
                    <p>{result.files_written.toLocaleString('fa-IR')} فایل در {Object.keys(result.folders).length.toLocaleString('fa-IR')} پوشه ساخته شد و هر پوشه یک مخزن Git با شاخهٔ sandbox دارد. همین حالا می‌توانید تسک بدهید.</p>
                  </div>
                </div>
                <p className="sdlc-builder-root" dir="ltr"><FolderTree size={14} /> {result.root}</p>
                <ul className="sdlc-builder-stages">
                  {Object.entries(result.folders).map(([stage, folder]) => (
                    <li key={stage}><span><b>{stage}</b> <small dir="ltr">{result.commits[stage]}</small></span><code dir="ltr">{folder}</code></li>
                  ))}
                </ul>
                {result.notes.map(note => <p key={note} className="sdlc-builder-note" dir="auto">{note}</p>)}
                <div className="sdlc-form-actions"><button type="button" className="sdlc-btn sdlc-btn-primary" onClick={close}>بستن</button></div>
              </div>
            ) : (
              <div className="sdlc-form-body">
                <div className="sdlc-form-group">
                  <label htmlFor="builder-idea">چه پروژه‌ای می‌خواهید؟</label>
                  <textarea id="builder-idea" rows={5} dir="auto" maxLength={MAX_IDEA} value={form.idea} onChange={event => set({idea: event.target.value})}
                    placeholder="مثلاً: یک API برای فروشگاه آنلاین کتاب با پایتون، سبد خرید و یک داشبورد وب برای مدیر فروشگاه" />
                  {form.idea.trim() && problem && <small className="sdlc-builder-hint">{problem}</small>}
                </div>
                <div className="sdlc-builder-grid">
                  <div className="sdlc-form-group">
                    <label htmlFor="builder-name">نام پروژه <small>(اختیاری)</small></label>
                    <input id="builder-name" type="text" dir="auto" value={form.name} onChange={event => set({name: event.target.value})} />
                  </div>
                  <div className="sdlc-form-group">
                    <label htmlFor="builder-stack">فناوری</label>
                    <select id="builder-stack" value={form.stack} onChange={event => set({stack: event.target.value})}>
                      {STACK_OPTIONS.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
                    </select>
                  </div>
                </div>
                <fieldset className="sdlc-builder-autonomy">
                  <legend>چقدر خودکار باشد؟</legend>
                  {AUTONOMY_OPTIONS.map(option => (
                    <label key={option.value} className={form.autonomy === option.value ? 'selected' : ''}>
                      <input type="radio" name="builder-autonomy" value={option.value} checked={form.autonomy === option.value} onChange={() => set({autonomy: option.value})} />
                      <span><b>{option.label}</b><small>{option.hint}</small></span>
                    </label>
                  ))}
                </fieldset>
                <div className="sdlc-form-group">
                  <label htmlFor="builder-dir">پوشهٔ والد <small>(اختیاری؛ پیش‌فرض ~/taskloom-projects)</small></label>
                  <input id="builder-dir" type="text" dir="ltr" value={form.baseDir} onChange={event => set({baseDir: event.target.value})} placeholder="D:\projects" />
                </div>
                <label className="sdlc-builder-check">
                  <input type="checkbox" checked={form.useAi} onChange={event => set({useAi: event.target.checked})} />
                  <span>غنی‌سازی با هوش مصنوعی (شرح، نیازمندی‌ها، معماری و راهنمای هر مرحله). اگر در دسترس نباشد، قالب‌های آماده استفاده می‌شوند.</span>
                </label>

                {error && <p className="sdlc-builder-error" role="alert"><AlertTriangle size={14} /> {error}</p>}

                {plan && (
                  <section className="sdlc-builder-plan" aria-label="پیش‌نمایش">
                    <h4><Eye size={14} /> پیش‌نمایش: <code>{plan.id}</code></h4>
                    <p dir="ltr" className="sdlc-builder-root"><FolderTree size={14} /> {plan.root}</p>
                    {plan.problems.map(item => <p key={item} className="sdlc-builder-error" role="alert"><AlertTriangle size={14} /> {item}</p>)}
                    {plan.stages.map(stage => (
                      <details key={stage.stage}>
                        <summary>{stageSummary(stage)}</summary>
                        <p dir="ltr"><code>{stage.folder}</code></p>
                        <p dir="ltr" className="sdlc-builder-files">{stage.files.join('  ·  ')}</p>
                        <pre dir="ltr" className="sdlc-builder-prompt">{stage.system_prompt}</pre>
                      </details>
                    ))}
                  </section>
                )}

                <div className="sdlc-form-actions">
                  <button type="button" className="sdlc-btn sdlc-btn-secondary" disabled={!!problem || !!busy} onClick={() => run('preview')}>
                    <Eye size={14} /> {busy === 'preview' ? 'در حال محاسبه…' : 'پیش‌نمایش'}
                  </button>
                  <button type="button" className="sdlc-btn sdlc-btn-primary" disabled={!!problem || !!busy || (plan?.problems.length > 0)} onClick={() => run('build')}>
                    <Rocket size={14} /> {busy === 'build' ? 'در حال ساخت پروژه…' : 'ساخت پروژه'}
                  </button>
                </div>
              </div>
            )}
          </div>
        </ModalShell>
      )}
    </>
  );
}
