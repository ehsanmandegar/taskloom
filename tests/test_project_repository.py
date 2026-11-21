"""Per-stage repositories: each agent (analysis, backend, frontend, ...) has its own Git/GitHub repo.

existing: clone once, fetch before every task; create: local repo first, private GitHub repo on first push.
"""

import asyncio
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import main as main_module
from backend.app import sdlc_git, sdlc_runner
from backend.app.models import (
    AgentConfig, AgentResult, AgentType, RepositoryConfig, RunStatus, SDLCProjectConfig, SDLCTask, StageRunner, TaskState,
)
from backend.app.services import SDLCProjectManager, SDLCTaskManager, initial_agent_args

URL = "https://github.com/acme/shop-backend"
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
    """A bare repo standing in for github.com/acme/shop-backend, with one commit on main."""
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
    monkeypatch.setattr(sdlc_git, "clean_github_url", lambda url: str(bare))
    monkeypatch.setattr(sdlc_git, "parse_github_url", lambda url: ("acme", "shop-backend"))
    return bare, seed


def project_with(tmp_path, **repos: RepositoryConfig) -> SDLCProjectConfig:
    return SDLCProjectConfig(id="shop", name="Shop", agents={stage: AgentConfig(repository=repo) for stage, repo in repos.items()})


def existing(tmp_path) -> RepositoryConfig:
    return RepositoryConfig(mode="existing", url=URL, local_path=str(tmp_path / "ws" / "backend"))


def test_each_stage_has_its_own_default_folder_and_repo_name():
    project = SDLCProjectConfig(id="shop", name="Shop", agents={
        "backend": AgentConfig(repository=RepositoryConfig(mode="create")),
        "frontend": AgentConfig(repository=RepositoryConfig(mode="create", name="shop-web")),
        "qa": AgentConfig(project_path="E:/qa"),
    })
    assert project.stage_path("backend") == str(Path.home() / "taskloom-workspaces" / "shop" / "backend")
    assert project.stage_repo_name("backend") == "shop-backend"
    assert project.stage_repo_name("frontend") == "shop-web"
    assert project.stage_path("qa") == "E:/qa"


def test_old_project_level_repository_moves_into_the_agents():
    project = SDLCProjectConfig(id="shop", name="Shop", agents={"backend": {}, "qa": {"project_path": "E:/qa"}},
                                repository={"mode": "existing", "url": URL})
    assert project.agents["backend"].repository.url == URL
    assert project.agents["qa"].repository.mode.value == "none"  # had its own folder
    assert project.repository.mode.value == "none"


def test_existing_repo_is_cloned_once_without_storing_the_token(tmp_path, remote):
    project = project_with(tmp_path, backend=existing(tmp_path))

    path = run(sdlc_git.ensure_workspace(project, "backend", TOKEN))

    assert (path / "app.py").read_text(encoding="utf-8") == "v = 1\n"
    assert run(sdlc_git.ensure_workspace(project, "backend", TOKEN)) == path
    assert TOKEN not in (path / ".git" / "config").read_text(encoding="utf-8")


def test_clone_refuses_a_non_empty_unrelated_folder(tmp_path, remote):
    project = project_with(tmp_path, backend=existing(tmp_path))
    folder = Path(project.stage_path("backend"))
    folder.mkdir(parents=True)
    (folder / "notes.txt").write_text("mine", encoding="utf-8")

    with pytest.raises(RuntimeError, match="not empty"):
        run(sdlc_git.ensure_workspace(project, "backend", TOKEN))


def test_every_new_task_branches_from_the_latest_remote_main(tmp_path, remote):
    bare, seed = remote
    project = project_with(tmp_path, backend=existing(tmp_path))
    path = run(sdlc_git.ensure_workspace(project, "backend", TOKEN))
    (seed / "app.py").write_text("v = 2\n", encoding="utf-8")
    git(seed, "commit", "-qam", "v2")
    git(seed, "push", "-q", str(bare), "main")

    run(sdlc_git.prepare_task_branch(make_task(), path, "main", TOKEN))

    assert git(path, "branch", "--show-current") == "sdlc/t1"
    assert (path / "app.py").read_text(encoding="utf-8") == "v = 2\n"


