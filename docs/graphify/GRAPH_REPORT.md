# Graph Report - taskloom  (2026-11-20)

## Corpus Check
- 51 files · ~54,784 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 6 file(s) not represented in the graph (top: (none) 2, .bat 1, .ico 1)

## Summary
- 1185 nodes · 3256 edges · 62 communities (54 shown, 8 thin omitted)
- Extraction: 86% EXTRACTED · 14% INFERRED · 0% AMBIGUOUS · INFERRED: 441 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `c0cfcf42`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- pathlib
- models.py
- app/main.py
- test_api.py
- SDLCTaskManager
- SDLC Platform Implementation Guide
- save_tasks
- SDLCProjectManager
- test_project_repository.py
- TaskWorkspace
- sdlc_git.py
- post
- قرارداد عملیاتی DWS Portal و Taskloom
- sdlc_runner.py
- AgentConfig
- SDLCTask
- test_sdlc_locking.py
- guide_mcp.py
- codex_account_status
- fake_command
- TaskState
- main.jsx
- test_sdlc_git.py
- services.py
- ایرادهای شناخته‌شده (بازبینی کد — 2026-11-20)
- package.json
- TaskRequest
- Path
- git_tasks.jsx
- .save_task
- test_sdlc_lifecycle.py
- command
- secret_store.py
- execute_task
- SecretStore
- sdlc_dashboard.jsx
- FileLock
- ClaudeEventStream
- SDLCProjectConfig
- test_session_todos_run_before_automatic_delivery_and_new_branches
- github_commit_push
- test_sdlc_approval.py
- App
- markdown.jsx
- commit_and_push
- codex_command
- CodexEventStream
- جریان SDLC
- Taskloom
- test_automatic_delivery_completes_before_releasing_the_next_todo
- os
- test_command_stdin.py
- delete_task
- test_git_commit_skips_hooks_when_nothing_is_staged
- lifespan
- StageTransitionRequest
- نقشهٔ نام‌های رابط کاربری
- dashboard.jsx
- test_command_resolves_relative_executable_from_working_directory
- test_selected_agent_status_exposes_claude_auth_without_sensitive_fields
- test_load_tasks_keeps_interrupted_sessions_when_storage_is_unavailable

## God Nodes (most connected - your core abstractions)
1. `TaskState` - 95 edges
2. `RunStatus` - 78 edges
3. `SDLCProjectConfig` - 65 edges
4. `SDLCTaskManager` - 64 edges
5. `SDLCTask` - 53 edges
6. `AgentConfig` - 42 edges
7. `run_cli_stage()` - 40 edges
8. `command()` - 39 edges
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

## Communities (62 total, 8 thin omitted)

### Community 0 - "pathlib"
Cohesion: 0.06
Nodes (19): kill_process_tree(), process_image(), stop_if_same_program(), record_agent_process(), started(), command_path(), get_data_separator(), main() (+11 more)

### Community 1 - "models.py"
Cohesion: 0.07
Nodes (19): create_sdlc_task(), BranchSwitchRequest, ChatRequest, CommitRequest, GitProvider, HumanInterventionResponse, McpFailureMode, McpStatus (+11 more)

### Community 2 - "app/main.py"
Cohesion: 0.08
Nodes (34): codex_status(), _default_project_path(), defaults(), delete_profile(), dws_test_defaults(), get_role_knowledge(), get_sdlc_project(), get_sdlc_task() (+26 more)

### Community 3 - "test_api.py"
Cohesion: 0.09
Nodes (32): local_test_setup_repo(), test_branch_list_exposes_local_and_origin_branches(), test_branch_switch_rejects_invalid_base_branch(), test_branch_switch_rejects_invalid_branch_name(), test_branch_switch_uses_existing_branch_or_creates_a_missing_one(), test_create_task_returns_a_confirmation_code_for_a_dirty_current_branch(), test_defaults_can_be_overridden_for_another_project(), test_detect_tests_prefers_the_node_test_script_over_a_generic_tests_directory() (+24 more)

### Community 4 - "SDLCTaskManager"
Cohesion: 0.10
Nodes (3): SDLCTaskManager, صندوق انسانی (human inbox), test_only_one_server_owns_a_data_directory()

