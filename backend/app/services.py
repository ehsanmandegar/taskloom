import asyncio
import codecs
from contextvars import ContextVar
import json
import os
import re
import shlex
import shutil
from pathlib import Path
from typing import Callable

from .models import ChatMessage, GitProvider, McpFailureMode, McpStatus, RunStatus, TaskRequest, TaskState


_command_output_handler: ContextVar[Callable[[str], None] | None] = ContextVar("command_output_handler", default=None)


async def command(args: list[str], cwd: Path, timeout: int = 900) -> tuple[int, str]:
    executable = args[0]
    executable_path = Path(executable).expanduser()
    if not executable_path.is_absolute() and any(separator in executable for separator in ("/", "\\")):
        executable_path = cwd / executable_path
    if executable_path.is_file():
        executable = str(executable_path.resolve())
    else:
        executable = shutil.which(executable) or executable

    process = await asyncio.create_subprocess_exec(executable, *args[1:], cwd=str(cwd), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, env=os.environ.copy())
    handler = _command_output_handler.get()
    try:
        if handler is None:
            output, _ = await asyncio.wait_for(process.communicate(), timeout)
        else:
            chunks: list[bytes] = []
            decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

            async def read_output() -> None:
                assert process.stdout is not None
                while chunk := await process.stdout.read(4096):
                    chunks.append(chunk)
                    text = decoder.decode(chunk)
                    if text:
                        handler(text)
                tail = decoder.decode(b"", final=True)
                if tail:
                    handler(tail)
                await process.wait()

            await asyncio.wait_for(read_output(), timeout)
            output = b"".join(chunks)
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


def cleanup_owned_test_artifacts(repo: Path) -> None:
    """Remove only temporary folders explicitly owned by Taskloom runs."""
    for path in repo.glob(".taskloom-test-*"):
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path, ignore_errors=True)


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
    if (repo / "pytest.ini").exists() or (repo / "pyproject.toml").exists() or (repo / "tests").exists():
        return [shutil.which("pytest") or "pytest", "-q"]
    if (repo / "package.json").exists():
        return [shutil.which("npm") or "npm", "test", "--", "--run"]
    return [shutil.which("python") or "python", "-m", "pytest", "-q"]


