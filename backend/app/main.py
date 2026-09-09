import asyncio
import json
import os
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .models import CommitRequest, ProjectProfile, RunStatus, TaskRequest, TaskState
from .services import create_merge_request, execute_task, git_commit, git_push, repository

app = FastAPI(title="Taskloom", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])
tasks: dict[str, TaskState] = {}


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
    state = TaskState(id=run_id, task_id=request.task_id, project_path=str(repo), branch=f"task/{request.task_id}", status=RunStatus.queued, step="Queued")
    tasks[run_id] = state
    asyncio.create_task(execute_task(request, state))
    return state


def get_state(run_id: str) -> TaskState:
    if run_id not in tasks:
        raise HTTPException(404, "Task run not found")
    return tasks[run_id]


@app.get("/api/tasks/{run_id}", response_model=TaskState)
async def task_status(run_id: str):
    return get_state(run_id)


@app.post("/api/tasks/{run_id}/commit")
async def commit(run_id: str, request: CommitRequest):
    state = get_state(run_id)
    try:
        return {"ok": True, "output": await git_commit(state, request.message.strip()), "task": state}
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/api/tasks/{run_id}/push")
async def push(run_id: str):
    state = get_state(run_id)
    try:
        return {"ok": True, "output": await git_push(state), "task": state}
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/api/tasks/{run_id}/merge-request")
async def merge_request(run_id: str):
    state = get_state(run_id)
    try:
        output = await create_merge_request(state)
        return {"ok": True, "output": output, "url": state.merge_request_url, "task": state}
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(409, str(exc)) from exc


dist = Path(__file__).parents[2] / "frontend" / "dist"
if dist.exists():
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        return FileResponse(dist / "index.html")
