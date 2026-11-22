"""Project builder: turn "I want project X" into a project that is ready to receive tasks.

From a free-text idea it decides the stages, lays out one folder per stage under a project root, writes each stage's
system prompt, working conventions and a small starter skeleton, gives every stage a Git repository (initial commit
plus the `sandbox` task base) and saves the SDLC project configuration.  The built-in templates always work offline;
when a coding agent (Claude Code) or Ollama answers, it enriches the description, requirements, architecture and the
per-stage guidance on top of them.  Nothing here talks to GitHub unless asked: a stage's repository is created there
on its first push, exactly like any other from-scratch stage.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import stat
import tempfile
from pathlib import Path
from typing import Awaitable, Callable, Literal

from pydantic import BaseModel, Field, field_validator

from .models import AgentConfig, ProjectWorkflowConfig, RepositoryConfig, RepositoryMode, SDLCProjectConfig

STAGE_ORDER = ["analysis", "backend", "n8n", "frontend", "qa"]
DEFAULT_ROOT = Path.home() / "taskloom-projects"
MIN_IDEA, MAX_IDEA = 10, 4000

Autonomy = Literal["manual", "balanced", "autopilot"]
Stack = Literal["auto", "python", "node", "web"]

# Ask an AI for JSON; returns the raw text or raises. Injected in tests.
Refiner = Callable[[str], Awaitable[str]]


class BuildRequest(BaseModel):
    idea: str
    name: str = ""
    id: str = ""
    stack: Stack = "auto"
    stages: list[str] = Field(default_factory=list)  # empty: chosen from the idea
    base_dir: str = ""                               # parent folder; default ~/taskloom-projects
    autonomy: Autonomy = "balanced"
    use_ai: bool = True
    preview: bool = False                            # plan only: write nothing, call no AI

    @field_validator("idea")
    @classmethod
    def idea_length(cls, value: str) -> str:
        value = value.strip()
        if not MIN_IDEA <= len(value) <= MAX_IDEA:
            raise ValueError(f"Describe the project in {MIN_IDEA}–{MAX_IDEA} characters")
        return value

    @field_validator("stages")
    @classmethod
    def known_stages(cls, value: list[str]) -> list[str]:
        unknown = [stage for stage in value if stage not in STAGE_ORDER]
        if unknown:
            raise ValueError(f"Unknown stages: {', '.join(unknown)}")
        return value


class BuildError(ValueError):
    """The request cannot be built (bad folder, duplicate id ...); the message is meant for the user."""


# ----------------------------------------------------------------------------- understanding the idea

def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:40].strip("-")


def project_id_for(request: BuildRequest) -> str:
    wanted = slugify(request.id) or slugify(request.name)
    if not wanted:  # e.g. a Persian-only idea: derive something stable and readable from the latin words, else generic
        words = re.findall(r"[a-zA-Z0-9]{3,}", request.idea)
        wanted = slugify("-".join(words[:3])) or "project"
    return wanted


def project_name_for(request: BuildRequest, project_id: str) -> str:
    if request.name.strip():
        return request.name.strip()[:80]
    first = re.split(r"[.\n!؟?]", request.idea.strip(), maxsplit=1)[0].strip()
    return (first[:60] or project_id).strip()


def _has(text: str, words: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in words)


def detect_stack(idea: str) -> str:
    if _has(idea, ("node", "express", "nestjs", "javascript", "typescript")) and not _has(idea, ("python", "fastapi", "django", "flask")):
        return "node"
    if _has(idea, ("python", "fastapi", "django", "flask", "پایتون")):
        return "python"
    if _has(idea, ("سایت", "وب‌سایت", "landing", "static site", "html")) and not _has(idea, ("api", "backend", "سرور", "بک‌اند", "database", "دیتابیس")):
        return "web"
    return "python"


def detect_stages(idea: str, stack: str) -> list[str]:
    stages = ["analysis"]
    if stack != "web":
        stages.append("backend")
    if _has(idea, ("n8n", "workflow automation", "اتوماسیون")):
        stages.append("n8n")
    if stack == "web" or _has(idea, ("frontend", "front-end", "ui", "react", "dashboard", "website", "web app", "page", "سایت", "داشبورد", "فرانت", "رابط کاربری", "صفحه", "وب")):
        stages.append("frontend")
    stages.append("qa")
    return [stage for stage in STAGE_ORDER if stage in stages]


def workflow_for(autonomy: str, stages: list[str]) -> ProjectWorkflowConfig:
    """Human gates stay on in every preset; a higher preset only hands Taskloom the low-risk decisions."""
    flow = dict(stages=stages, sequential=True, require_analysis_approval=True, require_final_human_approval=True)
    if autonomy == "balanced":
        flow.update(auto_retry_failed_stages=1, auto_final_approval=True, auto_approval_max_risk="low")
    elif autonomy == "autopilot":
        flow.update(auto_analysis_approval=True, auto_final_approval=True, auto_approval_max_risk="low",
                    auto_retry_failed_stages=2, auto_release=True, auto_release_min_tasks=2)
    return ProjectWorkflowConfig(**flow)


# ----------------------------------------------------------------------------- stage content

ROLE_TITLES = {
    "analysis": "software analyst", "backend": "backend developer", "n8n": "n8n workflow engineer",
    "frontend": "frontend developer", "qa": "QA engineer",
}

BASE_RULES = """\
- Read the project knowledge folder first: PROJECT.md (the goal), ARCHITECTURE.md, CONVENTIONS.md and DEFINITION_OF_DONE.md.
- Stay inside your stage's folder; read other stages' folders, never change them.
- Write code, comments and commit messages in English. Write reports in the language the task description is written in.
- Keep changes small and focused on the task. Do not add dependencies or files that the task does not need.
- Never put secrets, tokens or passwords in the repository. Use environment variables and document them in the README.
- If something is ambiguous or missing, say so as an open question instead of guessing."""

STAGE_PROMPTS = {
    "analysis": """\
