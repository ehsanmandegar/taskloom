"""Concurrency safety of SDLC task storage: versions, locks, retries and single-server ownership."""

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import file_lock, main as main_module, sdlc_runner, services
from backend.app.file_lock import FileLock, LockTimeout, replace_with_retry
from backend.app.models import (
    AgentConfig, AgentResult, ProjectWorkflowConfig, RunStatus, SDLCProjectConfig, SDLCStatus, SDLCTask,
    TaskRepo, TaskState,
)
from backend.app.services import SDLCTaskManager, TaskConflictError

ROOT = Path(__file__).resolve().parents[1]


def make_task(task_id: str = "t", status: SDLCStatus = SDLCStatus.backend_running) -> SDLCTask:
    base = TaskState(id=task_id, task_id=task_id, project_path=".", branch=f"tasks/{task_id}", status=RunStatus.queued, step="sdlc")
    return SDLCTask(base_task=base, title="Shop", current_stage="backend", project_config_id="p", sdlc_status=status)


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def manager(tmp_path):
    return SDLCTaskManager(data_dir=tmp_path / "tasks")


def test_saving_a_stale_copy_raises_instead_of_overwriting(manager):
    run(manager.save_task(make_task()))
    first = run(manager.load_task("t"))
    stale = run(manager.load_task("t"))

    first.title = "first writer"
    run(manager.save_task(first))
    stale.title = "stale writer"
    with pytest.raises(TaskConflictError):
        run(manager.save_task(stale))

    saved = run(manager.load_task("t"))
    assert saved.title == "first writer"
    assert saved.version == 2
    assert stale.version == 1  # unchanged after the failed save
    assert not list((manager.data_dir / "t").glob("*.tmp"))


def test_task_files_written_before_versioning_still_load_and_save(manager):
    task_dir = manager.data_dir / "old"
    task_dir.mkdir(parents=True)
    data = json.loads(make_task("old").model_dump_json())
    data.pop("version")
    (task_dir / "task.json").write_text(json.dumps(data), encoding="utf-8")

    task = run(manager.load_task("old"))
    assert task.version == 0
    run(manager.save_task(task))
    assert run(manager.load_task("old")).version == 1


def test_update_task_reapplies_the_change_on_top_of_a_concurrent_write(manager):
    run(manager.save_task(make_task()))
    calls = []

    def mutate(task):
        calls.append(task.version)
        if len(calls) == 1:  # another writer saves between our read and our write
            other = run_in_new_loop(manager.load_task("t"))
            other.transition_reason = "other writer"
            run_in_new_loop(manager.save_task(other))
        task.title = "mine"

    result = run(manager.update_task("t", mutate))

    assert calls == [1, 2]
    saved = run(manager.load_task("t"))
    assert (saved.title, saved.transition_reason) == ("mine", "other writer")
    assert result.version == saved.version


def run_in_new_loop(coro):
    """Run a coroutine from inside a sync callback that is itself called from a running loop."""
    import threading
    box = {}
    thread = threading.Thread(target=lambda: box.setdefault("value", asyncio.run(coro)))
    thread.start()
    thread.join()
    return box.get("value")


def test_github_action_does_not_clobber_a_stage_result_saved_meanwhile(tmp_path, monkeypatch):
    tasks = SDLCTaskManager(data_dir=tmp_path / "data" / "tasks")
    projects = services.SDLCProjectManager(tmp_path / "data" / "projects")
    repo_dir = tmp_path / "shop"
    repo_dir.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo_dir, check=True)
    projects.save_project(SDLCProjectConfig(id="p", name="Shop", agents={"backend": AgentConfig(project_path=str(repo_dir))}))
    monkeypatch.setattr(main_module, "sdlc_task_manager", tasks)
    monkeypatch.setattr(main_module, "sdlc_project_manager", projects)
    task = make_task()
    key = str(repo_dir.resolve())
    task.repos[key] = TaskRepo(path=key, branch="sdlc/t", base_branch="main")
    run(tasks.save_task(task))

    async def slow_commit_push(task, repo, repo_url, token):
        # While git runs, the agent worker stores the QA result.
        latest = await tasks.load_task("t")
        latest.agent_results["qa"] = AgentResult(agent="qa", status="completed", summary="QA ok")
        await tasks.save_task(latest)
        repo.commit_sha, repo.pushed = "abc123", True
        return {"message": "Committed and pushed", "commit_sha": "abc123", "branch": repo.branch}

    monkeypatch.setattr(main_module, "commit_and_push", slow_commit_push)

    response = TestClient(main_module.app).post("/api/sdlc/tasks/t/github/commit-push", json={"agent": "backend", "repo_url": "x"})

    assert response.status_code == 200, response.text
    saved = run(tasks.load_task("t"))
    assert saved.agent_results["qa"].summary == "QA ok"
    assert saved.repos[key].pushed is True and saved.repos[key].commit_sha == "abc123"


