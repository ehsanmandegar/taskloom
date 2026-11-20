import asyncio

from fastapi.testclient import TestClient

from backend.app import main as main_module
from backend.app.models import (
    AgentConfig, ProjectWorkflowConfig, RunStatus, SDLCProjectConfig, SDLCStatus, SDLCTask, TaskState,
)
from backend.app.services import SDLCTaskManager

client = TestClient(main_module.app)


def make_task(task_id: str, stage: str) -> SDLCTask:
    base = TaskState(id=task_id, task_id=task_id, project_path=".", base_branch="main", branch=f"tasks/{task_id}", status=RunStatus.queued, step="sdlc")
    return SDLCTask(base_task=base, title="t", current_stage=stage, current_agent=stage, project_config_id="p")


def test_last_stage_moves_task_to_pending_approval(tmp_path):
    manager = SDLCTaskManager(data_dir=tmp_path)
    project = SDLCProjectConfig(
        id="p", name="p",
        workflow=ProjectWorkflowConfig(stages=["analysis", "qa"]),
        agents={"qa": AgentConfig()},
    )
    task = make_task("sdlc-last", "qa")

    asyncio.run(manager._advance_or_complete(task, project))

    saved = asyncio.run(manager.load_task("sdlc-last"))
    assert saved.sdlc_status == SDLCStatus.pending_approval


def test_approve_endpoint_marks_task_done_only_from_pending_approval(tmp_path, monkeypatch):
    manager = SDLCTaskManager(data_dir=tmp_path)
    monkeypatch.setattr(main_module, "sdlc_task_manager", manager)
    task = make_task("sdlc-approve", "qa")
    task.sdlc_status = SDLCStatus.testing
    asyncio.run(manager.save_task(task))

    assert client.post("/api/sdlc/tasks/sdlc-approve/approve").status_code == 409

    task.sdlc_status = SDLCStatus.pending_approval
    asyncio.run(manager.save_task(task))
    response = client.post("/api/sdlc/tasks/sdlc-approve/approve")

    assert response.status_code == 200
    assert response.json()["sdlc_status"] == "done"
    assert asyncio.run(manager.load_task("sdlc-approve")).sdlc_status == SDLCStatus.done
    assert client.post("/api/sdlc/tasks/missing/approve").status_code == 404


def test_saved_project_with_default_github_config_loads_again(tmp_path):
    from backend.app.services import SDLCProjectManager

    manager = SDLCProjectManager(data_dir=tmp_path)
    manager.save_project(SDLCProjectConfig(id="p", name="p", agents={"backend": AgentConfig()}))

    reloaded = SDLCProjectManager(data_dir=tmp_path)
    assert reloaded.get_project("p").agents["backend"].github_config["auto_commit"] is False