You are the software analyst for "{name}". Project goal: {idea}

Your job is to turn each task into a precise, testable specification before any code is written.
{rules}
Deliver, in your report: the functional requirements, the technical requirements, the components and files likely to be
affected, risks, and a numbered list of open questions. Acceptance criteria must be checkable (Given/When/Then or a
clear pass/fail statement). Keep docs/requirements.md in your repository up to date with what was agreed.
Do not change application source code in this stage.{notes}""",
    "backend": """\
You are the backend developer for "{name}". Project goal: {idea}

Stack: {stack_line}
{rules}
Implement the task exactly as specified by the analysis. Add or update automated tests for every behaviour you add or change
and make sure `{test_command}` passes before you finish. Validate input at the boundary, return clear errors, and keep the
public interface documented in the README.{notes}""",
    "frontend": """\
You are the frontend developer for "{name}". Project goal: {idea}

Stack: {stack_line}
{rules}
Build only what the task asks for, matching the existing look and structure. The UI must be accessible (labels, keyboard use,
sufficient contrast), responsive, and handle loading, empty and error states. Add or update tests for the logic you write and
make sure `{test_command}` passes before you finish.{notes}""",
    "n8n": """\
You are the n8n workflow engineer for "{name}". Project goal: {idea}
{rules}
Keep each workflow as exported JSON under workflows/, one file per workflow, with a short description of its trigger, inputs
and outputs in workflows/README.md. Do not store credentials in the JSON: reference n8n credentials by name.{notes}""",
    "qa": """\
You are the QA engineer for "{name}". Project goal: {idea}
{rules}
Verify the finished work against the analysis' acceptance criteria. Run the available tests and exercise the behaviour yourself.
Report every defect with steps to reproduce, the expected and the actual result. Use status needs_revision (naming the stage
that must fix it) when something is wrong; otherwise confirm each acceptance criterion explicitly. Keep test-plan.md current.
Do not change application source code in this stage.{notes}""",
}


def stack_line(stack: str, stage: str) -> str:
    if stage == "frontend":
        return "plain HTML, CSS and JavaScript (ES modules), no build step unless the task requires one"
    return {"python": "Python 3.11+ with pytest", "node": "Node.js 20+ (ES modules) with the built-in node:test runner",
            "web": "plain HTML, CSS and JavaScript"}[stack]


def stage_commands(stack: str, stage: str) -> dict[str, str]:
    """setup / test / run commands of a stage's starter skeleton."""
    if stage == "backend" and stack == "python":
        return {"setup": "python -m pip install -r requirements.txt", "test": "python -m pytest -q", "run": "python -m app"}
    if stage == "backend" and stack == "node":
        return {"setup": "npm install", "test": "npm test", "run": "npm start"}
    if stage == "frontend":
        return {"setup": "", "test": "node --test", "run": "python -m http.server 5173"}
    return {"setup": "", "test": "", "run": ""}


