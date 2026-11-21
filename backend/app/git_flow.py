"""Shared Git branching strategy for every Taskloom workflow (DWS classic tasks, SDLC tasks, releases).

Branches
    sandbox          permanent base: every task branch starts from the latest `sandbox`
    develop          integration branch: receives a task branch only after final human approval
    <TASK-ID>        one branch per task, named exactly like the task (DWS-1001, SDLC-1500, ...)
    release/<ver>    built from `sandbox` out of the selected tasks, merged back into `sandbox`
                     only after validation and explicit human approval

Safety rules enforced here (callers cannot bypass them):
    * one Git operation per repository at a time (cross-process lock; the second caller gets GitBusyError)
    * `sandbox` is never silently replaced by another branch
    * merges and checkouts of `develop`/`sandbox` happen in the branch's own worktree (or a temporary one),
      so a developer's or agent's working tree is never touched
    * no force-push, no branch deletion, no commits made directly on protected branches
    * a step is reported as done only after Git confirmed it (exit codes and re-read refs, never assumptions)
"""

from __future__ import annotations

import asyncio
import base64
import os
import re
import shutil
import tempfile
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path

from . import services
from .file_lock import FileLock
from .models import GitIntegration

SANDBOX = "sandbox"
DEVELOP = "develop"
RELEASE_PREFIX = "release/"
PROTECTED_BRANCHES = frozenset({SANDBOX, DEVELOP, "main", "master"})
_TASK_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
_TASKLOOM_IDENTITY = ["-c", "user.name=Taskloom", "-c", "user.email=taskloom@localhost"]


class GitFlowError(RuntimeError):
    """A Git step failed or was refused; the message is safe to show to the administrator."""


class GitBusyError(GitFlowError):
    """Another Git operation is running on the same repository."""


class SandboxMissingError(GitFlowError):
    pass


class MergeConflictError(GitFlowError):
    def __init__(self, message: str, files: list[str]):
        super().__init__(message)
        self.files = files


# --------------------------------------------------------------------------------------------- naming

def task_branch_name(task_id: str) -> str:
    """The Git branch of a task: exactly its identifier. Never `develop`, `sandbox`, `main` or a release branch."""
    name = (task_id or "").strip()
    if not _TASK_ID.fullmatch(name) or ".." in name or name.endswith((".", ".lock")):
        raise GitFlowError(f"`{task_id}` is not a valid task identifier for a Git branch name")
    if name.lower() in PROTECTED_BRANCHES or name.lower().startswith(RELEASE_PREFIX):
        raise GitFlowError(f"`{name}` is a reserved branch name and cannot be used for a task")
    return name


def release_branch_name(version: str) -> str:
    return f"{RELEASE_PREFIX}{version}"


def assert_not_protected(branch: str, action: str = "commit to") -> None:
    if branch in PROTECTED_BRANCHES or branch.startswith(RELEASE_PREFIX):
        raise GitFlowError(f"Refusing to {action} protected branch `{branch}` directly")


# ---------------------------------------------------------------------------------------- auth helpers

def auth_args(token: str | None) -> list[str]:
    """git -c options that send the token as an HTTP header for this one command only.

    The token never lands in a URL, in .git/config, or in the remote's name."""
    if not token:
        return []
    basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    return ["-c", f"http.https://github.com/.extraheader=AUTHORIZATION: basic {basic}"]


def redact_auth(text: str, token: str | None) -> str:
    if not token:
        return text
    basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    return text.replace(token, "***").replace(basic, "***")


# ------------------------------------------------------------------------------------------- repository

