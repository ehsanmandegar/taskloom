# Graph Report - taskloom  (2026-11-20)

## Corpus Check
- 42 files · ~46,682 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 6 file(s) not represented in the graph (top: (none) 2, .bat 1, .ico 1)

## Summary
- 980 nodes · 2553 edges · 51 communities (44 shown, 7 thin omitted)
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 329 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `03c3f0d7`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_sdlc_git.py
- test_api.py
- guide_mcp.py
- test_sdlc_lifecycle.py
- app/main.py
- execute_task
- SDLC Platform Implementation Guide
- SDLCTaskManager
- TaskState
- TaskWorkspace
- sdlc_runner.py
- قرارداد عملیاتی DWS Portal و Taskloom
- Path
- save_tasks
- package.json
- post
- field_validator
- test_sdlc_runner.py
- main.jsx
- models.py
- command
- services.py
- SDLCProjectConfig
- build_exe.py
- AgentConfig
- theme.test.js
- ClaudeEventStream
- ProjectProfile
- test_session_todos_run_before_automatic_delivery_and_new_branches
- complete_automatic_delivery
- _codex_account_status
- App
- project_defaults
- SDLCTask
- CodexEventStream
- load_role_knowledge
- SDLCStatus
- git_commit
- markdown.jsx
- sdlc_dashboard.jsx
- Taskloom
- test_codex_account_status_uses_portable_pipes_and_waits_for_initialization
- codex_account_status
- StageTransitionRequest
- task_branch_preflight
- جریان SDLC
- git_tasks.jsx
- HumanInterventionResponse
- test_selected_agent_status_exposes_claude_auth_without_sensitive_fields
- test_new_tasks_use_the_tasks_branch_prefix

## God Nodes (most connected - your core abstractions)
1. `TaskState` - 87 edges
2. `RunStatus` - 70 edges
3. `SDLCTaskManager` - 43 edges
4. `SDLCProjectConfig` - 42 edges
5. `SDLCTask` - 42 edges
6. `execute_task()` - 37 edges
7. `TaskWorkspace()` - 36 edges
8. `AgentConfig` - 33 edges
9. `run_cli_stage()` - 32 edges
10. `command()` - 32 edges

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
Nodes (41): github_commit_push(), _github_context(), github_create_pr(), GitHubActionRequest, validate_github(), TaskRepo, commit_and_push(), commit_message() (+33 more)

### Community 1 - "test_api.py"
Cohesion: 0.07
Nodes (37): mcp_runtime_issue(), resolve_guides(), local_test_setup_repo(), test_branch_list_exposes_local_and_origin_branches(), test_branch_switch_rejects_invalid_base_branch(), test_branch_switch_rejects_invalid_branch_name(), test_branch_switch_uses_existing_branch_or_creates_a_missing_one(), test_create_task_returns_a_confirmation_code_for_a_dirty_current_branch() (+29 more)

### Community 2 - "guide_mcp.py"
Cohesion: 0.08
Nodes (13): Guide, GuideCatalog, main(), McpServer, serve(), tool_definitions(), configure_instance_storage(), run() (+5 more)

### Community 3 - "test_sdlc_lifecycle.py"
Cohesion: 0.08
Nodes (33): project_file_tree(), RevisionRequest, build_stage_prompt(), stage_feedback(), workspace_tree(), visit(), API, SDLC (+25 more)

### Community 4 - "app/main.py"
Cohesion: 0.09
Nodes (18): get_sdlc_project(), get_sdlc_task(), health(), lifespan(), list_branches(), list_pending_human_interventions(), list_profiles(), list_sdlc_projects() (+10 more)

### Community 5 - "execute_task"
Cohesion: 0.09
Nodes (20): TaskRequest, build_prompt(), cleanup_owned_test_artifacts(), execute_task(), preflight_project_mcp(), test_build_prompt_requires_reviewing_markdown_after_changes(), test_build_prompt_uses_dws_mcp_for_context_but_not_test_evidence(), test_claude_account_status_uses_cli_json_and_omits_identity() (+12 more)

