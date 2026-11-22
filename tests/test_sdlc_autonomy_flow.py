"""Automatic approval, merge and release drafting end to end (real Git repositories, real approval code)."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from backend.app import main as main_module
from backend.app import sdlc_git
from backend.app.models import (
    AgentConfig, AgentResult, Change, ProjectWorkflowConfig, RunStatus, SDLCProjectConfig, SDLCStatus, SDLCTask,
    TaskState, TestResults,
)
from backend.app.releases import ReleaseManager, ReleaseStatus, ReleaseStore
from backend.app.services import SDLCProjectManager, SDLCTaskManager

from gitflow_helpers import git, init_repo, run

client = TestClient(main_module.app)


@pytest.fixture
def world(tmp_path, monkeypatch):
    repo = init_repo(tmp_path / "shop")
    tasks = SDLCTaskManager(data_dir=tmp_path / "data" / "tasks")
    projects = SDLCProjectManager(tmp_path / "data" / "projects")
    tasks.auto_approver = main_module.auto_approve_task
    releases = ReleaseManager(ReleaseStore(tmp_path / "releases"), main_module.collect_integrated_tasks, main_module.validation_plan_for)
    monkeypatch.setattr(main_module, "sdlc_task_manager", tasks)
    monkeypatch.setattr(main_module, "sdlc_project_manager", projects)
    monkeypatch.setattr(main_module, "release_manager", releases)

    def configure(**workflow):
        config = SDLCProjectConfig(
            id="p", name="Shop",
            workflow=ProjectWorkflowConfig(stages=["analysis", "backend", "qa"], require_final_human_approval=True, **workflow),
            agents={"backend": AgentConfig(project_path=str(repo), test_instructions={"command": "python check.py"}),
                    "n8n": AgentConfig(enabled=False)})
        projects.save_project(config)
        return config

    return repo, tasks, releases, configure


async def afinished_task(repo, tasks, files: dict[str, str], touched: tuple[str, ...] | None = None) -> SDLCTask:
    """A task whose stages are all done and whose work sits uncommitted on its own branch."""
    task_id = tasks.next_task_id("SDLC")
    task = SDLCTask(base_task=TaskState(id=task_id, task_id=task_id, project_path=str(repo), branch=task_id,
                                        status=RunStatus.queued, step="s"),
                    title=f"Task {task_id}", project_config_id="p", current_stage="qa", sdlc_status=SDLCStatus.testing)
    await sdlc_git.prepare_task_branch(task, repo, "sandbox")
    for name, content in files.items():
        (repo / name).write_text(content, encoding="utf-8")
    changed = touched if touched is not None else tuple(files)
    for stage in ("backend", "qa"):
        task.agent_results[stage] = AgentResult(
            agent=stage, status="completed", summary=f"{stage} done", tests=TestResults(executed=True, passed=True, results=[]),
            changes=[Change(file=name, description="x") for name in changed] if stage == "backend" else [])
    await tasks.save_task(task)
    return task


def finished_task(*args, **kwargs) -> SDLCTask:
    return run(afinished_task(*args, **kwargs))


def test_low_risk_task_is_committed_merged_and_done_without_a_human(world):
    repo, tasks, _, configure = world
    config = configure(auto_final_approval=True)
    task = finished_task(repo, tasks, {"cart.py": "x = 1\n"})

    run(tasks._advance_or_complete(task, config))

    saved = run(tasks.load_task(task.base_task.task_id))
    assert saved.sdlc_status == SDLCStatus.done
    assert git(repo, "show", "develop:cart.py") == "x = 1"
    integration = saved.repos[str(repo.resolve())].integration
    assert integration.merged_into_develop and integration.merge_commit_sha == git(repo, "rev-parse", "develop")
    kinds = [event.kind for event in saved.timeline]
    assert kinds.index("all_stages_completed") < kinds.index("merged") < kinds.index("auto_approved")
    assert saved.risk.level == "low" and "Approved automatically" in saved.transition_reason
    assert git(repo, "rev-parse", "sandbox") == git(repo, "rev-parse", "main")  # sandbox only ever receives releases


def test_task_touching_sensitive_files_waits_for_a_human_and_nothing_is_merged(world):
    repo, tasks, _, configure = world
    config = configure(auto_final_approval=True)
    task = finished_task(repo, tasks, {"auth.py": "secret = 1\n"})

    run(tasks._advance_or_complete(task, config))

    saved = run(tasks.load_task(task.base_task.task_id))
    assert saved.sdlc_status == SDLCStatus.pending_approval and saved.risk.level == "medium"
    assert not [name for name in git(repo, "branch", "--list", "develop").split()]  # develop was never created
    # the human then approves through the normal button and it merges
    assert client.post(f"/api/sdlc/tasks/{task.base_task.task_id}/approve").status_code == 200
    assert git(repo, "show", "develop:auth.py") == "secret = 1"


def test_merge_conflict_during_automatic_approval_falls_back_to_a_human(world):
    repo, tasks, _, configure = world
    config = configure(auto_final_approval=True)
    first = finished_task(repo, tasks, {"shared.py": "one\n"})
    run(tasks._advance_or_complete(first, config))
    git(repo, "switch", "-q", "main")
    second = finished_task(repo, tasks, {"shared.py": "two\n"})

    run(tasks._advance_or_complete(second, config))

    saved = run(tasks.load_task(second.base_task.task_id))
    assert saved.sdlc_status == SDLCStatus.pending_approval  # never marked done
    assert saved.repos[str(repo.resolve())].integration.status == "conflict"
    assert any(event.kind == "escalated" and "Automatic approval did not complete" in event.message for event in saved.timeline)
    assert git(repo, "show", "develop:shared.py") == "one"


def test_auto_release_drafts_and_validates_a_release_but_a_human_approves_it(world):
    repo, tasks, releases, configure = world
    config = configure(auto_final_approval=True, auto_release=True, auto_release_min_tasks=2)

    async def scenario():
        for name in ("a.py", "b.py"):
            git(repo, "switch", "-q", "main")
            task = await afinished_task(repo, tasks, {name: f"# {name}\n"})
            await tasks._advance_or_complete(task, config)
            if name == "a.py":
                assert releases.store.list() == []  # one task is below the threshold
        await releases.wait()
        return releases.store.list()

    [release] = run(scenario())

    assert release.version == "0.1.0" and release.created_by == "taskloom-auto"
    assert release.status == ReleaseStatus.waiting_approval  # built + validated, NOT merged
    assert [t.task_id for t in release.tasks] == ["SDLC-1001", "SDLC-1002"]
    assert any("Created automatically" in line for line in release.logs)
    assert git(repo, "rev-parse", "sandbox") == git(repo, "rev-parse", "main")


def test_only_one_automatic_release_is_open_per_repository(world):
    repo, tasks, releases, configure = world
    config = configure(auto_final_approval=True, auto_release=True, auto_release_min_tasks=1)

    async def scenario():
        for name in ("a.py", "b.py"):
            git(repo, "switch", "-q", "main")
            await tasks._advance_or_complete(await afinished_task(repo, tasks, {name: "x\n"}), config)
            await releases.wait()
        return releases.store.list()

    found = run(scenario())

    assert len(found) == 1 and found[0].status == ReleaseStatus.waiting_approval  # the second task waits for the next one


def test_metrics_endpoint_reports_the_projects_delivery(world):
    repo, tasks, _, configure = world
    config = configure(auto_final_approval=True)
    run(tasks._advance_or_complete(finished_task(repo, tasks, {"cart.py": "x\n"}), config))

    body = client.get("/api/sdlc/metrics").json()

    assert body["total"] == 1 and body["done"] == 1 and body["automation_rate"] == 1.0
    assert body["risk"]["low"] == 1 and client.get("/api/sdlc/metrics", params={"project": "other"}).json()["total"] == 0
