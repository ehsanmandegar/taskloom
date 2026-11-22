"""Project builder: an idea becomes a project folder tree, prompts and Git repositories that are ready for tasks."""

import json
import shutil
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from backend.app import main as main_module
from backend.app import project_builder as pb
from backend.app import sdlc_git
from backend.app.models import RepositoryMode, RunStatus, SDLCTask, TaskState
from backend.app.services import SDLCProjectManager, SDLCTaskManager

from gitflow_helpers import git, run

IDEA = "An online bookshop API with a Python backend, a catalog, a cart, and a small web dashboard for the owner"


@pytest.fixture
def projects(tmp_path):
    return SDLCProjectManager(tmp_path / "data" / "projects")


def build(projects, tmp_path, refiner=None, **fields):
    request = pb.BuildRequest(idea=fields.pop("idea", IDEA), base_dir=str(tmp_path / "work"), use_ai=refiner is not None, **fields)
    return run(pb.build(request, {p.id for p in projects.list_projects()}, projects.save_project, refiner=refiner))


def test_idea_decides_stack_and_stages():
    assert pb.detect_stack("a Flask API for invoices") == "python"
    assert pb.detect_stack("a node express service") == "node"
    assert pb.detect_stack("a landing page for my cafe") == "web"
    assert pb.detect_stages(IDEA, "python") == ["analysis", "backend", "frontend", "qa"]
    assert pb.detect_stages("a Python script that cleans CSV files", "python") == ["analysis", "backend", "qa"]
    assert pb.detect_stages("sync orders with an n8n workflow automation", "python") == ["analysis", "backend", "n8n", "qa"]
    assert pb.detect_stages("a landing page", "web") == ["analysis", "frontend", "qa"]


def test_build_creates_folders_prompts_repositories_and_saves_the_project(projects, tmp_path):
    result = build(projects, tmp_path, name="Book Shop", autonomy="balanced")

    root = tmp_path / "work" / "book-shop"
    assert result["root"] == str(root) and result["files_written"] > 15
    saved = projects.get_project("book-shop")
    assert saved is not None and saved.name == "Book Shop"
    assert [s for s in saved.workflow.stages] == ["analysis", "backend", "frontend", "qa"]
    assert saved.agents["n8n"].enabled is False
    for stage in saved.workflow.stages:
        config = saved.agents[stage]
        folder = root / stage
        assert config.project_path == str(folder) and config.repository.mode == RepositoryMode.create
        assert config.knowledge_path == str(root / "knowledge")
        assert "Book Shop" in config.system_prompt and "bookshop API" in config.system_prompt
        assert (folder / "README.md").is_file() and (folder / "CLAUDE.md").read_text(encoding="utf-8").strip().endswith(config.system_prompt.strip())
        # a real Git repository, clean, with the initial commit on main and the sandbox base for task branches
        assert git(folder, "status", "--porcelain") == ""
        assert git(folder, "rev-parse", "main") == git(folder, "rev-parse", "sandbox")
        assert result["commits"][stage] == git(folder, "rev-parse", "--short", "HEAD")
    for name in ("PROJECT.md", "ARCHITECTURE.md", "CONVENTIONS.md", "DEFINITION_OF_DONE.md"):
        assert (root / "knowledge" / name).is_file()
    assert "bookshop" in (root / "analysis" / "docs" / "requirements.md").read_text(encoding="utf-8")
    assert not (root / "n8n").exists()


def test_the_generated_python_backend_passes_its_own_tests(projects, tmp_path):
    build(projects, tmp_path, name="Book Shop")
    folder = tmp_path / "work" / "book-shop" / "backend"
    done = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=folder, capture_output=True, text=True)
    assert done.returncode == 0, done.stdout + done.stderr
    assert projects.get_project("book-shop").agents["backend"].test_instructions == {"command": "python -m pytest -q"}


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_generated_frontend_and_node_backend_pass_their_own_tests(projects, tmp_path):
    build(projects, tmp_path, name="Node Shop", stack="node", idea="A node express service with a dashboard UI for orders")
    for stage in ("backend", "frontend"):
        done = subprocess.run(["node", "--test"], cwd=tmp_path / "work" / "node-shop" / stage, capture_output=True, text=True)
        assert done.returncode == 0, stage + done.stdout + done.stderr


