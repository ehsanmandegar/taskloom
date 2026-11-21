"""Autonomy policy: risk, automatic approvals/retries/releases, audit trail and metrics."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from backend.app import sdlc_policy as policy
from backend.app import services
from backend.app.models import (
    AgentConfig, AgentResult, Change, ProjectWorkflowConfig, RunStatus, SDLCProjectConfig, SDLCStatus, SDLCTask,
    StageQuestion, TaskState, TestResults,
)


def make_task(stage="qa", task_id="t1") -> SDLCTask:
    base = TaskState(id=task_id, task_id=task_id, project_path=".", branch=task_id, status=RunStatus.queued, step="sdlc")
    return SDLCTask(base_task=base, title="Shop", current_stage=stage, current_agent=stage, project_config_id="p")


def result(stage="backend", files=("app/cart.py",), tests=True, passed=True, issues=(), status="completed", kind="modified"):
    return AgentResult(
        agent=stage, status=status, summary=f"{stage} done", issues=list(issues),
        changes=[Change(file=name, description="x", kind=kind) for name in files],
        tests=TestResults(executed=tests, passed=passed if tests else False, results=[]))


def project(**workflow) -> SDLCProjectConfig:
    base = dict(stages=["analysis", "backend", "qa"], require_final_human_approval=True)
    return SDLCProjectConfig(id="p", name="Shop", workflow=ProjectWorkflowConfig(**{**base, **workflow}),
                             agents={"n8n": AgentConfig(enabled=False)})


def run(coro):
    return asyncio.run(coro)


# ------------------------------------------------------------------------------------------------- risk

def test_small_tested_change_is_low_risk():
    task = make_task()
    task.agent_results["backend"] = result(files=("app/cart.py", "tests/test_cart.py"))

    risk = policy.assess_risk(task)

    assert risk.level == "low" and risk.score == 0 and not risk.blocking and risk.reasons == []


def test_sensitive_paths_raise_the_risk_even_with_green_tests():
    task = make_task()
    task.agent_results["backend"] = result(files=("app/auth/login.py", "migrations/0002_add_cart.py"))

    risk = policy.assess_risk(task)

    assert risk.level == "high" and not risk.blocking
    assert any("authentication" in reason for reason in risk.reasons) and any("migrations" in reason for reason in risk.reasons)


def test_failing_tests_are_blocking_and_missing_tests_are_a_risk():
    failing = make_task()
    failing.agent_results["qa"] = result("qa", tests=True, passed=False)
    untested = make_task()
    untested.agent_results["backend"] = result(tests=False)

    assert policy.assess_risk(failing).blocking and policy.assess_risk(failing).level == "high"
    risk = policy.assess_risk(untested)
    assert risk.level == "low" and risk.score == 2 and "no automated tests ran" in risk.reasons


def test_size_revisions_retries_and_issues_add_up():
    task = make_task()
    task.agent_results["backend"] = result(files=tuple(f"src/f{i}.py" for i in range(12)), issues=("a", "b", "c"))
    task.revision_count = 2
    task.stage_attempts = {"backend": 1}

    risk = policy.assess_risk(task)

    assert risk.level == "high" and risk.score == 2 + 1 + 1 + 2  # size, revisions, retry, issues


# ----------------------------------------------------------------------------------------- decisions

def test_final_approval_policy_matrix():
    low, high = make_task(), make_task()
    low.agent_results["backend"] = result()
    high.agent_results["backend"] = result(files=("Dockerfile",))
    failing = make_task()
    failing.agent_results["backend"] = result(passed=False)

    assert policy.can_auto_approve(low, project())[0] is False                                    # humans decide by default
    assert policy.can_auto_approve(low, project(auto_final_approval=True))[0] is True
    assert policy.can_auto_approve(high, project(auto_final_approval=True))[0] is False           # medium/high needs a human
    assert policy.can_auto_approve(high, project(auto_final_approval=True, auto_approval_max_risk="medium"))[0] is True
    assert policy.can_auto_approve(failing, project(auto_final_approval=True, auto_approval_max_risk="medium"))[0] is False
    assert policy.can_auto_approve(failing, project(require_final_human_approval=False))[0] is False  # never waves failing tests through
    assert policy.can_auto_approve(low, project(require_final_human_approval=False))[0] is True


def test_pending_human_question_blocks_automatic_approval():
    task = make_task()
    task.agent_results["backend"] = result()
    from backend.app.models import HumanIntervention
    task.human_interventions.append(HumanIntervention(id="I1", task_id="t1", requesting_agent="qa", reason="r", description="d"))

    ok, why = policy.can_auto_approve(task, project(auto_final_approval=True))

    assert not ok and "pending" in why


def test_analysis_is_clean_only_when_nothing_is_open():
    task = make_task("analysis")
    assert policy.analysis_is_clean(task)[0] is False
    task.agent_results["analysis"] = AgentResult(agent="analysis", status="completed", summary="Plan: cart API")
    assert policy.analysis_is_clean(task)[0] is True
    task.stage_questions.append(StageQuestion(id="Q1", asking_stage="backend", question="which db?"))
    assert policy.analysis_is_clean(task)[0] is False
    task.stage_questions.clear()
    task.agent_results["analysis"].issues = ["unclear scope"]
    assert policy.analysis_is_clean(task)[0] is False


def test_next_release_version():
    assert policy.next_release_version([]) == "0.1.0"
    assert policy.next_release_version(["1.0.0", "1.0.9", "0.9.0"]) == "1.0.10"
    assert policy.next_release_version(["2.0.0-rc.1"]) == "0.1.0"  # only plain x.y.z versions count


# ---------------------------------------------------------------------------------- pipeline behaviour

@pytest.fixture
def pipeline(tmp_path, monkeypatch):
    manager = services.SDLCTaskManager(data_dir=tmp_path / "tasks")
    manager.AUTO_RETRY_DELAY = 0
    launched = []

    async def fake_execute(task_id, stage, project=None):
        task = await manager.load_task(task_id)
        task.current_stage = stage
        task.sdlc_status = manager.STAGE_STATUS[stage]
        policy.record_event(task, "stage_started", stage=stage)
        await manager.save_task(task)
        launched.append(stage)

    monkeypatch.setattr(manager, "execute_stage", fake_execute)
    return manager, launched


def test_clean_analysis_skips_the_human_gate_when_the_policy_allows(pipeline):
    manager, launched = pipeline
    cfg = project(require_analysis_approval=True, auto_analysis_approval=True)
    task = make_task("analysis")
    task.agent_results["analysis"] = AgentResult(agent="analysis", status="completed", summary="Plan: cart API")
    run(manager.save_task(task))

    run(manager._advance_or_complete(task, cfg))

    assert launched == ["backend"] and manager.list_pending_interventions() == []
    assert any(event.kind == "auto_approved" and event.stage == "analysis" for event in run(manager.load_task("t1")).timeline)


def test_unclean_analysis_still_goes_to_a_human_with_the_reason(pipeline):
    manager, launched = pipeline
    cfg = project(require_analysis_approval=True, auto_analysis_approval=True)
    task = make_task("analysis")
    task.agent_results["analysis"] = AgentResult(agent="analysis", status="completed", summary="Plan", issues=["unclear scope"])
    run(manager.save_task(task))

    run(manager._advance_or_complete(task, cfg))

    [question] = manager.list_pending_interventions()
    assert "Automatic approval was not possible" in question.description and launched == []
    assert any(event.kind == "escalated" for event in run(manager.load_task("t1")).timeline)


def test_failed_stage_is_retried_automatically_then_escalated(pipeline):
    manager, launched = pipeline
    cfg = project(auto_retry_failed_stages=2)
    task = make_task("backend")
    run(manager.save_task(task))
    failure = AgentResult(agent="backend", status="failed", summary="agent crashed")

    for expected in (1, 2):
        task = run(manager.load_task("t1"))
        run(manager._route_result(task, "backend", failure, cfg))
        task = run(manager.load_task("t1"))
        assert task.stage_attempts["backend"] == expected and task.sdlc_status == SDLCStatus.backend_running
    assert launched == ["backend", "backend"]

    run(manager._route_result(run(manager.load_task("t1")), "backend", failure, cfg))  # budget used up

    task = run(manager.load_task("t1"))
    assert task.sdlc_status == SDLCStatus.failed and launched == ["backend", "backend"]
    kinds = [event.kind for event in task.timeline]
    assert kinds.count("auto_retry") == 2 and kinds.count("stage_failed") == 3 and kinds[-1] == "escalated"


def test_without_a_retry_budget_a_failed_stage_fails_immediately(pipeline):
    manager, launched = pipeline
    task = make_task("backend")
    run(manager.save_task(task))

    run(manager._route_result(task, "backend", AgentResult(agent="backend", status="failed", summary="boom"), project()))

    assert run(manager.load_task("t1")).sdlc_status == SDLCStatus.failed and launched == []


def finish_pipeline(manager, cfg, files=("app/cart.py",), passed=True):
    task = make_task("qa")
    task.agent_results["backend"] = result(files=files, passed=passed)
    task.agent_results["qa"] = result("qa", files=(), passed=passed)
    run(manager.save_task(task))
    run(manager._advance_or_complete(task, cfg))
    return run(manager.load_task("t1"))


def test_low_risk_task_is_approved_by_taskloom_when_the_policy_allows(pipeline):
    manager, _ = pipeline
    approvals = []

    async def approver(task_id, reason):
        approvals.append((task_id, reason))
        await manager.update_task(task_id, lambda t: setattr(t, "sdlc_status", SDLCStatus.done))
        return True

    manager.auto_approver = approver

    task = finish_pipeline(manager, project(auto_final_approval=True))

    assert approvals and approvals[0][0] == "t1" and "risk is low" in approvals[0][1]
    assert task.sdlc_status == SDLCStatus.done and task.risk.level == "low"
    assert any(event.kind == "all_stages_completed" for event in task.timeline)


def test_risky_task_waits_for_a_human_even_with_auto_approval_on(pipeline):
    manager, _ = pipeline

    async def approver(task_id, reason):
        raise AssertionError("must not be called for a risky task")

    manager.auto_approver = approver

    task = finish_pipeline(manager, project(auto_final_approval=True), files=("app/auth/session.py",))

    assert task.sdlc_status == SDLCStatus.pending_approval and task.risk.level == "medium"
    assert any(event.kind == "escalated" and "risk is medium" in event.message for event in task.timeline)


def test_failed_automatic_approval_leaves_the_task_for_a_human(pipeline):
    manager, _ = pipeline

    async def approver(task_id, reason):
        return False  # e.g. a merge conflict

    manager.auto_approver = approver

    task = finish_pipeline(manager, project(auto_final_approval=True))

    assert task.sdlc_status == SDLCStatus.pending_approval
    assert any(event.kind == "escalated" and "Automatic approval did not complete" in event.message for event in task.timeline)


def test_default_policy_is_unchanged_a_human_approves(pipeline):
    manager, _ = pipeline

    async def approver(task_id, reason):
        raise AssertionError("auto_final_approval is off")

    manager.auto_approver = approver

    assert finish_pipeline(manager, project()).sdlc_status == SDLCStatus.pending_approval


def test_human_gate_off_means_taskloom_approves_every_passing_task(pipeline):
    manager, _ = pipeline
    seen = []

    async def approver(task_id, reason):
        seen.append(reason)
        await manager.update_task(task_id, lambda t: setattr(t, "sdlc_status", SDLCStatus.done))
        return True

    manager.auto_approver = approver

    task = finish_pipeline(manager, project(require_final_human_approval=False), files=("Dockerfile",))

    assert task.sdlc_status == SDLCStatus.done and seen == ["the project does not require a final approval"]


# ------------------------------------------------------------------------------- timeline and metrics

def test_timeline_is_bounded_and_durations_come_from_stage_starts():
    task = make_task()
    for index in range(520):
        policy.record_event(task, "stage_completed", f"event {index}")
    assert len(task.timeline) == 500 and task.timeline[-1].message == "event 519"

    started = policy.record_event(task, "stage_started", stage="backend")
    started.at = datetime.now(timezone.utc) - timedelta(seconds=42)
    assert 41 <= policy.stage_duration(task, "backend") <= 44
    assert policy.stage_duration(task, "qa") is None


def test_metrics_summarise_delivery_and_automation():
    now = datetime.now(timezone.utc)
    fast = make_task(task_id="t1"); fast.sdlc_status = SDLCStatus.done; fast.created_at = now - timedelta(seconds=100)
    policy.record_event(fast, "stage_completed", stage="backend", duration_seconds=30)
    policy.record_event(fast, "auto_approved")
    fast.risk = policy.assess_risk(fast)
    slow = make_task(task_id="t2"); slow.sdlc_status = SDLCStatus.done; slow.created_at = now - timedelta(seconds=300)
    slow.revision_count = 1; slow.stage_attempts = {"backend": 1}
    policy.record_event(slow, "stage_completed", stage="backend", duration_seconds=90)
    policy.record_event(slow, "human_response")
    policy.record_event(slow, "approved")
    open_task = make_task(task_id="t3"); open_task.sdlc_status = SDLCStatus.pending_approval

    metrics = policy.compute_metrics([fast, slow, open_task])

    assert metrics["total"] == 3 and metrics["done"] == 2 and metrics["by_status"] == {"done": 2, "pending_approval": 1}
    assert metrics["success_rate"] == round(2 / 3, 3)
    assert metrics["first_pass_rate"] == 0.5 and metrics["automation_rate"] == 0.5
    assert metrics["auto_retries"] == 1 and metrics["human_responses"] == 1
    assert metrics["stage_avg_seconds"] == {"backend": 60.0}
    assert 195 <= metrics["avg_cycle_seconds"] <= 205 and metrics["risk"]["low"] == 1
    assert policy.compute_metrics([])["success_rate"] is None
