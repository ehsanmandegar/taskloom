# Graph Report - taskloom  (2026-11-20)

## Corpus Check
- 44 files · ~48,018 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 6 file(s) not represented in the graph (top: (none) 2, .bat 1, .ico 1)

## Summary
- 1013 nodes · 2682 edges · 51 communities (44 shown, 7 thin omitted)
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 357 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `9f0fe67d`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_sdlc_git.py
- main.py
- test_api.py
- app/main.py
- command
- SDLC Platform Implementation Guide
- save_tasks
- TaskWorkspace
- SDLCTaskManager
- TaskState
- قرارداد عملیاتی DWS Portal و Taskloom
- guide_mcp.py
- AgentConfig
- test_sdlc_lifecycle.py
- package.json
- models.py
- field_validator
- sdlc_runner.py
- fake_command
- post
- SDLCProjectConfig
- ایرادهای شناخته‌شده (بازبینی کد — 2026-11-20)
- main.jsx
- TaskRequest
- services.py
- ProjectProfile
- test_sdlc_recovery.py
- execute_task
- SDLCProjectManager
- theme.test.js
- ClaudeEventStream
- test_session_todos_run_before_automatic_delivery_and_new_branches
- test_sdlc_approval.py
- _codex_account_status
- App
- complete_automatic_delivery
- CodexEventStream
- markdown.jsx
- sdlc_dashboard.jsx
- Taskloom
- test_codex_account_status_uses_portable_pipes_and_waits_for_initialization
- git_commit
- جریان SDLC
- delete_task
- StageTransitionRequest
- git_tasks.jsx
- lifespan
- test_command_resolves_relative_executable_from_working_directory
- test_selected_agent_status_exposes_claude_auth_without_sensitive_fields
- test_load_tasks_keeps_interrupted_sessions_when_storage_is_unavailable

## God Nodes (most connected - your core abstractions)
1. `TaskState` - 89 edges
2. `RunStatus` - 72 edges
3. `SDLCTaskManager` - 46 edges
4. `SDLCProjectConfig` - 45 edges
5. `SDLCTask` - 44 edges
6. `execute_task()` - 37 edges
7. `TaskWorkspace()` - 36 edges
8. `run_cli_stage()` - 34 edges
9. `AgentConfig` - 33 edges
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

## Communities (51 total, 7 thin omitted)

### Community 0 - "test_sdlc_git.py"
Cohesion: 0.06
Nodes (40): github_commit_push(), _github_context(), github_create_pr(), GitHubActionRequest, validate_github(), TaskRepo, commit_and_push(), commit_message() (+32 more)

### Community 1 - "main.py"
Cohesion: 0.06
Nodes (19): kill_process_tree(), process_image(), stop_if_same_program(), record_agent_process(), started(), command_path(), get_data_separator(), main() (+11 more)

### Community 2 - "test_api.py"
Cohesion: 0.10
Nodes (30): project_defaults(), local_test_setup_repo(), test_branch_list_exposes_local_and_origin_branches(), test_branch_switch_rejects_invalid_base_branch(), test_branch_switch_rejects_invalid_branch_name(), test_branch_switch_uses_existing_branch_or_creates_a_missing_one(), test_create_task_returns_a_confirmation_code_for_a_dirty_current_branch(), test_defaults_can_be_overridden_for_another_project() (+22 more)

### Community 3 - "app/main.py"
Cohesion: 0.09
Nodes (22): codex_status(), defaults(), get_role_knowledge(), get_sdlc_project(), get_sdlc_task(), health(), list_branches(), list_pending_human_interventions() (+14 more)

### Community 4 - "command"
Cohesion: 0.09
Nodes (19): base_branch_ref(), cleanup_owned_test_artifacts(), command(), continue_task(), git_branches(), prepare_tests(), read_workspace_docx(), read_workspace_text() (+11 more)

### Community 5 - "SDLC Platform Implementation Guide"
Cohesion: 0.06
Nodes (34): 1. Internal Scheduler/Loop, 2. Human Intervention System, 3. Structured Agent Outputs, 4. Project Configuration, Agent Types, API Integration, Architecture, Backend Tests (+26 more)

