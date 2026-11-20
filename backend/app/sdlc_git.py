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

from .models import SDLCTask, TaskRepo
from .services import base_branch_ref, command, task_branch_preflight

BRANCH_PREFIX = "sdlc/"
GITHUB_API = "https://api.github.com"
_GITHUB_URL = re.compile(r"^(?:https://(?:[^@/]+@)?github\.com/|git@github\.com:)([^/\s]+)/([^/\s]+?)(?:\.git)?/?$")


class GitHubError(RuntimeError):
    pass


def task_branch(task: SDLCTask) -> str:
    return f"{BRANCH_PREFIX}{task.base_task.task_id}"


async def git_root(path: Path) -> Path | None:
    """Return the repository root containing `path`, or None when it is not inside a Git repository."""
    code, output = await command(["git", "rev-parse", "--show-toplevel"], path)
    return Path(output.strip()).resolve() if code == 0 and output.strip() else None


async def prepare_task_branch(task: SDLCTask, workdir: Path, base_branch: str,
                              token: str | None = None) -> TaskRepo | None:
    """Put the repository containing `workdir` on the task's branch, creating it from the base once.

    When the task branch is new and the repository has an `origin`, fetch first and branch from the
    latest `origin/<base>`, so every task starts from current remote code.
    Raises RuntimeError when the repository has uncommitted changes on another branch, so work from
    different tasks (or from the user) is never mixed into one branch.
    """
    root = await git_root(workdir)
    if root is None:
        return None
    branch = task_branch(task)
    key = str(root)
    current, _ = await task_branch_preflight(root, branch, confirmed_dirty_worktree=True)
    code, _ = await command(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], root)
    branch_exists = code == 0
    if not branch_exists and await has_remote(root, "origin"):
        await fetch_origin(root, token)
    # Branch from the configured base: origin/<base> after a fetch, else local <base>, else the current branch.
    source, base = current or "HEAD", current or "main"
    if base_branch:
        remote_ref = f"refs/remotes/origin/{base_branch}"
        code, _ = await command(["git", "rev-parse", "--verify", "--quiet", f"{remote_ref}^{{commit}}"], root)
        if code == 0:
            source, base = f"origin/{base_branch}", base_branch
        else:
            try:
                source, base = await base_branch_ref(root, base_branch), base_branch
            except RuntimeError:
                pass
    if current != branch:
        args = ["git", "switch", branch] if branch_exists else ["git", "switch", "-c", branch, source]
        code, output = await command(args, root)
        if code:
            raise RuntimeError(output.strip() or f"Could not switch {root} to {branch}")
    recorded = task.repos.get(key)
    if recorded is None:
        recorded = TaskRepo(path=key, branch=branch, base_branch=base)
        task.repos[key] = recorded
    return recorded


async def has_remote(root: Path, name: str) -> bool:
    code, output = await command(["git", "remote"], root)
    return code == 0 and name in output.split()


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


async def fetch_origin(root: Path, token: str | None) -> None:
    code, output = await command(["git", *auth_args(token), "fetch", "--prune", "origin"], root, 300)
    if code:
        raise RuntimeError("git fetch failed: " + redact_auth(output.strip(), token))


def clean_github_url(repo_url: str) -> str:
    owner, name = parse_github_url(repo_url)
    return f"https://github.com/{owner}/{name}.git"


async def ensure_workspace(project, stage: str, token: str | None) -> Path:
    """Make sure the stage's repository exists locally before the stage runs.

    existing: clone `repository.url` into the workspace once (later tasks fetch it).
    create:   start a local repository with an initial commit; GitHub comes on the first push.
    """
    repository = project.stage_repository(stage)
    path = Path(project.stage_path(stage)).expanduser()
    token = resolve_token(token)
    is_repo = (path / ".git").exists()

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

    if repository.mode.value == "create" and not is_repo:
        path.mkdir(parents=True, exist_ok=True)
        branch = repository.default_branch or "main"
        code, output = await command(["git", "init", "-q", "-b", branch], path)
        if code:
            raise RuntimeError(output.strip() or "git init failed")
        if not any(child.name != ".git" for child in path.iterdir()):
            (path / "README.md").write_text(f"# {project.name} — {stage}\n\n{project.description}\n", encoding="utf-8")
        await command(["git", "add", "-A"], path)
        code, output = await command(["git", "commit", "-q", "-m", "Initial commit"], path)
        if code:
            raise RuntimeError("Initial commit failed (is git user.name/user.email configured?): " + output.strip())
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


async def create_github_repository(project, stage: str, token: str | None) -> str:
    """Create the stage's private repo under the token's account, push the base branch, return its URL."""
    token = resolve_token(token)
    if not token:
        raise GitHubError("A GitHub token is required to create the repository (save one in the project, or set GITHUB_TOKEN)")
    repository = project.stage_repository(stage)
    name = project.stage_repo_name(stage)
    status, user = await github_api("GET", "/user", token)
    if status != 200:
        raise GitHubError("The GitHub token is invalid or expired" if status == 401 else _github_message(status, user))
    owner = user["login"]
    status, payload = await github_api("POST", "/user/repos", token, {
        "name": name, "private": repository.private, "auto_init": False,
        "description": f"{project.name} — {stage} (managed by Taskloom SDLC)"[:350],
    })
    if status == 422 and "already exists" in json.dumps(payload):
        raise GitHubError(f"{owner}/{name} already exists on GitHub. Use it as the {stage} stage's existing "
                          "repository, or set a different repository name.")
    if status != 201:
        raise GitHubError(_github_message(status, payload))
    url = payload["html_url"]
    root = Path(project.stage_path(stage))
    if await has_remote(root, "origin"):
        await command(["git", "remote", "set-url", "origin", clean_github_url(url)], root)
    else:
        await command(["git", "remote", "add", "origin", clean_github_url(url)], root)
    base = repository.default_branch or "main"
    code, output = await command(["git", *auth_args(token), "push", "origin", f"refs/heads/{base}:refs/heads/{base}"], root, 300)
    if code:
        raise GitHubError(f"Created {url}, but pushing `{base}` failed: " + redact_auth(output.strip(), token))
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
        "base": repo.base_branch,
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
