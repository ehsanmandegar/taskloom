"""
Tests for multi-provider AI selection system.

All external AI services (Ollama, Codex, Claude) are mocked — no live
server or paid account is required to run this suite.
"""
from __future__ import annotations

import pytest

from backend.app.models import (
    AgentConfig,
    ProjectAISettings,
    SDLCProjectConfig,
    StageProviderConfig,
    StageRunner,
)
from backend.app.services import ProviderResolutionService


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def make_project(
    *,
    default_provider: str = "ollama",
    default_model: str = "qwen3.5:0.8b",
    stage_providers: dict | None = None,
    ollama_endpoint: str = "http://localhost:11434",
) -> SDLCProjectConfig:
    return SDLCProjectConfig(
        id="test-project",
        name="Test Project",
        ai_settings=ProjectAISettings(
            default_provider=default_provider,
            default_model=default_model,
            stage_providers=stage_providers or {},
            ollama_endpoint=ollama_endpoint,
        ),
    )


def make_stage_config(provider: str, model: str) -> StageProviderConfig:
    return StageProviderConfig(provider=provider, model=model, inherit_from_project=False)


# ---------------------------------------------------------------------------
# ProjectAISettings — unit tests
# ---------------------------------------------------------------------------

class TestProjectAISettings:
    def test_default_provider_returned_for_stage_without_override(self):
        project = make_project(default_provider="ollama", default_model="qwen3.5:0.8b")
        prov, model, inherited = project.ai_settings.get_provider_for_stage("backend")
        assert prov == "ollama"
        assert model == "qwen3.5:0.8b"
        assert inherited is True

    def test_stage_override_returned_when_set(self):
        project = make_project(
            stage_providers={"backend": make_stage_config("codex", "codex-advanced")}
        )
        prov, model, inherited = project.ai_settings.get_provider_for_stage("backend")
        assert prov == "codex"
        assert model == "codex-advanced"
        assert inherited is False

    def test_different_stages_independent(self):
        project = make_project(
            stage_providers={
                "backend": make_stage_config("codex", "codex"),
                "frontend": make_stage_config("claude", "claude-sonnet-4"),
            }
        )
        b_prov, _, _ = project.ai_settings.get_provider_for_stage("backend")
        f_prov, _, _ = project.ai_settings.get_provider_for_stage("frontend")
        assert b_prov == "codex"
        assert f_prov == "claude"

    def test_inherit_flag_means_project_defaults_used(self):
        # Stage config exists but inherit_from_project is True → use project defaults
        project = make_project(
            default_provider="ollama",
            default_model="qwen3.5:0.8b",
            stage_providers={
                "backend": StageProviderConfig(
                    provider="codex", model="codex", inherit_from_project=True
                )
            },
        )
        prov, model, inherited = project.ai_settings.get_provider_for_stage("backend")
        assert prov == "ollama"
        assert model == "qwen3.5:0.8b"
        assert inherited is True

    def test_get_effective_config_shows_inheritance(self):
        project = make_project(default_provider="ollama", default_model="qwen3.5:0.8b")
        config = project.ai_settings.get_effective_config_for_stage("qa")
        assert config["provider"] == "ollama"
        assert config["inherited"] is True
        assert config["stage_has_override"] is False

    def test_get_effective_config_shows_override(self):
        project = make_project(
            stage_providers={"qa": make_stage_config("claude", "claude-haiku-4-5")}
        )
        config = project.ai_settings.get_effective_config_for_stage("qa")
        assert config["provider"] == "claude"
        assert config["inherited"] is False
        assert config["stage_has_override"] is True

    def test_invalid_provider_raises(self):
        import pydantic
        with pytest.raises((ValueError, pydantic.ValidationError)):
            ProjectAISettings(default_provider="unknown-provider")


# ---------------------------------------------------------------------------
# StageProviderConfig — unit tests
# ---------------------------------------------------------------------------

class TestStageProviderConfig:
    def test_valid_providers_accepted(self):
        for p in ("ollama", "codex", "claude"):
            cfg = StageProviderConfig(provider=p, model="some-model")
            assert cfg.provider == p

    def test_invalid_provider_raises(self):
        import pydantic
        with pytest.raises((ValueError, pydantic.ValidationError)):
            StageProviderConfig(provider="gpt-99", model="x")

    def test_model_stripped(self):
        cfg = StageProviderConfig(provider="ollama", model="  qwen3.5:0.8b  ")
        assert cfg.model == "qwen3.5:0.8b"


# ---------------------------------------------------------------------------
# AgentConfig.get_effective_provider — unit tests
# ---------------------------------------------------------------------------

