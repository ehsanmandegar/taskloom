import asyncio
import json
import sys
from pathlib import Path

import pytest

from backend.app import sdlc_runner, services
from backend.app.models import (
    AgentConfig, AgentResult, ProjectWorkflowConfig, RunStatus, SDLCProjectConfig, SDLCStatus,
    SDLCTask, StageRunner, TaskState,
)


def make_task(task_id: str = "sdlc-run", stage: str = "backend") -> SDLCTask:
    base = TaskState(id=task_id, task_id=task_id, project_path=".", branch=f"tasks/{task_id}", status=RunStatus.queued, step="sdlc")
    return SDLCTask(base_task=base, title="Add login", description="JWT auth", current_stage=stage, current_agent=stage, project_config_id="p")


def report(**fields) -> str:
    return "Done.\n```json\n" + json.dumps(fields) + "\n```"


@pytest.fixture
def fake_agent(monkeypatch):
    """Replace the CLI with a callable that may edit the working folder and returns a reply."""
    calls = {}

    def install(reply: str, edit=None, exit_code: int = 0):
        async def fake_run(agent_type, args, repo, state, timeout):
            calls.update(agent_type=agent_type, prompt=args[-1], repo=repo, timeout=timeout)
            if edit:
                edit(Path(repo))
            return exit_code, reply

        monkeypatch.setattr(sdlc_runner, "agent_executable", lambda agent_type: "agent.exe")
        monkeypatch.setattr(sdlc_runner, "run_agent_command", fake_run)
        monkeypatch.setattr(sdlc_runner, "agent_response", lambda agent_type, output: ("session-1", output))
        return calls

    return install


def project(tmp_path: Path, **agent_fields) -> tuple[SDLCProjectConfig, AgentConfig]:
    config = AgentConfig(project_path=str(tmp_path), **agent_fields)
    return SDLCProjectConfig(id="p", name="Shop", agents={"backend": config}), config


def test_auto_runner_uses_cli_only_when_stage_has_a_folder_and_cli(monkeypatch):
    monkeypatch.setattr(sdlc_runner.shutil, "which", lambda name: "claude.exe" if name == "claude" else None)
    assert sdlc_runner.resolve_runner(AgentConfig(project_path="E:/shop")) == StageRunner.claude
    assert sdlc_runner.resolve_runner(AgentConfig()) == StageRunner.ollama
    assert sdlc_runner.resolve_runner(AgentConfig(project_path="E:/shop", runner="ollama")) == StageRunner.ollama

    monkeypatch.setattr(sdlc_runner.shutil, "which", lambda name: None)
    assert sdlc_runner.resolve_runner(AgentConfig(project_path="E:/shop")) == StageRunner.ollama


def test_cli_stage_records_real_file_changes_and_builds_full_prompt(tmp_path, fake_agent):
    (tmp_path / "old.py").write_text("x = 1", encoding="utf-8")
    calls = fake_agent(
        report(status="completed", summary="Added login API", issues=["no rate limit"], recommendations={"security": ["add MFA"]}),
        edit=lambda repo: (repo / "auth.py").write_text("def login(): ...", encoding="utf-8"),
    )
    proj, config = project(
        tmp_path, system_prompt="Use FastAPI.", knowledge_path=str(tmp_path / "docs"), cli_timeout_seconds=77,
        test_instructions={"command": f'"{sys.executable}" -c "pass"'},
    )
    task = make_task()
    task.agent_results["analysis"] = AgentResult(
        agent="analysis", status="completed", summary="Needs JWT login",
        tests={"executed": True, "passed": False, "results": []},
    )

    result = asyncio.run(sdlc_runner.run_cli_stage("backend", task, proj, config, StageRunner.claude))

    assert result.status == "completed"
    assert result.summary == "Added login API"
    assert [(c.file, c.kind) for c in result.changes] == [("auth.py", "created")]
    assert result.issues == ["no rate limit"]
    assert result.recommendations == {"security": ["add MFA"]}
    assert result.tests.executed and result.tests.passed
    assert task.base_task.codex_thread_id == "session-1"
    assert calls["repo"] == tmp_path.resolve() and calls["timeout"] == 77
    for expected in ("Use FastAPI.", "Add login", "JWT auth", str(tmp_path / "docs"), "Needs JWT login",
                     "tests: FAILED", "Taskloom itself runs", "Do not commit"):
        assert expected in calls["prompt"]


def test_code_stage_without_report_or_changes_is_flagged(tmp_path, fake_agent):
    fake_agent("I looked around.")
    proj, config = project(tmp_path)

    result = asyncio.run(sdlc_runner.run_cli_stage("backend", make_task(), proj, config, StageRunner.claude))

    assert result.status == "completed"
    assert result.summary == "I looked around."
    assert any("JSON report" in issue for issue in result.issues)
    assert any("without changing any file" in issue for issue in result.issues)


