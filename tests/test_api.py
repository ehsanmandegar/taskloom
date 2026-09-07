import json
from pathlib import Path
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app, tasks
from backend.app.guide_mcp import GuideCatalog
from backend.app.models import RunStatus, TaskState
from backend.app.services import resolve_guides

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
