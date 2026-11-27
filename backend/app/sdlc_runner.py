"""Run an SDLC stage with a real CLI coding agent (Claude Code or Codex).

The agent works inside the stage's ``project_path``. Taskloom — not the agent — decides what
actually changed (by snapshotting the folder before and after) and runs the stage's test
command, so the recorded result reflects what happened on disk rather than what the model claims.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

from .models import (
    AgentConfig, AgentResult, AgentType, Change, HumanIntervention, RevisionRequest,
    SDLCProjectConfig, SDLCTask, StageRunner, TestResults,
)
from .sdlc_git import ensure_workspace, prepare_task_branch, resolve_token
from .process_tools import process_image
from .services import (
    _command_started_handler,
    WORKSPACE_IGNORED_DIRECTORIES, agent_error_detail, agent_executable, agent_name,
    agent_response, command, initial_agent_args, run_agent_command, test_plan,
    OllamaCodingAgent, ModelResolutionService, _ollama_runner,
)

STAGE_ROLES = {
    "analysis": "software analyst",
    "backend": "backend developer",
    "backend_review": "analyst reviewing backend implementation",
    "n8n": "n8n workflow engineer",
    "frontend": "frontend developer",
    "frontend_review": "analyst reviewing frontend implementation",
    "qa": "QA engineer",
    "qa_review": "QA engineer reviewing test results",
    "analyst_final_review": "analyst performing final assessment",
    "po_pending_approval": "product owner evaluating release readiness",
}
REPORT_ONLY_STAGES = {"analysis", "qa"}
AGENT_STATUSES = {"completed", "needs_human", "needs_revision", "blocked"}
SNAPSHOT_MAX_FILES = 50_000
AGENT_LIMIT = re.compile(r"hit your .{0,40}limit|usage limit|rate limit|rate_limit|\b429\b|overloaded", re.IGNORECASE)
TEST_OUTPUT_TAIL = 4_000

Snapshot = dict[str, tuple[int, int]]


def resolve_runner(config: AgentConfig, workdir: str | None = None) -> StageRunner:
    """Pick who runs a stage; `auto` prefers Ollama when available, then CLI agents."""
    if config.runner != StageRunner.auto:
        return config.runner
    
    # Check if Ollama is available and preferred
    from .services import _ollama_discovery
    try:
        import asyncio
        # Check Ollama connection
        if asyncio.run(_ollama_discovery.check_connection()):
            # Ollama is available, use it as default
            return StageRunner.ollama
    except:
        pass
    
    # Fall back to CLI agents if Ollama is not available
    if workdir if workdir is not None else config.project_path:
        for runner in (StageRunner.claude, StageRunner.codex):
            if shutil.which(runner.value):
                return runner
    
    return StageRunner.ollama


def snapshot_folder(root: Path) -> Snapshot:
    """Record (mtime, size) for every file under root, skipping VCS/dependency/build folders."""
    files: Snapshot = {}
    for directory, subdirectories, filenames in os.walk(root):
        subdirectories[:] = [name for name in subdirectories if name not in WORKSPACE_IGNORED_DIRECTORIES]
        for filename in filenames:
            path = Path(directory) / filename
            try:
                stat = path.stat()
            except OSError:
                continue
            files[path.relative_to(root).as_posix()] = (stat.st_mtime_ns, stat.st_size)
            if len(files) >= SNAPSHOT_MAX_FILES:
                return files
    return files


def folder_changes(before: Snapshot, after: Snapshot) -> list[Change]:
    changes = [Change(file=path, description="", kind="created") for path in sorted(after.keys() - before.keys())]
    changes += [Change(file=path, description="", kind="modified") for path in sorted(after.keys() & before.keys()) if after[path] != before[path]]
    changes += [Change(file=path, description="", kind="deleted") for path in sorted(before.keys() - after.keys())]
    return changes


def stage_feedback(task: SDLCTask, stage: str) -> list[str]:
    """Prompt sections with revision requests aimed at this stage and human answers given to it."""
    sections = []
    revisions = [revision for revision in task.revisions if revision.target_agent == stage][-3:]
    if revisions:
        sections.append(
            "## Revision requested — address this first\n" + "\n\n".join(
                ("A human reviewer found a problem with the previous result; their opinion is binding: " if revision.requesting_agent == "human"
                 else f"From {revision.requesting_agent}: ") + revision.reason
                + (f"\n{revision.description}" if revision.description and revision.description != revision.reason else "")
                for revision in revisions
            )
        )
    answers = [
        item for item in task.human_interventions
        if item.status == "responded" and (item.context.get("stage") or item.requesting_agent) == stage
        and item.context.get("kind") not in ("agent_unavailable", "interrupted")
    ][-5:]
    if answers:
        sections.append(
            "## Answers from a human — follow them\n" + "\n\n".join(
                f"Question: {item.description}\nAnswer: {item.response}" for item in answers
            )
        )
    return sections


def consult_sections(task: SDLCTask, stage: str) -> list[str]:
    """Questions this stage asked the analyst (and the answers) or, for the analyst, the question to answer."""
    sections = []
    if stage == "analysis" and task.consult_question_id:
        asked = next((q for q in task.stage_questions if q.id == task.consult_question_id), None)
        if asked:
            sections.append(
                f"## Question from the {asked.asking_stage} stage — answer it now\n"
                f"The {asked.asking_stage} stage cannot continue without an answer:\n\n{asked.question}\n\n"
                "Answer from the code, the documents and your analysis; a human's answers above (if any) are binding. "
                "In this reply the `summary` must contain your numbered answers. Use status `completed` only when EVERY "
                "question is answered with confidence. If anything is still ambiguous, do not guess: use status "
                "`needs_human` and put in `question_for_human` a numbered list of ONLY the still-unanswered questions "
                "(a human operator will answer them)."
            )
    answered = [q for q in task.stage_questions if q.asking_stage == stage and q.status == "answered"][-5:]
    if answered:
        sections.append(
            "## Answers to your earlier questions — follow them\n" + "\n\n".join(
                f"Question: {q.question}\nAnswer ({'human operator via the analyst' if q.answered_by == 'human' else 'analyst'}): {q.answer}"
                for q in answered
            )
        )
    return sections


def other_stage_folders(stage: str, project: SDLCProjectConfig) -> dict[str, str]:
    """Existing folders of the other enabled stages (each stage may have its own repository)."""
    folders = {}
    for other, config in project.agents.items():
        if other == stage or not config.enabled:
            continue
        path = project.stage_path(other)
        if path and Path(path).expanduser().is_dir():
            folders[other] = str(Path(path).expanduser().resolve())
    return folders


def readable_dirs(stage: str, project: SDLCProjectConfig, config: AgentConfig, workdir: Path) -> list[str]:
    """Directories outside the working folder the agent needs to read: other stages and the knowledge path."""
    dirs = []
    candidates = [*other_stage_folders(stage, project).values()]
    if config.knowledge_path:
        candidates.append(config.knowledge_path)
    for path in candidates:
        resolved = Path(path).expanduser().resolve()
        if not resolved.is_dir() or resolved == workdir or workdir in resolved.parents:
            continue
        if str(resolved) not in dirs:
            dirs.append(str(resolved))
    return dirs


def build_stage_prompt(stage: str, task: SDLCTask, project: SDLCProjectConfig, config: AgentConfig, workdir: Path) -> str:
    role = STAGE_ROLES.get(stage, stage)
    sections = [f"You are the {role} stage of an automated software delivery pipeline (Taskloom) for project \"{project.name}\"."]
    if project.description:
        sections.append(f"Project description: {project.description}")
    if config.system_prompt.strip():
        sections.append("## Your instructions\n" + config.system_prompt.strip())
    sections.append(
        f"## Task {task.base_task.task_id}\nTitle: {task.title}\nPriority: {task.priority}\n"
        f"Description:\n{task.description or '(no description)'}"
    )
    if config.knowledge_path:
        sections.append(
            "## Project knowledge\n"
            f"Before starting, read the Markdown files under `{config.knowledge_path}`. "
            "They describe this project's conventions and decisions; follow them."
        )
    previous = [
        f"### {name} ({result.status})\n{result.summary}"
        + (f"\nChanged files: {', '.join(change.file for change in result.changes[:50])}" if result.changes else "")
        + (f"\nOpen issues: {'; '.join(result.issues[:10])}" if result.issues else "")
        + (f"\nTaskloom ran this stage's tests: {'passed' if result.tests.passed else 'FAILED'}" if result.tests.executed else "")
        for name, result in task.agent_results.items() if name != stage
    ]
    if previous:
        sections.append("## Results from earlier stages\n" + "\n\n".join(previous))
    sections.extend(stage_feedback(task, stage))
    sections.extend(consult_sections(task, stage))
    if stage in REPORT_ONLY_STAGES:
        work = (
            "Investigate the existing code and documents in your working folder and produce your report. "
            "Do not change application source code in this stage."
        )
    else:
        work = (
            "Implement everything this stage needs for the task, as the smallest complete change. "
            "Add or update tests where the project has them, and update affected Markdown documentation."
        )
    test_command = (config.test_instructions.get("command") or "").strip()
    if test_command:
        testing = (
            f"You may not be allowed to run shell commands. Taskloom itself runs `{test_command}` in this folder "
            "after you finish and records the result, so do not report \"tests were not run\" as an issue."
        )
    else:
        testing = "You may not be allowed to run shell commands, and no test command is configured for this stage; review tests by reading them."
    others = other_stage_folders(stage, project)
    if others:
        sections.append(
            "## Other stages' folders (read them, never change them)\n"
            + "\n".join(f"- {name}: `{path}`" for name, path in others.items())
        )
    sections.append(
        "## Rules\n"
        f"- Your working folder is `{workdir}`. Only create or modify files inside it.\n"
        "- Do not commit, push, or switch Git branches; a human reviews the result.\n"
        f"- {work}\n"
        f"- {testing}\n"
        + (
            "- If anything in the task or the code is ambiguous and you cannot resolve it yourself, do not guess: stop and "
            "ask with status `needs_human`, listing every open question, numbered, in `question_for_human`. A human operator answers.\n"
            if stage == "analysis" else
            "- If anything in the task is ambiguous or you lack information, do not guess: stop and ask with status "
            "`needs_human`, listing every open question, numbered, in `question_for_human`. The analyst answers them "
            "(asking a human when needed) and you are re-run with the answers.\n"
        ) +
        "- If an earlier stage's output is wrong or incomplete and blocks you, report it (status `needs_revision`)."
    )
    sections.append(
        "## Final answer format\n"
        "End your reply with exactly one fenced ```json block containing:\n"
        "{\"status\": \"completed | needs_human | needs_revision | blocked\", "
        "\"summary\": \"what you did or found, in a few sentences\", "
        "\"issues\": [\"open problems or risks\"], "
        "\"recommendations\": {\"category\": [\"suggestion\"]}, "
        "\"question_for_human\": \"only for needs_human\", "
        "\"revision_target\": \"stage to send back to, only for needs_revision\", "
        "\"revision_reason\": \"only for needs_revision\"}"
    )
    return "\n\n".join(sections)


def parse_agent_report(response: str) -> dict:
    """Return the last ```json block of the agent's reply as a dict, or {} when absent/invalid."""
    for block in reversed(re.findall(r"```json\s*(.*?)```", response, flags=re.DOTALL | re.IGNORECASE)):
        try:
            report = json.loads(block)
        except json.JSONDecodeError:
            continue
        if isinstance(report, dict):
            return report
    return {}


def _string_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)] if value else []


def _recommendations(value) -> dict[str, list[str]]:
    if isinstance(value, dict):
        return {str(key): _string_list(items) for key, items in value.items()}
    items = _string_list(value)
    return {"general": items} if items else {}


async def run_stage_tests(config: AgentConfig, workdir: Path) -> TestResults:
    """Run the stage's configured test command (test_instructions["command"]); nothing is auto-detected."""
    test_command = (config.test_instructions.get("command") or "").strip()
    if not test_command:
        return TestResults()
    args, cwd = test_plan(workdir, test_command, config.test_instructions.get("working_directory") or None)
    code, output = await command(args, cwd, 1800)
    passed = code == 0
    return TestResults(
        executed=True,
        passed=passed,
        results=[{"name": test_command, "status": "passed" if passed else "failed", "exit_code": code, "output": output[-TEST_OUTPUT_TAIL:]}],
    )


def record_agent_process(pid_file: Path, stage: str):
    """Return a callback that writes the started agent's PID and image name to `pid_file`."""
    def started(pid: int) -> None:
        image = process_image(pid) or ""
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text(json.dumps({"pid": pid, "image": image, "stage": stage}), encoding="utf-8")
    return started


# Claude Code in acceptEdits mode may edit files but is refused every shell command, so QA could never run the tests.
# These prefixes (and only these) are allowed: test/build/install tools and read-only git.
SDLC_ALLOWED_TOOLS = [
    "Bash(python -m pytest:*)", "Bash(pytest:*)", "Bash(python -m pip install:*)", "Bash(pip install:*)",
    "Bash(npm test:*)", "Bash(npm run:*)", "Bash(npm install:*)", "Bash(npm ci:*)", "Bash(node --test:*)",
    "Bash(git status:*)", "Bash(git diff:*)", "Bash(git log:*)", "Bash(git show:*)",
]


async def run_cli_stage(stage: str, task: SDLCTask, project: SDLCProjectConfig, config: AgentConfig, runner: StageRunner,
                        pid_file: Path | None = None, repo_token: str | None = None, persist_project=None,
                        model_name: str | None = None) -> AgentResult:
    """Run one SDLC stage with Claude Code or Codex inside the stage's folder (or the project repository)."""
    agent_type = AgentType.claude if runner == StageRunner.claude else AgentType.codex
    display_name = agent_name(agent_type)
    repository = project.stage_repository(stage)
    has_repo = repository.mode.value != "none"
    if has_repo:
        # Clone (existing repo) or initialise (new repo) this stage's repository before it runs.
        await ensure_workspace(project, stage, repo_token, persist_project, lambda message: task.base_task.logs.append(message))
    stage_path = project.stage_path(stage)
    if not stage_path:
        raise RuntimeError(f"Stage '{stage}' needs a project_path or a repository to run {display_name}")
    workdir = Path(stage_path).expanduser().resolve()
    if not workdir.is_dir():
        raise RuntimeError(f"Project folder for stage '{stage}' does not exist: {workdir}")

    executable = agent_executable(agent_type)
    # In a Git repository every task works on its own branch (sdlc/<task-id>), started from the
    # freshly fetched remote base branch when the repository has an origin.
    base_branch = repository.default_branch if has_repo else str(config.github_config.get("branch") or "main")
    await prepare_task_branch(task, workdir, base_branch, resolve_token(repo_token) if has_repo else None, auto_stash=has_repo)
    prompt = build_stage_prompt(stage, task, project, config, workdir)
    state = task.base_task
    state.step = f"{display_name} is running the {stage} stage"

    before = snapshot_folder(workdir)
    token = _command_started_handler.set(record_agent_process(pid_file, stage) if pid_file else None)
    try:
        args = initial_agent_args(agent_type, executable, prompt, readable_dirs(stage, project, config, workdir), SDLC_ALLOWED_TOOLS, model=model_name)
        code, output = await run_agent_command(agent_type, args, workdir, state, config.cli_timeout_seconds)
    finally:
        _command_started_handler.reset(token)
        if pid_file:
            pid_file.unlink(missing_ok=True)
    changes = folder_changes(before, snapshot_folder(workdir))
    session_id, response = agent_response(agent_type, output)
    state.codex_thread_id = session_id or state.codex_thread_id
    state.live_response = ""

    if code:
        detail = agent_error_detail(output) or output.strip()[-2000:]
        if AGENT_LIMIT.search(detail or output):
            # Usage/rate limit: temporary, not a failure of the work. Park it for a human to resume later.
            return AgentResult(
                agent=stage, status="needs_human", summary=f"{display_name} is unavailable: {detail[:300]}",
                changes=changes, issues=[detail], raw_output=output[-20_000:],
                human_intervention=HumanIntervention(
                    id="", task_id=task.base_task.task_id, requesting_agent=stage, reason="Agent unavailable",
                    description=f"{display_name} hit a usage or rate limit: {detail[:300]}. Answer 'resume' after the "
                                "limit resets to run this stage again, or 'stop'.",
                    context={"kind": "agent_unavailable"},
                ),
            )
        return AgentResult(
            agent=stage, status="failed", summary=f"{display_name} exited with code {code}",
            changes=changes, issues=[detail] if detail else [], raw_output=output[-20_000:],
        )

    report = parse_agent_report(response)
    status = report.get("status") if report.get("status") in AGENT_STATUSES else "completed"
    issues = _string_list(report.get("issues"))
    if not report:
        issues.append("The agent did not end with the requested JSON report; its full reply is in raw_output.")
    if stage not in REPORT_ONLY_STAGES and status == "completed" and not changes:
        issues.append(f"{display_name} finished without changing any file in {workdir}.")

    tests = await run_stage_tests(config, workdir)
    tests_failed = tests.executed and not tests.passed and status == "completed"
    if tests_failed:
        # Let the same stage fix its own work; the manager enforces max_revision_attempts.
        status = "needs_revision"
        issues.append("Stage tests failed; see test results.")

    result = AgentResult(
        agent=stage,
        status=status,
        summary=str(report.get("summary") or response.strip()[:1000] or f"{display_name} returned no text"),
        changes=changes,
        tests=tests,
        recommendations=_recommendations(report.get("recommendations")),
        issues=issues,
        raw_output=response[-20_000:] or output[-20_000:],
    )
    if status == "needs_human":
        question = str(report.get("question_for_human") or result.summary)
        result.human_intervention = HumanIntervention(
            id="", task_id=task.base_task.task_id, requesting_agent=stage,
            reason="Agent needs a human decision", description=question,
        )
    elif tests_failed:
        failure = tests.results[0]
        result.revision_request = RevisionRequest(
            requesting_agent=stage, target_agent=stage,
            reason=f"Tests failed: `{failure['name']}` exited with code {failure['exit_code']}",
            description=f"Fix the code so the tests pass. Test output (tail):\n{failure['output'][-1500:]}",
        )
    elif status == "needs_revision":
        result.revision_request = RevisionRequest(
            requesting_agent=stage,
            target_agent=str(report.get("revision_target") or ""),
            reason=str(report.get("revision_reason") or result.summary),
            description=result.summary,
        )
    return result


async def run_ollama_stage(stage: str, task: SDLCTask, project: SDLCProjectConfig, config: AgentConfig,
                          pid_file: Path | None = None, repo_token: str | None = None, persist_project=None,
                          model_name: str | None = None) -> AgentResult:
    """Run one SDLC stage with Ollama coding agent inside the stage's folder."""
    repository = project.stage_repository(stage)
    has_repo = repository.mode.value != "none"
    if has_repo:
        # Clone (existing repo) or initialise (new repo) this stage's repository before it runs.
        await ensure_workspace(project, stage, repo_token, persist_project, lambda message: task.base_task.logs.append(message))
    stage_path = project.stage_path(stage)
    if not stage_path:
        raise RuntimeError(f"Stage '{stage}' needs a project_path or a repository to run Ollama")
    workdir = Path(stage_path).expanduser().resolve()
    if not workdir.is_dir():
        raise RuntimeError(f"Project folder for stage '{stage}' does not exist: {workdir}")

    # In a Git repository every task works on its own branch (sdlc/<task-id>)
    base_branch = repository.default_branch if has_repo else str(config.github_config.get("branch") or "main")
    await prepare_task_branch(task, workdir, base_branch, resolve_token(repo_token) if has_repo else None, auto_stash=has_repo)
    
    state = task.base_task
    state.step = f"Ollama is running the {stage} stage"
    
    # Create Ollama coding agent with the specified model
    # Use provided model_name, or get from project configuration
    if model_name:
        # Get Ollama endpoint from project AI settings
        ollama_endpoint = project.ai_settings.ollama_endpoint
        coding_agent = OllamaCodingAgent(base_url=ollama_endpoint, model=model_name)
    else:
        # Fallback to legacy behavior
        coding_agent = OllamaCodingAgent()
    
    # Record PID if requested
    if pid_file:
        import json
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text(json.dumps({
            "pid": os.getpid(),
            "image": "ollama_coding_agent",
            "stage": stage
        }), encoding="utf-8")
    
    try:
        # Run the stage with Ollama coding agent
        result = await coding_agent.run_stage(stage, task, project, config, workdir)
        
        # Run tests after agent completes
        tests = await run_stage_tests(config, workdir)
        result.tests = tests
        
        # Handle test failures
        if tests.executed and not tests.passed and result.status == "completed":
            result.status = "needs_revision"
            result.issues.append("Stage tests failed; see test results.")
            failure = tests.results[0] if tests.results else {}
            result.revision_request = RevisionRequest(
                requesting_agent=stage,
                target_agent=stage,
                reason=f"Tests failed: exit code {failure.get('exit_code', 1)}",
                description=f"Fix the code so the tests pass. Test output:\n{failure.get('output', '')[-1500:]}",
            )
        
        return result
        
    except Exception as exc:
        return AgentResult(
            agent=stage,
            status="failed",
            summary=f"Ollama coding agent failed: {exc}",
            changes=[],
            tests=TestResults(),
            issues=[str(exc)],
            raw_output=""
        )
    finally:
        if pid_file:
            pid_file.unlink(missing_ok=True)


# تابع اصلی برای اجرای مرحله که runner مناسب را انتخاب می‌کند
async def execute_stage(stage: str, task: SDLCTask, project: SDLCProjectConfig,
                       pid_file: Path | None = None, repo_token: str | None = None,
                       persist_project=None) -> AgentResult:
    """Execute a stage with the appropriate runner based on configuration.
    
    Provider/model priority:
    1. Agent-level provider_override (new explicit field)
    2. Stage-level provider in project.ai_settings
    3. Project-level defaults in project.ai_settings
    4. Legacy AgentConfig.runner when != auto (backward compatibility)
    5. Auto-detect (Ollama available → ollama; else first installed CLI)
    """
    config = project.agents.get(stage, AgentConfig())
    
    # For legacy projects: if runner is explicitly set and no new provider fields exist,
    # map the legacy runner directly to a provider so old configs keep working.
    if config.runner != StageRunner.auto and not config.provider_override:
        runner_to_provider = {
            StageRunner.claude: "claude",
            StageRunner.codex: "codex",
            StageRunner.ollama: "ollama",
        }
        legacy_provider = runner_to_provider.get(config.runner)
        if legacy_provider:
            # Use the legacy runner with the project's default model for that provider
            runner = config.runner
            provider_id = legacy_provider
            model_name = project.ai_settings.default_model
            # For non-Ollama runners, model_name may not make sense — let it be empty so CLI uses default
            if legacy_provider != "ollama":
                model_name = None
            if runner == StageRunner.ollama:
                return await run_ollama_stage(stage, task, project, config, pid_file, repo_token, persist_project, model_name)
            else:
                return await run_cli_stage(stage, task, project, config, runner, pid_file, repo_token, persist_project, model_name)
    
    # Use provider resolution to determine which provider and model to use
    from .services import ProviderResolutionService
    resolver = ProviderResolutionService()
    
    # Get effective provider and model for this stage
    provider_id, model_name, is_overridden = resolver.resolve_provider_for_stage(
        stage, project, config
    )
    
    # Validate provider availability — do NOT silently fall back to another provider
    available, error_msg = await resolver.validate_provider_availability(provider_id, model_name)
    if not available:
        return AgentResult(
            agent=stage,
            status="failed",
            raw_output=f"Provider error: {error_msg}",
            issues=[f"Provider '{provider_id}' or model '{model_name}' is unavailable: {error_msg}"]
        )
    
    # Get runner based on provider
    from .providers import provider_registry
    provider = provider_registry.get_provider(provider_id)
    if not provider:
        return AgentResult(
            agent=stage,
            status="failed",
            raw_output=f"Provider '{provider_id}' not found",
            issues=[f"Provider '{provider_id}' not found in registry"]
        )
    
    runner = provider.get_runner_type()
    
    # Execute with the appropriate runner
    if runner == StageRunner.ollama:
        return await run_ollama_stage(stage, task, project, config, pid_file, repo_token, persist_project, model_name)
    else:
        return await run_cli_stage(stage, task, project, config, runner, pid_file, repo_token, persist_project, model_name)


# ===== TEAM WORKFLOW GATE FUNCTIONS =====

def build_stage_prompt_for_review(stage: str, task: SDLCTask, project: SDLCProjectConfig, 
                                   config: AgentConfig, workdir: Path) -> str:
    """Build prompt for review stages (backend_review, frontend_review, qa_review, analyst_final_review).
    
    These stages don't produce code but review previous outputs and decide on approval/revision.
    """
    role = STAGE_ROLES.get(stage, stage)
    sections = [f"You are the {role} stage of an automated software delivery pipeline (Taskloom) for project \"{project.name}\"."]
    
    if project.description:
        sections.append(f"Project description: {project.description}")
    
    if config.system_prompt.strip():
        sections.append("## Your instructions\n" + config.system_prompt.strip())
    
    # Task context
    sections.append(
        f"## Task {task.base_task.task_id}\nTitle: {task.title}\nPriority: {task.priority}\n"
        f"Description:\n{task.description or '(no description)'}"
    )
    
    # Approved requirements (from task specification if available)
    if task.task_specification:
        sections.append("## Approved Requirements\n")
        sections.append(f"User Need: {task.task_specification.user_business_need}")
        if task.task_specification.acceptance_criteria:
            sections.append("\n### Acceptance Criteria\n" + "\n".join(f"- {c}" for c in task.task_specification.acceptance_criteria))
    
    # Previous stage results
    if stage in {"backend_review"}:
        previous_stage = "backend"
        if previous_stage in task.agent_results:
            result = task.agent_results[previous_stage]
            sections.append(f"\n## {previous_stage} Result\nStatus: {result.status}\nSummary: {result.summary}")
            if result.changes:
                sections.append(f"\n### Changed Files\n" + "\n".join(f"- {c.file} ({c.kind})" for c in result.changes))
            if result.issues:
                sections.append(f"\n### Issues\n" + "\n".join(f"- {i}" for i in result.issues))
        
        # Include backend handoff if available
        if task.backend_handoff:
            sections.append("\n## Backend Handoff\n")
            if task.backend_handoff.api_contract:
                api = task.backend_handoff.api_contract
                sections.append(f"API Contract: {api.get('method', 'GET')} {api.get('path', '/api')}")
                if task.backend_handoff.frontend_handoff:
                    sections.append(f"\n### Frontend Impact\n{task.backend_handoff.frontend_handoff.get('required', 'No frontend impact')}")
    
    elif stage in {"frontend_review"}:
        # Include backend result and handoff
        if "backend" in task.agent_results:
            result = task.agent_results["backend"]
            sections.append(f"\n## Backend Result\nStatus: {result.status}\nSummary: {result.summary}")
        
        if task.backend_handoff:
            sections.append("\n## Backend Handoff\n")
            if task.backend_handoff.api_contract:
                api = task.backend_handoff.api_contract
                sections.append(f"API Contract: {api.get('method', 'GET')} {api.get('path', '/api')}")
        
        # Include frontend result
        if "frontend" in task.agent_results:
            result = task.agent_results["frontend"]
            sections.append(f"\n## Frontend Result\nStatus: {result.status}\nSummary: {result.summary}")
    
    elif stage in {"qa_review"}:
        # Include original requirements and requirement-level decisions only
        sections.append("\n## QA Review Instructions\n")
        sections.append("You are reviewing the implementation from a black-box perspective.")
        sections.append("Do NOT inspect implementation code or implementation-specific logic.")
        sections.append("Focus on whether the implementation satisfies the acceptance criteria.")
        
        # Include QA report if available
        if task.qa_report:
            sections.append("\n## QA Report\n")
            sections.append(f"Recommendation: {task.qa_report.overall_recommendation}")
            if task.qa_report.test_cases:
                sections.append(f"\nTest Cases: {len(task.qa_report.test_cases)}")
                sections.append("### Test Results\n")
                for tc in task.qa_report.test_cases[:5]:  # Show first 5
                    sections.append(f"- {tc.id}: {tc.result}")
        
        # Include frontend/backend results (sanitized for QA)
        if "frontend" in task.agent_results:
            result = task.agent_results["frontend"]
            sanitized_summary = result.summary.replace("I implemented", "The implementation").replace("I wrote", "The code was written")
            sections.append(f"\n## Frontend Implementation Summary\n{sanitized_summary}")
        
        if "backend" in task.agent_results:
            result = task.agent_results["backend"]
            sanitized_summary = result.summary.replace("I implemented", "The implementation").replace("I wrote", "The code was written")
            sections.append(f"\n## Backend Implementation Summary\n{sanitized_summary}")
    
    elif stage in {"analyst_final_review"}:
        # Include all stage results
        for stage_name, result in task.agent_results.items():
            sections.append(f"\n## {stage_name} Result\nStatus: {result.status}\nSummary: {result.summary}")
        
        # Include QA report
        if task.qa_report:
            sections.append("\n## QA Report\n")
            sections.append(f"Recommendation: {task.qa_report.overall_recommendation}")
        
        # Include PO decision
        if task.po_decision:
            sections.append("\n## PO Decision\n")
            sections.append(f"Decision: {task.po_decision.decision}")
            sections.append(f"Rationale: {task.po_decision.rationale}")
    
    # Review task
    if stage == "backend_review":
        sections.append("\n## Your Task\nReview the backend implementation against the approved requirements.")
        sections.append("1. Does it satisfy the acceptance criteria?")
        sections.append("2. Is the API contract clear and complete?")
        sections.append("3. Are there any issues or risks?")
        sections.append("4. Should Frontend review proceed?")
        sections.append("\nOutput: approve, request_revision, or escalate_to_human")
    
    elif stage == "frontend_review":
        sections.append("\n## Your Task\nReview the frontend implementation against the approved requirements and backend handoff.")
        sections.append("1. Does it satisfy the acceptance criteria?")
        sections.append("2. Is the API integration correct?")
        sections.append("3. Are there any issues or risks?")
        sections.append("4. Should QA testing proceed?")
        sections.append("\nOutput: approve, request_revision, or escalate_to_human")
    
    elif stage == "qa_review":
        sections.append("\n## Your Task\nReview the QA test results against the acceptance criteria.")
        sections.append("1. Are all acceptance criteria covered by tests?")
        sections.append("2. Are the test results accurate and reproducible?")
        sections.append("3. Are there coverage gaps or residual risks?")
        sections.append("4. Should Analyst Final Review proceed?")
        sections.append("\nOutput: approve, request_revision, or escalate_to_human")
    
    elif stage == "analyst_final_review":
        sections.append("\n## Your Task\nPerform final assessment before PO approval.")
        sections.append("Review all evidence and determine if the task is ready for release.")
        sections.append("If ready, recommend 'po_pending_approval'.")
        sections.append("If issues remain, request revision to appropriate stage.")
    
    # Final output format
    sections.append(
        "\n## Final Answer Format\n"
        "End your reply with exactly one fenced ```json block containing:\n"
        "{\"status\": \"completed | needs_human | needs_revision\", "
        "\"summary\": \"what you reviewed and decided\", "
        "\"recommendation\": \"approve | request_revision | escalate_to_human\", "
        "\"revision_target\": \"stage to request revision from, only for needs_revision\", "
        "\"revision_reason\": \"only for needs_revision\", "
        "\"question_for_human\": \"only for needs_human\"}"
    )
    
    return "\n\n".join(sections)