### Community 5 - "SDLC Platform Implementation Guide"
Cohesion: 0.06
Nodes (34): 1. Internal Scheduler/Loop, 2. Human Intervention System, 3. Structured Agent Outputs, 4. Project Configuration, Agent Types, API Integration, Architecture, Backend Tests (+26 more)

### Community 6 - "save_tasks"
Cohesion: 0.12
Nodes (22): add_todo(), advance_todo_queue(), create_task(), discard_todo(), dispatch_next_todo(), due_todos(), load_role_knowledge(), pending_todos() (+14 more)

### Community 7 - "SDLCProjectManager"
Cohesion: 0.12
Nodes (12): SDLCProjectManager, 🟡 کیفیت و نگهداری, test_legacy_project_token_is_copied_to_the_migrated_agents(), test_saved_project_with_default_github_config_loads_again(), api(), project_with_token(), test_api_never_returns_the_token(), test_deleting_a_project_deletes_its_tokens() (+4 more)

### Community 8 - "test_project_repository.py"
Cohesion: 0.16
Nodes (20): RepositoryConfig, api(), existing(), git(), make_task(), project_with(), remote(), run() (+12 more)

### Community 9 - "TaskWorkspace"
Cohesion: 0.14
Nodes (28): agentLabelFor(), apiError(), defaultBaseBranch(), loadWorkspaceState(), taskBranchFor(), taskIdForBranch(), TaskWorkspace(), action() (+20 more)

### Community 10 - "sdlc_git.py"
Cohesion: 0.15
Nodes (18): prepare_stage_repository(), auth_args(), clean_github_url(), create_github_repository(), create_pull_request(), describe_new_repository(), ensure_workspace(), github_api() (+10 more)

### Community 11 - "post"
Cohesion: 0.08
Nodes (21): approve_sdlc_task(), commit(), complete_automatic_delivery(), create_human_intervention_request(), create_sdlc_project(), get_state(), merge_request(), push() (+13 more)

### Community 12 - "قرارداد عملیاتی DWS Portal و Taskloom"
Cohesion: 0.07
Nodes (29): frontend, gate اصلی backend, Locust, MCP دانش پروژه, MCP مستقل پروژه, suite قدیمی, الزامی, قرارداد عملیاتی DWS Portal و Taskloom (+21 more)

### Community 13 - "sdlc_runner.py"
Cohesion: 0.14
Nodes (18): AgentType, Change, TestResults, folder_changes(), parse_agent_report(), readable_dirs(), _recommendations(), run_cli_stage() (+10 more)

### Community 14 - "AgentConfig"
Cohesion: 0.19
Nodes (17): AgentConfig, StageRunner, resolve_runner(), fake_agent(), install(), make_task(), project(), report() (+9 more)

### Community 15 - "SDLCTask"
Cohesion: 0.11
Nodes (13): AgentResult, HumanIntervention, SDLCTask, _feedback_text(), OllamaAgentRunner, ذخیره‌سازی, ماژول‌ها, معماری Taskloom (+5 more)

### Community 16 - "test_sdlc_locking.py"
Cohesion: 0.13
Nodes (16): _read_text_with_retry(), TaskConflictError, هم‌زمانی (`backend/app/file_lock.py`), ✅ رفع‌شده در مرحلهٔ ۷ — قفل فایل (2026-11-20), make_task(), manager(), run(), run_in_new_loop() (+8 more)

### Community 17 - "guide_mcp.py"
Cohesion: 0.17
Nodes (7): Guide, GuideCatalog, main(), McpServer, serve(), tool_definitions(), test_guide_catalog_reads_and_searches_only_markdown_roots()

### Community 18 - "codex_account_status"
Cohesion: 0.08
Nodes (9): agent_account_status(), codex_account_status(), _codex_account_status(), codex_account_status_payload(), _command_sync(), read_output(), test_codex_account_status_payload_omits_account_email_and_keeps_usage_data(), test_codex_account_status_reports_process_start_errors() (+1 more)

