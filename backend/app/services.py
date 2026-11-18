import asyncio
import codecs
from contextlib import ExitStack
from contextvars import ContextVar
from difflib import SequenceMatcher
import json
import mimetypes
import os
import queue
import re
import shlex
import shutil
import subprocess
import threading
import tempfile
import time
from xml.etree import ElementTree
from urllib.parse import urlsplit
from pathlib import Path
from typing import Callable
from zipfile import BadZipFile, ZipFile

from .models import AgentType, ChatMessage, GitProvider, McpFailureMode, McpStatus, RunStatus, TaskRequest, TaskState


_command_output_handler: ContextVar[Callable[[str], None] | None] = ContextVar("command_output_handler", default=None)
COMMIT_MESSAGE_PATTERN = re.compile(r"^(?:build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)(?:\([a-z0-9][a-z0-9._/-]*\))?!?: [A-Za-z0-9][ -~]{0,117}$")


def _command_sync(
    args: list[str],
    cwd: Path,
    timeout: int,
    env: dict[str, str] | None,
    handler: Callable[[str], None] | None,
    cancelled: threading.Event,
    stdin_text: str | None = None,
) -> tuple[int, str]:
    """Run a command without depending on the server's asyncio event-loop policy."""
    executable = args[0]
    executable_path = Path(executable).expanduser()
    if not executable_path.is_absolute() and any(separator in executable for separator in ("/", "\\")):
        executable_path = cwd / executable_path
    if executable_path.is_file():
        executable = str(executable_path.resolve())
    else:
        executable = shutil.which(executable) or executable

    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    # A file-backed stdin avoids both command-line limits and blocking pipe writes
    # before the output reader and cancellation loop have started.
    with ExitStack() as stack:
        input_file = None
        if stdin_text is not None:
            input_file = stack.enter_context(tempfile.TemporaryFile())
            input_file.write(stdin_text.encode("utf-8"))
            input_file.seek(0)
        process = subprocess.Popen(
            [executable, *args[1:]],
            cwd=str(cwd),
            stdin=input_file,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env or os.environ.copy(),
            creationflags=creationflags,
        )
    assert process.stdout is not None
    output_queue: queue.Queue[bytes | None] = queue.Queue()

    def read_output() -> None:
        try:
            while chunk := process.stdout.read(4096):
                output_queue.put(chunk)
        finally:
            output_queue.put(None)

    threading.Thread(target=read_output, name="taskloom-command-output", daemon=True).start()
    chunks: list[bytes] = []
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    deadline = time.monotonic() + timeout
    timed_out = False
    finished_output = False
    while not finished_output:
        if cancelled.is_set() or time.monotonic() >= deadline:
            timed_out = not cancelled.is_set()
            if process.poll() is None:
                process.kill()
        try:
            chunk = output_queue.get(timeout=0.1)
        except queue.Empty:
            continue
        if chunk is None:
            finished_output = True
            continue
        chunks.append(chunk)
        if handler:
            text = decoder.decode(chunk)
            if text:
                handler(text)
    process.wait()
    if handler:
        tail = decoder.decode(b"", final=True)
        if tail:
            handler(tail)
    if timed_out:
        return 124, f"Command timed out after {timeout}s"
    output = b"".join(chunks).decode("utf-8", errors="replace")
    return process.returncode or 0, output


async def command(
    args: list[str], cwd: Path, timeout: int = 900,
    env: dict[str, str] | None = None, stdin_text: str | None = None,
) -> tuple[int, str]:
    """Run a subprocess portably while preserving streaming, timeout, and cancellation."""
    cancelled = threading.Event()
    worker = asyncio.create_task(
        asyncio.to_thread(_command_sync, args, cwd, timeout, env, _command_output_handler.get(), cancelled, stdin_text)
    )
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError:
        cancelled.set()
        await asyncio.shield(worker)
        raise


def test_working_directory(repo: Path, configured: str | None) -> Path:
    """Resolve a test directory while keeping test execution inside its repository."""
    if not configured:
        return repo
    candidate = (repo / configured).resolve()
    try:
        candidate.relative_to(repo.resolve())
    except ValueError as exc:
        raise ValueError("Test working directory must be inside the project repository") from exc
    if not candidate.is_dir():
        raise ValueError(f"Test working directory does not exist: {configured}")
    return candidate


def test_plan(repo: Path, test_command: str | None, configured_working_directory: str | None) -> tuple[list[str], Path]:
    """Build the final test invocation from the selected command and directory."""
    cwd = test_working_directory(repo, configured_working_directory)
    return (shlex.split(test_command, posix=False) if test_command else detect_tests(cwd), cwd)


def codex_account_status_payload(responses: dict[int, dict]) -> dict:
    """Return the non-sensitive part of Codex App Server account responses."""
    account = responses.get(1, {}).get("account") or {}
    models = responses.get(4, {}).get("data") or []
    return {
        "account": {key: account.get(key) for key in ("type", "planType")},
        "rate_limits": responses.get(2, {}),
        "usage": responses.get(3, {}),
        "models": [
            {
                key: model.get(key)
                for key in ("id", "model", "displayName", "isDefault", "defaultReasoningEffort", "supportedReasoningEfforts")
            }
            for model in models
        ],
    }