### Community 6 - "SDLC Platform Implementation Guide"
Cohesion: 0.06
Nodes (34): 1. Internal Scheduler/Loop, 2. Human Intervention System, 3. Structured Agent Outputs, 4. Project Configuration, Agent Types, API Integration, Architecture, Backend Tests (+26 more)

### Community 8 - "TaskState"
Cohesion: 0.11
Nodes (23): load_tasks(), todo_destination(), RunStatus, TaskState, git_push(), test_continue_task_resumes_same_codex_session_and_retests(), test_follow_up_is_queued_for_a_stopped_codex_session(), fake_continue() (+15 more)

### Community 9 - "TaskWorkspace"
Cohesion: 0.13
Nodes (29): agentLabelFor(), apiError(), defaultBaseBranch(), DirectionalOutput(), loadWorkspaceState(), taskBranchFor(), taskIdForBranch(), TaskWorkspace() (+21 more)

### Community 10 - "sdlc_runner.py"
Cohesion: 0.13
Nodes (19): AgentType, TestResults, folder_changes(), parse_agent_report(), _recommendations(), run_cli_stage(), run_stage_tests(), snapshot_folder() (+11 more)

### Community 11 - "قرارداد عملیاتی DWS Portal و Taskloom"
Cohesion: 0.07
Nodes (29): frontend, gate اصلی backend, Locust, MCP دانش پروژه, MCP مستقل پروژه, suite قدیمی, الزامی, قرارداد عملیاتی DWS Portal و Taskloom (+21 more)

### Community 12 - "Path"
Cohesion: 0.09
Nodes (17): project_file(), project_file_diff(), project_raw_file(), run_manual_test_setup(), detect_tests(), prepare_tests(), read_workspace_docx(), read_workspace_text() (+9 more)

### Community 13 - "save_tasks"
Cohesion: 0.16
Nodes (18): add_todo(), advance_todo_queue(), create_task(), discard_todo(), dispatch_next_todo(), due_todos(), pending_todos(), queue_follow_up() (+10 more)

### Community 14 - "package.json"
Cohesion: 0.10
Nodes (23): dependencies, lucide-react@^0.294.0, react@^18.2.0, react-dom@^18.2.0, vite@^5.0.0, @vitejs/plugin-react@^5.0.0, name, private (+15 more)

### Community 15 - "post"
Cohesion: 0.11
Nodes (16): approve_sdlc_task(), commit(), create_human_intervention_request(), create_sdlc_project(), get_state(), merge_request(), push(), rename_task() (+8 more)

### Community 16 - "field_validator"
Cohesion: 0.11
Nodes (4): BranchSwitchRequest, SDLCTaskRequest, TodoRequest, valid_branch_name()

### Community 17 - "test_sdlc_runner.py"
Cohesion: 0.23
Nodes (16): StageRunner, resolve_runner(), fake_agent(), install(), make_task(), project(), report(), test_agent_can_ask_a_human_or_request_a_revision() (+8 more)

### Community 18 - "main.jsx"
Cohesion: 0.15
Nodes (17): CodePane(), DiffViewer(), extensionFor(), FilePreview(), initial, languageFor(), lineIsChanged(), localDateTimeValue() (+9 more)

### Community 19 - "models.py"
Cohesion: 0.16
Nodes (12): create_sdlc_task(), Change, ChatRequest, CommitRequest, GitProvider, McpFailureMode, McpStatus, RenameTaskRequest (+4 more)

### Community 20 - "command"
Cohesion: 0.10
Nodes (9): selected_agent_status(), agent_account_status(), codex_response(), command(), test_codex_response_reads_thread_and_final_message_from_jsonl(), test_command_resolves_relative_executable_from_working_directory(), test_codex_large_prompts_use_stdin_and_preserve_streamed_events(), test_command_receives_large_utf8_stdin_without_shell_expansion() (+1 more)

