from pathlib import Path
from fastapi.testclient import TestClient
from backend.app.main import app, tasks
from backend.app.models import RunStatus, TaskState

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