def test_a_task_can_be_started_right_away(projects, tmp_path):
    """The point of the builder: no manual step stands between the new project and its first task branch."""
    build(projects, tmp_path, name="Book Shop")
    folder = tmp_path / "work" / "book-shop" / "backend"
    tasks = SDLCTaskManager(data_dir=tmp_path / "data" / "tasks")
    task_id = tasks.next_task_id("SDLC")
    task = SDLCTask(base_task=TaskState(id=task_id, task_id=task_id, project_path=str(folder), branch=task_id,
                                        status=RunStatus.queued, step="s"), project_config_id="book-shop")
    run(sdlc_git.prepare_task_branch(task, folder, "sandbox"))
    assert git(folder, "rev-parse", "--abbrev-ref", "HEAD").startswith(("SDLC-", "sdlc/"))


def test_autonomy_presets_keep_the_human_gates(projects, tmp_path):
    manual = pb.workflow_for("manual", ["analysis", "qa"])
    balanced = pb.workflow_for("balanced", ["analysis", "qa"])
    autopilot = pb.workflow_for("autopilot", ["analysis", "qa"])
    for flow in (manual, balanced, autopilot):
        assert flow.require_analysis_approval and flow.require_final_human_approval
    assert not manual.auto_final_approval and not manual.auto_analysis_approval
    assert balanced.auto_final_approval and balanced.auto_approval_max_risk == "low" and not balanced.auto_analysis_approval
    assert autopilot.auto_analysis_approval and autopilot.auto_release and autopilot.auto_retry_failed_stages == 2


