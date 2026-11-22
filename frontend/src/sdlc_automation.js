// Pure helpers of the SDLC automation UI (no React, so `node --test` can cover them).

export const RISK_LABELS = {low: 'کم', medium: 'متوسط', high: 'زیاد'};
export const riskTone = level => ({low: 'green', medium: 'amber', high: 'red'})[level] || 'gray';

export const EVENT_LABELS = {
  created: {label: 'ایجاد', tone: 'gray'},
  stage_started: {label: 'شروع مرحله', tone: 'blue'},
  stage_completed: {label: 'پایان مرحله', tone: 'green'},
  stage_failed: {label: 'شکست مرحله', tone: 'red'},
  auto_retry: {label: 'تلاش مجدد خودکار', tone: 'amber'},
  escalated: {label: 'ارجاع به انسان', tone: 'orange'},
  human_response: {label: 'نظر/پاسخ انسان', tone: 'violet'},
  all_stages_completed: {label: 'پایان همهٔ مراحل', tone: 'green'},
  auto_approved: {label: 'تأیید خودکار', tone: 'jade'},
  approved: {label: 'تأیید انسان', tone: 'violet'},
  merged: {label: 'ادغام در develop', tone: 'green'},
};

// Statuses in which a human may write "this has a problem" and send the task back to the analyst: never while a
// stage is running, and never once the work is merged into develop (the server enforces the same rules).
export const SEND_BACK_STATUSES = ['human_review', 'analysis_approved', 'human_qa', 'pending_approval', 'done', 'failed'];

export function canSendBack(task) {
  if (!task || !SEND_BACK_STATUSES.includes(task.sdlc_status)) return false;
  return !Object.values(task.repos || {}).some(repo => repo.integration?.merged_into_develop);
}

export function formatDuration(seconds) {
  if (seconds == null || Number.isNaN(seconds)) return '—';
  const total = Math.round(seconds);
  if (total < 60) return `${total} ثانیه`;
  if (total < 3600) return `${Math.floor(total / 60)} دقیقه${total % 60 ? ` و ${total % 60} ثانیه` : ''}`;
  const hours = Math.floor(total / 3600), minutes = Math.floor((total % 3600) / 60);
  return `${hours} ساعت${minutes ? ` و ${minutes} دقیقه` : ''}`;
}

export const formatPercent = ratio => (ratio == null ? '—' : `${Math.round(ratio * 100)}٪`);

// Settings a project gets when the server did not send them (older project files).
export const AUTONOMY_DEFAULTS = {
  auto_analysis_approval: false, auto_final_approval: false, auto_approval_max_risk: 'low',
  auto_retry_failed_stages: 0, auto_release: false, auto_release_min_tasks: 2,
};

export const withAutonomyDefaults = workflow => ({...AUTONOMY_DEFAULTS, ...(workflow || {})});

// A short human summary of how automatic a workflow is (shown in the project review step).
export function autonomySummary(workflow) {
  const flow = withAutonomyDefaults(workflow);
  const parts = [];
  if (flow.auto_analysis_approval) parts.push('تحلیل');
  if (flow.auto_final_approval) parts.push(`تأیید نهایی (تا ریسک ${RISK_LABELS[flow.auto_approval_max_risk] || flow.auto_approval_max_risk})`);
  if (flow.auto_retry_failed_stages > 0) parts.push(`${flow.auto_retry_failed_stages} تلاش مجدد`);
  if (flow.auto_release) parts.push(`نسخه از ${flow.auto_release_min_tasks} تسک`);
  return parts.length ? parts.join('، ') : 'هیچ — همهٔ تصمیم‌ها با انسان';
}
