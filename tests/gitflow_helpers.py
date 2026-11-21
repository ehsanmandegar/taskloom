"""Real-Git fixtures shared by the git-flow and release tests (no mocked Git: every assertion reads the repository)."""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from backend.app import git_flow
from backend.app.git_flow import GitRepo
from backend.app.releases import IntegratedTask, MergeEntry, ReleaseManager, ReleaseStore, repository_id_for


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def git_ok(repo: Path, *args: str) -> bool:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True).returncode == 0


def run(coro):
    return asyncio.run(coro)


def init_repo(path: Path, origin: Path | None = None) -> Path:
    """A repository with `main` and `sandbox` at the same commit; with `origin` a bare remote holding both."""
    path.mkdir(parents=True)
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.name", "Test")
    git(path, "config", "user.email", "test@example.com")
    (path / "base.txt").write_text("base\n", encoding="utf-8")
    (path / "check.py").write_text(
        "import pathlib, sys\nsys.exit(1 if pathlib.Path('broken.txt').exists() else 0)\n", encoding="utf-8")
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", "init")
    git(path, "branch", "sandbox")
    if origin is not None:
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
        git(path, "remote", "add", "origin", str(origin))
        git(path, "push", "-q", "origin", "main", "sandbox")
    return path


def work_on_task(repo: Path, task_id: str, files: dict[str, str], message: str | None = None) -> str:
    """Create the task branch from sandbox with the shared service, commit `files` on it, return to `main`."""
    run(git_flow.create_task_branch(GitRepo(repo), task_id))
    git(repo, "switch", "-q", task_id)
    for name, content in files.items():
        target = repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message or f"work for {task_id}")
    head = git(repo, "rev-parse", "HEAD")
    git(repo, "switch", "-q", "main")
    return head


def approve(repo: Path, task_id: str) -> git_flow.IntegrationResult:
    """What the final approval does to Git."""
    return run(git_flow.integrate_task(repo, task_id, task_id))


class Registry:
    """Stands in for the task stores: remembers what each final approval merged, like TaskRepo.integration does."""

    def __init__(self, repo: Path, workflow: str = "DWS"):
        self.repo, self.workflow = repo, workflow
        self.tasks: dict[str, IntegratedTask] = {}
        self.plan: list[dict] = []

    def integrate(self, task_id: str, workflow: str | None = None) -> git_flow.IntegrationResult:
        return run(self.aintegrate(task_id, workflow))

    async def aintegrate(self, task_id: str, workflow: str | None = None) -> git_flow.IntegrationResult:
        result = await git_flow.integrate_task(self.repo, task_id, task_id)
        entry = MergeEntry(merge_commit_sha=result.merge_commit_sha, branch_head=result.branch_head_sha, files=result.files)
        task = self.tasks.get(task_id)
        if task is None:
            task = self.tasks[task_id] = IntegratedTask(
                task_id=task_id, workflow=workflow or self.workflow, title=task_id, status="done",
                repository_id=repository_id_for(self.repo), repository_path=str(self.repo), branch=task_id)
        if result.merge_commit_sha and all(m.merge_commit_sha != result.merge_commit_sha for m in task.merges):
            task.merges.append(entry)
        return result

    async def tasks_provider(self):
        return list(self.tasks.values())

    async def plan_provider(self, repository_path, task_ids):
        return list(self.plan)

    def manager(self, tmp_path: Path) -> ReleaseManager:
        return ReleaseManager(ReleaseStore(tmp_path / "releases"), self.tasks_provider, self.plan_provider)

    @property
    def repository_id(self) -> str:
        return repository_id_for(self.repo)


PASSING = [{"kind": "test", "command": "python check.py", "working_directory": ""}]
