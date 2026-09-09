"""Build the Windows Taskloom executable.

Run with: ``python build_exe.py``
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"
BUILD_DIR = ROOT / ".taskloom-build"
DIST_DIR = ROOT / "dist"


def command_path(command: str) -> str:
    """Return an available executable or stop with a useful error message."""
    path = shutil.which(command)
    if path is None:
        raise RuntimeError(f"{command} was not found. Install it and try again.")
    return path


def run_command(*command: str, cwd: Path = ROOT) -> None:
    print(f"\n> {' '.join(command)}")
    subprocess.run(command, cwd=cwd, check=True)


def main() -> None:
    try:
        npm = command_path("npm.cmd" if sys.platform == "win32" else "npm")
        command_path(sys.executable)

        print("[1/4] Installing Python build dependencies...")
        run_command(
            sys.executable,
            "-m",
            "pip",
            "install",
            "-r",
            str(ROOT / "requirements.txt"),
            "pyinstaller",
        )

        print("[2/4] Installing frontend dependencies...")
        run_command(npm, "ci", cwd=FRONTEND)

        print("[3/4] Building frontend...")
        run_command(npm, "run", "build", cwd=FRONTEND)

        print("[4/4] Creating the single-file executable...")
        run_command(
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onefile",
            "--name",
            "Taskloom",
            "--distpath",
            str(DIST_DIR),
            "--workpath",
            str(BUILD_DIR / "work"),
            "--specpath",
            str(BUILD_DIR),
            "--add-data",
            f"{FRONTEND / 'dist'}{';' if sys.platform == 'win32' else ':'}{FRONTEND / 'dist'}",
            "--collect-all",
            "uvicorn",
            str(ROOT / "main.py"),
        )
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"\n[ERROR] Build failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    else:
        shutil.rmtree(BUILD_DIR, ignore_errors=True)
        print(f"\nBuild completed: {DIST_DIR / 'Taskloom.exe'}")

if __name__ == "__main__":
    main()
