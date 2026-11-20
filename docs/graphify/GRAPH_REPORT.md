# Graph Report - taskloom  (2026-11-20)

## Corpus Check
- 40 files · ~43,905 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 6 file(s) not represented in the graph (top: (none) 2, .bat 1, .ico 1)

## Summary
- 913 nodes · 2342 edges · 57 communities (46 shown, 11 thin omitted)
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 309 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `8d94aaa9`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- guide_mcp.py
- app/main.py
- SDLC Platform Implementation Guide
- SDLCTaskManager
- TaskWorkspace
- قرارداد عملیاتی DWS Portal و Taskloom
- Path
- test_sdlc_lifecycle.py
- execute_task
- TaskState
- field_validator
- main.jsx
- save_tasks
- models.py
- test_sdlc_runner.py
- workspace_tree
- test_api.py
- package.json
- SDLCProjectConfig
- services.py
- get_state
- Path
- sdlc_runner.py
- command
- AgentConfig
- SDLCTask
- theme.test.js
- ProjectProfile
- ClaudeEventStream
- test_session_todos_run_before_automatic_delivery_and_new_branches
- AgentType
- _codex_account_status
- App
- load_role_knowledge
- CodexEventStream
- preflight_project_mcp
- SDLCStatus
- test_plan
- run_test_setup
- run_stage_tests
- markdown.jsx
- Taskloom
- test_codex_account_status_uses_portable_pipes_and_waits_for_initialization
- continue_task
- sdlc_dashboard.jsx
- test_automatic_delivery_completes_before_releasing_the_next_todo
- git_push
- StageTransitionRequest
- git_tasks.jsx
- lifespan
- HumanInterventionResponse
- codex_account_status
- dashboard.jsx
- test_command_resolves_relative_executable_from_working_directory
- test_selected_agent_status_exposes_claude_auth_without_sensitive_fields
- test_new_tasks_use_the_tasks_branch_prefix

## God Nodes (most connected - your core abstractions)
1. `TaskState` - 85 edges
2. `RunStatus` - 68 edges
3. `SDLCTaskManager` - 41 edges
4. `SDLCProjectConfig` - 40 edges
5. `execute_task()` - 37 edges
6. `TaskWorkspace()` - 36 edges
7. `SDLCTask` - 33 edges
8. `AgentConfig` - 31 edges
9. `run_cli_stage()` - 31 edges
10. `AgentType` - 30 edges

## Surprising Connections (you probably didn't know these)
- `ماشین وضعیت (`SDLCStatus`)` --references--> `SDLCStatus`  [INFERRED]
  docs/architecture.md → backend/app/models.py
- `عامل‌ها (اجراکنندهٔ هر مرحله)` --references--> `AgentConfig`  [INFERRED]
  docs/architecture.md → backend/app/models.py
- `✅ رفع‌شده در مرحلهٔ ۳ (2026-11-20)` --references--> `test_plan()`  [INFERRED]
  docs/known-issues.md → backend/app/services.py
- `ماژول‌ها` --references--> `TaskState`  [INFERRED]
  docs/architecture.md → backend/app/models.py
- `نمای کلی` --references--> `TaskState`  [INFERRED]
  docs/architecture.md → backend/app/models.py

## Import Cycles
- None detected.

## Communities (57 total, 11 thin omitted)

### Community 0 - "guide_mcp.py"
Cohesion: 0.06
Nodes (19): Guide, GuideCatalog, main(), McpServer, serve(), tool_definitions(), command_path(), get_data_separator() (+11 more)

### Community 1 - "app/main.py"
Cohesion: 0.07
Nodes (26): approve_sdlc_task(), codex_status(), create_human_intervention_request(), create_sdlc_project(), defaults(), delete_sdlc_project(), get_role_knowledge(), get_sdlc_project() (+18 more)

### Community 2 - "SDLC Platform Implementation Guide"
Cohesion: 0.06
Nodes (34): 1. Internal Scheduler/Loop, 2. Human Intervention System, 3. Structured Agent Outputs, 4. Project Configuration, Agent Types, API Integration, Architecture, Backend Tests (+26 more)

### Community 4 - "TaskWorkspace"
Cohesion: 0.14
Nodes (28): agentLabelFor(), apiError(), defaultBaseBranch(), DirectionalOutput(), taskBranchFor(), taskIdForBranch(), TaskWorkspace(), action() (+20 more)

### Community 5 - "قرارداد عملیاتی DWS Portal و Taskloom"
Cohesion: 0.07
Nodes (29): frontend, gate اصلی backend, Locust, MCP دانش پروژه, MCP مستقل پروژه, suite قدیمی, الزامی, قرارداد عملیاتی DWS Portal و Taskloom (+21 more)

