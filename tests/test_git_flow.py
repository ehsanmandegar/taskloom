"""Branching strategy: task branches from sandbox, final approval into develop, locking, shared DWS/SDLC behaviour."""

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import git_flow, main as main_module, sdlc_git, services
from backend.app.git_flow import GitBusyError, GitFlowError, GitRepo, MergeConflictError, SandboxMissingError
from backend.app.models import AgentConfig, RunStatus, SDLCProjectConfig, SDLCStatus, SDLCTask, TaskRequest, TaskState
from backend.app.services import SDLCProjectManager, SDLCTaskManager

from gitflow_helpers import approve, git, git_ok, init_repo, run, work_on_task

client = TestClient(main_module.app)


# ---------------------------------------------------------------------------------------- naming

@pytest.mark.parametrize("task_id", ["DWS-1001", "DWS-1002", "SDLC-1001", "SDLC-1500", "podw-225"])
def test_branch_name_is_the_task_identifier(task_id):
    assert git_flow.task_branch_name(task_id) == task_id


@pytest.mark.parametrize("bad", ["sandbox", "develop", "main", "Develop", "release/1.0.0", "a b", "../x", "x..y", "", "-x", "x.lock"])
def test_reserved_or_unsafe_branch_names_are_refused(bad):
    with pytest.raises(GitFlowError):
        git_flow.task_branch_name(bad)


def test_sdlc_ids_are_sequential_and_never_repeat(tmp_path):
    manager = SDLCTaskManager(data_dir=tmp_path)
    assert [manager.next_task_id("SDLC") for _ in range(3)] == ["SDLC-1001", "SDLC-1002", "SDLC-1003"]
    (tmp_path / "SDLC-1500").mkdir()  # a task folder above the counter lifts it
    assert manager.next_task_id("SDLC") == "SDLC-1501"
    assert manager.next_task_id("DWS") == "DWS-1001"


# --------------------------------------------------------------------- task branches from sandbox

