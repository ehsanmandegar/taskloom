import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import {
  AUTONOMY_DEFAULTS, EVENT_LABELS, autonomySummary, canSendBack, formatDuration, formatPercent, riskTone, withAutonomyDefaults,
} from './sdlc_automation.js';

test('a task can be sent back to analysis unless it is running or already merged into develop', () => {
  assert.equal(canSendBack(null), false);
  for (const status of ['human_review', 'pending_approval', 'done', 'failed']) assert.equal(canSendBack({sdlc_status: status}), true, status);
  for (const status of ['analyzing', 'backend_running', 'testing', 'revision', 'created']) assert.equal(canSendBack({sdlc_status: status}), false, status);
  const merged = {sdlc_status: 'done', repos: {r: {integration: {merged_into_develop: true}}}};
  assert.equal(canSendBack(merged), false);
  assert.equal(canSendBack({sdlc_status: 'done', repos: {r: {integration: {merged_into_develop: false}}}}), true);
});

test('the task dialog posts the opinion to the send-back endpoint from the Status section', () => {
  const source = readFileSync(new URL('./sdlc_dashboard.jsx', import.meta.url), 'utf8');
  assert.match(source, /\/send-back/);
  assert.match(source, /ارجاع به تحلیل/);
  assert.match(source, /canSendBack\(selectedTask\)/);
});

test('durations read naturally', () => {
  assert.equal(formatDuration(null), '—');
  assert.equal(formatDuration(42.4), '42 ثانیه');
  assert.equal(formatDuration(125), '2 دقیقه و 5 ثانیه');
  assert.equal(formatDuration(180), '3 دقیقه');
  assert.equal(formatDuration(3720), '1 ساعت و 2 دقیقه');
});

test('percentages and risk tones', () => {
  assert.equal(formatPercent(null), '—');
  assert.equal(formatPercent(0.667), '67٪');
  assert.equal(riskTone('low'), 'green');
  assert.equal(riskTone('high'), 'red');
  assert.equal(riskTone('?'), 'gray');
});

test('every audit-trail event kind the backend records has a label', () => {
  const policy = readFileSync(new URL('../../backend/app/services.py', import.meta.url), 'utf8')
    + readFileSync(new URL('../../backend/app/main.py', import.meta.url), 'utf8');
  const kinds = new Set([...policy.matchAll(/record_event\([^,]+,\s*"([a-z_]+)"/g)].map(match => match[1]));
  assert.ok(kinds.size >= 8, `found ${[...kinds]}`);
  for (const kind of kinds) assert.ok(EVENT_LABELS[kind], `missing label for ${kind}`);
});

test('older projects get safe autonomy defaults (a human decides everything)', () => {
  const flow = withAutonomyDefaults({require_final_human_approval: true});
  assert.equal(flow.require_final_human_approval, true);
  assert.deepEqual({...flow, require_final_human_approval: undefined}, {...AUTONOMY_DEFAULTS, require_final_human_approval: undefined});
  assert.equal(autonomySummary(null), 'هیچ — همهٔ تصمیم‌ها با انسان');
  assert.match(autonomySummary({auto_final_approval: true, auto_approval_max_risk: 'medium', auto_retry_failed_stages: 2}), /تأیید نهایی.*متوسط.*2 تلاش/);
});
