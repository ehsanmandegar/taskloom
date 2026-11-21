import asyncio
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import main as main_module
from backend.app import sdlc_git
from backend.app.models import AgentConfig, AgentResult, RunStatus, SDLCProjectConfig, SDLCTask, TaskState
from backend.app.services import SDLCProjectManager, SDLCTaskManager

client = TestClient(main_module.app)


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def make_repo(path: Path, branch: str = "main") -> Path:
    path.mkdir(parents=True)
    git(path, "init", "-q", "-b", branch)
    git(path, "config", "user.name", "Test")
    git(path, "config", "user.email", "test@example.com")
    (path / "app.py").write_text("x = 1\n", encoding="utf-8")
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", "init")
    return path


def make_task(task_id: str = "sdlc-git1") -> SDLCTask:
    base = TaskState(id=task_id, task_id=task_id, project_path=".", branch=f"tasks/{task_id}", status=RunStatus.queued, step="sdlc")
    task = SDLCTask(base_task=base, title="Add cart", description="Cart API", project_config_id="p")
    task.agent_results["backend"] = AgentResult(agent="backend", status="completed", summary="Added cart endpoint",
                                                tests={"executed": True, "passed": True, "results": []})
    return task


def run(coro):
    return asyncio.run(coro)


def test_task_branch_is_created_from_base_and_reused(tmp_path):
    repo = make_repo(tmp_path / "repo")
    sub = repo / "service"
    sub.mkdir()
    task = make_task()

    record = run(sdlc_git.prepare_task_branch(task, sub, "main"))

    assert git(repo, "branch", "--show-current") == "sdlc/sdlc-git1"
    assert record.branch == "sdlc/sdlc-git1" and record.base_branch == "main"
    assert task.repos[str(repo.resolve())] is record

    (repo / "app.py").write_text("x = 2\n", encoding="utf-8")  # an earlier stage's uncommitted work
    assert run(sdlc_git.prepare_task_branch(task, repo, "main")) is record
    assert git(repo, "branch", "--show-current") == "sdlc/sdlc-git1"


