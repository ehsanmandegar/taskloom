# Graph Report - taskloom  (2026-11-20)

## Corpus Check
- 37 files · ~40,769 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 6 file(s) not represented in the graph (top: (none) 2, .bat 1, .ico 1)

## Summary
- 838 nodes · 2037 edges · 43 communities (36 shown, 7 thin omitted)
- Extraction: 86% EXTRACTED · 14% INFERRED · 0% AMBIGUOUS · INFERRED: 275 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `b2cce62b`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- SDLCProjectConfig
- save_tasks
- main.py
- Path
- SDLC Platform Implementation Guide
- test_api.py
- app/main.py
- TaskWorkspace
- قرارداد عملیاتی DWS Portal و Taskloom
- services.py
- TaskState
- guide_mcp.py
- fake_command
- main.jsx
- command
- field_validator
- BaseModel
- Path
- workspace_tree
- package.json
- load_profiles
- App
- AgentType
- models.py
- ClaudeEventStream
- dashboard.jsx
- markdown.jsx
- test_session_todos_run_before_automatic_delivery_and_new_branches
- _codex_account_status
- git_tasks.jsx
- CodexEventStream
- codex_account_status
- Taskloom
- test_codex_account_status_uses_portable_pipes_and_waits_for_initialization
- test_automatic_delivery_completes_before_releasing_the_next_todo
- test_git_commit_skips_hooks_when_nothing_is_staged
- valid_branch_name
- test_command_resolves_relative_executable_from_working_directory
- StageTransitionRequest
- test_selected_agent_status_exposes_claude_auth_without_sensitive_fields
- test_load_tasks_keeps_interrupted_sessions_when_storage_is_unavailable
- RevisionRequest

## God Nodes (most connected - your core abstractions)
1. `TaskState` - 81 edges
2. `RunStatus` - 64 edges
3. `execute_task()` - 37 edges
4. `TaskWorkspace()` - 36 edges
5. `SDLCProjectConfig` - 29 edges
6. `SDLCTaskManager` - 29 edges
7. `AgentType` - 28 edges
8. `command()` - 26 edges
9. `save_tasks()` - 25 edges
10. `TaskRequest` - 25 edges

## Surprising Connections (you probably didn't know these)
- `ماژول‌ها` --references--> `TaskState`  [INFERRED]
  docs/architecture.md → backend/app/models.py
- `نمای کلی` --references--> `TaskState`  [INFERRED]
  docs/architecture.md → backend/app/models.py
- `ماشین وضعیت (`SDLCStatus`)` --references--> `SDLCStatus`  [INFERRED]
  docs/architecture.md → backend/app/models.py
- `تسک کلاسیک (Codex / Claude Code)` --references--> `workspace_tree()`  [INFERRED]
  docs/api.md → backend/app/services.py
- `🔴 بحرانی — سیستم را از کار می‌اندازد` --references--> `workspace_tree()`  [INFERRED]
  docs/known-issues.md → backend/app/services.py

## Import Cycles
- None detected.

## Communities (43 total, 7 thin omitted)

### Community 0 - "SDLCProjectConfig"
Cohesion: 0.06
Nodes (22): AgentConfig, AgentResult, HumanIntervention, SDLCProjectConfig, SDLCStatus, SDLCTask, BackendAgent, OllamaAgentRunner (+14 more)

### Community 1 - "save_tasks"
Cohesion: 0.06
Nodes (38): add_todo(), advance_todo_queue(), approve_sdlc_task(), commit(), create_human_intervention_request(), create_sdlc_project(), create_task(), delete_sdlc_project() (+30 more)

### Community 2 - "main.py"
Cohesion: 0.08
Nodes (12): command_path(), get_data_separator(), main(), remove_directory(), run_command(), validate_project(), configure_instance_storage(), run() (+4 more)

### Community 3 - "Path"
Cohesion: 0.06
Nodes (29): detect_tests(), test_plan(), local_test_setup_repo(), test_branch_list_exposes_local_and_origin_branches(), test_branch_switch_rejects_invalid_base_branch(), test_branch_switch_rejects_invalid_branch_name(), test_branch_switch_uses_existing_branch_or_creates_a_missing_one(), test_create_task_returns_a_confirmation_code_for_a_dirty_current_branch() (+21 more)

### Community 4 - "SDLC Platform Implementation Guide"
Cohesion: 0.06
Nodes (34): 1. Internal Scheduler/Loop, 2. Human Intervention System, 3. Structured Agent Outputs, 4. Project Configuration, Agent Types, API Integration, Architecture, Backend Tests (+26 more)

### Community 5 - "test_api.py"
Cohesion: 0.11
Nodes (20): TaskRequest, agent_error_detail(), build_prompt(), execute_task(), mcp_runtime_issue(), resolve_guides(), test_agent_error_detail_surfaces_cli_install_and_structured_failures(), test_build_prompt_requires_reviewing_markdown_after_changes() (+12 more)

