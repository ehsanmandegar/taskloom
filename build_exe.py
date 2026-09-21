"""
Build the Taskloom executable.

Run with:
    python build_exe.py

The resulting executable will be created at:
    dist/Taskloom.exe
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


# ============================================================================
# Paths
# ============================================================================

ROOT = Path(__file__).resolve().parent

FRONTEND = ROOT / "frontend"
FRONTEND_DIST = FRONTEND / "dist"

MAIN_FILE = ROOT / "main.py"
REQUIREMENTS_FILE = ROOT / "requirements.txt"
ICON_FILE = ROOT / "assets" / "taskloom.ico"

BUILD_DIR = ROOT / ".taskloom-build"
DIST_DIR = ROOT / "dist"

EXECUTABLE_NAME = "Taskloom"


# ============================================================================
# Helpers
# ============================================================================

def command_path(command: str) -> str:
    """
    Return the full path of an executable available on PATH.

    Raises:
        RuntimeError: If the executable cannot be found.
    """
    path = shutil.which(command)

    if path is None:
        raise RuntimeError(
            f"'{command}' was not found on PATH. "
            f"Please install it and make sure it is available from the terminal."
        )

    return path


def run_command(*command: str, cwd: Path = ROOT) -> None:
    """
    Run a command and stop the build if it fails.
    """
    printable_command = " ".join(f'"{arg}"' if " " in arg else arg for arg in command)

    print()
    print("=" * 80)
    print(f"> {printable_command}")
    print("=" * 80)

    subprocess.run(
        command,
        cwd=cwd,
        check=True,
    )


def remove_directory(path: Path) -> None:
    """
    Remove a directory if it exists.
    """
    if path.exists():
        print(f"Removing: {path}")
        shutil.rmtree(path, ignore_errors=True)


def validate_project() -> None:
    """
    Validate the files/directories required for the build.
    """
    print("[0/4] Validating project...")

    required_paths = {
        "main.py": MAIN_FILE,
        "requirements.txt": REQUIREMENTS_FILE,
        "application icon": ICON_FILE,
        "frontend directory": FRONTEND,
        "frontend/package.json": FRONTEND / "package.json",
        "frontend/package-lock.json": FRONTEND / "package-lock.json",
    }

    for name, path in required_paths.items():
        if not path.exists():
            raise RuntimeError(
                f"Required {name} was not found:\n"
                f"    {path}"
            )

    print("Project structure looks good.")


def get_data_separator() -> str:
    """
    Return the PyInstaller --add-data separator for the current platform.
    """
    return ";" if sys.platform == "win32" else ":"


# ============================================================================
# Build
# ============================================================================

def main() -> None:
    try:
        # --------------------------------------------------------------------
        # 0. Validate project
        # --------------------------------------------------------------------

        validate_project()

        # --------------------------------------------------------------------
        # 1. Locate required executables
        # --------------------------------------------------------------------

        print("\n[1/4] Checking build tools...")

        if sys.platform == "win32":
            npm = command_path("npm.cmd")
        else:
            npm = command_path("npm")

        python = command_path(sys.executable)

        print(f"Python : {python}")
        print(f"npm    : {npm}")

        # --------------------------------------------------------------------
        # Prepare directories
        # --------------------------------------------------------------------

        DIST_DIR.mkdir(parents=True, exist_ok=True)
        BUILD_DIR.mkdir(parents=True, exist_ok=True)

        # --------------------------------------------------------------------
        # 2. Install Python dependencies
        # --------------------------------------------------------------------

        print("\n[2/4] Installing Python build dependencies...")

        run_command(
            python,
            "-m",
            "pip",
            "install",
            "-r",
            str(REQUIREMENTS_FILE),
        )

        run_command(
            python,
            "-m",
            "pip",
            "install",
            "pyinstaller",
        )

        # --------------------------------------------------------------------
        # 3. Install and build frontend
        # --------------------------------------------------------------------

        print("\n[3/4] Installing frontend dependencies...")

        run_command(
            npm,
            "ci",
            cwd=FRONTEND,
        )

        print("\nBuilding frontend...")

        run_command(
            npm,
            "run",
            "build",
            cwd=FRONTEND,
        )

        # Make sure frontend build actually exists.
        if not FRONTEND_DIST.exists():
            raise RuntimeError(
                "Frontend build completed, but frontend/dist was not created.\n"
                f"Expected directory:\n    {FRONTEND_DIST}"
            )

        print(f"Frontend build found: {FRONTEND_DIST}")

        # --------------------------------------------------------------------
        # 4. Build executable
        # --------------------------------------------------------------------

        print("\n[4/4] Creating the single-file executable...")

        # IMPORTANT:
        #
        # PyInstaller expects:
        #
        #     --add-data=SOURCE;DEST
        #
        # on Windows, and:
        #
        #     --add-data=SOURCE:DEST
        #
        # on Linux/macOS.
        #
        # Keeping the complete option in ONE argument avoids the parsing
        # problem caused by:
        #
        #     "--add-data", "SOURCE;DEST"
        #
        # with newer PyInstaller versions.

        separator = get_data_separator()

        add_data_argument = (
            f"--add-data="
            f"{FRONTEND_DIST}"
            f"{separator}"
            f"frontend/dist"
        )

        # Clean previous PyInstaller output.
        remove_directory(BUILD_DIR / "work")

        executable_path = (
            DIST_DIR
            / (
                f"{EXECUTABLE_NAME}.exe"
                if sys.platform == "win32"
                else EXECUTABLE_NAME
            )
        )

        if executable_path.exists():
            print(f"Removing previous executable: {executable_path}")
            executable_path.unlink()

        run_command(
            python,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onefile",
            "--name",
            EXECUTABLE_NAME,
            "--icon",
            str(ICON_FILE),

            # Output directories
            "--distpath",
            str(DIST_DIR),

            "--workpath",
            str(BUILD_DIR / "work"),

            "--specpath",
            str(BUILD_DIR),

            # Frontend
            add_data_argument,

            # Uvicorn resources
            "--collect-all",
            "uvicorn",

            # Application entry point
            str(MAIN_FILE),
        )

        # --------------------------------------------------------------------
        # Verify output
        # --------------------------------------------------------------------

        if not executable_path.exists():
            raise RuntimeError(
                "PyInstaller finished, but the executable was not found.\n"
                f"Expected:\n    {executable_path}"
            )

    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print()
        print("=" * 80)
        print("[ERROR] Build failed")
        print("=" * 80)
        print(error)
        print()
        raise SystemExit(1) from error

    else:
        # Clean temporary build files.
        print("\nCleaning temporary build files...")
        remove_directory(BUILD_DIR)

        print()
        print("=" * 80)
        print("BUILD COMPLETED SUCCESSFULLY")
        print("=" * 80)
        print()
        print(f"Executable:")
        print(f"    {executable_path}")
        print()
        print("You can now run Taskloom.exe.")
        print()


# ============================================================================
# Entry point
# ============================================================================

if __name__ == "__main__":
    main()
