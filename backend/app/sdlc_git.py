"""Git branches and GitHub publishing for SDLC tasks.

Every SDLC task works on its own branch, ``sdlc/<task-id>``, in each Git repository its stages
touch. Commit, push and pull-request creation are explicit human actions from the dashboard.
GitHub tokens are used per request and never written to disk or to a Git remote.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from .git_flow import (  # noqa: F401  (auth_args / redact_auth are re-exported for existing callers)
    DEVELOP, SANDBOX, GitRepo, assert_not_protected, auth_args, create_task_branch, redact_auth, task_branch_name,
)
from .models import SDLCTask, TaskRepo
from .services import command, task_branch_preflight

GITHUB_API = "https://api.github.com"
_GITHUB_URL = re.compile(r"^(?:https://(?:[^@/]+@)?github\.com/|git@github\.com:)([^/\s]+)/([^/\s]+?)(?:\.git)?/?$")


class GitHubError(RuntimeError):
    pass


def task_branch(task: SDLCTask) -> str:
    """The task's branch: its identifier (SDLC-1001). Tasks created by older versions keep the branch
    recorded in `task.repos` (see prepare_task_branch)."""
    return task_branch_name(task.base_task.task_id)


async def git_root(path: Path) -> Path | None:
    """Return the repository root containing `path`, or None when it is not inside a Git repository."""
    code, output = await command(["git", "rev-parse", "--show-toplevel"], path)
    return Path(output.strip()).resolve() if code == 0 and output.strip() else None


async def prepare_task_branch(task: SDLCTask, workdir: Path, base_branch: str = SANDBOX,
                              token: str | None = None, auto_stash: bool = False) -> TaskRepo | None:
    """Put the repository containing `workdir` on the task's branch, creating it from the latest `sandbox` once.

    `base_branch` is accepted for compatibility and ignored: every task branch starts from `sandbox`, and a
    missing `sandbox` is an error (SandboxMissingError), never a silent fallback to develop/main/HEAD.
    Raises RuntimeError when the repository has uncommitted changes on another branch, so work from
    different tasks (or from the user) is never mixed into one branch.
    """
    root = await git_root(workdir)
    if root is None:
        return None
    key = str(root)
    recorded = task.repos.get(key)
    branch = recorded.branch if recorded else task_branch(task)
    if auto_stash:
        await stash_leftovers(task, root, branch)
    current, _ = await task_branch_preflight(root, branch, confirmed_dirty_worktree=True)
    repo = GitRepo(root, token)
    info = await create_task_branch(repo, task.base_task.task_id, branch if recorded else None)
    if info.created:
        task.base_task.logs.append(f"Created `{branch}` from the latest `{SANDBOX}` ({info.base_sha[:10]})")
    if current != branch:
        code, output = await command(["git", "switch", branch], root)
        if code:
            raise RuntimeError(output.strip() or f"Could not switch {root} to {branch}")
    if recorded is None:
        recorded = TaskRepo(path=key, branch=branch, base_branch=SANDBOX, base_commit_sha=info.base_sha)
        task.repos[key] = recorded
    return recorded


async def stash_leftovers(task: SDLCTask, root: Path, branch: str) -> None:
    """In a Taskloom-managed clone, set aside uncommitted leftovers (e.g. a lockfile rewritten by `npm install`)
    instead of failing: the task starts from a clean tree and the stash stays recoverable with `git stash list`."""
    code, current = await command(["git", "branch", "--show-current"], root)
    code2, status = await command(["git", "status", "--porcelain"], root)
    if code or code2 or current.strip() == branch or not status.strip():
        return
    code, output = await command(["git", "stash", "push", "--include-untracked", "-m",
                                  f"taskloom: auto-stash before {branch}"], root)
    if code:
        raise RuntimeError("Could not set aside uncommitted changes: " + output.strip())
    task.base_task.logs.append(f"Set aside uncommitted changes on `{current.strip() or 'detached HEAD'}` "
                               f"({len(status.strip().splitlines())} file(s)) with git stash before starting `{branch}`")


async def has_remote(root: Path, name: str) -> bool:
    code, output = await command(["git", "remote"], root)
    return code == 0 and name in output.split()


async def fetch_origin(root: Path, token: str | None) -> None:
    code, output = await command(["git", *auth_args(token), "fetch", "--prune", "origin"], root, 300)
    if code:
        raise RuntimeError("git fetch failed: " + redact_auth(output.strip(), token))


def clean_github_url(repo_url: str) -> str:
    owner, name = parse_github_url(repo_url)
    return f"https://github.com/{owner}/{name}.git"


def safe_repo_name(text: str) -> str:
    """A GitHub-valid repository name made from free text."""
    return re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-.") or "repo"


async def commit_with_fallback(path: Path, message: str, allow_empty: bool = False) -> tuple[int, str]:
    """git commit that never needs a human: falls back to a Taskloom identity when git has none."""
    tail = ["commit", "-q", *(["--allow-empty"] if allow_empty else []), "-m", message]
    code, output = await command(["git", *tail], path)
    lowered = output.lower()
    if code and ("identity" in lowered or "tell me who you are" in lowered):
        code, output = await command(["git", "-c", "user.name=Taskloom", "-c", "user.email=taskloom@localhost", *tail], path)
    return code, output


async def heal_local_repository(path: Path, project, stage: str, base: str) -> None:
    """Make a from-scratch repository usable without any manual git step.

    * no commits yet  -> create the initial commit (README when the folder is empty, else everything in it)
    * base branch missing (e.g. `sandbox`) -> create it at the current commit
    """
    code, _ = await command(["git", "rev-parse", "--verify", "--quiet", "HEAD^{commit}"], path)
    if code:  # unborn branch
        if not any(child.name != ".git" for child in path.iterdir()):
            (path / "README.md").write_text(f"# {project.name} — {stage}\n\n{project.description}\n", encoding="utf-8")
        await command(["git", "add", "-A"], path)
        code, output = await commit_with_fallback(path, "Initial commit")
        if code:  # e.g. everything in the folder is git-ignored: still give the base branch a commit
            code, output = await commit_with_fallback(path, "Initial commit", allow_empty=True)
        if code:
            raise RuntimeError("Initial commit failed: " + output.strip())
    for name in dict.fromkeys([base, SANDBOX]):  # a from-scratch repository also gets the fixed task base
        code, _ = await command(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{name}"], path)
        if code:
            code, output = await command(["git", "branch", name], path)
            if code:
                raise RuntimeError(f"Could not create the base branch `{name}`: {output.strip()}")


async def ensure_workspace(project, stage: str, token: str | None, persist=None, log=None) -> Path:
    """Make sure the stage's repository exists locally before the stage runs.

    existing: clone `repository.url` into the workspace once (later tasks fetch it).
    create:   fully automatic: init the repo, give it an initial commit and its base branch, pick a name when
              none was set, and create the private GitHub repo when a token is available. The name/URL that
              were decided are written back to the project (`persist`) so the forms show them.
    """
    repository = project.stage_repository(stage)
    path = Path(project.stage_path(stage)).expanduser()
    token = resolve_token(token)
    is_repo = (path / ".git").exists()
    note = log or (lambda message: None)

    if repository.mode.value == "existing":
        if not repository.url:
            raise RuntimeError(f"Stage {stage} uses an existing repository but its URL is empty")
        clean = clean_github_url(repository.url)
        if not is_repo:
            if path.exists() and any(path.iterdir()):
                raise RuntimeError(f"{path} is not empty and is not a Git repository; choose an empty folder for the clone")
            path.parent.mkdir(parents=True, exist_ok=True)
            code, output = await command(["git", *auth_args(token), "clone", clean, str(path)], path.parent, 1800)
            if code:
                raise RuntimeError("git clone failed: " + redact_auth(output.strip(), token))
        else:
            code, origin = await command(["git", "remote", "get-url", "origin"], path)
            if code or parse_github_url(origin.strip()) != parse_github_url(repository.url):
                raise RuntimeError(f"{path} is a Git repository whose origin is not {repository.url}")
        return path

    if repository.mode.value == "create":
        changed = False
        base = repository.default_branch or "main"
        if not repository.default_branch:
            repository.default_branch, changed = base, True
        if not is_repo:
            path.mkdir(parents=True, exist_ok=True)
            code, output = await command(["git", "init", "-q", "-b", base], path)
            if code:
                raise RuntimeError(output.strip() or "git init failed")
        await heal_local_repository(path, project, stage, base)
        if not repository.name.strip():
            repository.name, changed = safe_repo_name(project.stage_repo_name(stage)), True
            note(f"Repository name was empty; using `{repository.name}`")
        if repository.url and not await has_remote(path, "origin"):
            await command(["git", "remote", "add", "origin", clean_github_url(repository.url)], path)
        if not repository.url:
            if token:
                try:
                    repository.url = await create_github_repository(project, stage, token, allow_rename=True)
                    changed = True
                    note(f"Created GitHub repository {repository.url}")
                except GitHubError as exc:
                    note(f"GitHub repository was not created (the work stays local): {exc}")
            else:
                note("No GitHub token: the repository stays local until a token is saved")
        if changed and persist:
            persist(project)
        return path

    if repository.url and (path / ".git").exists() and not await has_remote(path, "origin"):
        await command(["git", "remote", "add", "origin", clean_github_url(repository.url)], path)
    return path


async def describe_new_repository(project, stage: str, token: str | None) -> dict:
    """Validate a token before the project's repository exists: who will own the new repo."""
    token = resolve_token(token)
    if not token:
        raise GitHubError("A GitHub token is required (save one in the project, or set GITHUB_TOKEN)")
    status, user = await github_api("GET", "/user", token)
    if status != 200:
        raise GitHubError("The GitHub token is invalid or expired" if status == 401 else _github_message(status, user))
    return {"status": "valid", "owner": user["login"], "repo": project.stage_repo_name(stage), "will_create": True,
            "private": project.stage_repository(stage).private}


