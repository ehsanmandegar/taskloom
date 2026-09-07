import asyncio
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .models import CommitRequest, RunStatus, TaskRequest, TaskState
from .services import execute_task, git_commit, git_push, repository

app = FastAPI(title="Taskloom", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])
tasks: dict[str, TaskState] = {}


@app.get("/api/health")
async def health():
    return {"status": "ok"}


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


dist = Path(__file__).parents[2] / "frontend" / "dist"
if dist.exists():
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        return FileResponse(dist / "index.html")