@dataclass
class GitRepo:
    """One repository plus the operation log every Git call is appended to."""
    root: Path
    token: str | None = None
    log: list[str] = field(default_factory=list)

    async def run(self, *args: str, cwd: Path | None = None, timeout: int = 300, check: bool = False,
                  network: bool = False, identity: bool = False) -> tuple[int, str]:
        argv = ["git", *(auth_args(self.token) if network else []), *(_TASKLOOM_IDENTITY if identity else []), *args]
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"} if network else None
        code, output = await services.command(argv, cwd or self.root, timeout, env=env) if env else \
            await services.command(argv, cwd or self.root, timeout)
        output = redact_auth(output or "", self.token)
        line = "git " + " ".join(args) + f" -> exit {code}"
        if code and output.strip():
            line += ": " + output.strip().splitlines()[0][:300]
        self.log.append(line)
        if check and code:
            raise GitFlowError(f"git {args[0]} failed: {output.strip()[:600] or 'no output'}")
        return code, output

    async def out(self, *args: str, cwd: Path | None = None) -> str:
        """stdout of a command that must succeed, stripped."""
        _, output = await self.run(*args, cwd=cwd, check=True)
        return output.strip()

    async def ok(self, *args: str, cwd: Path | None = None) -> bool:
        code, _ = await self.run(*args, cwd=cwd)
        return code == 0

    async def rev(self, ref: str, cwd: Path | None = None) -> str | None:
        code, output = await self.run("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", cwd=cwd)
        return output.strip() if code == 0 and output.strip() else None

    async def has_origin(self) -> bool:
        code, output = await self.run("remote")
        return code == 0 and "origin" in output.split()

    async def is_ancestor(self, ancestor: str, descendant: str) -> bool:
        return await self.ok("merge-base", "--is-ancestor", ancestor, descendant)

    async def fetch(self) -> None:
        """Fetch the latest remote references; two attempts so a transient network error is not fatal.
        With an origin a failed fetch is an error: working from stale references would be silent staleness."""
        if not await self.has_origin():
            return
        last = ""
        for attempt in range(2):
            code, output = await self.run("fetch", "--prune", "origin", network=True, timeout=300)
            if code == 0:
                return
            last = output.strip()
            if attempt == 0:
                await asyncio.sleep(1)
        raise GitFlowError("Could not fetch from origin (nothing was changed): " + last[:500])

    async def push(self, branch: str) -> None:
        """Fast-forward push of one local branch; never forced."""
        if not await self.has_origin():
            return
        code, output = await self.run("push", "origin", f"refs/heads/{branch}:refs/heads/{branch}", network=True, timeout=300)
        if code:
            raise GitFlowError(f"git push of `{branch}` to origin failed: {output.strip()[:500]}")

    async def dirty_tracked(self, cwd: Path) -> bool:
        code, output = await self.run("status", "--porcelain", "--untracked-files=no", cwd=cwd)
        if code:
            raise GitFlowError("Could not read the working tree status: " + output.strip()[:300])
        return bool(output.strip())


async def repo_root(path: Path) -> Path | None:
    code, output = await services.command(["git", "rev-parse", "--show-toplevel"], path)
    return Path(output.strip()).resolve() if code == 0 and output.strip() else None


# ------------------------------------------------------------------------------------------- locking

_active_operations: dict[str, str] = {}


@asynccontextmanager
async def repo_lock(root: Path, operation: str):
    """Exclusive, non-waiting lock for mutating Git operations on a repository (all of its worktrees).

    The lock file lives in the common git dir, so it is shared by every worktree and every Taskloom
    process; the OS drops it if the holder crashes."""
    code, common = await services.command(["git", "rev-parse", "--git-common-dir"], root)
    if code or not common.strip():
        raise GitFlowError(f"{root} is not a Git repository")
    git_dir = Path(common.strip())
    git_dir = (git_dir if git_dir.is_absolute() else root / git_dir).resolve()
    key = str(git_dir)
    lock = FileLock(git_dir / "taskloom-git.lock", timeout=0)
    if not lock.try_acquire():
        running = _active_operations.get(key)
        raise GitBusyError("Another Git operation" + (f" ({running})" if running else "") +
                           " is already running on this repository; try again when it has finished")
    _active_operations[key] = operation
    try:
        yield
    finally:
        _active_operations.pop(key, None)
        lock.release()


# ------------------------------------------------------------------------------------------ worktrees

async def _worktree_of(repo: GitRepo, branch: str) -> Path | None:
    code, output = await repo.run("worktree", "list", "--porcelain")
    if code:
        return None
    path = None
    for line in output.splitlines():
        if line.startswith("worktree "):
            path = Path(line[len("worktree "):].strip())
        elif line.strip() == f"branch refs/heads/{branch}" and path is not None:
            return path
    return None


