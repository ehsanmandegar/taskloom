# Graph Report - taskloom  (2026-11-20)

## Corpus Check
- 46 files · ~49,694 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 6 file(s) not represented in the graph (top: (none) 2, .bat 1, .ico 1)

## Summary
- 1074 nodes · 2871 edges · 52 communities (46 shown, 6 thin omitted)
- Extraction: 86% EXTRACTED · 14% INFERRED · 0% AMBIGUOUS · INFERRED: 396 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `4a46300a`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_sdlc_git.py
- test_sdlc_lifecycle.py
- guide_mcp.py
- test_api.py
- SDLC Platform Implementation Guide
- process_tools.py
- SDLCTaskManager
- save_tasks
- TaskWorkspace
- app/main.py
- قرارداد عملیاتی DWS Portal و Taskloom
- TaskState
- AgentConfig
- models.py
- post
- test_sdlc_locking.py
- package.json
- fake_command
- FileLock
- execute_task
- SDLCProjectConfig
- SDLCTask
- field_validator
- services.py
- main.jsx
- sdlc_runner.py
- .save_task
- codex_account_status
- ProjectProfile
- TaskRequest
- command
- Path
- theme.test.js
- ClaudeEventStream
- test_session_todos_run_before_automatic_delivery_and_new_branches
- App
- complete_automatic_delivery
- CodexEventStream
- markdown.jsx
- sdlc_dashboard.jsx
- Taskloom
- git_commit
- StageTransitionRequest
- test_sdlc_approval.py
- جریان SDLC
- git_tasks.jsx
- lifespan
- HumanInterventionResponse
- test_command_resolves_relative_executable_from_working_directory
- test_selected_agent_status_exposes_claude_auth_without_sensitive_fields
- test_load_tasks_keeps_interrupted_sessions_when_storage_is_unavailable

## God Nodes (most connected - your core abstractions)
1. `TaskState` - 91 edges
2. `RunStatus` - 74 edges
3. `SDLCTaskManager` - 59 edges
4. `SDLCProjectConfig` - 50 edges
5. `SDLCTask` - 49 edges
6. `execute_task()` - 37 edges
7. `AgentConfig` - 36 edges
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

## Communities (52 total, 6 thin omitted)

### Community 0 - "test_sdlc_git.py"
Cohesion: 0.06
Nodes (40): github_commit_push(), _github_context(), github_create_pr(), GitHubActionRequest, validate_github(), TaskRepo, commit_and_push(), commit_message() (+32 more)

### Community 1 - "test_sdlc_lifecycle.py"
Cohesion: 0.06
Nodes (35): RevisionRequest, build_stage_prompt(), stage_feedback(), workspace_tree(), visit(), API, SDLC, تسک کلاسیک (Codex / Claude Code) (+27 more)

### Community 2 - "guide_mcp.py"
Cohesion: 0.09
Nodes (13): Guide, GuideCatalog, main(), McpServer, serve(), tool_definitions(), configure_instance_storage(), run() (+5 more)

### Community 3 - "test_api.py"
Cohesion: 0.10
Nodes (29): local_test_setup_repo(), test_branch_list_exposes_local_and_origin_branches(), test_branch_switch_rejects_invalid_base_branch(), test_branch_switch_rejects_invalid_branch_name(), test_branch_switch_uses_existing_branch_or_creates_a_missing_one(), test_create_task_returns_a_confirmation_code_for_a_dirty_current_branch(), test_defaults_can_be_overridden_for_another_project(), test_detect_tests_prefers_the_node_test_script_over_a_generic_tests_directory() (+21 more)

### Community 4 - "SDLC Platform Implementation Guide"
Cohesion: 0.06
Nodes (34): 1. Internal Scheduler/Loop, 2. Human Intervention System, 3. Structured Agent Outputs, 4. Project Configuration, Agent Types, API Integration, Architecture, Backend Tests (+26 more)

### Community 5 - "process_tools.py"
Cohesion: 0.09
Nodes (13): kill_process_tree(), process_image(), stop_if_same_program(), record_agent_process(), started(), command_path(), get_data_separator(), main() (+5 more)

### Community 6 - "SDLCTaskManager"
Cohesion: 0.10
Nodes (3): SDLCTaskManager, صندوق انسانی (human inbox), test_only_one_server_owns_a_data_directory()

