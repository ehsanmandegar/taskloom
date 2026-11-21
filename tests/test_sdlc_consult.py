"""Only the analyst talks to humans: other stages ask the analyst, the analyst asks a human when it cannot answer."""
import asyncio
from pathlib import Path

from backend.app import sdlc_runner
from backend.app.models import (
    AgentConfig, AgentResult, HumanIntervention, RunStatus, SDLCProjectConfig, SDLCStatus, SDLCTask, StageRunner, TaskState,
)
from backend.app.services import SDLCTaskManager


def run(coro):
    return asyncio.run(coro)


def make_task(stage: str = "backend") -> SDLCTask:
    base = TaskState(id="t1", task_id="t1", project_path=".", base_branch="main", branch="sdlc/t1", status=RunStatus.queued, step="sdlc")
    return SDLCTask(base_task=base, title="Add cart", description="Cart API", project_config_id="p", current_stage=stage)


def needs_human(question: str) -> AgentResult:
    return AgentResult(agent="x", status="needs_human", summary=question,
                       human_intervention=HumanIntervention(id="", task_id="t1", requesting_agent="x", reason="ask", description=question))


def completed(summary: str) -> AgentResult:
    return AgentResult(agent="x", status="completed", summary=summary)


def setup(tmp_path, monkeypatch, analysis_enabled=True):
    manager = SDLCTaskManager(data_dir=tmp_path / "tasks")
    project = SDLCProjectConfig(id="p", name="P", agents={
        "analysis": AgentConfig(enabled=analysis_enabled, project_path=str(tmp_path)),
        "backend": AgentConfig(project_path=str(tmp_path)),
    })
    project.workflow.stages = ["analysis", "backend"]
    started = []

    async def fake_execute(task_id, stage, project=None):
        started.append(stage)

    monkeypatch.setattr(manager, "execute_stage", fake_execute)
    monkeypatch.setattr(manager, "load_project", lambda _id: project)
    monkeypatch.setattr(sdlc_runner, "resolve_runner", lambda *a, **k: StageRunner.claude)
    return manager, project, started


def test_a_stuck_stage_asks_the_analyst_not_the_human(tmp_path, monkeypatch):
    manager, project, started = setup(tmp_path, monkeypatch)
    task = make_task("backend")
    run(manager.save_task(task))

    run(manager._route_result(task, "backend", needs_human("1. Which currency?"), project))

    saved = run(manager.load_task("t1"))
    assert started == ["analysis"]
    assert saved.stage_questions[0].asking_stage == "backend" and saved.consult_question_id == saved.stage_questions[0].id
    assert saved.human_interventions == [] and manager.list_pending_interventions() == []


def test_analyst_answer_goes_back_to_the_asking_stage(tmp_path, monkeypatch):
    manager, project, started = setup(tmp_path, monkeypatch)
    task = make_task("backend")
    run(manager.save_task(task))
    run(manager._route_result(task, "backend", needs_human("1. Which currency?"), project))
    task = run(manager.load_task("t1"))
    task.agent_results["analysis"] = completed("original analysis")

    run(manager._route_result(task, "analysis", completed("1. USD"), project))

    saved = run(manager.load_task("t1"))
    assert started == ["analysis", "backend"]
    asked = saved.stage_questions[0]
    assert (asked.status, asked.answer, asked.answered_by) == ("answered", "1. USD", "analysis")
    assert saved.consult_question_id == "" and saved.agent_results["analysis"].summary == "original analysis"
    prompt = sdlc_runner.build_stage_prompt("backend", saved, project, project.agents["backend"], Path(tmp_path))
    assert "Which currency?" in prompt and "1. USD" in prompt


def test_what_the_analyst_cannot_answer_goes_to_a_human_until_nothing_is_open(tmp_path, monkeypatch):
    manager, project, started = setup(tmp_path, monkeypatch)
    task = make_task("backend")
    run(manager.save_task(task))
    run(manager._route_result(task, "backend", needs_human("1. Which currency? 2. Tax rule?"), project))
    task = run(manager.load_task("t1"))

    run(manager._route_result(task, "analysis", needs_human("2. Tax rule?"), project))  # analyst: only #1 is clear

    pending = manager.list_pending_interventions()
    assert len(pending) == 1 and pending[0].requesting_agent == "analysis"
    assert "Which currency" in pending[0].description and "Tax rule" in pending[0].description
    assert run(manager.load_task("t1")).sdlc_status == SDLCStatus.human_review

    assert run(manager.submit_human_response(pending[0].id, "Tax is 9%"))
    assert started == ["analysis", "analysis"]  # the analyst is re-run with the human's answer
    task = run(manager.load_task("t1"))
    analyst_prompt = sdlc_runner.build_stage_prompt("analysis", task, project, project.agents["analysis"], Path(tmp_path))
    assert "Tax is 9%" in analyst_prompt and "Question from the backend stage" in analyst_prompt

    run(manager._route_result(task, "analysis", needs_human("Still unclear: tax on shipping?"), project))  # still open
    assert len(manager.list_pending_interventions()) == 1 and started == ["analysis", "analysis"]
    pending = manager.list_pending_interventions()[0]
    assert run(manager.submit_human_response(pending.id, "No tax on shipping"))
    task = run(manager.load_task("t1"))

    run(manager._route_result(task, "analysis", completed("1. USD 2. 9%, shipping untaxed"), project))

    saved = run(manager.load_task("t1"))
    assert started[-1] == "backend" and saved.stage_questions[0].answered_by == "human"
    assert manager.list_pending_interventions() == []


def test_the_analyst_itself_asks_the_human_directly(tmp_path, monkeypatch):
    manager, project, started = setup(tmp_path, monkeypatch)
    task = make_task("analysis")
    run(manager.save_task(task))

    run(manager._route_result(task, "analysis", needs_human("Which database?"), project))

    assert [item.requesting_agent for item in manager.list_pending_interventions()] == ["analysis"]
    assert started == [] and run(manager.load_task("t1")).stage_questions == []


def test_without_an_analysis_stage_the_question_goes_to_a_human(tmp_path, monkeypatch):
    manager, project, started = setup(tmp_path, monkeypatch, analysis_enabled=False)
    task = make_task("backend")
    run(manager.save_task(task))

    run(manager._route_result(task, "backend", needs_human("Which currency?"), project))

    assert [item.requesting_agent for item in manager.list_pending_interventions()] == ["backend"]
    assert started == []


def test_a_stage_that_keeps_asking_is_eventually_sent_to_a_human(tmp_path, monkeypatch):
    manager, project, started = setup(tmp_path, monkeypatch)
    task = make_task("backend")
    for n in range(manager.MAX_ANALYST_QUESTIONS):
        run(manager._consult_analyst(task, "backend", f"question {n}", project))
    run(manager.save_task(task))

    run(manager._route_result(task, "backend", needs_human("one more"), project))

    assert [item.requesting_agent for item in manager.list_pending_interventions()] == ["backend"]
