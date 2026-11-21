"""Long-running "Run" processes of SDLC stages.

Two kinds, one per (project, stage):
  * a plain shell command (`npm run dev`) started by the ▶ button, and
  * an agent run: Claude Code follows the stage's RUN_TEST.md / RUN_REAL.md guide. Servers the agent
    starts are detached from it, so it records their PIDs in `pid_file`; stopping kills those too.

Output is kept in a bounded buffer so the dashboard can show it. The processes belong to the Taskloom
server: they are stopped on shutdown (stop_all).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .process_tools import kill_process_tree, process_image

MAX_LOG_LINES = 400


def format_claude_event(line: str) -> str:
    """Turn one Claude Code stream-json line into readable log text ('' to skip it)."""
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return line
    if not isinstance(event, dict):
        return line
    kind = event.get("type")
    if kind == "assistant":
        parts = []
        for block in (event.get("message") or {}).get("content") or []:
            if block.get("type") == "text" and block.get("text", "").strip():
                parts.append(block["text"].strip())
            elif block.get("type") == "tool_use":
                args = block.get("input") or {}
                detail = args.get("command") or args.get("file_path") or args.get("path") or ""
                parts.append(f"$ {block.get('name')}: {detail}".rstrip(": ").strip())
        return "\n".join(parts)
    if kind == "result":
        return f"--- {'ERROR' if event.get('is_error') else 'DONE'}: {str(event.get('result') or '').strip()}"
    return ""


class RunProcess:
    def __init__(self, key: str, label: str, args: list[str] | str, cwd: str, *, mode: str = "command",
                 stdin_text: str | None = None, pid_file: Path | None = None,
                 formatter: Callable[[str], str] | None = None) -> None:
        self.key = key
        self.label = label
        self.mode = mode
        self.cwd = cwd
        self.pid_file = pid_file
        self.formatter = formatter
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.lines: deque[str] = deque(maxlen=MAX_LOG_LINES)
        if pid_file:
            pid_file.parent.mkdir(parents=True, exist_ok=True)
            pid_file.unlink(missing_ok=True)
        kwargs: dict = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        self.proc = subprocess.Popen(
            args, shell=isinstance(args, str), cwd=cwd,
            stdin=subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", **kwargs,
        )
        if stdin_text is not None:
            assert self.proc.stdin is not None
            try:
                self.proc.stdin.write(stdin_text)
                self.proc.stdin.close()
            except OSError:
                pass
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self) -> None:
        assert self.proc.stdout is not None
        for raw in self.proc.stdout:
            line = raw.rstrip("\n")
            text = self.formatter(line) if self.formatter else line
            if text:
                self.lines.extend(text.split("\n"))

    def _detached_pids(self) -> list[int]:
        """PIDs the agent recorded for servers it left running."""
        if not self.pid_file or not self.pid_file.is_file():
            return []
        pids = []
        for token in self.pid_file.read_text(encoding="utf-8", errors="replace").split():
            if token.isdigit() and int(token) > 0:
                pids.append(int(token))
        return [pid for pid in pids if process_image(pid)]

    @property
    def running(self) -> bool:
        return self.proc.poll() is None or bool(self._detached_pids())

    def stop(self) -> None:
        for pid in self._detached_pids():
            kill_process_tree(pid)
        if self.proc.poll() is None:
            kill_process_tree(self.proc.pid)
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        if self.pid_file:
            self.pid_file.unlink(missing_ok=True)

    def status(self) -> dict:
        code = self.proc.poll()
        detached = self._detached_pids()
        return {
            "running": code is None or bool(detached),
            "agent_running": code is None,
            "detached_pids": detached,
            "exit_code": code,
            "pid": self.proc.pid,
            "mode": self.mode,
            "command": self.label,
            "cwd": self.cwd,
            "started_at": self.started_at,
            "log": "\n".join(self.lines),
        }


_processes: dict[str, RunProcess] = {}
_lock = threading.Lock()


def _key(project_id: str, stage: str) -> str:
    return f"{project_id}/{stage}"


def start(project_id: str, stage: str, command: str, cwd: str) -> dict:
    """Start the stage's plain command; an already running one is left alone (idempotent)."""
    return start_process(project_id, stage, lambda key: RunProcess(key, command, command, cwd))


def start_process(project_id: str, stage: str, factory: Callable[[str], RunProcess]) -> dict:
    key = _key(project_id, stage)
    with _lock:
        current = _processes.get(key)
        if current and current.running:
            return current.status()
        run = factory(key)
        _processes[key] = run
        return run.status()


def stop(project_id: str, stage: str) -> dict:
    with _lock:
        run = _processes.get(_key(project_id, stage))
    if run:
        run.stop()
        return run.status()
    return {"running": False}


def status(project_id: str, stage: str) -> dict:
    with _lock:
        run = _processes.get(_key(project_id, stage))
    return run.status() if run else {"running": False}


def running_stages(project_id: str) -> list[str]:
    prefix = f"{project_id}/"
    with _lock:
        return [k[len(prefix):] for k, p in _processes.items() if k.startswith(prefix) and p.running]


def stop_project(project_id: str) -> None:
    for stage in running_stages(project_id):
        stop(project_id, stage)


def stop_all() -> None:
    with _lock:
        runs = list(_processes.values())
    for run in runs:
        run.stop()