### Community 7 - "save_tasks"
Cohesion: 0.12
Nodes (22): add_todo(), advance_todo_queue(), commit(), create_task(), discard_todo(), dispatch_next_todo(), due_todos(), load_role_knowledge() (+14 more)

### Community 8 - "TaskWorkspace"
Cohesion: 0.13
Nodes (29): agentLabelFor(), apiError(), defaultBaseBranch(), DirectionalOutput(), loadWorkspaceState(), taskBranchFor(), taskIdForBranch(), TaskWorkspace() (+21 more)

### Community 9 - "app/main.py"
Cohesion: 0.12
Nodes (23): codex_status(), get_role_knowledge(), get_sdlc_project(), get_sdlc_task(), health(), list_branches(), list_pending_human_interventions(), list_sdlc_projects() (+15 more)

### Community 10 - "قرارداد عملیاتی DWS Portal و Taskloom"
Cohesion: 0.07
Nodes (29): frontend, gate اصلی backend, Locust, MCP دانش پروژه, MCP مستقل پروژه, suite قدیمی, الزامی, قرارداد عملیاتی DWS Portal و Taskloom (+21 more)

### Community 11 - "TaskState"
Cohesion: 0.13
Nodes (23): load_tasks(), todo_destination(), RunStatus, TaskState, git_push(), test_continue_task_resumes_same_codex_session_and_retests(), test_follow_up_is_queued_for_a_stopped_codex_session(), fake_continue() (+15 more)

### Community 12 - "AgentConfig"
Cohesion: 0.18
Nodes (18): AgentConfig, StageRunner, resolve_runner(), fake_agent(), install(), make_task(), project(), report() (+10 more)

### Community 13 - "models.py"
Cohesion: 0.13
Nodes (16): create_sdlc_task(), defaults(), project_defaults(), ChatRequest, CommitRequest, GitProvider, HumanIntervention, McpFailureMode (+8 more)

### Community 14 - "post"
Cohesion: 0.09
Nodes (15): approve_sdlc_task(), create_human_intervention_request(), create_sdlc_project(), delete_sdlc_project(), delete_task(), delete_todo(), get_state(), push() (+7 more)

### Community 15 - "test_sdlc_locking.py"
Cohesion: 0.14
Nodes (15): TaskConflictError, هم‌زمانی (`backend/app/file_lock.py`), ✅ رفع‌شده در مرحلهٔ ۷ — قفل فایل (2026-11-20), make_task(), manager(), run(), run_in_new_loop(), test_an_inbox_item_can_only_be_answered_once() (+7 more)

### Community 16 - "package.json"
Cohesion: 0.10
Nodes (23): dependencies, lucide-react@^0.294.0, react@^18.2.0, react-dom@^18.2.0, vite@^5.0.0, @vitejs/plugin-react@^5.0.0, name, private (+15 more)

### Community 17 - "fake_command"
Cohesion: 0.08
Nodes (13): test_claude_account_status_uses_cli_json_and_omits_identity(), test_claude_mcp_preflight_uses_its_native_command_and_rejects_unavailable_entries(), test_creates_merge_request_and_returns_url(), test_dirty_current_task_branch_requires_explicit_confirmation(), test_dirty_worktree_cannot_be_carried_to_a_different_task_branch(), test_execute_task_keeps_the_complete_failed_test_output(), test_execute_task_reuses_confirmed_dirty_current_branch_without_switching(), test_mcp_preflight_reports_unavailable_states() (+5 more)

### Community 18 - "FileLock"
Cohesion: 0.11
Nodes (5): FileLock, LockTimeout, replace_with_retry(), test_file_lock_excludes_another_process(), test_replace_retries_transient_windows_permission_errors()

### Community 19 - "execute_task"
Cohesion: 0.15
Nodes (19): AgentType, agent_executable(), agent_name(), agent_response(), cleanup_owned_test_artifacts(), codex_response(), continue_task(), execute_task() (+11 more)

### Community 20 - "SDLCProjectConfig"
Cohesion: 0.12
Nodes (6): SDLCProjectConfig, SDLCProjectManager, Backend Components, test_saved_project_with_default_github_config_loads_again(), setup(), manager()

### Community 21 - "SDLCTask"
Cohesion: 0.12
Nodes (10): AgentResult, SDLCTask, _feedback_text(), OllamaAgentRunner, ذخیره‌سازی, ماژول‌ها, معماری Taskloom, نمای کلی (+2 more)

