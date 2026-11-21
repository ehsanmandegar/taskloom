"""Per-stage run guides: RUN_TEST.md / RUN_REAL.md in the stage's folder.

The user edits them in the dashboard; "start" hands the chosen one to Claude Code, which follows it.
"""
from __future__ import annotations

from pathlib import Path

GUIDE_FILES = {"test": "RUN_TEST.md", "real": "RUN_REAL.md"}

TEMPLATES = {
    "test": """# How to run the {stage} tests

## Install
<!-- e.g. pip install -r requirements.txt  /  npm install -->

## Run the tests
<!-- e.g. python -m pytest -q  /  npm test -->

## Notes for the agent
<!-- env vars, test database, ports, things to avoid ... -->
""",
    "real": """# How to run {stage} for real

## Install
<!-- e.g. pip install -r requirements.txt  /  npm install -->

## Configuration
<!-- .env values, ports, URLs of the other services ... -->

## Start
<!-- e.g. uvicorn app.main:app --port 8000  /  npm run dev -->

## How to know it works
<!-- e.g. GET http://localhost:8000/health returns 200 -->
""",
}


def guide_path(folder: Path, mode: str) -> Path:
    return folder / GUIDE_FILES[mode]


def read_guides(folder: Path, stage: str) -> dict:
    """{mode: {file, exists, content}}; a missing file comes back as a starter template."""
    result = {}
    for mode, name in GUIDE_FILES.items():
        path = guide_path(folder, mode)
        exists = path.is_file()
        content = path.read_text(encoding="utf-8", errors="replace") if exists else TEMPLATES[mode].format(stage=stage)
        result[mode] = {"file": name, "exists": exists, "content": content}
    return result


def write_guide(folder: Path, mode: str, content: str) -> None:
    guide_path(folder, mode).write_text(content, encoding="utf-8")


def build_run_prompt(mode: str, stage: str, project_name: str, folder: Path, pid_file: Path) -> str:
    name = GUIDE_FILES[mode]
    goal = ("Run the project's tests exactly as the guide describes, and report which passed and which failed."
            if mode == "test" else
            "Start the project for real as the guide describes and confirm that it is up.")
    return f"""You are running the {stage} part of the project "{project_name}". Your working folder is {folder}.

Read ./{name} and follow it step by step. {goal}

Rules:
- Do the install/start/test steps the guide lists, in order. If a step fails, read the error, fix the cause when it is
  a setup problem (missing dependency, wrong port, missing config file) and retry. Do not rewrite application code to
  make a failing test pass; report the failure instead.
- If you start a server or any process that must keep running after you finish, start it detached from your shell
  (Windows PowerShell: Start-Process -PassThru -WindowStyle Hidden; Linux/macOS: nohup ... &), then append its PID,
  one per line, to this file: {pid_file}
  Taskloom uses that file to show the run state and to stop the processes later.
- Do not run commands that delete data outside {folder}.
- Finish with a short report: what you ran, whether it works, the URL/port if any, and any problem left.
"""
