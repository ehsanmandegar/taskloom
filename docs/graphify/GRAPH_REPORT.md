# Graph Report - taskloom  (2026-11-20)

## Corpus Check
- 48 files · ~50,863 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 6 file(s) not represented in the graph (top: (none) 2, .bat 1, .ico 1)

## Summary
- 1114 nodes · 2999 edges · 54 communities (46 shown, 8 thin omitted)
- Extraction: 86% EXTRACTED · 14% INFERRED · 0% AMBIGUOUS · INFERRED: 415 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `1ceaf61c`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- SDLCProjectManager
- test_sdlc_git.py
- test_api.py
- pathlib
- app/main.py
- SDLCProjectConfig
- SDLC Platform Implementation Guide
- TaskState
- TaskWorkspace
- test_sdlc_locking.py
- قرارداد عملیاتی DWS Portal و Taskloom
- AgentConfig
- sdlc_runner.py
- SDLCTaskManager
- guide_mcp.py
- post
- models.py
- Path
- test_sdlc_lifecycle.py
- package.json
- save_tasks
- ایرادهای شناخته‌شده (بازبینی کد — 2026-11-20)
- field_validator
- services.py
- execute_task
- main.jsx
- ProjectProfile
- test_sdlc_recovery.py
- theme.test.js
- workspace_diff
- ClaudeEventStream
- test_session_todos_run_before_automatic_delivery_and_new_branches
- _codex_account_status
- App
- complete_automatic_delivery
- CodexEventStream
- preflight_project_mcp
- test_codex_large_prompts_use_stdin_and_preserve_streamed_events
- .load_task
- TodoItem
- markdown.jsx
- sdlc_dashboard.jsx
- Taskloom
- test_codex_account_status_uses_portable_pipes_and_waits_for_initialization
- git_commit
- جریان SDLC
- git_tasks.jsx
- StageTransitionRequest
- HumanInterventionResponse
- test_command_resolves_relative_executable_from_working_directory
- test_selected_agent_status_exposes_claude_auth_without_sensitive_fields
- setup
- test_new_tasks_use_the_tasks_branch_prefix

## God Nodes (most connected - your core abstractions)
1. `TaskState` - 93 edges
2. `RunStatus` - 76 edges
3. `SDLCTaskManager` - 61 edges
4. `SDLCProjectConfig` - 54 edges
5. `SDLCTask` - 51 edges
6. `AgentConfig` - 38 edges
7. `execute_task()` - 37 edges
8. `TaskWorkspace()` - 36 edges
9. `run_cli_stage()` - 34 edges
10. `command()` - 33 edges

## Surprising Connections (you probably didn't know these)
- `ماشین وضعیت (`SDLCStatus`)` --references--> `SDLCStatus`  [INFERRED]
  docs/architecture.md → backend/app/models.py
- `عامل‌ها (اجراکنندهٔ هر مرحله)` --references--> `AgentConfig`  [INFERRED]
  docs/architecture.md → backend/app/models.py
- `Git و GitHub (`backend/app/sdlc_git.py`)` --references--> `TaskRepo`  [INFERRED]
  docs/architecture.md → backend/app/models.py
- `✅ رفع‌شده در مرحلهٔ ۳ (2026-11-20)` --references--> `test_plan()`  [INFERRED]
  docs/known-issues.md → backend/app/services.py
- `ماژول‌ها` --references--> `TaskState`  [INFERRED]
  docs/architecture.md → backend/app/models.py

## Import Cycles
- None detected.

## Communities (54 total, 8 thin omitted)

### Community 0 - "SDLCProjectManager"
Cohesion: 0.05
Nodes (19): FileLock, replace_with_retry(), _Blob, _dpapi(), SecretStore, SDLCProjectManager, 🟡 کیفیت و نگهداری, test_saved_project_with_default_github_config_loads_again() (+11 more)