async def create_github_repository(project, stage: str, token: str | None, allow_rename: bool = False) -> str:
    """Create the stage's private repo under the token's account, push the base branch, return its URL.

    With `allow_rename` a name that is already taken gets -2, -3 ... appended; the final name is stored
    in the stage's repository config."""
    token = resolve_token(token)
    if not token:
        raise GitHubError("A GitHub token is required to create the repository (save one in the project, or set GITHUB_TOKEN)")
    repository = project.stage_repository(stage)
    wanted = safe_repo_name(project.stage_repo_name(stage))
    status, user = await github_api("GET", "/user", token)
    if status != 200:
        raise GitHubError("The GitHub token is invalid or expired" if status == 401 else _github_message(status, user))
    owner = user["login"]
    name, payload = wanted, {}
    for attempt in range(1, 6 if allow_rename else 2):
        name = wanted if attempt == 1 else f"{wanted}-{attempt}"
        status, payload = await github_api("POST", "/user/repos", token, {
            "name": name, "private": repository.private, "auto_init": False,
            "description": f"{project.name} — {stage} (managed by Taskloom SDLC)"[:350],
        })
        if not (status == 422 and "already exists" in json.dumps(payload)):
            break
    if status == 422 and "already exists" in json.dumps(payload):
        raise GitHubError(f"{owner}/{name} already exists on GitHub. Use it as the {stage} stage's existing "
                          "repository, or set a different repository name.")
    if status != 201:
        raise GitHubError(_github_message(status, payload))
    repository.name = name
    url = payload["html_url"]
    root = Path(project.stage_path(stage))
    if await has_remote(root, "origin"):
        await command(["git", "remote", "set-url", "origin", clean_github_url(url)], root)
    else:
        await command(["git", "remote", "add", "origin", clean_github_url(url)], root)
    base = repository.default_branch or "main"
    for name in dict.fromkeys([base, SANDBOX]):
        code, output = await command(["git", *auth_args(token), "push", "origin", f"refs/heads/{name}:refs/heads/{name}"], root, 300)
        if code:
            raise GitHubError(f"Created {url}, but pushing `{name}` failed: " + redact_auth(output.strip(), token))
    return url


