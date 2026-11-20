"""Project-level repository: clone/fetch for existing repos, create-on-first-push for new projects."""

import asyncio
import json
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import main as main_module
from backend.app import sdlc_git, sdlc_runner
from backend.app.models import (
    AgentConfig, AgentResult, ProjectRepository, RunStatus, SDLCProjectConfig, SDLCTask, StageRunner, TaskState,
)
from backend.app.services import SDLCProjectManager, SDLCTaskManager

URL = "https://github.com/acme/shop"
TOKEN = "ghp_repo_token_for_tests_000000000"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def run(coro):
    return asyncio.run(coro)


def make_task(task_id: str = "t1") -> SDLCTask:
    base = TaskState(id=task_id, task_id=task_id, project_path=".", branch=f"tasks/{task_id}", status=RunStatus.queued, step="sdlc")
    task = SDLCTask(base_task=base, title="Add cart", description="Cart API", project_config_id="shop")
    task.agent_results["backend"] = AgentResult(agent="backend", status="completed", summary="Added cart")
    return task


@pytest.fixture
def remote(tmp_path, monkeypatch):
    """A bare repo standing in for github.com/acme/shop, with one commit on main."""
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
    seed = tmp_path / "seed"
    seed.mkdir()
    git(seed, "init", "-q", "-b", "main")
    git(seed, "config", "user.name", "T")
    git(seed, "config", "user.email", "t@example.com")
    (seed / "app.py").write_text("v = 1\n", encoding="utf-8")
    git(seed, "add", "-A")
    git(seed, "commit", "-q", "-m", "init")
    git(seed, "push", "-q", str(bare), "main")
    # Route every "GitHub" URL to the local bare repo.
    monkeypatch.setattr(sdlc_git, "clean_github_url", lambda url: str(bare))
    monkeypatch.setattr(sdlc_git, "parse_github_url", lambda url: ("acme", "shop"))
    return bare, seed


def existing_project(tmp_path) -> SDLCProjectConfig:
    return SDLCProjectConfig(id="shop", name="Shop", repository=ProjectRepository(
        mode="existing", url=URL, local_path=str(tmp_path / "ws" / "shop")))


def test_existing_repo_is_cloned_once(tmp_path, remote):
    project = existing_project(tmp_path)

    path = run(sdlc_git.ensure_workspace(project, TOKEN))

    assert (path / "app.py").read_text(encoding="utf-8") == "v = 1\n"
    assert run(sdlc_git.ensure_workspace(project, TOKEN)) == path  # already cloned: no-op
    assert TOKEN not in (path / ".git" / "config").read_text(encoding="utf-8")


def test_clone_refuses_a_non_empty_unrelated_folder(tmp_path, remote):
    project = existing_project(tmp_path)
    folder = Path(project.repository.local_path)
    folder.mkdir(parents=True)
    (folder / "notes.txt").write_text("mine", encoding="utf-8")

    with pytest.raises(RuntimeError, match="not empty"):
        run(sdlc_git.ensure_workspace(project, TOKEN))


def test_every_new_task_branches_from_the_latest_remote_main(tmp_path, remote):
    bare, seed = remote
    project = existing_project(tmp_path)
    path = run(sdlc_git.ensure_workspace(project, TOKEN))

    (seed / "app.py").write_text("v = 2\n", encoding="utf-8")  # someone pushes after our clone
    git(seed, "commit", "-qam", "v2")
    git(seed, "push", "-q", str(bare), "main")

    run(sdlc_git.prepare_task_branch(make_task(), path, "main", TOKEN))

    assert git(path, "branch", "--show-current") == "sdlc/t1"
    assert (path / "app.py").read_text(encoding="utf-8") == "v = 2\n"


def test_new_project_starts_a_local_repo_with_an_initial_commit(tmp_path):
    project = SDLCProjectConfig(id="fresh", name="Fresh Shop", description="from scratch", repository=ProjectRepository(
        mode="create", local_path=str(tmp_path / "ws" / "fresh")))

    path = run(sdlc_git.ensure_workspace(project, None))

    assert git(path, "branch", "--show-current") == "main"
    assert git(path, "log", "--format=%s") == "Initial commit"
    assert "Fresh Shop" in (path / "README.md").read_text(encoding="utf-8")


def test_github_repo_is_created_private_under_the_token_owner_and_main_pushed(tmp_path, remote, monkeypatch):
    bare, _ = remote
    project = SDLCProjectConfig(id="fresh", name="Fresh", repository=ProjectRepository(
        mode="create", local_path=str(tmp_path / "ws" / "fresh")))
    run(sdlc_git.ensure_workspace(project, None))
    calls = []

    async def fake_api(method, path, token, body=None):
        calls.append((method, path, body))
        if path == "/user":
            return 200, {"login": "ehsan"}
        return 201, {"html_url": "https://github.com/ehsan/fresh"}

    monkeypatch.setattr(sdlc_git, "github_api", fake_api)
    # The fixture's bare repo already has a main; use a fresh empty one for this new project.
    empty = tmp_path / "empty.git"
    subprocess.run(["git", "init", "-q", "--bare", str(empty)], check=True)
    monkeypatch.setattr(sdlc_git, "clean_github_url", lambda url: str(empty))

    url = run(sdlc_git.create_github_repository(project, TOKEN))

    assert url == "https://github.com/ehsan/fresh"
    assert calls[1][1] == "/user/repos" and calls[1][2]["name"] == "fresh" and calls[1][2]["private"] is True
    assert git(empty, "log", "--format=%s", "main") == "Initial commit"