### Community 22 - "field_validator"
Cohesion: 0.11
Nodes (4): BranchSwitchRequest, SDLCTaskRequest, TodoRequest, valid_branch_name()

### Community 23 - "services.py"
Cohesion: 0.10
Nodes (6): detect_tests(), _mcp_config(), preflight_project_mcp(), split_command(), test_plan(), test_working_directory()

### Community 24 - "main.jsx"
Cohesion: 0.15
Nodes (17): CodePane(), DiffViewer(), extensionFor(), FilePreview(), initial, languageFor(), lineIsChanged(), localDateTimeValue() (+9 more)

### Community 25 - "sdlc_runner.py"
Cohesion: 0.16
Nodes (10): Change, folder_changes(), parse_agent_report(), _recommendations(), run_cli_stage(), run_stage_tests(), snapshot_folder(), _string_list() (+2 more)

### Community 26 - ".save_task"
Cohesion: 0.26
Nodes (10): SDLCStatus, _read_text_with_retry(), make_task(), run(), test_auto_resume_reruns_without_asking(), test_command_reports_the_started_pid(), test_interrupted_running_tasks_go_to_the_inbox_once(), test_orphaned_agent_is_checked_and_reported() (+2 more)

### Community 27 - "codex_account_status"
Cohesion: 0.10
Nodes (6): codex_account_status(), _codex_account_status(), codex_account_status_payload(), test_codex_account_status_payload_omits_account_email_and_keeps_usage_data(), test_codex_account_status_reports_process_start_errors(), test_codex_account_status_uses_portable_pipes_and_waits_for_initialization()

### Community 28 - "ProjectProfile"
Cohesion: 0.15
Nodes (14): _default_project_path(), delete_profile(), dws_test_defaults(), list_profiles(), load_profiles(), migrate_legacy_test_settings(), profiles_path(), put_profile() (+6 more)

### Community 29 - "TaskRequest"
Cohesion: 0.12
Nodes (11): TaskRequest, build_prompt(), test_build_prompt_requires_reviewing_markdown_after_changes(), test_build_prompt_uses_dws_mcp_for_context_but_not_test_evidence(), test_execute_task_checks_out_an_existing_task_branch(), test_execute_task_creates_the_task_branch_from_selected_base(), test_new_tasks_use_the_tasks_branch_prefix(), test_parallel_tasks_require_separate_project_or_worktree_paths() (+3 more)

### Community 30 - "command"
Cohesion: 0.12
Nodes (9): agent_account_status(), base_branch_ref(), command(), _command_sync(), read_output(), git_branches(), switch_git_branch(), task_branch_preflight() (+1 more)

### Community 31 - "Path"
Cohesion: 0.18
Nodes (9): prepare_tests(), read_workspace_docx(), read_workspace_text(), run_test_setup(), test_setup_commands(), workspace_diff(), workspace_file(), workspace_path() (+1 more)

### Community 32 - "theme.test.js"
Cohesion: 0.20
Nodes (6): Clock(), resolveMarkdownAsset(), getInitialTheme(), nextTheme(), THEMES, formatTime()

### Community 33 - "ClaudeEventStream"
Cohesion: 0.26
Nodes (5): claude_command(), claude_response(), _claude_text_blocks(), ClaudeEventStream, test_claude_stream_json_preserves_session_final_response_and_live_activity()

### Community 34 - "test_session_todos_run_before_automatic_delivery_and_new_branches"
Cohesion: 0.17
Nodes (4): test_due_todos_skip_future_deadlines_without_blocking_ready_work(), fake_create_task(), test_scheduler_dispatch_releases_only_explicitly_scheduled_work(), test_session_todos_run_before_automatic_delivery_and_new_branches()

### Community 35 - "App"
Cohesion: 0.18
Nodes (7): App(), addWorkspace(), moveBoardTask(), saveRoleKnowledge(), loadBoardAssignments(), loadWorkspaces(), newWorkspace()

### Community 36 - "complete_automatic_delivery"
Cohesion: 0.22
Nodes (5): complete_automatic_delivery(), test_automatic_delivery_completes_before_releasing_the_next_todo(), fake_commit(), test_automatic_delivery_generates_a_commit_message_when_enabled(), test_uncommitted_changes_hold_the_todo_queue_without_auto_commit()