def _codex_account_status(codex: str, timeout: int) -> dict:
    """Read App Server messages without asyncio's Windows named-pipe transport."""
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        process = subprocess.Popen(
            [codex, "app-server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=creationflags,
        )
    except OSError as exc:
        raise RuntimeError(f"Could not start Codex App Server: {exc}") from exc

    requests = [
        {"method": "initialize", "id": 0, "params": {"clientInfo": {"name": "taskloom", "title": "Taskloom", "version": "0.1.0"}}},
        {"method": "initialized", "params": {}},
        {"method": "account/read", "id": 1, "params": {"refreshToken": False}},
        {"method": "account/rateLimits/read", "id": 2},
        {"method": "account/usage/read", "id": 3},
        {"method": "model/list", "id": 4, "params": {"limit": 100, "includeHidden": False}},
    ]
    assert process.stdin is not None and process.stdout is not None
    messages: queue.Queue[str | None] = queue.Queue()
    diagnostics: list[str] = []

    def read_output() -> None:
        try:
            for line in process.stdout:
                messages.put(line)
        finally:
            messages.put(None)

    threading.Thread(target=read_output, name="taskloom-codex-status", daemon=True).start()
    deadline = time.monotonic() + timeout

    def send(request: dict) -> None:
        try:
            process.stdin.write(json.dumps(request) + "\n")
            process.stdin.flush()
        except OSError as exc:
            raise RuntimeError(f"Could not send a request to Codex App Server: {exc}") from exc

    def receive(pending: set[int]) -> dict[int, dict]:
        responses: dict[int, dict] = {}
        while pending:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError("Codex App Server timed out while reading account status")
            try:
                line = messages.get(timeout=remaining)
            except queue.Empty as exc:
                raise RuntimeError("Codex App Server timed out while reading account status") from exc
            if line is None:
                detail = f": {diagnostics[-1]}" if diagnostics else ""
                raise RuntimeError(f"Codex App Server stopped before returning account status{detail}")
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                if stripped := line.strip():
                    diagnostics.append(stripped)
                continue
            request_id = message.get("id")
            if request_id not in pending:
                continue
            if "error" in message:
                error = message["error"]
                responses[request_id] = {"error": error.get("message", "Codex request failed") if isinstance(error, dict) else str(error)}
            else:
                responses[request_id] = message.get("result", {})
            pending.remove(request_id)
        return responses

    try:
        send(requests[0])
        initialized = receive({0})[0]
        if error := initialized.get("error"):
            raise RuntimeError(f"Codex App Server initialization failed: {error}")
        for request in requests[1:]:
            send(request)
        responses = receive({1, 2, 3, 4})
        return codex_account_status_payload(responses)
    finally:
        try:
            process.stdin.close()
        except OSError:
            pass
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


async def codex_account_status(timeout: int = 20) -> dict:
    """Read the local Codex CLI account, model catalog, and usage windows."""
    codex = shutil.which("codex")
    if not codex:
        raise RuntimeError("Codex CLI was not found. Install it and sign in first.")
    return await asyncio.to_thread(_codex_account_status, codex, timeout)


async def agent_account_status(agent_type: AgentType, timeout: int = 20) -> dict:
    """Return a small, non-sensitive status payload for the selected local agent."""
    if agent_type == AgentType.codex:
        return {"agent": agent_type.value, **await codex_account_status(timeout)}
    claude = shutil.which("claude")
    if not claude:
        raise RuntimeError("Claude Code CLI was not found. Install it and sign in first.")
    code, output = await command([claude, "auth", "status"], Path.cwd(), timeout)
    if code:
        raise RuntimeError(output.strip() or "Claude Code is not signed in.")
    try:
        status = json.loads(output)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Claude Code returned an unreadable authentication status.") from exc
    if status.get("loggedIn") is not True:
        raise RuntimeError("Claude Code is not signed in. Run `claude auth login` first.")
    return {
        "agent": agent_type.value,
        "account": {
            "type": status.get("authMethod"),
            "planType": status.get("subscriptionType"),
            "apiProvider": status.get("apiProvider"),
        },
        "rate_limits": {},
        "usage": {},
        "models": [],
    }


def repository(path: str) -> Path:
    repo = Path(path).expanduser().resolve()
    if not repo.is_dir() or not (repo / ".git").exists():
        raise ValueError("Project path must be an existing Git repository")
    return repo


WORKSPACE_IGNORED_DIRECTORIES = {
    ".git", ".idea", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".venv", "venv", "node_modules", "__pycache__", "dist", "build",
}
WORKSPACE_MAX_FILE_SIZE = 1_000_000
WORKSPACE_MAX_DOCX_FILE_SIZE = 20_000_000
WORKSPACE_MAX_DOCX_XML_SIZE = 5_000_000
WORKSPACE_MAX_NODES = 4_000
WORKSPACE_IMAGE_EXTENSIONS = {
    ".avif", ".bmp", ".gif", ".ico", ".jpeg", ".jpg", ".png", ".svg", ".webp",
}
WORKSPACE_WORD_EXTENSIONS = {".docx", ".docm", ".dotx"}


def workspace_path(repo: Path, relative_path: str) -> Path:
    """Resolve a user-selected workspace path without allowing repository escape."""
    if not relative_path or Path(relative_path).is_absolute():
        raise ValueError("File path must be relative to the project")
    candidate = (repo / relative_path).resolve()
    try:
        candidate.relative_to(repo.resolve())
    except ValueError as exc:
        raise ValueError("File path must stay inside the project repository") from exc
    return candidate


def workspace_tree(repo: Path) -> list[dict]:
    """Build a bounded, editor-friendly directory tree for the project sidebar."""
    node_count = 0

    def visit(directory: Path, depth: int = 0) -> list[dict]:
        nonlocal node_count
        if depth > 18 or node_count >= WORKSPACE_MAX_NODES:
            return []
        try:
            entries = sorted(
                directory.iterdir(),
                key=lambda item: (not item.is_dir(), item.name.casefold()),
            )
        except OSError:
            return []
        nodes = []
        for entry in entries:
            if node_count >= WORKSPACE_MAX_NODES:
                break
            if entry.is_symlink() or (entry.is_dir() and entry.name in WORKSPACE_IGNORED_DIRECTORIES):
                continue
            node_count += 1
            relative = entry.relative_to(repo).as_posix()
            if entry.is_dir():
                nodes.append({"name": entry.name, "path": relative, "type": "directory", "children": visit(entry, depth + 1)})
            elif entry.is_file():
                nodes.append({"name": entry.name, "path": relative, "type": "file"})
        return nodes

    return visit(repo)


def read_workspace_text(path: Path) -> str:
    """Read a reasonably-sized text file for display in the browser editor."""
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise ValueError(f"Could not read file: {exc}") from exc
    if size > WORKSPACE_MAX_FILE_SIZE:
        raise ValueError("File is too large to preview (maximum 1 MB)")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"Could not read file: {exc}") from exc
    if b"\0" in raw[:8192]:
        raise ValueError("Binary files cannot be previewed")
    return raw.decode("utf-8", errors="replace")


def read_workspace_docx(path: Path) -> str:
    """Extract readable paragraphs from an OOXML Word document without executing embedded content."""
    try:
        if path.stat().st_size > WORKSPACE_MAX_DOCX_FILE_SIZE:
            raise ValueError("Word file is too large to preview (maximum 20 MB)")
        with ZipFile(path) as archive:
            document = archive.getinfo("word/document.xml")
            if document.file_size > WORKSPACE_MAX_DOCX_XML_SIZE:
                raise ValueError("Word document content is too large to preview")
            root = ElementTree.fromstring(archive.read(document))
    except (OSError, BadZipFile, KeyError, ElementTree.ParseError) as exc:
        raise ValueError("Word file could not be read as a DOCX document") from exc

    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    paragraphs = []
    for paragraph in root.iter(f"{namespace}p"):
        chunks = []
        for node in paragraph.iter():
            if node.tag == f"{namespace}t" and node.text:
                chunks.append(node.text)
            elif node.tag == f"{namespace}tab":
                chunks.append("\t")
            elif node.tag in {f"{namespace}br", f"{namespace}cr"}:
                chunks.append("\n")
        text = "".join(chunks).strip()
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs)


