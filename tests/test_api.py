import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from backend.app import services
from backend.app import main as main_module
from backend.app.main import app, load_tasks, project_defaults, save_tasks, tasks
from backend.app.guide_mcp import GuideCatalog
from backend.app.models import McpFailureMode, RunStatus, TaskRequest, TaskState
from backend.app.services import CodexEventStream, build_prompt, codex_response, continue_task, execute_task, generate_commit_message, mcp_runtime_issue, preflight_project_mcp, resolve_guides

client = TestClient(app)


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_defaults_point_to_taskloom_and_its_contract(monkeypatch):
    project_root = Path(__file__).parents[1].resolve()
    monkeypatch.setenv("TASKLOOM_DEFAULT_PROJECT_PATH", str(project_root))
    monkeypatch.delenv("TASKLOOM_DEFAULT_GUIDE_PATHS", raising=False)
    monkeypatch.delenv("TASKLOOM_DEFAULT_TEST_COMMAND", raising=False)
    monkeypatch.delenv("TASKLOOM_DEFAULT_BASE_BRANCH", raising=False)

    response = client.get("/api/defaults")

    assert response.status_code == 200
    assert response.json()["project_path"] == str(project_root)
    assert response.json()["guide_paths"] == [str(project_root / "04-taskloom-project-contract.md")]
    assert response.json()["test_command"] in {
        r".venv\Scripts\python.exe -m pytest -q",
        ".venv/bin/python -m pytest -q",
        None,
    }
    assert response.json()["mcp_server_name"] == "dws_project"
    assert response.json()["mcp_failure_mode"] == "blocked"
    assert response.json()["base_branch"] == "main"


