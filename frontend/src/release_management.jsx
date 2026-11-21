import React, {useCallback, useEffect, useMemo, useState} from 'react';
import {AlertTriangle, CheckCircle2, GitBranch, GitMerge, Package, RefreshCw, Search, XCircle} from 'lucide-react';
import './release_management.css';
import {confirmDialog} from './ui.jsx';
import {
  adminHeaders, createBlocker, filterTasks, gitIntegrationSummary, hasBusyRelease, pruneSelection, releaseActions,
  releaseStatusLabel, releaseStatusTone, shortSha, toggleSelection,
} from './releases.js';

const API = import.meta.env.VITE_API_URL || '';
const TOKEN_KEY = 'taskloom.adminToken';
const USER_KEY = 'taskloom.adminUser';

function remember(key, value) { try { localStorage.setItem(key, value); } catch { /* private mode: keep going */ } }
function recall(key) { try { return localStorage.getItem(key) || ''; } catch { return ''; } }

async function call(path, {method = 'GET', body, token, user} = {}) {
  const response = await fetch(`${API}${path}`, {
    method,
    headers: adminHeaders(token, user),
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof data.detail === 'string' ? data.detail : Array.isArray(data.detail) ? data.detail.map(item => item.msg).join('؛ ') : '';
    throw new Error(detail || `خطای سرور (${response.status})`);
  }
  return data;
}

const formatDate = value => (value ? new Date(value).toLocaleString('fa-IR') : '—');
const Badge = ({tone, children}) => <span className={`rm-badge rm-${tone}`}>{children}</span>;
const Sha = ({value}) => <code className="rm-sha" dir="ltr" title={value}>{shortSha(value) || '—'}</code>;

/** Git facts of one task in one repository, shown in task details (DWS and SDLC share it). */
export function GitPanel({taskId, repoPath = '', branch = '', baseBranch = 'sandbox', commitSha = '', integration}) {
  const [releases, setReleases] = useState([]);
  useEffect(() => {
    let cancelled = false;
    if (!taskId) return undefined;
    call(`/api/releases/by-task/${encodeURIComponent(taskId)}`).then(items => { if (!cancelled) setReleases(items); }).catch(() => {});
    return () => { cancelled = true; };
  }, [taskId, integration?.merge_commit_sha, integration?.status]);
  const summary = gitIntegrationSummary(integration);
  const latest = integration?.merge_commit_sha || '';
  return (
    <section className="rm-git-panel" aria-label="وضعیت Git تسک">
      <h4><GitBranch size={14} /> Git <Badge tone={summary.tone}>{summary.label}</Badge></h4>
      <dl>
        <dt>شناسهٔ تسک</dt><dd dir="ltr">{taskId}</dd>
        <dt>مخزن</dt><dd dir="ltr">{repoPath || '—'}</dd>
        <dt>برنچ تسک</dt><dd dir="ltr"><code>{branch || '—'}</code></dd>
        <dt>برنچ مبنا</dt><dd dir="ltr"><code>{baseBranch}</code></dd>
        <dt>آخرین commit</dt><dd><Sha value={integration?.merged_branch_head || commitSha} /></dd>
        <dt>ادغام در develop</dt><dd>{integration?.merged_into_develop ? <>بله — commit ادغام <Sha value={latest} />، {formatDate(integration.merged_at)}</> : 'خیر'}</dd>
        <dt>نسخه‌های انتشار</dt>
        <dd>{releases.length ? releases.map(item => <Badge key={item.id} tone={releaseStatusTone(item.status)}>{item.version} · {releaseStatusLabel(item.status)}</Badge>) : '—'}</dd>
      </dl>
      {integration?.error && <p className="rm-error" role="alert">{integration.error}</p>}
      {integration?.conflicts?.length > 0 && <p className="rm-error">فایل‌های دارای تداخل: <code dir="ltr">{integration.conflicts.join(', ')}</code></p>}
    </section>
  );
}

export default function ReleaseManagement() {
  const [token, setToken] = useState(() => recall(TOKEN_KEY));
  const [user, setUser] = useState(() => recall(USER_KEY));
  const [repositories, setRepositories] = useState([]);
  const [repositoryId, setRepositoryId] = useState('');
  const [rows, setRows] = useState([]);
  const [releases, setReleases] = useState([]);
  const [openId, setOpenId] = useState('');
  const [version, setVersion] = useState('');
  const [selected, setSelected] = useState([]);
  const [reviewing, setReviewing] = useState(false);
  const [filters, setFilters] = useState({q: '', workflow: '', status: '', eligibleOnly: true});
  const [busy, setBusy] = useState('');
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  const credentials = {token, user};
  const refresh = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    try {
      const [repos, tasks, history] = await Promise.all([
        call('/api/releases/repositories'),
        call(`/api/releases/eligible-tasks${repositoryId ? `?repository_id=${encodeURIComponent(repositoryId)}` : ''}`),
        call('/api/releases'),
      ]);
      setRepositories(repos);
      setRows(tasks);
      setReleases(history);
      setSelected(current => pruneSelection(current, tasks));
      setRepositoryId(current => current || repos[0]?.id || '');
      if (!quiet) setError('');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [repositoryId]);

  useEffect(() => { refresh(); }, [refresh]);
  // While a release is being prepared, tested or merged the page follows it.
  useEffect(() => {
    if (!hasBusyRelease(releases)) return undefined;
    const timer = setInterval(() => refresh(true), 3000);
    return () => clearInterval(timer);
  }, [releases, refresh]);

  const visibleRows = useMemo(() => filterTasks(rows, filters), [rows, filters]);
  const workflows = useMemo(() => [...new Set(rows.map(row => row.workflow))].sort(), [rows]);
  const taskStatuses = useMemo(() => [...new Set(rows.map(row => row.status))].filter(Boolean).sort(), [rows]);
  const chosen = rows.filter(row => selected.includes(row.task_id));
  const blocker = createBlocker({repositoryId, version, selected});
  const open = releases.find(release => release.id === openId);

  async function act(label, path, body, success) {
    setBusy(label); setError(''); setNotice('');
    try {
      const result = await call(path, {method: 'POST', body, ...credentials});
      setNotice(success(result));
      await refresh(true);
      return result;
    } catch (err) {
      setError(err.message);
      return null;
    } finally {
      setBusy('');
    }
  }

  async function createRelease() {
    const created = await act('create', '/api/releases', {version: version.trim(), repository_id: repositoryId, task_ids: selected, start: true},
      result => `نسخهٔ ${result.version} ساخته شد و آماده‌سازی برنچ ${result.release_branch} شروع شد.`);
    if (created) { setOpenId(created.id); setSelected([]); setVersion(''); setReviewing(false); }
  }

  async function approve(release) {
    const ids = release.tasks.map(task => task.task_id).join('، ');
    if (!await confirmDialog(`تأیید نهایی نسخهٔ ${release.version}؟\nبا تأیید، برنچ ${release.release_branch} (شامل ${ids}) در ${release.target_branch} ادغام می‌شود.`)) return;
    act('approve', `/api/releases/${release.id}/approve`, null, () => `نسخهٔ ${release.version} تأیید شد؛ ادغام در ${release.target_branch} در حال انجام است.`);
  }

  const saveToken = value => { setToken(value); remember(TOKEN_KEY, value); };
  const saveUser = value => { setUser(value); remember(USER_KEY, value); };

  return (
    <main className="dashboard-page rm" aria-label="مدیریت نسخه">
      <div className="dashboard-heading">
        <div><span className="dashboard-kicker">TASKLOOM / RELEASES</span><h1>مدیریت نسخه</h1>
          <p>تسک‌های تأییدشده را در یک نسخه ترکیب کنید: ساخت برنچ release از sandbox، آزمون، تأیید انسانی و ادغام در sandbox.</p></div>
        <button type="button" className="dashboard-refresh" onClick={() => refresh()} disabled={loading}><RefreshCw size={16} className={loading ? 'spin' : ''} />{loading ? 'در حال دریافت…' : 'به‌روزرسانی'}</button>
      </div>

      {error && <p className="dashboard-error" role="alert">{error}</p>}
      {notice && <p className="rm-notice" role="status">{notice}</p>}

      <details className="rm-card rm-auth">
        <summary>هویت مدیر</summary>
        <div className="rm-form-row">
          <label>نام شما (ثبت در تاریخچه)<input value={user} onChange={event => saveUser(event.target.value)} placeholder="admin" autoComplete="off" /></label>
          <label>توکن مدیر <small>فقط اگر سرور با TASKLOOM_ADMIN_TOKEN اجرا شده باشد</small><input type="password" dir="ltr" value={token} onChange={event => saveToken(event.target.value)} autoComplete="off" /></label>
        </div>
      </details>

      <section className="rm-card" aria-label="ساخت نسخه">
        <div className="rm-card-title"><Package size={17} /><h2>ساخت نسخهٔ جدید</h2></div>
        <div className="rm-form-row">
          <label>مخزن
            <select value={repositoryId} onChange={event => { setRepositoryId(event.target.value); setSelected([]); }}>
              {repositories.length === 0 && <option value="">مخزنی با تسک ادغام‌شده در develop نیست</option>}
              {repositories.map(repo => <option key={repo.id} value={repo.id}>{repo.name} ({repo.tasks})</option>)}
            </select>
          </label>
          <label>شمارهٔ نسخه<input dir="ltr" value={version} onChange={event => setVersion(event.target.value)} placeholder="1.0.1" aria-invalid={!!version && !!createBlocker({repositoryId: 'x', version, selected: ['x']})} /></label>
        </div>

        <div className="rm-filters" role="search">
          <label className="rm-search"><Search size={14} /><input value={filters.q} onChange={event => setFilters({...filters, q: event.target.value})} placeholder="جستجوی شناسه یا عنوان تسک" aria-label="جستجوی تسک" /></label>
          <select aria-label="گردش کار" value={filters.workflow} onChange={event => setFilters({...filters, workflow: event.target.value})}>
            <option value="">همهٔ گردش‌کارها</option>{workflows.map(name => <option key={name} value={name}>{name}</option>)}
          </select>
          <select aria-label="وضعیت تسک" value={filters.status} onChange={event => setFilters({...filters, status: event.target.value})}>
            <option value="">همهٔ وضعیت‌ها</option>{taskStatuses.map(name => <option key={name} value={name}>{name}</option>)}
          </select>
          <label className="rm-check"><input type="checkbox" checked={filters.eligibleOnly} onChange={event => setFilters({...filters, eligibleOnly: event.target.checked})} />فقط قابل انتخاب</label>
        </div>

        <div className="rm-table-wrap">
          <table className="rm-table">
            <thead><tr><th></th><th>شناسه</th><th>گردش کار</th><th>عنوان</th><th>وضعیت</th><th>تغییرات منتشرنشده</th><th>نسخه‌ها</th></tr></thead>
            <tbody>
              {visibleRows.map(row => (
                <tr key={`${row.repository_id}:${row.task_id}`} className={row.eligible ? '' : 'rm-disabled'}>
                  <td><input type="checkbox" aria-label={`انتخاب ${row.task_id}`} checked={selected.includes(row.task_id)} disabled={!row.eligible} onChange={() => setSelected(toggleSelection(selected, row.task_id))} /></td>
                  <td dir="ltr"><code>{row.task_id}</code></td>
                  <td>{row.workflow}</td>
                  <td dir="auto">{row.title}</td>
                  <td>{row.status}</td>
                  <td>{row.eligible ? `${row.pending_merges.length} ادغام` : <span title={row.reason}>{row.reason || '—'}</span>}</td>
                  <td>{row.releases.map(item => <Badge key={item.id} tone={releaseStatusTone(item.status)}>{item.version}</Badge>)}</td>
                </tr>
              ))}
              {visibleRows.length === 0 && <tr><td colSpan={7} className="rm-empty">{rows.length ? 'تسکی با این فیلترها پیدا نشد.' : 'هنوز تسکی با تأیید نهایی در develop ادغام نشده است.'}</td></tr>}
            </tbody>
          </table>
        </div>

        <div className="rm-actions">
          <span>{selected.length} تسک انتخاب شد</span>
          <button type="button" className="rm-btn" disabled={!!blocker || !!busy} title={blocker} onClick={() => setReviewing(true)}>بازبینی انتخاب‌ها</button>
        </div>
        {blocker && <p className="rm-hint">{blocker}</p>}

        {reviewing && !blocker && (
          <div className="rm-review" role="region" aria-label="بازبینی نسخه">
            <h3>بازبینی پیش از شروع</h3>
            <p>نسخهٔ <b dir="ltr">{version.trim()}</b> از برنچ <code>sandbox</code> ساخته می‌شود و فقط تغییرات این تسک‌ها از <code>develop</code> در آن قرار می‌گیرد:</p>
            <ul>{chosen.map(row => <li key={row.task_id}><code dir="ltr">{row.task_id}</code> — {row.title} ({row.pending_merges.length} ادغام)</li>)}</ul>
            <p>سپس آزمون‌های پروژه اجرا می‌شوند و نسخه منتظر تأیید شما می‌ماند؛ تا آن زمان sandbox دست‌نخورده است.</p>
            <div className="rm-actions">
              <button type="button" className="rm-btn rm-primary" disabled={!!busy} onClick={createRelease}>{busy === 'create' ? 'در حال شروع…' : 'شروع ساخت نسخه'}</button>
              <button type="button" className="rm-btn" disabled={!!busy} onClick={() => setReviewing(false)}>بازگشت</button>
            </div>
          </div>
        )}
      </section>

      <section className="rm-card" aria-label="تاریخچهٔ نسخه‌ها">
        <div className="rm-card-title"><GitMerge size={17} /><h2>تاریخچهٔ نسخه‌ها</h2></div>
        <div className="rm-table-wrap">
          <table className="rm-table">
            <thead><tr><th>نسخه</th><th>وضعیت</th><th>تسک‌ها</th><th>سازنده</th><th>ایجاد</th><th>commit ادغام</th></tr></thead>
            <tbody>
              {releases.map(release => (
                <tr key={release.id} className={`rm-row ${release.id === openId ? 'rm-open' : ''}`} onClick={() => setOpenId(release.id === openId ? '' : release.id)}>
                  <td dir="ltr"><button type="button" className="rm-link" aria-expanded={release.id === openId}>{release.version}</button></td>
                  <td><Badge tone={releaseStatusTone(release.status)}>{releaseStatusLabel(release.status)}</Badge></td>
                  <td dir="ltr">{release.tasks.map(task => task.task_id).join(', ')}</td>
                  <td>{release.created_by}</td>
                  <td>{formatDate(release.created_at)}</td>
                  <td><Sha value={release.merge_commit_sha} /></td>
                </tr>
              ))}
              {releases.length === 0 && <tr><td colSpan={6} className="rm-empty">هنوز نسخه‌ای ساخته نشده است.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>

      {open && <ReleaseDetails release={open} busy={busy} onApprove={() => approve(open)}
        onAct={(label, action, success) => act(label, `/api/releases/${open.id}/${action}`, null, success)} />}
    </main>
  );
}

function ReleaseDetails({release, busy, onApprove, onAct}) {
  const actions = releaseActions(release);
  return (
    <section className="rm-card rm-details" aria-label={`جزئیات نسخهٔ ${release.version}`}>
      <div className="rm-card-title">
        <Package size={17} /><h2 dir="ltr">{release.version}</h2><Badge tone={releaseStatusTone(release.status)}>{releaseStatusLabel(release.status)}</Badge>
        <div className="rm-title-actions">
          {actions.approve && <button type="button" className="rm-btn rm-primary" disabled={!!busy} onClick={onApprove}><CheckCircle2 size={14} /> تأیید و ادغام در {release.target_branch}</button>}
          {actions.start && <button type="button" className="rm-btn" disabled={!!busy} onClick={() => onAct('start', 'start', () => 'آماده‌سازی نسخه شروع شد.')}>شروع</button>}
          {actions.retry && <button type="button" className="rm-btn" disabled={!!busy} onClick={() => onAct('retry', 'retry', () => 'تلاش مجدد شروع شد.')}><RefreshCw size={14} /> تلاش مجدد</button>}
          {actions.rebuild && <button type="button" className="rm-btn" disabled={!!busy} onClick={() => onAct('rebuild', 'rebuild', () => 'بازسازی برنچ از sandbox فعلی شروع شد.')}>بازسازی از sandbox</button>}
          {actions.cancel && <button type="button" className="rm-btn rm-danger" disabled={!!busy} onClick={async () => (await confirmDialog(`نسخهٔ ${release.version} لغو شود؟ برنچ‌ها حذف نمی‌شوند.`, {danger: true, confirmText: 'لغو نسخه'})) && onAct('cancel', 'cancel', () => 'نسخه لغو شد.')}><XCircle size={14} /> لغو</button>}
        </div>
      </div>

      {release.error && <p className="rm-error" role="alert"><AlertTriangle size={14} /> {release.error}{release.failed_phase ? ` (مرحله: ${release.failed_phase})` : ''}</p>}
      {release.validation_warning && <p className="rm-warning"><AlertTriangle size={14} /> {release.validation_warning}</p>}
      {release.status === 'waiting_approval' && <p className="rm-notice">آزمون‌ها پایان یافتند. تا پیش از تأیید شما چیزی در <code>{release.target_branch}</code> ادغام نمی‌شود.</p>}

      <dl className="rm-meta">
        <dt>مخزن</dt><dd dir="ltr">{release.repository_name || release.repository_path}</dd>
        <dt>برنچ‌ها</dt><dd dir="ltr"><code>{release.source_branch}</code> → <code>{release.release_branch}</code> → <code>{release.target_branch}</code></dd>
        <dt>پایه (sandbox)</dt><dd><Sha value={release.base_sha} /></dd>
        <dt>commit نهایی release</dt><dd><Sha value={release.final_commit_sha} /></dd>
        <dt>commit ادغام در sandbox</dt><dd><Sha value={release.merge_commit_sha} /></dd>
        <dt>سازنده</dt><dd>{release.created_by} — {formatDate(release.created_at)}</dd>
        <dt>تأییدکننده</dt><dd>{release.approved_by ? `${release.approved_by} — ${formatDate(release.approved_at)}` : '—'}</dd>
        <dt>منتشرشده</dt><dd>{formatDate(release.released_at)}</dd>
      </dl>

      <h3>تسک‌های این نسخه</h3>
      <ul className="rm-task-list">
        {release.tasks.map(task => (
          <li key={task.task_id}><code dir="ltr">{task.task_id}</code> <small>{task.workflow}</small> {task.title}
            {task.picks.length > 0 && <small dir="ltr"> — {task.picks.reduce((sum, pick) => sum + pick.files.length, 0)} file(s)</small>}</li>
        ))}
      </ul>

      <h3>نتیجهٔ اعتبارسنجی</h3>
      {release.validation.length === 0 ? <p className="rm-hint">{release.status === 'testing' ? 'آزمون‌ها در حال اجرا هستند…' : 'هنوز نتیجه‌ای ثبت نشده است.'}</p> : (
        <ul className="rm-validation">
          {release.validation.map((step, index) => (
            <li key={index} className={step.passed ? 'rm-pass' : 'rm-fail'}>
              <span>{step.passed ? <CheckCircle2 size={14} /> : <XCircle size={14} />} <code dir="ltr">{step.command}</code>
                <small> {step.kind === 'setup' ? 'setup' : 'test'} · exit {step.exit_code ?? '—'} · {step.duration_seconds}s</small></span>
              {step.output && <details><summary>خروجی</summary><pre dir="ltr">{step.output}</pre></details>}
            </li>
          ))}
        </ul>
      )}

      {release.logs.length > 0 && <details className="rm-logs"><summary>گزارش عملیات Git ({release.logs.length})</summary><pre dir="ltr">{release.logs.join('\n')}</pre></details>}
    </section>
  );
}