def system_prompt(stage: str, name: str, idea: str, stack: str, notes: str = "") -> str:
    commands = stage_commands(stack, stage)
    extra = f"\n\nProject-specific guidance:\n{notes.strip()}" if notes.strip() else ""
    return STAGE_PROMPTS[stage].format(
        name=name, idea=idea.replace("\n", " ").strip(), rules=BASE_RULES, stack_line=stack_line(stack, stage),
        test_command=commands["test"] or "the project's tests", notes=extra)


GITIGNORE = {
    "python": "__pycache__/\n*.pyc\n.venv/\nvenv/\n.pytest_cache/\n.env\n",
    "node": "node_modules/\ndist/\n.env\n",
    "web": "node_modules/\n.env\n.DS_Store\n",
    "docs": ".DS_Store\n",
}


def readme(stage: str, name: str, idea: str, commands: dict[str, str]) -> str:
    lines = [f"# {name} — {stage}", "", idea.strip(), "", f"This folder is the **{stage}** stage of the project and its own Git repository, "
             "managed by Taskloom (task branches are created from `sandbox`).", ""]
    labelled = [(label, commands[key]) for label, key in (("Install", "setup"), ("Test", "test"), ("Run", "run")) if commands[key]]
    if labelled:
        lines += ["## Commands", "", *[f"- {label}: `{value}`" for label, value in labelled], ""]
    return "\n".join(lines)


def claude_md(stage: str, name: str, prompt: str) -> str:
    """Claude Code reads CLAUDE.md from the working folder: the stage's instructions live next to its code too."""
    return f"# {name} — {stage} stage\n\n{prompt}\n"


def starter_files(stage: str, stack: str, name: str) -> dict[str, str]:
    """A tiny skeleton that already passes its own test command."""
    if stage == "backend" and stack == "python":
        return {
            "requirements.txt": "pytest>=8\n",
            "app/__init__.py": "",
            "app/__main__.py": "from app.main import health\n\nif __name__ == \"__main__\":\n    print(health())\n",
            "app/main.py": f'"""{name} backend entry point."""\n\n\ndef health() -> dict:\n    return {{"status": "ok"}}\n',
            "tests/test_health.py": "from app.main import health\n\n\ndef test_health_reports_ok():\n    assert health() == {\"status\": \"ok\"}\n",
        }
    if stage == "backend" and stack == "node":
        return {
            "package.json": json.dumps({"name": slugify(name) or "backend", "version": "0.1.0", "private": True, "type": "module",
                                        "scripts": {"start": "node src/index.js", "test": "node --test"}}, indent=2) + "\n",
            "src/health.js": "export function health() {\n  return { status: 'ok' };\n}\n",
            "src/index.js": "import { health } from './health.js';\n\nconsole.log(health());\n",
            "test/health.test.js": "import assert from 'node:assert/strict';\nimport test from 'node:test';\nimport { health } from '../src/health.js';\n\ntest('health reports ok', () => {\n  assert.deepEqual(health(), { status: 'ok' });\n});\n",
        }
    if stage == "frontend":
        return {
            "package.json": json.dumps({"name": slugify(name) or "frontend", "version": "0.1.0", "private": True, "type": "module",
                                        "scripts": {"start": "python -m http.server 5173", "test": "node --test"}}, indent=2) + "\n",
            "index.html": f'<!doctype html>\n<html lang="en">\n<head>\n  <meta charset="utf-8">\n  <meta name="viewport" content="width=device-width, initial-scale=1">\n  <title>{name}</title>\n  <link rel="stylesheet" href="styles.css">\n</head>\n<body>\n  <main id="app"></main>\n  <script type="module" src="src/main.js"></script>\n</body>\n</html>\n',
            "styles.css": "body { font-family: system-ui, sans-serif; margin: 0; padding: 24px; }\n",
            "src/title.js": f"export const appTitle = {json.dumps(name)};\n",
            "src/main.js": "import { appTitle } from './title.js';\n\ndocument.getElementById('app').textContent = appTitle;\n",
            "test/title.test.js": "import assert from 'node:assert/strict';\nimport test from 'node:test';\nimport { appTitle } from '../src/title.js';\n\ntest('the app has a title', () => {\n  assert.ok(appTitle.length > 0);\n});\n",
        }
    if stage == "n8n":
        return {"workflows/README.md": f"# {name} workflows\n\nOne exported n8n workflow (JSON) per file. Describe the trigger, inputs and outputs of each below.\n"}
    return {}


