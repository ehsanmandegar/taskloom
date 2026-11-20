"""Find and stop agent processes left behind when the Taskloom server dies mid-run.

A PID alone is not proof of identity: after a reboot the number can belong to an unrelated
program. Callers therefore compare the process image name recorded at launch before killing.
"""

from __future__ import annotations

import csv
import io
import os
import signal
import subprocess
from pathlib import Path

_NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def process_image(pid: int) -> str | None:
    """Executable name of a running process (e.g. ``claude.exe``), or None if it is not running."""
    if pid <= 0:
        return None
    if os.name == "nt":
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, creationflags=_NO_WINDOW,
        )
        for row in csv.reader(io.StringIO(result.stdout)):
            if len(row) >= 2 and row[1].strip() == str(pid):
                return row[0].strip()
        return None
    result = subprocess.run(["ps", "-p", str(pid), "-o", "comm="], capture_output=True, text=True)
    name = result.stdout.strip()
    return Path(name).name if result.returncode == 0 and name else None


def kill_process_tree(pid: int) -> bool:
    """Terminate a process and its children; True when the kill command succeeded."""
    if os.name == "nt":
        result = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, text=True, creationflags=_NO_WINDOW,
        )
        return result.returncode == 0
    try:
        os.killpg(os.getpgid(pid), signal.SIGKILL)
    except ProcessLookupError:
        return False
    except PermissionError:
        os.kill(pid, signal.SIGKILL)
    return True


def stop_if_same_program(pid: int, image: str) -> str:
    """Kill `pid` only if it is still the program recorded at launch; return what happened."""
    current = process_image(pid)
    if current is None:
        return "not running"
    if current.casefold() != image.casefold():
        return f"PID {pid} now belongs to {current}; left untouched"
    return "stopped" if kill_process_tree(pid) else "could not be stopped"