def test_new_stage_repo_starts_locally_with_an_initial_commit(tmp_path):
    project = project_with(tmp_path, frontend=RepositoryConfig(mode="create", local_path=str(tmp_path / "ws" / "frontend")))

    path = run(sdlc_git.ensure_workspace(project, "frontend", None))

    assert git(path, "branch", "--show-current") == "main"
    assert git(path, "log", "--format=%s") == "Initial commit"
    assert "Shop — frontend" in (path / "README.md").read_text(encoding="utf-8")


def test_stage_repo_is_created_private_with_its_own_name(tmp_path, monkeypatch):
    project = project_with(tmp_path, frontend=RepositoryConfig(mode="create", local_path=str(tmp_path / "ws" / "frontend")))
    run(sdlc_git.ensure_workspace(project, "frontend", None))
    empty = tmp_path / "empty.git"
    subprocess.run(["git", "init", "-q", "--bare", str(empty)], check=True)
    monkeypatch.setattr(sdlc_git, "clean_github_url", lambda url: str(empty))
    calls = []

    async def fake_api(method, path, token, body=None):
        calls.append((path, body))
        return (200, {"login": "ehsan"}) if path == "/user" else (201, {"html_url": "https://github.com/ehsan/shop-frontend"})

    monkeypatch.setattr(sdlc_git, "github_api", fake_api)

    url = run(sdlc_git.create_github_repository(project, "frontend", TOKEN))

    assert url == "https://github.com/ehsan/shop-frontend"
    assert calls[1][0] == "/user/repos" and calls[1][1]["name"] == "shop-frontend" and calls[1][1]["private"] is True
    assert git(empty, "log", "--format=%s", "main") == "Initial commit"


def test_existing_name_on_github_gives_a_clear_error(tmp_path, monkeypatch):
    project = project_with(tmp_path, backend=RepositoryConfig(mode="create"))

    async def fake_api(method, path, token, body=None):
        if path == "/user":
            return 200, {"login": "ehsan"}
        return 422, {"message": "Repository creation failed.", "errors": [{"message": "name already exists on this account"}]}

    monkeypatch.setattr(sdlc_git, "github_api", fake_api)
    with pytest.raises(sdlc_git.GitHubError, match="ehsan/shop-backend already exists"):
        run(sdlc_git.create_github_repository(project, "backend", TOKEN))


def test_each_stage_token_is_stored_encrypted_and_never_returned(tmp_path):
    manager = SDLCProjectManager(tmp_path / "data" / "projects")
    project = project_with(tmp_path, backend=existing(tmp_path), frontend=RepositoryConfig(mode="create"))
    project.agents["backend"].repository.github_token = TOKEN
    project.agents["frontend"].repository.github_token = "ghp_other"

    manager.save_project(project)

    text = (tmp_path / "data" / "projects" / "shop.json").read_text(encoding="utf-8")
    assert TOKEN not in text and "ghp_other" not in text
    assert manager.github_token("shop", "backend") == TOKEN
    assert manager.github_token("shop", "frontend") == "ghp_other"
    assert manager.get_project("shop").agents["backend"].repository.token_saved is True


def test_legacy_project_token_is_copied_to_the_migrated_agents(tmp_path):
    manager = SDLCProjectManager(tmp_path / "data" / "projects")
    manager.secrets.set("github:shop:repo", TOKEN)

    manager.save_project(SDLCProjectConfig(id="shop", name="Shop", agents={"backend": {}},
                                           repository={"mode": "create"}))

    assert manager.github_token("shop", "backend") == TOKEN
    assert manager.secrets.get("github:shop:repo") is None