class TestAgentConfigProviderOverride:
    def test_no_override_uses_project_defaults(self):
        project = make_project(default_provider="ollama", default_model="qwen3.5:0.8b")
        agent = AgentConfig()
        prov, model, overridden = agent.get_effective_provider(project.ai_settings, "backend")
        assert prov == "ollama"
        assert model == "qwen3.5:0.8b"
        assert overridden is False

    def test_provider_override_takes_precedence(self):
        project = make_project(default_provider="ollama", default_model="qwen3.5:0.8b")
        agent = AgentConfig(provider_override="codex", model_override="codex")
        prov, model, overridden = agent.get_effective_provider(project.ai_settings, "backend")
        assert prov == "codex"
        assert overridden is True

    def test_model_override_uses_project_default_when_empty(self):
        project = make_project(default_provider="ollama", default_model="qwen3.5:0.8b")
        # provider overridden but model left blank → model comes from project default
        agent = AgentConfig(provider_override="ollama", model_override="")
        prov, model, overridden = agent.get_effective_provider(project.ai_settings, "backend")
        assert prov == "ollama"
        # model falls back to project default
        assert model == "qwen3.5:0.8b"


# ---------------------------------------------------------------------------
# ProviderResolutionService — unit tests
# ---------------------------------------------------------------------------

class TestProviderResolutionService:
    def test_no_override_returns_project_defaults(self):
        project = make_project(default_provider="ollama", default_model="qwen3.5:0.8b")
        resolver = ProviderResolutionService()
        prov, model, overridden = resolver.resolve_provider_for_stage("analysis", project)
        assert prov == "ollama"
        assert model == "qwen3.5:0.8b"
        assert overridden is False

    def test_stage_override_in_ai_settings(self):
        project = make_project(
            stage_providers={"backend": make_stage_config("codex", "codex")}
        )
        resolver = ProviderResolutionService()
        prov, model, overridden = resolver.resolve_provider_for_stage("backend", project)
        assert prov == "codex"
        assert overridden is True

    def test_task_override_highest_priority(self):
        project = make_project(
            default_provider="ollama",
            stage_providers={"backend": make_stage_config("codex", "codex")},
        )
        resolver = ProviderResolutionService()
        prov, model, overridden = resolver.resolve_provider_for_stage(
            "backend", project,
            task_override_provider="claude",
            task_override_model="claude-haiku-4-5",
        )
        assert prov == "claude"
        assert model == "claude-haiku-4-5"
        assert overridden is True

    def test_different_stages_do_not_affect_each_other(self):
        project = make_project(
            default_provider="ollama",
            stage_providers={"backend": make_stage_config("codex", "codex")},
        )
        resolver = ProviderResolutionService()
        b_prov, _, _ = resolver.resolve_provider_for_stage("backend", project)
        a_prov, _, _ = resolver.resolve_provider_for_stage("analysis", project)
        assert b_prov == "codex"
        assert a_prov == "ollama"


# ---------------------------------------------------------------------------
# Provider availability checks (mocked)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_ollama_provider_available_when_connection_ok(monkeypatch):
    from backend.app.providers import OllamaProvider

    class MockDiscovery:
        async def check_connection(self):
            return True

    provider = OllamaProvider.__new__(OllamaProvider)
    provider.base_url = "http://localhost:11434"
    provider.discovery_service = MockDiscovery()

    assert await provider.check_availability() is True


@pytest.mark.anyio
async def test_ollama_provider_unavailable_when_connection_fails(monkeypatch):
    from backend.app.providers import OllamaProvider

    class MockDiscovery:
        async def check_connection(self):
            raise ConnectionRefusedError("not running")

    provider = OllamaProvider.__new__(OllamaProvider)
    provider.base_url = "http://localhost:11434"
    provider.discovery_service = MockDiscovery()

    assert await provider.check_availability() is False


@pytest.mark.anyio
async def test_ollama_model_discovery(monkeypatch):
    from backend.app.models import ModelInfo
    from backend.app.providers import OllamaProvider

    expected = [
        ModelInfo(name="qwen3.5:0.8b", family="Qwen"),
        ModelInfo(name="llama3.1:8b", family="Llama"),
    ]

    class MockDiscovery:
        async def list_models(self):
            return expected

    provider = OllamaProvider.__new__(OllamaProvider)
    provider.base_url = "http://localhost:11434"
    provider.discovery_service = MockDiscovery()

    models = await provider.get_available_models()
    assert len(models) == 2
    assert models[0].name == "qwen3.5:0.8b"


@pytest.mark.anyio
async def test_ollama_unavailable_raises_provider_error(monkeypatch):
    from backend.app.providers import OllamaProvider, ProviderError

    class MockDiscovery:
        async def list_models(self):
            raise RuntimeError("connection refused")
        async def check_connection(self):
            return False

    provider = OllamaProvider.__new__(OllamaProvider)
    provider.base_url = "http://localhost:11434"
    provider.discovery_service = MockDiscovery()

    with pytest.raises(ProviderError):
        await provider.get_available_models()


@pytest.mark.anyio
async def test_codex_provider_available_when_binary_present(tmp_path, monkeypatch):
    import shutil
    from backend.app.providers import CodexProvider

    provider = CodexProvider()
    # Mock shutil.which to return a path
    monkeypatch.setattr(shutil, "which", lambda name: str(tmp_path / name) if name == "codex" else None)
    assert await provider.check_availability() is True