### Community 19 - "fake_command"
Cohesion: 0.08
Nodes (13): test_claude_account_status_uses_cli_json_and_omits_identity(), test_claude_mcp_preflight_uses_its_native_command_and_rejects_unavailable_entries(), test_creates_merge_request_and_returns_url(), test_dirty_current_task_branch_requires_explicit_confirmation(), test_dirty_worktree_cannot_be_carried_to_a_different_task_branch(), test_execute_task_checks_out_an_existing_task_branch(), test_mcp_preflight_reports_unavailable_states(), test_mcp_preflight_requires_configured_and_enabled_entry() (+5 more)

### Community 20 - "TaskState"
Cohesion: 0.15
Nodes (19): load_tasks(), RunStatus, TaskState, test_continue_task_resumes_same_codex_session_and_retests(), test_follow_up_is_queued_for_a_stopped_codex_session(), fake_continue(), test_future_todo_is_persisted_without_running_early(), test_generate_commit_message_uses_the_task_codex_session() (+11 more)

### Community 21 - "main.jsx"
Cohesion: 0.13
Nodes (19): مودال‌ها, CodePane(), DiffViewer(), DirectionalOutput(), extensionFor(), FilePreview(), initial, languageFor() (+11 more)

### Community 22 - "test_sdlc_git.py"
Cohesion: 0.18
Nodes (16): api(), git(), make_repo(), make_task(), run(), test_commit_push_commits_task_changes_and_pushes_the_branch(), test_commit_push_refuses_when_repo_left_the_task_branch(), test_create_pr_requires_push_then_opens_pr_with_stage_summary() (+8 more)

### Community 23 - "services.py"
Cohesion: 0.10
Nodes (6): detect_tests(), _mcp_config(), preflight_project_mcp(), split_command(), test_plan(), test_working_directory()

### Community 24 - "ایرادهای شناخته‌شده (بازبینی کد — 2026-11-20)"
Cohesion: 0.09
Nodes (18): workspace_tree(), visit(), API, SDLC, تسک کلاسیک (Codex / Claude Code), نمونه, ایرادهای شناخته‌شده (بازبینی کد — 2026-11-20), 🔴 بحرانی — سیستم را از کار می‌اندازد (+10 more)

### Community 25 - "package.json"
Cohesion: 0.13
Nodes (18): dependencies, lucide-react@^0.294.0, react@^18.2.0, react-dom@^18.2.0, vite@^5.0.0, @vitejs/plugin-react@^5.0.0, name, private (+10 more)

### Community 26 - "TaskRequest"
Cohesion: 0.12
Nodes (11): TaskRequest, build_prompt(), test_build_prompt_requires_reviewing_markdown_after_changes(), test_build_prompt_uses_dws_mcp_for_context_but_not_test_evidence(), test_execute_task_creates_the_task_branch_from_selected_base(), test_execute_task_keeps_the_complete_failed_test_output(), test_execute_task_reuses_confirmed_dirty_current_branch_without_switching(), test_new_tasks_use_the_tasks_branch_prefix() (+3 more)

### Community 27 - "Path"
Cohesion: 0.15
Nodes (10): prepare_tests(), read_workspace_docx(), read_workspace_text(), run_test_setup(), test_setup_commands(), workspace_changes(), workspace_diff(), workspace_file() (+2 more)

### Community 28 - "git_tasks.jsx"
Cohesion: 0.16
Nodes (7): GitTaskList(), gitTaskRows(), Clock(), getInitialTheme(), nextTheme(), THEMES, formatTime()

### Community 29 - ".save_task"
Cohesion: 0.31
Nodes (9): SDLCStatus, make_task(), run(), test_auto_resume_reruns_without_asking(), test_command_reports_the_started_pid(), test_interrupted_running_tasks_go_to_the_inbox_once(), test_orphaned_agent_is_checked_and_reported(), test_resume_answer_reruns_the_interrupted_stage() (+1 more)

### Community 30 - "test_sdlc_lifecycle.py"
Cohesion: 0.27
Nodes (14): build_stage_prompt(), stage_feedback(), finish_analysis(), make_task(), run(), test_analysis_feedback_reruns_analysis_with_the_feedback_in_its_prompt(), test_analysis_gate_asks_a_human_and_approval_starts_development(), test_answer_to_an_agent_question_reruns_that_stage() (+6 more)