def redact(text: str, token: str | None) -> str:
    return text.replace(token, "***") if token else text


def parse_github_url(repo_url: str) -> tuple[str, str]:
    match = _GITHUB_URL.match(repo_url.strip())
    if not match:
        raise GitHubError("Repository URL must look like https://github.com/<owner>/<repo>")
    return match.group(1), match.group(2)


def resolve_token(token: str | None) -> str:
    return (token or "").strip() or os.environ.get("GITHUB_TOKEN", "").strip()


def push_url(repo_url: str, token: str) -> str:
    """Authenticated HTTPS URL for a single push; non-GitHub URLs (e.g. a local remote) pass through."""
    try:
        owner, repo = parse_github_url(repo_url)
    except GitHubError:
        return repo_url
    if not token:
        raise GitHubError("A GitHub token is required to push (send it, or set GITHUB_TOKEN)")
    return f"https://x-access-token:{token}@github.com/{owner}/{repo}.git"


def _github_request(method: str, path: str, token: str, body: dict | None = None) -> tuple[int, dict | list]:
    request = urllib.request.Request(
        GITHUB_API + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "taskloom",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read() or b"{}")
        except json.JSONDecodeError:
            payload = {}
        return exc.code, payload
    except urllib.error.URLError as exc:
        raise GitHubError(f"Could not reach GitHub: {exc.reason}") from exc