def test_claude_gets_the_other_stages_folders_as_readable_dirs(tmp_path):
    args = initial_agent_args(AgentType.claude, "claude.exe", "do it", ["E:/a", "E:/b"])

    assert args[-1] == "do it"
    assert args[args.index("--add-dir"):args.index("--permission-mode")] == ["--add-dir", "E:/a", "--add-dir", "E:/b"]


@pytest.fixture
def api(tmp_path, monkeypatch):
    projects = SDLCProjectManager(tmp_path / "data" / "projects")
    tasks = SDLCTaskManager(data_dir=tmp_path / "data" / "tasks")
    monkeypatch.setattr(main_module, "sdlc_project_manager", projects)
    monkeypatch.setattr(main_module, "sdlc_task_manager", tasks)
    return TestClient(main_module.app), projects, tasks


def test_first_push_of_a_new_stage_repo_creates_it_then_pushes_the_task(tmp_path, api, monkeypatch):
    client, projects, tasks = api
    project = project_with(tmp_path, backend=RepositoryConfig(mode="create", local_path=str(tmp_path / "ws" / "backend"), github_token=TOKEN))
    projects.save_project(project)
    path = run(sdlc_git.ensure_workspace(project, "backend", None))
    task = make_task()
    run(sdlc_git.prepare_task_branch(task, path, "main"))
    (path / "cart.py").write_text("def cart(): ...\n", encoding="utf-8")
    run(tasks.save_task(task))
    remote_repo = tmp_path / "gh.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote_repo)], check=True)
    monkeypatch.setattr(sdlc_git, "clean_github_url", lambda url: str(remote_repo))
    monkeypatch.setattr(sdlc_git, "push_url", lambda url, token: str(remote_repo))
    seen = []

    async def fake_api(method, path_, token, body=None):
        seen.append((path_, token))
        return (200, {"login": "ehsan"}) if path_ == "/user" else (201, {"html_url": "https://github.com/ehsan/shop-backend"})

    monkeypatch.setattr(sdlc_git, "github_api", fake_api)

    response = client.post("/api/sdlc/tasks/t1/github/commit-push", json={"agent": "backend"})

    assert response.status_code == 200, response.text
    assert response.json()["repository_url"] == "https://github.com/ehsan/shop-backend"
    assert seen == [("/user", TOKEN), ("/user/repos", TOKEN)]
    assert projects.get_project("shop").agents["backend"].repository.url == "https://github.com/ehsan/shop-backend"
    assert "cart.py" in git(remote_repo, "show", "--stat", "--format=", "sdlc/t1")
    assert TOKEN not in response.text


def test_validate_before_a_stage_repo_exists_reports_the_future_owner(api, monkeypatch, tmp_path):
    client, projects, tasks = api
    projects.save_project(project_with(tmp_path, backend=RepositoryConfig(mode="create", github_token=TOKEN)))
    run(tasks.save_task(make_task()))

    async def fake_api(method, path, token, body=None):
        return 200, {"login": "ehsan"}

    monkeypatch.setattr(sdlc_git, "github_api", fake_api)

    body = client.post("/api/sdlc/tasks/t1/github/validate", json={"agent": "backend"}).json()

    assert body == {"status": "valid", "owner": "ehsan", "repo": "shop-backend", "will_create": True, "private": True}