def build_prompt(req: TaskRequest, guides: list[Path], active_mcp: str | None = None) -> str:
    listed = "\n".join(f"- {path}" for path in guides) or "- Discover repository instructions."
    mcp_instruction = ""
    if active_mcp == "dws_project":
        mcp_instruction = f"""
Before inspecting the repository directly, use the read-only tools from the `{active_mcp}` MCP server for project knowledge. Start with `search_docs`, `read_doc`, `search_code`, or `read_file` as appropriate. Treat MCP responses as context only. Do not use its `run_tests` tool as evidence for Taskloom gates; Taskloom runs the required test plan independently."""
    elif active_mcp:
        mcp_instruction = f"\nUse the read-only project-knowledge tools from the `{active_mcp}` MCP server before inspecting the repository directly. Treat its responses as context, not test-gate evidence."
    return f"""Implement task {req.task_id}.
User request: {req.request}
Instruction/documentation paths:\n{listed}{mcp_instruction}
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


async def preflight_project_mcp(codex: str, repo: Path, server_name: str) -> tuple[bool, str]:
    code, output = await command([codex, "mcp", "get", server_name, "--json"], repo, 30)
    if code:
        if code == 124:
            return False, f"MCP `{server_name}` preflight timed out."
        if "not found" in output.casefold() or "does not exist" in output.casefold():
            return False, f"MCP `{server_name}` is not configured."
        return False, f"MCP `{server_name}` preflight failed with exit code {code}."
    config = _mcp_config(output, server_name)
    if config is None:
        return False, f"MCP `{server_name}` returned an unreadable preflight response."
    if config.get("enabled") is not True:
        return False, f"MCP `{server_name}` is configured but disabled."
    return True, f"MCP `{server_name}` is configured and enabled."


def mcp_runtime_issue(output: str, server_name: str) -> str | None:
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


async def codex_command(args: list[str], repo: Path, state: TaskState, timeout: int) -> tuple[int, str]:
    """Run Codex while applying its JSONL events to the observable task state."""
    state.live_output = ""
    state.live_response = ""
    stream = CodexEventStream(state)
    token = _command_output_handler.set(stream.feed)
    try:
        code, output = await command(args, repo, timeout)
    finally:
        _command_output_handler.reset(token)
    # Test doubles and alternative command runners may return buffered output.
    if not stream.saw_data:
        stream.feed(output)
    stream.finish()
    return code, output


async def refresh_git(state: TaskState, repo: Path) -> None:
    _, state.diff = await command(["git", "diff", "--no-ext-diff", "--"], repo)
    _, staged = await command(["git", "diff", "--cached", "--no-ext-diff", "--"], repo)
    state.diff = f"{state.diff}\n{staged}".strip()
    _, names = await command(["git", "status", "--short"], repo)
    state.changed_files = [line[3:] for line in names.splitlines() if len(line) > 3]


async def execute_task(req: TaskRequest, state: TaskState) -> None:
    try:
        repo, guides = repository(req.project_path), resolve_guides(repository(req.project_path), req.guide_paths)
        state.status, state.step = RunStatus.running, "Checking project prerequisites"
        codex = shutil.which("codex")
        if not codex:
            raise RuntimeError("Codex CLI was not found. Install it and sign in first.")
        active_mcp = None
        if req.mcp_server_name:
            state.mcp_status = McpStatus.checking
            ready, message = await preflight_project_mcp(codex, repo, req.mcp_server_name)
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

        state.step = "Creating task branch"
        code, output = await command(["git", "status", "--porcelain"], repo)
        if code or output.strip():
            raise RuntimeError("Repository must be clean before starting a task")
        code, output = await command(["git", "switch", "-c", state.branch], repo)
        if code:
            raise RuntimeError(output.strip() or "Could not create branch")
        state.logs.append(f"Created {state.branch}")
        state.step = "Codex is implementing the request"
        code, output = await codex_command([codex, "exec", "--sandbox", "workspace-write", "--color", "never", "--json", build_prompt(req, guides, active_mcp)], repo, state, 3600)
        runtime_issue = mcp_runtime_issue(output, active_mcp) if active_mcp else None
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
            state.mcp_message = f"MCP `{active_mcp}` was available to the Codex session."
        thread_id, response = codex_response(output)
        if not thread_id:
            raise RuntimeError("Codex did not return a resumable session ID")
        state.codex_thread_id = thread_id
        state.logs.append(output[-12000:])
        state.summary = response or output.strip()[-4000:]
        if response:
            state.messages.append(ChatMessage(role="assistant", content=response))
        state.live_response = ""
        await refresh_git(state, repo)
        cleanup_owned_test_artifacts(repo)
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


async def continue_task(message: str, state: TaskState) -> None:
    """Continue the exact Codex thread used for the task with a user follow-up."""
    try:
        if not state.codex_thread_id:
            raise RuntimeError("This task does not have a resumable Codex session")
        repo = repository(state.project_path)
        codex = shutil.which("codex")
        if not codex:
            raise RuntimeError("Codex CLI was not found. Install it and sign in first.")
        state.status, state.step, state.error = RunStatus.running, "Codex is responding", None
        prompt = f"""User follow-up:\n{message}\n\nContinue this conversation. Make edits when they help answer the request, but do not commit, push, switch branches, or modify files outside this repository. Summarize what you did or recommend next."""
        code, output = await codex_command([codex, "exec", "resume", "--json", state.codex_thread_id, prompt], repo, state, 3600)
        _, response = codex_response(output)
        state.logs.append(output[-12000:])
        state.summary = response or output.strip()[-4000:]
        if response:
            state.messages.append(ChatMessage(role="assistant", content=response))
        state.live_response = ""
        await refresh_git(state, repo)
        if code:
            raise RuntimeError(f"Codex exited with code {code}")
        state.status, state.step = RunStatus.testing, "Running tests"
        tests = shlex.split(state.test_command, posix=False) if state.test_command else detect_tests(repo)
        code, output = await command(tests, repo, 1800)
        state.test_output = output[-20000:]
        state.status, state.step = (RunStatus.passed, "Ready for further instructions") if code == 0 else (RunStatus.failed, "Tests failed")
        if code:
            state.error = f"Tests exited with code {code}"
        await refresh_git(state, repo)
        if state.changed_files:
            state.committed = False
            state.pushed = False
        cleanup_owned_test_artifacts(repo)
    except Exception as exc:
        state.status, state.step, state.error = RunStatus.failed, "Conversation failed", str(exc)
        state.logs.append(str(exc))


async def generate_commit_message(state: TaskState) -> str:
    """Ask the task's existing Codex session for a concise commit message."""
    if state.status != RunStatus.passed or not state.changed_files:
        raise ValueError("A successful test run with changes is required")
    if state.committed:
        raise ValueError("The task has already been committed")
    if not state.codex_thread_id:
        raise ValueError("This task does not have a resumable Codex session")
    repo = repository(state.project_path)
    codex = shutil.which("codex")
    if not codex:
        raise RuntimeError("Codex CLI was not found. Install it and sign in first.")
    prompt = """Review the current uncommitted diff and reply with exactly one Conventional Commit message.
Keep it under 200 characters and on one line. Do not edit files, run tests, commit, push, or add explanation."""
    code, output = await command([codex, "exec", "resume", "--json", state.codex_thread_id, prompt], repo, 600)
    if code:
        raise RuntimeError(f"Codex exited with code {code}")
    _, response = codex_response(output)
    message = response.splitlines()[0].strip().strip("`") if response else ""
    if not message or len(message) > 200:
        raise RuntimeError("Codex did not return a valid commit message")
    return message


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
        args = ["pr", "create", "--fill", "--head", state.branch, "--base", "develop"]
    elif provider == GitProvider.gitlab or (provider == GitProvider.auto and "gitlab" in normalized_remote):
        cli_name = "glab"
        args = ["mr", "create", "--fill", "--source-branch", state.branch, "--target-branch", "develop", "--yes"]
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