@asynccontextmanager
async def branch_workspace(repo: GitRepo, branch: str):
    """A directory where `branch` is checked out: its own worktree when it already has one (it must have no
    tracked local changes), otherwise a temporary worktree that is removed afterwards (the branch stays)."""
    existing = await _worktree_of(repo, branch)
    if existing is not None:
        if await repo.dirty_tracked(existing):
            raise GitFlowError(f"`{branch}` is checked out in {existing} with uncommitted changes; "
                               "commit or stash them first so nothing is overwritten")
        yield existing
        return
    temp = Path(tempfile.mkdtemp(prefix="taskloom-wt-"))
    shutil.rmtree(temp, ignore_errors=True)
    await repo.run("worktree", "add", str(temp), branch, check=True)
    try:
        yield temp
    finally:
        await remove_worktree(repo, temp)


async def remove_worktree(repo: GitRepo, path: Path) -> None:
    await repo.run("worktree", "remove", "--force", str(path))
    shutil.rmtree(path, ignore_errors=True)
    await repo.run("worktree", "prune")


# ---------------------------------------------------------------------------------- branch resolution

async def sandbox_ref(repo: GitRepo) -> str:
    """The most recent `sandbox` commit (after a fetch): origin's, or a local one that is ahead of it.
    Raises SandboxMissingError: there is deliberately no fallback to develop, main or any other branch."""
    return await _latest_ref(repo, SANDBOX, required=True)


async def _latest_ref(repo: GitRepo, branch: str, required: bool) -> str | None:
    local = await repo.rev(f"refs/heads/{branch}")
    remote = await repo.rev(f"refs/remotes/origin/{branch}")
    if local is None and remote is None:
        if required:
            raise SandboxMissingError(
                f"Base branch `{branch}` does not exist locally or on origin in {repo.root}. Create it first; "
                "Taskloom never falls back to another branch.")
        return None
    if local is None:
        return f"origin/{branch}"
    if remote is None or local == remote or await repo.is_ancestor(remote, local):
        return f"refs/heads/{branch}"
    if await repo.is_ancestor(local, remote):
        return f"origin/{branch}"
    raise GitFlowError(f"Local `{branch}` and origin/{branch} have diverged; resolve that before continuing")


@dataclass
class TaskBranch:
    name: str
    created: bool
    base_sha: str
    head_sha: str


async def create_task_branch(repo: GitRepo, task_id: str, branch: str | None = None) -> TaskBranch:
    """Make sure the task's branch exists, creating it from the latest `sandbox` when it is new.

    A new branch is created only after fetching the latest remote references. An existing branch is reused
    untouched (idempotent, and no network is needed). `branch` overrides the name only for branches recorded
    by older Taskloom versions (`sdlc/<id>`, `tasks/<id>`). Does not check anything out."""
    if branch:
        assert_not_protected(branch, "create a task on")
        name = branch
    else:
        name = task_branch_name(task_id)
    async with repo_lock(repo.root, f"create branch {name}"):
        local = await repo.rev(f"refs/heads/{name}")
        if local:
            try:
                base = await repo.out("merge-base", local, await sandbox_ref(repo))
            except GitFlowError:  # an existing branch stays usable even when sandbox is unreachable right now
                base = ""
            return TaskBranch(name, False, base, local)
        await repo.fetch()
        remote = await repo.rev(f"refs/remotes/origin/{name}")
        source = f"origin/{name}" if remote else await sandbox_ref(repo)
        base_sha = await repo.rev(source) or ""
        await repo.run("branch", "--no-track", name, source, check=True)
        head = await repo.rev(f"refs/heads/{name}")
        if head is None:  # Git said OK but the ref is not there: do not pretend
            raise GitFlowError(f"Branch `{name}` was not created")
        return TaskBranch(name, not remote, base_sha, head)


async def ensure_local_branch(repo: GitRepo, branch: str) -> str:
    """Head SHA of `branch`; a branch that exists only on origin gets a local ref. GitFlowError when missing."""
    head = await repo.rev(f"refs/heads/{branch}")
    if head:
        return head
    if await repo.rev(f"refs/remotes/origin/{branch}"):
        await repo.run("branch", "--no-track", branch, f"origin/{branch}", check=True)
        head = await repo.rev(f"refs/heads/{branch}")
        if head:
            return head
    raise GitFlowError(f"Branch `{branch}` does not exist locally or on origin")


