"""Human gates, human answers, and the revision loop of SDLCTaskManager."""

import asyncio

import pytest

from backend.app import services
from backend.app.models import (
    AgentConfig, AgentResult, ProjectWorkflowConfig, RevisionRequest, RunStatus, SDLCProjectConfig,
    SDLCStatus, SDLCTask, TaskState,
)
from backend.app.sdlc_runner import build_stage_prompt, stage_feedback


def make_task(stage: str = "analysis") -> SDLCTask:
    base = TaskState(id="t1", task_id="t1", project_path=".", branch="tasks/t1", status=RunStatus.queued, step="sdlc")
    return SDLCTask(base_task=base, title="Shop", current_stage=stage, current_agent=stage, project_config_id="p")


@pytest.fixture
def setup(tmp_path, monkeypatch):
    """A manager whose stage launches are recorded instead of running agents."""
    manager = services.SDLCTaskManager(data_dir=tmp_path / "tasks")
    project = SDLCProjectConfig(
        id="p", name="Shop",
        workflow=ProjectWorkflowConfig(
            stages=["analysis", "backend", "qa"], require_analysis_approval=True, max_revision_attempts=2,
        ),
        agents={"n8n": AgentConfig(enabled=False)},
    )
    services.SDLCProjectManager(tmp_path / "projects").save_project(project)
    launched = []

    async def fake_execute(task_id, stage, project=None):
        task = await manager.load_task(task_id)
        task.current_stage = stage
        task.sdlc_status = manager.STAGE_STATUS[stage]
        await manager.save_task(task)
        launched.append(stage)

    monkeypatch.setattr(manager, "execute_stage", fake_execute)
    return manager, project, launched


def run(coro):
    return asyncio.run(coro)


def finish_analysis(manager, project):
    task = make_task("analysis")
    task.agent_results["analysis"] = AgentResult(agent="analysis", status="completed", summary="Needs a cart API")
    run(manager.save_task(task))
    run(manager._advance_or_complete(task, project))
    return run(manager.load_task("t1"))


def test_analysis_gate_asks_a_human_and_approval_starts_development(setup):
    manager, project, launched = setup

    task = finish_analysis(manager, project)

    assert task.sdlc_status == SDLCStatus.human_review
    [question] = manager.list_pending_interventions()
    assert question.context["kind"] == "analysis_approval"
    assert "Needs a cart API" in question.description
    assert launched == []

    assert run(manager.submit_human_response(question.id, "approve"))

    assert launched == ["backend"]
    assert manager.list_pending_interventions() == []
    task = run(manager.load_task("t1"))
    assert task.human_interventions[0].response == "approve"


def test_analysis_feedback_reruns_analysis_with_the_feedback_in_its_prompt(setup):
    manager, project, launched = setup
    finish_analysis(manager, project)
    [question] = manager.list_pending_interventions()

    run(manager.submit_human_response(question.id, "Also cover discount codes"))

    assert launched == ["analysis"]
    task = run(manager.load_task("t1"))
    feedback = "\n".join(stage_feedback(task, "analysis"))
    assert "Also cover discount codes" in feedback
    assert "Also cover discount codes" in build_stage_prompt("analysis", task, project, AgentConfig(), "/work")


def test_stop_answer_fails_the_task(setup):
    manager, project, launched = setup
    finish_analysis(manager, project)
    [question] = manager.list_pending_interventions()

    run(manager.submit_human_response(question.id, "stop"))

    task = run(manager.load_task("t1"))
    assert task.sdlc_status == SDLCStatus.failed
    assert launched == []


def test_answer_to_an_agent_question_reruns_that_stage(setup):
    manager, project, launched = setup
    task = make_task("backend")
    run(manager.save_task(task))
    intervention_id = run(manager._ask_human(task, "backend", "agent_question", "backend needs a decision", "Which DB?", ["stop"]))

    run(manager.submit_human_response(intervention_id, "PostgreSQL"))

    assert launched == ["backend"]
    task = run(manager.load_task("t1"))
    assert "Answer: PostgreSQL" in "\n".join(stage_feedback(task, "backend"))


def test_unknown_or_answered_interventions_are_rejected(setup):
    manager, _, _ = setup
    assert run(manager.submit_human_response("INT-NOPE", "approve")) is False


def test_revision_goes_back_to_target_stage_until_the_limit(setup):
    manager, project, launched = setup
    task = make_task("qa")
    run(manager.save_task(task))
    request = lambda: RevisionRequest(requesting_agent="qa", target_agent="backend", reason="Cart total wrong", description="")

    run(manager._request_revision(task, "qa", request(), project))
    task = run(manager.load_task("t1"))
    assert launched == ["backend"]
    assert task.revision_count == 1
    assert "Cart total wrong" in "\n".join(stage_feedback(task, "backend"))

    run(manager._request_revision(task, "qa", request(), project))
    task = run(manager.load_task("t1"))
    assert launched == ["backend", "backend"] and task.revision_count == 2

    run(manager._request_revision(task, "qa", request(), project))
    task = run(manager.load_task("t1"))
    assert launched == ["backend", "backend"]
    assert task.sdlc_status == SDLCStatus.human_review
    [question] = manager.list_pending_interventions()
    assert question.context["kind"] == "revision_limit"

    run(manager.submit_human_response(question.id, "Use Decimal for money"))
    assert launched[-1] == "qa"


def test_revision_of_a_disabled_stage_asks_a_human(setup):
    manager, project, launched = setup
    task = make_task("qa")
    run(manager.save_task(task))

    run(manager._request_revision(task, "qa", RevisionRequest(requesting_agent="qa", target_agent="n8n", reason="x", description=""), project))

    assert launched == []
    assert manager.list_pending_interventions()[0].context["kind"] == "revision_limit"


@pytest.mark.parametrize("final_approval, expected", [(True, SDLCStatus.pending_approval), (False, SDLCStatus.done)])
def test_final_approval_setting_is_respected(setup, final_approval, expected):
    manager, project, _ = setup
    project.workflow.require_final_human_approval = final_approval
    task = make_task("qa")
    run(manager.save_task(task))

    run(manager._advance_or_complete(task, project))

    assert run(manager.load_task("t1")).sdlc_status == expected


def test_running_agent_output_is_visible_on_loaded_task(setup):
    manager, _, _ = setup
    run(manager.save_task(make_task("backend")))
    live = make_task("backend").base_task
    live.live_output = "Editing cart.py"
    manager.live_states["t1"] = live

    task = manager.with_live_output(run(manager.load_task("t1")))

    assert task.base_task.live_output == "Editing cart.py"