### Community 6 - "Path"
Cohesion: 0.07
Nodes (21): test_branch_list_exposes_local_and_origin_branches(), test_branch_switch_rejects_invalid_base_branch(), test_branch_switch_rejects_invalid_branch_name(), test_branch_switch_uses_existing_branch_or_creates_a_missing_one(), test_create_task_returns_a_confirmation_code_for_a_dirty_current_branch(), test_dirty_current_task_branch_requires_explicit_confirmation(), test_dirty_worktree_cannot_be_carried_to_a_different_task_branch(), test_follow_up_is_queued_for_a_stopped_codex_session() (+13 more)

### Community 7 - "test_sdlc_lifecycle.py"
Cohesion: 0.15
Nodes (17): RevisionRequest, build_stage_prompt(), stage_feedback(), test_command_receives_large_utf8_stdin_without_shell_expansion(), test_command_timeout_does_not_wait_for_stdin_consumption(), finish_analysis(), make_task(), run() (+9 more)

### Community 8 - "execute_task"
Cohesion: 0.14
Nodes (17): create_task(), run_task(), start_todo_task(), ChatMessage, TaskRequest, execute_task(), repository(), task_branch_preflight() (+9 more)

### Community 9 - "TaskState"
Cohesion: 0.15
Nodes (18): create_sdlc_task(), load_tasks(), stop_task(), todo_destination(), RunStatus, TaskState, test_future_todo_is_persisted_without_running_early(), test_load_tasks_keeps_interrupted_sessions_when_storage_is_unavailable() (+10 more)

### Community 10 - "field_validator"
Cohesion: 0.10
Nodes (3): SDLCTaskRequest, TodoRequest, valid_branch_name()

### Community 11 - "main.jsx"
Cohesion: 0.14
Nodes (18): CodePane(), DiffViewer(), extensionFor(), FilePreview(), initial, languageFor(), lineIsChanged(), loadWorkspaceState() (+10 more)

### Community 12 - "save_tasks"
Cohesion: 0.17
Nodes (16): add_todo(), advance_todo_queue(), commit(), discard_todo(), dispatch_next_todo(), due_todos(), pending_todos(), queue_follow_up() (+8 more)

### Community 13 - "models.py"
Cohesion: 0.15
Nodes (15): BranchSwitchRequest, Change, ChatRequest, CommitRequest, GitProvider, McpFailureMode, McpStatus, ProjectDefaults (+7 more)

### Community 14 - "test_sdlc_runner.py"
Cohesion: 0.23
Nodes (16): StageRunner, resolve_runner(), fake_agent(), install(), make_task(), project(), report(), test_agent_can_ask_a_human_or_request_a_revision() (+8 more)

### Community 15 - "workspace_tree"
Cohesion: 0.10
Nodes (17): project_file_tree(), workspace_tree(), visit(), API, SDLC, تسک کلاسیک (Codex / Claude Code), نمونه, ایرادهای شناخته‌شده (بازبینی کد — 2026-11-20) (+9 more)

### Community 16 - "test_api.py"
Cohesion: 0.13
Nodes (14): project_defaults(), build_prompt(), mcp_runtime_issue(), resolve_guides(), test_build_prompt_requires_reviewing_markdown_after_changes(), test_build_prompt_uses_dws_mcp_for_context_but_not_test_evidence(), test_claude_account_status_uses_cli_json_and_omits_identity(), test_codex_account_status_reports_process_start_errors() (+6 more)

### Community 17 - "package.json"
Cohesion: 0.12
Nodes (19): dependencies, lucide-react@^0.294.0, react@^18.2.0, react-dom@^18.2.0, vite@^5.0.0, @vitejs/plugin-react@^5.0.0, name, private (+11 more)

### Community 18 - "SDLCProjectConfig"
Cohesion: 0.15
Nodes (4): SDLCProjectConfig, SDLCProjectManager, test_saved_project_with_default_github_config_loads_again(), setup()

### Community 20 - "get_state"
Cohesion: 0.13
Nodes (11): complete_automatic_delivery(), delete_task(), delete_todo(), get_state(), merge_request(), suggest_commit_message(), task_events(), snapshots() (+3 more)

### Community 21 - "Path"
Cohesion: 0.15
Nodes (10): read_workspace_docx(), read_workspace_text(), workspace_diff(), workspace_file(), workspace_path(), workspace_preview_path(), test_workspace_diff_marks_only_the_exact_changed_line_ranges(), test_workspace_file_identifies_browser_media_and_extracts_word_text() (+2 more)