### Community 31 - "command"
Cohesion: 0.19
Nodes (9): fetch_origin(), git_root(), has_remote(), prepare_task_branch(), base_branch_ref(), command(), git_branches(), switch_git_branch() (+1 more)

### Community 32 - "secret_store.py"
Cohesion: 0.16
Nodes (4): replace_with_retry(), _Blob, _dpapi(), test_replace_retries_transient_windows_permission_errors()

### Community 33 - "execute_task"
Cohesion: 0.15
Nodes (11): RevisionRequest, agent_error_detail(), cleanup_owned_test_artifacts(), continue_task(), execute_task(), mcp_runtime_issue(), refresh_git(), resolve_guides() (+3 more)

### Community 34 - "SecretStore"
Cohesion: 0.26
Nodes (3): SecretStore, test_store_roundtrip_without_plaintext_on_disk(), test_windows_store_uses_dpapi()

### Community 35 - "sdlc_dashboard.jsx"
Cohesion: 0.24
Nodes (11): agentTypes, DEFAULT_REPOSITORY, interventionHints, readJsonOrThrow(), RepositorySettings(), responseOptionLabels, SDLCDashboard(), sdlcStages (+3 more)

### Community 36 - "FileLock"
Cohesion: 0.21
Nodes (3): FileLock, LockTimeout, test_file_lock_excludes_another_process()

### Community 37 - "ClaudeEventStream"
Cohesion: 0.26
Nodes (5): claude_command(), claude_response(), _claude_text_blocks(), ClaudeEventStream, test_claude_stream_json_preserves_session_final_response_and_live_activity()

### Community 38 - "SDLCProjectConfig"
Cohesion: 0.23
Nodes (4): SDLCProjectConfig, other_stage_folders(), test_each_stage_has_its_own_default_folder_and_repo_name(), manager()

### Community 39 - "test_session_todos_run_before_automatic_delivery_and_new_branches"
Cohesion: 0.17
Nodes (4): test_due_todos_skip_future_deadlines_without_blocking_ready_work(), fake_create_task(), test_scheduler_dispatch_releases_only_explicitly_scheduled_work(), test_session_todos_run_before_automatic_delivery_and_new_branches()

### Community 40 - "github_commit_push"
Cohesion: 0.24
Nodes (5): github_commit_push(), _github_context(), github_create_pr(), GitHubActionRequest, validate_github()

### Community 41 - "test_sdlc_approval.py"
Cohesion: 0.24
Nodes (5): ProjectWorkflowConfig, make_task(), test_approve_endpoint_marks_task_done_only_from_pending_approval(), test_last_stage_moves_task_to_pending_approval(), setup()

### Community 42 - "App"
Cohesion: 0.18
Nodes (7): App(), addWorkspace(), moveBoardTask(), saveRoleKnowledge(), loadBoardAssignments(), loadWorkspaces(), newWorkspace()

### Community 43 - "markdown.jsx"
Cohesion: 0.42
Nodes (8): inlineMarkdown(), isBlockStart(), isTableDivider(), MarkdownPreview(), renderBlocks(), safeExternalUrl(), splitCells(), resolveMarkdownAsset()

### Community 44 - "commit_and_push"
Cohesion: 0.22
Nodes (6): TaskRepo, commit_and_push(), commit_message(), push_url(), redact(), test_push_url_embeds_token_only_for_github()

### Community 45 - "codex_command"
Cohesion: 0.22
Nodes (5): codex_command(), codex_response(), run_agent_command(), test_codex_response_reads_thread_and_final_message_from_jsonl(), test_codex_large_prompts_use_stdin_and_preserve_streamed_events()

### Community 47 - "جریان SDLC"
Cohesion: 0.25
Nodes (8): Git و GitHub (`backend/app/sdlc_git.py`), بازیابی پس از restart, جریان SDLC, حلقهٔ بازبینی, ریپوی هر مرحله (`AgentConfig.repository`), عامل‌ها (اجراکنندهٔ هر مرحله), ماشین وضعیت (`SDLCStatus`), نگهداری token (`backend/app/secret_store.py`)

### Community 48 - "Taskloom"
Cohesion: 0.25
Nodes (7): Taskloom, دسترسی به راهنماها با MCP, راه‌اندازی, ساخت فایل اجرایی ویندوز, مسیر دانش نقش‌ها, نگه‌داری و ادامهٔ گفت‌وگو, چه کاری انجام می‌دهد؟

