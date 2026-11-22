"""A human writes that something is wrong and the task goes back to the analyst (M3-A in the task dialog)."""

import json

import pytest
from fastapi.testclient import TestClient

from backend.app import main as main_module
from backend.app.models import (
    AgentConfig, AgentResult, GitIntegration, HumanIntervention, ProjectWorkflowConfig, RunStatus, SDLCProjectConfig,
    SDLCStatus, SDLCTask, TaskRepo, TaskState,
)
from backend.app.sdlc_runner import stage_feedback
from backend.app.services import SDLCProjectManager, SDLCTaskManager

from gitflow_helpers import run

client = TestClient(main_module.app)


@pytest.fixture
def world(tmp_path, monkeypatch):
    tasks = SDLCTaskManager(data_dir=tmp_path / "data" / "tasks")
    projects = SDLCProjectManager(tmp_path / "data" / "projects")
    config = SDLCProjectConfig(
        id="p", name="Shop",
        workflow=ProjectWorkflowConfig(stages=["analysis", "backend", "qa"], require_analysis_approval=True,
                                       auto_analysis_approval=True),
        agents={"n8n": AgentConfig(enabled=False)})
    projects.save_project(config)
    monkeypatch.setattr(main_module, "sdlc_task_manager", tasks)
    started: list[str] = []

    async def fake_execute_stage(task_id, stage, project=None):
        started.append(stage)
        task = await tasks.load_task(task_id)
        task.current_stage = stage
        task.sdlc_status = SDLCStatus.analyzing
        await tasks.save_task(task)

    monkeypatch.setattr(tasks, "execute_stage", fake_execute_stage)
    return tasks, config, started


def make_task(tasks, status=SDLCStatus.pending_approval) -> SDLCTask:
    task_id = tasks.next_task_id("SDLC")
    task = SDLCTask(base_task=TaskState(id=task_id, task_id=task_id, project_path=".", branch=task_id,
                                        status=RunStatus.queued, step="s"),
                    title="T", project_config_id="p", current_stage="qa", sdlc_status=status)
    run(tasks.save_task(task))
    return task


def test_opinion_is_recorded_and_the_analyst_runs_again(world):
    tasks, _, started = world
    task = make_task(tasks)

    sent = run(tasks.send_back_to_analysis(task.base_task.task_id, "  The cart total ignores the tax.  ", "sara"))

    assert started == ["analysis"]
    saved = run(tasks.load_task(task.base_task.task_id))
    assert saved.revisions[-1].requesting_agent == "human" and saved.revisions[-1].target_agent == "analysis"
    assert saved.revisions[-1].reason == "The cart total ignores the tax."
    assert saved.timeline[-1].kind == "human_response" and saved.timeline[-1].actor == "sara"
    assert sent.base_task.task_id == task.base_task.task_id
    prompt = "\n".join(stage_feedback(saved, "analysis"))
    assert "A human reviewer found a problem" in prompt and "The cart total ignores the tax." in prompt
    assert stage_feedback(saved, "backend") == []


def test_opinion_replaces_a_pending_question_in_the_inbox(world):
    tasks, _, _ = world
    task = make_task(tasks, SDLCStatus.human_review)
    run(tasks.create_human_intervention(task.base_task.task_id, "analysis", "Approve", "Approve the analysis",
                                        {"kind": "analysis_approval"}, ["approve", "stop"]))
    assert len(tasks.list_pending_interventions()) == 1

    run(tasks.send_back_to_analysis(task.base_task.task_id, "Wrong scope"))

    assert tasks.list_pending_interventions() == []
    saved = run(tasks.load_task(task.base_task.task_id))
    assert [item.status for item in saved.human_interventions] == ["superseded"]
    resolved = json.loads(next((tasks.inbox_dir / "resolved").glob("*.json")).read_text(encoding="utf-8"))
    assert resolved["status"] == "superseded" and resolved["response"] == "Wrong scope"


def test_empty_or_oversized_opinion_is_refused_without_touching_the_task(world):
    tasks, _, started = world
    task = make_task(tasks)
    for text in ("   ", "x" * (SDLCTaskManager.MAX_FEEDBACK_CHARS + 1)):
        with pytest.raises(ValueError):
            run(tasks.send_back_to_analysis(task.base_task.task_id, text))
    assert started == []
    assert run(tasks.load_task(task.base_task.task_id)).revisions == []


def test_refused_while_running_after_merge_or_for_an_unknown_task(world):
    tasks, _, started = world
    task = make_task(tasks)
    task.repos["r"] = TaskRepo(path="r", branch=task.base_task.task_id, base_branch="sandbox",
                               integration=GitIntegration(status="merged", merged_into_develop=True))
    run(tasks.save_task(task))
    with pytest.raises(ValueError, match="already merged"):
        run(tasks.send_back_to_analysis(task.base_task.task_id, "problem"))

    other = make_task(tasks)
    tasks.is_running = lambda task_id: True
    with pytest.raises(ValueError, match="stage running"):
        run(tasks.send_back_to_analysis(other.base_task.task_id, "problem"))
    tasks.is_running = lambda task_id: False
    with pytest.raises(ValueError, match="not found"):
        run(tasks.send_back_to_analysis("SDLC-9999", "problem"))
    assert started == []


def test_automatic_approval_never_skips_a_human_who_objected(world):
    tasks, config, _ = world
    task = make_task(tasks, SDLCStatus.analyzing)
    task.current_stage = "analysis"
    task.agent_results["analysis"] = AgentResult(agent="analysis", status="completed", summary="clean analysis")
    run(tasks.save_task(task))

    run(tasks._advance_or_complete(task, config))  # no objection: approved by Taskloom
    assert run(tasks.load_task(task.base_task.task_id)).sdlc_status != SDLCStatus.human_review

    objected = make_task(tasks, SDLCStatus.pending_approval)
    run(tasks.send_back_to_analysis(objected.base_task.task_id, "Wrong"))
    objected = run(tasks.load_task(objected.base_task.task_id))
    objected.current_stage = "analysis"
    objected.agent_results["analysis"] = AgentResult(agent="analysis", status="completed", summary="clean analysis")
    run(tasks.save_task(objected))
    run(tasks._advance_or_complete(objected, config))
    saved = run(tasks.load_task(objected.base_task.task_id))
    assert saved.sdlc_status == SDLCStatus.human_review
    assert any("objected" in item.description for item in saved.human_interventions)


def test_endpoint_returns_the_task_and_maps_errors(world):
    tasks, _, started = world
    task = make_task(tasks)
    url = f"/api/sdlc/tasks/{task.base_task.task_id}/send-back"

    ok = client.post(url, json={"feedback": "Needs a rethink"}, headers={"X-Taskloom-User": "ali"})
    assert ok.status_code == 200 and ok.json()["revisions"][-1]["reason"] == "Needs a rethink"
    assert started == ["analysis"]
    assert client.post(url, json={"feedback": " "}).status_code == 409
    assert client.post("/api/sdlc/tasks/SDLC-9999/send-back", json={"feedback": "x"}).status_code == 404