def workspace_preview_path(repo: Path, relative_path: str) -> tuple[Path, str]:
    """Return a browser-previewable image or PDF while preserving repository confinement."""
    path = workspace_path(repo, relative_path)
    if not path.is_file():
        raise ValueError("File was not found")
    suffix = path.suffix.casefold()
    if suffix not in WORKSPACE_IMAGE_EXTENSIONS and suffix != ".pdf":
        raise ValueError("This file type cannot be opened as browser media")
    media_type = mimetypes.guess_type(path.name)[0]
    if suffix == ".pdf":
        media_type = "application/pdf"
    return path, media_type or "application/octet-stream"


async def workspace_changes(repo: Path) -> list[dict]:
    """Return uncommitted paths, including staged and untracked changes."""
    code, output = await command(["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"], repo)
    if code:
        raise RuntimeError(output.strip() or "Could not read Git changes")
    records, fields, index = [], output.split("\0"), 0
    while index < len(fields) and fields[index]:
        field = fields[index]
        if len(field) < 4:
            index += 1
            continue
        status, path = field[:2], field[3:]
        previous_path = None
        if status[0] in "RC" or status[1] in "RC":
            index += 1
            if index < len(fields):
                previous_path = fields[index]
        records.append({"path": path, "previous_path": previous_path, "status": status})
        index += 1
    return records


async def workspace_file(repo: Path, relative_path: str) -> dict:
    path = workspace_path(repo, relative_path)
    if not path.is_file():
        raise ValueError("File was not found")
    normalized_path = relative_path.replace("\\", "/")
    suffix = path.suffix.casefold()
    if suffix in WORKSPACE_IMAGE_EXTENSIONS:
        return {"path": normalized_path, "kind": "image", "mime_type": mimetypes.guess_type(path.name)[0]}
    if suffix == ".pdf":
        return {"path": normalized_path, "kind": "pdf", "mime_type": "application/pdf"}
    if suffix in WORKSPACE_WORD_EXTENSIONS:
        return {"path": normalized_path, "kind": "word", "content": read_workspace_docx(path)}
    return {"path": normalized_path, "kind": "text", "content": read_workspace_text(path)}


async def workspace_diff(repo: Path, relative_path: str, previous_path: str | None = None) -> dict:
    """Return HEAD and working-tree contents for a side-by-side diff viewer."""
    path = workspace_path(repo, relative_path)
    after = read_workspace_text(path) if path.is_file() else ""
    git_path = (previous_path or relative_path).replace("\\", "/")
    # Validate renamed paths too, even though Git reads the revision rather than disk.
    workspace_path(repo, git_path)
    code, before = await command(["git", "show", f"HEAD:{git_path}"], repo, timeout=30)
    if code:
        before = ""
    if "\0" in before[:8192]:
        raise ValueError("Binary files cannot be previewed")
    if len(before.encode("utf-8")) > WORKSPACE_MAX_FILE_SIZE:
        raise ValueError("Previous file is too large to preview (maximum 1 MB)")
    # Git emits LF while Windows working-tree files are commonly CRLF. Comparing
    # logical lines avoids painting the entire file for line-ending differences.
    before_lines = before.splitlines()
    after_lines = after.splitlines()
    before_changes: list[list[int]] = []
    after_changes: list[list[int]] = []
    for tag, before_start, before_end, after_start, after_end in SequenceMatcher(
        None, before_lines, after_lines, autojunk=False
    ).get_opcodes():
        if tag in {"replace", "delete"} and before_start < before_end:
            before_changes.append([before_start, before_end])
        if tag in {"replace", "insert"} and after_start < after_end:
            after_changes.append([after_start, after_end])
    return {
        "path": relative_path.replace("\\", "/"),
        "before": before,
        "after": after,
        "before_changes": before_changes,
        "after_changes": after_changes,
    }


async def git_branches(repo: Path) -> dict:
    """List local branches and origin-only branches without changing Git state."""
    code, output = await command(["git", "for-each-ref", "--format=%(refname:short)", "refs/heads"], repo)
    if code:
        raise RuntimeError(output.strip() or "Could not read Git branches")
    local = {line.strip() for line in output.splitlines() if line.strip()}

    code, output = await command(["git", "for-each-ref", "--format=%(refname:short)", "refs/remotes/origin"], repo)
    if code:
        # Repositories without an origin are still fully usable locally.
        output = ""
    remote = {
        line.removeprefix("origin/").strip()
        for line in output.splitlines()
        if line.startswith("origin/") and line.strip() != "origin/HEAD"
    }
    code, current = await command(["git", "branch", "--show-current"], repo)
    if code:
        raise RuntimeError(current.strip() or "Could not determine the current Git branch")
    code, status = await command(["git", "status", "--porcelain"], repo)
    if code:
        raise RuntimeError(status.strip() or "Could not determine the Git working tree status")
    return {
        "current": current.strip(),
        "dirty": bool(status.strip()),
        "branches": [
            {"name": name, "local": name in local, "remote": name in remote}
            for name in sorted(local | remote, key=str.casefold)
        ],
    }


async def task_branch_preflight(repo: Path, branch: str, confirmed_dirty_worktree: bool) -> tuple[str, bool]:
    """Allow a dirty worktree only when the user keeps its current branch and confirms it."""
    code, status = await command(["git", "status", "--porcelain"], repo)
    if code:
        raise RuntimeError(status.strip() or "Could not determine the Git working tree status")
    code, current = await command(["git", "branch", "--show-current"], repo)
    if code:
        raise RuntimeError(current.strip() or "Could not determine the current Git branch")
    current = current.strip()
    dirty = bool(status.strip())
    if dirty and current != branch:
        raise RuntimeError(
            f"Repository has uncommitted changes on `{current or 'detached HEAD'}`. "
            f"A task can keep those changes only on the current branch; requested branch is `{branch}`."
        )
    if dirty and not confirmed_dirty_worktree:
        raise RuntimeError("Confirm that you know the Git working tree has uncommitted changes before starting this session")
    return current, dirty


async def base_branch_ref(repo: Path, base_branch: str) -> str:
    """Resolve a selected base branch locally, then fall back to origin."""
    code, _ = await command(["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{base_branch}^{{commit}}"], repo)
    if code == 0:
        return base_branch
    source_branch = f"origin/{base_branch}"
    code, _ = await command(["git", "rev-parse", "--verify", "--quiet", f"refs/remotes/{source_branch}^{{commit}}"], repo)
    if code:
        raise RuntimeError(f"Base branch `{base_branch}` was not found locally or on origin")
    return source_branch