### Community 49 - "test_automatic_delivery_completes_before_releasing_the_next_todo"
Cohesion: 0.29
Nodes (3): test_automatic_delivery_completes_before_releasing_the_next_todo(), fake_commit(), test_automatic_delivery_generates_a_commit_message_when_enabled()

### Community 52 - "delete_task"
Cohesion: 0.33
Nodes (3): delete_sdlc_project(), delete_task(), delete_todo()

### Community 53 - "test_git_commit_skips_hooks_when_nothing_is_staged"
Cohesion: 0.33
Nodes (3): test_git_commit_skips_hooks_when_nothing_is_staged(), test_git_commit_stages_changes_before_running_commit(), fake_refresh()

### Community 56 - "نقشهٔ نام‌های رابط کاربری"
Cohesion: 0.40
Nodes (4): بخش‌های M3 (جزئیات تسک), مراحل M4 (فرم پروژه), نقشهٔ نام‌های رابط کاربری, پیام‌های مرورگر (`alert`)

### Community 57 - "dashboard.jsx"
Cohesion: 0.60
Nodes (4): DashboardPages(), stages, statusLabel(), taskTitle()

### Community 59 - "test_selected_agent_status_exposes_claude_auth_without_sensitive_fields"
Cohesion: 0.50
Nodes (3): test_codex_status_exposes_account_limits_usage_and_models(), fake_status(), test_selected_agent_status_exposes_claude_auth_without_sensitive_fields()

## Knowledge Gaps
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `TaskState` connect `TaskState` to `models.py`, `app/main.py`, `test_api.py`, `SDLCTaskManager`, `save_tasks`, `SDLCProjectManager`, `test_project_repository.py`, `post`, `sdlc_runner.py`, `AgentConfig`, `SDLCTask`, `test_sdlc_locking.py`, `fake_command`, `test_sdlc_git.py`, `services.py`, `TaskRequest`, `Path`, `.save_task`, `test_sdlc_lifecycle.py`, `execute_task`, `ClaudeEventStream`, `test_session_todos_run_before_automatic_delivery_and_new_branches`, `test_sdlc_approval.py`, `codex_command`, `CodexEventStream`, `test_automatic_delivery_completes_before_releasing_the_next_todo`, `test_command_stdin.py`, `test_git_commit_skips_hooks_when_nothing_is_staged`?**
  _High betweenness centrality (0.063) - this node is a cross-community bridge._
- **Are the 29 inferred relationships involving `TaskState` (e.g. with `advance_todo_queue()` and `complete_automatic_delivery()`) actually correct?**
  _`TaskState` has 29 INFERRED edges - model-reasoned connections that need verification._
- **Should `pathlib` be split into smaller, more focused modules?**
  _Cohesion score 0.058069381598793365 - nodes in this community are weakly interconnected._
- **Why does `SDLCProjectConfig` connect `SDLCProjectConfig` to `models.py`, `app/main.py`, `SDLCTaskManager`, `SDLCProjectManager`, `test_project_repository.py`, `test_sdlc_approval.py`, `post`, `sdlc_runner.py`, `AgentConfig`, `SDLCTask`, `test_sdlc_locking.py`, `test_sdlc_git.py`, `services.py`, `.save_task`, `test_sdlc_lifecycle.py`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **Are the 63 inferred relationships involving `RunStatus` (e.g. with `advance_todo_queue()` and `complete_automatic_delivery()`) actually correct?**
  _`RunStatus` has 63 INFERRED edges - model-reasoned connections that need verification._
- **Should `models.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07397959183673469 - nodes in this community are weakly interconnected._
- **Why does `SDLCTaskManager` connect `SDLCTaskManager` to `execute_task`, `app/main.py`, `models.py`, `FileLock`, `SDLCProjectConfig`, `SDLCProjectManager`, `test_project_repository.py`, `test_sdlc_approval.py`, `AgentConfig`, `SDLCTask`, `test_sdlc_locking.py`, `TaskState`, `test_sdlc_git.py`, `services.py`, `.save_task`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._