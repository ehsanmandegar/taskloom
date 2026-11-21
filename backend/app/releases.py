"""Release management: combine selected, already-approved tasks into one version and merge it into `sandbox`.

Flow (every step is confirmed by Git before it is recorded):

    develop ──(merge commit of each selected task)──▶ release/<version> (built from sandbox in its own worktree)
        draft → preparing → testing → waiting_approval ──human approval──▶ approved → merging → released
                     └──────────── failed (retry / cancel) ◀──────────────┘

Isolation: a task enters `develop` through a `--no-ff` merge commit (git_flow.integrate_task). Cherry-picking that
merge commit with `-m 1` replays exactly the diff the task contributed to develop, nothing else that happens
to be in develop. After the picks the release branch is compared to `sandbox`; any file that is not part of a
selected task's own merge aborts the release instead of shipping unrelated changes.

Releases are stored one JSON file per release (data/releases/<id>.json), written atomically under a file lock.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import shutil
import tempfile
import time
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Awaitable, Callable

from pydantic import BaseModel, Field

from . import services
from .file_lock import FileLock, replace_with_retry
from .git_flow import (
    DEVELOP, SANDBOX, GitFlowError, GitRepo, MergeConflictError, branch_workspace, ensure_develop, ensure_sandbox,
    order_commits, release_branch_name, remove_worktree, repo_lock, sandbox_ref, find_merge_commit,
)

VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")


class ReleaseError(RuntimeError):
    """A release request that cannot be honoured (bad input, wrong state, ineligible task)."""


class ReleaseInputError(ReleaseError):
    """The request itself is wrong (bad version, empty or ineligible selection)."""


class ReleaseStatus(str, Enum):
    draft = "draft"
    preparing = "preparing"
    testing = "testing"
    waiting_approval = "waiting_approval"
    approved = "approved"
    merging = "merging"
    released = "released"
    failed = "failed"
    cancelled = "cancelled"


# Releases in these states hold their version number and the merge commits of their tasks.
HOLDING = {ReleaseStatus.draft, ReleaseStatus.preparing, ReleaseStatus.testing, ReleaseStatus.waiting_approval,
           ReleaseStatus.approved, ReleaseStatus.merging, ReleaseStatus.released}
RUNNING = {ReleaseStatus.preparing, ReleaseStatus.testing, ReleaseStatus.approved, ReleaseStatus.merging}


def now() -> datetime:
    return datetime.now(timezone.utc)


def repository_id_for(path: str | Path) -> str:
    return "repo-" + hashlib.sha1(str(Path(path)).lower().encode()).hexdigest()[:10]


# ------------------------------------------------------------------------------------------------ models

class MergeEntry(BaseModel):
    merge_commit_sha: str
    branch_head: str = ""
    merged_at: datetime | None = None
    files: list[str] = Field(default_factory=list)


class IntegratedTask(BaseModel):
    """A task whose branch has been merged into develop by its final approval."""
    task_id: str
    workflow: str  # DWS or SDLC
    title: str = ""
    status: str = ""
    project_id: str = ""
    repository_id: str
    repository_path: str
    repository_name: str = ""
    branch: str = ""
    merges: list[MergeEntry] = Field(default_factory=list)


class ReleaseTask(BaseModel):
    task_id: str
    workflow: str = ""
    title: str = ""
    branch: str = ""
    merge_commit_shas: list[str] = Field(default_factory=list)
    picks: list[dict] = Field(default_factory=list)  # {merge_commit_sha, picked_commit_sha, files}


class ValidationResult(BaseModel):
    kind: str = "test"  # setup | test
    command: str
    working_directory: str = ""
    exit_code: int | None = None
    passed: bool = False
    output: str = ""
    duration_seconds: float = 0.0
    message: str = ""


class Release(BaseModel):
    id: str
    version: str
    repository_id: str
    repository_path: str
    repository_name: str = ""
    source_branch: str = DEVELOP
    target_branch: str = SANDBOX
    release_branch: str
    tasks: list[ReleaseTask] = Field(default_factory=list)
    status: ReleaseStatus = ReleaseStatus.draft
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)
    created_by: str = "admin"
    approved_at: datetime | None = None
    approved_by: str = ""
    released_at: datetime | None = None
    base_sha: str = ""            # sandbox commit the release branch was built on
    final_commit_sha: str = ""    # release branch head that was validated and approved
    merge_commit_sha: str = ""    # merge commit created on sandbox
    validation_plan: list[dict] = Field(default_factory=list)
    validation: list[ValidationResult] = Field(default_factory=list)
    validation_warning: str = ""
    error: str = ""
    failed_phase: str = ""        # preparing | testing | merging
    branch_pushed: bool = False
    logs: list[str] = Field(default_factory=list)
    schema_version: int = 1


# ------------------------------------------------------------------------------------------------ store

class ReleaseStore:
    """One JSON file per release; every write is atomic and serialised by a cross-process lock."""

    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def _file(self, release_id: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", release_id):
            raise ReleaseError("Invalid release id")
        return self.directory / f"{release_id}.json"

    def _lock(self) -> FileLock:
        return FileLock(self.directory / ".store.lock", timeout=15)

    def _read(self, release_id: str) -> Release | None:
        path = self._file(release_id)
        try:
            return Release.model_validate_json(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None

    def _write(self, release: Release) -> None:
        release.updated_at = now()
        path = self._file(release.id)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(release.model_dump_json(indent=2), encoding="utf-8")
        replace_with_retry(temporary, path)

    def get(self, release_id: str) -> Release | None:
        return self._read(release_id)

    def list(self) -> list[Release]:
        found = []
        for path in self.directory.glob("*.json"):
            try:
                found.append(Release.model_validate_json(path.read_text(encoding="utf-8")))
            except (OSError, ValueError) as exc:
                print(f"[Releases] Ignoring unreadable release file {path.name}: {exc}", flush=True)
        return sorted(found, key=lambda release: release.created_at, reverse=True)

    def add(self, release: Release, check: Callable[[list[Release]], None]) -> Release:
        """Insert a release if `check(all releases)` accepts it; the check and the insert are one atomic step."""
        with self._lock():
            check(self.list())
            self._write(release)
        return release

    def update(self, release_id: str, mutate: Callable[[Release], None]) -> Release:
        """Re-read, mutate and write one release atomically. `mutate` may raise to refuse (nothing is written)."""
        with self._lock():
            release = self._read(release_id)
            if release is None:
                raise ReleaseError(f"Release {release_id} not found")
            mutate(release)
            self._write(release)
            return release


# ---------------------------------------------------------------------------------------------- manager

TasksProvider = Callable[[], Awaitable[list[IntegratedTask]]]
PlanProvider = Callable[[str, list[str]], Awaitable[list[dict]]]
TokenProvider = Callable[[str], str | None]


class ReleaseManager:
    def __init__(self, store: ReleaseStore, tasks_provider: TasksProvider, plan_provider: PlanProvider,
                 token_provider: TokenProvider | None = None, validation_timeout: int = 1800):
        self.store = store
        self.tasks_provider = tasks_provider
        self.plan_provider = plan_provider
        self.token_provider = token_provider or (lambda path: None)
        self.validation_timeout = validation_timeout
        self._jobs: dict[str, asyncio.Task] = {}

    # ----- queries

    async def integrated_tasks(self) -> list[IntegratedTask]:
        return await self.tasks_provider()

    def _holders(self) -> dict[tuple[str, str], Release]:
        """(repository id, merge commit) -> the release that holds those changes."""
        holders = {}
        for release in self.store.list():
            if release.status in HOLDING:
                for task in release.tasks:
                    for sha in task.merge_commit_shas:
                        holders[(release.repository_id, sha)] = release
        return holders

    async def eligible_tasks(self) -> list[dict]:
        """Every task integrated into develop, with what is still unreleased, and why a task is not selectable."""
        holders = self._holders()
        rows = []
        for task in await self.integrated_tasks():
            pending = [m for m in task.merges if (task.repository_id, m.merge_commit_sha) not in holders]
            versions = {}
            for merge in task.merges:
                holder = holders.get((task.repository_id, merge.merge_commit_sha))
                if holder:
                    versions[holder.id] = {"id": holder.id, "version": holder.version, "status": holder.status.value}
            reason = ""
            if not task.merges:
                reason = "No merge commit was recorded for this task, so its changes cannot be isolated"
            elif not pending:
                reason = "All of its changes are already in " + ", ".join(v["version"] for v in versions.values())
            rows.append({**task.model_dump(mode="json"), "pending_merges": [m.model_dump(mode="json") for m in pending],
                         "eligible": bool(pending), "reason": reason, "releases": list(versions.values())})
        return rows

    async def repositories(self) -> list[dict]:
        seen: dict[str, dict] = {}
        for task in await self.integrated_tasks():
            entry = seen.setdefault(task.repository_id, {"id": task.repository_id, "path": task.repository_path,
                                                         "name": task.repository_name or Path(task.repository_path).name, "tasks": 0})
            entry["tasks"] += 1
        return sorted(seen.values(), key=lambda entry: entry["name"].lower())

    def releases_for_task(self, task_id: str) -> list[dict]:
        return [{"id": r.id, "version": r.version, "status": r.status.value, "released_at": r.released_at,
                 "merge_commit_sha": r.merge_commit_sha}
                for r in self.store.list() if r.status != ReleaseStatus.cancelled and any(t.task_id == task_id for t in r.tasks)]

    # ----- creation

    async def create(self, version: str, repository_id: str, task_ids: list[str], created_by: str = "admin",
                     start: bool = True) -> Release:
        version = (version or "").strip()
        if not VERSION_PATTERN.fullmatch(version):
            raise ReleaseInputError("Version must look like 1.0.1 (optionally 1.0.1-rc.1)")
        task_ids = list(dict.fromkeys(task_ids or []))
        if not task_ids:
            raise ReleaseInputError("Select at least one task")
        candidates = {t.task_id: t for t in await self.integrated_tasks() if t.repository_id == repository_id}
        unknown = [task_id for task_id in task_ids if task_id not in candidates]
        if unknown:
            raise ReleaseInputError("Not integrated into develop in this repository: " + ", ".join(unknown))
        repository = candidates[task_ids[0]]
        plan = await self.plan_provider(repository.repository_path, task_ids)
        release = Release(
            id="rel_" + uuid.uuid4().hex[:10], version=version, repository_id=repository_id,
            repository_path=repository.repository_path, repository_name=repository.repository_name,
            release_branch=release_branch_name(version), created_by=created_by or "admin", validation_plan=plan)

        def check(existing: list[Release]) -> None:
            held = {(r.repository_id, sha): r for r in existing if r.status in HOLDING for t in r.tasks for sha in t.merge_commit_shas}
            for other in existing:
                if other.repository_id == repository_id and other.version == version and other.status in HOLDING:
                    raise ReleaseError(f"Version {version} already exists in this repository ({other.status.value})")
            release.tasks = []
            for task_id in task_ids:
                task = candidates[task_id]
                pending = [m for m in task.merges if (repository_id, m.merge_commit_sha) not in held]
                if not pending:
                    raise ReleaseInputError(f"{task_id} has no unreleased changes: its changes are already part of another release")
                release.tasks.append(ReleaseTask(
                    task_id=task_id, workflow=task.workflow, title=task.title, branch=task.branch,
                    merge_commit_shas=[m.merge_commit_sha for m in pending]))

        self.store.add(release, check)
        if start:
            return await self.start(release.id)
        return release

    # ----- state transitions

    async def start(self, release_id: str) -> Release:
        def begin(release: Release) -> None:
            if release.status != ReleaseStatus.draft:
                raise ReleaseError(f"Release is {release.status.value}; only a draft can be started")
            self._reset_run(release)
            release.status = ReleaseStatus.preparing

        release = self.store.update(release_id, begin)
        self._spawn(release_id, self._prepare(release_id))
        return release

    @staticmethod
    def _reset_run(release: Release) -> None:
        release.error, release.failed_phase = "", ""
        release.validation, release.validation_warning = [], ""
        release.final_commit_sha, release.base_sha = "", ""
        release.approved_at, release.approved_by = None, ""
        for task in release.tasks:
            task.picks = []

    def approve(self, release_id: str, approved_by: str = "admin") -> Release:
        """The human release approval. Only a validated release waiting for approval can be approved."""
        def mark(release: Release) -> None:
            if release.status != ReleaseStatus.waiting_approval:
                raise ReleaseError(f"Release is {release.status.value}; only a release waiting for approval can be approved")
            release.status = ReleaseStatus.approved
            release.approved_by, release.approved_at = approved_by or "admin", now()

        release = self.store.update(release_id, mark)
        self._spawn(release_id, self._merge(release_id))
        return release

    def retry(self, release_id: str) -> Release:
        """Retry a failed release. A failure while merging returns to `waiting_approval` (the validated branch is
        intact, a fresh approval is needed); any other failure rebuilds the release branch from the current sandbox."""
        def reopen(release: Release) -> None:
            if release.status != ReleaseStatus.failed:
                raise ReleaseError(f"Release is {release.status.value}; only a failed release can be retried")
            if release.failed_phase == "merging" and release.final_commit_sha:
                release.status = ReleaseStatus.waiting_approval
                release.error, release.failed_phase = "", ""
                release.approved_at, release.approved_by = None, ""
            else:
                self._reset_run(release)
                release.status = ReleaseStatus.preparing

        release = self.store.update(release_id, reopen)
        if release.status == ReleaseStatus.preparing:
            self._spawn(release_id, self._prepare(release_id))
        return release

    def rebuild(self, release_id: str) -> Release:
        """Rebuild a failed/waiting release from the current sandbox (e.g. after sandbox moved)."""
        def reopen(release: Release) -> None:
            if release.status not in (ReleaseStatus.failed, ReleaseStatus.waiting_approval):
                raise ReleaseError(f"Release is {release.status.value}; it cannot be rebuilt now")
            self._reset_run(release)
            release.status = ReleaseStatus.preparing

        release = self.store.update(release_id, reopen)
        self._spawn(release_id, self._prepare(release_id))
        return release

    def cancel(self, release_id: str) -> Release:
        def stop(release: Release) -> None:
            if release.status in RUNNING:
                raise ReleaseError(f"Release is {release.status.value}; wait until the current step has finished")
            if release.status in (ReleaseStatus.released, ReleaseStatus.cancelled):
                raise ReleaseError(f"Release is already {release.status.value}")
            release.status = ReleaseStatus.cancelled
            release.logs.append("Cancelled by the administrator; the release branch (if any) was kept")

        return self.store.update(release_id, stop)

    # ----- background work

    def _spawn(self, release_id: str, coroutine) -> None:
        job = asyncio.get_running_loop().create_task(coroutine)
        self._jobs[release_id] = job
        job.add_done_callback(lambda done, key=release_id: self._jobs.get(key) is done and self._jobs.pop(key, None))

    async def wait(self, release_id: str | None = None) -> None:
        """Wait for background work (tests, graceful shutdown)."""
        jobs = [self._jobs[release_id]] if release_id and release_id in self._jobs else list(self._jobs.values())
        if jobs:
            await asyncio.gather(*jobs, return_exceptions=True)

    def _fail(self, release_id: str, phase: str, message: str, log: list[str] | None = None) -> None:
        def mark(release: Release) -> None:
            release.status, release.failed_phase, release.error = ReleaseStatus.failed, phase, message[:4000]
            release.logs.extend((log or [])[-80:])
            release.logs.append(f"FAILED during {phase}: {message[:500]}")

        try:
            self.store.update(release_id, mark)
        except ReleaseError:
            pass

    def _repo(self, release: Release) -> GitRepo:
        return GitRepo(Path(release.repository_path), self.token_provider(release.repository_path))

    async def _prepare(self, release_id: str) -> None:
        release = self.store.get(release_id)
        if release is None:
            return
        repo = self._repo(release)
        phase = "preparing"
        try:
            # The project's validation commands are re-read on every (re)build, so fixing the project config and
            # retrying picks the fix up.
            plan = await self.plan_provider(release.repository_path, [task.task_id for task in release.tasks])
            release = self.store.update(release_id, lambda r: setattr(r, "validation_plan", plan))
            await self._build_branch(release, repo)
            phase = "testing"
            self.store.update(release_id, lambda r: setattr(r, "status", ReleaseStatus.testing))
            await self._validate(release_id, repo)
        except asyncio.CancelledError:
            self._fail(release_id, phase, "Interrupted before it finished; retry to rebuild", repo.log)
            raise
        except (GitFlowError, ReleaseError) as exc:
            self._fail(release_id, phase, str(exc), repo.log)
        except Exception as exc:  # never leave a release stuck in a running state
            self._fail(release_id, phase, f"Unexpected error: {exc}", repo.log)

    async def _build_branch(self, release: Release, repo: GitRepo) -> None:
        branch = release.release_branch
        shas = [sha for task in release.tasks for sha in task.merge_commit_shas]
        owner = {sha: task for task in release.tasks for sha in task.merge_commit_shas}
        async with repo_lock(repo.root, f"prepare release {release.version}"):
            await repo.fetch()
            sandbox = await sandbox_ref(repo)
            base_sha = await repo.rev(sandbox) or ""
            develop_sha = await ensure_develop(repo)
            expected_files: set[str] = set()
            for sha in shas:
                if not await repo.is_ancestor(sha, develop_sha):
                    raise ReleaseError(f"{owner[sha].task_id}: merge commit {sha[:10]} is not in `{DEVELOP}`; its changes cannot be isolated")
                parents = (await repo.out("rev-list", "--parents", "-n", "1", sha)).split()
                if len(parents) != 3:
                    raise ReleaseError(f"{owner[sha].task_id}: {sha[:10]} is not a merge commit created by the final approval; "
                                       "its changes cannot be isolated reliably")
                _, names = await repo.run("diff", "--name-only", parents[1], sha)
                expected_files.update(line.strip() for line in names.splitlines() if line.strip())
            if await repo.rev(f"refs/remotes/origin/{branch}"):
                raise ReleaseError(f"`{branch}` already exists on origin; choose another version")
            order = await order_commits(repo, shas, develop_sha)
            temp = Path(tempfile.mkdtemp(prefix="taskloom-release-"))
            shutil.rmtree(temp, ignore_errors=True)
            # -B: (re)create the branch at sandbox. Only a never-published local branch of an earlier failed attempt
            # can exist here (origin was checked above), so nothing that anyone else has seen is rewritten.
            await repo.run("worktree", "add", "-B", branch, str(temp), base_sha, check=True)
            try:
                picks: dict[str, dict] = {}
                for sha in order:
                    code, output = await repo.run("cherry-pick", "-x", "-m", "1", "--keep-redundant-commits", sha, cwd=temp, identity=True)
                    if code:
                        _, unmerged = await repo.run("diff", "--name-only", "--diff-filter=U", cwd=temp)
                        files = [line.strip() for line in unmerged.splitlines() if line.strip()]
                        await repo.run("cherry-pick", "--abort", cwd=temp)
                        if files:
                            raise MergeConflictError(f"{owner[sha].task_id} conflicts with `{SANDBOX}` or the other selected tasks in: "
                                                     + ", ".join(files), files)
                        raise GitFlowError(f"Applying {owner[sha].task_id} ({sha[:10]}) failed: {output.strip()[:400]}")
                    picked = await repo.out("rev-parse", "HEAD", cwd=temp)
                    _, changed = await repo.run("diff-tree", "--no-commit-id", "--name-only", "-r", picked, cwd=temp)
                    picks[sha] = {"merge_commit_sha": sha, "picked_commit_sha": picked,
                                  "files": [line.strip() for line in changed.splitlines() if line.strip()]}
                head = await repo.out("rev-parse", "HEAD", cwd=temp)
                _, diff_names = await repo.run("diff", "--name-only", base_sha, head, cwd=temp)
                released_files = {line.strip() for line in diff_names.splitlines() if line.strip()}
                unrelated = sorted(released_files - expected_files)
                if unrelated:
                    raise ReleaseError("The release would contain changes that do not belong to the selected tasks ("
                                       + ", ".join(unrelated[:10]) + "); stopped instead of including them")
            finally:
                await remove_worktree(repo, temp)

        def record(stored: Release) -> None:
            stored.base_sha, stored.final_commit_sha = base_sha, head
            for task in stored.tasks:
                task.picks = [picks[sha] for sha in task.merge_commit_shas if sha in picks]
            stored.logs.append(f"Built {branch} from {sandbox} ({base_sha[:10]}): {len(order)} task change set(s), "
                               f"{len(released_files)} file(s), head {head[:10]}")
            stored.logs.extend(repo.log[-40:])

        self.store.update(release.id, record)

    async def _validate(self, release_id: str, repo: GitRepo) -> None:
        release = self.store.get(release_id)
        plan = release.validation_plan
        if not plan:
            warning = ("No validation command is configured for this repository, so nothing was tested. "
                       "Configure test commands on the project before relying on this release.")
            self.store.update(release_id, lambda r: (setattr(r, "validation_warning", warning), setattr(r, "status", ReleaseStatus.waiting_approval)))
            return
        async with repo_lock(repo.root, f"open worktree for release {release.version}"):
            temp = Path(tempfile.mkdtemp(prefix="taskloom-validate-"))
            shutil.rmtree(temp, ignore_errors=True)
            await repo.run("worktree", "add", "--detach", str(temp), release.final_commit_sha, check=True)
        results: list[ValidationResult] = []
        try:
            for step in plan:
                result = await self._run_step(step, temp)
                results.append(result)
                if not result.passed:
                    break
        finally:
            async with repo_lock(repo.root, f"close worktree for release {release.version}"):
                await remove_worktree(repo, temp)
        failed = next((r for r in results if not r.passed), None)

        def record(stored: Release) -> None:
            stored.validation = results
            if failed:
                stored.status, stored.failed_phase = ReleaseStatus.failed, "testing"
                stored.error = f"Validation failed: `{failed.command}` " + (failed.message or f"exited with code {failed.exit_code}")
            else:
                stored.status = ReleaseStatus.waiting_approval

        self.store.update(release_id, record)

    async def _run_step(self, step: dict, worktree: Path) -> ValidationResult:
        command_text = str(step.get("command", "")).strip()
        relative = str(step.get("working_directory", "") or "")
        result = ValidationResult(kind=step.get("kind", "test"), command=command_text, working_directory=relative)
        started = time.monotonic()
        try:
            cwd = services.test_working_directory(worktree, relative or None)
            code, output = await services.command(services.split_command(command_text), cwd, self.validation_timeout)
            result.exit_code, result.passed, result.output = code, code == 0, output[-6000:]
        except (ValueError, OSError) as exc:
            result.message, result.output = str(exc), str(exc)
        result.duration_seconds = round(time.monotonic() - started, 2)
        return result

    async def _merge(self, release_id: str) -> None:
        repo: GitRepo | None = None
        try:
            def begin(release: Release) -> None:
                if release.status != ReleaseStatus.approved:
                    raise ReleaseError(f"Release is {release.status.value}, not approved")
                release.status = ReleaseStatus.merging

            release = self.store.update(release_id, begin)
            repo = self._repo(release)
            merge_sha = await self._merge_into_sandbox(release, repo)
        except asyncio.CancelledError:
            self._fail(release_id, "merging", "Interrupted while merging; check the repository, then retry", repo.log if repo else None)
            raise
        except (GitFlowError, ReleaseError) as exc:
            self._fail(release_id, "merging", str(exc), repo.log if repo else None)
            return
        except Exception as exc:
            self._fail(release_id, "merging", f"Unexpected error: {exc}", repo.log if repo else None)
            return

        def done(stored: Release) -> None:
            stored.status, stored.merge_commit_sha, stored.released_at = ReleaseStatus.released, merge_sha, now()
            stored.error, stored.failed_phase = "", ""
            stored.logs.extend(repo.log[-40:])
            stored.logs.append(f"Released {stored.version}: merge commit {merge_sha[:10]} on {SANDBOX}")

        self.store.update(release_id, done)

    async def _merge_into_sandbox(self, release: Release, repo: GitRepo) -> str:
        branch = release.release_branch
        ids = ", ".join(task.task_id for task in release.tasks)
        async with repo_lock(repo.root, f"merge release {release.version} into {SANDBOX}"):
            await repo.fetch()
            head = await repo.rev(f"refs/heads/{branch}")
            if head is None or head != release.final_commit_sha:
                raise GitFlowError(f"`{branch}` is missing or changed since it was validated; rebuild the release")
            sandbox_sha = await ensure_sandbox(repo)
            if sandbox_sha != release.base_sha:
                raise GitFlowError(f"`{SANDBOX}` moved since this release was built ({release.base_sha[:10]} -> {sandbox_sha[:10]}); "
                                   "rebuild the release on the new sandbox so what was tested is what is merged")
            async with branch_workspace(repo, SANDBOX) as workspace:
                before = await repo.out("rev-parse", "HEAD", cwd=workspace)
                code, output = await repo.run("merge", "--no-ff", "--no-edit", "-m", f"Release {release.version}: {ids}", branch,
                                              cwd=workspace, identity=True)
                if code:
                    _, unmerged = await repo.run("diff", "--name-only", "--diff-filter=U", cwd=workspace)
                    files = [line.strip() for line in unmerged.splitlines() if line.strip()]
                    await repo.run("merge", "--abort", cwd=workspace)
                    raise MergeConflictError(f"Merging `{branch}` into `{SANDBOX}` failed"
                                             + (": conflicts in " + ", ".join(files) if files else ": " + output.strip()[:300])
                                             + f". `{SANDBOX}` was not changed.", files)
                after = await repo.out("rev-parse", "HEAD", cwd=workspace)
                try:
                    await repo.push(SANDBOX)
                except GitFlowError:
                    await repo.run("reset", "--hard", before, cwd=workspace)  # undo only the merge made a moment ago
                    raise
            confirmed = await repo.rev(f"refs/heads/{SANDBOX}")
            parents = (await repo.out("rev-list", "--parents", "-n", "1", after)).split()
            if confirmed != after or len(parents) != 3 or parents[2] != head:
                raise GitFlowError("Git did not confirm the merge into sandbox")
            try:  # reviewers get the branch too; the release is already merged, so a failure here is only a warning
                await repo.push(branch)
                self.store.update(release.id, lambda r: setattr(r, "branch_pushed", True))
            except GitFlowError as exc:
                repo.log.append(f"WARNING: release branch was not pushed: {exc}")
            return after

    # ----- recovery

    async def recover_interrupted(self) -> list[str]:
        """After a server restart: nothing is running any more. Preparing/testing releases fail with a retry option;
        approved/merging ones are reconciled with what Git actually says."""
        changed = []
        for release in self.store.list():
            if release.status in (ReleaseStatus.preparing, ReleaseStatus.testing):
                self._fail(release.id, release.status.value, "Interrupted by a server restart; retry to rebuild the release")
                changed.append(release.id)
            elif release.status in (ReleaseStatus.approved, ReleaseStatus.merging):
                changed.append(release.id)
                await self._reconcile(release)
        return changed

    async def _reconcile(self, release: Release) -> None:
        repo = self._repo(release)
        try:
            async with repo_lock(repo.root, "reconcile release"):
                sandbox = await repo.rev(f"refs/heads/{SANDBOX}")
                merged = bool(release.final_commit_sha and sandbox and await repo.is_ancestor(release.final_commit_sha, sandbox))
                published = True
                if merged and await repo.has_origin():
                    published = bool(await repo.rev(f"refs/remotes/origin/{SANDBOX}")) and \
                        await repo.is_ancestor(release.final_commit_sha, f"refs/remotes/origin/{SANDBOX}")
                merge_sha = await find_merge_commit(repo, release.final_commit_sha, sandbox) if merged and published else ""
        except (GitFlowError, OSError) as exc:
            self._fail(release.id, "merging", f"Interrupted while merging and Git could not be checked: {exc}")
            return
        if merge_sha:
            def done(stored: Release) -> None:
                stored.status, stored.merge_commit_sha, stored.released_at = ReleaseStatus.released, merge_sha, now()
                stored.error, stored.failed_phase = "", ""
                stored.logs.append("Recovered after restart: Git shows the merge into sandbox was completed and published")
            self.store.update(release.id, done)
        else:
            self._fail(release.id, "merging", "Interrupted while merging; Git does not show a published merge into sandbox. "
                       "Retry returns the release to approval.")