def test_failing_stage_tests_fail_the_stage(tmp_path, fake_agent):
    fake_agent(report(status="completed", summary="ok"), edit=lambda repo: (repo / "a.py").write_text("1", encoding="utf-8"))
    proj, config = project(tmp_path, test_instructions={"command": f'"{sys.executable}" -c "import sys; sys.exit(3)"'})

    result = asyncio.run(sdlc_runner.run_cli_stage("backend", make_task(), proj, config, StageRunner.claude))

    assert result.status == "failed"
    assert result.tests.executed and not result.tests.passed
    assert result.tests.results[0]["exit_code"] == 3


def test_agent_can_ask_a_human_or_request_a_revision(tmp_path, fake_agent):
    proj, config = project(tmp_path)

    fake_agent(report(status="needs_human", summary="Unclear", question_for_human="Which payment gateway?"))
    asked = asyncio.run(sdlc_runner.run_cli_stage("backend", make_task(), proj, config, StageRunner.claude))
    assert asked.status == "needs_human"
    assert asked.human_intervention.description == "Which payment gateway?"

    fake_agent(report(status="needs_revision", summary="Spec missing", revision_target="analysis", revision_reason="No data model"))
    revised = asyncio.run(sdlc_runner.run_cli_stage("backend", make_task(), proj, config, StageRunner.claude))
    assert revised.revision_request.target_agent == "analysis"
    assert revised.revision_request.reason == "No data model"


def test_cli_exit_code_fails_the_stage(tmp_path, fake_agent):
    fake_agent('{"type":"error","message":"not logged in"}', exit_code=1)
    proj, config = project(tmp_path)

    result = asyncio.run(sdlc_runner.run_cli_stage("backend", make_task(), proj, config, StageRunner.claude))

    assert result.status == "failed"
    assert "exited with code 1" in result.summary


def test_missing_project_folder_is_an_error(tmp_path, fake_agent):
    fake_agent("unused")
    proj, config = project(tmp_path / "missing")

    with pytest.raises(RuntimeError, match="does not exist"):
        asyncio.run(sdlc_runner.run_cli_stage("backend", make_task(), proj, config, StageRunner.claude))


def test_manager_routes_needs_human_to_the_inbox(tmp_path, monkeypatch, fake_agent):
    monkeypatch.chdir(tmp_path)
    workdir = tmp_path / "shop"
    workdir.mkdir()
    fake_agent(report(status="needs_human", summary="?", question_for_human="Which currency?"))
    monkeypatch.setattr(sdlc_runner.shutil, "which", lambda name: "claude.exe" if name == "claude" else None)
    manager = services.SDLCTaskManager(data_dir=tmp_path / "tasks")
    proj = SDLCProjectConfig(id="p", name="Shop", agents={"backend": AgentConfig(project_path=str(workdir))})
    asyncio.run(manager.save_task(make_task()))

    asyncio.run(manager._run_agent_async("sdlc-run", "backend", proj))

    task = asyncio.run(manager.load_task("sdlc-run"))
    assert task.sdlc_status == SDLCStatus.human_review
    assert task.human_interventions[0].description == "Which currency?"
    assert len(list((tmp_path / "data" / "human-inbox" / "pending").glob("*.json"))) == 1


def test_manager_marks_failed_stage_with_reason(tmp_path, monkeypatch, fake_agent):
    workdir = tmp_path / "shop"
    workdir.mkdir()
    fake_agent(report(status="blocked", summary="Cannot reach DB", issues=["DB down"]))
    manager = services.SDLCTaskManager(data_dir=tmp_path / "tasks")
    proj = SDLCProjectConfig(
        id="p", name="Shop", workflow=ProjectWorkflowConfig(stages=["backend"]),
        agents={"backend": AgentConfig(project_path=str(workdir), runner="claude")},
    )
    asyncio.run(manager.save_task(make_task()))

    asyncio.run(manager._run_agent_async("sdlc-run", "backend", proj))

    task = asyncio.run(manager.load_task("sdlc-run"))
    assert task.sdlc_status == SDLCStatus.failed
    assert task.transition_reason == "backend blocked: DB down"


def test_ollama_file_claims_are_proposals_not_changes(monkeypatch):
    runner = services.OllamaAgentRunner()
    monkeypatch.setattr(runner, "_chat", lambda system, user, timeout=240: json.dumps(
        {"summary": "plan", "changes": [{"file": "api.py", "description": "add route"}], "issues": []}
    ))

    result = runner.run_agent("backend", make_task(), SDLCProjectConfig(id="p", name="p"), {})

    assert result.changes == []
    assert result.recommendations["proposed_changes"] == ["api.py: add route"]
