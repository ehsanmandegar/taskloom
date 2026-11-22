"""Autonomy policy for the SDLC pipeline: how much Taskloom may decide by itself, and the audit trail behind it.

The pipeline was already automatic between human gates. This module adds the pieces that let a project hand the
remaining gates to Taskloom *when it is safe*, and keeps a human in the loop whenever it is not:

* risk assessment of a finished task (size, sensitive files, tests, revisions, open issues),
* the rules for automatic analysis approval / final approval / automatic stage retries / automatic release drafts,
* a timeline (audit trail) per task, and
* delivery metrics across tasks.

Everything here is a pure function of the task and project, so it is easy to test and to explain in the dashboard.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from statistics import mean

from .models import RiskAssessment, SDLCProjectConfig, SDLCStatus, SDLCTask, TimelineEvent

LEVELS = {"low": 0, "medium": 1, "high": 2}

# Paths whose change deserves a human look even when the tests are green.
SENSITIVE_PATTERNS = {
    "authentication / secrets": re.compile(r"(^|/)(auth|security|secrets?|credentials?|\.env[^/]*|.*token.*|.*password.*)([./]|$)", re.I),
    "database migrations": re.compile(r"(^|/)(migrations?|alembic|schema\.sql)([./]|$)", re.I),
    "build / deploy configuration": re.compile(r"(^|/)(Dockerfile|docker-compose[^/]*|\.github/workflows/|\.gitlab-ci[^/]*|Jenkinsfile|terraform/|k8s/)", re.I),
    "dependency manifests": re.compile(r"(^|/)(package(-lock)?\.json|requirements[^/]*\.txt|pyproject\.toml|poetry\.lock|pnpm-lock\.yaml|yarn\.lock)$", re.I),
    "payments / billing": re.compile(r"(^|/)(payments?|billing|invoice[^/]*|checkout)([./]|$)", re.I),
}


# ------------------------------------------------------------------------------------------------ timeline

def record_event(task: SDLCTask, kind: str, message: str = "", stage: str = "", actor: str = "system",
                 duration_seconds: float | None = None) -> TimelineEvent:
    """Append to the task's audit trail (the caller saves the task)."""
    event = TimelineEvent(kind=kind, message=message[:500], stage=stage, actor=actor, duration_seconds=duration_seconds)
    task.timeline.append(event)
    del task.timeline[:-500]  # bounded: the newest 500 events are kept
    return event


def stage_duration(task: SDLCTask, stage: str) -> float | None:
    """Seconds since the stage's latest start event (used when the stage completes or fails)."""
    for event in reversed(task.timeline):
        if event.kind == "stage_started" and event.stage == stage:
            return round((datetime.now(timezone.utc) - event.at).total_seconds(), 1)
    return None


# ----------------------------------------------------------------------------------------------- risk

def assess_risk(task: SDLCTask) -> RiskAssessment:
    """Score a finished task. Low risk = small, well-tested, nothing sensitive touched, no drama on the way."""
    score, reasons, blocking = 0, [], False
    files, deleted = {}, 0
    tests_executed = tests_failed = False
    issues = 0
    for result in task.agent_results.values():
        for change in result.changes:
            files[change.file] = change.kind
            deleted += change.kind == "deleted"
        tests_executed |= result.tests.executed
        tests_failed |= result.tests.executed and not result.tests.passed
        issues += len(result.issues)

    count = len(files)
    if count > 25:
        score += 3; reasons.append(f"large change: {count} files")
    elif count > 10:
        score += 2; reasons.append(f"sizeable change: {count} files")
    elif count > 5:
        score += 1; reasons.append(f"{count} files changed")
    if deleted >= 3:
        score += 1; reasons.append(f"{deleted} files deleted")

    for label, pattern in SENSITIVE_PATTERNS.items():
        touched = sorted(name for name in files if pattern.search(name.replace("\\", "/")))
        if touched:
            score += 3
            reasons.append(f"touches {label} ({', '.join(touched[:3])}{'…' if len(touched) > 3 else ''})")

    if tests_failed:
        score += 5; blocking = True; reasons.append("automated tests failed")
    elif not tests_executed:
        score += 2; reasons.append("no automated tests ran")
    if task.revision_count >= 2:
        score += 1; reasons.append(f"{task.revision_count} revision rounds")
    retries = sum(task.stage_attempts.values())
    if retries:
        score += 1; reasons.append(f"{retries} automatic stage retr{'y' if retries == 1 else 'ies'}")
    if issues:
        score += (issues + 1) // 2; reasons.append(f"{issues} open issue(s) reported by the agents")

    level = "high" if blocking or score > 5 else "medium" if score > 2 else "low"
    return RiskAssessment(level=level, score=score, reasons=reasons, blocking=blocking)


