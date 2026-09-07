from pathlib import Path
from fastapi.testclient import TestClient
from backend.app.main import app, tasks
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