def test_task_branch_starts_from_sandbox_not_main_or_develop(tmp_path):
    repo = init_repo(tmp_path / "repo")
    git(repo, "switch", "-q", "sandbox")
    (repo / "s.txt").write_text("sandbox only\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "sandbox moves ahead")
    git(repo, "switch", "-q", "main")
    git(repo, "branch", "develop", "main")

    info = run(git_flow.create_task_branch(GitRepo(repo), "DWS-1001"))

    assert info.created and info.name == "DWS-1001"
    assert git(repo, "rev-parse", "DWS-1001") == git(repo, "rev-parse", "sandbox") == info.base_sha
    assert git(repo, "show", "DWS-1001:s.txt") == "sandbox only"


def test_task_branch_is_created_from_the_latest_remote_sandbox(tmp_path):
    origin = tmp_path / "origin.git"
    repo = init_repo(tmp_path / "repo", origin)
    other = tmp_path / "other"
    git(tmp_path, "clone", "-q", str(origin), str(other))
    git(other, "config", "user.name", "T")
    git(other, "config", "user.email", "t@example.com")
    git(other, "switch", "-q", "sandbox")
    (other / "new.txt").write_text("remote\n", encoding="utf-8")
    git(other, "add", "-A")
    git(other, "commit", "-q", "-m", "remote sandbox commit")
    git(other, "push", "-q", "origin", "sandbox")
    assert not git_ok(repo, "cat-file", "-e", f"{git(other, 'rev-parse', 'HEAD')}^{{commit}}")  # not fetched yet

    run(git_flow.create_task_branch(GitRepo(repo), "DWS-1002"))

    assert git(repo, "rev-parse", "DWS-1002") == git(other, "rev-parse", "HEAD")


def test_existing_task_branch_is_reused_untouched(tmp_path):
    repo = init_repo(tmp_path / "repo")
    head = work_on_task(repo, "DWS-1003", {"a.txt": "a\n"})

    info = run(git_flow.create_task_branch(GitRepo(repo), "DWS-1003"))

    assert not info.created and info.head_sha == head == git(repo, "rev-parse", "DWS-1003")


def test_missing_sandbox_is_a_clear_error_without_fallback(tmp_path):
    repo = init_repo(tmp_path / "repo")
    git(repo, "branch", "-D", "sandbox")
    git(repo, "branch", "develop")

    with pytest.raises(SandboxMissingError, match="`sandbox` does not exist"):
        run(git_flow.create_task_branch(GitRepo(repo), "DWS-1004"))

    assert not git_ok(repo, "rev-parse", "--verify", "DWS-1004")


def test_unreachable_origin_stops_branch_creation_instead_of_using_stale_refs(tmp_path):
    repo = init_repo(tmp_path / "repo", tmp_path / "origin.git")
    git(repo, "remote", "set-url", "origin", str(tmp_path / "does-not-exist.git"))

    with pytest.raises(GitFlowError, match="Could not fetch"):
        run(git_flow.create_task_branch(GitRepo(repo), "DWS-1005"))

    assert not git_ok(repo, "rev-parse", "--verify", "DWS-1005")


# ------------------------------------------------------------------- final approval into develop

def test_final_approval_merges_the_task_branch_into_develop_and_keeps_it(tmp_path):
    repo = init_repo(tmp_path / "repo", tmp_path / "origin.git")
    work_on_task(repo, "DWS-1010", {"feature.txt": "feature\n"})
    assert not git_ok(repo, "rev-parse", "--verify", "develop")  # nothing is integrated before approval

    result = approve(repo, "DWS-1010")

    assert git(repo, "show", "develop:feature.txt") == "feature"
    assert result.merge_commit_sha == git(repo, "rev-parse", "develop")
    assert len(git(repo, "rev-list", "--parents", "-n", "1", "develop").split()) == 3  # a real merge commit
    assert git(repo, "rev-parse", "DWS-1010")  # task branch preserved
    assert git(tmp_path / "origin.git", "rev-parse", "develop") == result.merge_commit_sha  # pushed, not forced
    assert git(repo, "rev-parse", "sandbox") == git(repo, "rev-parse", "main")  # sandbox untouched


def test_approving_twice_is_idempotent(tmp_path):
    repo = init_repo(tmp_path / "repo")
    work_on_task(repo, "DWS-1011", {"f.txt": "f\n"})
    first = approve(repo, "DWS-1011")

    second = approve(repo, "DWS-1011")

    assert second.already_merged and second.merge_commit_sha == first.merge_commit_sha
    assert git(repo, "rev-parse", "develop") == first.merge_commit_sha


def test_merge_conflict_aborts_cleanly_and_reports_the_files(tmp_path):
    repo = init_repo(tmp_path / "repo")
    work_on_task(repo, "DWS-1012", {"base.txt": "from 1012\n"})
    work_on_task(repo, "DWS-1013", {"base.txt": "from 1013\n"})
    approve(repo, "DWS-1012")
    develop_before = git(repo, "rev-parse", "develop")

    with pytest.raises(MergeConflictError) as error:
        approve(repo, "DWS-1013")

    assert error.value.files == ["base.txt"] and "base.txt" in str(error.value)
    assert git(repo, "rev-parse", "develop") == develop_before
    assert git(repo, "show", "develop:base.txt") == "from 1012"
    assert not git_ok(repo, "rev-parse", "-q", "--verify", "MERGE_HEAD")


def test_uncommitted_work_on_the_task_branch_blocks_the_approval(tmp_path):
    repo = init_repo(tmp_path / "repo")
    work_on_task(repo, "DWS-1014", {"f.txt": "f\n"})
    git(repo, "switch", "-q", "DWS-1014")
    (repo / "f.txt").write_text("edited after the last commit\n", encoding="utf-8")

    with pytest.raises(GitFlowError, match="uncommitted changes"):
        approve(repo, "DWS-1014")


def test_push_failure_rolls_the_local_merge_back(tmp_path):
    origin = tmp_path / "origin.git"
    repo = init_repo(tmp_path / "repo", origin)
    work_on_task(repo, "DWS-1015", {"f.txt": "f\n"})
    hook = origin / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\necho rejected by policy >&2\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)

    with pytest.raises(GitFlowError, match="push"):
        approve(repo, "DWS-1015")

    assert git(repo, "rev-parse", "develop") == git(repo, "rev-parse", "sandbox")  # develop is back where it was