async def github_api(method: str, path: str, token: str, body: dict | None = None) -> tuple[int, dict | list]:
    return await asyncio.to_thread(_github_request, method, path, token, body)


def _github_message(status: int, payload) -> str:
    message = payload.get("message", "") if isinstance(payload, dict) else ""
    errors = payload.get("errors", []) if isinstance(payload, dict) else []
    details = "; ".join(str(error.get("message", error)) if isinstance(error, dict) else str(error) for error in errors)
    return f"GitHub returned {status}: {message}" + (f" ({details})" if details else "")


async def validate_repository(repo_url: str, token: str | None) -> dict:
    owner, repo = parse_github_url(repo_url)
    token = resolve_token(token)
    if not token:
        raise GitHubError("A GitHub token is required (send it, or set GITHUB_TOKEN)")
    status, payload = await github_api("GET", f"/repos/{owner}/{repo}", token)
    if status == 401:
        raise GitHubError("The GitHub token is invalid or expired")
    if status == 404:
        raise GitHubError(f"{owner}/{repo} was not found, or the token cannot access it")
    if status != 200:
        raise GitHubError(_github_message(status, payload))
    permissions = payload.get("permissions", {}) if isinstance(payload, dict) else {}
    return {
        "status": "valid",
        "owner": owner,
        "repo": repo,
        "default_branch": payload.get("default_branch", ""),
        "can_push": bool(permissions.get("push")),
    }


def commit_message(task: SDLCTask) -> str:
    lines = [f"feat({task.base_task.task_id}): {task.title}"[:120], ""]
    if task.description:
        lines += [task.description.strip(), ""]
    lines += [f"- {stage}: {result.summary.strip().splitlines()[0][:200]}" for stage, result in task.agent_results.items() if result.summary.strip()]
    lines += ["", "Generated by the Taskloom SDLC pipeline."]
    return "\n".join(lines).strip() + "\n"