def test_existing_name_on_github_gives_a_clear_error(tmp_path, monkeypatch):
    project = SDLCProjectConfig(id="fresh", name="Fresh", repository=ProjectRepository(mode="create"))

    async def fake_api(method, path, token, body=None):
        if path == "/user":
            return 200, {"login": "ehsan"}
        return 422, {"message": "Repository creation failed.", "errors": [{"message": "name already exists on this account"}]}

    monkeypatch.setattr(sdlc_git, "github_api", fake_api)
    with pytest.raises(sdlc_git.GitHubError, match="ehsan/fresh already exists"):
        run(sdlc_git.create_github_repository(project, TOKEN))


def test_repository_token_is_stored_encrypted_and_never_returned(tmp_path):
    manager = SDLCProjectManager(tmp_path / "data" / "projects")
    project = existing_project(tmp_path)
    project.repository.github_token = TOKEN

    manager.save_project(project)

    assert TOKEN not in (tmp_path / "data" / "projects" / "shop.json").read_text(encoding="utf-8")
    assert manager.repository_token("shop") == TOKEN
    assert manager.get_project("shop").repository.token_saved is True
    assert manager.get_project("shop").repository.github_token == ""


@pytest.fixture
def api(tmp_path, monkeypatch):
    projects = SDLCProjectManager(tmp_path / "data" / "projects")
    tasks = SDLCTaskManager(data_dir=tmp_path / "data" / "tasks")
    monkeypatch.setattr(main_module, "sdlc_project_manager", projects)
    monkeypatch.setattr(main_module, "sdlc_task_manager", tasks)
    return TestClient(main_module.app), projects, tasks


def test_first_push_of_a_new_project_creates_the_repo_then_pushes_the_task(tmp_path, api, monkeypatch):
    client, projects, tasks = api
    project = SDLCProjectConfig(id="shop", name="Shop", repository=ProjectRepository(
        mode="create", local_path=str(tmp_path / "ws" / "shop"), github_token=TOKEN))
    projects.save_project(project)
    path = run(sdlc_git.ensure_workspace(project, None))
    task = make_task()
    run(sdlc_git.prepare_task_branch(task, path, "main"))
    (path / "cart.py").write_text("def cart(): ...\n", encoding="utf-8")
    run(tasks.save_task(task))
    remote_repo = tmp_path / "gh.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote_repo)], check=True)
    monkeypatch.setattr(sdlc_git, "clean_github_url", lambda url: str(remote_repo))
    monkeypatch.setattr(sdlc_git, "push_url", lambda url, token: str(remote_repo))
    seen_tokens = []

    async def fake_api(method, path_, token, body=None):
        seen_tokens.append(token)
        return (200, {"login": "ehsan"}) if path_ == "/user" else (201, {"html_url": "https://github.com/ehsan/shop"})

    monkeypatch.setattr(sdlc_git, "github_api", fake_api)

    response = client.post("/api/sdlc/tasks/t1/github/commit-push", json={})

    assert response.status_code == 200, response.text
    assert response.json()["repository_url"] == "https://github.com/ehsan/shop"
    assert seen_tokens == [TOKEN, TOKEN]  # the saved project token was used
    assert projects.get_project("shop").repository.url == "https://github.com/ehsan/shop"
    assert git(remote_repo, "log", "--format=%s", "main") == "Initial commit"
    assert "cart.py" in git(remote_repo, "show", "--stat", "--format=", "sdlc/t1")
    assert TOKEN not in response.text


def test_validate_before_the_repo_exists_reports_the_future_owner(api, monkeypatch, tmp_path):
    client, projects, tasks = api
    projects.save_project(SDLCProjectConfig(id="shop", name="Shop", repository=ProjectRepository(mode="create", github_token=TOKEN)))
    run(tasks.save_task(make_task()))

    async def fake_api(method, path, token, body=None):
        return 200, {"login": "ehsan"}

    monkeypatch.setattr(sdlc_git, "github_api", fake_api)

    body = client.post("/api/sdlc/tasks/t1/github/validate", json={}).json()

    assert body == {"status": "valid", "owner": "ehsan", "repo": "shop", "will_create": True, "private": True}


def test_stage_without_its_own_folder_runs_in_the_cloned_repository(tmp_path, remote, monkeypatch):
    project = existing_project(tmp_path)
    project.agents["backend"] = AgentConfig()  # no project_path: use the project repository
    seen = {}

    async def fake_agent(agent_type, args, repo, state, timeout):
        seen["repo"] = repo
        (Path(repo) / "cart.py").write_text("x = 1\n", encoding="utf-8")
        return 0, 'Done.\n```json\n{"status": "completed", "summary": "cart"}\n```'

    monkeypatch.setattr(sdlc_runner, "agent_executable", lambda agent_type: "agent.exe")
    monkeypatch.setattr(sdlc_runner, "run_agent_command", fake_agent)
    monkeypatch.setattr(sdlc_runner, "agent_response", lambda agent_type, output: ("s", output))
    monkeypatch.setattr(sdlc_runner.shutil, "which", lambda name: "claude.exe" if name == "claude" else None)
    task = make_task()

    assert sdlc_runner.resolve_runner(project.agents["backend"], project.stage_path("backend")) == StageRunner.claude
    result = run(sdlc_runner.run_cli_stage("backend", task, project, project.agents["backend"], StageRunner.claude, repo_token=TOKEN))

    workspace = Path(project.repository.local_path).resolve()
    assert seen["repo"] == workspace
    assert [c.file for c in result.changes] == ["cart.py"]
    assert git(workspace, "branch", "--show-current") == "sdlc/t1"
    assert task.repos[str(workspace)].base_branch == "main"
