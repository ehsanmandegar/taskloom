# Graph Report - taskloom  (2026-11-20)

## Corpus Check
- 51 files · ~54,462 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 6 file(s) not represented in the graph (top: (none) 2, .bat 1, .ico 1)

## Summary
- 1176 nodes · 3216 edges · 58 communities (53 shown, 5 thin omitted)
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 430 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7dbf9100`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- sdlc_runner.py
- SDLCProjectConfig
- sdlc_git.py
- test_api.py
- SDLCTaskManager
- SDLC Platform Implementation Guide
- FileLock
- TaskWorkspace
- قرارداد عملیاتی DWS Portal و Taskloom
- TaskState
- test_sdlc_locking.py
- app/main.py
- models.py
- fake_command
- save_tasks
- ایرادهای شناخته‌شده (بازبینی کد — 2026-11-20)
- main.jsx
- execute_task
- post
- field_validator
- codex_account_status
- command
- TaskRequest
- GuideCatalog
- package.json
- pathlib
- git_tasks.jsx
- ProjectProfile
- os
- services.py
- SDLCTask
- build_exe.py
- Path
- workspace_diff
- sdlc_dashboard.jsx
- test_sdlc_recovery.py
- ClaudeEventStream
- test_session_todos_run_before_automatic_delivery_and_new_branches
- file_lock.py
- App
- CodexEventStream
- markdown.jsx
- guide_mcp.py
- TodoItem
- جریان SDLC
- Taskloom
- test_sdlc_approval.py
- test_automatic_delivery_completes_before_releasing_the_next_todo
- delete_task
- StageTransitionRequest
- test_git_commit_skips_hooks_when_nothing_is_staged
- نقشهٔ نام‌های رابط کاربری
- dashboard.jsx
- test_command_resolves_relative_executable_from_working_directory
- _command_sync
- test_selected_agent_status_exposes_claude_auth_without_sensitive_fields
- test_load_tasks_keeps_interrupted_sessions_when_storage_is_unavailable

## God Nodes (most connected - your core abstractions)
1. `TaskState` - 95 edges
2. `RunStatus` - 78 edges
3. `SDLCTaskManager` - 64 edges
4. `SDLCProjectConfig` - 63 edges
5. `SDLCTask` - 53 edges
6. `AgentConfig` - 40 edges
7. `command()` - 39 edges
8. `run_cli_stage()` - 38 edges
9. `SDLCProjectManager` - 38 edges
10. `execute_task()` - 37 edges

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

## Communities (58 total, 5 thin omitted)

### Community 0 - "sdlc_runner.py"
Cohesion: 0.05
Nodes (53): AgentConfig, AgentResult, Change, HumanIntervention, RevisionRequest, StageRunner, TestResults, build_stage_prompt() (+45 more)

### Community 1 - "SDLCProjectConfig"
Cohesion: 0.05
Nodes (35): ProjectRepository, SDLCProjectConfig, SDLCProjectManager, Backend Components, test_command_receives_large_utf8_stdin_without_shell_expansion(), test_command_timeout_does_not_wait_for_stdin_consumption(), api(), existing_project() (+27 more)

### Community 2 - "sdlc_git.py"
Cohesion: 0.06
Nodes (49): github_commit_push(), _github_context(), github_create_pr(), GitHubActionRequest, prepare_project_repository(), validate_github(), TaskRepo, auth_args() (+41 more)

### Community 3 - "test_api.py"
Cohesion: 0.10
Nodes (30): project_defaults(), local_test_setup_repo(), test_branch_list_exposes_local_and_origin_branches(), test_branch_switch_rejects_invalid_base_branch(), test_branch_switch_rejects_invalid_branch_name(), test_branch_switch_uses_existing_branch_or_creates_a_missing_one(), test_create_task_returns_a_confirmation_code_for_a_dirty_current_branch(), test_defaults_can_be_overridden_for_another_project() (+22 more)

### Community 4 - "SDLCTaskManager"
Cohesion: 0.11
Nodes (3): SDLCTaskManager, صندوق انسانی (human inbox), test_only_one_server_owns_a_data_directory()

### Community 5 - "SDLC Platform Implementation Guide"
Cohesion: 0.06
Nodes (34): 1. Internal Scheduler/Loop, 2. Human Intervention System, 3. Structured Agent Outputs, 4. Project Configuration, Agent Types, API Integration, Architecture, Backend Tests (+26 more)

### Community 6 - "FileLock"
Cohesion: 0.11
Nodes (7): FileLock, _Blob, _dpapi(), SecretStore, test_file_lock_excludes_another_process(), test_store_roundtrip_without_plaintext_on_disk(), test_windows_store_uses_dpapi()

### Community 7 - "TaskWorkspace"
Cohesion: 0.14
Nodes (28): agentLabelFor(), apiError(), defaultBaseBranch(), loadWorkspaceState(), taskBranchFor(), taskIdForBranch(), TaskWorkspace(), action() (+20 more)

### Community 8 - "قرارداد عملیاتی DWS Portal و Taskloom"
Cohesion: 0.07
Nodes (29): frontend, gate اصلی backend, Locust, MCP دانش پروژه, MCP مستقل پروژه, suite قدیمی, الزامی, قرارداد عملیاتی DWS Portal و Taskloom (+21 more)

### Community 9 - "TaskState"
Cohesion: 0.14
Nodes (22): load_tasks(), todo_destination(), RunStatus, TaskState, test_continue_task_resumes_same_codex_session_and_retests(), test_follow_up_is_queued_for_a_stopped_codex_session(), fake_continue(), test_future_todo_is_persisted_without_running_early() (+14 more)

### Community 10 - "test_sdlc_locking.py"
Cohesion: 0.14
Nodes (15): _read_text_with_retry(), TaskConflictError, هم‌زمانی (`backend/app/file_lock.py`), ✅ رفع‌شده در مرحلهٔ ۷ — قفل فایل (2026-11-20), make_task(), manager(), run(), run_in_new_loop() (+7 more)

### Community 11 - "app/main.py"
Cohesion: 0.11
Nodes (13): defaults(), get_role_knowledge(), get_sdlc_project(), get_sdlc_task(), health(), lifespan(), list_pending_human_interventions(), list_profiles() (+5 more)

### Community 12 - "models.py"
Cohesion: 0.13
Nodes (15): create_sdlc_task(), ChatRequest, CommitRequest, GitProvider, HumanInterventionResponse, McpFailureMode, McpStatus, ProjectDefaults (+7 more)

### Community 13 - "fake_command"
Cohesion: 0.08
Nodes (13): test_claude_account_status_uses_cli_json_and_omits_identity(), test_claude_mcp_preflight_uses_its_native_command_and_rejects_unavailable_entries(), test_creates_merge_request_and_returns_url(), test_dirty_current_task_branch_requires_explicit_confirmation(), test_dirty_worktree_cannot_be_carried_to_a_different_task_branch(), test_execute_task_checks_out_an_existing_task_branch(), test_generate_commit_message_uses_the_task_codex_session(), test_mcp_preflight_reports_unavailable_states() (+5 more)

### Community 14 - "save_tasks"
Cohesion: 0.16
Nodes (17): advance_todo_queue(), commit(), create_task(), discard_todo(), dispatch_next_todo(), load_role_knowledge(), queue_follow_up(), rename_task() (+9 more)

### Community 15 - "ایرادهای شناخته‌شده (بازبینی کد — 2026-11-20)"
Cohesion: 0.08
Nodes (20): project_file_tree(), workspace_tree(), visit(), API, SDLC, تسک کلاسیک (Codex / Claude Code), نمونه, ایرادهای شناخته‌شده (بازبینی کد — 2026-11-20) (+12 more)

### Community 16 - "main.jsx"
Cohesion: 0.13
Nodes (19): مودال‌ها, CodePane(), DiffViewer(), DirectionalOutput(), extensionFor(), FilePreview(), initial, languageFor() (+11 more)

### Community 17 - "execute_task"
Cohesion: 0.16
Nodes (18): AgentType, agent_executable(), agent_name(), agent_response(), cleanup_owned_test_artifacts(), codex_response(), continue_task(), execute_task() (+10 more)

### Community 18 - "post"
Cohesion: 0.11
Nodes (14): approve_sdlc_task(), create_human_intervention_request(), create_sdlc_project(), get_state(), merge_request(), push(), respond_to_human_intervention(), send_message() (+6 more)

### Community 19 - "field_validator"
Cohesion: 0.11
Nodes (4): BranchSwitchRequest, SDLCTaskRequest, TodoRequest, valid_branch_name()

### Community 20 - "codex_account_status"
Cohesion: 0.10
Nodes (7): codex_status(), codex_account_status(), _codex_account_status(), codex_account_status_payload(), test_codex_account_status_payload_omits_account_email_and_keeps_usage_data(), test_codex_account_status_reports_process_start_errors(), test_codex_account_status_uses_portable_pipes_and_waits_for_initialization()

### Community 21 - "command"
Cohesion: 0.14
Nodes (15): complete_automatic_delivery(), list_branches(), project_git_changes(), run_manual_test_setup(), switch_branch(), base_branch_ref(), command(), create_merge_request() (+7 more)

### Community 22 - "TaskRequest"
Cohesion: 0.10
Nodes (12): TaskRequest, build_prompt(), test_build_prompt_requires_reviewing_markdown_after_changes(), test_build_prompt_uses_dws_mcp_for_context_but_not_test_evidence(), test_execute_task_creates_the_task_branch_from_selected_base(), test_execute_task_keeps_the_complete_failed_test_output(), test_execute_task_reuses_confirmed_dirty_current_branch_without_switching(), test_new_tasks_use_the_tasks_branch_prefix() (+4 more)

### Community 23 - "GuideCatalog"
Cohesion: 0.23
Nodes (5): Guide, GuideCatalog, McpServer, tool_definitions(), test_guide_catalog_reads_and_searches_only_markdown_roots()

### Community 24 - "package.json"
Cohesion: 0.13
Nodes (18): dependencies, lucide-react@^0.294.0, react@^18.2.0, react-dom@^18.2.0, vite@^5.0.0, @vitejs/plugin-react@^5.0.0, name, private (+10 more)

### Community 25 - "pathlib"
Cohesion: 0.16
Nodes (6): configure_instance_storage(), run(), runtime_options(), test_custom_port_uses_an_isolated_data_directory(), test_each_non_default_port_has_its_own_default_namespace(), test_run_starts_browser_and_local_server()

### Community 26 - "git_tasks.jsx"
Cohesion: 0.16
Nodes (7): GitTaskList(), gitTaskRows(), Clock(), getInitialTheme(), nextTheme(), THEMES, formatTime()

### Community 27 - "ProjectProfile"
Cohesion: 0.16
Nodes (13): _default_project_path(), delete_profile(), dws_test_defaults(), load_profiles(), migrate_legacy_test_settings(), profiles_path(), put_profile(), put_role_knowledge() (+5 more)

### Community 28 - "os"
Cohesion: 0.19
Nodes (4): kill_process_tree(), process_image(), stop_if_same_program(), test_stop_if_same_program_only_kills_the_recorded_program()

### Community 29 - "services.py"
Cohesion: 0.13
Nodes (4): selected_agent_status(), agent_account_status(), _mcp_config(), preflight_project_mcp()

### Community 30 - "SDLCTask"
Cohesion: 0.15
Nodes (5): SDLCTask, ذخیره‌سازی, ماژول‌ها, معماری Taskloom, نمای کلی

### Community 31 - "build_exe.py"
Cohesion: 0.19
Nodes (6): command_path(), get_data_separator(), main(), remove_directory(), run_command(), validate_project()

### Community 32 - "Path"
Cohesion: 0.17
Nodes (8): detect_tests(), prepare_tests(), run_test_setup(), split_command(), task_branch_preflight(), test_plan(), test_setup_commands(), test_working_directory()

### Community 33 - "workspace_diff"
Cohesion: 0.15
Nodes (9): project_file(), project_file_diff(), project_raw_file(), read_workspace_docx(), read_workspace_text(), workspace_diff(), workspace_file(), workspace_path() (+1 more)

### Community 34 - "sdlc_dashboard.jsx"
Cohesion: 0.24
Nodes (11): agentTypes, DEFAULT_REPOSITORY, interventionHints, ProjectRepoActions(), readJsonOrThrow(), RepositorySettings(), responseOptionLabels, SDLCDashboard() (+3 more)

### Community 35 - "test_sdlc_recovery.py"
Cohesion: 0.42
Nodes (9): SDLCStatus, make_task(), run(), test_auto_resume_reruns_without_asking(), test_command_reports_the_started_pid(), test_interrupted_running_tasks_go_to_the_inbox_once(), test_orphaned_agent_is_checked_and_reported(), test_resume_answer_reruns_the_interrupted_stage() (+1 more)

### Community 36 - "ClaudeEventStream"
Cohesion: 0.26
Nodes (5): claude_command(), claude_response(), _claude_text_blocks(), ClaudeEventStream, test_claude_stream_json_preserves_session_final_response_and_live_activity()

### Community 37 - "test_session_todos_run_before_automatic_delivery_and_new_branches"
Cohesion: 0.17
Nodes (4): test_due_todos_skip_future_deadlines_without_blocking_ready_work(), fake_create_task(), test_scheduler_dispatch_releases_only_explicitly_scheduled_work(), test_session_todos_run_before_automatic_delivery_and_new_branches()

### Community 38 - "file_lock.py"
Cohesion: 0.20
Nodes (3): LockTimeout, replace_with_retry(), test_replace_retries_transient_windows_permission_errors()

### Community 39 - "App"
Cohesion: 0.18
Nodes (7): App(), addWorkspace(), moveBoardTask(), saveRoleKnowledge(), loadBoardAssignments(), loadWorkspaces(), newWorkspace()

### Community 40 - "CodexEventStream"
Cohesion: 0.36
Nodes (3): codex_command(), CodexEventStream, test_codex_jsonl_events_update_live_output_incrementally()

### Community 41 - "markdown.jsx"
Cohesion: 0.42
Nodes (8): inlineMarkdown(), isBlockStart(), isTableDivider(), MarkdownPreview(), renderBlocks(), safeExternalUrl(), splitCells(), resolveMarkdownAsset()

### Community 43 - "TodoItem"
Cohesion: 0.36
Nodes (5): add_todo(), due_todos(), pending_todos(), todo_is_due(), TodoItem

### Community 44 - "جریان SDLC"
Cohesion: 0.25
Nodes (8): Git و GitHub (`backend/app/sdlc_git.py`), بازیابی پس از restart, جریان SDLC, حلقهٔ بازبینی, ریپوی پروژه (`SDLCProjectConfig.repository`), عامل‌ها (اجراکنندهٔ هر مرحله), ماشین وضعیت (`SDLCStatus`), نگهداری token (`backend/app/secret_store.py`)

### Community 45 - "Taskloom"
Cohesion: 0.25
Nodes (7): Taskloom, دسترسی به راهنماها با MCP, راه‌اندازی, ساخت فایل اجرایی ویندوز, مسیر دانش نقش‌ها, نگه‌داری و ادامهٔ گفت‌وگو, چه کاری انجام می‌دهد؟

### Community 46 - "test_sdlc_approval.py"
Cohesion: 0.43
Nodes (4): ProjectWorkflowConfig, make_task(), test_approve_endpoint_marks_task_done_only_from_pending_approval(), test_last_stage_moves_task_to_pending_approval()

### Community 47 - "test_automatic_delivery_completes_before_releasing_the_next_todo"
Cohesion: 0.29
Nodes (3): test_automatic_delivery_completes_before_releasing_the_next_todo(), fake_commit(), test_automatic_delivery_generates_a_commit_message_when_enabled()

### Community 48 - "delete_task"
Cohesion: 0.33
Nodes (3): delete_sdlc_project(), delete_task(), delete_todo()

### Community 49 - "StageTransitionRequest"
Cohesion: 0.33
Nodes (3): transition_sdlc_task(), StageTransitionRequest, 🟡 کیفیت و نگهداری

### Community 50 - "test_git_commit_skips_hooks_when_nothing_is_staged"
Cohesion: 0.33
Nodes (3): test_git_commit_skips_hooks_when_nothing_is_staged(), test_git_commit_stages_changes_before_running_commit(), fake_refresh()

### Community 51 - "نقشهٔ نام‌های رابط کاربری"
Cohesion: 0.40
Nodes (4): بخش‌های M3 (جزئیات تسک), مراحل M4 (فرم پروژه), نقشهٔ نام‌های رابط کاربری, پیام‌های مرورگر (`alert`)

### Community 52 - "dashboard.jsx"
Cohesion: 0.60
Nodes (4): DashboardPages(), stages, statusLabel(), taskTitle()

### Community 55 - "test_selected_agent_status_exposes_claude_auth_without_sensitive_fields"
Cohesion: 0.50
Nodes (3): test_codex_status_exposes_account_limits_usage_and_models(), fake_status(), test_selected_agent_status_exposes_claude_auth_without_sensitive_fields()

## Knowledge Gaps
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SDLCTaskManager` connect `SDLCTaskManager` to `sdlc_runner.py`, `SDLCProjectConfig`, `sdlc_git.py`, `test_sdlc_recovery.py`, `file_lock.py`, `FileLock`, `TaskState`, `test_sdlc_locking.py`, `app/main.py`, `test_sdlc_approval.py`, `field_validator`, `services.py`, `SDLCTask`?**
  _High betweenness centrality (0.072) - this node is a cross-community bridge._