def stage_documents(stage: str, name: str, idea: str, requirements: list[str], questions: list[str]) -> dict[str, str]:
    if stage == "analysis":
        reqs = "\n".join(f"- {item}" for item in requirements) or "- (to be refined by the first analysis)"
        asks = "\n".join(f"- {item}" for item in questions) or "- (none yet)"
        return {
            "docs/requirements.md": f"# {name} — requirements\n\n## Goal\n\n{idea}\n\n## Initial requirements\n\n{reqs}\n",
            "docs/open-questions.md": f"# Open questions\n\n{asks}\n",
            "docs/glossary.md": "# Glossary\n\nDefine domain terms here so every stage uses the same words.\n",
        }
    if stage == "qa":
        return {"test-plan.md": f"# {name} — test plan\n\n## Scope\n\n{idea}\n\n## Checks\n\n- Every acceptance criterion of every task is verified.\n- The automated tests of the other stages pass.\n- Error and empty states are exercised.\n"}
    return {}


def knowledge_documents(name: str, idea: str, stack: str, stages: list[str], architecture: str,
                        requirements: list[str]) -> dict[str, str]:
    arch = architecture.strip() or (
        f"The project is split into stages, each with its own folder and Git repository: {', '.join(stages)}.\n"
        f"Stack: {stack_line(stack, 'backend') if 'backend' in stages else stack_line(stack, 'frontend')}.\n"
        "Stages communicate through documented interfaces only; record every cross-stage contract here.")
    reqs = "\n".join(f"- {item}" for item in requirements) or "- To be refined by the first analysis."
    return {
        "PROJECT.md": f"# {name}\n\n{idea}\n\n## Initial requirements\n\n{reqs}\n",
        "ARCHITECTURE.md": f"# Architecture\n\n{arch}\n",
        "CONVENTIONS.md": "# Conventions\n\n- Small, focused commits with imperative English messages.\n- One task = one branch (named by the task id); never commit to `main`, `develop` or `sandbox` directly.\n"
                          "- Tests accompany every behaviour change.\n- Public interfaces are documented in the README of the stage that owns them.\n- No secrets in the repository.\n",
        "DEFINITION_OF_DONE.md": "# Definition of done\n\n- The acceptance criteria from the analysis are met and checked.\n- Automated tests pass.\n- The README and docs reflect the change.\n- No unrelated files were changed.\n",
    }


# ----------------------------------------------------------------------------- AI enrichment

AI_INSTRUCTIONS = """\
You help set up a new software project. Reply with ONE JSON object only, no prose, with these keys:
"name": short project name; "description": 1-3 sentences; "requirements": up to 8 short strings;
"open_questions": up to 5 short strings; "architecture": a short paragraph; "stage_notes": an object mapping each of
{stages} to 2-5 lines of project-specific guidance for that stage.
Project idea:
"""


def sanitize_enrichment(data: object, stages: list[str]) -> dict:
    """Keep only well-formed, bounded fields from an AI answer; anything else is dropped."""
    if not isinstance(data, dict):
        return {}

    def text(value: object, limit: int) -> str:
        return value.strip()[:limit] if isinstance(value, str) else ""

    def items(value: object, count: int) -> list[str]:
        return [text(item, 200) for item in value[:count] if text(item, 200)] if isinstance(value, list) else []

    def note(value: object) -> str:
        """Per-stage guidance arrives as one string or (often) as a list of lines."""
        if isinstance(value, list):
            return "\n".join(f"- {line}" for line in items(value, 6))[:800]
        return text(value, 800)

    notes = data.get("stage_notes")
    return {
        "name": text(data.get("name"), 80),
        "description": text(data.get("description"), 600),
        "requirements": items(data.get("requirements"), 8),
        "open_questions": items(data.get("open_questions"), 5),
        "architecture": text(data.get("architecture"), 1500),
        "stage_notes": {stage: note(notes.get(stage)) for stage in stages if isinstance(notes, dict) and note(notes.get(stage))},
    }