def test_commits_on_protected_branches_are_refused(tmp_path):
    repo = init_repo(tmp_path / "repo")
    git(repo, "switch", "-q", "develop") if git_ok(repo, "rev-parse", "--verify", "develop") else git(repo, "switch", "-q", "-c", "develop")

    with pytest.raises(GitFlowError, match="protected"):
        run(git_flow.commit_task_work(repo, "develop", "msg"))


# ------------------------------------------------------------------------------- git locking

def test_concurrent_git_operations_on_one_repository_are_refused(tmp_path):
    repo = init_repo(tmp_path / "repo")
    work_on_task(repo, "DWS-1020", {"f.txt": "f\n"})

    async def scenario():
        async with git_flow.repo_lock(repo, "long running operation"):
            with pytest.raises(GitBusyError, match="long running operation"):
                await git_flow.create_task_branch(GitRepo(repo), "DWS-1021")
            with pytest.raises(GitBusyError):
                await git_flow.integrate_task(repo, "DWS-1020", "DWS-1020")
        await git_flow.create_task_branch(GitRepo(repo), "DWS-1021")  # free again afterwards

    run(scenario())
    assert git(repo, "rev-parse", "DWS-1021")


def test_two_simultaneous_approvals_merge_once(tmp_path):
    repo = init_repo(tmp_path / "repo")
    work_on_task(repo, "DWS-1022", {"f.txt": "f\n"})

    async def scenario():
        return await asyncio.gather(git_flow.integrate_task(repo, "DWS-1022", "DWS-1022"),
                                    git_flow.integrate_task(repo, "DWS-1022", "DWS-1022"), return_exceptions=True)

    outcomes = run(scenario())

    assert sum(isinstance(item, git_flow.IntegrationResult) and not item.already_merged for item in outcomes) <= 1
    assert len(git(repo, "rev-list", "--merges", "develop").splitlines()) == 1


# ---------------------------------------------------------- DWS and SDLC share one implementation

def test_dws_and_sdlc_branches_both_come_from_the_shared_service(tmp_path, monkeypatch):
    """Classic (DWS) execute_task and the SDLC stage runner create branches through git_flow.create_task_branch."""
    calls = []
    real = git_flow.create_task_branch

    async def spy(repo, task_id, branch=None):
        calls.append((task_id, branch))
        return await real(repo, task_id, branch)

    monkeypatch.setattr(git_flow, "create_task_branch", spy)
    monkeypatch.setattr(sdlc_git, "create_task_branch", spy)

    sdlc_repo = init_repo(tmp_path / "sdlc")
    task = SDLCTask(base_task=TaskState(id="x", task_id="SDLC-1001", project_path=".", branch="SDLC-1001",
                                        status=RunStatus.queued, step="s"), title="t")
    run(sdlc_git.prepare_task_branch(task, sdlc_repo, "main"))

    dws_repo = init_repo(tmp_path / "dws")
    request = TaskRequest(project_path=str(dws_repo), task_id="DWS-1001", request="do the thing please")
    state = TaskState(id="y", task_id="DWS-1001", project_path=str(dws_repo), branch="DWS-1001", status=RunStatus.queued, step="q")
    monkeypatch.setattr(services, "agent_executable", lambda agent_type: "codex")

    async def stop_before_the_agent(*args, **kwargs):  # the agent itself is irrelevant: only the branch matters
        raise RuntimeError("stop after branch preparation")

    monkeypatch.setattr(services, "run_agent_command", stop_before_the_agent)
    run(services.execute_task(request, state))

    assert [call[0] for call in calls] == ["SDLC-1001", "DWS-1001"]
    for repo, name in ((sdlc_repo, "SDLC-1001"), (dws_repo, "DWS-1001")):
        assert git(repo, "rev-parse", name) == git(repo, "rev-parse", "sandbox")
        assert git(repo, "branch", "--show-current") == name
    assert state.base_branch == "sandbox"