def test_defaults_can_be_overridden_for_another_project(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("TASKLOOM_DEFAULT_PROJECT_PATH", str(tmp_path))
    monkeypatch.setenv("TASKLOOM_DEFAULT_GUIDE_PATHS", os.pathsep.join(["AGENTS.md", "docs"]))
    monkeypatch.setenv("TASKLOOM_DEFAULT_TEST_COMMAND", "python -m pytest tests/unit")
    monkeypatch.setenv("TASKLOOM_DEFAULT_MCP_SERVER", "other_project")
    monkeypatch.setenv("TASKLOOM_DEFAULT_MCP_FAILURE_MODE", "warning")
    monkeypatch.setenv("TASKLOOM_DEFAULT_BASE_BRANCH", "release/next")

    defaults = project_defaults()

    assert defaults.project_path == str(tmp_path.resolve())
    assert defaults.guide_paths == ["AGENTS.md", "docs"]
    assert defaults.test_command == "python -m pytest tests/unit"
    assert defaults.mcp_server_name == "other_project"
    assert defaults.mcp_failure_mode == McpFailureMode.warning
    assert defaults.base_branch == "release/next"


def test_dws_defaults_include_the_documentation_directory(monkeypatch, tmp_path: Path):
    backend = tmp_path / "backend"
    docs = backend / "docs"
    docs.mkdir(parents=True)
    readme = tmp_path / "README.md"
    testing_guide = backend / "TESTING_GUIDE.md"
    readme.write_text("project", encoding="utf-8")
    testing_guide.write_text("testing", encoding="utf-8")
    monkeypatch.setenv("TASKLOOM_DEFAULT_PROJECT_PATH", str(tmp_path))
    monkeypatch.setenv("DWS_PROJECT_PATH", str(tmp_path))
    monkeypatch.delenv("TASKLOOM_DEFAULT_GUIDE_PATHS", raising=False)
    monkeypatch.delenv("TASKLOOM_DEFAULT_BASE_BRANCH", raising=False)

    defaults = project_defaults()

    assert defaults.guide_paths == [str(readme), str(testing_guide), str(docs)]
    assert defaults.base_branch == "sandbox"


def test_rejects_non_git_directory(tmp_path: Path):
    response = client.post("/api/tasks", json={"project_path": str(tmp_path), "task_id": "podw-205", "request": "add a useful feature"})
    assert response.status_code == 422


def test_invalid_task_id_rejected(tmp_path: Path):
    (tmp_path / ".git").mkdir()
    response = client.post("/api/tasks", json={"project_path": str(tmp_path), "task_id": "bad/id", "request": "add a useful feature"})
    assert response.status_code == 422


def test_invalid_base_branch_is_rejected(tmp_path: Path):
    (tmp_path / ".git").mkdir()
    response = client.post("/api/tasks", json={"project_path": str(tmp_path), "task_id": "podw-branch", "request": "add a useful feature", "base_branch": "../sandbox"})
    assert response.status_code == 422


def test_new_tasks_use_the_tasks_branch_prefix(monkeypatch, tmp_path: Path):
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(main_module, "save_tasks", lambda states: None)

    def discard_background_task(coroutine):
        coroutine.close()

    monkeypatch.setattr(main_module.asyncio, "create_task", discard_background_task)
    request = TaskRequest(
        project_path=str(tmp_path),
        task_id="podw-225",
        request="add a useful feature",
        base_branch="sandbox",
    )

    state = asyncio.run(main_module.create_task(request))

    assert state.branch == "tasks/podw-225"
    assert state.base_branch == "sandbox"
    tasks.pop(state.id)


def test_execute_task_creates_the_task_branch_from_selected_base(monkeypatch):
    project_root = Path(__file__).parents[1].resolve()
    request = TaskRequest(
        project_path=str(project_root),
        task_id="podw-base",
        request="add a useful feature",
        base_branch="sandbox",
    )
    state = TaskState(
        id="base-branch",
        task_id=request.task_id,
        project_path=str(project_root),
        branch="tasks/podw-base",
        base_branch=request.base_branch,
        status=RunStatus.queued,
        step="Queued",
    )
    calls = []

    async def fake_command(args, cwd, timeout=900):
        calls.append(args)
        if args[:3] == ["git", "switch", "-c"]:
            return 1, "stop after branch assertion"
        return 0, ""

    monkeypatch.setattr(services, "command", fake_command)
    monkeypatch.setattr(services.shutil, "which", lambda name: "codex")

    asyncio.run(execute_task(request, state))

    assert ["git", "rev-parse", "--verify", "--quiet", "refs/heads/sandbox^{commit}"] in calls
    assert ["git", "switch", "-c", "tasks/podw-base", "sandbox"] in calls


def test_push_requires_commit(tmp_path: Path):
    (tmp_path / ".git").mkdir()
    tasks["demo"] = TaskState(id="demo", task_id="podw-205", project_path=str(tmp_path), branch="tasks/podw-205", status=RunStatus.passed, step="ready")
    assert client.post("/api/tasks/demo/push").status_code == 409


def test_merge_request_requires_push():
    tasks["not-pushed"] = TaskState(id="not-pushed", task_id="podw-214", project_path="unused", branch="tasks/podw-214", status=RunStatus.passed, step="ready", committed=True)

    response = client.post("/api/tasks/not-pushed/merge-request")

    assert response.status_code == 409
    assert response.json()["detail"] == "Push the task branch first"


@pytest.mark.parametrize(
    ("remote", "cli", "cli_args", "url"),
    [
        (
            "https://github.com/acme/example.git",
            "gh",
            ["pr", "create", "--fill", "--head", "tasks/podw-214", "--base", "sandbox"],
            "https://github.com/acme/example/pull/42",
        ),
        (
            "git@gitlab.com:acme/example.git",
            "glab",
            ["mr", "create", "--fill", "--source-branch", "tasks/podw-214", "--target-branch", "sandbox", "--yes"],
            "https://gitlab.com/acme/example/-/merge_requests/42",
        ),
    ],
)
def test_creates_merge_request_and_returns_url(monkeypatch, tmp_path: Path, remote, cli, cli_args, url):
    project_root = Path(__file__).parents[1]
    monkeypatch.setenv("TASKLOOM_SESSIONS_PATH", str(tmp_path / "sessions.json"))
    run_id = f"pushed-{cli}"
    tasks[run_id] = TaskState(id=run_id, task_id="podw-214", project_path=str(project_root), branch="tasks/podw-214", base_branch="sandbox", status=RunStatus.passed, step="ready", committed=True, pushed=True)
    calls = []

    async def fake_command(args, cwd, timeout=900):
        calls.append((args, cwd, timeout))
        if args == ["git", "remote", "get-url", "origin"]:
            return 0, remote + "\n"
        return 0, url + "\n"

    monkeypatch.setattr(services, "command", fake_command)
    monkeypatch.setattr(services.shutil, "which", lambda name: f"/tools/{name}")

    response = client.post(f"/api/tasks/{run_id}/merge-request")

    assert response.status_code == 200
    assert response.json()["url"] == url
    assert response.json()["task"]["merge_request_url"] == response.json()["url"]
    assert calls[1] == ([f"/tools/{cli}", *cli_args], project_root.resolve(), 600)
    assert client.post(f"/api/tasks/{run_id}/merge-request").status_code == 409


def test_profiles_are_persisted(monkeypatch, tmp_path: Path):
    profile_file = tmp_path / "profiles.json"
    monkeypatch.setenv("TASKLOOM_PROFILES_PATH", str(profile_file))
    profile = {"name": "project 1", "project_path": str(tmp_path), "guide_paths": ["docs"], "test_command": "pytest -q"}

    assert client.put("/api/profiles/project%201", json=profile).status_code == 200
    assert client.get("/api/profiles").json() == [
        {**profile, "base_branch": "main", "mcp_server_name": None, "mcp_failure_mode": "warning", "git_provider": "auto"}
    ]
    assert profile_file.exists()

    assert client.delete("/api/profiles/project%201").status_code == 204
    assert client.get("/api/profiles").json() == []


def test_resolve_guides_expands_markdown_directories(tmp_path: Path):
    docs = tmp_path / "docs"
    nested = docs / "nested"
    nested.mkdir(parents=True)
    first, second = docs / "one.md", nested / "two.md"
    first.write_text("one", encoding="utf-8")
    second.write_text("two", encoding="utf-8")
    (docs / "ignored.txt").write_text("no", encoding="utf-8")

    assert resolve_guides(tmp_path, ["docs", str(first)]) == [first.resolve(), second.resolve()]


def test_build_prompt_requires_reviewing_markdown_after_changes():
    request = TaskRequest(
        project_path="project",
        task_id="podw-215",
        request="change application behavior",
    )

    prompt = build_prompt(request, [])

    assert "After every implementation change" in prompt
    assert "review the relevant Markdown (.md) files" in prompt
    assert "If no Markdown update is needed, state that explicitly" in prompt


def test_build_prompt_uses_dws_mcp_for_context_but_not_test_evidence():
    request = TaskRequest(
        project_path="project",
        task_id="podw-223",
        request="change application behavior",
        mcp_server_name="dws_project",
        mcp_failure_mode="blocked",
    )

    prompt = build_prompt(request, [], active_mcp="dws_project")

    assert "`search_docs`, `read_doc`, `search_code`, or `read_file`" in prompt
    assert "Do not use its `run_tests` tool as evidence" in prompt


def test_mcp_preflight_requires_configured_and_enabled_entry(monkeypatch):
    calls = []

    async def fake_command(args, cwd, timeout=900):
        calls.append((args, cwd, timeout))
        return 0, 'warning on stderr\n{\n  "name": "dws_project",\n  "enabled": true\n}\n'

    monkeypatch.setattr(services, "command", fake_command)

    ready, message = asyncio.run(preflight_project_mcp("codex", Path("repo"), "dws_project"))

    assert ready is True
    assert "configured and enabled" in message
    assert calls == [(["codex", "mcp", "get", "dws_project", "--json"], Path("repo"), 30)]


@pytest.mark.parametrize(
    ("code", "output", "expected"),
    [
        (1, "not found", "not configured"),
        (0, '{"name":"dws_project","enabled":false}', "disabled"),
        (0, "not json", "unreadable"),
    ],
)
def test_mcp_preflight_reports_unavailable_states(monkeypatch, code, output, expected):
    async def fake_command(args, cwd, timeout=900):
        return code, output

    monkeypatch.setattr(services, "command", fake_command)

    ready, message = asyncio.run(preflight_project_mcp("codex", Path("repo"), "dws_project"))

    assert ready is False
    assert expected in message


def test_mcp_runtime_issue_detects_initialization_failure_without_exposing_output():
    output = "MCP client dws_project failed to initialize: private implementation detail"

    assert mcp_runtime_issue(output, "dws_project") == (
        "MCP `dws_project` did not initialize in the Codex session."
    )


def test_required_mcp_blocks_before_creating_a_branch(monkeypatch):
    project_root = Path(__file__).parents[1].resolve()
    request = TaskRequest(
        project_path=str(project_root),
        task_id="podw-223",
        request="change application behavior",
        mcp_server_name="dws_project",
        mcp_failure_mode="blocked",
    )
    state = TaskState(
        id="mcp-blocked",
        task_id=request.task_id,
        project_path=str(project_root),
        branch="tasks/podw-223",
        mcp_server_name="dws_project",
        mcp_failure_mode="blocked",
        status=RunStatus.queued,
        step="Queued",
    )
    calls = []

    async def fake_command(args, cwd, timeout=900):
        calls.append(args)
        return 1, "missing"

    monkeypatch.setattr(services, "command", fake_command)
    monkeypatch.setattr(services.shutil, "which", lambda name: "codex")

    asyncio.run(execute_task(request, state))

    assert state.status == RunStatus.blocked
    assert state.mcp_status == "blocked"
    assert state.step == "Project MCP preflight blocked"
    assert calls == [["codex", "mcp", "get", "dws_project", "--json"]]


def test_required_mcp_initialization_failure_blocks_without_thread_id(monkeypatch):
    project_root = Path(__file__).parents[1].resolve()
    request = TaskRequest(
        project_path=str(project_root),
        task_id="podw-224",
        request="change application behavior",
        mcp_server_name="dws_project",
        mcp_failure_mode="blocked",
    )
    state = TaskState(
        id="mcp-init-blocked",
        task_id=request.task_id,
        project_path=str(project_root),
        branch="tasks/podw-224",
        mcp_server_name="dws_project",
        mcp_failure_mode="blocked",
        status=RunStatus.queued,
        step="Queued",
    )

    async def fake_command(args, cwd, timeout=900):
        if args[1:5] == ["mcp", "get", "dws_project", "--json"]:
            return 0, '{"name":"dws_project","enabled":true}'
        if args[:3] == ["git", "status", "--porcelain"] or args[:3] == ["git", "switch", "-c"]:
            return 0, ""
        if args[1:3] == ["exec", "--sandbox"]:
            return 1, "MCP dws_project failed to initialize before thread startup"
        return 0, ""

    monkeypatch.setattr(services, "command", fake_command)
    monkeypatch.setattr(services.shutil, "which", lambda name: "codex")

    asyncio.run(execute_task(request, state))

    assert state.status == RunStatus.blocked
    assert state.mcp_status == "blocked"
    assert state.codex_thread_id == ""
    assert state.error == "MCP `dws_project` did not initialize in the Codex session."


def test_codex_response_reads_thread_and_final_message_from_jsonl():
    output = "\n".join(
        [
            "Codex progress on stderr",
            json.dumps({"type": "thread.started", "thread_id": "thread-123"}),
            json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "First response"}}),
            json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "Final response"}}),
        ]
    )

    assert codex_response(output) == ("thread-123", "First response\n\nFinal response")


