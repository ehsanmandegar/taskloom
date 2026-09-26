import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .models import BranchSwitchRequest, ChatMessage, ChatRequest, CommitRequest, GitProvider, McpFailureMode, ProjectDefaults, ProjectProfile, RenameTaskRequest, RunStatus, TaskRequest, TaskState, TestSetupRequest, TodoItem, TodoRequest, valid_branch_name
from .services import codex_account_status, continue_task, create_merge_request, execute_task, generate_commit_message, git_branches, git_commit, git_push, repository, run_test_setup, switch_git_branch

app = FastAPI(title="Taskloom", version="0.1.0")
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
            state.error = "Taskloom was restarted before Codex finished responding."
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
    )


def profiles_path() -> Path:
    configured = os.getenv("TASKLOOM_PROFILES_PATH")
    return Path(configured).expanduser() if configured else Path.home() / ".taskloom" / "profiles.json"


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
        raise HTTPException(409, "Stop the active Codex task for this project before switching branches")
    try:
        return await switch_git_branch(repo, request.branch)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


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
    run_id = uuid.uuid4().hex[:12]
    state = TaskState(
        id=run_id,
        task_id=request.task_id,
        session_name=request.session_name or request.task_id,
        project_path=str(repo),
        branch=f"tasks/{request.task_id}",
        base_branch=request.base_branch,
        guide_paths=request.guide_paths,
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
        raise HTTPException(409, "Wait for the current Codex response before sending another message")
    if not state.codex_thread_id:
        raise HTTPException(409, "This task does not have a resumable Codex session")
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
    pending = pending_todos()
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


async def dispatch_next_todo() -> None:
    """Run only one queued Todo at a time, preserving the user-defined order."""
    active = {RunStatus.queued, RunStatus.running, RunStatus.testing}
    if any(state.status in active for state in tasks.values()):
        return
    for owner, todo in pending_todos():
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

    state.step = "Stopping Codex"
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


dist = Path(__file__).parents[2] / "frontend" / "dist"
if dist.exists():
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        return FileResponse(dist / "index.html")