# ----------------------------------------------------------------------------------------- decisions

def analysis_is_clean(task: SDLCTask) -> tuple[bool, str]:
    """May the analysis gate be skipped? Only when the analysis finished cleanly and nothing is left open."""
    analysis = task.agent_results.get("analysis")
    if analysis is None or analysis.status != "completed":
        return False, "the analysis did not complete"
    if analysis.issues:
        return False, f"the analysis lists {len(analysis.issues)} open issue(s)"
    if any(question.status == "open" for question in task.stage_questions):
        return False, "a stage question is still open"
    if not analysis.summary.strip():
        return False, "the analysis has no summary to approve"
    return True, "the analysis is complete, has no open issues and no open questions"


def can_auto_approve(task: SDLCTask, project: SDLCProjectConfig) -> tuple[bool, str]:
    """May this finished task be approved (and merged into develop) without a human?"""
    workflow = project.workflow
    risk = task.risk or assess_risk(task)
    if not workflow.require_final_human_approval:
        # The project switched the human gate off: Taskloom approves, but a failing test run is never waved through.
        return (False, "automated tests failed") if risk.blocking else (True, "the project does not require a final approval")
    if not workflow.auto_final_approval:
        return False, "this project requires a human final approval"
    if risk.blocking:
        return False, "; ".join(risk.reasons) or "blocking risk"
    ceiling = LEVELS.get(workflow.auto_approval_max_risk, 0)
    if LEVELS[risk.level] > ceiling:
        return False, f"risk is {risk.level} (allowed without a human: {workflow.auto_approval_max_risk}): " + "; ".join(risk.reasons)
    if any(item.status == "pending" for item in task.human_interventions):
        return False, "a human intervention is still pending"
    return True, f"risk is {risk.level}" + (f" ({'; '.join(risk.reasons)})" if risk.reasons else " and the tests passed")


def retries_left(task: SDLCTask, stage: str, project: SDLCProjectConfig) -> int:
    return max(0, project.workflow.auto_retry_failed_stages - task.stage_attempts.get(stage, 0))


# ------------------------------------------------------------------------------------------- releases

_SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def next_release_version(existing: list[str]) -> str:
    """Next patch version after the highest plain x.y.z already used (0.1.0 when there is none)."""
    versions = [tuple(map(int, match.groups())) for version in existing if (match := _SEMVER.match(version))]
    if not versions:
        return "0.1.0"
    major, minor, patch = max(versions)
    return f"{major}.{minor}.{patch + 1}"


# --------------------------------------------------------------------------------------------- metrics

def compute_metrics(tasks: list[SDLCTask]) -> dict:
    """Delivery metrics for the dashboard: throughput, cycle time, first-pass rate, automation rate, stage timings."""
    by_status: dict[str, int] = {}
    cycle, stage_times = [], {}
    done = first_pass = auto_approved = human_touches = retries = escalations = 0
    risk_counts = {"low": 0, "medium": 0, "high": 0}
    for task in tasks:
        by_status[task.sdlc_status.value] = by_status.get(task.sdlc_status.value, 0) + 1
        retries += sum(task.stage_attempts.values())
        human_touches += sum(1 for event in task.timeline if event.kind == "human_response")
        escalations += sum(1 for event in task.timeline if event.kind == "escalated")
        for event in task.timeline:
            if event.kind in ("stage_completed", "stage_failed") and event.duration_seconds is not None:
                stage_times.setdefault(event.stage, []).append(event.duration_seconds)
        if task.risk:
            risk_counts[task.risk.level] = risk_counts.get(task.risk.level, 0) + 1
        if task.sdlc_status == SDLCStatus.done:
            done += 1
            finished = next((e.at for e in reversed(task.timeline) if e.kind in ("approved", "auto_approved")), task.updated_at)
            cycle.append(max(0.0, (finished - task.created_at).total_seconds()))
            first_pass += task.revision_count == 0 and not task.stage_attempts
            auto_approved += any(e.kind == "auto_approved" for e in task.timeline)
    total = len(tasks)
    return {
        "total": total,
        "by_status": by_status,
        "done": done,
        "success_rate": round(done / total, 3) if total else None,
        "avg_cycle_seconds": round(mean(cycle), 1) if cycle else None,
        "first_pass_rate": round(first_pass / done, 3) if done else None,
        "automation_rate": round(auto_approved / done, 3) if done else None,
        "auto_retries": retries,
        "escalations": escalations,
        "human_responses": human_touches,
        "stage_avg_seconds": {stage: round(mean(values), 1) for stage, values in stage_times.items()},
        "risk": risk_counts,
    }
