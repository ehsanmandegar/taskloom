# Graph Report - taskloom  (2026-11-20)

## Corpus Check
- 39 files · ~42,225 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 6 file(s) not represented in the graph (top: (none) 2, .bat 1, .ico 1)

## Summary
- 874 nodes · 2217 edges · 44 communities (37 shown, 7 thin omitted)
- Extraction: 86% EXTRACTED · 14% INFERRED · 0% AMBIGUOUS · INFERRED: 300 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `216dc67a`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- SDLCProjectConfig
- models.py
- test_api.py
- main.py
- SDLC Platform Implementation Guide
- TaskWorkspace
- قرارداد عملیاتی DWS Portal و Taskloom
- execute_task
- app/main.py
- guide_mcp.py
- TaskState
- Path
- main.jsx
- fake_command
- services.py
- get_state
- codex_account_status
- TaskRequest
- workspace_tree
- save_tasks
- package.json
- App
- command
- ProjectProfile
- dashboard.jsx
- ClaudeEventStream
- markdown.jsx
- test_session_todos_run_before_automatic_delivery_and_new_branches
- test_command_stdin.py
- TodoItem
- CodexEventStream
- switch_git_branch
- Taskloom
- test_automatic_delivery_completes_before_releasing_the_next_todo
- delete_task
- test_git_commit_skips_hooks_when_nothing_is_staged
- lifespan
- formatTime
- test_command_resolves_relative_executable_from_working_directory
- _command_sync
- test_selected_agent_status_exposes_claude_auth_without_sensitive_fields
- test_load_tasks_keeps_interrupted_sessions_when_storage_is_unavailable
- rename_task

## God Nodes (most connected - your core abstractions)
1. `TaskState` - 83 edges
2. `RunStatus` - 66 edges
3. `execute_task()` - 37 edges
4. `TaskWorkspace()` - 36 edges
5. `SDLCProjectConfig` - 34 edges
6. `run_cli_stage()` - 31 edges
7. `SDLCTaskManager` - 31 edges
8. `AgentType` - 30 edges
9. `command()` - 28 edges
10. `AgentConfig` - 27 edges

## Surprising Connections (you probably didn't know these)
- `✅ رفع‌شده در مرحلهٔ ۳ (2026-11-20)` --references--> `test_plan()`  [INFERRED]
  docs/known-issues.md → backend/app/services.py
- `ماژول‌ها` --references--> `TaskState`  [INFERRED]
  docs/architecture.md → backend/app/models.py
- `نمای کلی` --references--> `TaskState`  [INFERRED]
  docs/architecture.md → backend/app/models.py
- `ماشین وضعیت (`SDLCStatus`)` --references--> `SDLCStatus`  [INFERRED]
  docs/architecture.md → backend/app/models.py
- `عامل‌ها (اجراکنندهٔ هر مرحله)` --references--> `AgentConfig`  [INFERRED]
  docs/architecture.md → backend/app/models.py

## Import Cycles
- None detected.

## Communities (44 total, 7 thin omitted)

### Community 0 - "SDLCProjectConfig"
Cohesion: 0.06
Nodes (39): AgentConfig, AgentResult, HumanIntervention, ProjectWorkflowConfig, SDLCProjectConfig, SDLCStatus, SDLCTask, StageRunner (+31 more)

### Community 1 - "models.py"
Cohesion: 0.06
Nodes (23): create_sdlc_task(), BranchSwitchRequest, Change, ChatRequest, CommitRequest, GitProvider, HumanInterventionResponse, McpFailureMode (+15 more)

### Community 2 - "test_api.py"
Cohesion: 0.08
Nodes (34): project_defaults(), detect_tests(), resolve_guides(), test_plan(), workspace_file(), local_test_setup_repo(), test_branch_list_exposes_local_and_origin_branches(), test_branch_switch_rejects_invalid_base_branch() (+26 more)

