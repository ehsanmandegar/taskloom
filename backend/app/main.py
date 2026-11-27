import asyncio
import hmac
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
import json
import mimetypes
import os
import sys
import uuid
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .models import AgentType, BranchSwitchRequest, ChatMessage, ChatRequest, CommitRequest, GitProvider, McpFailureMode, ProjectDefaults, ProjectProfile, RenameTaskRequest, RoleKnowledgeSettings, RunStatus, TaskRequest, TaskRoleRequest, TaskState, TestSetupRequest, TodoItem, TodoRequest, valid_branch_name
from .models import SDLCStatus, SDLCProjectConfig, AgentConfig, ProjectWorkflowConfig, SDLCTask, SDLCTaskRequest, AgentResult, HumanIntervention, RevisionRequest, SDLCTaskContext, StageTransitionRequest, HumanInterventionResponse, StageProviderConfig
from .services import agent_account_status, codex_account_status, continue_task, create_merge_request, execute_task, generate_commit_message, git_branches, git_commit, git_push, repository, run_test_setup, switch_git_branch, task_branch_preflight, workspace_changes, workspace_diff, workspace_file, workspace_preview_path, workspace_tree
from .services import SDLCProjectManager, SDLCTaskManager, TaskConflictError, command, OllamaDiscoveryService, ModelResolutionService, ProviderResolutionService, _ollama_coding_agent
from . import project_builder, run_guides, run_processes
from .services import agent_executable
from .sdlc_git import (
    GitHubError, commit_and_push, create_github_repository, create_pull_request, describe_new_repository,
    commit_message, ensure_workspace, git_root, validate_repository,
)
from .git_flow import SANDBOX, GitBusyError, GitRepo, create_task_branch, GitFlowError, MergeConflictError, commit_task_work, integrate_task, record_failure, record_merge, task_branch_name
from . import sdlc_policy as policy
from .sdlc_policy import compute_metrics, next_release_version
from .releases import HOLDING, ReleaseStatus, IntegratedTask, MergeEntry, ReleaseError, ReleaseInputError, ReleaseManager, ReleaseStore, repository_id_for
from pydantic import BaseModel

scheduler_worker: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Keep scheduled Todos moving while the Taskloom server is running."""
    global scheduler_worker
    scheduler_worker = asyncio.create_task(todo_scheduler())
    manager = sdlc_task_manager
    if manager.claim_data_dir():
        try:
            await manager.recover_interrupted_tasks()
            await release_manager.recover_interrupted()
        except Exception as exc:  # recovery must never keep the server from starting
            print(f"[SDLC] Recovery after restart failed: {exc}", flush=True)
    else:
        print(f"[SDLC] Another Taskloom server is using {manager.data_dir}; this one will not run SDLC stages.", flush=True)
    try:
        yield
    finally:
        run_processes.stop_all()
        manager.release_data_dir()
        scheduler_worker.cancel()
        with suppress(asyncio.CancelledError):
            await scheduler_worker
        scheduler_worker = None


app = FastAPI(title="Taskloom", version="0.1.0", lifespan=lifespan)


@app.exception_handler(TaskConflictError)
async def task_conflict_handler(_: Request, exc: TaskConflictError):
    return JSONResponse(status_code=409, content={"detail": str(exc)})
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])


def dws_test_defaults(project_path: Path) -> tuple[str, str] | None:
    """Return DWS's backend interpreter and its required test directory."""
    backend = project_path / "backend"
    interpreter = backend / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not interpreter.is_file():
        return None
    command = r".\venv\Scripts\python.exe -m pytest" if os.name == "nt" else ".venv/bin/python -m pytest"
    return command, "backend"


def migrate_legacy_test_settings(project_path: Path, command: str | None, working_directory: str | None) -> tuple[str | None, str | None]:
    """Upgrade Taskloom's former generic DWS pytest setting without touching custom plans."""
    defaults = dws_test_defaults(project_path)
    if defaults and working_directory is None and command in {"python -m pytest", "python -m pytest -q"}:
        return defaults
    return command, working_directory


def sessions_path() -> Path:
    configured = os.getenv("TASKLOOM_SESSIONS_PATH")
    return Path(configured).expanduser() if configured else Path.home() / ".taskloom" / "sessions.json"


def load_tasks() -> dict[str, TaskState]:
    path = sessions_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        loaded = {run_id: TaskState.model_validate(state) for run_id, state in data.items()}
    except (OSError, json.JSONDecodeError, ValueError):
        # A damaged history must not prevent the local dashboard from starting.
        return {}

    restarted = migrated = False
    for state in loaded.values():
        command, working_directory = migrate_legacy_test_settings(
            Path(state.project_path), state.test_command, state.test_working_directory
        )
        if (command, working_directory) != (state.test_command, state.test_working_directory):
            state.test_command, state.test_working_directory = command, working_directory
            migrated = True
        if state.status in {RunStatus.queued, RunStatus.running, RunStatus.testing}:
            state.status = RunStatus.failed
            state.step = "Interrupted by Taskloom restart"
            agent = "Claude" if state.agent_type == AgentType.claude else "Codex"
            state.error = f"Taskloom was restarted before {agent} finished responding."
            restarted = True
    if restarted or migrated:
        try:
            save_tasks(loaded)
        except HTTPException:
            # Session history is optional at startup: retain the recovered
            # states in memory even when its storage is temporarily unavailable.
            pass
    return loaded