def test_codex_jsonl_events_update_live_output_incrementally():
    state = TaskState(id="live", task_id="podw-live", project_path="unused", branch="task/podw-live", status=RunStatus.running, step="running")
    stream = CodexEventStream(state)
    first = json.dumps({"type": "thread.started", "thread_id": "thread-live"}) + "\n"
    update = json.dumps({"type": "item.updated", "item": {"id": "reply", "type": "agent_message", "text": "در حال بررسی"}}) + "\n"
    completed = json.dumps({"type": "item.completed", "item": {"id": "reply", "type": "agent_message", "text": "در حال بررسی فایل‌ها"}}) + "\n"

    stream.feed(first[:12])
    assert state.codex_thread_id == ""
    stream.feed(first[12:] + update + completed)
    stream.finish()

    assert state.codex_thread_id == "thread-live"
    assert state.live_response == "در حال بررسی فایل‌ها"
    assert "در حال بررسی فایل‌ها" in state.live_output


def test_task_event_stream_returns_latest_terminal_snapshot():
    state = TaskState(id="streamed", task_id="podw-stream", project_path="unused", branch="task/podw-stream", status=RunStatus.passed, step="ready", live_output="finished")
    tasks[state.id] = state
    try:
        response = client.get(f"/api/tasks/{state.id}/events")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.text.startswith("data: ")
        payload = json.loads(response.text.removeprefix("data: ").strip())
        assert payload["live_output"] == "finished"
    finally:
        tasks.pop(state.id, None)