def test_stages_work_in_their_own_repos_and_see_each_other(tmp_path, remote, monkeypatch):
    project = project_with(
        tmp_path,
        backend=existing(tmp_path),
        frontend=RepositoryConfig(mode="create", local_path=str(tmp_path / "ws" / "frontend")),
    )
    run(sdlc_git.ensure_workspace(project, "backend", TOKEN))  # backend already cloned by an earlier stage
    seen = {}

    async def fake_agent(agent_type, args, repo, state, timeout):
        seen.update(repo=repo, args=args)
        (Path(repo) / "App.tsx").write_text("x\n", encoding="utf-8")
        return 0, 'Done.\n```json\n{"status": "completed", "summary": "ui"}\n```'

    monkeypatch.setattr(sdlc_runner, "agent_executable", lambda agent_type: "agent.exe")
    monkeypatch.setattr(sdlc_runner, "run_agent_command", fake_agent)
    monkeypatch.setattr(sdlc_runner, "agent_response", lambda agent_type, output: ("s", output))
    monkeypatch.setattr(sdlc_runner.shutil, "which", lambda name: "claude.exe" if name == "claude" else None)
    task = make_task()
    frontend = project.agents["frontend"]

    assert sdlc_runner.resolve_runner(frontend, project.stage_path("frontend")) == StageRunner.claude
    result = run(sdlc_runner.run_cli_stage("frontend", task, project, frontend, StageRunner.claude, repo_token=TOKEN))

    frontend_repo = (tmp_path / "ws" / "frontend").resolve()
    backend_repo = str((tmp_path / "ws" / "backend").resolve())
    assert seen["repo"] == frontend_repo
    assert [c.file for c in result.changes] == ["App.tsx"]
    assert git(frontend_repo, "branch", "--show-current") == "sdlc/t1"
    assert backend_repo in seen["args"][seen["args"].index("--add-dir") + 1]
    assert f"backend: `{backend_repo}`" in seen["args"][-1]  # prompt lists the other stage's folder


def test_create_mode_heals_an_unborn_repo_names_itself_and_creates_the_remote(tmp_path, monkeypatch):
    """Empty repo on a not-yet-existing base branch + empty name + token => everything is done automatically."""
    folder = tmp_path / "ws" / "analysis"
    folder.mkdir(parents=True)
    git(folder, "init", "-q", "-b", "sandbox")  # what a failed first attempt leaves behind: no commits
    project = project_with(tmp_path, analysis=RepositoryConfig(mode="create", local_path=str(folder), default_branch="sandbox", name=""))
    empty = tmp_path / "empty.git"
    subprocess.run(["git", "init", "-q", "--bare", str(empty)], check=True)
    monkeypatch.setattr(sdlc_git, "clean_github_url", lambda url: str(empty))
    taken = {"shop-analysis"}
    created = []

    async def fake_api(method, path, token, body=None):
        if path == "/user":
            return 200, {"login": "ehsan"}
        if body["name"] in taken:
            return 422, {"message": "Repository creation failed.", "errors": [{"message": "name already exists on this account"}]}
        created.append(body["name"])
        return 201, {"html_url": f"https://github.com/ehsan/{body['name']}"}

    monkeypatch.setattr(sdlc_git, "github_api", fake_api)
    saved, notes = [], []

    path = run(sdlc_git.ensure_workspace(project, "analysis", TOKEN, saved.append, notes.append))

    repo = project.stage_repository("analysis")
    assert git(path, "log", "--format=%s", "sandbox") == "Initial commit"
    assert repo.name == created[0] == "shop-analysis-2"  # the first name was taken, so it picked the next one
    assert repo.url == "https://github.com/ehsan/shop-analysis-2"
    assert saved == [project] and any("Created GitHub repository" in n for n in notes)
    assert git(empty, "log", "--format=%s", "sandbox") == "Initial commit"
    # a task can now branch from the base
    run(sdlc_git.prepare_task_branch(make_task(), path, "sandbox"))
    assert git(path, "branch", "--show-current") == "sdlc/t1"