def extract_json(raw: str) -> object:
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in the answer")
    return json.loads(raw[start:end + 1])


async def default_refiner(prompt: str) -> str:
    """Ask Claude Code (non-interactive) when installed, else a local Ollama model."""
    from .services import _ollama_runner, command  # late import: services imports a lot

    claude = shutil.which("claude")
    if claude:
        with tempfile.TemporaryDirectory(prefix="taskloom-builder-") as scratch:  # nothing to read or change there
            code, output = await command([claude, "-p", prompt], Path(scratch), 180)
        if code == 0 and output.strip():
            return output
        raise RuntimeError(output.strip()[:300] or "Claude Code returned nothing")
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: _ollama_runner._chat("You output only JSON.", prompt, timeout=120))


# ----------------------------------------------------------------------------- blueprint + build

class Blueprint(BaseModel):
    project: SDLCProjectConfig
    root: str
    knowledge: dict[str, str]
    stage_files: dict[str, dict[str, str]]
    notes: list[str] = Field(default_factory=list)
    ai_used: bool = False


def plan(request: BuildRequest, enrichment: dict | None = None) -> Blueprint:
    """Everything that will be created, decided in memory (no disk, no network)."""
    enrichment = enrichment or {}
    project_id = project_id_for(request)
    name = (request.name.strip() or enrichment.get("name") or project_name_for(request, project_id))[:80]
    stack = request.stack if request.stack != "auto" else detect_stack(request.idea)
    stages = [stage for stage in STAGE_ORDER if stage in (request.stages or detect_stages(request.idea, stack))]
    if "analysis" not in stages:
        stages.insert(0, "analysis")
    root = Path(request.base_dir).expanduser() if request.base_dir.strip() else DEFAULT_ROOT
    root = root / project_id
    notes_by_stage = enrichment.get("stage_notes", {})

    agents: dict[str, AgentConfig] = {}
    stage_files: dict[str, dict[str, str]] = {}
    for stage in STAGE_ORDER:
        if stage not in stages:
            agents[stage] = AgentConfig(enabled=False)
            continue
        commands = stage_commands(stack, stage)
        prompt = system_prompt(stage, name, request.idea, stack, notes_by_stage.get(stage, ""))
        folder = root / stage
        agents[stage] = AgentConfig(
            knowledge_path=str(root / "knowledge"), project_path=str(folder), system_prompt=prompt,
            test_instructions={"command": commands["test"]} if commands["test"] else {},
            setup_command=commands["setup"], run_command=commands["run"],
            repository=RepositoryConfig(mode=RepositoryMode.create, local_path=str(folder), default_branch="main"))
        files = {
            "README.md": readme(stage, name, request.idea, commands),
            "CLAUDE.md": claude_md(stage, name, prompt),
            ".gitignore": GITIGNORE["python" if stack == "python" and stage == "backend" else "node" if stage in ("backend", "frontend") else "docs"],
        }
        files.update(starter_files(stage, stack, name))
        files.update(stage_documents(stage, name, request.idea, enrichment.get("requirements", []), enrichment.get("open_questions", [])))
        stage_files[stage] = files

    project = SDLCProjectConfig(
        id=project_id, name=name, description=enrichment.get("description") or request.idea.strip()[:600],
        workflow=workflow_for(request.autonomy, stages), agents=agents)
    knowledge = knowledge_documents(name, request.idea, stack, stages, enrichment.get("architecture", ""), enrichment.get("requirements", []))
    return Blueprint(project=project, root=str(root), knowledge=knowledge, stage_files=stage_files, ai_used=bool(enrichment))


def with_free_id(request: BuildRequest, existing_ids: set[str]) -> BuildRequest:
    """When the id was derived (not typed by the user), pick the next free `name-2`, `name-3` ... instead of failing."""
    if request.id.strip():
        return request
    base = project_id_for(request)

    def taken(candidate: str) -> bool:
        root = (Path(request.base_dir).expanduser() if request.base_dir.strip() else DEFAULT_ROOT) / candidate
        return candidate in existing_ids or (root.exists() and any(root.iterdir()))

    candidate, number = base, 1
    while taken(candidate):
        number += 1
        candidate = f"{base[:36]}-{number}"
    return request.model_copy(update={"id": candidate})