def test_stopping_a_running_task_cancels_worker_and_keeps_session_resumable(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("TASKLOOM_SESSIONS_PATH", str(tmp_path / "sessions.json"))

    async def scenario():
        state = TaskState(
            id="stop-me",
            task_id="podw-stop",
            project_path="unused",
            branch="tasks/podw-stop",
            status=RunStatus.running,
            step="Codex is responding",
            codex_thread_id="thread-stop",
            live_response="پاسخ ناتمام",
        )
        tasks[state.id] = state
        started = asyncio.Event()

        async def active_worker():
            started.set()
            await asyncio.Event().wait()

        worker = asyncio.create_task(active_worker())
        main_module.task_workers[state.id] = worker
        await started.wait()
        try:
            result = await main_module.stop_task(state.id)
            assert worker.cancelled()
            assert result.status == RunStatus.stopped
            assert result.codex_thread_id == "thread-stop"
            assert result.live_response == "پاسخ ناتمام"
        finally:
            tasks.pop(state.id, None)
            main_module.task_workers.pop(state.id, None)

    asyncio.run(scenario())


def test_follow_up_is_queued_for_a_stopped_codex_session(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("TASKLOOM_SESSIONS_PATH", str(tmp_path / "sessions.json"))
    run_id = "chat-ready"
    tasks[run_id] = TaskState(
        id=run_id,
        task_id="podw-217",
        project_path=str(Path(__file__).parents[1]),
        branch="tasks/podw-217",
        status=RunStatus.stopped,
        step="Stopped by user",
        codex_thread_id="thread-123",
    )

    async def fake_continue(message, state):
        return None

    monkeypatch.setattr(main_module, "continue_task", fake_continue)
    response = client.post(f"/api/tasks/{run_id}/messages", json={"message": "Please improve the result"})

    assert response.status_code == 202
    assert response.json()["step"] == "Queued follow-up"
    assert response.json()["messages"] == [{"role": "user", "content": "Please improve the result"}]


def test_task_sessions_are_persisted_and_listed(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("TASKLOOM_SESSIONS_PATH", str(tmp_path / "sessions.json"))
    state = TaskState(
        id="saved-chat",
        task_id="podw-218",
        project_path=str(tmp_path),
        branch="tasks/podw-218",
        status=RunStatus.passed,
        step="Ready for further instructions",
        codex_thread_id="thread-218",
        messages=[{"role": "user", "content": "Keep improving this."}],
    )

    save_tasks({state.id: state})
    restored = load_tasks()

    assert restored[state.id].codex_thread_id == "thread-218"
    assert restored[state.id].messages[0].content == "Keep improving this."
    original = dict(tasks)
    try:
        tasks.clear()
        tasks.update(restored)
        response = client.get("/api/tasks")
        assert response.status_code == 200
        assert response.json()[0]["id"] == "saved-chat"
    finally:
        tasks.clear()
        tasks.update(original)


def test_load_tasks_keeps_interrupted_sessions_when_storage_is_unavailable(monkeypatch):
    class SessionFile:
        def exists(self):
            return True

        def read_text(self, encoding):
            return json.dumps(
                {
                    "interrupted": {
                        "id": "interrupted",
                        "task_id": "podw-219",
                        "project_path": "project",
                        "branch": "tasks/podw-219",
                        "status": "running",
                        "step": "Codex is implementing the request",
                    }
                }
            )

    def unavailable_storage(_states):
        raise main_module.HTTPException(500, "storage unavailable")

    monkeypatch.setattr(main_module, "sessions_path", lambda: SessionFile())
    monkeypatch.setattr(main_module, "save_tasks", unavailable_storage)

    restored = load_tasks()

    assert restored["interrupted"].status == RunStatus.failed
    assert restored["interrupted"].step == "Interrupted by Taskloom restart"


def test_generate_commit_message_uses_the_task_codex_session(monkeypatch):
    state = TaskState(
        id="commit-message",
        task_id="podw-219",
        project_path=str(Path(__file__).parents[1]),
        branch="tasks/podw-219",
        status=RunStatus.passed,
        step="Ready for review",
        codex_thread_id="thread-219",
        changed_files=["backend/app/main.py"],
    )
    calls = []

    async def fake_command(args, cwd, timeout=900):
        calls.append((args, cwd, timeout))
        return 0, "\n".join(
            [
                json.dumps({"type": "thread.started", "thread_id": "thread-219"}),
                json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "fix(podw-219): recover sessions when storage is unavailable"}}),
            ]
        )

    monkeypatch.setattr(services, "command", fake_command)
    monkeypatch.setattr(services.shutil, "which", lambda name: "codex" if name == "codex" else name)

    assert asyncio.run(generate_commit_message(state)) == "fix(podw-219): recover sessions when storage is unavailable"
    assert calls[0][0][:5] == ["codex", "exec", "resume", "--json", "thread-219"]
    assert "exactly one Conventional Commit message" in calls[0][0][-1]