- **Are the 29 inferred relationships involving `TaskState` (e.g. with `advance_todo_queue()` and `complete_automatic_delivery()`) actually correct?**
  _`TaskState` has 29 INFERRED edges - model-reasoned connections that need verification._
- **Should `sdlc_runner.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05337078651685393 - nodes in this community are weakly interconnected._
- **Why does `TaskState` connect `TaskState` to `sdlc_runner.py`, `SDLCProjectConfig`, `sdlc_git.py`, `test_api.py`, `SDLCTaskManager`, `test_sdlc_locking.py`, `app/main.py`, `models.py`, `fake_command`, `save_tasks`, `execute_task`, `post`, `command`, `TaskRequest`, `services.py`, `SDLCTask`, `Path`, `test_sdlc_recovery.py`, `ClaudeEventStream`, `test_session_todos_run_before_automatic_delivery_and_new_branches`, `CodexEventStream`, `TodoItem`, `test_sdlc_approval.py`, `test_automatic_delivery_completes_before_releasing_the_next_todo`, `test_git_commit_skips_hooks_when_nothing_is_staged`?**
  _High betweenness centrality (0.064) - this node is a cross-community bridge._
- **Are the 63 inferred relationships involving `RunStatus` (e.g. with `advance_todo_queue()` and `complete_automatic_delivery()`) actually correct?**
  _`RunStatus` has 63 INFERRED edges - model-reasoned connections that need verification._
- **Should `SDLCProjectConfig` be split into smaller, more focused modules?**
  _Cohesion score 0.050774526678141134 - nodes in this community are weakly interconnected._
- **Why does `Backend Components` connect `SDLCProjectConfig` to `sdlc_runner.py`, `test_sdlc_recovery.py`, `SDLCTaskManager`, `SDLC Platform Implementation Guide`, `SDLCTask`?**
  _High betweenness centrality (0.058) - this node is a cross-community bridge._