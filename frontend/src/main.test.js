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
  assert.match(source, /base_branch:current\.base_branch===startupDefaults\.base_branch\?defaultBaseBranch\(value\):current\.base_branch/);
  assert.match(source, /برنچ مبنای پیش‌فرض همان پروژه تنظیم می‌شوند/);
});

test('lets each project profile choose its task base branch', () => {
  const source = readFileSync(new URL('./main.jsx', import.meta.url), 'utf8');

  assert.match(source, /base_branch:'main'/);
  assert.match(source, /defaultBaseBranch=.*?'sandbox':'main'/);
  assert.match(source, /base_branch:defaults\.base_branch\|\|'main'/);
  assert.match(source, /base_branch:profile\.base_branch\|\|defaultBaseBranch\(profile\.project_path\)/);
  assert.match(source, /base_branch:form\.base_branch\.trim\(\)/);
  assert.match(source, /name="base_branch" value=\{form\.base_branch\}/);
  assert.match(source, /برنچ مبنا/);
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

test('can opt into generating a commit message during automatic delivery', () => {
  const source = readFileSync(new URL('./main.jsx', import.meta.url), 'utf8');

  assert.match(source, /auto_generate_commit_message:false/);
  assert.match(source, /checked=\{form\.auto_generate_commit_message\}/);
  assert.match(source, /پیش از commit، پیام را با Codex خودکار تولید کن/);
  assert.match(source, /auto_generate_commit_message:form\.auto_generate_commit_message/);
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

test('copies individual user and Codex messages from the chat history', () => {
  const source = readFileSync(new URL('./main.jsx', import.meta.url), 'utf8');
  const styles = readFileSync(new URL('./styles.css', import.meta.url), 'utf8');

  assert.match(source, /function copyMessage\(content,key\)/);
  assert.match(source, /navigator\.clipboard\?\.writeText/);
  assert.match(source, /className="chat-copy"/);
  assert.match(source, /کپی پیام \$\{message\.role==='user'\?'شما':'Codex'\}/);
  assert.match(source, /copyMessage\(task\.live_response,`live-\$\{task\.id\}`\)/);
  assert.match(source, /aria-label="کپی پاسخ Codex"/);
  assert.match(styles, /\.chat-copy\{position:absolute/);
});

test('creates separately named sessions and lets the user rename them', () => {
  const source = readFileSync(new URL('./main.jsx', import.meta.url), 'utf8');
  const styles = readFileSync(new URL('./styles.css', import.meta.url), 'utf8');

  assert.match(source, /session_name:''/);
  assert.match(source, /function newSession\(\)/);
  assert.match(source, /function renameSession\(\)/);
  assert.match(source, /method:'PATCH'/);
  assert.match(source, /task_id=taskIdForBranch\(form\.task_id\)\|\|`session-\$\{Date\.now\(\)\.toString\(36\)\}`/);
  assert.match(source, /item\.session_name\|\|item\.task_id/);
  assert.match(source, /className="new-session"/);
  assert.match(styles, /\.session-controls\{display:grid;grid-template-columns:minmax\(0,1fr\) auto auto;align-items:center/);
});

test('scrolls chat history to the newest message and streamed reply', () => {
  const source = readFileSync(new URL('./main.jsx', import.meta.url), 'utf8');

  assert.match(source, /document\.querySelectorAll\('\.chat-history'\)/);
  assert.match(source, /history\.scrollTo\(\{top:history\.scrollHeight,behavior:'smooth'\}\)/);
  assert.match(source, /\[task\?\.id,task\?\.messages\?\.length,task\?\.live_response,task\?\.status\]/);
});

test('shows real Codex account status, usage windows, and available models', () => {
  const source = readFileSync(new URL('./main.jsx', import.meta.url), 'utf8');
  const styles = readFileSync(new URL('./styles.css', import.meta.url), 'utf8');

  assert.match(source, /\/api\/codex\/status/);
  assert.match(source, /function refreshCodexStatus/);
  assert.match(source, /codexRateLimits=Object\.values/);
  assert.match(source, /codexUsage\.slice\(-7\)/);
  assert.match(source, /className="codex-rate-limits"/);
  assert.match(styles, /\.codex-status-overview\{display:grid/);
});

test('keeps the Codex status section closed until the user opens it', () => {
  const source = readFileSync(new URL('./main.jsx', import.meta.url), 'utf8');
  const styles = readFileSync(new URL('./styles.css', import.meta.url), 'utf8');

  assert.match(source, /<details className="codex-cli" aria-label="Codex CLI">/);
  assert.match(source, /<summary className="codex-cli-title">/);
  assert.doesNotMatch(source, /<details className="codex-cli"[^>]*\bopen\b/);
  assert.match(styles, /\.codex-cli\[open\] \.codex-cli-title:before/);
});

test('can notify Windows when a Codex reply is ready', () => {
  const source = readFileSync(new URL('./main.jsx', import.meta.url), 'utf8');
  const styles = readFileSync(new URL('./styles.css', import.meta.url), 'utf8');

  assert.match(source, /Notification\.requestPermission\(\)/);
  assert.match(source, /sameTask=!!task&&previous\?\.id===task\.id/);
  assert.match(source, /new Notification\(reply\?/);
  assert.match(source, /reply\?\.content\|\|task\.summary\|\|task\.error/);
  assert.match(source, /taskloom-windows-notifications/);
  assert.match(source, /className=\{`windows-notifications/);
  assert.match(styles, /\.windows-notifications\{/);
});

test('uses one task field with dropdown suggestions to switch to or create task branches', () => {
  const source = readFileSync(new URL('./main.jsx', import.meta.url), 'utf8');
  const styles = readFileSync(new URL('./styles.css', import.meta.url), 'utf8');

  assert.match(source, /\/api\/branches\?project_path=/);
  assert.match(source, /\/api\/branches\/switch/);
  assert.match(source, /function loadBranches/);
  assert.match(source, /function switchBranch/);
  assert.match(source, /const taskIdForBranch=/);
  assert.match(source, /const taskBranchFor=/);
  assert.match(source, /list="task-branches"/);
  assert.match(source, /branch\.name\.startsWith\('tasks\/'\)/);
  assert.match(source, /branch:taskBranchFor\(task_id\)/);
  assert.equal((source.match(/name="task_id"/g) || []).length, 1);
  assert.match(source, /برنچ فعال/);
  assert.match(source, /ساخت یا سوییچ/);
  assert.match(source, /هیچ reset یا stashی انجام نمی‌شود/);
  assert.match(styles, /\.branch-manager\{/);
});

test('offers an opt-in local test setup and a manual setup tab', () => {
  const source = readFileSync(new URL('./main.jsx', import.meta.url), 'utf8');
  const styles = readFileSync(new URL('./styles.css', import.meta.url), 'utf8');

  assert.match(source, /<details className="test-setup"><summary>Setup تست<\/summary>/);
  assert.doesNotMatch(source, /<details className="test-setup" open>/);
  assert.match(source, /name="test_setup_enabled" checked=\{form\.test_setup_enabled\}/);
  assert.match(source, /\/api\/test-setup/);
  assert.match(source, /tab==='test-setup'/);
  assert.match(source, /confirm_test_database:true/);
  assert.match(styles, /\.test-setup\{margin-bottom:14px/);
  assert.match(styles, /\.test-setup-toggle\{/);
  assert.match(styles, /\.run-test-setup\{/);
});

test('keeps execution details closed until the user opens them', () => {
  const source = readFileSync(new URL('./main.jsx', import.meta.url), 'utf8');
  const styles = readFileSync(new URL('./styles.css', import.meta.url), 'utf8');

  assert.match(source, /<details className="execution-details"><summary>/);
  assert.doesNotMatch(source, /<details className="execution-details" open>/);
  assert.match(styles, /\.execution-details\{margin-bottom:14px/);
});

test('shows the complete failed-test output from a dedicated details control', () => {
  const source = readFileSync(new URL('./main.jsx', import.meta.url), 'utf8');
  const styles = readFileSync(new URL('./styles.css', import.meta.url), 'utf8');

  assert.match(source, /className="test-error-details"/);
  assert.match(source, /<summary>مشاهده جزئیات<\/summary>/);
  assert.match(source, /خروجی کامل آخرین اجرای تست/);
  assert.match(source, /<DirectionalOutput text=\{task\.test_output\}\/>/);
  assert.match(styles, /\.test-error-details\{margin-top:10px/);
});