def test_create_mode_without_a_token_stays_local_but_still_gets_its_base_branch(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    project = project_with(tmp_path, analysis=RepositoryConfig(mode="create", local_path=str(tmp_path / "a"), default_branch="sandbox"))
    saved = []

    path = run(sdlc_git.ensure_workspace(project, "analysis", None, saved.append))

    assert git(path, "branch", "--list", "sandbox").strip().endswith("sandbox")
    assert project.stage_repository("analysis").name == "shop-analysis" and saved == [project]


def test_sdlc_stages_may_run_test_and_build_commands_but_not_arbitrary_shell():
    args = initial_agent_args(AgentType.claude, "claude.exe", "do it", ["E:/a"], sdlc_runner.SDLC_ALLOWED_TOOLS)

    tools = args[args.index("--allowedTools") + 1]
    assert "Bash(python -m pytest:*)" in tools and "Bash(npm run:*)" in tools
    assert "Bash(rm" not in tools and "Bash(*" not in tools and "Bash)" not in tools
    assert args.index("--allowedTools") < args.index("--permission-mode")  # the variadic flag never touches the prompt
    assert args[-1] == "do it"
    assert "--allowedTools" not in initial_agent_args(AgentType.claude, "claude.exe", "do it")


def test_final_approval_commits_pushes_and_opens_a_pull_request_into_the_base_branch(tmp_path, api, monkeypatch):
    client, projects, tasks = api
    folder = tmp_path / "ws" / "backend"
    project = project_with(tmp_path, backend=RepositoryConfig(
        mode="create", local_path=str(folder), default_branch="sandbox", url="https://github.com/ehsan/shop-backend", name="shop-backend"))
    projects.save_project(project)
    remote_repo = tmp_path / "gh.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote_repo)], check=True)
    monkeypatch.setattr(sdlc_git, "clean_github_url", lambda url: str(remote_repo))
    path = run(sdlc_git.ensure_workspace(project, "backend", None))
    git(path, "push", "-q", str(remote_repo), "sandbox")
    task = make_task()
    run(sdlc_git.prepare_task_branch(task, path, "sandbox"))
    (path / "cart.py").write_text("def cart(): ...\n", encoding="utf-8")
    task.sdlc_status = main_module.SDLCStatus.pending_approval
    run(tasks.save_task(task))
    monkeypatch.setattr(sdlc_git, "push_url", lambda url, token: str(remote_repo))
    monkeypatch.setattr(sdlc_git, "resolve_token", lambda token: "tok")
    prs = []

    async def fake_api(method, path_, token, body=None):
        prs.append((method, path_, body))
        return 201, {"number": 7, "html_url": "https://github.com/ehsan/shop-backend/pull/7"}

    monkeypatch.setattr(sdlc_git, "github_api", fake_api)

    response = client.post("/api/sdlc/tasks/t1/approve")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["sdlc_status"] == "done"
    assert "pull/7" in body["transition_reason"] and "`sandbox`" in body["transition_reason"]
    assert prs[0][1] == "/repos/ehsan/shop-backend/pulls" and prs[0][2]["base"] == "sandbox" and prs[0][2]["head"] == "sdlc/t1"
    assert "cart.py" in git(remote_repo, "show", "--stat", "--format=", "sdlc/t1")
    saved = run(tasks.load_task("t1"))
    repo = saved.repos[str(path.resolve())]
    assert repo.pushed and repo.pr_number == 7


def test_final_approval_still_succeeds_when_publishing_fails(tmp_path, api, monkeypatch):
    client, projects, tasks = api
    project = project_with(tmp_path, backend=RepositoryConfig(
        mode="create", local_path=str(tmp_path / "ws" / "backend"), url="https://github.com/ehsan/shop-backend"))
    projects.save_project(project)
    remote_repo = tmp_path / "gh.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote_repo)], check=True)
    monkeypatch.setattr(sdlc_git, "clean_github_url", lambda url: str(remote_repo))
    path = run(sdlc_git.ensure_workspace(project, "backend", None))
    task = make_task()
    run(sdlc_git.prepare_task_branch(task, path, "main"))
    task.sdlc_status = main_module.SDLCStatus.pending_approval
    run(tasks.save_task(task))
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    response = client.post("/api/sdlc/tasks/t1/approve")

    assert response.status_code == 200 and response.json()["sdlc_status"] == "done"
    assert "could not publish" in response.json()["transition_reason"]
