import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';

test('does not show the removed delivery heading', () => {
  const source = readFileSync(new URL('./main.jsx', import.meta.url), 'utf8');

  assert.doesNotMatch(source, /از درخواست تا برنچ آماده‌ی تحویل/);
});

test('offers merge request creation only after push and links the result', () => {
  const source = readFileSync(new URL('./main.jsx', import.meta.url), 'utf8');

  assert.match(source, /action\('merge-request'\)/);
  assert.match(source, /disabled=\{!task\.pushed\|\|!!task\.merge_request_url\|\|busy\}/);
  assert.match(source, /href=\{task\.merge_request_url\}/);
});

test('restores a saved Codex session and lets the user switch recent conversations', () => {
  const source = readFileSync(new URL('./main.jsx', import.meta.url), 'utf8');

  assert.match(source, /taskloom-active-session/);
  assert.match(source, /fetch\(`\$\{API\}\/api\/tasks`\)/);
  assert.match(source, /session-picker/);
});

test('turns API validation details into readable form errors', () => {
  const source = readFileSync(new URL('./main.jsx', import.meta.url), 'utf8');

  assert.match(source, /const apiError=/);
  assert.match(source, /apiError\(d\.detail,'شروع تسک ناموفق بود'\)/);
});

test('offers a follow-up chat that resumes the task session', () => {
  const source = readFileSync(new URL('./main.jsx', import.meta.url), 'utf8');

  assert.match(source, /\/api\/tasks\/\$\{task\.id\}\/messages/);
  assert.match(source, /task\.codex_thread_id/);
  assert.match(source, /گفت‌وگو با Codex/);
});

test('can request an automatic commit message from the task Codex session', () => {
  const source = readFileSync(new URL('./main.jsx', import.meta.url), 'utf8');

  assert.match(source, /\/api\/tasks\/\$\{task\.id\}\/commit-message/);
  assert.match(source, /Generate commit message with Codex/);
  assert.match(source, /onClick=\{generateCommitMessage\}/);
});

test('sends chat messages with Enter while preserving Shift+Enter for a new line', () => {
  const source = readFileSync(new URL('./main.jsx', import.meta.url), 'utf8');

  assert.match(source, /function submitChatOnEnter\(e\)\{if\(e\.key!==\'Enter\'\|\|e\.shiftKey\|\|e\.nativeEvent\.isComposing\)return;e\.preventDefault\(\);e\.currentTarget\.form\?\.requestSubmit\(\)\}/);
  assert.match(source, /onKeyDown=\{submitChatOnEnter\}/);
});

test('distinguishes Codex replies and shows a typing indicator while Codex responds', () => {
  const source = readFileSync(new URL('./main.jsx', import.meta.url), 'utf8');
  const styles = readFileSync(new URL('./styles.css', import.meta.url), 'utf8');

  assert.match(source, /codexTyping=task&&\['queued','running'\]\.includes\(task\.status\)/);
  assert.match(source, /chat-typing/);
  assert.match(source, /Codex در حال پاسخ است/);
  assert.match(styles, /\.chat-message\.assistant\{[^}]*background:#eef1fb/);
  assert.match(styles, /@keyframes typing-dot/);
});