### Community 3 - "main.py"
Cohesion: 0.08
Nodes (12): command_path(), get_data_separator(), main(), remove_directory(), run_command(), validate_project(), configure_instance_storage(), run() (+4 more)

### Community 4 - "SDLC Platform Implementation Guide"
Cohesion: 0.06
Nodes (34): 1. Internal Scheduler/Loop, 2. Human Intervention System, 3. Structured Agent Outputs, 4. Project Configuration, Agent Types, API Integration, Architecture, Backend Tests (+26 more)

### Community 5 - "TaskWorkspace"
Cohesion: 0.15
Nodes (27): agentLabelFor(), apiError(), defaultBaseBranch(), taskBranchFor(), taskIdForBranch(), TaskWorkspace(), action(), addTodo() (+19 more)

### Community 6 - "قرارداد عملیاتی DWS Portal و Taskloom"
Cohesion: 0.07
Nodes (29): frontend, gate اصلی backend, Locust, MCP دانش پروژه, MCP مستقل پروژه, suite قدیمی, الزامی, قرارداد عملیاتی DWS Portal و Taskloom (+21 more)

### Community 7 - "execute_task"
Cohesion: 0.14
Nodes (20): AgentType, build_stage_prompt(), folder_changes(), parse_agent_report(), _recommendations(), run_cli_stage(), run_stage_tests(), snapshot_folder() (+12 more)

### Community 8 - "app/main.py"
Cohesion: 0.12
Nodes (19): defaults(), get_role_knowledge(), get_sdlc_project(), get_sdlc_task(), health(), list_pending_human_interventions(), list_sdlc_projects(), list_sdlc_tasks() (+11 more)

### Community 9 - "guide_mcp.py"
Cohesion: 0.16
Nodes (7): Guide, GuideCatalog, main(), McpServer, serve(), tool_definitions(), test_guide_catalog_reads_and_searches_only_markdown_roots()

### Community 10 - "TaskState"
Cohesion: 0.14
Nodes (21): load_tasks(), RunStatus, TaskState, test_continue_task_resumes_same_codex_session_and_retests(), test_follow_up_is_queued_for_a_stopped_codex_session(), fake_continue(), test_future_todo_is_persisted_without_running_early(), test_generate_commit_message_uses_the_task_codex_session() (+13 more)

### Community 11 - "Path"
Cohesion: 0.09
Nodes (14): project_file_diff(), project_raw_file(), run_manual_test_setup(), cleanup_owned_test_artifacts(), prepare_tests(), read_workspace_docx(), read_workspace_text(), run_test_setup() (+6 more)

### Community 12 - "main.jsx"
Cohesion: 0.13
Nodes (19): CodePane(), DiffViewer(), DirectionalOutput(), extensionFor(), FilePreview(), initial, languageFor(), lineIsChanged() (+11 more)

### Community 13 - "fake_command"
Cohesion: 0.08
Nodes (13): test_claude_account_status_uses_cli_json_and_omits_identity(), test_claude_mcp_preflight_uses_its_native_command_and_rejects_unavailable_entries(), test_creates_merge_request_and_returns_url(), test_dirty_current_task_branch_requires_explicit_confirmation(), test_dirty_worktree_cannot_be_carried_to_a_different_task_branch(), test_execute_task_reuses_confirmed_dirty_current_branch_without_switching(), test_mcp_preflight_reports_unavailable_states(), test_mcp_preflight_requires_configured_and_enabled_entry() (+5 more)

### Community 14 - "services.py"
Cohesion: 0.09
Nodes (3): _mcp_config(), preflight_project_mcp(), split_command()

### Community 15 - "get_state"
Cohesion: 0.12
Nodes (14): approve_sdlc_task(), commit(), create_human_intervention_request(), create_sdlc_project(), get_state(), merge_request(), push(), respond_to_human_intervention() (+6 more)