# ------------------------------------------------- approval endpoints (SDLC and classic DWS)

@pytest.fixture
def sdlc_api(tmp_path, monkeypatch):
    repo = init_repo(tmp_path / "shop")
    tasks = SDLCTaskManager(data_dir=tmp_path / "data" / "tasks")
    projects = SDLCProjectManager(tmp_path / "data" / "projects")
    projects.save_project(SDLCProjectConfig(id="p", name="Shop", agents={"backend": AgentConfig(project_path=str(repo))}))
    monkeypatch.setattr(main_module, "sdlc_task_manager", tasks)
    monkeypatch.setattr(main_module, "sdlc_project_manager", projects)
    return repo, tasks


def sdlc_task_in_review(repo: Path, tasks: SDLCTaskManager, files: dict[str, str]) -> str:
    task_id = tasks.next_task_id("SDLC")
    task = SDLCTask(base_task=TaskState(id=task_id, task_id=task_id, project_path=str(repo), branch=task_id,
                                        status=RunStatus.queued, step="s"), title="Cart", project_config_id="p")
    run(sdlc_git.prepare_task_branch(task, repo, "sandbox"))
    for name, content in files.items():
        (repo / name).write_text(content, encoding="utf-8")  # uncommitted work of the last stage
    task.sdlc_status = SDLCStatus.pending_approval
    run(tasks.save_task(task))
    return task_id


def test_sdlc_final_approval_merges_into_develop_then_marks_done(sdlc_api):
    repo, tasks = sdlc_api
    task_id = sdlc_task_in_review(repo, tasks, {"cart.py": "x = 1\n"})
    assert task_id == "SDLC-1001" and git(repo, "branch", "--show-current") == "SDLC-1001"

    response = client.post(f"/api/sdlc/tasks/{task_id}/approve")

    assert response.status_code == 200, response.text
    assert response.json()["sdlc_status"] == "done"
    saved = run(tasks.load_task(task_id))
    integration = saved.repos[str(repo.resolve())].integration
    assert integration.merged_into_develop and integration.status == "merged"
    assert integration.merge_commit_sha == git(repo, "rev-parse", "develop")
    assert git(repo, "show", "develop:cart.py") == "x = 1"
    assert git(repo, "rev-parse", "sandbox") == git(repo, "rev-parse", "main")


def test_sdlc_merge_failure_does_not_mark_the_task_done(sdlc_api):
    repo, tasks = sdlc_api
    # develop already holds a conflicting change to the same file
    work_on_task(repo, "DWS-9000", {"cart.py": "from develop\n"})
    approve(repo, "DWS-9000")
    git(repo, "switch", "-q", "main")
    task_id = sdlc_task_in_review(repo, tasks, {"cart.py": "from the sdlc task\n"})
    develop_before = git(repo, "rev-parse", "develop")

    response = client.post(f"/api/sdlc/tasks/{task_id}/approve")

    assert response.status_code == 409 and "cart.py" in response.json()["detail"]
    saved = run(tasks.load_task(task_id))
    assert saved.sdlc_status == SDLCStatus.pending_approval  # NOT done
    integration = saved.repos[str(repo.resolve())].integration
    assert integration.status == "conflict" and integration.conflicts == ["cart.py"] and not integration.merged_into_develop
    assert git(repo, "rev-parse", "develop") == develop_before


def test_sdlc_approval_requires_the_pending_approval_state(sdlc_api):
    repo, tasks = sdlc_api
    task_id = sdlc_task_in_review(repo, tasks, {"a.py": "a\n"})
    run(tasks.update_task(task_id, lambda task: setattr(task, "sdlc_status", SDLCStatus.testing)))

    assert client.post(f"/api/sdlc/tasks/{task_id}/approve").status_code == 409
    assert not git_ok(repo, "rev-parse", "--verify", "develop")