### Community 37 - "CodexEventStream"
Cohesion: 0.36
Nodes (3): codex_command(), CodexEventStream, test_codex_jsonl_events_update_live_output_incrementally()

### Community 38 - "markdown.jsx"
Cohesion: 0.54
Nodes (7): inlineMarkdown(), isBlockStart(), isTableDivider(), MarkdownPreview(), renderBlocks(), safeExternalUrl(), splitCells()

### Community 39 - "sdlc_dashboard.jsx"
Cohesion: 0.29
Nodes (6): agentTypes, interventionHints, readJsonOrThrow(), responseOptionLabels, SDLCDashboard(), sdlcStages

### Community 40 - "Taskloom"
Cohesion: 0.25
Nodes (7): Taskloom, دسترسی به راهنماها با MCP, راه‌اندازی, ساخت فایل اجرایی ویندوز, مسیر دانش نقش‌ها, نگه‌داری و ادامهٔ گفت‌وگو, چه کاری انجام می‌دهد؟

### Community 41 - "git_commit"
Cohesion: 0.33
Nodes (4): git_commit(), test_git_commit_skips_hooks_when_nothing_is_staged(), test_git_commit_stages_changes_before_running_commit(), fake_refresh()

### Community 42 - "StageTransitionRequest"
Cohesion: 0.33
Nodes (3): transition_sdlc_task(), StageTransitionRequest, 🟡 کیفیت و نگهداری

### Community 43 - "test_sdlc_approval.py"
Cohesion: 0.53
Nodes (4): ProjectWorkflowConfig, make_task(), test_approve_endpoint_marks_task_done_only_from_pending_approval(), test_last_stage_moves_task_to_pending_approval()

### Community 44 - "جریان SDLC"
Cohesion: 0.33
Nodes (6): Git و GitHub (`backend/app/sdlc_git.py`), بازیابی پس از restart, جریان SDLC, حلقهٔ بازبینی, عامل‌ها (اجراکنندهٔ هر مرحله), ماشین وضعیت (`SDLCStatus`)

### Community 49 - "test_selected_agent_status_exposes_claude_auth_without_sensitive_fields"
Cohesion: 0.50
Nodes (3): test_codex_status_exposes_account_limits_usage_and_models(), fake_status(), test_selected_agent_status_exposes_claude_auth_without_sensitive_fields()

## Knowledge Gaps
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SDLCTaskManager` connect `SDLCTaskManager` to `test_sdlc_git.py`, `test_sdlc_lifecycle.py`, `app/main.py`, `TaskState`, `AgentConfig`, `models.py`, `test_sdlc_approval.py`, `test_sdlc_locking.py`, `FileLock`, `SDLCProjectConfig`, `SDLCTask`, `field_validator`, `services.py`, `.save_task`?**
  _High betweenness centrality (0.066) - this node is a cross-community bridge._
- **Are the 29 inferred relationships involving `TaskState` (e.g. with `advance_todo_queue()` and `complete_automatic_delivery()`) actually correct?**
  _`TaskState` has 29 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_sdlc_git.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06189640035118525 - nodes in this community are weakly interconnected._
- **Why does `TaskState` connect `TaskState` to `test_sdlc_git.py`, `test_sdlc_lifecycle.py`, `test_api.py`, `SDLCTaskManager`, `save_tasks`, `app/main.py`, `AgentConfig`, `models.py`, `post`, `test_sdlc_locking.py`, `fake_command`, `execute_task`, `SDLCTask`, `services.py`, `.save_task`, `TaskRequest`, `Path`, `ClaudeEventStream`, `test_session_todos_run_before_automatic_delivery_and_new_branches`, `complete_automatic_delivery`, `CodexEventStream`, `git_commit`, `test_sdlc_approval.py`?**
  _High betweenness centrality (0.063) - this node is a cross-community bridge._
- **Are the 61 inferred relationships involving `RunStatus` (e.g. with `advance_todo_queue()` and `complete_automatic_delivery()`) actually correct?**
  _`RunStatus` has 61 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_sdlc_lifecycle.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06462585034013606 - nodes in this community are weakly interconnected._
- **Why does `Backend Components` connect `SDLCProjectConfig` to `SDLC Platform Implementation Guide`, `SDLCTaskManager`, `AgentConfig`, `models.py`, `SDLCTask`, `.save_task`?**
  _High betweenness centrality (0.043) - this node is a cross-community bridge._