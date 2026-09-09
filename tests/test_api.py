import asyncio
import json
from pathlib import Path
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from backend.app import services
from backend.app import main as main_module
from backend.app.main import app, load_tasks, save_tasks, tasks
from backend.app.guide_mcp import GuideCatalog
from backend.app.models import RunStatus, TaskRequest, TaskState
from backend.app.services import build_prompt, codex_response, continue_task, resolve_guides

client = TestClient(app)


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_rejects_non_git_directory(tmp_path: Path):
    response = client.post("/api/tasks", json={"project_path": str(tmp_path), "task_id": "podw-205", "request": "add a useful feature"})
    assert response.status_code == 422


def test_invalid_task_id_rejected(tmp_path: Path):
    (tmp_path / ".git").mkdir()
    response = client.post("/api/tasks", json={"project_path": str(tmp_path), "task_id": "bad/id", "request": "add a useful feature"})
    assert response.status_code == 422


def test_push_requires_commit(tmp_path: Path):
    (tmp_path / ".git").mkdir()
    tasks["demo"] = TaskState(id="demo", task_id="podw-205", project_path=str(tmp_path), branch="task/podw-205", status=RunStatus.passed, step="ready")
    assert client.post("/api/tasks/demo/push").status_code == 409


def test_merge_request_requires_push():
    tasks["not-pushed"] = TaskState(id="not-pushed", task_id="podw-214", project_path="unused", branch="task/podw-214", status=RunStatus.passed, step="ready", committed=True)

    response = client.post("/api/tasks/not-pushed/merge-request")

    assert response.status_code == 409
    assert response.json()["detail"] == "Push the task branch first"


@pytest.mark.parametrize(
    ("remote", "cli", "cli_args", "url"),
    [
        (
            "https://github.com/acme/example.git",
            "gh",
            ["pr", "create", "--fill", "--head", "task/podw-214"],
            "https://github.com/acme/example/pull/42",
        ),
        (
            "git@gitlab.com:acme/example.git",
            "glab",
            ["mr", "create", "--fill", "--source-branch", "task/podw-214", "--yes"],
            "https://gitlab.com/acme/example/-/merge_requests/42",
        ),
    ],
)
def test_creates_merge_request_and_returns_url(monkeypatch, tmp_path: Path, remote, cli, cli_args, url):
    project_root = Path(__file__).parents[1]
    monkeypatch.setenv("TASKLOOM_SESSIONS_PATH", str(tmp_path / "sessions.json"))
    run_id = f"pushed-{cli}"
    tasks[run_id] = TaskState(id=run_id, task_id="podw-214", project_path=str(project_root), branch="task/podw-214", status=RunStatus.passed, step="ready", committed=True, pushed=True)
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
    assert client.get("/api/profiles").json() == [profile]
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


def test_follow_up_is_queued_for_the_existing_codex_session(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("TASKLOOM_SESSIONS_PATH", str(tmp_path / "sessions.json"))
    run_id = "chat-ready"
    tasks[run_id] = TaskState(
        id=run_id,
        task_id="podw-217",
        project_path=str(Path(__file__).parents[1]),
        branch="task/podw-217",
        status=RunStatus.passed,
        step="ready",
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
        branch="task/podw-218",
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


def test_continue_task_resumes_same_codex_session_and_retests(monkeypatch):
    state = TaskState(
        id="continue",
        task_id="podw-217",
        project_path=str(Path(__file__).parents[1]),
        branch="task/podw-217",
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