@pytest.mark.anyio
async def test_codex_provider_unavailable_when_binary_missing(monkeypatch):
    import shutil
    from backend.app.providers import CodexProvider

    provider = CodexProvider()
    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert await provider.check_availability() is False


@pytest.mark.anyio
async def test_codex_model_discovery_uses_app_server(monkeypatch):
    from backend.app.providers import CodexProvider
    import backend.app.services as svc

    async def mock_status(timeout=15):
        return {
            "models": [
                {"id": "o4-mini", "model": "o4-mini", "displayName": "o4-mini", "isDefault": True},
                {"id": "o3", "model": "o3", "displayName": "o3", "isDefault": False},
            ]
        }

    monkeypatch.setattr(svc, "codex_account_status", mock_status)
    provider = CodexProvider()
    models = await provider.get_available_models()
    assert any(m.name == "o4-mini" for m in models)
    assert any(m.name == "o3" for m in models)


@pytest.mark.anyio
async def test_codex_model_discovery_falls_back_when_server_unavailable(monkeypatch):
    from backend.app.providers import CodexProvider
    import backend.app.services as svc

    async def mock_status(timeout=15):
        raise RuntimeError("Codex App Server not available")

    monkeypatch.setattr(svc, "codex_account_status", mock_status)
    provider = CodexProvider()
    models = await provider.get_available_models()
    # Fallback must return at least one model
    assert len(models) >= 1


@pytest.mark.anyio
async def test_claude_provider_returns_known_models():
    from backend.app.providers import ClaudeProvider
    provider = ClaudeProvider()
    models = await provider.get_available_models()
    names = [m.name for m in models]
    assert "claude" in names
    assert len(models) >= 4


@pytest.mark.anyio
async def test_claude_validate_model_accepts_any_nonempty_string():
    from backend.app.providers import ClaudeProvider
    provider = ClaudeProvider()
    assert await provider.validate_model("claude-custom-xyz") is True
    assert await provider.validate_model("") is False


# ---------------------------------------------------------------------------
# ProviderResolutionService.validate_provider_availability (mocked)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_validate_provider_unavailable_returns_false(monkeypatch):
    from backend.app.providers import OllamaProvider, ProviderRegistry

    class UnavailableOllama(OllamaProvider):
        async def check_availability(self):
            return False

    registry = ProviderRegistry.__new__(ProviderRegistry)
    registry._providers = {"ollama": UnavailableOllama.__new__(UnavailableOllama)}

    resolver = ProviderResolutionService(provider_registry=registry)
    ok, msg = await resolver.validate_provider_availability("ollama", "qwen3.5:0.8b")
    assert ok is False
    assert "unavailable" in msg.lower()


@pytest.mark.anyio
async def test_validate_unknown_provider_returns_false():
    from backend.app.providers import ProviderRegistry
    registry = ProviderRegistry.__new__(ProviderRegistry)
    registry._providers = {}
    resolver = ProviderResolutionService(provider_registry=registry)
    ok, msg = await resolver.validate_provider_availability("unknown", "some-model")
    assert ok is False


# ---------------------------------------------------------------------------
# Backward compatibility: legacy runner field
# ---------------------------------------------------------------------------

class TestLegacyRunnerField:
    def test_legacy_ollama_runner_still_resolves(self):
        """Projects that set runner=ollama explicitly must keep working."""
        project = make_project()
        # Simulate a legacy agent config (no new provider fields)
        agent = AgentConfig(runner=StageRunner.ollama)
        prov, model, _ = agent.get_effective_provider(project.ai_settings, "backend")
        # Falls through to project default because provider_override is empty
        assert prov == "ollama"

    def test_legacy_codex_runner_field_respected_in_execute_stage(self, monkeypatch):
        """If AgentConfig.runner == codex and no new override, execute_stage must use Codex."""
        import asyncio
        from pathlib import Path
        from backend.app import sdlc_runner
        from backend.app.models import AgentConfig, RunStatus, SDLCTask, StageRunner, TaskState

        base = TaskState(
            id="t1", task_id="t1", project_path=".", branch="tasks/t1",
            status=RunStatus.queued, step="sdlc",
        )
        task = SDLCTask(base_task=base, current_stage="backend", current_agent="backend", project_config_id="p")

        project = make_project()
        project.agents["backend"] = AgentConfig(runner=StageRunner.codex)

        called_with = {}

        async def fake_cli(stage, t, proj, cfg, runner, pid_file, repo_token, persist_project, model_name=None):
            called_with["runner"] = runner
            from backend.app.models import AgentResult
            return AgentResult(agent=stage, status="completed")

        monkeypatch.setattr(sdlc_runner, "run_cli_stage", fake_cli)

        asyncio.run(sdlc_runner.execute_stage("backend", task, project))
        assert called_with.get("runner") == StageRunner.codex