### Community 22 - "sdlc_runner.py"
Cohesion: 0.19
Nodes (10): folder_changes(), parse_agent_report(), _recommendations(), run_cli_stage(), _string_list(), agent_error_detail(), agent_executable(), agent_name() (+2 more)

### Community 23 - "command"
Cohesion: 0.16
Nodes (9): switch_branch(), base_branch_ref(), command(), git_commit(), refresh_git(), switch_git_branch(), test_git_commit_skips_hooks_when_nothing_is_staged(), test_git_commit_stages_changes_before_running_commit() (+1 more)

### Community 24 - "AgentConfig"
Cohesion: 0.22
Nodes (6): AgentConfig, AgentResult, _feedback_text(), OllamaAgentRunner, Backend Components, test_ollama_file_claims_are_proposals_not_changes()

### Community 25 - "SDLCTask"
Cohesion: 0.15
Nodes (10): SDLCTask, جریان SDLC, حلقهٔ بازبینی, ذخیره‌سازی, صندوق انسانی (human inbox), عامل‌ها (اجراکنندهٔ هر مرحله), ماشین وضعیت (`SDLCStatus`), ماژول‌ها (+2 more)

### Community 26 - "theme.test.js"
Cohesion: 0.20
Nodes (6): Clock(), resolveMarkdownAsset(), getInitialTheme(), nextTheme(), THEMES, formatTime()

### Community 27 - "ProjectProfile"
Cohesion: 0.24
Nodes (10): _default_project_path(), delete_profile(), dws_test_defaults(), load_profiles(), migrate_legacy_test_settings(), profiles_path(), put_profile(), save_profiles() (+2 more)

### Community 28 - "ClaudeEventStream"
Cohesion: 0.26
Nodes (5): claude_command(), claude_response(), _claude_text_blocks(), ClaudeEventStream, test_claude_stream_json_preserves_session_final_response_and_live_activity()

### Community 29 - "test_session_todos_run_before_automatic_delivery_and_new_branches"
Cohesion: 0.17
Nodes (4): test_due_todos_skip_future_deadlines_without_blocking_ready_work(), fake_create_task(), test_scheduler_dispatch_releases_only_explicitly_scheduled_work(), test_session_todos_run_before_automatic_delivery_and_new_branches()

### Community 30 - "AgentType"
Cohesion: 0.27
Nodes (8): AgentType, agent_response(), codex_response(), initial_agent_args(), resume_agent_args(), test_claude_commands_start_and_resume_the_exact_session_with_safe_edit_permissions(), test_codex_response_reads_thread_and_final_message_from_jsonl(), test_codex_large_prompts_use_stdin_and_preserve_streamed_events()

### Community 31 - "_codex_account_status"
Cohesion: 0.18
Nodes (5): _codex_account_status(), codex_account_status_payload(), _command_sync(), read_output(), test_codex_account_status_payload_omits_account_email_and_keeps_usage_data()

### Community 32 - "App"
Cohesion: 0.18
Nodes (7): App(), addWorkspace(), moveBoardTask(), saveRoleKnowledge(), loadBoardAssignments(), loadWorkspaces(), newWorkspace()

### Community 33 - "load_role_knowledge"
Cohesion: 0.20
Nodes (6): load_role_knowledge(), put_role_knowledge(), rename_task(), role_knowledge_path(), set_task_role(), update_sdlc_project()

### Community 34 - "CodexEventStream"
Cohesion: 0.36
Nodes (3): codex_command(), CodexEventStream, test_codex_jsonl_events_update_live_output_incrementally()

### Community 35 - "preflight_project_mcp"
Cohesion: 0.20
Nodes (5): preflight_project_mcp(), test_claude_mcp_preflight_uses_its_native_command_and_rejects_unavailable_entries(), test_creates_merge_request_and_returns_url(), test_mcp_preflight_reports_unavailable_states(), test_mcp_preflight_requires_configured_and_enabled_entry()

### Community 36 - "SDLCStatus"
Cohesion: 0.36
Nodes (5): ProjectWorkflowConfig, SDLCStatus, make_task(), test_approve_endpoint_marks_task_done_only_from_pending_approval(), test_last_stage_moves_task_to_pending_approval()

### Community 37 - "test_plan"
Cohesion: 0.22
Nodes (7): detect_tests(), test_plan(), test_working_directory(), test_detect_tests_prefers_the_node_test_script_over_a_generic_tests_directory(), test_detect_tests_uses_pytest_when_package_has_no_test_script(), test_test_plan_rejects_a_working_directory_outside_the_project(), test_test_plan_runs_the_command_from_its_configured_project_subdirectory()