async def switch_git_branch(repo: Path, branch: str, base_branch: str) -> dict:
    """Switch to an existing branch, or create it from the selected base once."""
    code, output = await command(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], repo)
    if code == 0:
        args, created, message = ["git", "switch", branch], False, f"Checked out existing branch `{branch}`"
    else:
        code, output = await command(["git", "show-ref", "--verify", "--quiet", f"refs/remotes/origin/{branch}"], repo)
        if code == 0:
            args, created, message = ["git", "switch", "--track", "-c", branch, f"origin/{branch}"], False, f"Checked out existing remote branch `{branch}`"
        else:
            source_branch = await base_branch_ref(repo, base_branch)
            args = ["git", "switch", "-c", branch, source_branch]
            created, message = True, f"Created and checked out `{branch}` from `{source_branch}`"
    code, output = await command(args, repo)
    if code:
        raise RuntimeError(output.strip() or f"Could not switch to branch `{branch}`")
    result = await git_branches(repo)
    return {**result, "created": created, "message": message}


def cleanup_owned_test_artifacts(repo: Path) -> None:
    """Remove only temporary folders explicitly owned by Taskloom runs."""
    for path in repo.glob(".taskloom-test-*"):
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path, ignore_errors=True)


def test_setup_commands(repo: Path) -> tuple[Path, list[tuple[list[str], dict[str, str] | None]]]:
    """Return local test setup commands without placing secrets in the output."""
    backend = repo / "backend"
    scripts = backend / "scripts"
    interpreter = backend / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    required = [
        scripts / "seed_local_test_database.py",
        scripts / "bootstrap_sso_tokens.py",
        scripts / "grant_local_test_admin.py",
    ]
    if not interpreter.is_file():
        raise RuntimeError("Test setup requires backend/venv with its Python interpreter")
    if missing := [str(path.relative_to(repo)) for path in required if not path.is_file()]:
        raise RuntimeError(f"Test setup scripts are missing: {', '.join(missing)}")
    database_url = os.getenv("TEST_DATABASE_URL", "").strip()
    if database_url:
        parsed = urlsplit(database_url)
        if parsed.hostname is None or parsed.hostname.casefold() not in {"localhost", "127.0.0.1", "::1"}:
            raise RuntimeError("Test setup only permits TEST_DATABASE_URL hosts localhost, 127.0.0.1, or ::1")
        if parsed.scheme not in {"postgres", "postgresql"} or not parsed.path.strip("/"):
            raise RuntimeError("TEST_DATABASE_URL must be a PostgreSQL URL with a database name")
    executable = str(interpreter)
    return backend, [
        ([executable, "scripts/seed_local_test_database.py", "--reset-public"], None),
        ([executable, "scripts/bootstrap_sso_tokens.py"], None),
        ([executable, "scripts/grant_local_test_admin.py"], None),
    ]


async def run_test_setup(repo: Path) -> str:
    """Reset a verified local test DB, retry login bootstrap, then grant admin access."""
    backend, commands = test_setup_commands(repo)
    labels = ("Resetting local test database", "Bootstrapping test-user logins", "Granting first test user admin access")
    transcript: list[str] = []
    for index, (label, (args, command_env)) in enumerate(zip(labels, commands)):
        attempts = 3 if index == 1 else 1
        for attempt in range(1, attempts + 1):
            code, output = await command(args, backend, 900, command_env)
            transcript.append(f"{label}{f' (attempt {attempt}/{attempts})' if attempts > 1 else ''}: {'ok' if code == 0 else 'failed'}")
            if code == 0:
                break
        else:
            raise RuntimeError(f"{label} failed after {attempts} attempts")
    return "\n".join(transcript)[-20_000:]


async def prepare_tests(state: TaskState, repo: Path, step: str) -> None:
    state.step = step
    state.test_setup_output = await run_test_setup(repo)
    state.logs.append("Local test environment setup completed")


def resolve_guides(repo: Path, paths: list[str]) -> list[Path]:
    result: list[Path] = []
    for raw in paths:
        path = Path(raw).expanduser()
        path = path.resolve() if path.is_absolute() else (repo / path).resolve()
        if not path.exists():
            raise ValueError(f"Guide path does not exist: {raw}")
        if path.is_dir():
            result.extend(candidate for candidate in path.rglob("*.md") if candidate.is_file())
        elif path.is_file():
            result.append(path)
        else:
            raise ValueError(f"Guide path must be a file or directory: {raw}")
    # Keep prompt order stable and avoid duplicates from overlapping directories.
    result = list(dict.fromkeys(result))
    return result