### Community 6 - "app/main.py"
Cohesion: 0.09
Nodes (16): defaults(), get_role_knowledge(), get_sdlc_project(), get_sdlc_task(), health(), lifespan(), list_pending_human_interventions(), list_profiles() (+8 more)

### Community 7 - "TaskWorkspace"
Cohesion: 0.15
Nodes (27): agentLabelFor(), apiError(), defaultBaseBranch(), taskBranchFor(), taskIdForBranch(), TaskWorkspace(), action(), addTodo() (+19 more)

### Community 8 - "قرارداد عملیاتی DWS Portal و Taskloom"
Cohesion: 0.07
Nodes (29): frontend, gate اصلی backend, Locust, MCP دانش پروژه, MCP مستقل پروژه, suite قدیمی, الزامی, قرارداد عملیاتی DWS Portal و Taskloom (+21 more)

### Community 9 - "services.py"
Cohesion: 0.09
Nodes (10): agent_executable(), agent_name(), agent_response(), cleanup_owned_test_artifacts(), codex_response(), continue_task(), generate_commit_message(), _mcp_config() (+2 more)

### Community 10 - "TaskState"
Cohesion: 0.13
Nodes (22): load_tasks(), todo_destination(), RunStatus, TaskState, test_continue_task_resumes_same_codex_session_and_retests(), test_follow_up_is_queued_for_a_stopped_codex_session(), fake_continue(), test_future_todo_is_persisted_without_running_early() (+14 more)

### Community 11 - "guide_mcp.py"
Cohesion: 0.16
Nodes (7): Guide, GuideCatalog, main(), McpServer, serve(), tool_definitions(), test_guide_catalog_reads_and_searches_only_markdown_roots()

### Community 12 - "fake_command"
Cohesion: 0.09
Nodes (14): preflight_project_mcp(), task_branch_preflight(), test_claude_account_status_uses_cli_json_and_omits_identity(), test_claude_mcp_preflight_uses_its_native_command_and_rejects_unavailable_entries(), test_creates_merge_request_and_returns_url(), test_dirty_current_task_branch_requires_explicit_confirmation(), test_dirty_worktree_cannot_be_carried_to_a_different_task_branch(), test_mcp_preflight_reports_unavailable_states() (+6 more)

### Community 13 - "main.jsx"
Cohesion: 0.13
Nodes (19): CodePane(), DiffViewer(), DirectionalOutput(), extensionFor(), FilePreview(), initial, languageFor(), lineIsChanged() (+11 more)

### Community 14 - "command"
Cohesion: 0.13
Nodes (16): complete_automatic_delivery(), list_branches(), project_file_tree(), project_git_changes(), run_manual_test_setup(), switch_branch(), base_branch_ref(), command() (+8 more)

### Community 15 - "field_validator"
Cohesion: 0.13
Nodes (3): ProjectProfile, SDLCTaskRequest, TodoRequest

### Community 16 - "BaseModel"
Cohesion: 0.10
Nodes (11): Change, ChatRequest, CommitRequest, HumanInterventionResponse, ProjectWorkflowConfig, RenameTaskRequest, RoleKnowledgeSettings, SDLCTaskContext (+3 more)

### Community 17 - "Path"
Cohesion: 0.15
Nodes (11): project_file(), project_file_diff(), prepare_tests(), read_workspace_docx(), read_workspace_text(), run_test_setup(), test_setup_commands(), test_working_directory() (+3 more)

### Community 18 - "workspace_tree"
Cohesion: 0.12
Nodes (13): workspace_tree(), visit(), API, SDLC, تسک کلاسیک (Codex / Claude Code), نمونه, ایرادهای شناخته‌شده (بازبینی کد — 2026-11-20), 🔴 بحرانی — سیستم را از کار می‌اندازد (+5 more)

### Community 19 - "package.json"
Cohesion: 0.14
Nodes (16): dependencies, lucide-react@^0.294.0, react-dom@^18.2.0, vite@^5.0.0, @vitejs/plugin-react@^5.0.0, name, private, scripts (+8 more)

### Community 20 - "load_profiles"
Cohesion: 0.16
Nodes (12): _default_project_path(), delete_profile(), dws_test_defaults(), load_profiles(), migrate_legacy_test_settings(), profiles_path(), put_profile(), put_role_knowledge() (+4 more)

### Community 21 - "App"
Cohesion: 0.15
Nodes (10): App(), addWorkspace(), moveBoardTask(), saveRoleKnowledge(), loadBoardAssignments(), loadWorkspaces(), newWorkspace(), getInitialTheme() (+2 more)

### Community 22 - "AgentType"
Cohesion: 0.20
Nodes (7): AgentType, initial_agent_args(), resume_agent_args(), test_claude_commands_start_and_resume_the_exact_session_with_safe_edit_permissions(), test_codex_large_prompts_use_stdin_and_preserve_streamed_events(), test_command_receives_large_utf8_stdin_without_shell_expansion(), test_command_timeout_does_not_wait_for_stdin_consumption()

### Community 23 - "models.py"
Cohesion: 0.29
Nodes (8): create_sdlc_task(), project_defaults(), GitProvider, McpFailureMode, McpStatus, ProjectDefaults, TaskRole, test_defaults_can_be_overridden_for_another_project()