def test_ai_enrichment_fills_description_requirements_and_stage_guidance(projects, tmp_path):
    async def refiner(prompt):
        assert IDEA in prompt
        return "Sure!\n" + json.dumps({
            "name": "Bookshop", "description": "A catalog and cart API for an online bookshop.",
            "requirements": ["Browse the catalog", "Add books to a cart", "<b>x</b>" * 100],
            "open_questions": ["Which payment provider?"], "architecture": "REST API plus a static dashboard.",
            "stage_notes": {"backend": "Use integer cents for prices.", "ghost": "ignored", "qa": 5}})

    result = build(projects, tmp_path, refiner=refiner)
    pid = result["project"]["id"]  # derived from the idea, so a preview and the real build agree

    assert result["ai_used"] and projects.get_project(pid).name == "Bookshop" and projects.get_project(pid).description == "A catalog and cart API for an online bookshop."
    backend = projects.get_project(pid).agents["backend"].system_prompt
    assert "Use integer cents for prices." in backend and "ghost" not in backend
    root = tmp_path / "work" / pid
    assert "Browse the catalog" in (root / "knowledge" / "PROJECT.md").read_text(encoding="utf-8")
    assert "Which payment provider?" in (root / "analysis" / "docs" / "open-questions.md").read_text(encoding="utf-8")
    assert "REST API plus a static dashboard." in (root / "knowledge" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    assert "Use integer cents" not in (root / "qa" / "CLAUDE.md").read_text(encoding="utf-8")


def test_stage_guidance_may_arrive_as_a_list_of_lines():
    clean = pb.sanitize_enrichment({"stage_notes": {"backend": ["Use cents", "", "Paginate lists"], "qa": "Check the cart", "frontend": 7}},
                                   ["analysis", "backend", "frontend", "qa"])
    assert clean["stage_notes"] == {"backend": "- Use cents\n- Paginate lists", "qa": "Check the cart"}
    assert pb.sanitize_enrichment("not a dict", ["backend"]) == {}


def test_an_unavailable_or_garbled_ai_falls_back_to_the_templates(projects, tmp_path):
    async def broken(prompt):
        raise RuntimeError("Ollama call failed: connection refused")

    async def garbled(prompt):
        return "I cannot do that"

    first = build(projects, tmp_path, refiner=broken, name="One")
    second = build(projects, tmp_path, refiner=garbled, name="Two")
    for result in (first, second):
        assert not result["ai_used"] and any("built-in templates" in note for note in result["notes"])
        assert result["files_written"] > 15


def test_a_derived_id_never_collides_but_a_typed_one_is_refused(projects, tmp_path):
    first = build(projects, tmp_path, name="Shop")
    second = build(projects, tmp_path, name="Shop")
    assert first["project"]["id"] == "shop" and second["project"]["id"] == "shop-2"
    with pytest.raises(pb.BuildError, match="already exists"):
        build(projects, tmp_path, id="shop")


def test_a_non_empty_destination_is_refused_and_left_untouched(projects, tmp_path):
    existing = tmp_path / "work" / "mine"
    existing.mkdir(parents=True)
    (existing / "keep.txt").write_text("precious", encoding="utf-8")
    with pytest.raises(pb.BuildError, match="not empty"):
        build(projects, tmp_path, id="mine")
    assert (existing / "keep.txt").read_text(encoding="utf-8") == "precious" and projects.get_project("mine") is None


def test_a_failed_build_leaves_no_half_project_behind(projects, tmp_path, monkeypatch):
    def failing_save(project):
        raise RuntimeError("disk full")

    request = pb.BuildRequest(idea=IDEA, base_dir=str(tmp_path / "work"), name="Doomed", use_ai=False)
    with pytest.raises(RuntimeError, match="disk full"):
        run(pb.build(request, set(), failing_save))
    assert not (tmp_path / "work" / "doomed").exists()


def test_templates_cannot_write_outside_their_folder(tmp_path):
    with pytest.raises(pb.BuildError, match="outside"):
        pb.write_tree(tmp_path / "stage", {"../escape.txt": "x"})
    assert not (tmp_path / "escape.txt").exists()


def test_preview_writes_nothing_and_reports_problems(projects, tmp_path):
    request = pb.BuildRequest(idea=IDEA, base_dir=str(tmp_path / "work"), name="Book Shop", preview=True)
    plan = pb.preview(request, set())
    assert plan["id"] == "book-shop" and [s["stage"] for s in plan["stages"]] == ["analysis", "backend", "frontend", "qa"]
    assert "app/main.py" in next(s for s in plan["stages"] if s["stage"] == "backend")["files"] and plan["problems"] == []
    assert not (tmp_path / "work").exists()


def test_request_validation():
    with pytest.raises(ValueError):
        pb.BuildRequest(idea="too short")
    with pytest.raises(ValueError):
        pb.BuildRequest(idea=IDEA, stages=["analysis", "launch-rockets"])
    assert pb.BuildRequest(idea="  " + IDEA + "  ").idea == IDEA


def test_a_persian_idea_gets_a_usable_id_and_name(projects, tmp_path):
    result = build(projects, tmp_path, idea="یک فروشگاه آنلاین کتاب با داشبورد برای مدیر فروشگاه می‌خواهم")
    assert result["project"]["id"] == "project" and "فروشگاه" in result["project"]["name"]
    assert "frontend" in result["folders"]


def test_endpoint_previews_then_builds(projects, tmp_path, monkeypatch):
    monkeypatch.setattr(main_module, "sdlc_project_manager", projects)
    client = TestClient(main_module.app)
    body = {"idea": IDEA, "name": "Book Shop", "base_dir": str(tmp_path / "work"), "use_ai": False}

    plan = client.post("/api/sdlc/project-builder", json={**body, "preview": True})
    assert plan.status_code == 200 and plan.json()["id"] == "book-shop" and not (tmp_path / "work").exists()

    built = client.post("/api/sdlc/project-builder", json=body)
    assert built.status_code == 200 and built.json()["project"]["id"] == "book-shop"
    assert client.get("/api/sdlc/projects/book-shop").status_code == 200

    again = client.post("/api/sdlc/project-builder", json={**body, "id": "book-shop"})
    assert again.status_code == 409 and "already exists" in again.json()["detail"]
    assert client.post("/api/sdlc/project-builder", json={**body, "idea": "short"}).status_code == 422