def detect_tests(repo: Path) -> list[str]:
    package_json = repo / "package.json"
    if package_json.is_file():
        try:
            package = json.loads(package_json.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            package = {}
        scripts = package.get("scripts") if isinstance(package, dict) else None
        test_script = scripts.get("test") if isinstance(scripts, dict) else None
        if isinstance(test_script, str) and test_script.strip():
            return [shutil.which("npm") or "npm", "test"]
    if (repo / "pytest.ini").exists() or (repo / "pyproject.toml").exists() or (repo / "tests").exists():
        return [shutil.which("pytest") or "pytest", "-q"]
    return [shutil.which("python") or "python", "-m", "pytest", "-q"]


def build_prompt(req: TaskRequest, guides: list[Path], active_mcp: str | None = None) -> str:
    listed = "\n".join(f"- {path}" for path in guides) or "- Discover repository instructions."
    mcp_instruction = ""
    if active_mcp == "dws_project":
        mcp_instruction = f"""
Before inspecting the repository directly, use the read-only tools from the `{active_mcp}` MCP server for project knowledge. Start with `search_docs`, `read_doc`, `search_code`, or `read_file` as appropriate. Treat MCP responses as context only. Do not use its `run_tests` tool as evidence for Taskloom gates; Taskloom runs the required test plan independently."""
    elif active_mcp:
        mcp_instruction = f"\nUse the read-only project-knowledge tools from the `{active_mcp}` MCP server before inspecting the repository directly. Treat its responses as context, not test-gate evidence."
    test_setup_instruction = ""
    if req.test_setup_enabled:
        test_setup_instruction = """
Local test setup has been explicitly enabled for this task. Taskloom prepares it before this session and again before its final test gate. If you run a stateful project test yourself, first run the project's documented local-test setup: reset only TEST_DATABASE_URL after confirming it points to localhost, bootstrap SSO tokens (retry up to three total attempts), then grant the first test user admin access. Stop and report a failed setup; never point these commands at a non-local database."""
    return f"""Implement task {req.task_id}.
User request: {req.request}
Instruction/documentation paths:\n{listed}{mcp_instruction}{test_setup_instruction}
Inspect and obey repository instructions. Implement the smallest complete change. After every implementation change, review the relevant Markdown (.md) files and update any documentation affected by that change. If no Markdown update is needed, state that explicitly in the final summary. Add meaningful pytest or project-native tests; use Locust only for performance work. Do not commit, push, switch branches, or modify files outside this repository. Finish with a concise summary and testing notes."""


def _mcp_config(output: str, server_name: str) -> dict | None:
    decoder = json.JSONDecoder()
    for match in re.finditer(r"(?m)^\s*\{", output):
        try:
            value, _ = decoder.raw_decode(output[match.start():].lstrip())
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and value.get("name") == server_name:
            return value
    return None


async def preflight_project_mcp(
    executable: str,
    repo: Path,
    server_name: str,
    agent_type: AgentType = AgentType.codex,
) -> tuple[bool, str]:
    args = [executable, "mcp", "get", server_name]
    if agent_type == AgentType.codex:
        args.append("--json")
    code, output = await command(args, repo, 30)
    if code:
        if code == 124:
            return False, f"MCP `{server_name}` preflight timed out."
        if "not found" in output.casefold() or "does not exist" in output.casefold():
            return False, f"MCP `{server_name}` is not configured."
        return False, f"MCP `{server_name}` preflight failed with exit code {code}."
    if agent_type == AgentType.claude:
        lowered = output.casefold()
        unavailable = (
            "pending approval",
            "rejected",
            "disabled",
            "failed to connect",
            "needs authentication",
            "not configured",
        )
        if any(marker in lowered for marker in unavailable):
            return False, f"MCP `{server_name}` is configured but unavailable to Claude Code."
        return True, f"MCP `{server_name}` is configured for Claude Code."
    config = _mcp_config(output, server_name)
    if config is None:
        return False, f"MCP `{server_name}` returned an unreadable preflight response."
    if config.get("enabled") is not True:
        return False, f"MCP `{server_name}` is configured but disabled."
    return True, f"MCP `{server_name}` is configured and enabled."


def mcp_runtime_issue(
    output: str,
    server_name: str,
    agent_type: AgentType = AgentType.codex,
) -> str | None:
    if agent_type == AgentType.claude:
        for line in output.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") != "system" or event.get("subtype") != "init":
                continue
            servers = event.get("mcp_servers") or []
            server = next(
                (item for item in servers if isinstance(item, dict) and item.get("name") == server_name),
                None,
            )
            if server is None or str(server.get("status", "")).casefold() not in {"connected", "ready"}:
                return f"MCP `{server_name}` did not initialize in the Claude session."
        return None
    markers = (
        "failed to start",
        "failed to initialize",
        "initialization failed",
        "startup timed out",
        "timed out during initialization",
    )
    for line in output.splitlines():
        lowered = line.casefold()
        if server_name.casefold() in lowered and any(marker in lowered for marker in markers):
            return f"MCP `{server_name}` did not initialize in the Codex session."
    return None


def codex_response(output: str) -> tuple[str, str]:
    """Extract the persisted thread ID and final agent message from JSONL output."""
    thread_id = ""
    messages: list[str] = []
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "thread.started":
            thread_id = event.get("thread_id", "")
        item = event.get("item", {})
        if event.get("type") == "item.completed" and item.get("type") == "agent_message":
            messages.append(item.get("text", ""))
    return thread_id, "\n\n".join(message for message in messages if message).strip()


def _claude_text_blocks(event: dict) -> list[str]:
    message = event.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, list):
        return []
    return [
        block.get("text", "")
        for block in content
        if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str)
    ]


def claude_response(output: str) -> tuple[str, str]:
    """Extract Claude Code's persisted session ID and final result from JSONL."""
    session_id = ""
    messages: list[str] = []
    result = ""
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        session_id = event.get("session_id", "") or session_id
        if event.get("type") == "assistant":
            messages.extend(_claude_text_blocks(event))
        elif event.get("type") == "result" and isinstance(event.get("result"), str):
            result = event["result"].strip()
    return session_id, result or "\n\n".join(message for message in messages if message).strip()


class CodexEventStream:
    """Turn Codex JSONL events into a compact, user-facing live transcript."""

    def __init__(self, state: TaskState) -> None:
        self.state = state
        self.buffer = ""
        self.saw_data = False
        self.started_items: set[str] = set()
        self.agent_items: dict[str, str] = {}
        self.command_outputs: dict[str, str] = {}
        self.event_index = 0

    def feed(self, chunk: str) -> None:
        self.saw_data = True
        self.buffer += chunk
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            self._event(line.rstrip("\r"))

    def finish(self) -> None:
        if self.buffer:
            self._event(self.buffer.rstrip("\r"))
            self.buffer = ""

    def _append(self, text: str) -> None:
        if not text:
            return
        separator = "" if not self.state.live_output or self.state.live_output.endswith("\n") else "\n"
        self.state.live_output = f"{self.state.live_output}{separator}{text}"[-30_000:]

    def _event(self, line: str) -> None:
        if not line.strip():
            return
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            self._append(line)
            return

        event_type = event.get("type", "")
        if event_type == "thread.started":
            self.state.codex_thread_id = event.get("thread_id", "") or self.state.codex_thread_id
            self._append("Codex session started.\n")
            return
        if event_type in {"turn.failed", "error"}:
            error = event.get("error") or event.get("message") or "Codex reported an error."
            if isinstance(error, dict):
                error = error.get("message") or json.dumps(error, ensure_ascii=False)
            self._append(f"Error: {error}\n")
            return

        item = event.get("item")
        if not isinstance(item, dict):
            return
        self.event_index += 1
        item_id = str(item.get("id") or f"{item.get('type', 'item')}:{self.event_index}")
        item_type = item.get("type")

        if item_type == "agent_message" and event_type in {"item.updated", "item.completed"}:
            previous = self.agent_items.get(item_id, "")
            text = item.get("text", "")
            if not text and isinstance(item.get("delta"), str):
                text = previous + item["delta"]
            if not isinstance(text, str) or not text:
                return
            delta = text[len(previous):] if text.startswith(previous) else text
            self.agent_items[item_id] = text
            self.state.live_response = "\n\n".join(self.agent_items.values())[-20_000:]
            if delta:
                self.state.live_output = f"{self.state.live_output}{delta}"[-30_000:]
            if event_type == "item.completed" and not self.state.live_output.endswith("\n"):
                self.state.live_output += "\n"
            return

        if item_type == "command_execution" and event_type in {"item.started", "item.updated", "item.completed"}:
            command_text = item.get("command", "")
            if event_type == "item.started" and command_text:
                self.started_items.add(item_id)
                self._append(f"$ {command_text}\n")
            elif item_id not in self.started_items and command_text:
                self.started_items.add(item_id)
                self._append(f"$ {command_text}\n")
            output = item.get("aggregated_output", "")
            previous_output = self.command_outputs.get(item_id, "")
            if isinstance(output, str) and output:
                delta = output[len(previous_output):] if output.startswith(previous_output) else output
                self.command_outputs[item_id] = output
                if delta:
                    self.state.live_output = f"{self.state.live_output}{delta}"[-30_000:]
            if event_type == "item.completed":
                exit_code = item.get("exit_code")
                if exit_code not in {None, 0}:
                    self._append(f"[exit {exit_code}]\n")
            return

        if event_type != "item.completed":
            return
        if item_type == "file_change":
            changes = item.get("changes") or []
            details = [f"{change.get('kind', 'updated')}: {change.get('path', '')}" for change in changes if isinstance(change, dict)]
            self._append("\n".join(details) + ("\n" if details else "Files updated.\n"))
        elif item_type == "mcp_tool_call":
            tool = item.get("tool") or item.get("name") or "tool"
            server = item.get("server") or "MCP"
            self._append(f"{server}: {tool}\n")
        elif item_type == "web_search":
            query = item.get("query") or "search"
            self._append(f"Search: {query}\n")


