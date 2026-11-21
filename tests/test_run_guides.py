import json
import sys
import time

from fastapi.testclient import TestClient

from backend.app import main as main_module, run_guides, run_processes
from backend.app.models import AgentConfig, SDLCProjectConfig
from backend.app.services import SDLCProjectManager

client = TestClient(main_module.app)


def setup_project(tmp_path, monkeypatch):
    manager = SDLCProjectManager(data_dir=tmp_path / "projects")
    folder = tmp_path / "backend"
    folder.mkdir()
    manager.save_project(SDLCProjectConfig(id="p", name="P", agents={"backend": AgentConfig(project_path=str(folder))}))
    monkeypatch.setattr(main_module, "sdlc_project_manager", manager)
    return folder


def test_guides_come_back_as_templates_then_save_to_the_stage_folder(tmp_path, monkeypatch):
    folder = setup_project(tmp_path, monkeypatch)

    data = client.get("/api/sdlc/projects/p/agents/backend/run-guide").json()
    assert data["guides"]["test"]["exists"] is False
    assert "How to run the backend tests" in data["guides"]["test"]["content"]

    assert client.put("/api/sdlc/projects/p/agents/backend/run-guide/real", json={"content": "# go\nuvicorn x"}).status_code == 200
    assert (folder / "RUN_REAL.md").read_text(encoding="utf-8") == "# go\nuvicorn x"
    assert client.get("/api/sdlc/projects/p/agents/backend/run-guide").json()["guides"]["real"]["exists"] is True
    assert client.put("/api/sdlc/projects/p/agents/backend/run-guide/other", json={"content": "x"}).status_code == 400


def test_start_with_mode_needs_a_saved_guide(tmp_path, monkeypatch):
    setup_project(tmp_path, monkeypatch)
    response = client.post("/api/sdlc/projects/p/agents/backend/run/start", json={"mode": "test"})
    assert response.status_code == 400
    assert "RUN_TEST.md" in response.json()["detail"]


def test_agent_start_passes_guide_prompt_and_stop_kills_recorded_servers(tmp_path, monkeypatch):
    folder = setup_project(tmp_path, monkeypatch)
    monkeypatch.chdir(tmp_path)
    (folder / "RUN_REAL.md").write_text("# start it", encoding="utf-8")
    # A fake "claude": echoes the prompt it got on stdin as a stream-json assistant event.
    fake = tmp_path / "fake_claude.py"
    fake.write_text(
        "import sys, json\nprompt = sys.stdin.read()\n"
        "print(json.dumps({'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': prompt[:60]}]}}))\n",
        encoding="utf-8")
    real_popen = run_processes.subprocess.Popen
    monkeypatch.setattr(main_module, "agent_executable", lambda _: sys.executable)
    monkeypatch.setattr(run_processes.subprocess, "Popen",
                        lambda args, **kw: real_popen([sys.executable, str(fake)], **kw))

    status = client.post("/api/sdlc/projects/p/agents/backend/run/start", json={"mode": "real"}).json()
    assert status["mode"] == "real"
    for _ in range(50):
        status = client.get("/api/sdlc/projects/p/agents/backend/run").json()
        if status["exit_code"] is not None:
            break
        time.sleep(0.1)
    time.sleep(0.2)
    status = client.get("/api/sdlc/projects/p/agents/backend/run").json()
    assert status["exit_code"] == 0
    assert "backend part" in status["log"]
    assert status["running"] is False
    run_processes.stop_all()


def test_format_claude_event():
    line = json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {"command": "npm test"}}]}})
    assert run_processes.format_claude_event(line) == "$ Bash: npm test"
    assert run_processes.format_claude_event(json.dumps({"type": "system"})) == ""
    assert run_guides.GUIDE_FILES["test"] == "RUN_TEST.md"