### Community 1 - "test_sdlc_git.py"
Cohesion: 0.06
Nodes (40): github_commit_push(), _github_context(), github_create_pr(), GitHubActionRequest, validate_github(), TaskRepo, commit_and_push(), commit_message() (+32 more)

### Community 2 - "test_api.py"
Cohesion: 0.06
Nodes (41): project_defaults(), detect_tests(), mcp_runtime_issue(), resolve_guides(), test_setup_commands(), local_test_setup_repo(), test_branch_list_exposes_local_and_origin_branches(), test_branch_switch_rejects_invalid_base_branch() (+33 more)

### Community 3 - "pathlib"
Cohesion: 0.06
Nodes (17): kill_process_tree(), process_image(), stop_if_same_program(), started(), command_path(), get_data_separator(), main(), remove_directory() (+9 more)

### Community 4 - "app/main.py"
Cohesion: 0.09
Nodes (19): codex_status(), defaults(), get_role_knowledge(), get_sdlc_project(), get_sdlc_task(), health(), lifespan(), list_pending_human_interventions() (+11 more)

### Community 5 - "SDLCProjectConfig"
Cohesion: 0.11
Nodes (12): AgentResult, HumanIntervention, SDLCProjectConfig, SDLCTask, _feedback_text(), OllamaAgentRunner, ذخیره‌سازی, ماژول‌ها (+4 more)

### Community 6 - "SDLC Platform Implementation Guide"
Cohesion: 0.06
Nodes (34): 1. Internal Scheduler/Loop, 2. Human Intervention System, 3. Structured Agent Outputs, 4. Project Configuration, Agent Types, API Integration, Architecture, Backend Tests (+26 more)

### Community 7 - "TaskState"
Cohesion: 0.11
Nodes (24): load_tasks(), todo_destination(), RunStatus, TaskState, git_push(), test_continue_task_resumes_same_codex_session_and_retests(), test_follow_up_is_queued_for_a_stopped_codex_session(), fake_continue() (+16 more)

### Community 8 - "TaskWorkspace"
Cohesion: 0.13
Nodes (29): agentLabelFor(), apiError(), defaultBaseBranch(), DirectionalOutput(), loadWorkspaceState(), taskBranchFor(), taskIdForBranch(), TaskWorkspace() (+21 more)

### Community 9 - "test_sdlc_locking.py"
Cohesion: 0.12
Nodes (17): LockTimeout, TaskConflictError, هم‌زمانی (`backend/app/file_lock.py`), ✅ رفع‌شده در مرحلهٔ ۷ — قفل فایل (2026-11-20), make_task(), run(), run_in_new_loop(), test_an_inbox_item_can_only_be_answered_once() (+9 more)

### Community 10 - "قرارداد عملیاتی DWS Portal و Taskloom"
Cohesion: 0.07
Nodes (29): frontend, gate اصلی backend, Locust, MCP دانش پروژه, MCP مستقل پروژه, suite قدیمی, الزامی, قرارداد عملیاتی DWS Portal و Taskloom (+21 more)

### Community 11 - "AgentConfig"
Cohesion: 0.18
Nodes (18): AgentConfig, StageRunner, resolve_runner(), fake_agent(), install(), make_task(), project(), report() (+10 more)

### Community 12 - "sdlc_runner.py"
Cohesion: 0.14
Nodes (16): AgentType, folder_changes(), parse_agent_report(), _recommendations(), record_agent_process(), run_cli_stage(), run_stage_tests(), snapshot_folder() (+8 more)

### Community 13 - "SDLCTaskManager"
Cohesion: 0.11
Nodes (4): SDLCTaskManager, صندوق انسانی (human inbox), manager(), test_only_one_server_owns_a_data_directory()

### Community 14 - "guide_mcp.py"
Cohesion: 0.17
Nodes (7): Guide, GuideCatalog, main(), McpServer, serve(), tool_definitions(), test_guide_catalog_reads_and_searches_only_markdown_roots()

