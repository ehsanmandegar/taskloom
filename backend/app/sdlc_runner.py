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
from .sdlc_git import prepare_task_branch
from .services import (
    WORKSPACE_IGNORED_DIRECTORIES, agent_error_detail, agent_executable, agent_name,
    agent_response, command, initial_agent_args, run_agent_command, test_plan,
)

STAGE_ROLES = {
    "analysis": "software analyst",
    "backend": "backend developer",
    "n8n": "n8n workflow engineer",
    "frontend": "frontend developer",
    "qa": "QA engineer",
}
REPORT_ONLY_STAGES = {"analysis", "qa"}
AGENT_STATUSES = {"completed", "needs_human", "needs_revision", "blocked"}
SNAPSHOT_MAX_FILES = 50_000
TEST_OUTPUT_TAIL = 4_000

Snapshot = dict[str, tuple[int, int]]


def resolve_runner(config: AgentConfig) -> StageRunner:
    """Pick who runs a stage; `auto` prefers a CLI agent whenever the stage has a working folder."""
    if config.runner != StageRunner.auto:
        return config.runner
    if config.project_path:
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
                f"From {revision.requesting_agent}: {revision.reason}"
                + (f"\n{revision.description}" if revision.description and revision.description != revision.reason else "")
                for revision in revisions
            )
        )
    answers = [
        item for item in task.human_interventions
        if item.status == "responded" and (item.context.get("stage") or item.requesting_agent) == stage
    ][-5:]
    if answers:
        sections.append(
            "## Answers from a human — follow them\n" + "\n\n".join(
                f"Question: {item.description}\nAnswer: {item.response}" for item in answers
            )
        )
    return sections


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
    sections.append(
        "## Rules\n"
        f"- Your working folder is `{workdir}`. Only create or modify files inside it.\n"
        "- Do not commit, push, or switch Git branches; a human reviews the result.\n"
        f"- {work}\n"
        f"- {testing}\n"
        "- If you cannot proceed without a decision from a human, stop and ask (status `needs_human`).\n"
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


async def run_cli_stage(stage: str, task: SDLCTask, project: SDLCProjectConfig, config: AgentConfig, runner: StageRunner) -> AgentResult:
    """Run one SDLC stage with Claude Code or Codex inside the stage's project folder."""
    agent_type = AgentType.claude if runner == StageRunner.claude else AgentType.codex
    display_name = agent_name(agent_type)
    if not config.project_path:
        raise RuntimeError(f"Stage '{stage}' needs a project_path to run {display_name}")
    workdir = Path(config.project_path).expanduser().resolve()
    if not workdir.is_dir():
        raise RuntimeError(f"Project folder for stage '{stage}' does not exist: {workdir}")

    executable = agent_executable(agent_type)
    # In a Git repository every task works on its own branch (sdlc/<task-id>).
    await prepare_task_branch(task, workdir, str(config.github_config.get("branch") or "main"))
    prompt = build_stage_prompt(stage, task, project, config, workdir)
    state = task.base_task
    state.step = f"{display_name} is running the {stage} stage"

    before = snapshot_folder(workdir)
    code, output = await run_agent_command(agent_type, initial_agent_args(agent_type, executable, prompt), workdir, state, config.cli_timeout_seconds)
    changes = folder_changes(before, snapshot_folder(workdir))
    session_id, response = agent_response(agent_type, output)
    state.codex_thread_id = session_id or state.codex_thread_id
    state.live_response = ""

    if code:
        detail = agent_error_detail(output) or output.strip()[-2000:]
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
