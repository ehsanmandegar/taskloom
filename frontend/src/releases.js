// Pure helpers for the Release Management page (kept free of React so `npm test` can cover them).

export const VERSION_PATTERN = /^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$/;

export const isValidVersion = value => VERSION_PATTERN.test((value || '').trim());

export const RELEASE_STATUS = {
  draft: {label: 'پیش‌نویس', tone: 'gray'},
  preparing: {label: 'در حال آماده‌سازی', tone: 'blue', busy: true},
  testing: {label: 'در حال آزمون', tone: 'blue', busy: true},
  waiting_approval: {label: 'منتظر تأیید', tone: 'amber'},
  approved: {label: 'تأییدشده', tone: 'blue', busy: true},
  merging: {label: 'در حال ادغام در sandbox', tone: 'blue', busy: true},
  released: {label: 'منتشر شد', tone: 'green'},
  failed: {label: 'ناموفق', tone: 'red'},
  cancelled: {label: 'لغو شد', tone: 'gray'},
};

export const releaseStatusLabel = status => (RELEASE_STATUS[status] || {label: status || 'نامشخص'}).label;
export const releaseStatusTone = status => (RELEASE_STATUS[status] || {tone: 'gray'}).tone;
export const isReleaseBusy = status => !!(RELEASE_STATUS[status] || {}).busy;
export const hasBusyRelease = releases => (releases || []).some(release => isReleaseBusy(release.status));

// Which actions the server will accept in each state (the server re-checks every one of them).
export const releaseActions = release => ({
  start: release.status === 'draft',
  approve: release.status === 'waiting_approval',
  retry: release.status === 'failed',
  rebuild: release.status === 'failed' || release.status === 'waiting_approval',
  cancel: ['draft', 'waiting_approval', 'failed'].includes(release.status),
});

// Client-side refinement on top of the server-side filters (so typing in the search box feels instant).
export function filterTasks(rows, {q = '', workflow = '', status = '', eligibleOnly = false} = {}) {
  const needle = q.trim().toLowerCase();
  return (rows || []).filter(row =>
    (!workflow || row.workflow === workflow) &&
    (!status || row.status === status) &&
    (!eligibleOnly || row.eligible) &&
    (!needle || [row.task_id, row.title, row.branch].some(text => (text || '').toLowerCase().includes(needle))));
}

// Selecting a task also keeps selection valid when the list changes (ineligible rows can never stay selected).
export function pruneSelection(selected, rows) {
  const selectable = new Set((rows || []).filter(row => row.eligible).map(row => row.task_id));
  return (selected || []).filter(id => selectable.has(id));
}

export function toggleSelection(selected, taskId) {
  return selected.includes(taskId) ? selected.filter(id => id !== taskId) : [...selected, taskId];
}

export function adminHeaders(token, user) {
  const headers = {'Content-Type': 'application/json'};
  if ((token || '').trim()) headers['X-Taskloom-Admin-Token'] = token.trim();
  if ((user || '').trim()) headers['X-Taskloom-User'] = user.trim();
  return headers;
}

// Why the "create" button is disabled (empty string = it can be pressed).
export function createBlocker({repositoryId, version, selected}) {
  if (!repositoryId) return 'یک مخزن انتخاب کنید';
  if (!isValidVersion(version)) return 'شمارهٔ نسخه باید مثل 1.0.1 باشد';
  if (!selected.length) return 'حداقل یک تسک انتخاب کنید';
  return '';
}

export const shortSha = sha => (sha || '').slice(0, 10);

// Normalises what the task detail panels know about a task's Git state, for both workflows.
export function gitIntegrationSummary(integration) {
  const info = integration || {};
  if (info.merged_into_develop) return {tone: 'green', label: 'ادغام‌شده در develop'};
  if (info.status === 'conflict') return {tone: 'red', label: 'تداخل در ادغام'};
  if (info.status === 'failed') return {tone: 'red', label: 'ادغام ناموفق'};
  if (info.status === 'merging') return {tone: 'blue', label: 'در حال ادغام'};
  return {tone: 'gray', label: 'هنوز در develop نیست'};
}

// The administrator identity the Release Management page keeps in this browser (also used by the approval buttons).
export function storedAdminHeaders() {
  try {
    return adminHeaders(localStorage.getItem('taskloom.adminToken'), localStorage.getItem('taskloom.adminUser'));
  } catch {
    return adminHeaders('', '');
  }
}