### Community 15 - "post"
Cohesion: 0.09
Nodes (16): approve_sdlc_task(), create_human_intervention_request(), create_sdlc_project(), delete_sdlc_project(), delete_task(), delete_todo(), get_state(), merge_request() (+8 more)

### Community 16 - "models.py"
Cohesion: 0.13
Nodes (17): create_sdlc_task(), BranchSwitchRequest, Change, ChatRequest, CommitRequest, GitProvider, McpFailureMode, McpStatus (+9 more)

### Community 17 - "Path"
Cohesion: 0.13
Nodes (16): list_branches(), project_git_changes(), switch_branch(), base_branch_ref(), cleanup_owned_test_artifacts(), command(), continue_task(), create_merge_request() (+8 more)

### Community 18 - "test_sdlc_lifecycle.py"
Cohesion: 0.16
Nodes (17): RevisionRequest, build_stage_prompt(), stage_feedback(), test_command_receives_large_utf8_stdin_without_shell_expansion(), test_command_timeout_does_not_wait_for_stdin_consumption(), finish_analysis(), make_task(), run() (+9 more)

### Community 19 - "package.json"
Cohesion: 0.10
Nodes (23): dependencies, lucide-react@^0.294.0, react@^18.2.0, react-dom@^18.2.0, vite@^5.0.0, @vitejs/plugin-react@^5.0.0, name, private (+15 more)

### Community 20 - "save_tasks"
Cohesion: 0.16
Nodes (17): advance_todo_queue(), commit(), create_task(), discard_todo(), dispatch_next_todo(), load_role_knowledge(), queue_follow_up(), rename_task() (+9 more)

### Community 21 - "ایرادهای شناخته‌شده (بازبینی کد — 2026-11-20)"
Cohesion: 0.08
Nodes (20): project_file_tree(), workspace_tree(), visit(), API, SDLC, تسک کلاسیک (Codex / Claude Code), نمونه, ایرادهای شناخته‌شده (بازبینی کد — 2026-11-20) (+12 more)

### Community 22 - "field_validator"
Cohesion: 0.11
Nodes (3): SDLCTaskRequest, TodoRequest, valid_branch_name()

### Community 23 - "services.py"
Cohesion: 0.09
Nodes (4): _mcp_config(), split_command(), test_plan(), test_working_directory()

### Community 24 - "execute_task"
Cohesion: 0.15
Nodes (14): TaskRequest, build_prompt(), execute_task(), test_build_prompt_requires_reviewing_markdown_after_changes(), test_build_prompt_uses_dws_mcp_for_context_but_not_test_evidence(), test_claude_account_status_uses_cli_json_and_omits_identity(), test_execute_task_checks_out_an_existing_task_branch(), test_execute_task_creates_the_task_branch_from_selected_base() (+6 more)

### Community 25 - "main.jsx"
Cohesion: 0.15
Nodes (17): CodePane(), DiffViewer(), extensionFor(), FilePreview(), initial, languageFor(), lineIsChanged(), localDateTimeValue() (+9 more)

### Community 26 - "ProjectProfile"
Cohesion: 0.16
Nodes (13): _default_project_path(), delete_profile(), dws_test_defaults(), load_profiles(), migrate_legacy_test_settings(), profiles_path(), put_profile(), put_role_knowledge() (+5 more)

### Community 27 - "test_sdlc_recovery.py"
Cohesion: 0.27
Nodes (11): SDLCStatus, make_task(), manager(), run(), test_auto_resume_reruns_without_asking(), test_command_reports_the_started_pid(), test_interrupted_running_tasks_go_to_the_inbox_once(), test_orphaned_agent_is_checked_and_reported() (+3 more)

### Community 28 - "theme.test.js"
Cohesion: 0.20
Nodes (6): Clock(), resolveMarkdownAsset(), getInitialTheme(), nextTheme(), THEMES, formatTime()

