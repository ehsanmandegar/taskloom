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

test('loads Taskloom defaults while keeping the project path editable', () => {
  const source = readFileSync(new URL('./main.jsx', import.meta.url), 'utf8');

  assert.match(source, /fetch\(`\$\{API\}\/api\/defaults`\)/);
  assert.match(source, /setForm\(current=>current\.project_path\?current:\{\.\.\.current,\.\.\.loaded\}\)/);
  assert.match(source, /name="project_path" value=\{form\.project_path\} onChange=\{update\}/);
  assert.match(source, /current\.guide_paths===startupDefaults\.guide_paths\?'':current\.guide_paths/);
  assert.match(source, /mcp_server_name:current\.mcp_server_name===startupDefaults\.mcp_server_name\?'':current\.mcp_server_name/);
  assert.match(source, /با تغییر مسیر، راهنما، تست و MCP پیش‌فرض آن پروژه پاک می‌شوند/);
});

test('keeps the project profile controls aligned in one row', () => {
  const source = readFileSync(new URL('./main.jsx', import.meta.url), 'utf8');
  const styles = readFileSync(new URL('./styles.css', import.meta.url), 'utf8');

  assert.match(source, /aria-label="حذف پروفایل"/);
  assert.match(source, /<Trash2 size=\{16\}\/\><span>حذف<\/span>/);
  assert.match(styles, /\.profile-picker\{display:grid;grid-template-columns:minmax\(0,1fr\) auto auto/);
  assert.match(styles, /\.form \.profile-picker select\{width:auto;min-width:0;height:38px;margin:0/);
});

test('configures and displays project MCP preflight status', () => {
  const source = readFileSync(new URL('./main.jsx', import.meta.url), 'utf8');
  const styles = readFileSync(new URL('./styles.css', import.meta.url), 'utf8');

  assert.match(source, /name="mcp_server_name" value=\{form\.mcp_server_name\}/);
  assert.match(source, /name="mcp_failure_mode" value=\{form\.mcp_failure_mode\}/);
  assert.match(source, /\['passed','failed','blocked','stopped'\]\.includes\(task\.status\)/);
  assert.match(source, /\['failed','blocked'\]\.includes\(task\.status\)/);
  assert.match(source, /MCP \{task\.mcp_server_name\}: \{task\.mcp_message\|\|task\.mcp_status\}/);
  assert.match(styles, /\.mcp-state\.blocked/);
});

test('offers a follow-up chat that resumes the task session', () => {
  const source = readFileSync(new URL('./main.jsx', import.meta.url), 'utf8');

  assert.match(source, /\/api\/tasks\/\$\{task\.id\}\/messages/);
  assert.match(source, /task\.codex_thread_id/);
  assert.match(source, /گفت‌وگو با Codex/);
});

test('can request an automatic commit message from the task Codex session', () => {
  const source = readFileSync(new URL('./main.jsx', import.meta.url), 'utf8');
  const styles = readFileSync(new URL('./styles.css', import.meta.url), 'utf8');

  assert.match(source, /\/api\/tasks\/\$\{task\.id\}\/commit-message/);
  assert.match(source, /Generate commit message with Codex/);
  assert.match(source, /onClick=\{generateCommitMessage\}/);
  assert.match(source, /<Sparkles size=\{14\}\/>AutoGenerate/);
  assert.match(source, /<GitCommit size=\{16\}\/>commit/);
  assert.match(source, /<Upload size=\{16\}\/>push/);
  assert.match(styles, /\.delivery \.suggest-commit\{height:32px;padding:0 9px;font-size:10px/);
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

test('streams Codex activity into changes and the in-progress reply', () => {
  const source = readFileSync(new URL('./main.jsx', import.meta.url), 'utf8');
  const styles = readFileSync(new URL('./styles.css', import.meta.url), 'utf8');

  assert.match(source, /new EventSource\(`\$\{API\}\/api\/tasks\/\$\{task\.id\}\/events`\)/);
  assert.match(source, /codexTyping&&task\.live_output\?task\.live_output/);
  assert.match(source, /task\.live_response/);
  assert.match(source, /className="chat-message assistant live-response"/);
  assert.match(styles, /\.live-console/);
  assert.match(styles, /@keyframes live-cursor/);
});

test('renders mixed Persian and English output with per-line direction', () => {
  const source = readFileSync(new URL('./main.jsx', import.meta.url), 'utf8');
  const styles = readFileSync(new URL('./styles.css', import.meta.url), 'utf8');

  assert.match(source, /function DirectionalOutput\(\{text\}\)/);
  assert.match(source, /className="output-line" dir="auto"/);
  assert.match(source, /<DirectionalOutput text=\{outputText\}\/\>/);
  assert.match(source, /<p dir="auto">\{message\.content\}<\/p>/);
  assert.match(styles, /\.output-line\{display:block;min-height:1\.7em;unicode-bidi:plaintext;text-align:start\}/);
});

test('can stop an active Codex run and resume its conversation', () => {
  const source = readFileSync(new URL('./main.jsx', import.meta.url), 'utf8');
  const styles = readFileSync(new URL('./styles.css', import.meta.url), 'utf8');

  assert.match(source, /\/api\/tasks\/\$\{task\.id\}\/stop/);
  assert.match(source, /running&&task\.codex_thread_id&&<button className="stop-run"/);
  assert.match(source, /onClick=\{stopTask\}/);
  assert.match(source, /> توقف<\/button>/);
  assert.match(source, /task\?\.status==='stopped'&&task\.live_response/);
  assert.match(source, /پاسخ Codex متوقف شد/);
  assert.match(styles, /\.stop-run\{/);
  assert.match(styles, /\.status mark\.stopped/);
});