### Community 6 - "save_tasks"
Cohesion: 0.12
Nodes (22): add_todo(), advance_todo_queue(), commit(), create_task(), discard_todo(), dispatch_next_todo(), due_todos(), load_role_knowledge() (+14 more)

### Community 7 - "TaskWorkspace"
Cohesion: 0.13
Nodes (29): agentLabelFor(), apiError(), defaultBaseBranch(), DirectionalOutput(), loadWorkspaceState(), taskBranchFor(), taskIdForBranch(), TaskWorkspace() (+21 more)

### Community 9 - "TaskState"
Cohesion: 0.12
Nodes (24): load_tasks(), todo_destination(), RunStatus, TaskState, git_push(), test_continue_task_resumes_same_codex_session_and_retests(), test_follow_up_is_queued_for_a_stopped_codex_session(), fake_continue() (+16 more)

### Community 10 - "قرارداد عملیاتی DWS Portal و Taskloom"
Cohesion: 0.07
Nodes (29): frontend, gate اصلی backend, Locust, MCP دانش پروژه, MCP مستقل پروژه, suite قدیمی, الزامی, قرارداد عملیاتی DWS Portal و Taskloom (+21 more)

### Community 11 - "guide_mcp.py"
Cohesion: 0.17
Nodes (7): Guide, GuideCatalog, main(), McpServer, serve(), tool_definitions(), test_guide_catalog_reads_and_searches_only_markdown_roots()

### Community 12 - "AgentConfig"
Cohesion: 0.20
Nodes (17): AgentConfig, StageRunner, resolve_runner(), fake_agent(), install(), make_task(), project(), report() (+9 more)

### Community 13 - "test_sdlc_lifecycle.py"
Cohesion: 0.16
Nodes (17): RevisionRequest, build_stage_prompt(), stage_feedback(), test_command_receives_large_utf8_stdin_without_shell_expansion(), test_command_timeout_does_not_wait_for_stdin_consumption(), finish_analysis(), make_task(), run() (+9 more)

### Community 14 - "package.json"
Cohesion: 0.10
Nodes (23): dependencies, lucide-react@^0.294.0, react@^18.2.0, react-dom@^18.2.0, vite@^5.0.0, @vitejs/plugin-react@^5.0.0, name, private (+15 more)

### Community 15 - "models.py"
Cohesion: 0.13
Nodes (14): create_sdlc_task(), ChatRequest, CommitRequest, GitProvider, HumanInterventionResponse, McpFailureMode, McpStatus, ProjectDefaults (+6 more)

### Community 16 - "field_validator"
Cohesion: 0.11
Nodes (4): BranchSwitchRequest, SDLCTaskRequest, TodoRequest, valid_branch_name()

### Community 17 - "sdlc_runner.py"
Cohesion: 0.14
Nodes (12): Change, TestResults, folder_changes(), parse_agent_report(), _recommendations(), run_cli_stage(), run_stage_tests(), snapshot_folder() (+4 more)

### Community 18 - "fake_command"
Cohesion: 0.09
Nodes (12): test_claude_account_status_uses_cli_json_and_omits_identity(), test_claude_mcp_preflight_uses_its_native_command_and_rejects_unavailable_entries(), test_creates_merge_request_and_returns_url(), test_dirty_current_task_branch_requires_explicit_confirmation(), test_dirty_worktree_cannot_be_carried_to_a_different_task_branch(), test_execute_task_reuses_confirmed_dirty_current_branch_without_switching(), test_mcp_preflight_reports_unavailable_states(), test_mcp_preflight_requires_configured_and_enabled_entry() (+4 more)

### Community 19 - "post"
Cohesion: 0.11
Nodes (16): approve_sdlc_task(), create_human_intervention_request(), create_sdlc_project(), get_state(), merge_request(), push(), respond_to_human_intervention(), run_manual_test_setup() (+8 more)

### Community 20 - "SDLCProjectConfig"
Cohesion: 0.16
Nodes (11): AgentResult, SDLCProjectConfig, SDLCTask, _feedback_text(), OllamaAgentRunner, ذخیره‌سازی, ماژول‌ها, معماری Taskloom (+3 more)