def test_classic_dws_approval_merges_into_develop(tmp_path, monkeypatch):
    repo = init_repo(tmp_path / "dws")
    work_on_task(repo, "DWS-1100", {"feature.txt": "f\n"})
    state = TaskState(id="dws-run", task_id="DWS-1100", project_path=str(repo), branch="DWS-1100", base_branch="sandbox",
                      status=RunStatus.passed, step="Ready for review")
    monkeypatch.setattr(main_module, "save_tasks", lambda states: None)
    main_module.tasks["dws-run"] = state
    try:
        response = client.post("/api/tasks/dws-run/approve")
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "done"
        assert state.git_integration.merged_into_develop
        assert git(repo, "show", "develop:feature.txt") == "f"
    finally:
        main_module.tasks.pop("dws-run", None)


def test_classic_failed_merge_stays_passed_not_done(tmp_path, monkeypatch):
    repo = init_repo(tmp_path / "dws")
    work_on_task(repo, "DWS-1101", {"base.txt": "one\n"})
    work_on_task(repo, "DWS-1102", {"base.txt": "two\n"})
    approve(repo, "DWS-1101")
    state = TaskState(id="dws-run2", task_id="DWS-1102", project_path=str(repo), branch="DWS-1102", base_branch="sandbox",
                      status=RunStatus.passed, step="Ready for review")
    monkeypatch.setattr(main_module, "save_tasks", lambda states: None)
    main_module.tasks["dws-run2"] = state
    try:
        response = client.post("/api/tasks/dws-run2/approve")
        assert response.status_code == 409 and "base.txt" in response.json()["detail"]
        assert state.status == RunStatus.passed and not state.git_integration.merged_into_develop
        assert state.git_integration.status == "conflict"
    finally:
        main_module.tasks.pop("dws-run2", None)


def test_admin_token_protects_final_approval(sdlc_api, monkeypatch):
    repo, tasks = sdlc_api
    task_id = sdlc_task_in_review(repo, tasks, {"a.py": "a\n"})
    monkeypatch.setenv("TASKLOOM_ADMIN_TOKEN", "s3cret")

    assert client.post(f"/api/sdlc/tasks/{task_id}/approve").status_code == 403
    assert client.post(f"/api/sdlc/tasks/{task_id}/approve", headers={"X-Taskloom-Admin-Token": "wrong"}).status_code == 403
    ok = client.post(f"/api/sdlc/tasks/{task_id}/approve", headers={"X-Taskloom-Admin-Token": "s3cret"})
    assert ok.status_code == 200


def test_branch_switch_endpoint_creates_new_task_branches_from_sandbox_whatever_base_is_requested(tmp_path):
    repo = init_repo(tmp_path / "repo")
    git(repo, "branch", "develop")
    work_on_task(repo, "DWS-1200", {"f.txt": "f\n"})

    existing = client.post("/api/branches/switch", json={"project_path": str(repo), "branch": "DWS-1200", "base_branch": "develop"})
    created = client.post("/api/branches/switch", json={"project_path": str(repo), "branch": "DWS-1201", "base_branch": "develop"})

    assert existing.status_code == 200 and existing.json()["created"] is False and existing.json()["current"] == "DWS-1200"
    assert created.status_code == 200 and created.json()["created"] is True and created.json()["current"] == "DWS-1201"
    assert git(repo, "merge-base", "DWS-1201", "sandbox") == git(repo, "rev-parse", "sandbox")


def test_branch_switch_endpoint_reports_a_missing_sandbox(tmp_path):
    repo = init_repo(tmp_path / "repo")
    git(repo, "branch", "-D", "sandbox")

    response = client.post("/api/branches/switch", json={"project_path": str(repo), "branch": "DWS-1202"})

    assert response.status_code == 409 and "sandbox" in response.json()["detail"]
    assert not git_ok(repo, "rev-parse", "--verify", "DWS-1202")