### Community 29 - "workspace_diff"
Cohesion: 0.15
Nodes (9): project_file(), project_file_diff(), project_raw_file(), read_workspace_docx(), read_workspace_text(), workspace_diff(), workspace_file(), workspace_path() (+1 more)

### Community 30 - "ClaudeEventStream"
Cohesion: 0.26
Nodes (5): claude_command(), claude_response(), _claude_text_blocks(), ClaudeEventStream, test_claude_stream_json_preserves_session_final_response_and_live_activity()

### Community 31 - "test_session_todos_run_before_automatic_delivery_and_new_branches"
Cohesion: 0.17
Nodes (4): test_due_todos_skip_future_deadlines_without_blocking_ready_work(), fake_create_task(), test_scheduler_dispatch_releases_only_explicitly_scheduled_work(), test_session_todos_run_before_automatic_delivery_and_new_branches()

### Community 32 - "_codex_account_status"
Cohesion: 0.18
Nodes (5): _codex_account_status(), codex_account_status_payload(), _command_sync(), read_output(), test_codex_account_status_payload_omits_account_email_and_keeps_usage_data()

### Community 33 - "App"
Cohesion: 0.18
Nodes (7): App(), addWorkspace(), moveBoardTask(), saveRoleKnowledge(), loadBoardAssignments(), loadWorkspaces(), newWorkspace()

### Community 34 - "complete_automatic_delivery"
Cohesion: 0.22
Nodes (5): complete_automatic_delivery(), test_automatic_delivery_completes_before_releasing_the_next_todo(), fake_commit(), test_automatic_delivery_generates_a_commit_message_when_enabled(), test_uncommitted_changes_hold_the_todo_queue_without_auto_commit()

### Community 35 - "CodexEventStream"
Cohesion: 0.36
Nodes (3): codex_command(), CodexEventStream, test_codex_jsonl_events_update_live_output_incrementally()

### Community 36 - "preflight_project_mcp"
Cohesion: 0.20
Nodes (5): preflight_project_mcp(), test_claude_mcp_preflight_uses_its_native_command_and_rejects_unavailable_entries(), test_creates_merge_request_and_returns_url(), test_mcp_preflight_reports_unavailable_states(), test_mcp_preflight_requires_configured_and_enabled_entry()

### Community 37 - "test_codex_large_prompts_use_stdin_and_preserve_streamed_events"
Cohesion: 0.25
Nodes (6): codex_response(), initial_agent_args(), resume_agent_args(), test_claude_commands_start_and_resume_the_exact_session_with_safe_edit_permissions(), test_codex_response_reads_thread_and_final_message_from_jsonl(), test_codex_large_prompts_use_stdin_and_preserve_streamed_events()

### Community 38 - ".load_task"
Cohesion: 0.31
Nodes (4): _read_text_with_retry(), make_task(), test_approve_endpoint_marks_task_done_only_from_pending_approval(), test_last_stage_moves_task_to_pending_approval()

### Community 39 - "TodoItem"
Cohesion: 0.36
Nodes (5): add_todo(), due_todos(), pending_todos(), todo_is_due(), TodoItem

### Community 40 - "markdown.jsx"
Cohesion: 0.54
Nodes (7): inlineMarkdown(), isBlockStart(), isTableDivider(), MarkdownPreview(), renderBlocks(), safeExternalUrl(), splitCells()

### Community 41 - "sdlc_dashboard.jsx"
Cohesion: 0.29
Nodes (6): agentTypes, interventionHints, readJsonOrThrow(), responseOptionLabels, SDLCDashboard(), sdlcStages

### Community 42 - "Taskloom"
Cohesion: 0.25
Nodes (7): Taskloom, دسترسی به راهنماها با MCP, راه‌اندازی, ساخت فایل اجرایی ویندوز, مسیر دانش نقش‌ها, نگه‌داری و ادامهٔ گفت‌وگو, چه کاری انجام می‌دهد؟