class ClaudeEventStream:
    """Turn Claude Code stream-json events into Taskloom's live transcript."""

    def __init__(self, state: TaskState) -> None:
        self.state = state
        self.buffer = ""
        self.saw_data = False

    def feed(self, chunk: str) -> None:
        self.saw_data = True
        self.buffer += chunk
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            self._event(line.rstrip("\r"))

    def finish(self) -> None:
        if self.buffer:
            self._event(self.buffer.rstrip("\r"))
            self.buffer = ""

    def _append(self, text: str) -> None:
        if not text:
            return
        separator = "" if not self.state.live_output or self.state.live_output.endswith("\n") else "\n"
        self.state.live_output = f"{self.state.live_output}{separator}{text}"[-30_000:]

    def _event(self, line: str) -> None:
        if not line.strip():
            return
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            self._append(line)
            return
        self.state.codex_thread_id = event.get("session_id", "") or self.state.codex_thread_id
        event_type = event.get("type")
        if event_type == "system" and event.get("subtype") == "init":
            self._append("Claude session started.\n")
            return
        if event_type == "assistant":
            texts = _claude_text_blocks(event)
            if texts:
                text = "\n\n".join(texts)
                self.state.live_response = f"{self.state.live_response}\n\n{text}".strip()[-20_000:]
                self._append(text + "\n")
            message = event.get("message")
            content = message.get("content") if isinstance(message, dict) else []
            for block in content if isinstance(content, list) else []:
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue
                tool, tool_input = block.get("name", "tool"), block.get("input") or {}
                detail = tool_input.get("command") or tool_input.get("file_path") or tool_input.get("pattern") or ""
                self._append(f"{tool}: {detail}\n" if detail else f"{tool}\n")
            return
        if event_type == "result" and event.get("is_error"):
            error = event.get("result") or event.get("subtype") or "Claude reported an error."
            self._append(f"Error: {error}\n")


async def codex_command(args: list[str], repo: Path, state: TaskState, timeout: int) -> tuple[int, str]:
    """Run Codex while applying its JSONL events to the observable task state."""
    state.live_output = ""
    state.live_response = ""
    stream = CodexEventStream(state)
    token = _command_output_handler.set(stream.feed)
    try:
        code, output = await command([*args[:-1], "-"], repo, timeout, stdin_text=args[-1])
    finally:
        _command_output_handler.reset(token)
    # Test doubles and alternative command runners may return buffered output.
    if not stream.saw_data:
        stream.feed(output)
    stream.finish()
    return code, output


async def claude_command(args: list[str], repo: Path, state: TaskState, timeout: int) -> tuple[int, str]:
    """Run Claude Code while applying stream-json events to the task state."""
    state.live_output = ""
    state.live_response = ""
    stream = ClaudeEventStream(state)
    token = _command_output_handler.set(stream.feed)
    try:
        code, output = await command(args, repo, timeout)
    finally:
        _command_output_handler.reset(token)
    if not stream.saw_data:
        stream.feed(output)
    stream.finish()
    return code, output


def agent_name(agent_type: AgentType) -> str:
    return "Claude" if agent_type == AgentType.claude else "Codex"


def agent_executable(agent_type: AgentType) -> str:
    executable_name = "claude" if agent_type == AgentType.claude else "codex"
    executable = shutil.which(executable_name)
    if not executable:
        display_name = "Claude Code" if agent_type == AgentType.claude else "Codex"
        raise RuntimeError(f"{display_name} CLI was not found. Install it and sign in first.")
    return executable


def initial_agent_args(agent_type: AgentType, executable: str, prompt: str) -> list[str]:
    if agent_type == AgentType.claude:
        return [
            executable,
            "--print",
            "--output-format",
            "stream-json",
            "--verbose",
            "--permission-mode",
            "acceptEdits",
            prompt,
        ]
    return [executable, "exec", "--sandbox", "workspace-write", "--color", "never", "--json", prompt]


def resume_agent_args(agent_type: AgentType, executable: str, session_id: str, prompt: str) -> list[str]:
    if agent_type == AgentType.claude:
        return [
            executable,
            "--print",
            "--resume",
            session_id,
            "--output-format",
            "stream-json",
            "--verbose",
            "--permission-mode",
            "acceptEdits",
            prompt,
        ]
    return [executable, "exec", "resume", "--json", session_id, prompt]


async def run_agent_command(
    agent_type: AgentType,
    args: list[str],
    repo: Path,
    state: TaskState,
    timeout: int,
) -> tuple[int, str]:
    if agent_type == AgentType.claude:
        return await claude_command(args, repo, state, timeout)
    return await codex_command(args, repo, state, timeout)


def agent_response(agent_type: AgentType, output: str) -> tuple[str, str]:
    return claude_response(output) if agent_type == AgentType.claude else codex_response(output)


def agent_error_detail(output: str) -> str:
    """Extract a concise CLI failure without dumping the full event stream."""
    diagnostics: list[str] = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            event = json.loads(stripped)
        except json.JSONDecodeError:
            diagnostics.append(stripped)
            continue
        if event.get("type") in {"error", "turn.failed"}:
            error = event.get("error") or event.get("message")
            if isinstance(error, dict):
                error = error.get("message")
            if isinstance(error, str) and error.strip():
                diagnostics.append(error.strip())
        elif event.get("type") == "result" and event.get("is_error"):
            error = event.get("result") or event.get("subtype")
            if isinstance(error, str) and error.strip():
                diagnostics.append(error.strip())
    return " ".join(diagnostics)[-2_000:]