def save_tasks(states: dict[str, TaskState]) -> None:
    path = sessions_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps({run_id: state.model_dump(mode="json") for run_id, state in states.items()}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(path)
    except OSError as exc:
        raise HTTPException(500, f"Could not save task sessions: {exc}") from exc


tasks: dict[str, TaskState] = load_tasks()
task_workers: dict[str, asyncio.Task] = {}


def track_worker(run_id: str, worker: asyncio.Task | None) -> None:
    """Keep the active task handle so a user can stop its subprocess safely."""
    if worker is None:
        return
    task_workers[run_id] = worker

    def forget(completed: asyncio.Task) -> None:
        if task_workers.get(run_id) is completed:
            task_workers.pop(run_id, None)

    worker.add_done_callback(forget)


DEFAULT_GUIDE_NAME = "04-taskloom-project-contract.md"


def _default_project_path() -> Path:
    configured = os.getenv("DWS_PROJECT_PATH")
    if configured:
        candidate = Path(configured).expanduser().resolve()
        if candidate.is_dir() and (candidate / ".git").exists():
            return candidate
    configured = os.getenv("TASKLOOM_DEFAULT_PROJECT_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    dws = Path(r"E:\dws")
    if dws.is_dir() and (dws / ".git").exists():
        return dws.resolve()
    source_root = Path(__file__).resolve().parents[2]
    executable_dir = Path(sys.executable).resolve().parent
    candidates = [Path.cwd().resolve(), executable_dir, executable_dir.parent, source_root]
    for candidate in dict.fromkeys(candidates):
        if (candidate / DEFAULT_GUIDE_NAME).is_file() and (candidate / ".git").exists():
            return candidate
    return source_root


def project_defaults() -> ProjectDefaults:
    project_path = _default_project_path()
    configured_dws = os.getenv("DWS_PROJECT_PATH")
    is_dws = project_path.name.casefold() == "dws" or bool(
        configured_dws and Path(configured_dws).expanduser().resolve() == project_path
    )
    configured_guides = os.getenv("TASKLOOM_DEFAULT_GUIDE_PATHS")
    if configured_guides is not None:
        guide_paths = [value.strip() for value in configured_guides.split(os.pathsep) if value.strip()]
    else:
        contract = project_path / DEFAULT_GUIDE_NAME
        if contract.is_file():
            guide_paths = [str(contract)]
        else:
            guide_candidates = (
                project_path / "README.md",
                project_path / "backend" / "TESTING_GUIDE.md",
                project_path / "backend" / "docs",
            )
            guide_paths = [
                str(path)
                for path in guide_candidates
                if path.is_file() or path.is_dir()
            ]

    configured_test = os.getenv("TASKLOOM_DEFAULT_TEST_COMMAND")
    configured_test_working_directory = os.getenv("TASKLOOM_DEFAULT_TEST_WORKING_DIRECTORY")
    test_working_directory = configured_test_working_directory.strip() if configured_test_working_directory else None
    if configured_test is not None:
        test_command = configured_test.strip() or None
    elif dws_defaults := dws_test_defaults(project_path):
        test_command, test_working_directory = dws_defaults
    elif os.name == "nt" and (project_path / ".venv" / "Scripts" / "python.exe").is_file():
        test_command = r".venv\Scripts\python.exe -m pytest -q"
    elif (project_path / ".venv" / "bin" / "python").is_file():
        test_command = ".venv/bin/python -m pytest -q"
    else:
        test_command = None

    configured_mcp = os.getenv("TASKLOOM_DEFAULT_MCP_SERVER")
    mcp_server_name = configured_mcp.strip() if configured_mcp is not None else (
        "dws_project" if (project_path / DEFAULT_GUIDE_NAME).is_file() or project_path.name.casefold() == "dws" else None
    )
    mcp_server_name = mcp_server_name or None
    configured_mode = os.getenv("TASKLOOM_DEFAULT_MCP_FAILURE_MODE")
    mcp_failure_mode = McpFailureMode(
        configured_mode.strip().lower() if configured_mode else (
            McpFailureMode.blocked if mcp_server_name else McpFailureMode.warning
        )
    )
    configured_base = os.getenv("TASKLOOM_DEFAULT_BASE_BRANCH")
    base_branch = valid_branch_name(configured_base) if configured_base else ("sandbox" if is_dws else "main")
    configured_agent = os.getenv("TASKLOOM_DEFAULT_AGENT_TYPE", AgentType.codex.value)
    agent_type = AgentType(configured_agent.strip().lower())

    return ProjectDefaults(
        project_path=str(project_path),
        guide_paths=guide_paths,
        base_branch=base_branch,
        test_command=test_command,
        test_working_directory=test_working_directory,
        test_setup_enabled=False,
        mcp_server_name=mcp_server_name,
        mcp_failure_mode=mcp_failure_mode,
        git_provider=GitProvider.gitlab,
        agent_type=agent_type,
    )


def profiles_path() -> Path:
    configured = os.getenv("TASKLOOM_PROFILES_PATH")
    return Path(configured).expanduser() if configured else Path.home() / ".taskloom" / "profiles.json"


def role_knowledge_path() -> Path:
    configured = os.getenv("TASKLOOM_ROLE_KNOWLEDGE_PATH")
    return Path(configured).expanduser() if configured else Path.home() / ".taskloom" / "role-knowledge.json"


def load_role_knowledge() -> RoleKnowledgeSettings:
    path = role_knowledge_path()
    if not path.exists():
        return RoleKnowledgeSettings()
    try:
        return RoleKnowledgeSettings.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HTTPException(500, f"Could not read role knowledge settings: {exc}") from exc


@app.get("/api/role-knowledge", response_model=RoleKnowledgeSettings)
async def get_role_knowledge():
    return load_role_knowledge()


@app.put("/api/role-knowledge", response_model=RoleKnowledgeSettings)
async def put_role_knowledge(settings: RoleKnowledgeSettings):
    for role, raw in settings.model_dump().items():
        if raw and not Path(raw).expanduser().is_dir():
            raise HTTPException(422, f"Knowledge root for {role} must be an existing directory: {raw}")
    path = role_knowledge_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(settings.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(path)
    except OSError as exc:
        raise HTTPException(500, f"Could not save role knowledge settings: {exc}") from exc
    for state in tasks.values():
        state.role_knowledge_path = getattr(settings, state.role.value)
    save_tasks(tasks)
    return settings


def load_profiles() -> dict[str, ProjectProfile]:
    path = profiles_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        profiles = {name: ProjectProfile.model_validate(profile) for name, profile in data.items()}
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(500, f"Could not read project profiles: {exc}") from exc
    migrated = False
    for profile in profiles.values():
        command, working_directory = migrate_legacy_test_settings(
            Path(profile.project_path), profile.test_command, profile.test_working_directory
        )
        if (command, working_directory) != (profile.test_command, profile.test_working_directory):
            profile.test_command, profile.test_working_directory = command, working_directory
            migrated = True
    if migrated:
        save_profiles(profiles)
    return profiles


def save_profiles(profiles: dict[str, ProjectProfile]) -> None:
    path = profiles_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps({name: value.model_dump() for name, value in profiles.items()}, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
    except OSError as exc:
        raise HTTPException(500, f"Could not save project profiles: {exc}") from exc


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/codex/status")
async def codex_status():
    try:
        return await codex_account_status()
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.get("/api/agents/{agent_type}/status")
async def selected_agent_status(agent_type: AgentType):
    try:
        return await agent_account_status(agent_type)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.get("/api/defaults", response_model=ProjectDefaults)
async def defaults():
    return project_defaults()


@app.get("/api/tasks", response_model=list[TaskState])
async def list_tasks():
    return list(reversed(list(tasks.values())))


@app.get("/api/profiles", response_model=list[ProjectProfile])
async def list_profiles():
    return sorted(load_profiles().values(), key=lambda profile: profile.name.casefold())


@app.get("/api/branches")
async def list_branches(project_path: str):
    try:
        return await git_branches(repository(project_path))
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get("/api/workspace/tree")
async def project_file_tree(project_path: str):
    try:
        repo = repository(project_path)
        return {"root": repo.name, "tree": await asyncio.to_thread(workspace_tree, repo)}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/workspace/file")
async def project_file(project_path: str, path: str):
    try:
        return await workspace_file(repository(project_path), path)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/workspace/raw")
async def project_raw_file(project_path: str, path: str):
    try:
        file_path, media_type = workspace_preview_path(repository(project_path), path)
        response = FileResponse(file_path, media_type=media_type, filename=file_path.name, content_disposition_type="inline")
        response.headers["Content-Security-Policy"] = "sandbox"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/workspace/changes")
async def project_git_changes(project_path: str):
    try:
        return {"changes": await workspace_changes(repository(project_path))}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get("/api/workspace/diff")
async def project_file_diff(project_path: str, path: str, previous_path: str | None = None):
    try:
        return await workspace_diff(repository(project_path), path, previous_path)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/branches/switch")
async def switch_branch(request: BranchSwitchRequest):
    try:
        repo = repository(request.project_path)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    active_states = {RunStatus.queued, RunStatus.running, RunStatus.testing}
    if any(
        state.status in active_states and Path(state.project_path).expanduser().resolve() == repo
        for state in tasks.values()
    ):
        raise HTTPException(409, "Stop the active agent task for this project before switching branches")
    # A task branch that does not exist yet is always created from the latest `sandbox` (the request's
    # base_branch is only validated, not used); a missing sandbox is an error, never a fallback.
    git_repo = GitRepo(repo)
    try:
        created = False
        if not (await git_repo.rev(f"refs/heads/{request.branch}") or await git_repo.rev(f"refs/remotes/origin/{request.branch}")):
            await create_task_branch(git_repo, request.branch, request.branch)
            created = True
        result = await switch_git_branch(repo, request.branch, SANDBOX)
    except (GitFlowError, RuntimeError) as exc:
        raise HTTPException(409, str(exc)) from exc
    if created:
        result = {**result, "created": True, "message": f"Created `{request.branch}` from the latest `{SANDBOX}` and checked it out"}
    return result


@app.put("/api/profiles/{name}", response_model=ProjectProfile)
async def put_profile(name: str, profile: ProjectProfile):
    if name != profile.name:
        raise HTTPException(422, "Profile name in URL and body must match")
    profiles = load_profiles()
    profiles[name] = profile
    save_profiles(profiles)
    return profile


@app.delete("/api/profiles/{name}", status_code=204)
async def delete_profile(name: str):
    profiles = load_profiles()
    if name not in profiles:
        raise HTTPException(404, "Project profile not found")
    del profiles[name]
    save_profiles(profiles)


@app.post("/api/tasks", response_model=TaskState, status_code=202)
async def create_task(request: TaskRequest):
    try:
        repo = repository(request.project_path)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    active_states = {RunStatus.queued, RunStatus.running, RunStatus.testing}
    if any(
        state.status in active_states and Path(state.project_path).expanduser().resolve() == repo
        for state in tasks.values()
    ):
        raise HTTPException(
            409,
            "Another task is already running in this project path. Use a separate Git worktree path for parallel tasks.",
        )
    try:
        task_branch = task_branch_name(request.task_id)
    except GitFlowError as exc:
        raise HTTPException(422, str(exc)) from exc
    try:
        await task_branch_preflight(repo, task_branch, request.confirm_dirty_worktree)
    except RuntimeError as exc:
        message = str(exc)
        detail = (
            {"code": "dirty_worktree_confirmation_required", "message": message}
            if message.startswith("Confirm that you know")
            else message
        )
        raise HTTPException(409, detail) from exc
    run_id = uuid.uuid4().hex[:12]
    state = TaskState(
        id=run_id,
        task_id=request.task_id,
        session_name=request.session_name or request.task_id,
        project_path=str(repo),
        branch=task_branch,
        base_branch=SANDBOX,
        guide_paths=request.guide_paths,
        role=request.role,
        role_knowledge_path=getattr(load_role_knowledge(), request.role.value),
        test_command=request.test_command,
        test_working_directory=request.test_working_directory,
        test_setup_enabled=request.test_setup_enabled,
        auto_commit=request.auto_commit,
        auto_generate_commit_message=request.auto_generate_commit_message,
        auto_push=request.auto_push,
        auto_merge_request=request.auto_merge_request,
        mcp_server_name=request.mcp_server_name,
        mcp_failure_mode=request.mcp_failure_mode,
        git_provider=request.git_provider,
        agent_type=request.agent_type,
        status=RunStatus.queued,
        step="Queued",
        messages=[ChatMessage(role="user", content=request.request)],
    )
    tasks[run_id] = state
    save_tasks(tasks)
    track_worker(run_id, asyncio.create_task(run_task(request, state)))
    return state


@app.post("/api/test-setup")
async def run_manual_test_setup(request: TestSetupRequest):
    if not request.confirm_test_database:
        raise HTTPException(422, "Confirm that this is a disposable local test database before running setup")
    try:
        output = await run_test_setup(repository(request.project_path))
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"output": output}


def get_state(run_id: str) -> TaskState:
    if run_id not in tasks:
        raise HTTPException(404, "Task run not found")
    return tasks[run_id]


async def run_task(request: TaskRequest, state: TaskState) -> None:
    await execute_task(request, state)
    save_tasks(tasks)
    await advance_todo_queue(state)


async def run_follow_up(message: str, state: TaskState) -> None:
    await continue_task(message, state)
    save_tasks(tasks)
    await advance_todo_queue(state)


async def complete_automatic_delivery(state: TaskState) -> bool:
    """Finish optional delivery steps before allowing the Todo queue to advance."""
    if state.status != RunStatus.passed:
        return False
    if not state.auto_commit:
        return state.committed or not state.changed_files
    try:
        if state.changed_files and not state.committed:
            if state.auto_generate_commit_message and not state.commit_message:
                state.commit_message = await generate_commit_message(state)
            message = state.commit_message or f"feat({state.task_id}): complete task"
            await git_commit(state, message)
        if state.auto_push and state.committed and not state.pushed:
            await git_push(state)
        if state.auto_merge_request and state.pushed and not state.merge_request_url:
            await create_merge_request(state)
        return True
    except (ValueError, RuntimeError) as exc:
        state.status, state.step, state.error = RunStatus.failed, "Automatic delivery failed", str(exc)
        state.logs.append(f"Automatic delivery failed: {exc}")
        return False


def queue_follow_up(state: TaskState, message: str) -> None:
    if state.status in {RunStatus.queued, RunStatus.running, RunStatus.testing}:
        raise HTTPException(409, "Wait for the current agent response before sending another message")
    if not state.codex_thread_id:
        raise HTTPException(409, "This task does not have a resumable agent session")
    state.messages.append(ChatMessage(role="user", content=message))
    state.status, state.step, state.error = RunStatus.queued, "Queued follow-up", None
    save_tasks(tasks)
    track_worker(state.id, asyncio.create_task(run_follow_up(message, state)))


def pending_todos() -> list[tuple[TaskState, TodoItem]]:
    """Return the shared Todo queue in the exact order in which it was recorded."""
    items = [
        (state, todo)
        for state in tasks.values()
        for todo in state.todos
        if todo.status == "pending"
    ]
    return sorted(items, key=lambda item: (item[1].order, item[1].id))


def todo_is_due(todo: TodoItem, now: datetime | None = None) -> bool:
    """Unscheduled Todos are immediate; scheduled ones become eligible at their UTC deadline."""
    if todo.scheduled_for is None:
        return True
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        current = current.replace(tzinfo=timezone.utc)
    return todo.scheduled_for <= current.astimezone(timezone.utc)


def due_todos(*, scheduled_only: bool = False) -> list[tuple[TaskState, TodoItem]]:
    return [
        (owner, todo)
        for owner, todo in pending_todos()
        if todo_is_due(todo) and (not scheduled_only or todo.scheduled_for is not None)
    ]


def todo_destination(todo: TodoItem) -> TaskState | None:
    """Resolve a Todo target: current session, then branch, then project."""
    terminal = {RunStatus.passed, RunStatus.failed, RunStatus.blocked, RunStatus.stopped}
    session = tasks.get(todo.session_id)
    if session and session.status in terminal and session.codex_thread_id:
        return session
    branch_matches = [
        state for state in reversed(list(tasks.values()))
        if state.status in terminal and state.codex_thread_id
        and state.project_path == todo.project_path and state.branch == todo.branch
    ]
    if branch_matches:
        return branch_matches[0]
    project_matches = [
        state for state in reversed(list(tasks.values()))
        if state.status in terminal and state.codex_thread_id and state.project_path == todo.project_path
    ]
    return project_matches[0] if project_matches else None


def discard_todo(owner: TaskState, todo: TodoItem) -> None:
    owner.todos = [item for item in owner.todos if item.id != todo.id]


def start_todo_task(owner: TaskState, todo: TodoItem) -> None:
    """Create a normal Taskloom task when no resumable session can accept the Todo."""
    project_path = todo.project_path or owner.project_path
    branch = valid_branch_name(todo.branch or owner.branch)
    branch_task_id = branch.removeprefix("tasks/")
    task_id = branch_task_id if branch.startswith("tasks/") and "/" not in branch_task_id else f"todo-{todo.id}"
    request = TaskRequest(
        project_path=project_path,
        task_id=task_id,
        request=todo.content,
        base_branch=owner.base_branch,
        guide_paths=owner.guide_paths,
        role=owner.role,
        test_command=owner.test_command,
        test_working_directory=owner.test_working_directory,
        test_setup_enabled=owner.test_setup_enabled,
        auto_commit=owner.auto_commit,
        auto_generate_commit_message=owner.auto_generate_commit_message,
        auto_push=owner.auto_push,
        auto_merge_request=owner.auto_merge_request,
        mcp_server_name=owner.mcp_server_name,
        mcp_failure_mode=owner.mcp_failure_mode,
        git_provider=owner.git_provider,
        agent_type=owner.agent_type,
    )
    repo = repository(request.project_path)
    run_id = uuid.uuid4().hex[:12]
    state = TaskState(
        id=run_id,
        task_id=request.task_id,
        session_name=request.task_id,
        project_path=str(repo),
        branch=branch,
        base_branch=request.base_branch,
        guide_paths=request.guide_paths,
        role=request.role,
        role_knowledge_path=getattr(load_role_knowledge(), request.role.value),
        test_command=request.test_command,
        test_working_directory=request.test_working_directory,
        test_setup_enabled=request.test_setup_enabled,
        auto_commit=request.auto_commit,
        auto_generate_commit_message=request.auto_generate_commit_message,
        auto_push=request.auto_push,
        auto_merge_request=request.auto_merge_request,
        mcp_server_name=request.mcp_server_name,
        mcp_failure_mode=request.mcp_failure_mode,
        git_provider=request.git_provider,
        agent_type=request.agent_type,
        status=RunStatus.queued,
        step="Queued Todo",
        messages=[ChatMessage(role="user", content=request.request)],
    )
    tasks[run_id] = state
    discard_todo(owner, todo)
    save_tasks(tasks)
    track_worker(run_id, asyncio.create_task(run_task(request, state)))


def start_todo_follow_up(owner: TaskState, todo: TodoItem, destination: TaskState) -> None:
    destination.messages.append(ChatMessage(role="user", content=todo.content))
    destination.status, destination.step, destination.error = RunStatus.queued, "Queued Todo", None
    discard_todo(owner, todo)
    save_tasks(tasks)
    track_worker(destination.id, asyncio.create_task(run_follow_up(todo.content, destination)))


async def advance_todo_queue(state: TaskState) -> None:
    """Finish the session and branch queue before delivery and fresh branches."""
    active = {RunStatus.queued, RunStatus.running, RunStatus.testing}
    if state.status != RunStatus.passed or any(item.status in active for item in tasks.values()):
        return
    pending = due_todos()
    session_items = [(owner, todo) for owner, todo in pending if todo.session_id == state.id]
    branch_items = [
        (owner, todo) for owner, todo in pending
        if todo.session_id != state.id
        and todo.project_path == state.project_path and todo.branch == state.branch
    ]
    if session_items:
        owner, todo = session_items[0]
        start_todo_follow_up(owner, todo, state)
        return
    if branch_items and state.codex_thread_id:
        owner, todo = branch_items[0]
        start_todo_follow_up(owner, todo, state)
        return
    if not await complete_automatic_delivery(state):
        save_tasks(tasks)
        return
    save_tasks(tasks)
    await dispatch_next_todo()


async def dispatch_next_todo(*, scheduled_only: bool = False) -> None:
    """Run only one queued Todo at a time, preserving the user-defined order."""
    active = {RunStatus.queued, RunStatus.running, RunStatus.testing}
    if any(state.status in active for state in tasks.values()):
        return
    for owner, todo in due_todos(scheduled_only=scheduled_only):
        try:
            destination = todo_destination(todo)
            if destination:
                start_todo_follow_up(owner, todo, destination)
                return
            start_todo_task(owner, todo)
            return
        except (ValueError, RuntimeError) as exc:
            todo.status, todo.error = "failed", str(exc)
            save_tasks(tasks)


async def todo_scheduler() -> None:
    """Release due Todos, including persisted deadlines recovered after a restart."""
    while True:
        try:
            await dispatch_next_todo(scheduled_only=True)
        except Exception:
            # A transient persistence or repository error must not permanently
            # stop later deadlines from being checked.
            pass
        await asyncio.sleep(0.5)


@app.get("/api/tasks/{run_id}", response_model=TaskState)
async def task_status(run_id: str):
    return get_state(run_id)


@app.patch("/api/tasks/{run_id}", response_model=TaskState)
async def rename_task(run_id: str, request: RenameTaskRequest):
    """Rename the user-facing session label without changing its branch or task ID."""
    state = get_state(run_id)
    state.session_name = request.session_name
    save_tasks(tasks)
    return state


@app.patch("/api/tasks/{run_id}/role", response_model=TaskState)
async def set_task_role(run_id: str, request: TaskRoleRequest):
    state = get_state(run_id)
    state.role = request.role
    state.role_knowledge_path = getattr(load_role_knowledge(), request.role.value)
    save_tasks(tasks)
    return state


@app.delete("/api/tasks/{run_id}", status_code=204)
async def delete_task(run_id: str):
    """Permanently remove a finished session from memory and saved history."""
    state = get_state(run_id)
    terminal = {RunStatus.passed, RunStatus.failed, RunStatus.blocked, RunStatus.stopped}
    if state.status not in terminal:
        raise HTTPException(409, "Stop or finish the task before deleting its session")

    remaining = {task_id: task for task_id, task in tasks.items() if task_id != run_id}
    save_tasks(remaining)
    tasks.pop(run_id, None)
    task_workers.pop(run_id, None)


@app.get("/api/tasks/{run_id}/events")
async def task_events(run_id: str, request: Request):
    """Stream changing task snapshots so the UI can render Codex output live."""
    get_state(run_id)

    async def snapshots():
        previous = ""
        while True:
            if await request.is_disconnected():
                return
            state = get_state(run_id)
            serialized = state.model_dump_json()
            if serialized != previous:
                yield f"data: {serialized}\n\n"
                previous = serialized
            if state.status in {RunStatus.passed, RunStatus.failed, RunStatus.blocked, RunStatus.stopped}:
                return
            await asyncio.sleep(0.1)

    return StreamingResponse(
        snapshots(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/tasks/{run_id}/messages", response_model=TaskState, status_code=202)
async def send_message(run_id: str, request: ChatRequest):
    state = get_state(run_id)
    message = request.message.strip()
    queue_follow_up(state, message)
    return state


@app.post("/api/tasks/{run_id}/todos", response_model=TaskState)
async def add_todo(run_id: str, request: TodoRequest):
    state = get_state(run_id)
    next_order = max((todo.order for _, todo in pending_todos()), default=0) + 1
    state.todos.append(TodoItem(
        id=uuid.uuid4().hex[:12],
        content=request.content,
        project_path=request.project_path or state.project_path,
        branch=request.branch or state.branch,
        session_id=request.session_id or state.id,
        order=next_order,
        scheduled_for=request.scheduled_for,
    ))
    save_tasks(tasks)
    await advance_todo_queue(state)
    return state


@app.delete("/api/tasks/{run_id}/todos/{todo_id}", response_model=TaskState)
async def delete_todo(run_id: str, todo_id: str):
    state = get_state(run_id)
    original_count = len(state.todos)
    state.todos = [todo for todo in state.todos if todo.id != todo_id]
    if len(state.todos) == original_count:
        raise HTTPException(404, "Todo not found")
    save_tasks(tasks)
    return state


@app.post("/api/tasks/{run_id}/todos/{todo_id}/send", response_model=TaskState, status_code=202)
async def send_todo(run_id: str, todo_id: str):
    state = get_state(run_id)
    todo = next((item for item in state.todos if item.id == todo_id), None)
    if todo is None:
        raise HTTPException(404, "Todo not found")
    queue_follow_up(state, todo.content)
    discard_todo(state, todo)
    save_tasks(tasks)
    return state


@app.post("/api/tasks/{run_id}/stop", response_model=TaskState)
async def stop_task(run_id: str):
    state = get_state(run_id)
    if state.status not in {RunStatus.queued, RunStatus.running, RunStatus.testing}:
        raise HTTPException(409, "This task is not currently running")

    state.step = "Stopping agent"
    worker = task_workers.get(run_id)
    if worker is not None and not worker.done():
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass
    if state.status in {RunStatus.queued, RunStatus.running, RunStatus.testing}:
        state.status, state.step, state.error = RunStatus.stopped, "Stopped by user", None
        state.logs.append("Run stopped by user")
    save_tasks(tasks)
    return state


@app.post("/api/tasks/{run_id}/commit")
async def commit(run_id: str, request: CommitRequest):
    state = get_state(run_id)
    try:
        result = {"ok": True, "output": await git_commit(state, request.message.strip()), "task": state}
        save_tasks(tasks)
        await advance_todo_queue(state)
        return result
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/api/tasks/{run_id}/commit-message")
async def suggest_commit_message(run_id: str):
    state = get_state(run_id)
    try:
        return {"message": await generate_commit_message(state)}
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/api/tasks/{run_id}/push")
async def push(run_id: str):
    state = get_state(run_id)
    try:
        result = {"ok": True, "output": await git_push(state), "task": state}
        save_tasks(tasks)
        return result
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/api/tasks/{run_id}/merge-request")
async def merge_request(run_id: str):
    state = get_state(run_id)
    try:
        output = await create_merge_request(state)
        save_tasks(tasks)
        return {"ok": True, "output": output, "url": state.merge_request_url, "task": state}
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(409, str(exc)) from exc


# ===== SDLC PLATFORM API ENDPOINTS =====

# Initialize SDLC managers
sdlc_project_manager = SDLCProjectManager()
sdlc_task_manager = SDLCTaskManager()


@app.get("/api/sdlc/projects", response_model=list[SDLCProjectConfig])
async def list_sdlc_projects():
    """List all SDLC project configurations"""
    return sdlc_project_manager.list_projects()


@app.post("/api/sdlc/project-builder")
async def build_sdlc_project(request: project_builder.BuildRequest):
    """From a free-text idea: create the stage folders, system prompts, starter files and Git repositories, and save the
    project so tasks can be given to it right away. `preview: true` only returns the plan (nothing is written)."""
    existing = {item.id for item in sdlc_project_manager.list_projects()}
    if request.preview:
        return project_builder.preview(request, existing)
    try:
        return await project_builder.build(request, existing, sdlc_project_manager.save_project)
    except project_builder.BuildError as exc:
        raise HTTPException(409, str(exc)) from exc
    except (OSError, RuntimeError) as exc:
        raise HTTPException(500, f"Could not build the project: {exc}") from exc


@app.get("/api/sdlc/projects/{project_id}", response_model=SDLCProjectConfig)
async def get_sdlc_project(project_id: str):
    """Get SDLC project configuration by ID"""
    project = sdlc_project_manager.get_project(project_id)
    if not project:
        raise HTTPException(404, f"SDLC project {project_id} not found")
    return project


@app.post("/api/sdlc/projects", response_model=SDLCProjectConfig)
async def create_sdlc_project(project: SDLCProjectConfig):
    """Create new SDLC project configuration"""
    # Check if project already exists
    existing = sdlc_project_manager.get_project(project.id)
    if existing:
        raise HTTPException(409, f"Project {project.id} already exists. Use PUT to update.")
    
    try:
        sdlc_project_manager.save_project(project)
        return project
    except RuntimeError as exc:
        raise HTTPException(500, str(exc)) from exc


@app.put("/api/sdlc/projects/{project_id}", response_model=SDLCProjectConfig)
async def update_sdlc_project(project_id: str, project: SDLCProjectConfig):
    """Update existing SDLC project configuration"""
    # Verify project exists
    existing = sdlc_project_manager.get_project(project_id)
    if not existing:
        raise HTTPException(404, f"Project {project_id} not found")
    
    # Ensure ID consistency
    if project.id != project_id:
        raise HTTPException(400, "Project ID cannot be changed")
    
    try:
        sdlc_project_manager.save_project(project)
        return project
    except RuntimeError as exc:
        raise HTTPException(500, str(exc)) from exc


@app.get("/api/sdlc/projects/{project_id}/tasks/count")
async def count_sdlc_project_tasks(project_id: str):
    """How many tasks a project delete would remove (shown in the confirmation dialog)."""
    return {"count": len(await sdlc_task_manager.project_task_ids(project_id))}


@app.delete("/api/sdlc/projects/{project_id}")
async def delete_sdlc_project(project_id: str):
    """Delete an SDLC project together with its tasks and their inbox items.

    Nothing is deleted while one of the project's tasks is running. Git repositories and their
    sdlc/<task-id> branches are left untouched."""
    if not sdlc_project_manager.get_project(project_id):
        raise HTTPException(404, f"SDLC project {project_id} not found")
    try:
        deleted = await sdlc_task_manager.delete_project_tasks(project_id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    run_processes.stop_project(project_id)
    sdlc_project_manager.delete_project(project_id)
    return {"project_id": project_id, "deleted_tasks": deleted}


def _stage_folder(project_id: str, stage: str) -> tuple[SDLCProjectConfig, Path]:
    project = sdlc_project_manager.get_project(project_id)
    if not project or stage not in project.agents:
        raise HTTPException(404, f"Project {project_id} or its agent {stage} not found")
    folder = project.stage_path(stage)
    if not folder or not Path(folder).expanduser().is_dir():
        raise HTTPException(400, f"The {stage} stage's folder does not exist: {folder or '(no project path set)'}")
    return project, Path(folder).expanduser().resolve()


def _run_target(project_id: str, stage: str) -> tuple[str, str]:
    """(command, folder) of a stage's ▶ Run button."""
    project, folder = _stage_folder(project_id, stage)
    cmd = project.agents[stage].run_command.strip()
    if not cmd:
        raise HTTPException(400, f"The {stage} stage has no run command; set one in the project settings")
    return cmd, str(folder)


class RunStartRequest(BaseModel):
    mode: Optional[str] = None  # "test" | "real": let Claude Code follow the guide; None: the plain run command


class RunGuideRequest(BaseModel):
    content: str


@app.get("/api/sdlc/projects/{project_id}/agents/{stage}/run-guide")
async def get_run_guides(project_id: str, stage: str):
    """The stage's RUN_TEST.md / RUN_REAL.md (a starter template where the file does not exist yet)."""
    _, folder = _stage_folder(project_id, stage)
    return {"folder": str(folder), "guides": run_guides.read_guides(folder, stage)}


@app.put("/api/sdlc/projects/{project_id}/agents/{stage}/run-guide/{mode}")
async def save_run_guide(project_id: str, stage: str, mode: str, body: RunGuideRequest):
    if mode not in run_guides.GUIDE_FILES:
        raise HTTPException(400, "mode must be 'test' or 'real'")
    _, folder = _stage_folder(project_id, stage)
    run_guides.write_guide(folder, mode, body.content)
    return {"file": run_guides.GUIDE_FILES[mode], "saved": True}


@app.get("/api/sdlc/projects/{project_id}/run")
async def sdlc_run_overview(project_id: str):
    """Which stages of a project are running their run command right now."""
    return {"running": run_processes.running_stages(project_id)}


@app.post("/api/sdlc/projects/{project_id}/agents/{stage}/run/start")
async def start_stage_run(project_id: str, stage: str, body: Optional[RunStartRequest] = None):
    mode = body.mode if body else None
    try:
        if mode is None:
            cmd, folder = _run_target(project_id, stage)
            return run_processes.start(project_id, stage, cmd, folder)
        if mode == "setup":
            project, folder = _stage_folder(project_id, stage)
            cmd = project.agents[stage].setup_command.strip()
            if not cmd:
                raise HTTPException(400, f"The {stage} stage has no install command; set one in the project settings")
            return run_processes.start_process(project_id, stage, lambda key: run_processes.RunProcess(
                key, cmd, cmd, str(folder), mode="setup"))
        if mode not in run_guides.GUIDE_FILES:
            raise HTTPException(400, "mode must be 'test', 'real' or 'setup'")
        project, folder = _stage_folder(project_id, stage)
        guide = run_guides.guide_path(folder, mode)
        if not guide.is_file() or not guide.read_text(encoding="utf-8", errors="replace").strip():
            raise HTTPException(400, f"Write and save {guide.name} first")
        try:
            executable = agent_executable(AgentType.claude)
        except RuntimeError as exc:
            raise HTTPException(400, str(exc)) from exc
        pid_file = Path("data/run-pids") / f"{project_id}-{stage}.pids"
        prompt = run_guides.build_run_prompt(mode, stage, project.name, folder, pid_file.resolve())
        args = [executable, "--print", "--verbose", "--output-format", "stream-json",
                "--permission-mode", "acceptEdits", "--allowedTools", "Bash", "Read", "Edit", "Write"]
        return run_processes.start_process(project_id, stage, lambda key: run_processes.RunProcess(
            key, f"{guide.name} (Claude Code)", args, str(folder), mode=mode, stdin_text=prompt,
            pid_file=pid_file.resolve(), formatter=run_processes.format_claude_event))
    except OSError as exc:
        raise HTTPException(400, f"Could not start the command: {exc}") from exc


@app.post("/api/sdlc/projects/{project_id}/agents/{stage}/run/stop")
async def stop_stage_run(project_id: str, stage: str):
    return await asyncio.to_thread(run_processes.stop, project_id, stage)


@app.get("/api/sdlc/projects/{project_id}/agents/{stage}/run")
async def stage_run_status(project_id: str, stage: str):
    return run_processes.status(project_id, stage)


@app.delete("/api/sdlc/tasks/{task_id}")
async def delete_sdlc_task(task_id: str):
    """Delete one SDLC task and its inbox items."""
    try:
        if not await sdlc_task_manager.delete_task(task_id):
            raise HTTPException(404, f"SDLC task {task_id} not found")
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"task_id": task_id, "deleted": True}


@app.get("/api/sdlc/tasks", response_model=list[SDLCTask])
async def list_sdlc_tasks(
    status: Optional[str] = None,
    project: Optional[str] = None
):
    """List SDLC tasks with optional filters"""
    tasks = await sdlc_task_manager.list_tasks(status_filter=status, project_filter=project)
    return tasks


@app.get("/api/sdlc/tasks/{task_id}", response_model=SDLCTask)
async def get_sdlc_task(task_id: str):
    """Get SDLC task by ID"""
    task = await sdlc_task_manager.load_task(task_id)
    if not task:
        raise HTTPException(404, f"SDLC task {task_id} not found")
    return sdlc_task_manager.with_live_output(task)


@app.post("/api/sdlc/tasks", response_model=SDLCTask, status_code=202)
async def create_sdlc_task(request: SDLCTaskRequest):
    """Create a new SDLC task and enqueue it for analysis"""
    project = sdlc_project_manager.get_project(request.project_id)
    if not project:
        raise HTTPException(404, f"Project {request.project_id} not found")

    if not project.sdlc_enabled:
        raise HTTPException(400, f"Project {request.project_id} does not have SDLC enabled")

    task_uuid = uuid.uuid4().hex
    sdlc_task_id = sdlc_task_manager.next_task_id("SDLC")  # SDLC-1001, ...: also the task's Git branch
    base_task_state = TaskState(
        id=task_uuid[:12],
        task_id=sdlc_task_id,
        session_name=request.title[:100],
        project_path=project.agents.get("backend", AgentConfig()).project_path or "",
        branch=sdlc_task_id,
        base_branch=SANDBOX,
        guide_paths=[],
        role="analyst",
        role_knowledge_path="",
        test_command=None,
        test_working_directory=None,
        test_setup_enabled=False,
        auto_commit=False,
        auto_generate_commit_message=False,
        auto_push=False,
        auto_merge_request=False,
        test_setup_output="",
        mcp_server_name=None,
        mcp_failure_mode=McpFailureMode.warning,
        mcp_status="not_configured",
        mcp_message="",
        git_provider=GitProvider.auto,
        agent_type=AgentType.codex,
        status=RunStatus.queued,
        step="SDLC task created",
        logs=[],
        live_output="",
        live_response="",
        summary=request.description[:1000],
        diff="",
        changed_files=[],
        test_output="",
        commit_message="",
        error=None,
        committed=False,
        pushed=False,
        merge_request_url="",
        codex_thread_id="",
        messages=[ChatMessage(role="user", content=request.description)],
        todos=[]
    )

    try:
        task = await sdlc_task_manager.create_task(request, project, base_task_state)
        return task
    except Exception as exc:
        raise HTTPException(500, f"Failed to create SDLC task: {exc}") from exc


@app.post("/api/sdlc/tasks/{task_id}/transition", response_model=SDLCTask)
async def transition_sdlc_task(task_id: str, transition: StageTransitionRequest):
    """Transition SDLC task to next stage"""
    if task_id != transition.task_id:
        raise HTTPException(422, "Task ID in URL and body must match")
    
    task = await sdlc_task_manager.load_task(task_id)
    if not task:
        raise HTTPException(404, f"SDLC task {task_id} not found")
    
    try:
        if transition.force:
            # Force transition to specified stage
            await sdlc_task_manager.execute_stage(task_id, transition.stage)
        else:
            # Transition to next stage in workflow
            success = await sdlc_task_manager.transition_to_next_stage(task_id)
            if not success:
                raise HTTPException(400, "Cannot transition task to next stage")
        
        # Return updated task
        updated_task = await sdlc_task_manager.load_task(task_id)
        return updated_task
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, f"Failed to transition task: {exc}") from exc


class SendBackRequest(BaseModel):
    feedback: str


@app.post("/api/sdlc/tasks/{task_id}/send-back", response_model=SDLCTask)
async def send_back_sdlc_task(task_id: str, body: SendBackRequest, request: Request):
    """A human wrote that something is wrong: the analyst runs again with that opinion and the human re-approves."""
    actor = (request.headers.get("X-Taskloom-User") or "human").strip()[:80] or "human"
    try:
        return await sdlc_task_manager.send_back_to_analysis(task_id, body.feedback, actor)
    except ValueError as exc:
        raise HTTPException(404 if "not found" in str(exc) else 409, str(exc)) from exc


def require_admin(request: Request) -> str:
    """Authorisation for final approvals and release actions. Taskloom has no user accounts: set TASKLOOM_ADMIN_TOKEN
    and every such request must send it in `X-Taskloom-Admin-Token` (the dashboard asks for it once). The optional
    `X-Taskloom-User` header names the person for the audit fields (created_by / approved_by)."""
    expected = os.environ.get("TASKLOOM_ADMIN_TOKEN", "").strip()
    if expected and not hmac.compare_digest(request.headers.get("X-Taskloom-Admin-Token", ""), expected):
        raise HTTPException(403, "An administrator token is required for this action")
    return (request.headers.get("X-Taskloom-User") or "admin").strip()[:80] or "admin"


_integrating: set[str] = set()  # task ids whose final approval is running right now (no duplicate merges)


async def stage_for_repository(project, root_text: str) -> str | None:
    """The stage whose configured repository lives at `root_text` (None when no stage manages it)."""
    for name, config in project.agents.items():
        folder = project.stage_path(name)
        if config.enabled and config.repository.mode.value != "none" and folder:
            root = await git_root(Path(folder).expanduser())
            if root is not None and str(root) == root_text:
                return name
    return None


async def integrate_sdlc_task(task: SDLCTask, project: SDLCProjectConfig | None) -> list[str]:
    """Commit the task's work and merge its branch into `develop` in every repository it touched.

    Returns the problems found (empty when everything merged). Each repository's result is written to the
    task as soon as Git has confirmed it; a failure never marks anything as merged."""
    problems: list[str] = []
    for key, repo in list(task.repos.items()):
        root = Path(key)
        stage = await stage_for_repository(project, key) if project else None
        token = sdlc_project_manager.github_token(project.id, stage) if project and stage else None
        try:
            await commit_task_work(root, repo.branch, commit_message(task))
            result = await integrate_task(root, task.base_task.task_id, repo.branch, token)
            def record(latest, key=key, result=result):
                record_merge(latest.repos[key].integration, Path(key), result)
                policy.record_event(latest, "merged", f"{Path(key).name}: `{latest.repos[key].branch}` merged into develop "
                                    f"({result.merge_commit_sha[:10] or 'already merged'})")
        except (GitFlowError, RuntimeError) as exc:
            problems.append(f"{root.name}: {exc}")
            record = lambda latest, key=key, exc=exc: record_failure(latest.repos[key].integration, Path(key), exc)
        await sdlc_task_manager.update_task(task.base_task.task_id, record)
    return problems


async def finalize_approval(task_id: str, actor: str = "human", reason: str = "") -> SDLCTask:
    """The final approval, shared by the human button and the automatic policy: merge the task branch into `develop`
    and only after Git confirmed every merge move the task from pending_approval to done. A conflict or any Git
    failure leaves it pending_approval (HTTP 409 with the reason)."""
    task = await sdlc_task_manager.load_task(task_id)
    if not task:
        raise HTTPException(404, f"SDLC task {task_id} not found")
    if task.sdlc_status != SDLCStatus.pending_approval:
        raise HTTPException(409, f"Task status is {task.sdlc_status.value}, not pending_approval")
    if task_id in _integrating:
        raise HTTPException(409, f"Task {task_id} is already being integrated into develop")
    _integrating.add(task_id)
    try:
        project = sdlc_project_manager.get_project(task.project_config_id)
        problems = await integrate_sdlc_task(task, project)
        if problems:
            message = "Final approval did not complete; the task is still waiting for approval. " + " ".join(problems)
            await sdlc_task_manager.update_task(task_id, lambda latest: (
                setattr(latest, "transition_reason", message[:1000]), latest.base_task.logs.append(message[:2000]),
                policy.record_event(latest, "escalated", "Merge into develop failed: " + " ".join(problems)[:300], actor=actor)))
            raise HTTPException(409, message)

        def approve(latest: SDLCTask) -> None:
            if latest.sdlc_status != SDLCStatus.pending_approval:
                raise ValueError(f"Task status is {latest.sdlc_status.value}, not pending_approval")
            latest.previous_status = latest.sdlc_status
            latest.sdlc_status = SDLCStatus.done
            latest.transition_reason = "Approved by human; merged into develop" if latest.repos else "Approved by human"
            if actor != "human":
                latest.transition_reason = latest.transition_reason.replace("Approved by human", "Approved automatically")
            policy.record_event(latest, "approved" if actor == "human" else "auto_approved",
                                reason or "Final approval", actor=actor)
            latest.updated_at = datetime.now(timezone.utc)

        try:
            task = await sdlc_task_manager.update_task(task_id, approve)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        if not task:
            raise HTTPException(404, f"SDLC task {task_id} not found")
        notes = await publish_approved_task(task_id)
        if notes:
            task = await sdlc_task_manager.update_task(task_id, lambda latest: (
                setattr(latest, "transition_reason", latest.transition_reason + ". " + " ".join(notes)),
                latest.base_task.logs.extend(notes),
            )) or task
    finally:
        _integrating.discard(task_id)
    if project:
        await maybe_auto_release(project)
    return task


@app.post("/api/sdlc/tasks/{task_id}/approve", response_model=SDLCTask)
async def approve_sdlc_task(task_id: str, _: str = Depends(require_admin)):
    """Final human approval (see finalize_approval)."""
    return await finalize_approval(task_id, actor="human", reason="Approved by the administrator")


async def auto_approve_task(task_id: str, reason: str) -> bool:
    """The policy hook of SDLCTaskManager: approve a low-risk task without a human. False = a human must decide."""
    try:
        await finalize_approval(task_id, actor="taskloom", reason=reason)
    except HTTPException as exc:
        print(f"[SDLC] Automatic approval of {task_id} did not complete: {exc.detail}", flush=True)
        return False
    return True


sdlc_task_manager.auto_approver = auto_approve_task


async def maybe_auto_release(project: SDLCProjectConfig) -> str | None:
    """Policy `auto_release`: when enough of this project's tasks sit unreleased in develop, build and validate a release.
    The release then waits for a human approval like any other: Taskloom never merges into sandbox by itself."""
    workflow = project.workflow
    if not workflow.auto_release:
        return None
    try:
        rows = [row for row in await release_manager.eligible_tasks()
                if row["eligible"] and row["workflow"] == "SDLC" and row["project_id"] == project.id]
        by_repository: dict[str, list[dict]] = {}
        for row in rows:
            by_repository.setdefault(row["repository_id"], []).append(row)
        for repository_id, items in by_repository.items():
            if len(items) < max(1, workflow.auto_release_min_tasks):
                continue
            releases = [r for r in release_manager.store.list() if r.repository_id == repository_id]
            if any(r.status in (ReleaseStatus.draft, ReleaseStatus.preparing, ReleaseStatus.testing, ReleaseStatus.waiting_approval,
                                ReleaseStatus.approved, ReleaseStatus.merging) for r in releases):
                continue  # one release at a time per repository: finish (or cancel) the open one first
            version = next_release_version([r.version for r in releases if r.status in HOLDING])
            items.sort(key=lambda item: min((m.get("merged_at") or "") for m in item["pending_merges"]))  # oldest merge first
            release = await release_manager.create(version, repository_id, [item["task_id"] for item in items], "taskloom-auto")
            release_manager.store.update(release.id, lambda r: r.logs.append(
                f"Created automatically: {len(items)} tasks reached develop (policy auto_release). A human approves the merge into sandbox."))
            return release.id
    except Exception as exc:  # a release draft is a convenience: never let it break the task's approval
        print(f"[SDLC] Automatic release draft failed: {exc}", flush=True)
    return None


@app.get("/api/sdlc/metrics")
async def sdlc_metrics(project: str = ""):
    """Delivery metrics: throughput, cycle time, first-pass and automation rates, stage timings, risk mix."""
    tasks_ = await sdlc_task_manager.list_tasks(project_filter=project or None)
    return compute_metrics(tasks_)


async def publish_approved_task(task_id: str) -> list[str]:
    """After the final approval and the merge into develop: push the task branch of every repository the task
    worked in so the work is on GitHub. Never opens a pull request into sandbox: sandbox only receives
    releases. Never raises: what could not be published is reported in the returned notes."""
    task = await sdlc_task_manager.load_task(task_id)
    project = sdlc_project_manager.get_project(task.project_config_id) if task else None
    if not task or not project:
        return []
    notes: list[str] = []
    for root_text, repo in list(task.repos.items()):
        stage = await stage_for_repository(project, root_text)
        if stage is None:
            notes.append(f"{Path(root_text).name}: no GitHub repository is configured for it, so the task branch was not pushed.")
            continue
        repository = project.stage_repository(stage)
        token = sdlc_project_manager.github_token(project.id, stage)
        try:
            repo_url = repository.url
            if not repo_url and repository.mode.value == "create":
                repo_url = await create_github_repository(project, stage, token, allow_rename=True)
                repository.url = repo_url
                sdlc_project_manager.save_project(project)
            if not repo_url:
                raise GitHubError("Repository URL is required")
            await commit_and_push(task, repo, repo_url, token)
            notes.append(f"{stage}: pushed `{repo.branch}`.")
        except (GitHubError, RuntimeError) as exc:
            notes.append(f"{stage}: could not push `{repo.branch}` ({exc}).")
        await sdlc_task_manager.update_task(task_id, lambda latest, key=root_text, value=repo: (
            setattr(latest.repos[key], "pushed", value.pushed), setattr(latest.repos[key], "commit_sha", value.commit_sha)))
    return notes


@app.post("/api/tasks/{run_id}/approve", response_model=TaskState)
async def approve_task(run_id: str, _: str = Depends(require_admin)):
    """Final human approval of a classic (DWS) task: merge its branch into `develop`; `done` only after Git confirmed it."""
    state = tasks.get(run_id)
    if not state:
        raise HTTPException(404, "Task not found")
    if state.status != RunStatus.passed:
        raise HTTPException(409, f"Task status is {state.status.value}; only a task whose run passed can be approved")
    if run_id in _integrating:
        raise HTTPException(409, "This task is already being integrated into develop")
    _integrating.add(run_id)
    try:
        root = Path(state.project_path)
        try:
            if state.branch == await _current_branch(root):  # work lives in the checked-out branch: commit it first
                await commit_task_work(root, state.branch, state.commit_message or f"feat({state.task_id}): implement requested changes")
            result = await integrate_task(root, state.task_id, state.branch)
        except (GitFlowError, RuntimeError) as exc:
            record_failure(state.git_integration, root, exc)
            state.logs.append(f"Final approval failed: {exc}")
            save_tasks(tasks)
            raise HTTPException(409, str(exc)) from exc
        record_merge(state.git_integration, root, result)
        state.committed = True
        state.status, state.step = RunStatus.done, "Approved and merged into develop"
        state.logs.append(f"Merged `{state.branch}` into develop ({result.merge_commit_sha[:10] or 'already merged'})")
        save_tasks(tasks)
        return state
    finally:
        _integrating.discard(run_id)


async def _current_branch(root: Path) -> str:
    code, output = await command(["git", "branch", "--show-current"], root)
    return output.strip() if code == 0 else ""


class GitHubActionRequest(BaseModel):
    """Body of the dashboard's GitHub buttons. `agent` selects the stage whose repository is used;
    empty URL/token fall back to that stage's saved repository settings, then to GITHUB_TOKEN."""
    agent: str = ""
    repo_url: str = ""
    github_token: str = ""
    title: str | None = None
    description: str | None = None


async def _github_context(task_id: str, request: GitHubActionRequest, need_repo: bool = True):
    """Resolve the task, project, the stage's repository record and the repo URL/token to use."""
    task = await sdlc_task_manager.load_task(task_id)
    if not task:
        raise HTTPException(404, f"SDLC task {task_id} not found")
    project = sdlc_project_manager.get_project(task.project_config_id)
    if not project:
        raise HTTPException(404, f"Project {task.project_config_id} not found")
    config = project.agents.get(request.agent) if request.agent else None
    if config:
        managed = config.repository.mode.value != "none"
        saved_url = config.repository.url if managed else str(config.github_config.get("repository_url") or "")
        repo_url = request.repo_url.strip() or saved_url
        token = request.github_token.strip() or sdlc_project_manager.github_token(project.id, request.agent)
        folder = project.stage_path(request.agent)
    elif not need_repo:  # validating a URL/token typed into the dashboard
        managed, repo_url, token, folder = False, request.repo_url.strip(), request.github_token.strip(), ""
    else:
        raise HTTPException(400, "agent is required")
    repo = None
    if need_repo:
        if not folder:
            raise HTTPException(400, f"Agent {request.agent} has no folder or repository")
        root = await git_root(Path(folder))
        if root is None:
            raise HTTPException(400, f"Not a Git repository: {folder}")
        repo = task.repos.get(str(root))
        if repo is None:
            raise HTTPException(400, f"The {request.agent} stage of this task has not worked in {root} yet")
    return task, project, repo, repo_url, token, managed


@app.post("/api/sdlc/tasks/{task_id}/github/validate")
async def validate_github(task_id: str, request: GitHubActionRequest):
    """Check that the repository exists and the token can access it (or, before a stage's new repo
    is created, that the token works and which account will own it)."""
    _, project, _, repo_url, token, managed = await _github_context(task_id, request, need_repo=False)
    try:
        if managed and not repo_url:
            return await describe_new_repository(project, request.agent, token)
        if not repo_url:
            return {"status": "invalid", "message": "Repository URL is required"}
        return await validate_repository(repo_url, token)
    except GitHubError as exc:
        return {"status": "invalid", "message": str(exc)}


@app.post("/api/sdlc/tasks/{task_id}/github/commit-push")
async def github_commit_push(task_id: str, request: GitHubActionRequest):
    """Commit the stage's changes on the task branch and push it; creates the stage's GitHub repo
    first when it is a new (from-scratch) repository without a URL yet."""
    task, project, repo, repo_url, token, managed = await _github_context(task_id, request)
    try:
        repository = project.stage_repository(request.agent)
        if not repo_url and managed and repository.mode.value == "create":
            repo_url = await create_github_repository(project, request.agent, token)
            repository.url = repo_url
            sdlc_project_manager.save_project(project)
        if not repo_url:
            raise GitHubError("Repository URL is required")
        result = await commit_and_push(task, repo, repo_url, token)
    except (GitHubError, RuntimeError) as exc:
        raise HTTPException(400, str(exc)) from exc
    # Git/GitHub took a while; merge only the repository record into the latest task.
    await sdlc_task_manager.update_task(task_id, lambda latest: latest.repos.__setitem__(repo.path, repo))
    return {**result, "repository_url": repo_url}


@app.post("/api/sdlc/tasks/{task_id}/github/create-pr")
async def github_create_pr(task_id: str, request: GitHubActionRequest):
    """Open (or find) the pull request for the task branch in the stage's repository."""
    task, _, repo, repo_url, token, _ = await _github_context(task_id, request)
    try:
        if not repo_url:
            raise GitHubError("Push the task first: the repository does not exist on GitHub yet")
        result = await create_pull_request(task, repo, repo_url, token, request.title, None)
    except GitHubError as exc:
        raise HTTPException(400, str(exc)) from exc
    # Git/GitHub took a while; merge only the repository record into the latest task.
    await sdlc_task_manager.update_task(task_id, lambda latest: latest.repos.__setitem__(repo.path, repo))
    return result


@app.post("/api/sdlc/projects/{project_id}/agents/{agent}/repository/prepare")
async def prepare_stage_repository(project_id: str, agent: str):
    """Clone (existing repo) or initialise (new repo) a stage's local repository now."""
    project = sdlc_project_manager.get_project(project_id)
    if not project or agent not in project.agents:
        raise HTTPException(404, f"Project {project_id} or its agent {agent} not found")
    if project.stage_repository(agent).mode.value == "none":
        raise HTTPException(400, f"The {agent} stage has no repository configured")
    try:
        path = await ensure_workspace(project, agent, sdlc_project_manager.github_token(project_id, agent))
    except (GitHubError, RuntimeError) as exc:
        raise HTTPException(400, str(exc)) from exc
    code, branch = await command(["git", "branch", "--show-current"], path)
    return {"path": str(path), "url": project.stage_repository(agent).url, "branch": branch.strip() if code == 0 else ""}


@app.post("/api/sdlc/human-intervention", response_model=dict)
async def create_human_intervention_request(
    task_id: str,
    agent: str,
    reason: str,
    description: str,
    context: dict = {},
    response_options: list[str] = []
):
    """Create a human intervention request"""
    try:
        intervention_id = await sdlc_task_manager.create_human_intervention(
            task_id, agent, reason, description, context, response_options
        )
        return {"intervention_id": intervention_id, "task_id": task_id}
    except Exception as exc:
        raise HTTPException(500, f"Failed to create human intervention: {exc}") from exc


@app.post("/api/sdlc/human-intervention/{intervention_id}/respond", response_model=dict)
async def respond_to_human_intervention(
    intervention_id: str,
    response: HumanInterventionResponse
):
    """Submit response to human intervention"""
    if intervention_id != response.intervention_id:
        raise HTTPException(422, "Intervention ID in URL and body must match")
    
    success = await sdlc_task_manager.submit_human_response(intervention_id, response.response)
    if not success:
        raise HTTPException(404, f"Human intervention {intervention_id} not found or already resolved")
    
    return {"success": True, "intervention_id": intervention_id}


@app.get("/api/sdlc/human-inbox/pending", response_model=list[HumanIntervention])
async def list_pending_human_interventions():
    """List pending human intervention requests (oldest first)"""
    return sdlc_task_manager.list_pending_interventions()


# ===== TEAM WORKFLOW EXTENSION API ENDPOINTS =====

@app.post("/api/sdlc/tasks/{task_id}/backend-review", response_model=SDLCTask)
async def submit_backend_review(task_id: str, request: Request):
    """Submit backend result for analyst review."""
    from .services import SDLCTask
    from .models import StageTransitionRequest
    
    task = sdlc_task_manager.get_task(task_id)
    if not task:
        raise HTTPException(404, f"Task {task_id} not found")
    
    try:
        # Transition to backend review stage
        transition = StageTransitionRequest(task_id=task_id, stage="backend_review", force=False)
        return await transition_sdlc_task(task_id, transition)
    except Exception as exc:
        raise HTTPException(400, f"Failed to submit backend review: {exc}") from exc


@app.post("/api/sdlc/tasks/{task_id}/frontend-review", response_model=SDLCTask)
async def submit_frontend_review(task_id: str, request: Request):
    """Submit frontend result for analyst review."""
    from .services import SDLCTask
    from .models import StageTransitionRequest
    
    task = sdlc_task_manager.get_task(task_id)
    if not task:
        raise HTTPException(404, f"Task {task_id} not found")
    
    try:
        # Transition to frontend review stage
        transition = StageTransitionRequest(task_id=task_id, stage="frontend_review", force=False)
        return await transition_sdlc_task(task_id, transition)
    except Exception as exc:
        raise HTTPException(400, f"Failed to submit frontend review: {exc}") from exc


@app.post("/api/sdlc/tasks/{task_id}/qa-review", response_model=SDLCTask)
async def submit_qa_review(task_id: str, request: Request):
    """Submit QA test results for review."""
    from .services import SDLCTask
    from .models import StageTransitionRequest, QAReport
    
    task = sdlc_task_manager.get_task(task_id)
    if not task:
        raise HTTPException(404, f"Task {task_id} not found")
    
    body = await request.json()
    qa_report_data = body.get("qa_report", {})
    
    try:
        # Create QA report
        qa_report = QAReport(
            id=f"qa-{task_id}",
            test_strategy=qa_report_data.get("test_strategy", "requirements-led, implementation-independent"),
            test_cases=[],
            coverage_gaps=qa_report_data.get("coverage_gaps", []),
            residual_risks=qa_report_data.get("residual_risks", []),
            overall_recommendation=qa_report_data.get("overall_recommendation", "pending")
        )
        
        # Update task with QA report
        await sdlc_task_manager.update_task(task_id, lambda t: setattr(t, "qa_report", qa_report))
        
        # Transition to QA review stage
        transition = StageTransitionRequest(task_id=task_id, stage="qa_review", force=False)
        return await transition_sdlc_task(task_id, transition)
    except Exception as exc:
        raise HTTPException(400, f"Failed to submit QA review: {exc}") from exc


@app.post("/api/sdlc/tasks/{task_id}/analyst-final-review", response_model=SDLCTask)
async def submit_analyst_final_review(task_id: str, request: Request):
    """Submit analyst's final assessment before PO approval."""
    from .models import StageTransitionRequest
    
    task = sdlc_task_manager.get_task(task_id)
    if not task:
        raise HTTPException(404, f"Task {task_id} not found")
    
    body = await request.json()
    final_summary = body.get("final_summary", "")
    
    try:
        # Update task with analyst final review
        await sdlc_task_manager.update_task(task_id, lambda t: setattr(t, "analyst_final_summary", final_summary))
        
        # Transition to analyst final review stage
        transition = StageTransitionRequest(task_id=task_id, stage="analyst_final_review", force=False)
        return await transition_sdlc_task(task_id, transition)
    except Exception as exc:
        raise HTTPException(400, f"Failed to submit analyst final review: {exc}") from exc


@app.post("/api/sdlc/tasks/{task_id}/po-approval", response_model=SDLCTask)
async def submit_po_decision(task_id: str, request: Request):
    """Submit Product Owner's decision on release readiness."""
    from .models import StageTransitionRequest, PODecision
    
    task = sdlc_task_manager.get_task(task_id)
    if not task:
        raise HTTPException(404, f"Task {task_id} not found")
    
    body = await request.json()
    decision_data = body.get("decision", {})
    
    try:
        # Create PO decision
        po_decision = PODecision(
            id=f"po-{task_id}",
            decision=decision_data.get("decision", "pending"),
            rationale=decision_data.get("rationale", ""),
            affected_requirements=decision_data.get("affected_requirements", []),
            revision_required=decision_data.get("revision_required", False),
            return_to_stage=decision_data.get("return_to_stage", "")
        )
        
        # Update task with PO decision
        await sdlc_task_manager.update_task(task_id, lambda t: setattr(t, "po_decision", po_decision))
        
        # Determine next stage based on decision
        if po_decision.decision == "approve":
            # Transition to release ready
            return await transition_sdlc_task(task_id, StageTransitionRequest(task_id=task_id, stage="release_ready", force=True))
        elif po_decision.decision == "changes_requested":
            # Return to appropriate stage
            return_to = po_decision.return_to_stage or "analyst_final_review"
            return await transition_sdlc_task(task_id, StageTransitionRequest(task_id=task_id, stage=return_to, force=True))
        else:  # reject
            return await transition_sdlc_task(task_id, StageTransitionRequest(task_id=task_id, stage="failed", force=True))
    except Exception as exc:
        raise HTTPException(400, f"Failed to submit PO decision: {exc}") from exc


@app.post("/api/sdlc/tasks/{task_id}/release-ready", response_model=SDLCTask)
async def mark_task_release_ready(task_id: str, request: Request):
    """Mark task as release-ready after PO approval."""
    from .models import StageTransitionRequest
    
    task = sdlc_task_manager.get_task(task_id)
    if not task:
        raise HTTPException(404, f"Task {task_id} not found")
    
    try:
        # Transition to release ready stage
        return await transition_sdlc_task(task_id, StageTransitionRequest(task_id=task_id, stage="release_ready", force=True))
    except Exception as exc:
        raise HTTPException(400, f"Failed to mark task as release-ready: {exc}") from exc


@app.get("/api/sdlc/tasks/{task_id}/workflow-status", response_model=dict)
async def get_workflow_status(task_id: str):
    """Get detailed workflow status for a task."""
    task = sdlc_task_manager.get_task(task_id)
    if not task:
        raise HTTPException(404, f"Task {task_id} not found")
    
    return {
        "current_stage": task.current_stage,
        "workflow_status": task.workflow_status,
        "current_review_stage": task.current_review_stage,
        "backend_review_status": task.backend_review_status,
        "frontend_review_status": task.frontend_review_status,
        "qa_review_status": task.qa_review_status,
        "analyst_final_review_status": task.analyst_final_review_status,
        "po_decision": task.po_decision.model_dump() if task.po_decision else None,
        "qa_report": task.qa_report.model_dump() if task.qa_report else None,
        "can_transition": task.current_stage in ["backend_running", "frontend_running", "qa_running", "analyst_final_review", "po_pending_approval"]
    }


@app.get("/api/sdlc/projects/{project_id}/default-workflow", response_model=list[str])
async def get_default_workflow(project_id: str):
    """Get the default workflow stages for a new project."""
    project = sdlc_project_manager.get_project(project_id)
    if not project:
        # Return default workflow
        return ["analysis", "backend", "backend_review", "frontend", "frontend_review", "qa", "qa_review", "analyst_final_review", "po_pending_approval"]
    
    return project.workflow.stages


# ===== OLLAMA MODEL MANAGEMENT API =====

@app.get("/api/ollama/models")
async def get_ollama_models():
    """Get list of available Ollama models"""
    try:
        discovery = OllamaDiscoveryService()
        models = await discovery.list_models()
        return [model.model_dump() for model in models]
    except Exception as exc:
        raise HTTPException(500, f"Failed to fetch Ollama models: {exc}")


@app.get("/api/ollama/connection")
async def check_ollama_connection():
    """Check if Ollama is reachable"""
    try:
        discovery = OllamaDiscoveryService()
        connected = await discovery.check_connection()
        return {"connected": connected}
    except Exception as exc:
        return {"connected": False, "error": str(exc)}


@app.get("/api/ollama/models/{model_name}")
async def get_ollama_model_info(model_name: str):
    """Get detailed information about a specific Ollama model"""
    try:
        discovery = OllamaDiscoveryService()
        model_info = await discovery.get_model_info(model_name)
        if not model_info:
            raise HTTPException(404, f"Model '{model_name}' not found")
        return model_info.model_dump()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to get model info: {exc}")


@app.get("/api/sdlc/projects/{project_id}/model-settings")
async def get_project_model_settings(project_id: str):
    """Get AI model settings for a project (legacy endpoint)"""
    project = sdlc_project_manager.get_project(project_id)
    if not project:
        raise HTTPException(404, f"Project {project_id} not found")
    
    # Return legacy model settings or convert from AI settings
    if project.model_settings:
        return project.model_settings.model_dump()
    else:
        # Convert from new AI settings to legacy format
        legacy_settings = {
            "default_model": project.ai_settings.default_model,
            "stage_assignments": {},
            "ollama_endpoint": project.ai_settings.ollama_endpoint
        }
        
        # Convert stage providers to stage assignments (only for Ollama)
        for stage, config in project.ai_settings.stage_providers.items():
            if config.provider == "ollama":
                legacy_settings["stage_assignments"][stage] = config.model
        
        return legacy_settings


@app.put("/api/sdlc/projects/{project_id}/model-settings")
async def update_project_model_settings(project_id: str, settings: dict):
    """Update AI model settings for a project (legacy endpoint)"""
    from .models import ProjectModelSettings
    project = sdlc_project_manager.get_project(project_id)
    if not project:
        raise HTTPException(404, f"Project {project_id} not found")
    
    try:
        # Ensure legacy model_settings exists
        if project.model_settings is None:
            project.model_settings = ProjectModelSettings()
        
        # Update legacy model settings
        if "default_model" in settings:
            project.model_settings.default_model = settings["default_model"]
        if "stage_assignments" in settings:
            project.model_settings.stage_assignments = settings["stage_assignments"]
        if "ollama_endpoint" in settings:
            project.model_settings.ollama_endpoint = settings["ollama_endpoint"]
        
        # Also update AI settings for backward compatibility
        project.ai_settings.default_model = settings.get("default_model", project.ai_settings.default_model)
        project.ai_settings.ollama_endpoint = settings.get("ollama_endpoint", project.ai_settings.ollama_endpoint)
        
        # Convert stage assignments to stage providers
        stage_assignments = settings.get("stage_assignments", {})
        for stage, model in stage_assignments.items():
            project.ai_settings.stage_providers[stage] = StageProviderConfig(
                provider="ollama",
                model=model,
                inherit_from_project=False
            )
        
        # Save the project
        sdlc_project_manager.save_project(project)
        return project.model_settings.model_dump()
    except Exception as exc:
        raise HTTPException(400, f"Invalid model settings: {exc}")


@app.get("/api/sdlc/projects/{project_id}/stage-model/{stage}")
async def get_stage_model(project_id: str, stage: str):
    """Get the resolved model for a specific stage (legacy endpoint)"""
    project = sdlc_project_manager.get_project(project_id)
    if not project:
        raise HTTPException(404, f"Project {project_id} not found")
    
    # Use new provider resolution
    agent_config = project.agents.get(stage)
    provider_info = await ProviderResolutionService().get_provider_info_for_stage(stage, project, agent_config)
    
    # For backward compatibility, only return model info for Ollama
    if provider_info["provider"] == "ollama":
        model_name = provider_info["model"]
        try:
            discovery = OllamaDiscoveryService()
            model_info = await discovery.get_model_info(model_name)
            return {
                "model": model_name,
                "info": model_info.model_dump() if model_info else None,
                "source": "project_default" if model_name == project.ai_settings.default_model else "stage_assignment",
                "provider": "ollama"
            }
        except Exception:
            return {
                "model": model_name,
                "info": None,
                "source": "project_default" if model_name == project.ai_settings.default_model else "stage_assignment",
                "provider": "ollama"
            }
    else:
        # For non-Ollama providers, return provider info
        return {
            "model": provider_info["model"],
            "info": None,
            "source": "provider_override" if provider_info["overridden"] else "project_default",
            "provider": provider_info["provider"],
            "provider_name": provider_info["provider_name"]
        }


# ===== MULTI-PROVIDER AI API ENDPOINTS =====

@app.get("/api/ai/providers")
async def get_ai_providers():
    """Get list of all available AI providers with their status"""
    try:
        from .providers import provider_registry
        providers = await provider_registry.get_available_providers()
        return providers
    except Exception as exc:
        raise HTTPException(500, f"Failed to fetch providers: {exc}")


@app.get("/api/ai/providers/{provider_id}/status")
async def get_provider_status(provider_id: str):
    """Get status and information for a specific provider"""
    try:
        from .providers import provider_registry, ProviderError
        provider = provider_registry.get_provider(provider_id)
        if not provider:
            raise HTTPException(404, f"Provider '{provider_id}' not found")
        
        available = await provider.check_availability()
        result = {
            "id": provider.get_provider_id(),
            "name": provider.get_display_name(),
            "available": available,
            "agent_type": provider.get_agent_type().value,
            "runner_type": provider.get_runner_type().value,
        }
        
        if available:
            try:
                models = await provider.get_available_models()
                result["models"] = [model.model_dump() for model in models]
                result["model_count"] = len(models)
            except Exception as exc:
                result["models"] = []
                result["model_count"] = 0
                result["model_error"] = str(exc)
        
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to get provider status: {exc}")


@app.get("/api/ai/providers/{provider_id}/models")
async def get_provider_models(provider_id: str):
    """Get available models for a specific provider"""
    try:
        from .providers import provider_registry, ProviderError
        models = await provider_registry.get_provider_models(provider_id)
        return [model.model_dump() for model in models]
    except ProviderError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        raise HTTPException(500, f"Failed to fetch models: {exc}")


@app.post("/api/ai/providers/{provider_id}/refresh")
async def refresh_provider_models(provider_id: str):
    """Refresh the model list for a provider"""
    try:
        from .providers import provider_registry, ProviderError
        # This will force a re-fetch of models
        models = await provider_registry.get_provider_models(provider_id)
        return {
            "provider": provider_id,
            "model_count": len(models),
            "refreshed": True
        }
    except ProviderError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        raise HTTPException(500, f"Failed to refresh models: {exc}")


@app.get("/api/sdlc/projects/{project_id}/ai-settings")
async def get_project_ai_settings(project_id: str):
    """Get AI provider and model settings for a project"""
    project = sdlc_project_manager.get_project(project_id)
    if not project:
        raise HTTPException(404, f"Project {project_id} not found")
    return project.ai_settings.model_dump()


@app.put("/api/sdlc/projects/{project_id}/ai-settings")
async def update_project_ai_settings(project_id: str, settings: dict):
    """Update AI provider and model settings for a project"""
    project = sdlc_project_manager.get_project(project_id)
    if not project:
        raise HTTPException(404, f"Project {project_id} not found")
    
    try:
        # Update AI settings
        if "default_provider" in settings:
            project.ai_settings.default_provider = settings["default_provider"]
        if "default_model" in settings:
            project.ai_settings.default_model = settings["default_model"]
        if "stage_providers" in settings:
            # Convert dict to StageProviderConfig objects
            stage_providers = {}
            for stage, config_dict in settings["stage_providers"].items():
                stage_providers[stage] = StageProviderConfig(**config_dict)
            project.ai_settings.stage_providers = stage_providers
        if "ollama_endpoint" in settings:
            project.ai_settings.ollama_endpoint = settings["ollama_endpoint"]
        if "codex_endpoint" in settings:
            project.ai_settings.codex_endpoint = settings["codex_endpoint"]
        if "claude_endpoint" in settings:
            project.ai_settings.claude_endpoint = settings["claude_endpoint"]
        
        # Save the project
        sdlc_project_manager.save_project(project)
        return project.ai_settings.model_dump()
    except Exception as exc:
        raise HTTPException(400, f"Invalid AI settings: {exc}")


@app.get("/api/sdlc/projects/{project_id}/stage-config/{stage}")
async def get_stage_provider_config(project_id: str, stage: str):
    """Get the resolved provider and model configuration for a specific stage"""
    project = sdlc_project_manager.get_project(project_id)
    if not project:
        raise HTTPException(404, f"Project {project_id} not found")
    
    agent_config = project.agents.get(stage)
    provider_info = await ProviderResolutionService().get_provider_info_for_stage(stage, project, agent_config)
    
    return {
        **provider_info,
        "effective_config": project.ai_settings.get_effective_config_for_stage(stage),
        "agent_has_override": bool(agent_config and (agent_config.provider_override or agent_config.model_override)),
    }


# ===== END SDLC API ENDPOINTS =====

# ===== RELEASE MANAGEMENT API =====

async def collect_integrated_tasks() -> list[IntegratedTask]:
    """Every DWS and SDLC task whose branch was merged into develop, one entry per (task, repository)."""
    found: list[IntegratedTask] = []
    for task in await sdlc_task_manager.list_tasks():
        for key, repo in task.repos.items():
            integration = repo.integration
            if integration.merged_into_develop and integration.history:
                found.append(IntegratedTask(
                    task_id=task.base_task.task_id, workflow="SDLC", title=task.title, status=task.sdlc_status.value,
                    project_id=task.project_config_id, repository_id=repository_id_for(key), repository_path=key,
                    repository_name=Path(key).name, branch=repo.branch,
                    merges=[MergeEntry.model_validate(entry) for entry in integration.history]))
    for state in tasks.values():
        integration = state.git_integration
        if integration.merged_into_develop and integration.history and integration.repo_root:
            found.append(IntegratedTask(
                task_id=state.task_id, workflow="DWS", title=state.session_name or state.task_id, status=state.status.value,
                repository_id=repository_id_for(integration.repo_root), repository_path=integration.repo_root,
                repository_name=Path(integration.repo_root).name, branch=state.branch,
                merges=[MergeEntry.model_validate(entry) for entry in integration.history]))
    return found


async def validation_plan_for(repository_path: str, task_ids: list[str]) -> list[dict]:
    """The project's own setup/test commands for this repository, as paths relative to the repository root."""
    root = Path(repository_path)
    plan: list[dict] = []

    def add(kind: str, command_text: str, folder: Path) -> None:
        try:
            relative = folder.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            relative = ""
        step = {"kind": kind, "command": command_text.strip(), "working_directory": "" if relative == "." else relative}
        if step["command"] and step not in plan:
            plan.append(step)

    for task_id in task_ids:
        sdlc = await sdlc_task_manager.load_task(task_id)
        if sdlc:
            project = sdlc_project_manager.get_project(sdlc.project_config_id)
            for stage, config in (project.agents.items() if project else []):
                folder_text = project.stage_path(stage)
                if not config.enabled or not folder_text:
                    continue
                folder = Path(folder_text).expanduser()
                stage_root = await git_root(folder)
                if stage_root is None or str(stage_root) != repository_path:
                    continue
                add("setup", config.setup_command or "", folder)
                configured = (config.test_instructions or {}).get("working_directory") or ""
                add("test", (config.test_instructions or {}).get("command") or "", folder / configured)
            continue
        for state in tasks.values():
            if state.task_id == task_id and state.test_command:
                add("test", state.test_command, root / (state.test_working_directory or ""))
    return plan


def release_token(repository_path: str) -> str | None:
    """GitHub token for fetch/push of a repository: the one saved on the stage that manages it, else GITHUB_TOKEN."""
    for project in sdlc_project_manager.list_projects():
        for stage, config in project.agents.items():
            folder = project.stage_path(stage)
            if config.repository.mode.value != "none" and folder and str(Path(folder).expanduser().resolve()) == str(Path(repository_path).resolve()):
                return sdlc_project_manager.github_token(project.id, stage) or None
    return None


release_manager = ReleaseManager(ReleaseStore(Path("data/releases")), collect_integrated_tasks, validation_plan_for, release_token)


class ReleaseCreateRequest(BaseModel):
    version: str
    repository_id: str
    task_ids: list[str]
    start: bool = True


def _release_or_404(release_id: str):
    release = release_manager.store.get(release_id)
    if release is None:
        raise HTTPException(404, f"Release {release_id} not found")
    return release


def _release_action(action):
    try:
        return action()
    except ReleaseInputError as exc:
        raise HTTPException(422, str(exc)) from exc
    except ReleaseError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get("/api/releases/repositories")
async def list_release_repositories():
    """Repositories that have at least one task merged into develop."""
    return await release_manager.repositories()


@app.get("/api/releases/eligible-tasks")
async def list_release_tasks(repository_id: str = "", q: str = "", workflow: str = "", status: str = "", eligible_only: bool = False):
    """Tasks merged into develop, with their unreleased changes; searchable by id/title, workflow and task status."""
    rows = await release_manager.eligible_tasks()
    needle = q.strip().lower()
    return [row for row in rows
            if (not repository_id or row["repository_id"] == repository_id)
            and (not workflow or row["workflow"].lower() == workflow.lower())
            and (not status or row["status"] == status)
            and (not eligible_only or row["eligible"])
            and (not needle or needle in row["task_id"].lower() or needle in row["title"].lower() or needle in row["branch"].lower())]


@app.get("/api/releases/by-task/{task_id}")
async def releases_of_task(task_id: str):
    """Release versions a task participates in (any status except cancelled)."""
    return release_manager.releases_for_task(task_id)


@app.get("/api/releases")
async def list_releases(status: str = "", repository_id: str = "", q: str = ""):
    needle = q.strip().lower()
    return [release for release in release_manager.store.list()
            if (not status or release.status.value == status)
            and (not repository_id or release.repository_id == repository_id)
            and (not needle or needle in release.version.lower() or any(needle in task.task_id.lower() for task in release.tasks))]


@app.post("/api/releases", status_code=202)
async def create_release(body: ReleaseCreateRequest, user: str = Depends(require_admin)):
    """Create a release from selected tasks and start building/validating its branch in the background."""
    try:
        return await release_manager.create(body.version, body.repository_id, body.task_ids, user, body.start)
    except ReleaseInputError as exc:
        raise HTTPException(422, str(exc)) from exc
    except ReleaseError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get("/api/releases/{release_id}")
async def get_release(release_id: str):
    return _release_or_404(release_id)


@app.post("/api/releases/{release_id}/start", status_code=202)
async def start_release(release_id: str, _: str = Depends(require_admin)):
    _release_or_404(release_id)
    try:
        return await release_manager.start(release_id)
    except ReleaseError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/api/releases/{release_id}/approve", status_code=202)
async def approve_release(release_id: str, user: str = Depends(require_admin)):
    """The human release approval: only now is the release branch merged into sandbox (in the background)."""
    _release_or_404(release_id)
    return _release_action(lambda: release_manager.approve(release_id, user))


@app.post("/api/releases/{release_id}/retry", status_code=202)
async def retry_release(release_id: str, _: str = Depends(require_admin)):
    _release_or_404(release_id)
    return _release_action(lambda: release_manager.retry(release_id))


@app.post("/api/releases/{release_id}/rebuild", status_code=202)
async def rebuild_release(release_id: str, _: str = Depends(require_admin)):
    _release_or_404(release_id)
    return _release_action(lambda: release_manager.rebuild(release_id))


@app.post("/api/releases/{release_id}/cancel")
async def cancel_release(release_id: str, _: str = Depends(require_admin)):
    _release_or_404(release_id)
    return _release_action(lambda: release_manager.cancel(release_id))


# ===== END RELEASE MANAGEMENT API =====


# The Windows registry often maps .js to text/plain, which browsers refuse to run as a module script.
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/css", ".css")

dist = Path(__file__).parents[2] / "frontend" / "dist"
if dist.exists():
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        return FileResponse(dist / "index.html")