### Community 22 - "SDLCProjectConfig"
Cohesion: 0.15
Nodes (4): SDLCProjectConfig, SDLCProjectManager, test_saved_project_with_default_github_config_loads_again(), setup()

### Community 23 - "build_exe.py"
Cohesion: 0.18
Nodes (6): command_path(), get_data_separator(), main(), remove_directory(), run_command(), validate_project()

### Community 24 - "AgentConfig"
Cohesion: 0.22
Nodes (6): AgentConfig, AgentResult, _feedback_text(), OllamaAgentRunner, Backend Components, test_ollama_file_claims_are_proposals_not_changes()

### Community 25 - "theme.test.js"
Cohesion: 0.20
Nodes (6): Clock(), resolveMarkdownAsset(), getInitialTheme(), nextTheme(), THEMES, formatTime()

### Community 26 - "ClaudeEventStream"
Cohesion: 0.26
Nodes (5): claude_command(), claude_response(), _claude_text_blocks(), ClaudeEventStream, test_claude_stream_json_preserves_session_final_response_and_live_activity()

### Community 27 - "ProjectProfile"
Cohesion: 0.24
Nodes (9): delete_profile(), delete_sdlc_project(), delete_task(), delete_todo(), load_profiles(), profiles_path(), put_profile(), save_profiles() (+1 more)

### Community 28 - "test_session_todos_run_before_automatic_delivery_and_new_branches"
Cohesion: 0.17
Nodes (4): test_due_todos_skip_future_deadlines_without_blocking_ready_work(), fake_create_task(), test_scheduler_dispatch_releases_only_explicitly_scheduled_work(), test_session_todos_run_before_automatic_delivery_and_new_branches()

### Community 29 - "complete_automatic_delivery"
Cohesion: 0.20
Nodes (6): complete_automatic_delivery(), create_merge_request(), test_automatic_delivery_completes_before_releasing_the_next_todo(), fake_commit(), test_automatic_delivery_generates_a_commit_message_when_enabled(), test_uncommitted_changes_hold_the_todo_queue_without_auto_commit()

### Community 30 - "_codex_account_status"
Cohesion: 0.18
Nodes (5): _codex_account_status(), codex_account_status_payload(), _command_sync(), read_output(), test_codex_account_status_payload_omits_account_email_and_keeps_usage_data()

### Community 31 - "App"
Cohesion: 0.18
Nodes (7): App(), addWorkspace(), moveBoardTask(), saveRoleKnowledge(), loadBoardAssignments(), loadWorkspaces(), newWorkspace()

### Community 32 - "project_defaults"
Cohesion: 0.24
Nodes (7): _default_project_path(), defaults(), dws_test_defaults(), migrate_legacy_test_settings(), project_defaults(), sessions_path(), ProjectDefaults

### Community 33 - "SDLCTask"
Cohesion: 0.24
Nodes (5): SDLCTask, ذخیره‌سازی, ماژول‌ها, معماری Taskloom, نمای کلی

### Community 34 - "CodexEventStream"
Cohesion: 0.36
Nodes (3): codex_command(), CodexEventStream, test_codex_jsonl_events_update_live_output_incrementally()

### Community 35 - "load_role_knowledge"
Cohesion: 0.25
Nodes (6): get_role_knowledge(), load_role_knowledge(), put_role_knowledge(), role_knowledge_path(), update_sdlc_project(), RoleKnowledgeSettings

### Community 36 - "SDLCStatus"
Cohesion: 0.43
Nodes (5): ProjectWorkflowConfig, SDLCStatus, make_task(), test_approve_endpoint_marks_task_done_only_from_pending_approval(), test_last_stage_moves_task_to_pending_approval()