### Community 21 - "ایرادهای شناخته‌شده (بازبینی کد — 2026-11-20)"
Cohesion: 0.09
Nodes (18): workspace_tree(), visit(), API, SDLC, تسک کلاسیک (Codex / Claude Code), نمونه, ایرادهای شناخته‌شده (بازبینی کد — 2026-11-20), 🔴 بحرانی — سیستم را از کار می‌اندازد (+10 more)

### Community 22 - "main.jsx"
Cohesion: 0.15
Nodes (17): CodePane(), DiffViewer(), extensionFor(), FilePreview(), initial, languageFor(), lineIsChanged(), localDateTimeValue() (+9 more)

### Community 23 - "TaskRequest"
Cohesion: 0.11
Nodes (11): TaskRequest, build_prompt(), test_build_prompt_requires_reviewing_markdown_after_changes(), test_build_prompt_uses_dws_mcp_for_context_but_not_test_evidence(), test_execute_task_checks_out_an_existing_task_branch(), test_execute_task_creates_the_task_branch_from_selected_base(), test_execute_task_keeps_the_complete_failed_test_output(), test_new_tasks_use_the_tasks_branch_prefix() (+3 more)

### Community 24 - "services.py"
Cohesion: 0.12
Nodes (6): detect_tests(), _mcp_config(), preflight_project_mcp(), split_command(), test_plan(), test_working_directory()

### Community 25 - "ProjectProfile"
Cohesion: 0.15
Nodes (14): _default_project_path(), delete_profile(), dws_test_defaults(), list_profiles(), load_profiles(), migrate_legacy_test_settings(), profiles_path(), put_profile() (+6 more)

### Community 26 - "test_sdlc_recovery.py"
Cohesion: 0.28
Nodes (9): SDLCStatus, make_task(), run(), test_auto_resume_reruns_without_asking(), test_command_reports_the_started_pid(), test_interrupted_running_tasks_go_to_the_inbox_once(), test_orphaned_agent_is_checked_and_reported(), test_resume_answer_reruns_the_interrupted_stage() (+1 more)

### Community 27 - "execute_task"
Cohesion: 0.20
Nodes (14): AgentType, agent_executable(), agent_name(), agent_response(), codex_response(), execute_task(), generate_commit_message(), initial_agent_args() (+6 more)

### Community 28 - "SDLCProjectManager"
Cohesion: 0.14
Nodes (3): SDLCProjectManager, test_saved_project_with_default_github_config_loads_again(), manager()

### Community 29 - "theme.test.js"
Cohesion: 0.20
Nodes (6): Clock(), resolveMarkdownAsset(), getInitialTheme(), nextTheme(), THEMES, formatTime()

### Community 30 - "ClaudeEventStream"
Cohesion: 0.26
Nodes (5): claude_command(), claude_response(), _claude_text_blocks(), ClaudeEventStream, test_claude_stream_json_preserves_session_final_response_and_live_activity()

### Community 31 - "test_session_todos_run_before_automatic_delivery_and_new_branches"
Cohesion: 0.17
Nodes (4): test_due_todos_skip_future_deadlines_without_blocking_ready_work(), fake_create_task(), test_scheduler_dispatch_releases_only_explicitly_scheduled_work(), test_session_todos_run_before_automatic_delivery_and_new_branches()

### Community 32 - "test_sdlc_approval.py"
Cohesion: 0.24
Nodes (5): ProjectWorkflowConfig, make_task(), test_approve_endpoint_marks_task_done_only_from_pending_approval(), test_last_stage_moves_task_to_pending_approval(), setup()

### Community 33 - "_codex_account_status"
Cohesion: 0.18
Nodes (5): _codex_account_status(), codex_account_status_payload(), _command_sync(), read_output(), test_codex_account_status_payload_omits_account_email_and_keeps_usage_data()

### Community 34 - "App"
Cohesion: 0.18
Nodes (7): App(), addWorkspace(), moveBoardTask(), saveRoleKnowledge(), loadBoardAssignments(), loadWorkspaces(), newWorkspace()

### Community 35 - "complete_automatic_delivery"
Cohesion: 0.22
Nodes (5): complete_automatic_delivery(), test_automatic_delivery_completes_before_releasing_the_next_todo(), fake_commit(), test_automatic_delivery_generates_a_commit_message_when_enabled(), test_uncommitted_changes_hold_the_todo_queue_without_auto_commit()