def test_continue_task_resumes_same_codex_session_and_retests(monkeypatch):
    state = TaskState(
        id="continue",
        task_id="podw-217",
        project_path=str(Path(__file__).parents[1]),
        branch="tasks/podw-217",
        test_command="pytest -q custom",
        status=RunStatus.passed,
        step="ready",
        codex_thread_id="thread-123",
    )
    calls = []

    async def fake_command(args, cwd, timeout=900):
        calls.append(args)
        if args[:3] == ["codex", "exec", "resume"]:
            return 0, "\n".join(
                [
                    json.dumps({"type": "thread.started", "thread_id": "thread-123"}),
                    json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "Improved it."}}),
                ]
            )
        return 0, ""

    monkeypatch.setattr(services, "command", fake_command)
    monkeypatch.setattr(services.shutil, "which", lambda name: "codex" if name == "codex" else name)

    asyncio.run(continue_task("Improve it", state))

    assert calls[0][:5] == ["codex", "exec", "resume", "--json", "thread-123"]
    assert ["pytest", "-q", "custom"] in calls
    assert state.status == RunStatus.passed
    assert state.step == "Ready for further instructions"
    assert [message.model_dump() for message in state.messages] == [{"role": "assistant", "content": "Improved it."}]


def test_guide_catalog_reads_and_searches_only_markdown_roots(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    guide = docs / "setup.md"
    guide.write_text("# Setup\nRun pytest for verification.\n", encoding="utf-8")
    (docs / "private.txt").write_text("not a guide", encoding="utf-8")
    outside = tmp_path / "outside.md"
    outside.write_text("secret", encoding="utf-8")
    catalog = GuideCatalog([docs])

    assert [item["path"] for item in catalog.list_guides()] == ["setup.md"]
    assert catalog.read_guide("setup.md").startswith("# Setup")
    assert catalog.search_guides("PYTEST") == [
        {
            "path": "setup.md",
            "uri": guide.resolve().as_uri(),
            "line": 2,
            "text": "Run pytest for verification.",
        }
    ]
    with pytest.raises(ValueError, match="not available"):
        catalog.read_guide(str(outside))


def test_guide_mcp_stdio_handshake_and_tools(tmp_path: Path):
    guide = tmp_path / "README.md"
    guide.write_text("# راهنما\nMCP can read this guide.\n", encoding="utf-8")
    requests = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"},
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "read_guide", "arguments": {"path": "README.md"}},
        },
        {"jsonrpc": "2.0", "id": 4, "method": "resources/list", "params": {}},
    ]
    project_root = Path(__file__).parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "backend.app.guide_mcp",
            "--root",
            str(tmp_path),
        ],
        input="".join(json.dumps(request) + "\n" for request in requests),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=project_root,
        timeout=10,
        check=True,
    )
    responses = [json.loads(line) for line in result.stdout.splitlines()]

    assert [response["id"] for response in responses] == [1, 2, 3, 4]
    assert responses[0]["result"]["serverInfo"]["name"] == "taskloom-guides"
    assert {tool["name"] for tool in responses[1]["result"]["tools"]} == {
        "list_guides",
        "read_guide",
        "search_guides",
    }
    assert "# راهنما" in responses[2]["result"]["content"][0]["text"]
    assert "MCP can read this guide" in responses[2]["result"]["content"][0]["text"]
    assert responses[3]["result"]["resources"][0]["uri"] == guide.resolve().as_uri()
