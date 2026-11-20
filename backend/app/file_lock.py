"""Cross-process exclusive file locks (Windows and POSIX) for Taskloom's JSON storage.

Locks are held on an open handle, so they work between processes and between separate handles
in the same process, and the OS releases them if the holder crashes.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

if os.name == "nt":
    import msvcrt
else:
    import fcntl


class LockTimeout(TimeoutError):
    pass


class FileLock:
    def __init__(self, path: Path, timeout: float = 10.0, poll: float = 0.02):
        self.path = Path(path)
        self.timeout = timeout
        self.poll = poll
        self._handle = None

    def try_acquire(self) -> bool:
        """Take the lock without waiting; False when another handle holds it."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(self.path, "a+b")
        try:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            return False
        self._handle = handle
        return True

    def acquire(self) -> None:
        deadline = time.monotonic() + self.timeout
        while not self.try_acquire():
            if time.monotonic() >= deadline:
                raise LockTimeout(f"Timed out waiting for lock {self.path}")
            time.sleep(self.poll)

    def release(self) -> None:
        handle, self._handle = self._handle, None
        if handle is None:
            return
        try:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()

    @property
    def held(self) -> bool:
        return self._handle is not None

    def __enter__(self) -> "FileLock":
        self.acquire()
        return self

    def __exit__(self, *_exc) -> None:
        self.release()


def replace_with_retry(source: Path, target: Path, attempts: int = 20, delay: float = 0.025) -> None:
    """os.replace that tolerates Windows' transient PermissionError while a reader has `target` open."""
    for attempt in range(attempts):
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(delay)