### Community 36 - "CodexEventStream"
Cohesion: 0.36
Nodes (3): codex_command(), CodexEventStream, test_codex_jsonl_events_update_live_output_incrementally()

### Community 37 - "markdown.jsx"
Cohesion: 0.54
Nodes (7): inlineMarkdown(), isBlockStart(), isTableDivider(), MarkdownPreview(), renderBlocks(), safeExternalUrl(), splitCells()

### Community 38 - "sdlc_dashboard.jsx"
Cohesion: 0.29
Nodes (6): agentTypes, interventionHints, readJsonOrThrow(), responseOptionLabels, SDLCDashboard(), sdlcStages

### Community 39 - "Taskloom"
Cohesion: 0.25
Nodes (7): Taskloom, دسترسی به راهنماها با MCP, راه‌اندازی, ساخت فایل اجرایی ویندوز, مسیر دانش نقش‌ها, نگه‌داری و ادامهٔ گفت‌وگو, چه کاری انجام می‌دهد؟

### Community 41 - "git_commit"
Cohesion: 0.33
Nodes (4): git_commit(), test_git_commit_skips_hooks_when_nothing_is_staged(), test_git_commit_stages_changes_before_running_commit(), fake_refresh()

### Community 42 - "جریان SDLC"
Cohesion: 0.29
Nodes (7): Git و GitHub (`backend/app/sdlc_git.py`), بازیابی پس از restart, جریان SDLC, حلقهٔ بازبینی, صندوق انسانی (human inbox), عامل‌ها (اجراکنندهٔ هر مرحله), ماشین وضعیت (`SDLCStatus`)

### Community 43 - "delete_task"
Cohesion: 0.33
Nodes (3): delete_sdlc_project(), delete_task(), delete_todo()

### Community 44 - "StageTransitionRequest"
Cohesion: 0.33
Nodes (3): transition_sdlc_task(), StageTransitionRequest, 🟡 کیفیت و نگهداری

### Community 48 - "test_selected_agent_status_exposes_claude_auth_without_sensitive_fields"
Cohesion: 0.50
Nodes (3): test_codex_status_exposes_account_limits_usage_and_models(), fake_status(), test_selected_agent_status_exposes_claude_auth_without_sensitive_fields()

## Knowledge Gaps
- **7 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `TaskState` connect `TaskState` to `test_sdlc_git.py`, `test_api.py`, `app/main.py`, `command`, `save_tasks`, `SDLCTaskManager`, `AgentConfig`, `test_sdlc_lifecycle.py`, `models.py`, `sdlc_runner.py`, `fake_command`, `post`, `SDLCProjectConfig`, `TaskRequest`, `services.py`, `test_sdlc_recovery.py`, `execute_task`, `ClaudeEventStream`, `test_session_todos_run_before_automatic_delivery_and_new_branches`, `test_sdlc_approval.py`, `complete_automatic_delivery`, `CodexEventStream`, `git_commit`?**
  _High betweenness centrality (0.072) - this node is a cross-community bridge._
- **Are the 29 inferred relationships involving `TaskState` (e.g. with `advance_todo_queue()` and `complete_automatic_delivery()`) actually correct?**
  _`TaskState` has 29 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_sdlc_git.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06331976481230213 - nodes in this community are weakly interconnected._
- **Why does `Backend Components` connect `SDLCProjectConfig` to `SDLC Platform Implementation Guide`, `SDLCTaskManager`, `AgentConfig`, `test_sdlc_recovery.py`, `SDLCProjectManager`?**
  _High betweenness centrality (0.054) - this node is a cross-community bridge._
- **Are the 60 inferred relationships involving `RunStatus` (e.g. with `advance_todo_queue()` and `complete_automatic_delivery()`) actually correct?**
  _`RunStatus` has 60 INFERRED edges - model-reasoned connections that need verification._
- **Should `main.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05519480519480519 - nodes in this community are weakly interconnected._
- **Why does `Architecture` connect `SDLC Platform Implementation Guide` to `SDLCProjectConfig`?**
  _High betweenness centrality (0.053) - this node is a cross-community bridge._