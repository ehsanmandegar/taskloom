"""GitHub tokens live only in the encrypted secret store, never in project JSON or API responses."""

import asyncio
import json
import os

import pytest
from fastapi.testclient import TestClient

from backend.app import main as main_module
from backend.app import sdlc_git
from backend.app.models import AgentConfig, RunStatus, SDLCProjectConfig, SDLCTask, TaskState
from backend.app.secret_store import SecretStore
from backend.app.services import SDLCProjectManager, SDLCTaskManager

TOKEN = "ghp_SECRET_test_token_0123456789"


def test_store_roundtrip_without_plaintext_on_disk(tmp_path):
    store = SecretStore(tmp_path / "secrets.json")

    store.set("github:p:backend", TOKEN)

    assert TOKEN not in (tmp_path / "secrets.json").read_text(encoding="utf-8")
    assert store.get("github:p:backend") == TOKEN and store.has("github:p:backend")
    store.delete("github:p:backend")
    assert store.get("github:p:backend") is None and not store.has("github:p:backend")


@pytest.mark.skipif(os.name != "nt", reason="DPAPI is Windows-only")
def test_windows_store_uses_dpapi(tmp_path):
    store = SecretStore(tmp_path / "secrets.json")
    store.set("x", TOKEN)
    assert json.loads((tmp_path / "secrets.json").read_text(encoding="utf-8"))["x"]["scheme"] == "dpapi"


def project_with_token(token: str = TOKEN, **github) -> SDLCProjectConfig:
    config = AgentConfig(project_path="E:/shop")
    config.github_config.update({"repository_url": "https://github.com/acme/shop", "github_token": token, **github})
    return SDLCProjectConfig(id="p", name="Shop", agents={"backend": config})


def test_saving_a_project_moves_the_token_to_the_store(tmp_path):
    manager = SDLCProjectManager(tmp_path / "projects")

    manager.save_project(project_with_token())

    file_text = (tmp_path / "projects" / "p.json").read_text(encoding="utf-8")
    assert TOKEN not in file_text
    github = json.loads(file_text)["agents"]["backend"]["github_config"]
    assert github["github_token"] == "" and github["token_saved"] is True
    assert manager.github_token("p", "backend") == TOKEN
    assert SDLCProjectManager(tmp_path / "projects").github_token("p", "backend") == TOKEN  # survives reload


def test_empty_token_keeps_clear_token_removes_new_token_replaces(tmp_path):
    manager = SDLCProjectManager(tmp_path / "projects")
    manager.save_project(project_with_token())

    manager.save_project(project_with_token(""))
    assert manager.github_token("p", "backend") == TOKEN

    manager.save_project(project_with_token("ghp_new"))
    assert manager.github_token("p", "backend") == "ghp_new"

    manager.save_project(project_with_token("", clear_token=True))
    assert manager.github_token("p", "backend") == ""
    github = manager.get_project("p").agents["backend"].github_config
    assert github["token_saved"] is False and "clear_token" not in github


def test_old_project_files_are_migrated_on_load(tmp_path):
    (tmp_path / "projects").mkdir()
    (tmp_path / "projects" / "p.json").write_text(project_with_token().model_dump_json(), encoding="utf-8")

    manager = SDLCProjectManager(tmp_path / "projects")

    assert TOKEN not in (tmp_path / "projects" / "p.json").read_text(encoding="utf-8")
    assert manager.github_token("p", "backend") == TOKEN
    assert manager.get_project("p").agents["backend"].github_config["token_saved"] is True


def test_deleting_a_project_deletes_its_tokens(tmp_path):
    manager = SDLCProjectManager(tmp_path / "projects")
    manager.save_project(project_with_token())

    assert manager.delete_project("p")

    assert manager.secrets.get("github:p:backend") is None


@pytest.fixture
def api(tmp_path, monkeypatch):
    projects = SDLCProjectManager(tmp_path / "data" / "projects")
    tasks = SDLCTaskManager(data_dir=tmp_path / "data" / "tasks")
    monkeypatch.setattr(main_module, "sdlc_project_manager", projects)
    monkeypatch.setattr(main_module, "sdlc_task_manager", tasks)
    return TestClient(main_module.app), projects, tasks


def test_api_never_returns_the_token(api):
    client, _, _ = api

    created = client.post("/api/sdlc/projects", json=json.loads(project_with_token().model_dump_json()))
    listed = client.get("/api/sdlc/projects")
    single = client.get("/api/sdlc/projects/p")

    for response in (created, listed, single):
        assert response.status_code == 200, response.text
        assert TOKEN not in response.text
    assert single.json()["agents"]["backend"]["github_config"]["token_saved"] is True


def test_github_actions_use_the_stored_token(api, monkeypatch):
    client, projects, tasks = api
    projects.save_project(project_with_token())
    base = TaskState(id="t", task_id="t", project_path=".", branch="tasks/t", status=RunStatus.queued, step="sdlc")
    asyncio.run(tasks.save_task(SDLCTask(base_task=base, title="Shop", project_config_id="p")))
    seen = []

    async def fake_api(method, path, token, body=None):
        seen.append(token)
        return 200, {"default_branch": "main", "permissions": {"push": True}}

    monkeypatch.setattr(sdlc_git, "github_api", fake_api)

    body = client.post("/api/sdlc/tasks/t/github/validate", json={"agent": "backend"}).json()

    assert body["status"] == "valid"
    assert seen == [TOKEN]