async def refresh_git(state: TaskState, repo: Path) -> None:
    _, state.diff = await command(["git", "diff", "--no-ext-diff", "--"], repo)
    _, staged = await command(["git", "diff", "--cached", "--no-ext-diff", "--"], repo)
    state.diff = f"{state.diff}\n{staged}".strip()
    _, names = await command(["git", "status", "--short"], repo)
    state.changed_files = [line[3:] for line in names.splitlines() if len(line) > 3]


async def execute_task(req: TaskRequest, state: TaskState) -> None:
    try:
        repo = repository(req.project_path)
        guides = resolve_guides(repo, [*req.guide_paths, *([state.role_knowledge_path] if state.role_knowledge_path else [])])
        state.status, state.step = RunStatus.running, "Checking project prerequisites"
        executable = agent_executable(req.agent_type)
        display_name = agent_name(req.agent_type)
        active_mcp = None
        if req.mcp_server_name:
            state.mcp_status = McpStatus.checking
            ready, message = await preflight_project_mcp(executable, repo, req.mcp_server_name, req.agent_type)
            state.mcp_message = message
            if ready:
                state.mcp_status = McpStatus.ready
                active_mcp = req.mcp_server_name
            elif req.mcp_failure_mode == McpFailureMode.blocked:
                state.status = RunStatus.blocked
                state.step = "Project MCP preflight blocked"
                state.error = message
                state.mcp_status = McpStatus.blocked
                state.logs.append(message)
                return
            else:
                state.mcp_status = McpStatus.warning
            state.logs.append(message)

        if req.test_setup_enabled:
            await prepare_tests(state, repo, "Preparing local test environment")

        state.step = "Preparing task branch"
        current_branch, dirty_worktree = await task_branch_preflight(
            repo, state.branch, req.confirm_dirty_worktree
        )
        state.base_branch = req.base_branch
        if current_branch == state.branch:
            args = None
            message = f"Using current task branch {state.branch}"
            if dirty_worktree:
                message += " with the user's confirmed uncommitted changes"
        else:
            code, _ = await command(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{state.branch}"], repo)
        if current_branch != state.branch and not code:
            args, message = ["git", "switch", state.branch], f"Checked out existing task branch {state.branch}"
        elif current_branch != state.branch:
            code, _ = await command(["git", "show-ref", "--verify", "--quiet", f"refs/remotes/origin/{state.branch}"], repo)
            if not code:
                args, message = ["git", "switch", "--track", "-c", state.branch, f"origin/{state.branch}"], f"Checked out existing remote task branch {state.branch}"
            else:
                source_branch = await base_branch_ref(repo, req.base_branch)
                args, message = ["git", "switch", "-c", state.branch, source_branch], f"Created {state.branch} from {source_branch}"
        if args:
            code, output = await command(args, repo)
            if code:
                raise RuntimeError(output.strip() or "Could not prepare task branch")
        state.logs.append(message)
        state.step = f"{display_name} is implementing the request"
        args = initial_agent_args(req.agent_type, executable, build_prompt(req, guides, active_mcp))
        code, output = await run_agent_command(req.agent_type, args, repo, state, 3600)
        runtime_issue = mcp_runtime_issue(output, active_mcp, req.agent_type) if active_mcp else None
        if runtime_issue:
            state.mcp_message = runtime_issue
            state.logs.append(runtime_issue)
            if req.mcp_failure_mode == McpFailureMode.blocked:
                await refresh_git(state, repo)
                state.status = RunStatus.blocked
                state.step = "Project MCP initialization blocked"
                state.error = runtime_issue
                state.mcp_status = McpStatus.blocked
                return
            state.mcp_status = McpStatus.warning
        elif active_mcp:
            state.mcp_message = f"MCP `{active_mcp}` was available to the {display_name} session."
        thread_id, response = agent_response(req.agent_type, output)
        if not thread_id:
            detail = agent_error_detail(output)
            if detail:
                raise RuntimeError(f"{display_name} failed before creating a resumable session: {detail}")
            raise RuntimeError(f"{display_name} did not return a resumable session ID")
        state.codex_thread_id = thread_id
        state.logs.append(output[-12000:])
        state.summary = response or output.strip()[-4000:]
        if response:
            state.messages.append(ChatMessage(role="assistant", content=response))
        state.live_response = ""
        await refresh_git(state, repo)
        cleanup_owned_test_artifacts(repo)
        if code:
            raise RuntimeError(f"{display_name} exited with code {code}")
        if not state.changed_files:
            raise RuntimeError(f"{display_name} completed without producing file changes")
        if req.test_setup_enabled:
            await prepare_tests(state, repo, "Preparing local test environment before final tests")
        state.status, state.step = RunStatus.testing, "Running tests"
        tests, test_cwd = test_plan(repo, state.test_command, state.test_working_directory)
        code, output = await command(tests, test_cwd, 1800)
        state.test_output = output
        state.commit_message = f"feat({req.task_id}): implement requested changes"
        state.status, state.step = (RunStatus.passed, "Ready for review") if code == 0 else (RunStatus.failed, "Tests failed")
        if code:
            state.error = f"Tests exited with code {code}"
        await refresh_git(state, repo)
    except asyncio.CancelledError:
        state.status, state.step, state.error = RunStatus.stopped, "Stopped by user", None
        state.logs.append("Run stopped by user")
        try:
            await refresh_git(state, repo)
        except Exception:
            pass
    except Exception as exc:
        state.status, state.step, state.error = RunStatus.failed, "Run failed", str(exc)
        state.logs.append(str(exc))


async def continue_task(message: str, state: TaskState) -> None:
    """Continue the exact agent session used for the task with a user follow-up."""
    try:
        if not state.codex_thread_id:
            raise RuntimeError("This task does not have a resumable agent session")
        repo = repository(state.project_path)
        executable = agent_executable(state.agent_type)
        display_name = agent_name(state.agent_type)
        state.status, state.step, state.error = RunStatus.running, f"{display_name} is responding", None
        role_guides = resolve_guides(repo, [state.role_knowledge_path]) if state.role_knowledge_path else []
        role_instruction = f"Current role: {state.role.value}. Read these role knowledge files before responding:\n" + "\n".join(f"- {path}" for path in role_guides) + "\n\n" if role_guides else ""
        prompt = f"""{role_instruction}User follow-up:\n{message}\n\nContinue this conversation. Make edits when they help answer the request, but do not commit, push, switch branches, or modify files outside this repository. Summarize what you did or recommend next."""
        args = resume_agent_args(state.agent_type, executable, state.codex_thread_id, prompt)
        code, output = await run_agent_command(state.agent_type, args, repo, state, 3600)
        _, response = agent_response(state.agent_type, output)
        state.logs.append(output[-12000:])
        state.summary = response or output.strip()[-4000:]
        if response:
            state.messages.append(ChatMessage(role="assistant", content=response))
        state.live_response = ""
        await refresh_git(state, repo)
        if code:
            raise RuntimeError(f"{display_name} exited with code {code}")
        if state.test_setup_enabled:
            await prepare_tests(state, repo, "Preparing local test environment before final tests")
        state.status, state.step = RunStatus.testing, "Running tests"
        tests, test_cwd = test_plan(repo, state.test_command, state.test_working_directory)
        code, output = await command(tests, test_cwd, 1800)
        state.test_output = output
        state.status, state.step = (RunStatus.passed, "Ready for further instructions") if code == 0 else (RunStatus.failed, "Tests failed")
        if code:
            state.error = f"Tests exited with code {code}"
        await refresh_git(state, repo)
        if state.changed_files:
            state.committed = False
            state.pushed = False
        cleanup_owned_test_artifacts(repo)
    except asyncio.CancelledError:
        state.status, state.step, state.error = RunStatus.stopped, "Stopped by user", None
        state.logs.append("Conversation stopped by user")
        try:
            await refresh_git(state, repo)
        except Exception:
            pass
        if state.changed_files:
            state.committed = False
            state.pushed = False
    except Exception as exc:
        state.status, state.step, state.error = RunStatus.failed, "Conversation failed", str(exc)
        state.logs.append(str(exc))


async def generate_commit_message(state: TaskState) -> str:
    """Ask the task's existing agent session for a concise commit message."""
    if state.status != RunStatus.passed or not state.changed_files:
        raise ValueError("A successful test run with changes is required")
    if state.committed:
        raise ValueError("The task has already been committed")
    if not state.codex_thread_id:
        raise ValueError("This task does not have a resumable agent session")
    repo = repository(state.project_path)
    executable = agent_executable(state.agent_type)
    display_name = agent_name(state.agent_type)
    prompt = """Review only the work completed in this task's current session and its uncommitted diff.
Reply with exactly one concise, English Conventional Commit subject in this format: type(optional-scope): imperative summary
Choose the type from build, chore, ci, docs, feat, fix, perf, refactor, revert, style, or test. Keep it to one line and 120 ASCII characters or fewer. Do not add a body, Markdown, translation, task commentary, or explanation. Do not edit files, run tests, commit, or push."""
    args = resume_agent_args(state.agent_type, executable, state.codex_thread_id, prompt)
    if state.agent_type == AgentType.codex:
        code, output = await command([*args[:-1], "-"], repo, 600, stdin_text=prompt)
    else:
        code, output = await command(args, repo, 600)
    if code:
        raise RuntimeError(f"{display_name} exited with code {code}")
    _, response = agent_response(state.agent_type, output)
    message = response.splitlines()[0].strip().strip("`") if response else ""
    if not COMMIT_MESSAGE_PATTERN.fullmatch(message):
        raise RuntimeError(f"{display_name} did not return a concise English Conventional Commit message")
    return message


async def git_commit(state: TaskState, message: str) -> str:
    repo = repository(state.project_path)
    await refresh_git(state, repo)
    if state.status != RunStatus.passed or not state.changed_files:
        raise ValueError("A successful test run with changes is required")
    code, output = await command(["git", "add", "."], repo)
    if code:
        raise RuntimeError(output)
    code, output = await command(["git", "diff", "--cached", "--quiet"], repo)
    if code == 0:
        raise RuntimeError("No changes were staged for commit")
    if code > 1:
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
    code, current = await command(["git", "branch", "--show-current"], repo)
    if code:
        raise RuntimeError(current.strip() or "Could not determine the current Git branch")
    if current.strip() != state.branch:
        raise ValueError(f"Switch to task branch `{state.branch}` before pushing")
    code, status = await command(["git", "status", "--porcelain"], repo)
    if code:
        raise RuntimeError(status.strip() or "Could not inspect the repository before pushing")
    if status.strip():
        raise ValueError("Commit all changes and resolve any merge conflicts before pushing")
    code, pull_output = await command(
        ["git", "pull", "--no-rebase", "--no-edit", "origin", state.base_branch],
        repo,
        600,
    )
    if code:
        # Keeping the task branch current with the base is a best-effort delivery
        # check. A conflict must not leave the repository mid-merge or prevent the
        # already committed task branch from being pushed.
        await command(["git", "merge", "--abort"], repo)
        pull_warning = (
            pull_output.strip()
            or f"Could not merge origin/{state.base_branch} before pushing"
        )
        state.logs.append(f"Optional base-branch pull skipped: {pull_warning}")
        pull_output = f"Warning: optional base-branch pull skipped. {pull_warning}"
    code, push_output = await command(["git", "push", "-u", "origin", state.branch], repo, 600)
    if code:
        raise RuntimeError(push_output)
    state.pushed = True
    return "\n".join(part.strip() for part in (pull_output, push_output) if part.strip())


async def create_merge_request(state: TaskState) -> str:
    if not state.pushed:
        raise ValueError("Push the task branch first")
    if state.merge_request_url:
        raise ValueError("A merge request already exists for this task")
    repo = repository(state.project_path)
    code, remote = await command(["git", "remote", "get-url", "origin"], repo)
    if code:
        raise RuntimeError(remote.strip() or "Could not read the origin remote")

    normalized_remote = remote.casefold()
    provider = state.git_provider
    if provider == GitProvider.github or (provider == GitProvider.auto and "github" in normalized_remote):
        cli_name = "gh"
        args = ["pr", "create", "--fill", "--head", state.branch, "--base", state.base_branch]
    elif provider == GitProvider.gitlab or (provider == GitProvider.auto and "gitlab" in normalized_remote):
        cli_name = "glab"
        args = ["mr", "create", "--fill", "--source-branch", state.branch, "--target-branch", state.base_branch, "--yes"]
    else:
        raise ValueError("Merge requests are supported for GitHub and GitLab origin remotes")

    cli = shutil.which(cli_name)
    if not cli:
        raise RuntimeError(f"{cli_name} CLI was not found. Install it and sign in first.")
    code, output = await command([cli, *args], repo, 600)
    if code:
        raise RuntimeError(output.strip() or "Could not create the merge request")
    urls = re.findall(r"https?://[^\s]+", output)
    if not urls:
        raise RuntimeError("The merge request was created but its URL was not returned")
    state.merge_request_url = urls[-1].rstrip(".,;)")
    state.step = "Merge request ready"
    return output
