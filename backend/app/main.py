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

from .models import ChatMessage, ChatRequest, CommitRequest, GitProvider, McpFailureMode, ProjectDefaults, ProjectProfile, RunStatus, TaskRequest, TaskState
from .services import continue_task, create_merge_request, execute_task, generate_commit_message, git_commit, git_push, repository

app = FastAPI(title="Taskloom", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])


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

    restarted = False
    for state in loaded.values():
        if state.status in {RunStatus.queued, RunStatus.running, RunStatus.testing}:
            state.status = RunStatus.failed
            state.step = "Interrupted by Taskloom restart"
            state.error = "Taskloom was restarted before Codex finished responding."
            restarted = True
    if restarted:
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
    if configured_test is not None:
        test_command = configured_test.strip() or None
    elif os.name == "nt" and (project_path / ".venv" / "Scripts" / "python.exe").is_file():
        test_command = r".venv\Scripts\python.exe -m pytest -q"
    elif (project_path / ".venv" / "bin" / "python").is_file():
        test_command = ".venv/bin/python -m pytest -q"
    elif os.name == "nt" and (project_path / "backend" / "venv" / "Scripts" / "python.exe").is_file():
        test_command = r"backend\venv\Scripts\python.exe -m pytest -q"
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

    return ProjectDefaults(
        project_path=str(project_path),
        guide_paths=guide_paths,
        test_command=test_command,
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
        return {name: ProjectProfile.model_validate(profile) for name, profile in data.items()}
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(500, f"Could not read project profiles: {exc}") from exc


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


@app.get("/api/defaults", response_model=ProjectDefaults)
async def defaults():
    return project_defaults()


@app.get("/api/tasks", response_model=list[TaskState])
async def list_tasks():
    return list(reversed(list(tasks.values())))


@app.get("/api/profiles", response_model=list[ProjectProfile])
async def list_profiles():
    return sorted(load_profiles().values(), key=lambda profile: profile.name.casefold())


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
        project_path=str(repo),
        branch=f"tasks/{request.task_id}",
        test_command=request.test_command,
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


def get_state(run_id: str) -> TaskState:
    if run_id not in tasks:
        raise HTTPException(404, "Task run not found")
    return tasks[run_id]


async def run_task(request: TaskRequest, state: TaskState) -> None:
    await execute_task(request, state)
    save_tasks(tasks)


async def run_follow_up(message: str, state: TaskState) -> None:
    await continue_task(message, state)
    save_tasks(tasks)


@app.get("/api/tasks/{run_id}", response_model=TaskState)
async def task_status(run_id: str):
    return get_state(run_id)


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
    if state.status in {RunStatus.queued, RunStatus.running, RunStatus.testing}:
        raise HTTPException(409, "Wait for the current Codex response before sending another message")
    if not state.codex_thread_id:
        raise HTTPException(409, "This task does not have a resumable Codex session")
    message = request.message.strip()
    state.messages.append(ChatMessage(role="user", content=message))
    state.status, state.step, state.error = RunStatus.queued, "Queued follow-up", None
    save_tasks(tasks)
    track_worker(run_id, asyncio.create_task(run_follow_up(message, state)))
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