async def commit_and_push(task: SDLCTask, repo: TaskRepo, repo_url: str, token: str | None) -> dict:
    """Commit everything on the task branch and push it to `repo_url`."""
    root = Path(repo.path)
    token = resolve_token(token)
    assert_not_protected(repo.branch)
    code, current = await command(["git", "branch", "--show-current"], root)
    if code or current.strip() != repo.branch:
        raise GitHubError(f"{root} is on `{current.strip() or 'detached HEAD'}`, not the task branch `{repo.branch}`")

    code, output = await command(["git", "add", "-A"], root)
    if code:
        raise GitHubError(output.strip() or "git add failed")
    code, _ = await command(["git", "diff", "--cached", "--quiet"], root)
    committed = False
    if code:  # something is staged
        code, output = await command(["git", "commit", "-q", "-F", "-"], root, stdin_text=commit_message(task))
        if code:
            raise GitHubError(output.strip() or "git commit failed")
        committed = True
    code, sha = await command(["git", "rev-parse", "HEAD"], root)
    repo.commit_sha = sha.strip()

    target = push_url(repo_url, token)
    code, output = await command(["git", "push", target, f"HEAD:refs/heads/{repo.branch}"], root, 300)
    if code:
        raise GitHubError("git push failed: " + redact(output.strip(), token))
    repo.pushed = True
    return {
        "message": "Committed and pushed" if committed else "Nothing new to commit; pushed the branch",
        "commit_sha": repo.commit_sha,
        "branch": repo.branch,
    }


def pull_request_body(task: SDLCTask) -> str:
    parts = [f"## {task.title}", task.description.strip() or "_No description._", "", "## Stages"]
    for stage, result in task.agent_results.items():
        tests = ""
        if result.tests.executed:
            tests = " — tests passed" if result.tests.passed else " — **tests failed**"
        parts.append(f"### {stage} ({result.status}){tests}\n{result.summary.strip()}")
        if result.changes:
            parts.append("Changed: " + ", ".join(f"`{change.file}`" for change in result.changes[:30]))
        if result.issues:
            parts.append("Open issues:\n" + "\n".join(f"- {issue}" for issue in result.issues[:10]))
    if task.revision_count:
        parts.append(f"\nRevisions during the run: {task.revision_count}")
    parts.append(f"\n_Task `{task.base_task.task_id}` — generated by the Taskloom SDLC pipeline; review before merging._")
    return "\n\n".join(parts)


async def create_pull_request(task: SDLCTask, repo: TaskRepo, repo_url: str, token: str | None,
                              title: str | None = None, body: str | None = None) -> dict:
    owner, name = parse_github_url(repo_url)
    token = resolve_token(token)
    if not token:
        raise GitHubError("A GitHub token is required (send it, or set GITHUB_TOKEN)")
    if not repo.pushed:
        raise GitHubError(f"Push `{repo.branch}` before opening a pull request")
    status, payload = await github_api("POST", f"/repos/{owner}/{name}/pulls", token, {
        "title": (title or f"{task.title} ({task.base_task.task_id})")[:250],
        "head": repo.branch,
        "base": DEVELOP,  # never sandbox: sandbox only receives validated releases
        "body": body or pull_request_body(task),
    })
    if status == 422 and "already exists" in json.dumps(payload):
        status, existing = await github_api("GET", f"/repos/{owner}/{name}/pulls?head={owner}:{repo.branch}&state=open", token)
        if status == 200 and isinstance(existing, list) and existing:
            payload, message = existing[0], "A pull request for this branch already exists"
        else:
            raise GitHubError(_github_message(422, payload))
    elif status != 201:
        raise GitHubError(_github_message(status, payload))
    else:
        message = "Pull request created"
    repo.pr_number = payload.get("number")
    repo.pr_url = payload.get("html_url", "")
    return {"message": message, "pr_number": repo.pr_number, "pr_url": repo.pr_url}
