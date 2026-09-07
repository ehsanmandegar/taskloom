import asyncio
import os
import shlex
import shutil
from pathlib import Path

from .models import RunStatus, TaskRequest, TaskState


async def command(args: list[str], cwd: Path, timeout: int = 900) -> tuple[int, str]:
    process = await asyncio.create_subprocess_exec(*args, cwd=str(cwd), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, env=os.environ.copy())
    try:
        output, _ = await asyncio.wait_for(process.communicate(), timeout)
    except asyncio.TimeoutError:
        process.kill()
        await process.communicate()
        return 124, f"Command timed out after {timeout}s"
    return process.returncode or 0, output.decode("utf-8", errors="replace")


def repository(path: str) -> Path:
    repo = Path(path).expanduser().resolve()
    if not repo.is_dir() or not (repo / ".git").exists():
        raise ValueError("Project path must be an existing Git repository")
    return repo


def resolve_guides(repo: Path, paths: list[str]) -> list[Path]:
    result = []
    for raw in paths:
        path = Path(raw).expanduser()
        path = path.resolve() if path.is_absolute() else (repo / path).resolve()
        if not path.exists():
            raise ValueError(f"Guide path does not exist: {raw}")
        result.append(path)
    return result


def detect_tests(repo: Path) -> list[str]:
    if (repo / "pytest.ini").exists() or (repo / "pyproject.toml").exists() or (repo / "tests").exists():
        return [shutil.which("pytest") or "pytest", "-q"]
    if (repo / "package.json").exists():
        return [shutil.which("npm") or "npm", "test", "--", "--run"]
    return [shutil.which("python") or "python", "-m", "pytest", "-q"]


def build_prompt(req: TaskRequest, guides: list[Path]) -> str:
    listed = "\n".join(f"- {path}" for path in guides) or "- Discover repository instructions."
    return f"""Implement task {req.task_id}.
User request: {req.request}
Instruction/documentation paths:\n{listed}
Inspect and obey repository instructions. Implement the smallest complete change. Create or update documentation only when its structure calls for it. Add meaningful pytest or project-native tests; use Locust only for performance work. Do not commit, push, switch branches, or modify files outside this repository. Finish with a concise summary and testing notes."""


async def refresh_git(state: TaskState, repo: Path) -> None:
    _, state.diff = await command(["git", "diff", "--no-ext-diff", "--"], repo)
    _, staged = await command(["git", "diff", "--cached", "--no-ext-diff", "--"], repo)
    state.diff = f"{state.diff}\n{staged}".strip()
    _, names = await command(["git", "status", "--short"], repo)
    state.changed_files = [line[3:] for line in names.splitlines() if len(line) > 3]


async def execute_task(req: TaskRequest, state: TaskState) -> None:
    try:
        repo, guides = repository(req.project_path), resolve_guides(repository(req.project_path), req.guide_paths)
        state.status, state.step = RunStatus.running, "Creating task branch"
        code, output = await command(["git", "status", "--porcelain"], repo)
        if code or output.strip():
            raise RuntimeError("Repository must be clean before starting a task")
        code, output = await command(["git", "switch", "-c", state.branch], repo)
        if code:
            raise RuntimeError(output.strip() or "Could not create branch")
        state.logs.append(f"Created {state.branch}")
        state.step = "Codex is implementing the request"
        codex = shutil.which("codex")
        if not codex:
            raise RuntimeError("Codex CLI was not found. Install it and sign in first.")
        code, output = await command([codex, "exec", "--sandbox", "workspace-write", "--color", "never", build_prompt(req, guides)], repo, 3600)
        state.logs.append(output[-12000:])
        state.summary = output.strip()[-4000:]
        await refresh_git(state, repo)
        if code:
            raise RuntimeError(f"Codex exited with code {code}")
        if not state.changed_files:
            raise RuntimeError("Codex completed without producing file changes")
        state.status, state.step = RunStatus.testing, "Running tests"
        tests = shlex.split(req.test_command, posix=False) if req.test_command else detect_tests(repo)
        code, output = await command(tests, repo, 1800)
        state.test_output = output[-20000:]
        state.commit_message = f"feat({req.task_id}): implement requested changes"
        state.status, state.step = (RunStatus.passed, "Ready for review") if code == 0 else (RunStatus.failed, "Tests failed")
        if code:
            state.error = f"Tests exited with code {code}"
        await refresh_git(state, repo)
    except Exception as exc:
        state.status, state.step, state.error = RunStatus.failed, "Run failed", str(exc)
        state.logs.append(str(exc))


async def git_commit(state: TaskState, message: str) -> str:
    repo = repository(state.project_path)
    await refresh_git(state, repo)
    if state.status != RunStatus.passed or not state.changed_files:
        raise ValueError("A successful test run with changes is required")
    code, output = await command(["git", "add", "--all"], repo)
    if code:
        raise RuntimeError(output)
    code, output = await command(["git", "commit", "-m", message], repo)
    if code:
        raise RuntimeError(output)
    state.committed, state.commit_message = True, message
    await refresh_git(state, repo)
    return output


async def git_push(state: TaskState) -> str:
    if not state.committed:
        raise ValueError("Commit the reviewed changes first")
    repo = repository(state.project_path)
    code, output = await command(["git", "push", "-u", "origin", state.branch], repo, 600)
    if code:
        raise RuntimeError(output)
    state.pushed = True
    return output
