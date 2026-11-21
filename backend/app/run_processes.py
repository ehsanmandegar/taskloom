"""Long-running "Run" commands of SDLC stages (e.g. `npm run dev`, `uvicorn app.main:app`).

One process per (project, stage). Output is kept in a bounded buffer so the dashboard can show it.
The processes belong to the Taskloom server: they are stopped on shutdown (stop_all).
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
from collections import deque
from datetime import datetime, timezone

MAX_LOG_LINES = 400


class RunProcess:
    def __init__(self, key: str, command: str, cwd: str) -> None:
        self.key = key
        self.command = command
        self.cwd = cwd
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.lines: deque[str] = deque(maxlen=MAX_LOG_LINES)
        kwargs: dict = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        self.proc = subprocess.Popen(
            command, shell=True, cwd=cwd,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", **kwargs,
        )
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self) -> None:
        assert self.proc.stdout is not None
        for line in self.proc.stdout:
            self.lines.append(line.rstrip("\n"))

    @property
    def running(self) -> bool:
        return self.proc.poll() is None

    def stop(self) -> None:
        if not self.running:
            return
        if sys.platform == "win32":
            # shell=True spawns cmd.exe -> node/python...; /T kills the whole tree.
            subprocess.run(["taskkill", "/PID", str(self.proc.pid), "/T", "/F"],
                           capture_output=True, check=False)
        else:
            import signal
            try:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
            except ProcessLookupError:
                pass
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()

    def status(self) -> dict:
        code = self.proc.poll()
        return {
            "running": code is None,
            "exit_code": code,
            "pid": self.proc.pid,
            "command": self.command,
            "cwd": self.cwd,
            "started_at": self.started_at,
            "log": "\n".join(self.lines),
        }


_processes: dict[str, RunProcess] = {}
_lock = threading.Lock()


def _key(project_id: str, stage: str) -> str:
    return f"{project_id}/{stage}"


def start(project_id: str, stage: str, command: str, cwd: str) -> dict:
    """Start the stage's command; an already running one is left alone (idempotent)."""
    key = _key(project_id, stage)
    with _lock:
        current = _processes.get(key)
        if current and current.running:
            return current.status()
        run = RunProcess(key, command, cwd)
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