async def sync_local_branch(repo: GitRepo, branch: str, create_from: str | None = None) -> str:
    """Bring the local `branch` up to date with origin by fast-forward only (never a reset), creating it from
    origin's copy, or from `create_from` when it exists nowhere. Returns the local head SHA."""
    latest = await _latest_ref(repo, branch, required=create_from is None)
    if latest is None:
        await repo.run("branch", "--no-track", branch, create_from, check=True)
        repo.log.append(f"`{branch}` did not exist: created it from {create_from}")
    elif latest.startswith("origin/"):
        if await repo.rev(f"refs/heads/{branch}") is None:
            await repo.run("branch", "--no-track", branch, latest, check=True)
        else:  # fast-forward the local branch to origin's without disturbing anyone's checkout
            async with branch_workspace(repo, branch) as workspace:
                await repo.run("merge", "--ff-only", latest, cwd=workspace, check=True, identity=True)
    head = await repo.rev(f"refs/heads/{branch}")
    if head is None:
        raise GitFlowError(f"Branch `{branch}` could not be prepared")
    return head


async def ensure_develop(repo: GitRepo) -> str:
    """The `develop` integration branch, up to date with origin. A missing `develop` is created from `sandbox`
    and logged; it is never a task's development branch."""
    return await sync_local_branch(repo, DEVELOP, create_from=await sandbox_ref(repo))


async def ensure_sandbox(repo: GitRepo) -> str:
    return await sync_local_branch(repo, SANDBOX)


async def order_commits(repo: GitRepo, shas: list[str], tip: str) -> list[str]:
    """`shas` in the order they entered `tip`'s history (oldest first), so changes are replayed as they happened."""
    out = await repo.out("rev-list", "--topo-order", "--reverse", tip)
    position = {sha: index for index, sha in enumerate(out.splitlines())}
    return sorted(dict.fromkeys(shas), key=lambda sha: position.get(sha, len(position)))


# ------------------------------------------------------------------------------ task -> develop

@dataclass
class IntegrationResult:
    already_merged: bool
    merge_commit_sha: str
    branch_head_sha: str
    develop_before_sha: str
    develop_after_sha: str
    files: list[str]
    log: list[str]


async def integrate_task(root: Path, task_id: str, branch: str, token: str | None = None) -> IntegrationResult:
    """Final approval: merge the task branch into `develop` with a merge commit (`--no-ff`).

    The merge commit is what releases later use to isolate exactly this task's changes. Conflicts abort the
    merge and leave `develop` as it was. Push failures roll the local merge back. Nothing is force-pushed."""
    if branch.startswith(("sdlc/", "tasks/")):  # branches recorded by older Taskloom versions
        assert_not_protected(branch, "merge")
    else:
        task_branch_name(branch)
    repo = GitRepo(root, token)
    async with repo_lock(root, f"merge {branch} into {DEVELOP}"):
        await repo.fetch()
        head = await ensure_local_branch(repo, branch)
        task_workspace = await _worktree_of(repo, branch)
        if task_workspace is not None and await repo.dirty_tracked(task_workspace):
            raise GitFlowError(f"Task branch `{branch}` has uncommitted changes in {task_workspace}; "
                               "commit them before the final approval")
        develop = await ensure_develop(repo)
        if await repo.is_ancestor(head, develop):
            merge_sha = await find_merge_commit(repo, head, develop)
            return IntegrationResult(True, merge_sha, head, develop, develop, [], repo.log)
        async with branch_workspace(repo, DEVELOP) as workspace:
            before = await repo.out("rev-parse", "HEAD", cwd=workspace)
            code, output = await repo.run("merge", "--no-ff", "--no-edit", "-m", f"Merge {task_id} into {DEVELOP}", branch,
                                          cwd=workspace, identity=True)
            if code:
                _, unmerged = await repo.run("diff", "--name-only", "--diff-filter=U", cwd=workspace)
                files = [line.strip() for line in unmerged.splitlines() if line.strip()]
                await repo.run("merge", "--abort", cwd=workspace)
                if await repo.out("rev-parse", "HEAD", cwd=workspace) != before:
                    raise GitFlowError(f"Merge of `{branch}` failed and `{DEVELOP}` moved unexpectedly; inspect it manually")
                if files:
                    raise MergeConflictError(f"Merge conflict merging `{branch}` into `{DEVELOP}` in: " + ", ".join(files) +
                                             f". `{DEVELOP}` was not changed.", files)
                raise GitFlowError(f"Merging `{branch}` into `{DEVELOP}` failed: {output.strip()[:500]}")
            after = await repo.out("rev-parse", "HEAD", cwd=workspace)
            try:
                await repo.push(DEVELOP)
            except GitFlowError:
                await repo.run("reset", "--hard", before, cwd=workspace)  # undo only the merge we just made
                raise
            _, changed = await repo.run("diff", "--name-only", before, after, cwd=workspace)
        parents = (await repo.out("rev-list", "--parents", "-n", "1", after)).split()
        if after == before or len(parents) < 3:
            raise GitFlowError(f"Git did not create a merge commit for `{branch}`")
        return IntegrationResult(False, after, head, before, after,
                                 [line.strip() for line in changed.splitlines() if line.strip()], repo.log)


