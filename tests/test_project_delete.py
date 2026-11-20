"""Deleting a project deletes its tasks (and their inbox items); running tasks block the delete."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from backend.app import main as main_module
from backend.app.models import RunStatus, SDLCProjectConfig, SDLCTask, TaskState
from backend.app.services import SDLCProjectManager, SDLCTaskManager


def make_task(task_id: str, project_id: str) -> SDLCTask:
    base = TaskState(id=task_id, task_id=task_id, project_path=".", branch=f"tasks/{task_id}", status=RunStatus.queued, step="sdlc")
    return SDLCTask(base_task=base, title=task_id, current_stage="backend", project_config_id=project_id)


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def api(tmp_path, monkeypatch):
    projects = SDLCProjectManager(tmp_path / "data" / "projects")
    tasks = SDLCTaskManager(data_dir=tmp_path / "data" / "tasks")
    monkeypatch.setattr(main_module, "sdlc_project_manager", projects)
    monkeypatch.setattr(main_module, "sdlc_task_manager", tasks)
    for project_id in ("shop", "blog"):
        projects.save_project(SDLCProjectConfig(id=project_id, name=project_id))
    for task_id, project_id in [("s1", "shop"), ("s2", "shop"), ("b1", "blog")]:
        run(tasks.save_task(make_task(task_id, project_id)))
    run(tasks._ask_human(run(tasks.load_task("s1")), "backend", "agent_question", "q", "Which DB?", ["stop"]))
    run(tasks._ask_human(run(tasks.load_task("b1")), "backend", "agent_question", "q", "Which CMS?", ["stop"]))
    return TestClient(main_module.app), projects, tasks


def test_deleting_a_project_deletes_only_its_tasks_and_inbox_items(api):
    client, projects, tasks = api

    assert client.get("/api/sdlc/projects/shop/tasks/count").json() == {"count": 2}
    response = client.delete("/api/sdlc/projects/shop")

    assert response.status_code == 200, response.text
    assert sorted(response.json()["deleted_tasks"]) == ["s1", "s2"]
    assert projects.get_project("shop") is None
    remaining = [task.base_task.task_id for task in run(tasks.list_tasks())]
    assert remaining == ["b1"]
    assert [item.task_id for item in tasks.list_pending_interventions()] == ["b1"]
    assert not (tasks.data_dir / "s1").exists()


def test_a_running_task_blocks_the_project_delete(api, monkeypatch):
    client, projects, tasks = api
    monkeypatch.setattr(tasks, "is_running", lambda task_id: task_id == "s2")

    response = client.delete("/api/sdlc/projects/shop")

    assert response.status_code == 409
    assert "s2" in response.json()["detail"]
    assert projects.get_project("shop") is not None
    assert len(run(tasks.list_tasks(project_filter="shop"))) == 2  # nothing was deleted


def test_single_task_delete(api):
    client, _, tasks = api

    assert client.delete("/api/sdlc/tasks/b1").json() == {"task_id": "b1", "deleted": True}
    assert client.delete("/api/sdlc/tasks/b1").status_code == 404
    assert tasks.list_pending_interventions()[0].task_id == "s1"


def test_unknown_project_is_404(api):
    client, _, _ = api
    assert client.delete("/api/sdlc/projects/nope").status_code == 404