def remove_tree(path: Path) -> None:
    """Delete a folder including Git's read-only object files (plain rmtree leaves them behind on Windows)."""
    def make_writable(function, target, _error):
        try:
            os.chmod(target, stat.S_IWRITE)
            function(target)
        except OSError:
            pass  # best effort: a locked file must not hide the original error

    shutil.rmtree(path, onerror=make_writable)


def write_tree(base: Path, files: dict[str, str]) -> int:
    for relative, content in files.items():
        target = (base / relative).resolve()
        if base.resolve() not in target.parents:  # a template can never write outside its folder
            raise BuildError(f"Refusing to write outside the project folder: {relative}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
    return len(files)


def check_destination(blueprint: Blueprint, existing_ids: set[str]) -> Path:
    project_id = blueprint.project.id
    if project_id in existing_ids:
        raise BuildError(f"A project with the id `{project_id}` already exists; choose another name")
    root = Path(blueprint.root)
    if root.exists() and any(root.iterdir()):
        raise BuildError(f"The folder {root} already exists and is not empty; choose another name or base folder")
    return root


async def build(request: BuildRequest, existing_ids: set[str], save: Callable[[SDLCProjectConfig], None],
                refiner: Refiner | None = default_refiner) -> dict:
    """Create the project on disk and save its configuration. Raises BuildError for anything the user can fix."""
    from .sdlc_git import command, heal_local_repository

    request = with_free_id(request, existing_ids)
    enrichment: dict = {}
    notes: list[str] = []
    if request.use_ai and refiner is not None:
        base = plan(request)
        prompt = AI_INSTRUCTIONS.format(stages=", ".join(s for s in STAGE_ORDER if s in base.stage_files)) + request.idea
        try:
            enrichment = sanitize_enrichment(extract_json(await refiner(prompt)), list(base.stage_files))
            notes.append("AI enrichment applied: description, requirements, architecture and per-stage guidance.")
        except Exception as exc:  # the templates are a complete project on their own
            notes.append(f"No AI answer was available ({str(exc)[:120]}); the built-in templates were used.")
    blueprint = plan(request, enrichment)
    root = check_destination(blueprint, existing_ids)

    created: list[Path] = []
    try:
        root.mkdir(parents=True, exist_ok=True)
        created.append(root)
        files_written = write_tree(root / "knowledge", blueprint.knowledge)
        commits: dict[str, str] = {}
        for stage, files in blueprint.stage_files.items():
            folder = root / stage
            files_written += write_tree(folder, files)
            code, output = await command(["git", "init", "-q", "-b", "main"], folder)
            if code:
                raise BuildError(f"git init failed in {folder}: {output.strip()}")
            await heal_local_repository(folder, blueprint.project, stage, "main")  # initial commit + the sandbox base
            _, sha = await command(["git", "rev-parse", "--short", "HEAD"], folder)
            commits[stage] = sha.strip()
        save(blueprint.project)
    except BaseException:
        remove_tree(root)  # a half-built project is worse than none
        raise
    return {
        "project": blueprint.project.model_dump(), "root": str(root), "files_written": files_written,
        "folders": {stage: str(root / stage) for stage in blueprint.stage_files}, "commits": commits,
        "notes": notes, "ai_used": bool(enrichment),
    }


def preview(request: BuildRequest, existing_ids: set[str]) -> dict:
    """What a build would create, without touching the disk (AI enrichment is only applied by the real build)."""
    blueprint = plan(with_free_id(request, existing_ids))
    problems: list[str] = []
    try:
        check_destination(blueprint, existing_ids)
    except BuildError as exc:
        problems.append(str(exc))
    return {
        "id": blueprint.project.id, "name": blueprint.project.name, "root": blueprint.root,
        "stages": [{"stage": stage, "folder": str(Path(blueprint.root) / stage), "files": sorted(files),
                    "system_prompt": blueprint.project.agents[stage].system_prompt,
                    "test_command": blueprint.project.agents[stage].test_instructions.get("command", ""),
                    "run_command": blueprint.project.agents[stage].run_command}
                   for stage, files in blueprint.stage_files.items()],
        "knowledge": sorted(blueprint.knowledge), "workflow": blueprint.project.workflow.model_dump(), "problems": problems,
    }