### Community 44 - "git_commit"
Cohesion: 0.33
Nodes (4): git_commit(), test_git_commit_skips_hooks_when_nothing_is_staged(), test_git_commit_stages_changes_before_running_commit(), fake_refresh()

### Community 45 - "جریان SDLC"
Cohesion: 0.29
Nodes (7): Git و GitHub (`backend/app/sdlc_git.py`), بازیابی پس از restart, جریان SDLC, حلقهٔ بازبینی, عامل‌ها (اجراکنندهٔ هر مرحله), ماشین وضعیت (`SDLCStatus`), نگهداری token (`backend/app/secret_store.py`)

### Community 50 - "test_selected_agent_status_exposes_claude_auth_without_sensitive_fields"
Cohesion: 0.50
Nodes (3): test_codex_status_exposes_account_limits_usage_and_models(), fake_status(), test_selected_agent_status_exposes_claude_auth_without_sensitive_fields()

## Knowledge Gaps
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `TaskState` connect `TaskState` to `SDLCProjectManager`, `test_sdlc_git.py`, `test_api.py`, `app/main.py`, `SDLCProjectConfig`, `test_sdlc_locking.py`, `AgentConfig`, `sdlc_runner.py`, `SDLCTaskManager`, `post`, `models.py`, `Path`, `test_sdlc_lifecycle.py`, `save_tasks`, `services.py`, `execute_task`, `test_sdlc_recovery.py`, `ClaudeEventStream`, `test_session_todos_run_before_automatic_delivery_and_new_branches`, `complete_automatic_delivery`, `CodexEventStream`, `preflight_project_mcp`, `test_codex_large_prompts_use_stdin_and_preserve_streamed_events`, `.load_task`, `TodoItem`, `git_commit`?**
  _High betweenness centrality (0.073) - this node is a cross-community bridge._
- **Are the 29 inferred relationships involving `TaskState` (e.g. with `advance_todo_queue()` and `complete_automatic_delivery()`) actually correct?**
  _`TaskState` has 29 INFERRED edges - model-reasoned connections that need verification._
- **Should `SDLCProjectManager` be split into smaller, more focused modules?**
  _Cohesion score 0.0517503805175038 - nodes in this community are weakly interconnected._
- **Why does `SDLCTaskManager` connect `SDLCTaskManager` to `SDLCProjectManager`, `test_sdlc_git.py`, `app/main.py`, `SDLCProjectConfig`, `.load_task`, `TaskState`, `test_sdlc_locking.py`, `AgentConfig`, `Path`, `test_sdlc_lifecycle.py`, `setup`, `field_validator`, `services.py`, `test_sdlc_recovery.py`?**
  _High betweenness centrality (0.061) - this node is a cross-community bridge._
- **Are the 62 inferred relationships involving `RunStatus` (e.g. with `advance_todo_queue()` and `complete_automatic_delivery()`) actually correct?**
  _`RunStatus` has 62 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_sdlc_git.py` be split into smaller, more focused modules?**
  _Cohesion score 0.0648018648018648 - nodes in this community are weakly interconnected._
- **Why does `RunStatus` connect `TaskState` to `SDLCProjectManager`, `test_sdlc_git.py`, `test_api.py`, `app/main.py`, `test_sdlc_locking.py`, `AgentConfig`, `sdlc_runner.py`, `post`, `models.py`, `Path`, `test_sdlc_lifecycle.py`, `save_tasks`, `services.py`, `execute_task`, `test_sdlc_recovery.py`, `ClaudeEventStream`, `test_session_todos_run_before_automatic_delivery_and_new_branches`, `complete_automatic_delivery`, `CodexEventStream`, `preflight_project_mcp`, `test_codex_large_prompts_use_stdin_and_preserve_streamed_events`, `.load_task`, `git_commit`?**
  _High betweenness centrality (0.048) - this node is a cross-community bridge._