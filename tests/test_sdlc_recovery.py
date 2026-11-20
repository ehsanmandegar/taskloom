"""Recovery of SDLC tasks whose stage was running when the server stopped."""

import asyncio
import json
import subprocess
import sys
import time

import pytest
from fastapi.testclient import TestClient

from backend.app import main as main_module
from backend.app import process_tools, services
from backend.app.models import ProjectWorkflowConfig, RunStatus, SDLCProjectConfig, SDLCStatus, SDLCTask, TaskState
from backend.app.sdlc_runner import record_agent_process


def make_task(task_id: str, status: SDLCStatus, stage: str = "backend") -> SDLCTask:
    base = TaskState(id=task_id, task_id=task_id, project_path=".", branch=f"tasks/{task_id}", status=RunStatus.queued, step="sdlc")
    return SDLCTask(base_task=base, title="Shop", current_stage=stage, current_agent=stage, project_config_id="p", sdlc_status=status)


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def manager(tmp_path, monkeypatch):
    manager = services.SDLCTaskManager(data_dir=tmp_path / "tasks")
    services.SDLCProjectManager(tmp_path / "projects").save_project(SDLCProjectConfig(id="p", name="Shop"))
    launched = []

    async def fake_execute(task_id, stage, project=None):
        launched.append((task_id, stage))

    monkeypatch.setattr(manager, "execute_stage", fake_execute)
    manager.launched = launched
    return manager


def test_interrupted_running_tasks_go_to_the_inbox_once(manager):
    run(manager.save_task(make_task("running", SDLCStatus.backend_running)))
    for task_id, status in [("done", SDLCStatus.done), ("failed", SDLCStatus.failed), ("waiting", SDLCStatus.human_review)]:
        run(manager.save_task(make_task(task_id, status)))

    assert run(manager.recover_interrupted_tasks()) == ["running"]
    assert run(manager.recover_interrupted_tasks()) == []

    [item] = manager.list_pending_interventions()
    assert item.task_id == "running" and item.context["kind"] == "interrupted"
    assert item.response_options == ["resume", "stop"]
    assert run(manager.load_task("running")).sdlc_status == SDLCStatus.human_review
    assert run(manager.load_task("done")).sdlc_status == SDLCStatus.done
    assert manager.launched == []


def test_resume_answer_reruns_the_interrupted_stage(manager):
    run(manager.save_task(make_task("t", SDLCStatus.frontend_running, stage="frontend")))
    run(manager.recover_interrupted_tasks())
    [item] = manager.list_pending_interventions()

    run(manager.submit_human_response(item.id, "resume"))

    assert manager.launched == [("t", "frontend")]


def test_auto_resume_reruns_without_asking(manager):
    project = SDLCProjectConfig(id="p", name="Shop", workflow=ProjectWorkflowConfig(auto_resume_interrupted=True))
    services.SDLCProjectManager(manager.data_dir.parent / "projects").save_project(project)
    run(manager.save_task(make_task("t", SDLCStatus.testing, stage="qa")))

    run(manager.recover_interrupted_tasks())

    assert manager.launched == [("t", "qa")]
    assert manager.list_pending_interventions() == []
    assert "Resumed qa" in run(manager.load_task("t")).transition_reason


def test_orphaned_agent_is_checked_and_reported(manager, monkeypatch):
    run(manager.save_task(make_task("t", SDLCStatus.backend_running)))
    pid_file = manager.agent_pid_file("t")
    pid_file.write_text(json.dumps({"pid": 4242, "image": "claude.exe", "stage": "backend"}), encoding="utf-8")
    checked = []
    monkeypatch.setattr(process_tools, "stop_if_same_program", lambda pid, image: checked.append((pid, image)) or "stopped")

    run(manager.recover_interrupted_tasks())

    assert checked == [(4242, "claude.exe")]
    assert not pid_file.exists()
    assert "(PID 4242): stopped" in manager.list_pending_interventions()[0].description


def test_command_reports_the_started_pid(tmp_path):
    seen = []
    token = services._command_started_handler.set(seen.append)
    try:
        code, output = run(services.command([sys.executable, "-c", "import os; print(os.getpid())"], tmp_path))
    finally:
        services._command_started_handler.reset(token)

    assert code == 0
    assert seen == [int(output.strip())]


def test_pid_record_contains_the_real_image_name(tmp_path):
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        record_agent_process(tmp_path / "agent.pid", "backend")(child.pid)
        info = json.loads((tmp_path / "agent.pid").read_text(encoding="utf-8"))
        assert info["pid"] == child.pid and info["stage"] == "backend"
        assert info["image"].casefold().startswith("python")
    finally:
        child.kill()


def test_stop_if_same_program_only_kills_the_recorded_program():
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        image = process_tools.process_image(child.pid)
        assert image

        assert "left untouched" in process_tools.stop_if_same_program(child.pid, "claude.exe")
        assert child.poll() is None

        assert process_tools.stop_if_same_program(child.pid, image) == "stopped"
        for _ in range(50):
            if child.poll() is not None:
                break
            time.sleep(0.1)
        assert child.poll() is not None
        assert process_tools.stop_if_same_program(child.pid, image) == "not running"
    finally:
        if child.poll() is None:
            child.kill()


def test_server_startup_runs_recovery(manager, monkeypatch):
    run(manager.save_task(make_task("t", SDLCStatus.analyzing, stage="analysis")))
    monkeypatch.setattr(main_module, "sdlc_task_manager", manager)

    with TestClient(main_module.app):
        pass

    assert manager.list_pending_interventions()[0].task_id == "t"
