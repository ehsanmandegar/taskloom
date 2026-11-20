# Graph Report - taskloom  (2026-11-20)

## Corpus Check
- 44 files · ~43,954 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 6 file(s) not represented in the graph (top: (none) 2, .bat 1, .ico 1)

## Summary
- 878 nodes · 1865 edges · 59 communities (47 shown, 12 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 197 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `0736c924`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- guide_mcp.py
- test_api.py
- simple_backend.py
- app/main.py
- TaskWorkspace
- قرارداد عملیاتی DWS Portal و Taskloom
- SDLC Platform Startup Guide
- Path
- SDLCTaskManager
- TaskState
- execute_task
- field_validator
- models.py
- SDLCProjectConfig
- main.jsx
- AgentType
- test_sdlc_backend.py
- build_exe.py
- package.json
- dashboard.jsx
- Deploy Task Loop to Render
- SDLCProjectManager
- uvicorn
- test_session_todos_run_before_automatic_delivery_and_new_branches
- services.py
- theme.test.js
- ClaudeEventStream
- App
- SDLC Platform Implementation Guide
- command
- _codex_account_status
- Task Loop - Quick Deployment Guide
- codex_account_status
- CodexEventStream
- preflight_project_mcp
- markdown.jsx
- START_HERE.md
- switch_git_branch
- test_codex_account_status_uses_portable_pipes_and_waits_for_initialization
- create_sdlc_project
- Taskloom
- test_automatic_delivery_completes_before_releasing_the_next_todo
- workspace_tree
- task_branch_preflight
- start.js
- test_git_commit_skips_hooks_when_nothing_is_staged
- RoleKnowledgeSettings
- 🆘 Troubleshooting
- Key Features
- test_command_resolves_relative_executable_from_working_directory
- API Integration
- Testing
- Support and Maintenance
- Future Enhancements (Stage 2+)
- test_selected_agent_status_exposes_claude_auth_without_sensitive_fields
- test_load_tasks_keeps_interrupted_sessions_when_storage_is_unavailable
- dws_test_defaults

## God Nodes (most connected - your core abstractions)
1. `TaskState` - 63 edges
2. `RunStatus` - 50 edges
3. `TaskWorkspace()` - 36 edges
4. `execute_task()` - 34 edges
5. `AgentType` - 27 edges
6. `SDLCTaskManager` - 27 edges
7. `SDLCProjectConfig` - 26 edges
8. `command()` - 26 edges
9. `fake_command()` - 25 edges
10. `apiError()` - 24 edges

## Surprising Connections (you probably didn't know these)
- `Backend Components` --references--> `SDLCStatus`  [INFERRED]
  SDLC_PLATFORM_GUIDE.md → backend/app/models.py
- `Backend Components` --references--> `HumanIntervention`  [INFERRED]
  SDLC_PLATFORM_GUIDE.md → backend/app/models.py
- `Backend Components` --references--> `SDLCProjectManager`  [INFERRED]
  SDLC_PLATFORM_GUIDE.md → backend/app/services.py
- `Backend Components` --references--> `SDLCTaskManager`  [INFERRED]
  SDLC_PLATFORM_GUIDE.md → backend/app/services.py
- `Backend Components` --references--> `AgentConfig`  [INFERRED]
  SDLC_PLATFORM_GUIDE.md → backend/app/models.py

## Import Cycles
- None detected.

## Communities (59 total, 12 thin omitted)

### Community 0 - "guide_mcp.py"
Cohesion: 0.07
Nodes (14): Guide, GuideCatalog, main(), McpServer, serve(), tool_definitions(), configure_instance_storage(), run() (+6 more)

### Community 1 - "test_api.py"
Cohesion: 0.08
Nodes (32): detect_tests(), mcp_runtime_issue(), resolve_guides(), test_plan(), local_test_setup_repo(), test_branch_list_exposes_local_and_origin_branches(), test_branch_switch_rejects_invalid_base_branch(), test_branch_switch_rejects_invalid_branch_name() (+24 more)

### Community 2 - "simple_backend.py"
Cohesion: 0.08
Nodes (29): catch_all(), commit_task(), create_merge_request(), create_task(), create_todo(), delete_todo(), generate_commit_message(), get_agent_status() (+21 more)

### Community 3 - "app/main.py"
Cohesion: 0.09
Nodes (15): get_branches(), get_defaults(), get_profiles(), get_role_knowledge(), get_sdlc_project(), get_sdlc_task(), get_tasks(), get_workspace_changes() (+7 more)

### Community 4 - "TaskWorkspace"
Cohesion: 0.13
Nodes (29): agentLabelFor(), apiError(), defaultBaseBranch(), DirectionalOutput(), loadWorkspaceState(), taskBranchFor(), taskIdForBranch(), TaskWorkspace() (+21 more)

### Community 5 - "قرارداد عملیاتی DWS Portal و Taskloom"
Cohesion: 0.07
Nodes (29): frontend, gate اصلی backend, Locust, MCP دانش پروژه, MCP مستقل پروژه, suite قدیمی, الزامی, قرارداد عملیاتی DWS Portal و Taskloom (+21 more)

### Community 6 - "SDLC Platform Startup Guide"
Cohesion: 0.07
Nodes (29): 1. Create a Test Project, 1. Start Backend Server, 2. Create a Test Task, 2. Start Frontend Development Server, 3. Access the Platform, 3. Monitor the Pipeline, Agent Types, Architecture Overview (+21 more)

### Community 7 - "Path"
Cohesion: 0.09
Nodes (16): get_workspace_diff(), cleanup_owned_test_artifacts(), prepare_tests(), read_workspace_docx(), read_workspace_text(), run_test_setup(), test_setup_commands(), test_working_directory() (+8 more)

### Community 9 - "TaskState"
Cohesion: 0.13
Nodes (21): RunStatus, TaskState, git_push(), test_continue_task_resumes_same_codex_session_and_retests(), test_follow_up_is_queued_for_a_stopped_codex_session(), fake_continue(), test_future_todo_is_persisted_without_running_early(), test_generate_commit_message_uses_the_task_codex_session() (+13 more)

### Community 10 - "execute_task"
Cohesion: 0.12
Nodes (16): TaskRequest, agent_error_detail(), build_prompt(), execute_task(), test_agent_error_detail_surfaces_cli_install_and_structured_failures(), test_build_prompt_requires_reviewing_markdown_after_changes(), test_build_prompt_uses_dws_mcp_for_context_but_not_test_evidence(), test_execute_task_checks_out_an_existing_task_branch() (+8 more)

### Community 11 - "field_validator"
Cohesion: 0.10
Nodes (4): ProjectProfile, SDLCTaskRequest, TodoRequest, valid_branch_name()

### Community 12 - "models.py"
Cohesion: 0.12
Nodes (14): BranchSwitchRequest, Change, ChatRequest, CommitRequest, HumanInterventionResponse, ProjectDefaults, ProjectWorkflowConfig, RenameTaskRequest (+6 more)

### Community 13 - "SDLCProjectConfig"
Cohesion: 0.17
Nodes (7): AgentConfig, AgentResult, SDLCProjectConfig, SDLCTask, BackendAgent, OllamaAgentRunner, Backend Components

### Community 14 - "main.jsx"
Cohesion: 0.15
Nodes (17): CodePane(), DiffViewer(), extensionFor(), FilePreview(), initial, languageFor(), lineIsChanged(), localDateTimeValue() (+9 more)

### Community 15 - "AgentType"
Cohesion: 0.20
Nodes (13): AgentType, agent_executable(), agent_name(), agent_response(), codex_response(), continue_task(), generate_commit_message(), initial_agent_args() (+5 more)

### Community 16 - "test_sdlc_backend.py"
Cohesion: 0.23
Nodes (10): ChatMessage, GitProvider, McpFailureMode, McpStatus, SDLCStatus, TaskRole, main(), main_async() (+2 more)

### Community 17 - "build_exe.py"
Cohesion: 0.18
Nodes (6): command_path(), get_data_separator(), main(), remove_directory(), run_command(), validate_project()

### Community 18 - "package.json"
Cohesion: 0.15
Nodes (15): dependencies, react-dom@^18.2.0, vite@^5.0.0, @vitejs/plugin-react@^5.0.0, name, private, scripts, build (+7 more)

### Community 19 - "dashboard.jsx"
Cohesion: 0.16
Nodes (12): lucide-react@^0.294.0, react@^18.2.0, DashboardPages(), stages, statusLabel(), taskTitle(), GitTaskList(), gitTaskRows() (+4 more)

### Community 20 - "Deploy Task Loop to Render"
Cohesion: 0.12
Nodes (16): Data Persistence, Deploy Task Loop to Render, Deployment URLs, Free Tier Limitations, Important Notes, Monitoring, Next Steps, Ollama Integration (+8 more)

### Community 22 - "uvicorn"
Cohesion: 0.18
Nodes (6): lifespan(), todo_scheduler(), root(), sdlc_info(), root(), test_sdlc()

### Community 23 - "test_session_todos_run_before_automatic_delivery_and_new_branches"
Cohesion: 0.16
Nodes (6): TodoItem, test_due_todos_skip_future_deadlines_without_blocking_ready_work(), fake_create_task(), test_scheduler_dispatch_releases_only_explicitly_scheduled_work(), test_session_todos_run_before_automatic_delivery_and_new_branches(), test_todo_destination_prioritizes_session_then_branch_then_project()

### Community 25 - "theme.test.js"
Cohesion: 0.22
Nodes (5): Clock(), getInitialTheme(), nextTheme(), THEMES, formatTime()

### Community 26 - "ClaudeEventStream"
Cohesion: 0.26
Nodes (5): claude_command(), claude_response(), _claude_text_blocks(), ClaudeEventStream, test_claude_stream_json_preserves_session_final_response_and_live_activity()

### Community 27 - "App"
Cohesion: 0.15
Nodes (8): App(), addWorkspace(), moveBoardTask(), saveRoleKnowledge(), loadBoardAssignments(), loadWorkspaces(), newWorkspace(), SDLCDashboard()

### Community 28 - "SDLC Platform Implementation Guide"
Cohesion: 0.15
Nodes (13): Agent Types, Architecture, Backward Compatibility, Common Issues, Deployment, Frontend Components, Logs and Debugging, Overview (+5 more)

### Community 29 - "command"
Cohesion: 0.21
Nodes (7): command(), create_merge_request(), git_commit(), refresh_git(), repository(), test_command_receives_large_utf8_stdin_without_shell_expansion(), test_command_timeout_does_not_wait_for_stdin_consumption()

### Community 30 - "_codex_account_status"
Cohesion: 0.18
Nodes (5): _codex_account_status(), codex_account_status_payload(), _command_sync(), read_output(), test_codex_account_status_payload_omits_account_email_and_keeps_usage_data()

### Community 31 - "Task Loop - Quick Deployment Guide"
Cohesion: 0.18
Nodes (11): 🚀 Deploy in 5 Minutes, 📍 Environment Variables, 💰 Estimated Monthly Cost, ⚡ First Task, 📚 More Info, 📊 Next Steps, Option A: Render (Recommended), Option B: Docker (Local/VPS) (+3 more)

### Community 32 - "codex_account_status"
Cohesion: 0.22
Nodes (5): get_agent_status(), agent_account_status(), codex_account_status(), test_claude_account_status_uses_cli_json_and_omits_identity(), test_codex_account_status_reports_process_start_errors()

### Community 33 - "CodexEventStream"
Cohesion: 0.36
Nodes (3): codex_command(), CodexEventStream, test_codex_jsonl_events_update_live_output_incrementally()

### Community 34 - "preflight_project_mcp"
Cohesion: 0.20
Nodes (5): preflight_project_mcp(), test_claude_mcp_preflight_uses_its_native_command_and_rejects_unavailable_entries(), test_creates_merge_request_and_returns_url(), test_mcp_preflight_reports_unavailable_states(), test_mcp_preflight_requires_configured_and_enabled_entry()

### Community 35 - "markdown.jsx"
Cohesion: 0.42
Nodes (8): inlineMarkdown(), isBlockStart(), isTableDivider(), MarkdownPreview(), renderBlocks(), safeExternalUrl(), splitCells(), resolveMarkdownAsset()

### Community 37 - "switch_git_branch"
Cohesion: 0.25
Nodes (4): base_branch_ref(), switch_git_branch(), test_switch_git_branch_checks_out_remote_before_creating(), test_switch_git_branch_creates_missing_branch_from_selected_base()

### Community 39 - "create_sdlc_project"
Cohesion: 0.29
Nodes (3): create_sdlc_project(), create_sdlc_task(), transition_sdlc_task()

### Community 40 - "Taskloom"
Cohesion: 0.29
Nodes (7): Taskloom, دسترسی به راهنماها با MCP, راه‌اندازی, ساخت فایل اجرایی ویندوز, مسیر دانش نقش‌ها, نگه‌داری و ادامهٔ گفت‌وگو, چه کاری انجام می‌دهد؟

### Community 41 - "test_automatic_delivery_completes_before_releasing_the_next_todo"
Cohesion: 0.29
Nodes (3): test_automatic_delivery_completes_before_releasing_the_next_todo(), fake_commit(), test_automatic_delivery_generates_a_commit_message_when_enabled()

### Community 42 - "workspace_tree"
Cohesion: 0.33
Nodes (4): get_workspace_tree(), workspace_tree(), visit(), test_workspace_tree_is_bounded_to_useful_project_files()

### Community 43 - "task_branch_preflight"
Cohesion: 0.33
Nodes (3): task_branch_preflight(), test_dirty_current_task_branch_requires_explicit_confirmation(), test_dirty_worktree_cannot_be_carried_to_a_different_task_branch()

### Community 45 - "test_git_commit_skips_hooks_when_nothing_is_staged"
Cohesion: 0.33
Nodes (3): test_git_commit_skips_hooks_when_nothing_is_staged(), test_git_commit_stages_changes_before_running_commit(), fake_refresh()

### Community 47 - "🆘 Troubleshooting"
Cohesion: 0.40
Nodes (5): "Build failed", "Cannot connect to backend", "Ollama not responding", "Services timing out", 🆘 Troubleshooting

### Community 48 - "Key Features"
Cohesion: 0.40
Nodes (5): 1. Internal Scheduler/Loop, 2. Human Intervention System, 3. Structured Agent Outputs, 4. Project Configuration, Key Features

### Community 50 - "API Integration"
Cohesion: 0.50
Nodes (4): API Integration, Human Intervention, Project Management, Task Management

### Community 51 - "Testing"
Cohesion: 0.50
Nodes (4): Backend Tests, Frontend Tests, Integration Test, Testing

### Community 52 - "Support and Maintenance"
Cohesion: 0.50
Nodes (4): Backup and Recovery, Monitoring, Support and Maintenance, Updates and Patches

### Community 53 - "Future Enhancements (Stage 2+)"
Cohesion: 0.50
Nodes (4): Future Enhancements (Stage 2+), Phase 1: External Integration, Phase 2: Advanced Features, Phase 3: Enterprise Features

### Community 54 - "test_selected_agent_status_exposes_claude_auth_without_sensitive_fields"
Cohesion: 0.50
Nodes (3): test_codex_status_exposes_account_limits_usage_and_models(), fake_status(), test_selected_agent_status_exposes_claude_auth_without_sensitive_fields()

## Knowledge Gaps
- **12 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SDLC Platform Implementation Guide` connect `SDLC Platform Implementation Guide` to `START_HERE.md`, `Key Features`, `API Integration`, `Testing`, `Support and Maintenance`, `Future Enhancements (Stage 2+)`?**
  _High betweenness centrality (0.128) - this node is a cross-community bridge._
- **Are the 14 inferred relationships involving `TaskState` (e.g. with `claude_command()` and `ClaudeEventStream`) actually correct?**
  _`TaskState` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Should `guide_mcp.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06623376623376623 - nodes in this community are weakly interconnected._
- **Why does `Backend Components` connect `SDLCProjectConfig` to `SDLCTaskManager`, `test_sdlc_backend.py`, `SDLC Platform Implementation Guide`, `SDLCProjectManager`?**
  _High betweenness centrality (0.127) - this node is a cross-community bridge._
- **Are the 42 inferred relationships involving `RunStatus` (e.g. with `continue_task()` and `execute_task()`) actually correct?**
  _`RunStatus` has 42 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_api.py` be split into smaller, more focused modules?**
  _Cohesion score 0.0797979797979798 - nodes in this community are weakly interconnected._
- **Why does `Architecture` connect `SDLC Platform Implementation Guide` to `SDLCProjectConfig`?**
  _High betweenness centrality (0.126) - this node is a cross-community bridge._