def test_stage_result_is_reapplied_after_a_save_conflict(tmp_path, monkeypatch):
    manager = SDLCTaskManager(data_dir=tmp_path / "tasks")
    project = SDLCProjectConfig(
        id="p", name="Shop", workflow=ProjectWorkflowConfig(stages=["backend"], require_final_human_approval=True),
        agents={"backend": AgentConfig(project_path=str(tmp_path), runner="claude")},
    )
    run(manager.save_task(make_task()))

    async def fake_stage(stage, task, project, config, runner, pid_file=None, repo_token=None, persist_project=None):
        return AgentResult(agent=stage, status="completed", summary="done")

    monkeypatch.setattr(sdlc_runner, "run_cli_stage", fake_stage)
    real_save = manager.save_task
    conflicts = []

    async def flaky_save(task):
        if not conflicts:
            conflicts.append(1)
            raise TaskConflictError("simulated concurrent writer")
        await real_save(task)

    monkeypatch.setattr(manager, "save_task", flaky_save)

    run(manager._run_agent_async("t", "backend", project))

    saved = run(manager.load_task("t"))
    assert conflicts == [1]
    assert saved.sdlc_status == SDLCStatus.pending_approval
    assert saved.agent_results["backend"].summary == "done"


def test_an_inbox_item_can_only_be_answered_once(manager, monkeypatch):
    services.SDLCProjectManager(manager.data_dir.parent / "projects").save_project(SDLCProjectConfig(id="p", name="Shop"))
    launched = []

    async def fake_execute(task_id, stage, project=None):
        launched.append(stage)

    monkeypatch.setattr(manager, "execute_stage", fake_execute)
    task = make_task()
    run(manager.save_task(task))
    item_id = run(manager._ask_human(task, "backend", "agent_question", "q", "Which DB?", ["stop"]))

    async def answer_twice():
        return await asyncio.gather(
            manager.submit_human_response(item_id, "Postgres"),
            manager.submit_human_response(item_id, "MySQL"),
        )

    assert sorted(run(answer_twice())) == [False, True]
    assert launched == ["backend"]
    assert manager.list_pending_interventions() == []


def test_file_lock_excludes_another_process(tmp_path):
    lock_path = tmp_path / "x.lock"
    script = (
        "import sys, time; sys.path.insert(0, sys.argv[1]);"
        "from backend.app.file_lock import FileLock;"
        "lock = FileLock(sys.argv[2]); lock.acquire(); print('locked', flush=True); time.sleep(30)"
    )
    holder = subprocess.Popen([sys.executable, "-c", script, str(ROOT), str(lock_path)], stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout.readline().strip() == "locked"
        with pytest.raises(LockTimeout):
            FileLock(lock_path, timeout=0.3).acquire()
    finally:
        holder.kill()
        holder.wait()
    with FileLock(lock_path, timeout=5):  # released by the OS when the holder died
        pass


def test_only_one_server_owns_a_data_directory(tmp_path):
    first = SDLCTaskManager(data_dir=tmp_path / "tasks")
    second = SDLCTaskManager(data_dir=tmp_path / "tasks")

    assert first.claim_data_dir() is True
    assert second.claim_data_dir() is False
    assert second.read_only
    with pytest.raises(ValueError, match="Another Taskloom server"):
        run(second.execute_stage("t", "backend"))

    first.release_data_dir()
    assert second.claim_data_dir() is True


def test_replace_retries_transient_windows_permission_errors(tmp_path, monkeypatch):
    source, target = tmp_path / "a.tmp", tmp_path / "a.json"
    source.write_text("new", encoding="utf-8")
    target.write_text("old", encoding="utf-8")
    real_replace, failures = os.replace, []

    def flaky_replace(src, dst):
        if len(failures) < 2:
            failures.append(1)
            raise PermissionError("file is open")
        real_replace(src, dst)

    monkeypatch.setattr(file_lock.os, "replace", flaky_replace)
    replace_with_retry(source, target, delay=0)

    assert target.read_text(encoding="utf-8") == "new" and len(failures) == 2
