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

from .models import AgentType, ChatMessage, GitProvider, McpFailureMode, McpStatus, RunStatus, TaskRequest, TaskState, SDLCTask, SDLCProjectConfig, AgentResult, ModelInfo, ProjectModelSettings, Change, AgentConfig


_command_output_handler: ContextVar[Callable[[str], None] | None] = ContextVar("command_output_handler", default=None)
# Called with the child's PID right after it starts (used to find orphaned agents after a crash).
_command_started_handler: ContextVar[Callable[[int], None] | None] = ContextVar("command_started_handler", default=None)
COMMIT_MESSAGE_PATTERN = re.compile(r"^(?:build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)(?:\([a-z0-9][a-z0-9._/-]*\))?!?: [A-Za-z0-9][ -~]{0,117}$")


def _command_sync(
    args: list[str],
    cwd: Path,
    timeout: int,
    env: dict[str, str] | None,
    handler: Callable[[str], None] | None,
    cancelled: threading.Event,
    stdin_text: str | None = None,
    started: Callable[[int], None] | None = None,
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
    if started:
        started(process.pid)
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
        asyncio.to_thread(_command_sync, args, cwd, timeout, env, _command_output_handler.get(), cancelled, stdin_text, _command_started_handler.get())
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
    return (split_command(test_command) if test_command else detect_tests(cwd), cwd)


def split_command(text: str) -> list[str]:
    """Split a command line, keeping Windows backslashes and dropping the quotes around tokens."""
    return [token[1:-1] if len(token) > 1 and token[0] == token[-1] and token[0] in "\"'" else token
            for token in shlex.split(text, posix=False)]


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
WORKSPACE_PREVIEW_MEDIA_TYPES = {
    ".avif": "image/avif", ".svg": "image/svg+xml", ".webp": "image/webp", ".pdf": "application/pdf",
}


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
    # Windows' mimetypes registry often lacks modern image types, so pin the ones we allow.
    media_type = WORKSPACE_PREVIEW_MEDIA_TYPES.get(suffix) or mimetypes.guess_type(path.name)[0]
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
        # `claude --print` reads the prompt from stdin when no positional prompt is given,
        # which avoids the Windows command-line length limit for long prompts.
        code, output = await command(args[:-1], repo, timeout, stdin_text=args[-1])
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


def initial_agent_args(agent_type: AgentType, executable: str, prompt: str,
                       extra_dirs: list[str] | None = None, allowed_tools: list[str] | None = None,
                       model: str | None = None) -> list[str]:
    if agent_type == AgentType.claude:
        # --add-dir lets the agent read the other SDLC stages' repositories (it is variadic, so it
        # must come before another option, never directly before the prompt).
        add_dirs = [arg for directory in (extra_dirs or []) for arg in ("--add-dir", directory)]
        model_args = ["--model", model] if model and model not in ("claude", "") else []
        return [
            executable,
            "--print",
            "--output-format",
            "stream-json",
            "--verbose",
            *add_dirs,
            *model_args,
            # One comma-separated value: --allowedTools is variadic and must not swallow the next option.
            *(["--allowedTools", ",".join(allowed_tools)] if allowed_tools else []),
            "--permission-mode",
            "acceptEdits",
            prompt,
        ]
    # Codex: pass model via --model flag when explicitly specified
    model_args = ["--model", model] if model and model not in ("codex", "") else []
    return [executable, "exec", "--sandbox", "workspace-write", "--color", "never", "--json", *model_args, prompt]


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
        from .git_flow import SANDBOX, GitRepo, create_task_branch  # local import: git_flow imports this module

        state.base_branch = SANDBOX  # every task branch starts from the latest sandbox, whatever the request said
        info = await create_task_branch(GitRepo(repo), req.task_id, state.branch)
        if current_branch == state.branch:
            message = f"Using current task branch {state.branch}"
            if dirty_worktree:
                message += " with the user's confirmed uncommitted changes"
        else:
            code, output = await command(["git", "switch", state.branch], repo)
            if code:
                raise RuntimeError(output.strip() or "Could not prepare task branch")
            message = (f"Created {state.branch} from the latest {SANDBOX} ({info.base_sha[:10]})" if info.created
                       else f"Checked out existing task branch {state.branch}")
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



# ===== SDLC PLATFORM SERVICES =====

import asyncio
import json
import uuid
import urllib.request
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional
from .file_lock import FileLock, LockTimeout, replace_with_retry
from .secret_store import SecretStore
from . import sdlc_policy as policy
from .models import (
    SDLCStatus, SDLCProjectConfig, AgentConfig, ProjectWorkflowConfig,
    SDLCTask, SDLCTaskRequest, AgentResult, HumanIntervention,
    RevisionRequest, SDLCTaskContext, TaskState, RunStatus, StageRunner, StageQuestion
)

from .config import OLLAMA_BASE_URL, OLLAMA_MODEL

def _feedback_text(task: SDLCTask, stage: str) -> str:
    """Revision requests and human answers for a stage, as plain prompt text (shared with CLI stages)."""
    from .sdlc_runner import stage_feedback

    sections = stage_feedback(task, stage)
    return "\n\n".join(sections) + "\n\n" if sections else ""


class OllamaDiscoveryService:
    """Service for discovering Ollama models and their capabilities"""
    
    def __init__(self, base_url: str = OLLAMA_BASE_URL):
        self.base_url = base_url.rstrip("/")
    
    async def list_models(self) -> list[ModelInfo]:
        """Get list of available Ollama models"""
        try:
            import urllib.request
            import json
            
            req = urllib.request.Request(
                f"{self.base_url}/api/tags",
                headers={"Content-Type": "application/json"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                models_data = data.get("models", [])
                
                models = []
                for model_data in models_data:
                    model_name = model_data.get("name", "")
                    # Extract family and parameters from name
                    family = "unknown"
                    parameters = ""
                    quantization = ""
                    
                    # Try to parse model name
                    if "qwen" in model_name.lower():
                        family = "Qwen"
                    elif "llama" in model_name.lower():
                        family = "Llama"
                    elif "mistral" in model_name.lower():
                        family = "Mistral"
                    elif "gemma" in model_name.lower():
                        family = "Gemma"
                    
                    # Extract parameter count
                    import re
                    param_match = re.search(r'(\d+(?:\.\d+)?[bB])', model_name)
                    if param_match:
                        parameters = param_match.group(1)
                    
                    # Extract quantization
                    if "q4" in model_name.lower():
                        quantization = "Q4"
                    elif "q5" in model_name.lower():
                        quantization = "Q5"
                    elif "q6" in model_name.lower():
                        quantization = "Q6"
                    elif "q8" in model_name.lower():
                        quantization = "Q8"
                    
                    models.append(ModelInfo(
                        name=model_name,
                        family=family,
                        parameters=parameters,
                        quantization=quantization,
                        supports_tool_calls=("qwen" in model_name.lower() and "0.8b" not in model_name),
                        description=model_data.get("details", {}).get("description", ""),
                        modified_at=datetime.fromisoformat(model_data.get("modified_at", "").replace("Z", "+00:00")) 
                            if model_data.get("modified_at") else None,
                        size=model_data.get("size", 0)
                    ))
                
                return models
        except Exception as exc:
            raise RuntimeError(f"Failed to fetch Ollama models: {exc}") from exc
    
    async def get_model_info(self, model_name: str) -> ModelInfo | None:
        """Get detailed information about a specific model"""
        try:
            import urllib.request
            import json
            
            payload = json.dumps({"name": model_name}).encode()
            req = urllib.request.Request(
                f"{self.base_url}/api/show",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                
                # Extract information
                family = data.get("family", "unknown")
                parameters = data.get("parameter_size", "")
                quantization = data.get("quantization_level", "")
                
                return ModelInfo(
                    name=model_name,
                    family=family,
                    parameters=parameters,
                    quantization=quantization,
                    supports_tool_calls=data.get("support_tool_calls", False),
                    description=data.get("description", ""),
                    size=data.get("size", 0)
                )
        except Exception as exc:
            print(f"Failed to get model info for {model_name}: {exc}")
            return None
    
    async def check_connection(self) -> bool:
        """Check if Ollama is reachable"""
        try:
            import urllib.request
            
            req = urllib.request.Request(
                f"{self.base_url}/api/tags",
                method="GET",
                timeout=5
            )
            with urllib.request.urlopen(req):
                return True
        except Exception:
            return False


class ModelResolutionService:
    """Service for resolving which model to use for each SDLC stage (legacy)"""
    
    def __init__(self, discovery_service: OllamaDiscoveryService | None = None):
        self.discovery_service = discovery_service or OllamaDiscoveryService()
    
    def resolve_model_for_stage(
        self,
        stage: str,
        project_config: SDLCProjectConfig,
        task_override: str | None = None,
        agent_config: AgentConfig | None = None
    ) -> str:
        """Resolve which model to use for a specific stage (legacy)
        
        Priority order:
        1. Task-level override (if provided)
        2. Project stage assignment
        3. Project default model
        4. OLLAMA_MODEL environment variable
        5. Fallback to "qwen3.5:0.8b"
        """
        # 1. Task override (highest priority)
        if task_override and task_override.strip():
            return task_override.strip()
        
        # 2. Project stage assignment
        model_settings = project_config.model_settings
        stage_model = model_settings.stage_assignments.get(stage)
        if stage_model and stage_model.strip():
            return stage_model.strip()
        
        # 3. Project default model
        if model_settings.default_model.strip():
            return model_settings.default_model.strip()
        
        # 4. Environment variable
        from .config import OLLAMA_MODEL
        if OLLAMA_MODEL.strip():
            return OLLAMA_MODEL.strip()
        
        # 5. Fallback
        return "qwen3.5:0.8b"
    
    async def get_model_info_for_stage(
        self,
        stage: str,
        project_config: SDLCProjectConfig,
        task_override: str | None = None
    ) -> tuple[str, ModelInfo | None]:
        """Get both model name and detailed info for a stage"""
        model_name = self.resolve_model_for_stage(stage, project_config, task_override)
        model_info = await self.discovery_service.get_model_info(model_name)
        return model_name, model_info
    
    async def validate_model_availability(self, model_name: str) -> bool:
        """Check if a specific model is available"""
        try:
            models = await self.discovery_service.list_models()
            return any(model.name == model_name for model in models)
        except Exception:
            return False
    
    async def get_available_models(self) -> list[ModelInfo]:
        """Get list of available models"""
        try:
            return await self.discovery_service.list_models()
        except Exception as exc:
            print(f"Failed to get available models: {exc}")
            return []


class ProviderResolutionService:
    """Service for resolving which provider and model to use for each SDLC stage"""
    
    def __init__(self, provider_registry=None):
        from .providers import provider_registry as default_registry
        self.provider_registry = provider_registry or default_registry
    
    def resolve_provider_for_stage(
        self,
        stage: str,
        project_config: SDLCProjectConfig,
        agent_config: AgentConfig | None = None,
        task_override_provider: str | None = None,
        task_override_model: str | None = None
    ) -> tuple[str, str, bool]:
        """Resolve which provider and model to use for a specific stage
        
        Priority order:
        1. Task-level overrides (provider and model)
        2. Agent-level overrides (provider_override, model_override)
        3. Stage-specific provider and model from project AI settings
        4. Project default provider and model
        
        Returns:
            tuple: (provider_id, model_name, is_overridden)
        """
        is_overridden = False
        
        # 1. Task-level overrides (highest priority)
        if task_override_provider and task_override_provider.strip():
            provider = task_override_provider.strip().lower()
            model = task_override_model.strip() if task_override_model else ""
            is_overridden = True
            
            # If model is empty, use project default for that provider
            if not model:
                project_defaults = project_config.ai_settings
                if provider == project_defaults.default_provider:
                    model = project_defaults.default_model
                else:
                    # For different provider, we need a sensible default
                    if provider == "ollama":
                        model = "qwen3.5:0.8b"
                    elif provider == "codex":
                        model = "codex"
                    elif provider == "claude":
                        model = "claude"
            
            return provider, model, is_overridden
        
        # 2. Agent-level overrides
        if agent_config:
            provider, model, agent_overridden = agent_config.get_effective_provider(
                project_config.ai_settings, stage
            )
            if agent_overridden:
                is_overridden = True
                return provider, model, is_overridden
        
        # 3. Get from project AI settings for this stage
        provider, model, inherited = project_config.ai_settings.get_provider_for_stage(stage)
        
        # If the stage has an explicit override in project settings, mark as overridden
        if stage in project_config.ai_settings.stage_providers and not project_config.ai_settings.stage_providers[stage].inherit_from_project:
            is_overridden = True
        
        return provider, model, is_overridden
    
    async def validate_provider_availability(self, provider_id: str, model_name: str) -> tuple[bool, str]:
        """Validate that a provider and model are available
        
        Returns:
            tuple: (is_available, error_message)
        """
        provider = self.provider_registry.get_provider(provider_id)
        if not provider:
            return False, f"Provider '{provider_id}' not found"
        
        # Check provider availability
        if not await provider.check_availability():
            return False, f"Provider '{provider_id}' is unavailable"
        
        # Validate model
        if not await provider.validate_model(model_name):
            return False, f"Model '{model_name}' is not available for provider '{provider_id}'"
        
        return True, ""
    
    async def get_provider_info_for_stage(
        self,
        stage: str,
        project_config: SDLCProjectConfig,
        agent_config: AgentConfig | None = None
    ) -> dict:
        """Get provider and model information for a specific stage"""
        provider_id, model_name, is_overridden = self.resolve_provider_for_stage(
            stage, project_config, agent_config
        )
        
        provider = self.provider_registry.get_provider(provider_id)
        if not provider:
            return {
                "provider": provider_id,
                "model": model_name,
                "available": False,
                "overridden": is_overridden,
                "error": f"Provider '{provider_id}' not found"
            }
        
        # Check availability
        available = await provider.check_availability()
        result = {
            "provider": provider_id,
            "model": model_name,
            "available": available,
            "overridden": is_overridden,
            "provider_name": provider.get_display_name(),
            "agent_type": provider.get_agent_type().value,
            "runner_type": provider.get_runner_type().value,
        }
        
        if not available:
            result["error"] = f"Provider '{provider_id}' is unavailable"
        
        return result


class OllamaAgentRunner:
    """Calls ollama /v1/chat/completions to run an SDLC agent."""

    def __init__(self, base_url: str = OLLAMA_BASE_URL, model: str = OLLAMA_MODEL):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.resolution_service = ModelResolutionService()

    def _chat(self, system: str, user: str, timeout: int = 240) -> str:
        payload = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            "stream": False,
            "think": False,
            "options": {"num_predict": 500, "temperature": 0.3},
        }).encode()

        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read())
                # Native ollama /api/chat returns {"message": {"content": "..."}}
                if "message" in data:
                    return data["message"].get("content", "") or ""
                # OpenAI-compatible /v1/chat/completions fallback
                return data.get("choices", [{}])[0].get("message", {}).get("content", "")
        except Exception as exc:
            raise RuntimeError(f"Ollama call failed: {exc}") from exc

    def run_analysis(self, task: SDLCTask, project: SDLCProjectConfig) -> AgentResult:
        agent_cfg = project.agents.get("analysis", AgentConfig())
        system = agent_cfg.system_prompt or (
            "You are an expert software analyst. Analyse the task and produce a "
            "structured JSON report with keys: summary, functional_requirements, "
            "technical_requirements, affected_components, risks, open_questions."
        )
        user = (
            f"Project: {project.name}\n"
            f"Task title: {task.title}\n"
            f"Task description: {task.description}\n\n"
            + _feedback_text(task, "analysis")
            + "Produce only the JSON report, no extra text."
        )
        raw = self._chat(system, user, timeout=agent_cfg.timeout_seconds)
        # Try to parse JSON; fall back to plain text summary
        try:
            parsed = json.loads(raw)
            summary = parsed.get("summary", raw[:500])
        except (json.JSONDecodeError, TypeError):
            parsed = {}
            summary = raw[:500]

        return AgentResult(
            agent="analysis",
            status="completed",
            summary=str(summary),
            changes=[],
            tests={"executed": False, "passed": False, "results": []},
            recommendations=(parsed.get("recommendations", {}) if isinstance(parsed.get("recommendations", {}), dict) else {}),
            issues=[str(i) for i in (parsed.get("open_questions", []) if isinstance(parsed.get("open_questions", []), list) else [])],
            revision_request=None,
            raw_output=raw,
        )

    def run_agent(self, agent_key: str, task: SDLCTask, project: SDLCProjectConfig,
                  previous_results: dict) -> AgentResult:
        """Generic agent runner for backend / n8n / frontend / qa."""
        agent_cfg = project.agents.get(agent_key, AgentConfig())
        agent_labels = {
            "backend":  "backend developer",
            "n8n":      "n8n workflow engineer",
            "frontend": "frontend developer",
            "qa":       "QA engineer",
        }
        label = agent_labels.get(agent_key, agent_key)
        system = agent_cfg.system_prompt or (
            f"You are an expert {label}. Review the task and previous agent results, "
            "then produce a JSON report with keys: summary, changes (list of "
            "{file, description}), issues, recommendations."
        )
        prev_summary = "\n".join(
            f"- {k}: {v.get('summary','') if isinstance(v, dict) else str(v)[:200]}"
            for k, v in previous_results.items()
        )
        user = (
            f"Project: {project.name}\n"
            f"Task: {task.title}\n"
            f"Description: {task.description}\n"
            f"Previous agent results:\n{prev_summary}\n\n"
            + _feedback_text(task, agent_key)
            + "Produce only the JSON report."
        )
        raw = self._chat(system, user, timeout=agent_cfg.timeout_seconds)
        try:
            parsed = json.loads(raw)
            summary = parsed.get("summary", raw[:500])
            changes = parsed.get("changes", [])
            issues  = parsed.get("issues", [])
        except (json.JSONDecodeError, TypeError):
            parsed, summary, changes, issues = {}, raw[:500], [], []

        # Coerce recommendations to dict[str, list[str]] as required by AgentResult
        recs_raw = parsed.get("recommendations", {})
        if isinstance(recs_raw, dict):
            recommendations = {k: (v if isinstance(v, list) else [str(v)]) for k, v in recs_raw.items()}
        elif isinstance(recs_raw, list):
            recommendations = {"general": recs_raw} if recs_raw else {}
        else:
            recommendations = {}

        # Coerce changes to list[Change]
        clean_changes = []
        if isinstance(changes, list):
            for c in changes:
                if isinstance(c, dict) and "file" in c:
                    clean_changes.append(c)
                elif isinstance(c, str):
                    clean_changes.append({"file": c, "description": ""})

        # Ollama only returns text and writes nothing, so its file list is a proposal, not a change.
        proposed = [f"{c['file']}: {c.get('description', '')}".rstrip(": ") for c in clean_changes]
        if proposed:
            recommendations["proposed_changes"] = proposed

        return AgentResult(
            agent=agent_key,
            status="completed",
            summary=str(summary),
            changes=[],
            tests={"executed": False, "passed": False, "results": []},
            recommendations=recommendations,
            issues=[str(i) for i in (issues if isinstance(issues, list) else [])],
            revision_request=None,
            raw_output=raw,
        )


_ollama_runner = OllamaAgentRunner()


class SDLCProjectManager:
    """Manages SDLC project configurations.

    GitHub tokens never stay in project JSON: on save (and when an old file is loaded) they move
    into the encrypted SecretStore, and the config keeps only `github_config.token_saved`.
    """

    def __init__(self, data_dir: Path = Path("data/projects"), secrets: Optional[SecretStore] = None):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.secrets = secrets or SecretStore(self.data_dir.parent / "secrets.json")
        self.projects: Dict[str, SDLCProjectConfig] = {}
        self.load_projects()

    @staticmethod
    def _token_name(project_id: str, agent: str) -> str:
        return f"github:{project_id}:{agent}"

    def _move_tokens_to_store(self, project: SDLCProjectConfig) -> bool:
        """Store any token from the config in the secret store and blank it; True if one was moved.

        Each agent has one token slot, shared by its repository settings and its legacy github_config.
        """
        moved = False
        legacy_name = self._token_name(project.id, "repo")  # old project-level repository token
        legacy = self.secrets.get(legacy_name)
        for agent, config in project.agents.items():
            github, repository = config.github_config, config.repository
            name = self._token_name(project.id, agent)
            if github.pop("clear_token", False) is True or repository.clear_token:
                self.secrets.delete(name)
            for token in (github.get("github_token"), repository.github_token):
                if isinstance(token, str) and token.strip():
                    self.secrets.set(name, token.strip())
                    moved = True
            if legacy and repository.mode.value != "none" and not self.secrets.has(name):
                self.secrets.set(name, legacy)
                moved = True
            github["github_token"] = ""
            repository.github_token = ""
            repository.clear_token = False
            github["token_saved"] = repository.token_saved = self.secrets.has(name)
        if legacy:
            self.secrets.delete(legacy_name)
        return moved

    def github_token(self, project_id: str, agent: str) -> str:
        return self.secrets.get(self._token_name(project_id, agent)) or ""

    def _write_project(self, project: SDLCProjectConfig) -> None:
        project_file = self.data_dir / f"{project.id}.json"
        temp_file = project_file.with_name(f"{project.id}.{uuid.uuid4().hex}.tmp")
        try:
            temp_file.write_text(json.dumps(project.model_dump(), indent=2, ensure_ascii=False), encoding="utf-8")
            replace_with_retry(temp_file, project_file)
        except OSError as e:
            temp_file.unlink(missing_ok=True)
            raise RuntimeError(f"Could not save project {project.id}: {e}") from e

    def load_projects(self) -> None:
        """Load all project configurations; migrate plaintext tokens out of old files."""
        self.projects = {}
        if not self.data_dir.exists():
            return

        for project_file in self.data_dir.glob("*.json"):
            try:
                project = SDLCProjectConfig(**json.loads(_read_text_with_retry(project_file)))
            except (OSError, json.JSONDecodeError, ValueError) as e:
                print(f"Error loading project {project_file}: {e}")
                continue
            if self._move_tokens_to_store(project):
                self._write_project(project)
                print(f"[SDLC] Moved GitHub token(s) of project {project.id} into the secret store", flush=True)
            self.projects[project.id] = project

    def save_project(self, project: SDLCProjectConfig) -> None:
        """Save project configuration to disk (tokens go to the secret store, not the file)."""
        self._move_tokens_to_store(project)
        self._write_project(project)
        self.projects[project.id] = project

    def get_project(self, project_id: str) -> Optional[SDLCProjectConfig]:
        """Get project configuration by ID"""
        return self.projects.get(project_id)
    
    def list_projects(self) -> List[SDLCProjectConfig]:
        """List all project configurations"""
        return list(self.projects.values())
    
    def delete_project(self, project_id: str) -> bool:
        """Delete project configuration"""
        if project_id not in self.projects:
            return False
            
        project_file = self.data_dir / f"{project_id}.json"
        if project_file.exists():
            project_file.unlink()
        for agent in [*self.projects[project_id].agents, "repo"]:
            self.secrets.delete(self._token_name(project_id, agent))
        del self.projects[project_id]
        return True


class TaskConflictError(RuntimeError):
    """Raised when saving a task that another writer changed since it was loaded."""


def _read_text_with_retry(path: Path, attempts: int = 20, delay: float = 0.025) -> str:
    """Read a file, tolerating Windows' transient PermissionError while it is being replaced."""
    for attempt in range(attempts):
        try:
            return path.read_text(encoding="utf-8")
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(delay)
    return ""


class SDLCTaskManager:
    """Manages SDLC tasks and their lifecycle"""
    
    def __init__(self, data_dir: Path = Path("data/tasks")):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.active_tasks: Dict[str, SDLCTask] = {}
        self.task_workers: Dict[str, asyncio.Task] = {}
        self.live_states: Dict[str, TaskState] = {}
        # Set by the API layer: approves + integrates a finished task without a human (see sdlc_policy.can_auto_approve).
        # Called as `await auto_approver(task_id, reason) -> bool`; False leaves the task waiting for a human.
        self.auto_approver = None
        self.read_only = False  # True when another server process owns data_dir
        self._instance_lock: Optional[FileLock] = None
    
    AUTO_RETRY_DELAY = 5.0  # seconds * attempt number before an automatic stage retry (tests set 0)

    def generate_task_id(self) -> str:
        """Generate a unique task ID"""
        return f"TASK-{uuid.uuid4().hex[:8].upper()}"

    def next_task_id(self, prefix: str = "SDLC", start: int = 1001) -> str:
        """The next human-readable identifier for a workflow (SDLC-1001, SDLC-1002, ...), also the task's Git branch.

        Numbers never repeat: the counter lives next to the tasks and is also kept above every task folder
        that already exists. A cross-process lock makes concurrent creations get different numbers."""
        pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$", re.IGNORECASE)
        with FileLock(self.data_dir / ".task-counters.lock", timeout=10):
            counters_file = self.data_dir / ".task-counters.json"
            try:
                counters = json.loads(counters_file.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                counters = {}
            highest = max([int(counters.get(prefix, start - 1)), start - 1] +
                          [int(match.group(1)) for child in self.data_dir.iterdir() if (match := pattern.match(child.name))])
            counters[prefix] = highest + 1
            temporary = counters_file.with_suffix(".tmp")
            temporary.write_text(json.dumps(counters), encoding="utf-8")
            replace_with_retry(temporary, counters_file)
            return f"{prefix}-{highest + 1}"
    
    async def create_task(self, request: SDLCTaskRequest, 
                         project_config: SDLCProjectConfig,
                         base_task_state: TaskState) -> SDLCTask:
        """Create a new SDLC task"""
        
        # Generate unique task ID
        task_id = self.generate_task_id()
        
        # Create SDLC task
        sdlc_task = SDLCTask(
            base_task=base_task_state,
            title=request.title,
            description=request.description,
            priority=request.priority,
            tags=request.tags,
            sdlc_status=SDLCStatus.created,
            current_stage="analysis",
            current_agent="analysis",
            project_config_id=project_config.id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        policy.record_event(sdlc_task, "created", f"Task created: {request.title[:120]}", actor="human")
        # Save task to disk
        await self.save_task(sdlc_task)
        
        # Enqueue for analysis
        await self.enqueue_task(sdlc_task)
        
        return sdlc_task
    
    def _task_file(self, task_id: str) -> Path:
        return self.data_dir / task_id / "task.json"

    async def save_task(self, task: SDLCTask) -> None:
        """Write the task atomically, refusing to overwrite a newer version (TaskConflictError).

        `task.version` must equal the version on disk; it is incremented on success. The check and
        the write happen under a per-task file lock, so this also holds across server processes.
        """
        task_id = task.base_task.task_id
        task_file = self._task_file(task_id)
        task_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with FileLock(task_file.parent / ".lock"):
                if task_file.exists():
                    on_disk = json.loads(_read_text_with_retry(task_file)).get("version", 0)
                    if on_disk != task.version:
                        raise TaskConflictError(
                            f"Task {task_id} changed on disk (version {on_disk}, this copy {task.version}); reload and retry"
                        )
                task.version += 1
                temp_file = task_file.with_name(f"task.{uuid.uuid4().hex}.tmp")
                try:
                    temp_file.write_text(
                        json.dumps(task.model_dump(), indent=2, ensure_ascii=False, default=str), encoding="utf-8"
                    )
                    replace_with_retry(temp_file, task_file)
                except BaseException:
                    task.version -= 1
                    temp_file.unlink(missing_ok=True)
                    raise
        except (OSError, LockTimeout) as e:
            raise RuntimeError(f"Could not save task {task_id}: {e}") from e
        self.active_tasks[task_id] = task

    async def update_task(self, task_id: str, mutate: Callable[[SDLCTask], None],
                          attempts: int = 5) -> Optional[SDLCTask]:
        """Read the latest task, apply `mutate`, and save; retry when another writer got there first.

        Keep long-running work (git, agents) outside `mutate` and apply only its result here.
        """
        for attempt in range(attempts):
            task = await self.load_task(task_id)
            if task is None:
                return None
            mutate(task)
            try:
                await self.save_task(task)
                return task
            except TaskConflictError:
                if attempt == attempts - 1:
                    raise
        return None

    async def load_task(self, task_id: str) -> Optional[SDLCTask]:
        """Load task from disk"""
        task_dir = self.data_dir / task_id
        task_file = task_dir / "task.json"
        
        if not task_file.exists():
            return None
            
        try:
            data = json.loads(_read_text_with_retry(task_file))

            # Convert string dates back to datetime objects
            for date_field in ['created_at', 'updated_at', 'last_checkpoint']:
                if date_field in data and data[date_field]:
                    data[date_field] = datetime.fromisoformat(data[date_field].replace('Z', '+00:00'))
            
            # Load base task state
            base_task_data = data.pop('base_task')
            base_task = TaskState(**base_task_data)
            
            # Create SDLC task
            task = SDLCTask(base_task=base_task, **data)
            
            # Update in-memory cache
            self.active_tasks[task_id] = task
            return task
        except (OSError, json.JSONDecodeError, ValueError, KeyError) as e:
            print(f"Error loading task {task_id}: {e}")
            return None
    
    async def enqueue_task(self, task: SDLCTask) -> None:
        """Enqueue task for execution in appropriate stage queue"""
        # For now, transition to analyzing status
        task.sdlc_status = SDLCStatus.analyzing
        task.updated_at = datetime.now(timezone.utc)
        await self.save_task(task)
        
        # Start analysis (in real implementation, this would be queued)
        await self.execute_stage(task.base_task.task_id, "analysis")
    
    STAGE_STATUS = {
        "analysis": SDLCStatus.analyzing,
        "backend": SDLCStatus.backend_running,
        "n8n": SDLCStatus.n8n_running,
        "frontend": SDLCStatus.frontend_running,
        "qa": SDLCStatus.testing,
    }
    APPROVE_WORDS = {"approve", "approved", "ok", "yes", "تأیید", "تایید", "بله"}
    STOP_WORDS = {"stop", "توقف"}

    @property
    def inbox_dir(self) -> Path:
        return self.data_dir.parent / "human-inbox"

    def claim_data_dir(self) -> bool:
        """Become the only server that runs agents for this data directory (held until release)."""
        if self._instance_lock is None or not self._instance_lock.held:
            self._instance_lock = FileLock(self.data_dir / ".server.lock")
            self.read_only = not self._instance_lock.try_acquire()
        return not self.read_only

    def release_data_dir(self) -> None:
        if self._instance_lock is not None:
            self._instance_lock.release()

    def agent_token(self, project_id: str, stage: str) -> str:
        return SDLCProjectManager(self.data_dir.parent / "projects").github_token(project_id, stage)

    def persist_project(self, project: SDLCProjectConfig) -> None:
        """Write back what automation decided (repository name, URL, base branch) so the forms show it."""
        SDLCProjectManager(self.data_dir.parent / "projects").save_project(project)

    def agent_pid_file(self, task_id: str) -> Path:

        return self.data_dir / task_id / "agent.pid"

    async def recover_interrupted_tasks(self) -> List[str]:
        """On startup: find tasks whose stage was running when the server died, stop orphaned
        agent processes, and either resume the stage or ask a human what to do."""
        from .process_tools import stop_if_same_program

        running = set(self.STAGE_STATUS.values()) | {SDLCStatus.created, SDLCStatus.revision}
        recovered = []
        for task in await self.list_tasks():
            task_id = task.base_task.task_id
            if task.sdlc_status not in running or self.is_running(task_id):
                continue
            stage = task.current_stage or "analysis"
            note = ""
            pid_file = self.agent_pid_file(task_id)
            if pid_file.exists():
                try:
                    info = json.loads(pid_file.read_text(encoding="utf-8"))
                    outcome = stop_if_same_program(int(info["pid"]), str(info.get("image", "")))
                    note = f" The previous agent process (PID {info['pid']}): {outcome}."
                except (OSError, ValueError, KeyError) as exc:
                    note = f" Could not check the previous agent process: {exc}."
                pid_file.unlink(missing_ok=True)
            print(f"[SDLC] Recovering {task_id}: {stage} was interrupted.{note}", flush=True)
            recovered.append(task_id)

            project = self.load_project(task.project_config_id)
            if project and project.workflow.auto_resume_interrupted:
                task.transition_reason = f"Resumed {stage} after a server restart.{note}"
                await self.save_task(task)
                await self.execute_stage(task_id, stage, project)
                continue
            await self._ask_human(
                task, stage, "interrupted", f"Interrupted: the server restarted during {stage}",
                f"Taskloom stopped while the {stage} stage was running, so its result was lost. "
                f"Files the agent had already changed are still in its working folder.{note}\n\n"
                f"Answer 'resume' to run {stage} again (you may add guidance), or 'stop'.",
                ["resume", "stop"],
            )
        return recovered

    def load_project(self, project_id: str) -> Optional[SDLCProjectConfig]:
        return SDLCProjectManager(self.data_dir.parent / "projects").get_project(project_id)

    def is_running(self, task_id: str) -> bool:
        worker = self.task_workers.get(task_id)
        return worker is not None and not worker.done()

    def with_live_output(self, task: SDLCTask) -> SDLCTask:
        """Copy the in-memory transcript of a running agent onto a task loaded from disk."""
        live = self.live_states.get(task.base_task.task_id)
        if live is not None:
            task.base_task.live_output = live.live_output
            task.base_task.live_response = live.live_response
            task.base_task.step = live.step
        return task

    async def execute_stage(self, task_id: str, stage: str,
                            project: Optional[SDLCProjectConfig] = None) -> None:
        """Mark the task as running `stage` and start that stage's agent in the background."""
        if self.read_only:
            raise ValueError(f"Another Taskloom server owns {self.data_dir}; run SDLC stages from that server")
        if self.is_running(task_id):
            raise ValueError(f"Task {task_id} already has a stage running")
        task = await self.load_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        project = project or self.load_project(task.project_config_id)
        if not project:
            task.sdlc_status = SDLCStatus.failed
            task.transition_reason = f"Project {task.project_config_id} not found"
            await self.save_task(task)
            return

        task.current_stage = stage
        task.current_agent = stage
        if stage in self.STAGE_STATUS:
            task.sdlc_status = self.STAGE_STATUS[stage]
        task.updated_at = datetime.now(timezone.utc)
        policy.record_event(task, "stage_started", f"Started {stage}", stage, actor=stage)
        await self.save_task(task)
        print(f"[SDLC] Starting {stage} stage for task {task_id}", flush=True)

        worker = asyncio.create_task(self._run_agent_async(task_id, stage, project))
        self.task_workers[task_id] = worker
        worker.add_done_callback(lambda done, key=task_id: self.task_workers.get(key) is done and self.task_workers.pop(key, None))

    async def _run_agent_async(self, task_id: str, stage: str,
                               project: SDLCProjectConfig) -> None:
        """Background coroutine: run one stage with its configured runner and route the result."""
        from .sdlc_runner import resolve_runner, run_cli_stage

        task = await self.load_task(task_id)
        if not task:
            return

        try:
            agent_cfg = project.agents.get(stage, AgentConfig())
            runner = resolve_runner(agent_cfg, project.stage_path(stage))
            print(f"[SDLC] Running {stage} for {task_id} with {runner.value}", flush=True)
            self.live_states[task_id] = task.base_task

            if runner == StageRunner.ollama:
                loop = asyncio.get_running_loop()
                if stage == "analysis":
                    result = await loop.run_in_executor(None, _ollama_runner.run_analysis, task, project)
                else:
                    previous = {k: v.model_dump() for k, v in task.agent_results.items()}
                    result = await loop.run_in_executor(None, _ollama_runner.run_agent, stage, task, project, previous)
            else:
                result = await run_cli_stage(stage, task, project, agent_cfg, runner, self.agent_pid_file(task_id),
                                             self.agent_token(project.id, stage), self.persist_project)

            print(f"[SDLC] {stage} finished for {task_id}: {result.status} - {result.summary[:120]}", flush=True)

            # The worker must not count as "running" while it schedules the next stage.
            self.task_workers.pop(task_id, None)
            self.live_states.pop(task_id, None)
            for attempt in range(5):
                # Reload: the task may have changed (e.g. a GitHub action) while the agent ran.
                fresh_task = await self.load_task(task_id) or task
                # While the analyst answers another stage's question, keep the original analysis result.
                fresh_task.agent_results["analysis_consult" if stage == "analysis" and fresh_task.consult_question_id else stage] = result
                fresh_task.base_task.codex_thread_id = task.base_task.codex_thread_id
                for key, repo in task.repos.items():
                    fresh_task.repos.setdefault(key, repo)
                fresh_task.updated_at = datetime.now(timezone.utc)
                try:
                    await self._route_result(fresh_task, stage, result, project)
                    break
                except TaskConflictError:
                    if attempt == 4:
                        raise

        except Exception as exc:
            import traceback
            print(f"[SDLC] Agent {stage} error for {task_id}: {exc}", flush=True)
            traceback.print_exc()

            current = await self.load_task(task_id)
            if current is not None and policy.retries_left(current, stage, project) > 0:
                self.task_workers.pop(task_id, None)
                self.live_states.pop(task_id, None)
                await self._fail_or_retry(current, stage, project, f"{stage} error: {exc}")
            else:
                def mark_failed(failed: SDLCTask) -> None:
                    failed.sdlc_status = SDLCStatus.failed
                    failed.transition_reason = f"{stage} error: {exc}"
                    failed.updated_at = datetime.now(timezone.utc)
                    policy.record_event(failed, "stage_failed", f"{stage} error: {exc}", stage, actor=stage,
                                        duration_seconds=policy.stage_duration(failed, stage))
                    policy.record_event(failed, "escalated", "The stage failed; a human has to decide what to do", stage)

                await self.update_task(task_id, mark_failed)
        finally:
            if self.live_states.get(task_id) is task.base_task:
                self.live_states.pop(task_id, None)

    async def _route_result(self, task: SDLCTask, stage: str, result: AgentResult,
                            project: SDLCProjectConfig) -> None:
        """Save a finished stage's result and move the workflow on accordingly."""
        question = result.human_intervention.description if result.human_intervention else result.summary
        kind = result.human_intervention.context.get("kind", "agent_question") if result.human_intervention else "agent_question"
        if (stage == "analysis" and task.consult_question_id and kind != "agent_unavailable"
                and result.status in ("completed", "needs_human")):
            await self._finish_analyst_consult(task, result, question, project)
        elif result.status == "completed":
            policy.record_event(task, "stage_completed", result.summary.strip().splitlines()[0][:200] if result.summary.strip() else "",
                                stage, actor=stage, duration_seconds=policy.stage_duration(task, stage))
            await self.save_task(task)
            await self._advance_or_complete(task, project)
        elif result.status == "needs_human":
            if kind == "agent_unavailable":
                await self._ask_human(task, stage, kind, f"{stage}: agent unavailable", question, ["resume", "stop"])
            elif self._analyst_can_answer(task, stage, project):
                await self._consult_analyst(task, stage, question, project)
            else:
                await self._ask_human(task, stage, "agent_question", f"{stage} needs a human decision", question, ["stop"])
        elif result.status == "needs_revision" and result.revision_request:
            await self._request_revision(task, stage, result.revision_request, project)
        else:  # blocked / failed / needs_revision without details
            await self._fail_or_retry(task, stage, project, f"{stage} {result.status}: " + ("; ".join(result.issues) or result.summary))

    async def _fail_or_retry(self, task: SDLCTask, stage: str, project: SDLCProjectConfig, reason: str) -> None:
        """A stage failed: re-run it automatically while the project's retry budget lasts, else escalate to a human."""
        task_id = task.base_task.task_id
        duration = policy.stage_duration(task, stage)
        policy.record_event(task, "stage_failed", reason, stage, actor=stage, duration_seconds=duration)
        if policy.retries_left(task, stage, project) > 0:
            attempt = task.stage_attempts.get(stage, 0) + 1
            task.stage_attempts[stage] = attempt
            budget = project.workflow.auto_retry_failed_stages
            task.transition_reason = f"{reason} - automatic retry {attempt}/{budget}"
            policy.record_event(task, "auto_retry", f"Automatic retry {attempt}/{budget} of {stage}: {reason[:200]}", stage)
            await self.save_task(task)
            await asyncio.sleep(self.AUTO_RETRY_DELAY * attempt)
            await self.execute_stage(task_id, stage, project)
            return
        task.sdlc_status = SDLCStatus.failed
        task.transition_reason = reason
        policy.record_event(task, "escalated", "Out of automatic retries; a human has to decide what to do"
                            if project.workflow.auto_retry_failed_stages else "The stage failed; a human has to decide what to do", stage)
        await self.save_task(task)

    MAX_ANALYST_QUESTIONS = 4  # per asking stage and task; after that the stage's question goes straight to a human

    def _analyst_can_answer(self, task: SDLCTask, stage: str, project: SDLCProjectConfig) -> bool:
        """Only the analyst talks to humans: every other stage asks the analyst first."""
        from .sdlc_runner import resolve_runner
        if stage == "analysis" or "analysis" not in self.enabled_stages(project):
            return False
        if resolve_runner(project.agents.get("analysis", AgentConfig()), project.stage_path("analysis")) == StageRunner.ollama:
            return False  # a text-only report cannot answer a question
        return sum(1 for q in task.stage_questions if q.asking_stage == stage) < self.MAX_ANALYST_QUESTIONS

    async def _consult_analyst(self, task: SDLCTask, stage: str, question: str, project: SDLCProjectConfig) -> None:
        """A stage is stuck on a question: record it and let the analysis stage answer it."""
        asked = StageQuestion(id=f"Q-{uuid.uuid4().hex[:6].upper()}", asking_stage=stage, question=question.strip())
        task.stage_questions.append(asked)
        task.consult_question_id = asked.id
        task.previous_status = task.sdlc_status
        task.transition_reason = f"{stage} asked the analyst: {asked.question[:300]}"
        task.updated_at = datetime.now(timezone.utc)
        await self.save_task(task)
        print(f"[SDLC] {task.base_task.task_id}: {stage} asks the analyst ({asked.id})", flush=True)
        await self.execute_stage(task.base_task.task_id, "analysis", project)

    async def _finish_analyst_consult(self, task: SDLCTask, result: AgentResult, question: str,
                                      project: SDLCProjectConfig) -> None:
        """The analyst replied to a stage's question: pass the answer back, or ask a human what it cannot answer."""
        asked = next((q for q in task.stage_questions if q.id == task.consult_question_id), None)
        if asked is None:
            task.consult_question_id = ""
            await self.save_task(task)
            await self._advance_or_complete(task, project)
            return
        if result.status == "completed":
            asked.answer = result.summary.strip()
            asked.status = "answered"
            asked.answered_by = "human" if any(
                item.status == "responded" and item.context.get("consult_id") == asked.id
                for item in task.human_interventions
            ) else "analysis"
            task.consult_question_id = ""
            task.transition_reason = f"Analyst answered {asked.asking_stage}; re-running {asked.asking_stage}"
            task.updated_at = datetime.now(timezone.utc)
            await self.save_task(task)
            await self.execute_stage(task.base_task.task_id, asked.asking_stage, project)
            return
        # The analyst could not answer everything: the human operator gets what is still open.
        await self._ask_human(
            task, "analysis", "agent_question", f"analysis needs a human answer (question from {asked.asking_stage})",
            f"Question from the {asked.asking_stage} stage:\n{asked.question}\n\nThe analyst could not answer:\n{question}",
            ["stop"], {"consult_id": asked.id},
        )

    @staticmethod
    def enabled_stages(project: SDLCProjectConfig) -> List[str]:
        stages = project.workflow.stages or ["analysis", "backend", "n8n", "frontend", "qa"]
        return [stage for stage in stages if project.agents.get(stage, AgentConfig()).enabled]

    async def _request_revision(self, task: SDLCTask, stage: str, request: RevisionRequest,
                                project: SDLCProjectConfig) -> None:
        """Send the pipeline back to the stage that must fix something, within the revision budget."""
        target = request.target_agent or stage
        request.target_agent = target
        task.revisions.append(request)
        limit = project.workflow.max_revision_attempts
        if target not in self.enabled_stages(project):
            await self._ask_human(
                task, stage, "revision_limit", f"{stage} asked for a revision of an unknown stage '{target}'",
                f"{request.reason}\n\n{request.description}\n\nAnswer with guidance to re-run {stage}, or 'stop'.", ["stop"],
            )
            return
        if task.revision_count >= limit:
            await self._ask_human(
                task, stage, "revision_limit", f"Revision limit reached ({limit})",
                f"{stage} still asks {target} to revise: {request.reason}\n\n"
                f"Answer with guidance to re-run {stage}, or 'stop'.", ["stop"],
            )
            return
        task.revision_count += 1
        task.previous_status = task.sdlc_status
        task.sdlc_status = SDLCStatus.revision
        task.transition_reason = f"Revision {task.revision_count}/{limit}: {stage} -> {target}: {request.reason}"
        task.updated_at = datetime.now(timezone.utc)
        await self.save_task(task)
        print(f"[SDLC] {task.transition_reason}", flush=True)
        await self.execute_stage(task.base_task.task_id, target, project)

    async def _advance_or_complete(self, task: SDLCTask,
                                   project: SDLCProjectConfig) -> None:
        """After task.current_stage completed: gate, start the next enabled stage, or finish."""
        if (task.current_stage == "analysis" and project.workflow.require_analysis_approval
                and task.sdlc_status != SDLCStatus.analysis_approved):
            analysis = task.agent_results.get("analysis")
            clean, why = policy.analysis_is_clean(task) if project.workflow.auto_analysis_approval else (False, "")
            if clean and any(r.requesting_agent == "human" and r.target_agent == "analysis" for r in task.revisions):
                clean, why = False, "a human objected to the earlier analysis and must review the new one"
            if clean:
                policy.record_event(task, "auto_approved", f"Analysis approved automatically: {why}", "analysis")
                task.sdlc_status = SDLCStatus.analysis_approved
                task.transition_reason = "Analysis approved automatically"
                await self.save_task(task)  # the next stage reloads the task from disk
            else:
                if project.workflow.auto_analysis_approval:
                    policy.record_event(task, "escalated", f"Analysis needs a human: {why}", "analysis")
                await self._ask_human(
                    task, "analysis", "analysis_approval", "Approve the analysis",
                    (analysis.summary if analysis else "")
                    + (f"\n\n(Automatic approval was not possible: {why}.)" if why else "")
                    + "\n\nApprove to start development, write feedback to redo the analysis, or 'stop'.",
                    ["approve", "stop"],
                )
                return

        stages = project.workflow.stages or ["analysis", "backend", "n8n", "frontend", "qa"]
        try:
            idx = stages.index(task.current_stage)
        except ValueError:
            idx = -1
        next_stage = next(
            (stage for stage in stages[idx + 1:] if project.agents.get(stage, AgentConfig()).enabled), None
        )
        if next_stage:
            print(f"[SDLC] Advancing {task.base_task.task_id} to {next_stage}", flush=True)
            await self.execute_stage(task.base_task.task_id, next_stage, project)
            return

        task.previous_status = task.sdlc_status
        task.risk = policy.assess_risk(task)
        policy.record_event(task, "all_stages_completed", f"All stages finished; risk {task.risk.level} (score {task.risk.score})")
        auto_ok, auto_why = policy.can_auto_approve(task, project)
        if self.auto_approver is not None and auto_ok:
            # Taskloom decides: park the task where a human would approve it, then run exactly that approval.
            task.sdlc_status = SDLCStatus.pending_approval
            task.transition_reason = f"All stages finished; approving automatically ({auto_why})"
            task.updated_at = datetime.now(timezone.utc)
            await self.save_task(task)
            approved, detail = False, ""
            try:
                approved = bool(await self.auto_approver(task.base_task.task_id, auto_why))
            except Exception as exc:  # the human gate is the safe fallback for anything unexpected
                detail = str(exc)
            if not approved:
                await self.update_task(task.base_task.task_id, lambda latest: policy.record_event(
                    latest, "escalated", "Automatic approval did not complete; waiting for a human" + (f": {detail}" if detail else "")))
            return
        if project.workflow.require_final_human_approval:
            task.sdlc_status = SDLCStatus.pending_approval
            task.transition_reason = "All stages finished; waiting for final approval"
            if project.workflow.auto_final_approval:
                policy.record_event(task, "escalated", f"Final approval needs a human: {auto_why}")
        else:
            task.sdlc_status = SDLCStatus.done
            task.transition_reason = "All stages finished"
        task.updated_at = datetime.now(timezone.utc)
        print(f"[SDLC] Task {task.base_task.task_id}: {task.transition_reason}", flush=True)
        await self.save_task(task)

    async def transition_to_next_stage(self, task_id: str) -> bool:
        """Treat the current stage as finished and continue the workflow."""
        task = await self.load_task(task_id)
        if not task:
            return False
        project = self.load_project(task.project_config_id)
        if not project:
            return False
        await self._advance_or_complete(task, project)
        return True

    async def _ask_human(self, task: SDLCTask, agent: str, kind: str, reason: str, description: str,
                         response_options: List[str], context: Optional[dict] = None) -> str:
        """Put a question in the human inbox and park the task in human_review."""
        intervention = HumanIntervention(
            id=f"INT-{uuid.uuid4().hex[:8].upper()}",
            task_id=task.base_task.task_id,
            requesting_agent=agent,
            reason=reason,
            description=description.strip(),
            context={**(context or {}), "kind": kind, "stage": agent},
            response_options=response_options,
        )
        task.human_interventions.append(intervention)
        policy.record_event(task, "escalated", f"Waiting for a human: {reason}", agent)
        task.previous_status = task.sdlc_status
        task.sdlc_status = SDLCStatus.human_review
        task.transition_reason = reason
        task.updated_at = datetime.now(timezone.utc)
        # Save first: if this conflicts, the caller retries and no orphan inbox item is left behind.
        await self.save_task(task)
        pending = self.inbox_dir / "pending"
        pending.mkdir(parents=True, exist_ok=True)
        (pending / f"{intervention.id}.json").write_text(
            json.dumps(intervention.model_dump(), indent=2, ensure_ascii=False, default=str), encoding="utf-8"
        )
        return intervention.id

    async def create_human_intervention(self, task_id: str, agent: str,
                                        reason: str, description: str,
                                        context: dict, response_options: List[str]) -> str:
        """Create a human intervention request (API entry point)."""
        task = await self.load_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        return await self._ask_human(task, agent, context.get("kind", "manual"), reason, description,
                                     response_options, context)

    MAX_FEEDBACK_CHARS = 4000

    async def send_back_to_analysis(self, task_id: str, feedback: str, actor: str = "human") -> SDLCTask:
        """A human found a problem: record the opinion and run the analyst again with it as binding input.

        The task then goes through the normal analysis approval again, and Taskloom never approves that analysis
        by itself (the human objected, so a human looks at the new result). Refused while a stage is running and
        once the work has been merged into develop (that needs a new task, not a re-analysis)."""
        if self.read_only:
            raise ValueError(f"Another Taskloom server owns {self.data_dir}; send the task back from that server")
        feedback = (feedback or "").strip()
        if not feedback:
            raise ValueError("Write what is wrong first: the analyst needs your opinion")
        if len(feedback) > self.MAX_FEEDBACK_CHARS:
            raise ValueError(f"The opinion is too long ({len(feedback)} characters; the limit is {self.MAX_FEEDBACK_CHARS})")
        if self.is_running(task_id):
            raise ValueError(f"Task {task_id} has a stage running; wait for it to finish")
        task = await self.load_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        if any(repo.integration and repo.integration.merged_into_develop for repo in task.repos.values()):
            raise ValueError("This task is already merged into develop; create a new task for the change")
        project = self.load_project(task.project_config_id)
        if not project or "analysis" not in self.enabled_stages(project):
            raise ValueError("The project has no enabled analysis stage to send the task back to")

        # Open questions to a human are answered by this opinion: close them so the inbox has no stale duplicate.
        pending = self.inbox_dir / "pending"
        resolved = self.inbox_dir / "resolved"
        for item in task.human_interventions:
            if item.status != "pending":
                continue
            item.status = "superseded"
            item.response = feedback
            item.responded_at = datetime.now(timezone.utc)
            source = pending / f"{item.id}.json"
            if source.exists():
                resolved.mkdir(parents=True, exist_ok=True)
                (resolved / f"{item.id}.json").write_text(
                    json.dumps(item.model_dump(), indent=2, ensure_ascii=False, default=str), encoding="utf-8")
                source.unlink(missing_ok=True)

        task.revisions.append(RevisionRequest(
            requesting_agent="human", target_agent="analysis", reason=feedback, description=feedback, priority="high"))
        task.previous_status = task.sdlc_status
        task.sdlc_status = SDLCStatus.revision
        task.transition_reason = "A human found a problem and sent the task back to analysis"
        policy.record_event(task, "human_response", f"Sent back to analysis: {feedback[:200]}", "analysis", actor=actor)
        task.updated_at = datetime.now(timezone.utc)
        await self.save_task(task)
        await self.execute_stage(task_id, "analysis", project)
        return await self.load_task(task_id) or task

    async def delete_task(self, task_id: str) -> bool:
        """Delete a task's folder and its inbox items. Refuses while one of its stages is running."""
        if self.is_running(task_id):
            raise ValueError(f"Task {task_id} has a stage running; wait for it to finish before deleting")
        task_dir = self.data_dir / task_id
        if not (task_dir / "task.json").exists():
            return False
        for folder in ("pending", "resolved"):
            for item in (self.inbox_dir / folder).glob("*.json"):
                try:
                    if json.loads(item.read_text(encoding="utf-8")).get("task_id") == task_id:
                        item.unlink(missing_ok=True)
                except (OSError, json.JSONDecodeError):
                    continue
        for attempt in range(20):  # Windows: a reader may briefly hold a file open
            try:
                shutil.rmtree(task_dir)
                break
            except FileNotFoundError:
                break
            except PermissionError:
                if attempt == 19:
                    raise
                await asyncio.sleep(0.05)
        self.active_tasks.pop(task_id, None)
        self.live_states.pop(task_id, None)
        return True

    async def project_task_ids(self, project_id: str) -> List[str]:
        return [task.base_task.task_id for task in await self.list_tasks(project_filter=project_id)]

    async def delete_project_tasks(self, project_id: str) -> List[str]:
        """Delete every task of a project; nothing is deleted if any of them is running."""
        task_ids = await self.project_task_ids(project_id)
        running = [task_id for task_id in task_ids if self.is_running(task_id)]
        if running:
            raise ValueError(f"Tasks still running: {', '.join(running)}; wait for them before deleting the project")
        return [task_id for task_id in task_ids if await self.delete_task(task_id)]

    def list_pending_interventions(self) -> List[HumanIntervention]:
        interventions = []
        for path in (self.inbox_dir / "pending").glob("*.json"):
            try:
                interventions.append(HumanIntervention(**json.loads(path.read_text(encoding="utf-8"))))
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                print(f"Error loading intervention {path}: {exc}")
        interventions.sort(key=lambda item: item.created_at)
        return interventions

    async def submit_human_response(self, intervention_id: str, response: str) -> bool:
        """Record a human answer and resume the workflow accordingly."""
        pending_file = self.inbox_dir / "pending" / f"{intervention_id}.json"
        # Claim the item atomically so a double click (or a second server) cannot answer it twice.
        claimed = pending_file.with_name(f"{intervention_id}.{uuid.uuid4().hex}.claimed")
        try:
            os.rename(pending_file, claimed)
        except OSError:
            return False
        try:
            intervention = HumanIntervention(**json.loads(claimed.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print(f"Error reading intervention {intervention_id}: {exc}")
            os.rename(claimed, pending_file)
            return False

        intervention.response = response.strip()
        intervention.responded_at = datetime.now(timezone.utc)
        intervention.status = "responded"
        resolved = self.inbox_dir / "resolved"
        resolved.mkdir(parents=True, exist_ok=True)
        (resolved / f"{intervention_id}.json").write_text(
            json.dumps(intervention.model_dump(), indent=2, ensure_ascii=False, default=str), encoding="utf-8"
        )
        claimed.unlink()

        task = await self.load_task(intervention.task_id)
        if not task:
            return True
        if any(item.id == intervention_id for item in task.human_interventions):
            task.human_interventions = [
                intervention if item.id == intervention_id else item for item in task.human_interventions
            ]
        else:
            task.human_interventions.append(intervention)

        answer = intervention.response.casefold()
        kind = intervention.context.get("kind", "manual")
        stage = intervention.context.get("stage") or intervention.requesting_agent
        policy.record_event(task, "human_response", f"{kind}: {intervention.response[:200]}", stage, actor="human")
        task.updated_at = datetime.now(timezone.utc)

        if answer in self.STOP_WORDS:
            task.sdlc_status = SDLCStatus.failed
            task.transition_reason = f"Stopped by a human at {stage}"
            await self.save_task(task)
            return True

        project = self.load_project(task.project_config_id)
        if kind == "manual" or not project:
            await self.save_task(task)
            return True

        if kind == "analysis_approval" and answer in self.APPROVE_WORDS:
            task.sdlc_status = SDLCStatus.analysis_approved
            task.transition_reason = "Analysis approved by a human"
            await self.save_task(task)
            await self._advance_or_complete(task, project)
            return True

        # Feedback on the analysis, an answer to an agent's question, or guidance after the
        # revision limit: re-run that stage; the answer is part of its next prompt.
        task.transition_reason = f"Human answered {stage}; re-running it"
        await self.save_task(task)
        await self.execute_stage(task.base_task.task_id, stage, project)
        return True

    async def list_tasks(self, status_filter: Optional[str] = None,
                        project_filter: Optional[str] = None) -> List[SDLCTask]:
        """List tasks with optional filters"""
        tasks = []
        
        for task_dir in self.data_dir.iterdir():
            if task_dir.is_dir():
                task = await self.load_task(task_dir.name)
                if task:
                    # Apply filters
                    if status_filter and task.sdlc_status.value != status_filter:
                        continue
                    if project_filter and task.project_config_id != project_filter:
                        continue
                    tasks.append(task)
        
        # Sort by creation date (newest first)
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return tasks
# ===== OLLAMA CODING AGENT =====

class OllamaCodingAgent:
    """Coding agent that uses Ollama with tool calling to edit files"""
    
    def __init__(self, base_url: str = OLLAMA_BASE_URL, model: str = OLLAMA_MODEL):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.resolution_service = ModelResolutionService()
        self.tools = self._create_tools()
    
    def _create_tools(self) -> list[dict]:
        """Create tool definitions for Ollama"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read the contents of a file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Path to the file relative to project root"
                            }
                        },
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_files",
                    "description": "List files in the project directory",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Directory path relative to project root (optional)",
                                "default": "."
                            },
                            "recursive": {
                                "type": "boolean",
                                "description": "Whether to list recursively",
                                "default": False
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Create or modify a file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Path to the file relative to project root"
                            },
                            "content": {
                                "type": "string",
                                "description": "File content to write"
                            },
                            "append": {
                                "type": "boolean",
                                "description": "Whether to append to existing file",
                                "default": False
                            }
                        },
                        "required": ["path", "content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "delete_file",
                    "description": "Delete a file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Path to the file relative to project root"
                            }
                        },
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_files",
                    "description": "Search for text in files",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pattern": {
                                "type": "string",
                                "description": "Text pattern to search for"
                            },
                            "path": {
                                "type": "string",
                                "description": "Directory path to search in (optional)",
                                "default": "."
                            }
                        },
                        "required": ["pattern"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "run_command",
                    "description": "Run a shell command (restricted to safe commands)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "Command to run"
                            },
                            "working_dir": {
                                "type": "string",
                                "description": "Working directory (optional)",
                                "default": "."
                            }
                        },
                        "required": ["command"]
                    }
                }
            }
        ]
    
    def _is_safe_command(self, command: str) -> bool:
        """Check if a command is safe to run"""
        safe_prefixes = [
            "npm ", "yarn ", "pnpm ",
            "python ", "python3 ", "pip ", "pip3 ",
            "node ", "npx ",
            "git status", "git diff", "git log", "git show",
            "go ", "cargo ", "dotnet ",
            "make ", "cmake "
        ]
        command_lower = command.lower()
        return any(command_lower.startswith(prefix) for prefix in safe_prefixes)
    
    async def _call_ollama_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        workdir: Path,
        max_iterations: int = 10
    ) -> tuple[str, list[Change]]:
        """Call Ollama with tool calling support"""
        import urllib.request
        import json
        
        changes = []
        iteration = 0
        
        while iteration < max_iterations:
            payload = {
                "model": self.model,
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto",
                "stream": False,
                "temperature": 0.3,
            }
            
            try:
                req = urllib.request.Request(
                    f"{self.base_url}/api/chat",
                    data=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                
                with urllib.request.urlopen(req, timeout=300) as resp:
                    response = json.loads(resp.read())
                    
                    # Check for tool calls
                    message = response.get("message", {})
                    tool_calls = message.get("tool_calls", [])
                    
                    if tool_calls:
                        # Execute tool calls
                        for tool_call in tool_calls:
                            tool_name = tool_call.get("function", {}).get("name")
                            tool_args = json.loads(tool_call.get("function", {}).get("arguments", "{}"))
                            
                            # Execute tool
                            result = await self._execute_tool(tool_name, tool_args, workdir)
                            
                            # Record file changes
                            if tool_name == "write_file":
                                file_path = tool_args.get("path")
                                if file_path:
                                    changes.append(Change(
                                        file=file_path,
                                        description="Modified by Ollama agent",
                                        kind="created" if not (workdir / file_path).exists() else "modified"
                                    ))
                            elif tool_name == "delete_file":
                                file_path = tool_args.get("path")
                                if file_path:
                                    changes.append(Change(
                                        file=file_path,
                                        description="Deleted by Ollama agent",
                                        kind="deleted"
                                    ))
                            
                            # Add tool result to messages
                            messages.append({
                                "role": "tool",
                                "content": json.dumps(result),
                                "tool_call_id": tool_call.get("id")
                            })
                    else:
                        # No more tool calls, return final response
                        final_response = message.get("content", "")
                        return final_response, changes
                    
            except Exception as exc:
                raise RuntimeError(f"Ollama tool call failed: {exc}") from exc
            
            iteration += 1
        
        raise RuntimeError(f"Maximum iterations ({max_iterations}) reached")
    
    async def _execute_tool(self, tool_name: str, args: dict, workdir: Path) -> dict:
        """Execute a tool call"""
        try:
            if tool_name == "read_file":
                file_path = workdir / args["path"]
                if not file_path.exists():
                    return {"error": f"File not found: {args['path']}"}
                if not file_path.is_relative_to(workdir):
                    return {"error": "Path traversal attempt blocked"}
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                return {"content": content}
            
            elif tool_name == "list_files":
                dir_path = workdir / args.get("path", ".")
                if not dir_path.exists():
                    return {"error": f"Directory not found: {args.get('path', '.')}"}
                if not dir_path.is_relative_to(workdir):
                    return {"error": "Path traversal attempt blocked"}
                
                files = []
                recursive = args.get("recursive", False)
                
                if recursive:
                    for root, dirs, filenames in os.walk(dir_path):
                        # Skip hidden directories
                        dirs[:] = [d for d in dirs if not d.startswith(".")]
                        for filename in filenames:
                            if not filename.startswith("."):
                                rel_path = (Path(root) / filename).relative_to(workdir)
                                files.append(str(rel_path))
                else:
                    for item in dir_path.iterdir():
                        if not item.name.startswith("."):
                            rel_path = item.relative_to(workdir)
                            files.append(str(rel_path))
                
                return {"files": files}
            
            elif tool_name == "write_file":
                file_path = workdir / args["path"]
                if not file_path.is_relative_to(workdir):
                    return {"error": "Path traversal attempt blocked"}
                
                # Create parent directories
                file_path.parent.mkdir(parents=True, exist_ok=True)
                
                content = args["content"]
                if args.get("append", False) and file_path.exists():
                    with file_path.open("a", encoding="utf-8") as f:
                        f.write(content)
                else:
                    file_path.write_text(content, encoding="utf-8")
                
                return {"success": True, "path": str(file_path.relative_to(workdir))}
            
            elif tool_name == "delete_file":
                file_path = workdir / args["path"]
                if not file_path.is_relative_to(workdir):
                    return {"error": "Path traversal attempt blocked"}
                if not file_path.exists():
                    return {"error": f"File not found: {args['path']}"}
                
                file_path.unlink()
                return {"success": True, "path": str(file_path.relative_to(workdir))}
            
            elif tool_name == "search_files":
                search_path = workdir / args.get("path", ".")
                if not search_path.exists():
                    return {"error": f"Path not found: {args.get('path', '.')}"}
                if not search_path.is_relative_to(workdir):
                    return {"error": "Path traversal attempt blocked"}
                
                pattern = args["pattern"]
                results = []
                
                for root, dirs, filenames in os.walk(search_path):
                    # Skip hidden directories
                    dirs[:] = [d for d in dirs if not d.startswith(".")]
                    for filename in filenames:
                        if filename.startswith("."):
                            continue
                        file_path = Path(root) / filename
                        try:
                            content = file_path.read_text(encoding="utf-8", errors="ignore")
                            if pattern in content:
                                rel_path = file_path.relative_to(workdir)
                                results.append({
                                    "file": str(rel_path),
                                    "matches": content.count(pattern)
                                })
                        except:
                            continue
                
                return {"results": results}
            
            elif tool_name == "run_command":
                if not self._is_safe_command(args["command"]):
                    return {"error": "Command not allowed for security reasons"}
                
                working_dir = workdir / args.get("working_dir", ".")
                if not working_dir.is_relative_to(workdir):
                    return {"error": "Path traversal attempt blocked"}
                
                import subprocess
                try:
                    result = subprocess.run(
                        args["command"],
                        shell=True,
                        cwd=str(working_dir),
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    return {
                        "exit_code": result.returncode,
                        "stdout": result.stdout,
                        "stderr": result.stderr
                    }
                except subprocess.TimeoutExpired:
                    return {"error": "Command timeout"}
                except Exception as e:
                    return {"error": str(e)}
            
            else:
                return {"error": f"Unknown tool: {tool_name}"}
                
        except Exception as exc:
            return {"error": str(exc)}
    
    async def run_stage(
        self,
        stage: str,
        task: SDLCTask,
        project: SDLCProjectConfig,
        config: AgentConfig,
        workdir: Path
    ) -> AgentResult:
        """Run an SDLC stage with Ollama coding agent"""
        # Resolve model for this stage
        model_name = self.resolution_service.resolve_model_for_stage(stage, project)
        self.model = model_name
        
        # Get system prompt for this stage
        system_prompt = config.system_prompt or self._get_default_system_prompt(stage)
        
        # Build initial messages
        from .sdlc_runner import build_stage_prompt
        user_prompt = build_stage_prompt(stage, task, project, config, workdir)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            # Run Ollama with tool calling
            final_response, changes = await self._call_ollama_with_tools(
                messages, self.tools, workdir
            )
            
            # Parse agent report
            from .sdlc_runner import parse_agent_report
            report = parse_agent_report(final_response)
            
            # Create AgentResult
            return AgentResult(
                agent=stage,
                status=report.get("status", "completed"),
                summary=report.get("summary", final_response[:500]),
                changes=changes,
                tests=TestResults(),
                recommendations=report.get("recommendations", {}),
                issues=report.get("issues", []),
                raw_output=final_response
            )
            
        except Exception as exc:
            return AgentResult(
                agent=stage,
                status="failed",
                summary=f"Ollama coding agent failed: {exc}",
                changes=[],
                tests=TestResults(),
                recommendations={},
                issues=[str(exc)],
                raw_output=""
            )
    
    def _get_default_system_prompt(self, stage: str) -> str:
        """Get default system prompt for a stage"""
        prompts = {
            "analysis": "You are an expert software analyst. Analyze requirements and create detailed specifications.",
            "backend": "You are an expert backend developer. Write clean, efficient, and secure backend code.",
            "frontend": "You are an expert frontend developer. Create responsive, accessible, and user-friendly interfaces.",
            "n8n": "You are an expert n8n workflow engineer. Design efficient and reliable automation workflows.",
            "qa": "You are an expert QA engineer. Write comprehensive tests and ensure software quality."
        }
        return prompts.get(stage, "You are a software development assistant. Complete the task professionally.")


# ===== TEAM WORKFLOW GATE FUNCTIONS =====

def get_next_workflow_stage(current_stage: str, project: SDLCProjectConfig) -> str | None:
    """Determine the next stage in the workflow based on current stage and project config.
    
    Handles review gates and maintains workflow sequence.
    """
    workflow = project.workflow
    stages = workflow.stages
    
    try:
        current_idx = stages.index(current_stage)
    except ValueError:
        # If current stage not in config, try common progression
        if current_stage == "analysis_approved":
            return "backend_running"
        if current_stage == "backend_running":
            return "backend_review" if "backend_review" in stages else "frontend_running"
        if current_stage == "backend_review":
            return "frontend_running"
        if current_stage == "frontend_running":
            return "frontend_review" if "frontend_review" in stages else "qa_running"
        if current_stage == "frontend_review":
            return "qa_running"
        if current_stage == "qa_running":
            return "qa_review" if "qa_review" in stages else "analyst_final_review"
        if current_stage == "qa_review":
            return "analyst_final_review"
        if current_stage == "analyst_final_review":
            return "po_pending_approval" if workflow.require_po_approval else None
        if current_stage == "po_pending_approval":
            return None  # Waiting for PO approval
        return None
    
    # If current stage is last, return None
    if current_idx >= len(stages) - 1:
        return None
    
    # Find next non-review stage or next stage based on review configuration
    next_idx = current_idx + 1
    while next_idx < len(stages):
        next_stage = stages[next_idx]
        
        # If this is a review stage, check if automatic review is enabled
        if next_stage in {"backend_review", "frontend_review", "qa_review", "analyst_final_review", "po_pending_approval"}:
            if next_stage == "backend_review" and workflow.auto_backend_review:
                return "backend_review"
            elif next_stage == "frontend_review" and workflow.auto_frontend_review:
                return "frontend_review"
            elif next_stage == "qa_review" and workflow.auto_qa_review:
                return "qa_review"
            elif next_stage == "analyst_final_review" and workflow.auto_analyst_final_review:
                return "analyst_final_review"
            elif next_stage == "po_pending_approval" and workflow.require_po_approval:
                return "po_pending_approval"
            else:
                # Skip review stage if not enabled, go to next
                next_idx += 1
                continue
        
        # Found next executable stage
        return next_stage
    
    return None


def can_transition_to(task: SDLCTask, target_stage: str, project: SDLCProjectConfig) -> tuple[bool, str]:
    """Check if a task can transition to the target stage.
    
    Returns (can_transition, reason_if_not).
    """
    current_stage = task.current_stage
    workflow = project.workflow
    
    # Define valid transitions
    valid_transitions = {
        "created": ["analyzing"],
        "analyzing": ["human_review", "backend_running", "backend_review"],
        "human_review": ["analyzing", "backend_running", "backend_review"],
        "analysis_approved": ["backend_running", "backend_review"],
        "backend_running": ["backend_review", "revision"],
        "backend_review": ["frontend_running", "frontend_review", "backend_running", "revision"],
        "frontend_running": ["frontend_review", "revision"],
        "frontend_review": ["qa_running", "qa_review", "backend_running", "revision"],
        "qa_running": ["qa_review", "revision"],
        "qa_review": ["analyst_final_review", "backend_running", "frontend_running", "revision"],
        "analyst_final_review": ["po_pending_approval", "qa_running", "revision"],
        "po_pending_approval": ["analyst_final_review", "done"],
        "revision": ["backend_running", "frontend_running", "qa_running", "analyzing"],
        "failed": [],  # Terminal
        "blocked": [],  # Terminal
        "done": [],  # Terminal
    }
    
    valid_targets = valid_transitions.get(current_stage, [])
    
    if target_stage not in valid_targets:
        return False, f"Invalid transition from {current_stage} to {target_stage}. Valid targets: {', '.join(valid_targets)}"
    
    # Check for blocking conditions
    if target_stage in {"backend_review", "frontend_review", "qa_review"}:
        # These require previous stage to be completed successfully
        previous_stage = current_stage.replace("_review", "").rstrip("_running")
        if previous_stage not in task.agent_results:
            return False, f"Previous stage {previous_stage} has not completed yet"
        if task.agent_results[previous_stage].status != "completed":
            return False, f"Previous stage {previous_stage} did not complete successfully"
    
    if target_stage == "po_pending_approval":
        if not workflow.require_po_approval:
            return False, "PO approval not required for this project"
        # Check that QA passed (if qa_review exists)
        if "qa_review" in workflow.stages and task.qa_report:
            if task.qa_report.overall_recommendation not in {"pass", ""}:
                return False, f"QA must pass before PO approval (currently: {task.qa_report.overall_recommendation})"
    
    if target_stage == "done":
        # Must have PO approval if required
        if workflow.require_po_approval:
            if not task.po_decision or task.po_decision.decision != "approve":
                return False, "PO approval required before marking task done"
        # All stages must be completed
        for stage in workflow.stages:
            if stage not in {"backend_review", "frontend_review", "qa_review", "analyst_final_review", "po_pending_approval"}:
                if stage not in task.agent_results:
                    return False, f"Stage {stage} has not completed yet"
                if task.agent_results[stage].status != "completed":
                    return False, f"Stage {stage} did not complete successfully"
    
    return True, ""


def create_sanitized_prompt_for_role(role: str, task: SDLCTask, project: SDLCProjectConfig) -> tuple[str, list[str]]:
    """Create a prompt sanitized for the given role's knowledge boundaries.
    
    Returns (prompt, list of included directories).
    """
    sanitized_parts = []
    included_dirs = []
    
    # Always include: original request, approved requirements
    sanitized_parts.append(f"# Task {task.base_task.task_id}")
    if task.title:
        sanitized_parts.append(f"Title: {task.title}")
    if task.description:
        sanitized_parts.append(f"Description:\n{task.description}")
    
    if task.task_specification:
        sanitized_parts.append(f"\n## Approved Requirements\n{task.task_specification.user_business_need}")
        if task.task_specification.acceptance_criteria:
            sanitized_parts.append(f"\n### Acceptance Criteria\n" + "\n".join(f"- {c}" for c in task.task_specification.acceptance_criteria))
    
    # Role-specific additions
    if role == "analyst":
        # Analyst needs all stage results
        for stage, result in task.agent_results.items():
            sanitized_parts.append(f"\n## {stage} Result\nStatus: {result.status}\nSummary: {result.summary}")
            if result.issues:
                sanitized_parts.append(f"Issues: {', '.join(result.issues)}")
        
        # Include revision history
        if task.revisions:
            sanitized_parts.append("\n## Revision History")
            for rev in task.revisions:
                sanitized_parts.append(f"- From {rev.requesting_agent} to {rev.target_agent}: {rev.reason}")
        
        # Add QA report
        if task.qa_report:
            sanitized_parts.append("\n## QA Report")
            sanitized_parts.append(f"Recommendation: {task.qa_report.overall_recommendation}")
            sanitized_parts.append(f"Test Cases: {len(task.qa_report.test_cases)}")
        
        # Add PO decision
        if task.po_decision:
            sanitized_parts.append("\n## PO Decision")
            sanitized_parts.append(f"Decision: {task.po_decision.decision}")
            sanitized_parts.append(f"Rationale: {task.po_decision.rationale}")
    
    elif role == "backend":
        # Backend gets: original request, approved requirements, backend handoff (if exists)
        sanitized_parts.append("\n## Your Task")
        sanitized_parts.append("Implement the backend portion of this task.")
        
        if task.backend_handoff:
            sanitized_parts.append("\n## Frontend Handoff")
            sanitized_parts.append(task.backend_handoff.frontend_handoff.get("required", "No frontend impact"))
        
        # Add backend knowledge path
        if project.agents.get("backend") and project.agents["backend"].knowledge_path:
            included_dirs.append(project.agents["backend"].knowledge_path)
    
    elif role == "frontend":
        # Frontend gets: original request, approved requirements, approved backend handoff
        sanitized_parts.append("\n## Your Task")
        sanitized_parts.append("Implement the frontend portion of this task.")
        
        if task.backend_handoff:
            sanitized_parts.append("\n## Backend API Contract")
            api = task.backend_handoff.api_contract
            sanitized_parts.append(f"Endpoint: {api.get('method', 'GET')} {api.get('path', '/api')}")
            sanitized_parts.append(f"Data Format: {task.backend_handoff.frontend_handoff.get('data_format', 'JSON')}")
        
        # Add frontend knowledge path
        if project.agents.get("frontend") and project.agents["frontend"].knowledge_path:
            included_dirs.append(project.agents["frontend"].knowledge_path)
    
    elif role == "qa":
        # QA gets: ONLY original request, approved requirements, requirement-level decisions
        # MUST NOT include: backend/frontend source, private knowledge, implementation details
        
        sanitized_parts.append("\n## Test Objective")
        sanitized_parts.append("Create a black-box test strategy based solely on the requirements.")
        sanitized_parts.append("Do NOT inspect implementation code or implementation-specific logic.")
        
        # Only include requirement-level task decisions, not implementation details
        if task.stage_questions:
            sanitized_parts.append("\n## Requirement-Level Decisions")
            for q in task.stage_questions:
                if q.answered_by == "human" or q.asking_stage in {"analysis", "backend", "frontend"}:
                    sanitized_parts.append(f"- {q.question}: {q.answer}")
        
        # Add QA knowledge path
        qa_knowledge = task.qa_knowledge_path or project.agents.get("qa", AgentConfig()).knowledge_path
        if qa_knowledge:
            included_dirs.append(qa_knowledge)
    
    return "\n".join(sanitized_parts), included_dirs


def sanitize_agent_result_for_role(result: AgentResult, target_role: str) -> AgentResult:
    """Sanitize an agent result for sharing with a role that has limited knowledge.
    
    Removes implementation details from results shared with roles that shouldn't see them.
    """
    sanitized = result.model_copy()
    
    if target_role == "qa":
        # Remove implementation-specific information
        sanitized.summary = "Implementation completed. See acceptance criteria for verification."
        sanitized.changes = []  # Don't expose specific file changes to QA
        sanitized.recommendations = {}  # Remove implementation suggestions
        sanitized.issues = []  # Remove implementation-specific issues
    
    if target_role in {"backend", "frontend"}:
        # For implementation stages, keep most information but redact sensitive paths
        sanitized.summary = result.summary
        sanitized.changes = result.changes
    
    return sanitized


# Create singleton instances
_ollama_discovery = OllamaDiscoveryService()
_model_resolver = ModelResolutionService(_ollama_discovery)
_ollama_coding_agent = OllamaCodingAgent()
_ollama_runner = OllamaAgentRunner()