### Community 16 - "codex_account_status"
Cohesion: 0.10
Nodes (7): codex_status(), codex_account_status(), _codex_account_status(), codex_account_status_payload(), test_codex_account_status_payload_omits_account_email_and_keeps_usage_data(), test_codex_account_status_reports_process_start_errors(), test_codex_account_status_uses_portable_pipes_and_waits_for_initialization()

### Community 17 - "TaskRequest"
Cohesion: 0.10
Nodes (12): TaskRequest, build_prompt(), test_build_prompt_requires_reviewing_markdown_after_changes(), test_build_prompt_uses_dws_mcp_for_context_but_not_test_evidence(), test_execute_task_checks_out_an_existing_task_branch(), test_execute_task_creates_the_task_branch_from_selected_base(), test_execute_task_keeps_the_complete_failed_test_output(), test_new_tasks_use_the_tasks_branch_prefix() (+4 more)

### Community 18 - "workspace_tree"
Cohesion: 0.11
Nodes (15): project_file_tree(), workspace_tree(), visit(), API, SDLC, تسک کلاسیک (Codex / Claude Code), نمونه, ایرادهای شناخته‌شده (بازبینی کد — 2026-11-20) (+7 more)

### Community 19 - "save_tasks"
Cohesion: 0.22
Nodes (13): advance_todo_queue(), create_task(), discard_todo(), dispatch_next_todo(), queue_follow_up(), run_follow_up(), run_task(), save_tasks() (+5 more)

### Community 20 - "package.json"
Cohesion: 0.14
Nodes (16): dependencies, react@^18.2.0, react-dom@^18.2.0, vite@^5.0.0, @vitejs/plugin-react@^5.0.0, name, private, scripts (+8 more)

### Community 21 - "App"
Cohesion: 0.13
Nodes (11): App(), addWorkspace(), moveBoardTask(), saveRoleKnowledge(), loadBoardAssignments(), loadWorkspaces(), newWorkspace(), SDLCDashboard() (+3 more)

### Community 22 - "command"
Cohesion: 0.20
Nodes (12): complete_automatic_delivery(), project_git_changes(), command(), continue_task(), create_merge_request(), generate_commit_message(), git_commit(), git_push() (+4 more)

### Community 23 - "ProjectProfile"
Cohesion: 0.17
Nodes (12): _default_project_path(), delete_profile(), dws_test_defaults(), list_profiles(), load_profiles(), migrate_legacy_test_settings(), profiles_path(), put_profile() (+4 more)

### Community 24 - "dashboard.jsx"
Cohesion: 0.17
Nodes (11): lucide-react@^0.294.0, DashboardPages(), stages, statusLabel(), taskTitle(), GitTaskList(), gitTaskRows(), agentTypes (+3 more)

### Community 25 - "ClaudeEventStream"
Cohesion: 0.26
Nodes (5): claude_command(), claude_response(), _claude_text_blocks(), ClaudeEventStream, test_claude_stream_json_preserves_session_final_response_and_live_activity()

### Community 26 - "markdown.jsx"
Cohesion: 0.29
Nodes (8): inlineMarkdown(), isBlockStart(), isTableDivider(), MarkdownPreview(), renderBlocks(), safeExternalUrl(), splitCells(), resolveMarkdownAsset()

### Community 27 - "test_session_todos_run_before_automatic_delivery_and_new_branches"
Cohesion: 0.17
Nodes (4): test_due_todos_skip_future_deadlines_without_blocking_ready_work(), fake_create_task(), test_scheduler_dispatch_releases_only_explicitly_scheduled_work(), test_session_todos_run_before_automatic_delivery_and_new_branches()

### Community 28 - "test_command_stdin.py"
Cohesion: 0.18
Nodes (5): codex_response(), test_codex_response_reads_thread_and_final_message_from_jsonl(), test_codex_large_prompts_use_stdin_and_preserve_streamed_events(), test_command_receives_large_utf8_stdin_without_shell_expansion(), test_command_timeout_does_not_wait_for_stdin_consumption()