def test_uncommitted_changes_on_another_branch_block_the_stage(tmp_path):
    repo = make_repo(tmp_path / "repo")
    (repo / "app.py").write_text("dirty\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="uncommitted changes"):
        run(sdlc_git.prepare_task_branch(make_task(), repo, "main"))
    assert git(repo, "branch", "--show-current") == "main"


def test_missing_base_branch_falls_back_to_current_branch(tmp_path):
    repo = make_repo(tmp_path / "repo", branch="master")

    record = run(sdlc_git.prepare_task_branch(make_task(), repo, "main"))

    assert record.base_branch == "master"
    assert git(repo, "branch", "--show-current") == "sdlc/sdlc-git1"


def test_plain_folder_has_no_branch(tmp_path):
    assert run(sdlc_git.prepare_task_branch(make_task(), tmp_path, "main")) is None


@pytest.mark.parametrize("url", [
    "https://github.com/acme/shop", "https://github.com/acme/shop.git", "git@github.com:acme/shop.git",
    "https://user@github.com/acme/shop/",
])
def test_github_urls_are_parsed(url):
    assert sdlc_git.parse_github_url(url) == ("acme", "shop")


def test_non_github_url_is_rejected_for_api_calls():
    with pytest.raises(sdlc_git.GitHubError):
        sdlc_git.parse_github_url("https://gitlab.com/acme/shop")


def test_push_url_embeds_token_only_for_github():
    assert sdlc_git.push_url("https://github.com/acme/shop", "tok") == "https://x-access-token:tok@github.com/acme/shop.git"
    assert sdlc_git.push_url("C:/remotes/shop.git", "") == "C:/remotes/shop.git"
    with pytest.raises(sdlc_git.GitHubError, match="token is required"):
        sdlc_git.push_url("https://github.com/acme/shop", "")


@pytest.fixture
def api(tmp_path, monkeypatch):
    """Point the API at temp managers with a project whose backend folder is a Git repo."""
    repo = make_repo(tmp_path / "shop")
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    tasks = SDLCTaskManager(data_dir=tmp_path / "data" / "tasks")
    projects = SDLCProjectManager(tmp_path / "data" / "projects")
    projects.save_project(SDLCProjectConfig(id="p", name="Shop", agents={"backend": AgentConfig(project_path=str(repo))}))
    monkeypatch.setattr(main_module, "sdlc_task_manager", tasks)
    monkeypatch.setattr(main_module, "sdlc_project_manager", projects)
    task = make_task()
    run(sdlc_git.prepare_task_branch(task, repo, "main"))
    (repo / "cart.py").write_text("def cart(): ...\n", encoding="utf-8")
    run(tasks.save_task(task))
    return tasks, repo, remote


def test_commit_push_commits_task_changes_and_pushes_the_branch(api):
    tasks, repo, remote = api

    response = client.post("/api/sdlc/tasks/sdlc-git1/github/commit-push", json={"agent": "backend", "repo_url": str(remote)})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["branch"] == "sdlc/sdlc-git1" and body["message"] == "Committed and pushed"
    assert git(remote, "rev-parse", "refs/heads/sdlc/sdlc-git1") == body["commit_sha"]
    message = git(repo, "log", "-1", "--format=%B")
    assert message.startswith("feat(sdlc-git1): Add cart") and "backend: Added cart endpoint" in message
    saved = run(tasks.load_task("sdlc-git1"))
    assert saved.repos[str(repo.resolve())].pushed is True

    again = client.post("/api/sdlc/tasks/sdlc-git1/github/commit-push", json={"agent": "backend", "repo_url": str(remote)})
    assert again.json()["message"].startswith("Nothing new to commit")


def test_commit_push_refuses_when_repo_left_the_task_branch(api):
    _, repo, remote = api
    git(repo, "stash", "-u")
    git(repo, "switch", "main")

    response = client.post("/api/sdlc/tasks/sdlc-git1/github/commit-push", json={"agent": "backend", "repo_url": str(remote)})

    assert response.status_code == 400
    assert "not the task branch" in response.json()["detail"]


def test_push_errors_never_echo_the_token(api, monkeypatch):
    monkeypatch.setattr(sdlc_git, "push_url", lambda url, token: str(api[2]) + "-missing-secret-tok")

    response = client.post("/api/sdlc/tasks/sdlc-git1/github/commit-push",
                           json={"agent": "backend", "repo_url": "https://github.com/acme/shop", "github_token": "secret-tok"})

    assert response.status_code == 400
    assert "secret-tok" not in response.json()["detail"]


def test_create_pr_requires_push_then_opens_pr_with_stage_summary(api, monkeypatch):
    tasks, repo, remote = api
    calls = []

    async def fake_api(method, path, token, body=None):
        calls.append((method, path, token, body))
        return 201, {"number": 7, "html_url": "https://github.com/acme/shop/pull/7"}

    monkeypatch.setattr(sdlc_git, "github_api", fake_api)
    payload = {"agent": "backend", "repo_url": "https://github.com/acme/shop", "github_token": "tok"}

    not_pushed = client.post("/api/sdlc/tasks/sdlc-git1/github/create-pr", json=payload)
    assert not_pushed.status_code == 400 and "Push" in not_pushed.json()["detail"]

    client.post("/api/sdlc/tasks/sdlc-git1/github/commit-push", json={"agent": "backend", "repo_url": str(remote)})
    response = client.post("/api/sdlc/tasks/sdlc-git1/github/create-pr", json=payload)

    assert response.status_code == 200, response.text
    assert response.json() == {"message": "Pull request created", "pr_number": 7, "pr_url": "https://github.com/acme/shop/pull/7"}
    method, path, token, body = calls[-1]
    assert (method, path, token) == ("POST", "/repos/acme/shop/pulls", "tok")
    assert body["head"] == "sdlc/sdlc-git1" and body["base"] == "main"
    assert "Added cart endpoint" in body["body"] and "tests passed" in body["body"]
    assert run(tasks.load_task("sdlc-git1")).repos[str(repo.resolve())].pr_number == 7


def test_existing_pr_is_returned_instead_of_failing(api, monkeypatch):
    tasks, repo, remote = api

    async def fake_api(method, path, token, body=None):
        if method == "POST":
            return 422, {"message": "Validation Failed", "errors": [{"message": "A pull request already exists for acme:sdlc/sdlc-git1."}]}
        return 200, [{"number": 3, "html_url": "https://github.com/acme/shop/pull/3"}]

    monkeypatch.setattr(sdlc_git, "github_api", fake_api)
    client.post("/api/sdlc/tasks/sdlc-git1/github/commit-push", json={"agent": "backend", "repo_url": str(remote)})

    response = client.post("/api/sdlc/tasks/sdlc-git1/github/create-pr",
                           json={"agent": "backend", "repo_url": "https://github.com/acme/shop", "github_token": "tok"})

    assert response.json()["pr_number"] == 3


@pytest.mark.parametrize("status, expected", [(200, "valid"), (401, "invalid or expired"), (404, "was not found")])
def test_validate_reports_repo_access(api, monkeypatch, status, expected):
    async def fake_api(method, path, token, body=None):
        return status, {"default_branch": "main", "permissions": {"push": True}}

    monkeypatch.setattr(sdlc_git, "github_api", fake_api)

    body = client.post("/api/sdlc/tasks/sdlc-git1/github/validate",
                       json={"repo_url": "https://github.com/acme/shop", "github_token": "tok"}).json()

    if status == 200:
        assert body == {"status": "valid", "owner": "acme", "repo": "shop", "default_branch": "main", "can_push": True}
    else:
        assert body["status"] == "invalid" and expected in body["message"]


def test_task_branch_in_a_repository_without_commits(tmp_path):
    repo = tmp_path / "fresh"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "sandbox")  # the configured base branch exists only as an unborn branch

    record = run(sdlc_git.prepare_task_branch(make_task(), repo, "sandbox"))

    assert git(repo, "branch", "--show-current") == "sdlc/sdlc-git1"
    assert record.branch == "sdlc/sdlc-git1"


def test_managed_repo_sets_aside_uncommitted_leftovers_instead_of_failing(tmp_path):
    repo = make_repo(tmp_path / "repo")
    (repo / "app.py").write_text("npm rewrote me\n", encoding="utf-8")
    (repo / "new.txt").write_text("untracked\n", encoding="utf-8")
    task = make_task()

    with pytest.raises(RuntimeError, match="uncommitted changes"):  # a user's own folder is never touched
        run(sdlc_git.prepare_task_branch(task, repo, "main"))

    run(sdlc_git.prepare_task_branch(task, repo, "main", auto_stash=True))

    assert git(repo, "branch", "--show-current") == "sdlc/sdlc-git1"
    assert git(repo, "status", "--porcelain") == ""
    assert "taskloom: auto-stash" in git(repo, "stash", "list")
    assert any("Set aside uncommitted changes" in line for line in task.base_task.logs)