async def find_merge_commit(repo: GitRepo, branch_head: str, develop: str) -> str:
    """The merge commit on develop's first-parent line that brought `branch_head` in, if any."""
    code, output = await repo.run("rev-list", "--merges", "--first-parent", "--ancestry-path", f"{branch_head}..{develop}")
    candidates = [line.strip() for line in output.splitlines() if line.strip()] if code == 0 else []
    for sha in reversed(candidates):  # oldest first
        parents = (await repo.out("rev-list", "--parents", "-n", "1", sha)).split()
        if len(parents) >= 3 and parents[2] == branch_head:
            return sha
    return ""


async def commit_task_work(root: Path, branch: str, message: str) -> str:
    """Commit everything on the task branch (it must be checked out in `root`); returns the branch head SHA.
    Refuses protected branches."""
    assert_not_protected(branch)
    repo = GitRepo(root)
    current = (await repo.run("branch", "--show-current"))[1].strip()
    if current != branch:
        raise GitFlowError(f"{root} is on `{current or 'detached HEAD'}`, not the task branch `{branch}`")
    async with repo_lock(root, f"commit on {branch}"):
        await repo.run("add", "-A", check=True)
        if not await repo.ok("diff", "--cached", "--quiet"):  # something is staged
            code, output = await services.command(["git", "commit", "-q", "-F", "-"], root, stdin_text=message)
            lowered = output.lower()
            if code and ("identity" in lowered or "tell me who you are" in lowered):
                code, output = await services.command(["git", *_TASKLOOM_IDENTITY, "commit", "-q", "-F", "-"], root, stdin_text=message)
            if code:
                raise GitFlowError("git commit failed: " + output.strip()[:500])
        head = await repo.rev("HEAD")
        if head is None:
            raise GitFlowError("The task branch has no commits")
        return head


# -------------------------------------------------------------------- recording on the task's integration

def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)


def record_merge(integration: GitIntegration, root: Path, result: IntegrationResult) -> None:
    """Store a confirmed merge into develop on the task's integration record (history keeps every merge)."""
    integration.repo_root = str(root)
    integration.status, integration.merged_into_develop = "merged", True
    integration.conflicts, integration.error = [], ""
    integration.log = result.log[-60:]
    if result.merge_commit_sha:
        known = {entry.get("merge_commit_sha") for entry in integration.history}
        if result.merge_commit_sha not in known:
            integration.history.append({"merge_commit_sha": result.merge_commit_sha, "branch_head": result.branch_head_sha,
                                        "merged_at": _now().isoformat(), "files": result.files})
        integration.merge_commit_sha = result.merge_commit_sha
        integration.merged_branch_head = result.branch_head_sha
        integration.develop_before_sha = result.develop_before_sha
        integration.merged_at = _now()


def record_failure(integration: GitIntegration, root: Path, error: Exception, log: list[str] | None = None) -> None:
    integration.repo_root = str(root)
    integration.status = "conflict" if isinstance(error, MergeConflictError) else "failed"
    integration.conflicts = list(getattr(error, "files", []) or [])
    integration.error = str(error)
    if log:
        integration.log = log[-60:]
    # A failed attempt never clears a previous successful merge: `merged_into_develop` keeps describing develop.