### Community 37 - "git_commit"
Cohesion: 0.29
Nodes (5): git_commit(), refresh_git(), test_git_commit_skips_hooks_when_nothing_is_staged(), test_git_commit_stages_changes_before_running_commit(), fake_refresh()

### Community 38 - "markdown.jsx"
Cohesion: 0.54
Nodes (7): inlineMarkdown(), isBlockStart(), isTableDivider(), MarkdownPreview(), renderBlocks(), safeExternalUrl(), splitCells()

### Community 39 - "sdlc_dashboard.jsx"
Cohesion: 0.29
Nodes (6): agentTypes, interventionHints, readJsonOrThrow(), responseOptionLabels, SDLCDashboard(), sdlcStages

### Community 40 - "Taskloom"
Cohesion: 0.25
Nodes (7): Taskloom, دسترسی به راهنماها با MCP, راه‌اندازی, ساخت فایل اجرایی ویندوز, مسیر دانش نقش‌ها, نگه‌داری و ادامهٔ گفت‌وگو, چه کاری انجام می‌دهد؟

### Community 42 - "codex_account_status"
Cohesion: 0.33
Nodes (3): codex_status(), codex_account_status(), test_codex_account_status_reports_process_start_errors()

### Community 43 - "StageTransitionRequest"
Cohesion: 0.33
Nodes (3): transition_sdlc_task(), StageTransitionRequest, 🟡 کیفیت و نگهداری

### Community 44 - "task_branch_preflight"
Cohesion: 0.33
Nodes (3): task_branch_preflight(), test_dirty_current_task_branch_requires_explicit_confirmation(), test_dirty_worktree_cannot_be_carried_to_a_different_task_branch()

### Community 45 - "جریان SDLC"
Cohesion: 0.33
Nodes (6): Git و GitHub (`backend/app/sdlc_git.py`), جریان SDLC, حلقهٔ بازبینی, صندوق انسانی (human inbox), عامل‌ها (اجراکنندهٔ هر مرحله), ماشین وضعیت (`SDLCStatus`)

### Community 48 - "test_selected_agent_status_exposes_claude_auth_without_sensitive_fields"
Cohesion: 0.50
Nodes (3): test_codex_status_exposes_account_limits_usage_and_models(), fake_status(), test_selected_agent_status_exposes_claude_auth_without_sensitive_fields()

## Knowledge Gaps
- **7 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `TaskState` connect `TaskState` to `test_sdlc_git.py`, `test_api.py`, `test_sdlc_lifecycle.py`, `app/main.py`, `execute_task`, `SDLCTaskManager`, `sdlc_runner.py`, `Path`, `save_tasks`, `post`, `test_sdlc_runner.py`, `models.py`, `command`, `services.py`, `ClaudeEventStream`, `test_session_todos_run_before_automatic_delivery_and_new_branches`, `complete_automatic_delivery`, `SDLCTask`, `CodexEventStream`, `SDLCStatus`, `git_commit`?**
  _High betweenness centrality (0.067) - this node is a cross-community bridge._
- **Are the 29 inferred relationships involving `TaskState` (e.g. with `advance_todo_queue()` and `complete_automatic_delivery()`) actually correct?**
  _`TaskState` has 29 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_sdlc_git.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06095481670929241 - nodes in this community are weakly interconnected._
- **Why does `Backend Components` connect `AgentConfig` to `SDLCTask`, `SDLCStatus`, `SDLC Platform Implementation Guide`, `SDLCTaskManager`, `SDLCProjectConfig`?**
  _High betweenness centrality (0.057) - this node is a cross-community bridge._
- **Are the 59 inferred relationships involving `RunStatus` (e.g. with `advance_todo_queue()` and `complete_automatic_delivery()`) actually correct?**
  _`RunStatus` has 59 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_api.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07183673469387755 - nodes in this community are weakly interconnected._
- **Why does `Architecture` connect `SDLC Platform Implementation Guide` to `AgentConfig`?**
  _High betweenness centrality (0.055) - this node is a cross-community bridge._