### Community 29 - "TodoItem"
Cohesion: 0.27
Nodes (6): add_todo(), due_todos(), pending_todos(), todo_destination(), todo_is_due(), TodoItem

### Community 30 - "CodexEventStream"
Cohesion: 0.36
Nodes (3): codex_command(), CodexEventStream, test_codex_jsonl_events_update_live_output_incrementally()

### Community 31 - "switch_git_branch"
Cohesion: 0.25
Nodes (5): list_branches(), switch_branch(), base_branch_ref(), git_branches(), switch_git_branch()

### Community 32 - "Taskloom"
Cohesion: 0.25
Nodes (7): Taskloom, دسترسی به راهنماها با MCP, راه‌اندازی, ساخت فایل اجرایی ویندوز, مسیر دانش نقش‌ها, نگه‌داری و ادامهٔ گفت‌وگو, چه کاری انجام می‌دهد؟

### Community 33 - "test_automatic_delivery_completes_before_releasing_the_next_todo"
Cohesion: 0.29
Nodes (3): test_automatic_delivery_completes_before_releasing_the_next_todo(), fake_commit(), test_automatic_delivery_generates_a_commit_message_when_enabled()

### Community 34 - "delete_task"
Cohesion: 0.33
Nodes (3): delete_sdlc_project(), delete_task(), delete_todo()

### Community 35 - "test_git_commit_skips_hooks_when_nothing_is_staged"
Cohesion: 0.33
Nodes (3): test_git_commit_skips_hooks_when_nothing_is_staged(), test_git_commit_stages_changes_before_running_commit(), fake_refresh()

### Community 40 - "test_selected_agent_status_exposes_claude_auth_without_sensitive_fields"
Cohesion: 0.50
Nodes (3): test_codex_status_exposes_account_limits_usage_and_models(), fake_status(), test_selected_agent_status_exposes_claude_auth_without_sensitive_fields()

## Knowledge Gaps
- **7 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `TaskState` connect `TaskState` to `SDLCProjectConfig`, `models.py`, `test_api.py`, `execute_task`, `app/main.py`, `Path`, `fake_command`, `services.py`, `get_state`, `TaskRequest`, `save_tasks`, `command`, `ClaudeEventStream`, `test_session_todos_run_before_automatic_delivery_and_new_branches`, `test_command_stdin.py`, `TodoItem`, `CodexEventStream`, `test_automatic_delivery_completes_before_releasing_the_next_todo`, `test_git_commit_skips_hooks_when_nothing_is_staged`?**
  _High betweenness centrality (0.066) - this node is a cross-community bridge._
- **Are the 29 inferred relationships involving `TaskState` (e.g. with `advance_todo_queue()` and `complete_automatic_delivery()`) actually correct?**
  _`TaskState` has 29 INFERRED edges - model-reasoned connections that need verification._
- **Should `SDLCProjectConfig` be split into smaller, more focused modules?**
  _Cohesion score 0.05554386703134862 - nodes in this community are weakly interconnected._
- **Why does `Backend Components` connect `SDLCProjectConfig` to `SDLC Platform Implementation Guide`?**
  _High betweenness centrality (0.062) - this node is a cross-community bridge._
- **Are the 57 inferred relationships involving `RunStatus` (e.g. with `advance_todo_queue()` and `complete_automatic_delivery()`) actually correct?**
  _`RunStatus` has 57 INFERRED edges - model-reasoned connections that need verification._
- **Should `models.py` be split into smaller, more focused modules?**
  _Cohesion score 0.055523085914669784 - nodes in this community are weakly interconnected._
- **Why does `Architecture` connect `SDLC Platform Implementation Guide` to `SDLCProjectConfig`?**
  _High betweenness centrality (0.060) - this node is a cross-community bridge._