### Community 38 - "run_test_setup"
Cohesion: 0.25
Nodes (6): run_test_setup(), test_setup_commands(), local_test_setup_repo(), test_manual_test_setup_requires_confirmation(), test_test_setup_rejects_non_local_database(), test_test_setup_retries_login_without_storing_sensitive_command_output()

### Community 40 - "markdown.jsx"
Cohesion: 0.54
Nodes (7): inlineMarkdown(), isBlockStart(), isTableDivider(), MarkdownPreview(), renderBlocks(), safeExternalUrl(), splitCells()

### Community 41 - "Taskloom"
Cohesion: 0.25
Nodes (7): Taskloom, دسترسی به راهنماها با MCP, راه‌اندازی, ساخت فایل اجرایی ویندوز, مسیر دانش نقش‌ها, نگه‌داری و ادامهٔ گفت‌وگو, چه کاری انجام می‌دهد؟

### Community 43 - "continue_task"
Cohesion: 0.29
Nodes (4): cleanup_owned_test_artifacts(), continue_task(), prepare_tests(), test_continue_task_resumes_same_codex_session_and_retests()

### Community 44 - "sdlc_dashboard.jsx"
Cohesion: 0.29
Nodes (5): agentTypes, interventionHints, responseOptionLabels, SDLCDashboard(), sdlcStages

### Community 45 - "test_automatic_delivery_completes_before_releasing_the_next_todo"
Cohesion: 0.29
Nodes (3): test_automatic_delivery_completes_before_releasing_the_next_todo(), fake_commit(), test_automatic_delivery_generates_a_commit_message_when_enabled()

### Community 46 - "git_push"
Cohesion: 0.33
Nodes (4): push(), git_push(), test_git_push_aborts_optional_base_merge_conflict_and_continues(), test_git_push_merges_latest_base_before_pushing()

### Community 47 - "StageTransitionRequest"
Cohesion: 0.33
Nodes (3): transition_sdlc_task(), StageTransitionRequest, 🟡 کیفیت و نگهداری

### Community 52 - "dashboard.jsx"
Cohesion: 0.60
Nodes (4): DashboardPages(), stages, statusLabel(), taskTitle()

### Community 54 - "test_selected_agent_status_exposes_claude_auth_without_sensitive_fields"
Cohesion: 0.50
Nodes (3): test_codex_status_exposes_account_limits_usage_and_models(), fake_status(), test_selected_agent_status_exposes_claude_auth_without_sensitive_fields()

## Knowledge Gaps
- **11 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `TaskState` connect `TaskState` to `app/main.py`, `SDLCTaskManager`, `Path`, `test_sdlc_lifecycle.py`, `execute_task`, `save_tasks`, `models.py`, `test_sdlc_runner.py`, `test_api.py`, `services.py`, `get_state`, `sdlc_runner.py`, `command`, `SDLCTask`, `ClaudeEventStream`, `test_session_todos_run_before_automatic_delivery_and_new_branches`, `AgentType`, `CodexEventStream`, `preflight_project_mcp`, `SDLCStatus`, `continue_task`, `test_automatic_delivery_completes_before_releasing_the_next_todo`, `git_push`?**
  _High betweenness centrality (0.069) - this node is a cross-community bridge._
- **Are the 29 inferred relationships involving `TaskState` (e.g. with `advance_todo_queue()` and `complete_automatic_delivery()`) actually correct?**
  _`TaskState` has 29 INFERRED edges - model-reasoned connections that need verification._
- **Should `guide_mcp.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05721153846153846 - nodes in this community are weakly interconnected._
- **Why does `Backend Components` connect `AgentConfig` to `SDLC Platform Implementation Guide`, `SDLCTaskManager`, `SDLCStatus`, `SDLCProjectConfig`, `SDLCTask`?**
  _High betweenness centrality (0.060) - this node is a cross-community bridge._
- **Are the 58 inferred relationships involving `RunStatus` (e.g. with `advance_todo_queue()` and `complete_automatic_delivery()`) actually correct?**
  _`RunStatus` has 58 INFERRED edges - model-reasoned connections that need verification._
- **Should `app/main.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06976744186046512 - nodes in this community are weakly interconnected._
- **Why does `Architecture` connect `SDLC Platform Implementation Guide` to `AgentConfig`?**
  _High betweenness centrality (0.058) - this node is a cross-community bridge._