### Community 24 - "ClaudeEventStream"
Cohesion: 0.26
Nodes (5): claude_command(), claude_response(), _claude_text_blocks(), ClaudeEventStream, test_claude_stream_json_preserves_session_final_response_and_live_activity()

### Community 25 - "dashboard.jsx"
Cohesion: 0.19
Nodes (10): react@^18.2.0, DashboardPages(), stages, statusLabel(), taskTitle(), agentTypes, SDLCDashboard(), sdlcStages (+2 more)

### Community 26 - "markdown.jsx"
Cohesion: 0.29
Nodes (8): inlineMarkdown(), isBlockStart(), isTableDivider(), MarkdownPreview(), renderBlocks(), safeExternalUrl(), splitCells(), resolveMarkdownAsset()

### Community 27 - "test_session_todos_run_before_automatic_delivery_and_new_branches"
Cohesion: 0.17
Nodes (4): test_due_todos_skip_future_deadlines_without_blocking_ready_work(), fake_create_task(), test_scheduler_dispatch_releases_only_explicitly_scheduled_work(), test_session_todos_run_before_automatic_delivery_and_new_branches()

### Community 28 - "_codex_account_status"
Cohesion: 0.18
Nodes (5): _codex_account_status(), codex_account_status_payload(), _command_sync(), read_output(), test_codex_account_status_payload_omits_account_email_and_keeps_usage_data()

### Community 29 - "git_tasks.jsx"
Cohesion: 0.25
Nodes (4): GitTaskList(), gitTaskRows(), Clock(), formatTime()

### Community 30 - "CodexEventStream"
Cohesion: 0.36
Nodes (3): codex_command(), CodexEventStream, test_codex_jsonl_events_update_live_output_incrementally()

### Community 31 - "codex_account_status"
Cohesion: 0.22
Nodes (5): codex_status(), selected_agent_status(), agent_account_status(), codex_account_status(), test_codex_account_status_reports_process_start_errors()

### Community 32 - "Taskloom"
Cohesion: 0.25
Nodes (7): Taskloom, دسترسی به راهنماها با MCP, راه‌اندازی, ساخت فایل اجرایی ویندوز, مسیر دانش نقش‌ها, نگه‌داری و ادامهٔ گفت‌وگو, چه کاری انجام می‌دهد؟

### Community 34 - "test_automatic_delivery_completes_before_releasing_the_next_todo"
Cohesion: 0.29
Nodes (3): test_automatic_delivery_completes_before_releasing_the_next_todo(), fake_commit(), test_automatic_delivery_generates_a_commit_message_when_enabled()

### Community 35 - "test_git_commit_skips_hooks_when_nothing_is_staged"
Cohesion: 0.33
Nodes (3): test_git_commit_skips_hooks_when_nothing_is_staged(), test_git_commit_stages_changes_before_running_commit(), fake_refresh()

### Community 39 - "test_selected_agent_status_exposes_claude_auth_without_sensitive_fields"
Cohesion: 0.50
Nodes (3): test_codex_status_exposes_account_limits_usage_and_models(), fake_status(), test_selected_agent_status_exposes_claude_auth_without_sensitive_fields()

## Knowledge Gaps
- **7 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `TaskState` connect `TaskState` to `SDLCProjectConfig`, `save_tasks`, `test_automatic_delivery_completes_before_releasing_the_next_todo`, `test_git_commit_skips_hooks_when_nothing_is_staged`, `test_api.py`, `app/main.py`, `services.py`, `fake_command`, `command`, `BaseModel`, `Path`, `AgentType`, `models.py`, `ClaudeEventStream`, `test_session_todos_run_before_automatic_delivery_and_new_branches`, `CodexEventStream`?**
  _High betweenness centrality (0.067) - this node is a cross-community bridge._
- **Are the 29 inferred relationships involving `TaskState` (e.g. with `advance_todo_queue()` and `complete_automatic_delivery()`) actually correct?**
  _`TaskState` has 29 INFERRED edges - model-reasoned connections that need verification._
- **Should `SDLCProjectConfig` be split into smaller, more focused modules?**
  _Cohesion score 0.06037000973709834 - nodes in this community are weakly interconnected._
- **Why does `Backend Components` connect `SDLCProjectConfig` to `SDLC Platform Implementation Guide`?**
  _High betweenness centrality (0.064) - this node is a cross-community bridge._
- **Are the 56 inferred relationships involving `RunStatus` (e.g. with `advance_todo_queue()` and `complete_automatic_delivery()`) actually correct?**
  _`RunStatus` has 56 INFERRED edges - model-reasoned connections that need verification._
- **Should `save_tasks` be split into smaller, more focused modules?**
  _Cohesion score 0.06271186440677966 - nodes in this community are weakly interconnected._
- **Why does `Architecture` connect `SDLC Platform Implementation Guide` to `SDLCProjectConfig`?**
  _High betweenness centrality (0.062) - this node is a cross-community bridge._