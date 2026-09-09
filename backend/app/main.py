import asyncio
import json
import os
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .models import ChatMessage, ChatRequest, CommitRequest, ProjectProfile, RunStatus, TaskRequest, TaskState
from .services import continue_task, create_merge_request, execute_task, git_commit, git_push, repository

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
        save_tasks(loaded)
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
    state = TaskState(id=run_id, task_id=request.task_id, project_path=str(repo), branch=f"task/{request.task_id}", test_command=request.test_command, status=RunStatus.queued, step="Queued", messages=[ChatMessage(role="user", content=request.request)])
    tasks[run_id] = state
    save_tasks(tasks)
    asyncio.create_task(run_task(request, state))
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
    asyncio.create_task(run_follow_up(message, state))
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
