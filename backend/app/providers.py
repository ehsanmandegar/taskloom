"""
Provider abstraction layer for multi-provider AI support.

This module provides a unified interface for interacting with different AI providers:
- Ollama (local LLM)
- Codex CLI
- Claude CLI

Each provider implements the same interface for:
- Checking availability and connection status
- Discovering available models
- Validating selected models
- Executing agent requests
- Returning normalized output
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
import asyncio
from datetime import datetime

from .models import ModelInfo, AgentResult, StageRunner, AgentType
from .config import OLLAMA_BASE_URL, OLLAMA_MODEL


class ProviderError(Exception):
    """Base exception for provider-related errors"""
    pass


class ProviderUnavailableError(ProviderError):
    """Raised when a provider is unavailable"""
    pass


class ModelUnavailableError(ProviderError):
    """Raised when a specific model is unavailable"""
    pass


class ProviderInterface(ABC):
    """Abstract base class for AI providers"""
    
    @abstractmethod
    async def check_availability(self) -> bool:
        """Check if the provider is available and reachable"""
        pass
    
    @abstractmethod
    async def get_available_models(self) -> List[ModelInfo]:
        """Get list of available models for this provider"""
        pass
    
    @abstractmethod
    async def validate_model(self, model_name: str) -> bool:
        """Validate that a specific model is available"""
        pass
    
    @abstractmethod
    async def execute_agent(
        self,
        stage: str,
        prompt: str,
        model_name: str,
        system_prompt: str = "",
        timeout_seconds: int = 300,
        **kwargs
    ) -> AgentResult:
        """Execute an agent request with the given model"""
        pass
    
    @abstractmethod
    def get_provider_id(self) -> str:
        """Get the provider identifier (e.g., 'ollama', 'codex', 'claude')"""
        pass
    
    @abstractmethod
    def get_display_name(self) -> str:
        """Get human-readable display name"""
        pass
    
    @abstractmethod
    def get_agent_type(self) -> AgentType:
        """Get the AgentType enum value for this provider"""
        pass
    
    @abstractmethod
    def get_runner_type(self) -> StageRunner:
        """Get the StageRunner enum value for this provider"""
        pass


class OllamaProvider(ProviderInterface):
    """Ollama provider implementation"""
    
    def __init__(self, base_url: str = OLLAMA_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.discovery_service = None
        # Lazy import to avoid circular dependencies
        from .services import OllamaDiscoveryService
        self.discovery_service = OllamaDiscoveryService(base_url)
    
    async def check_availability(self) -> bool:
        """Check if Ollama is reachable"""
        try:
            return await self.discovery_service.check_connection()
        except Exception:
            return False
    
    async def get_available_models(self) -> List[ModelInfo]:
        """Get list of available Ollama models"""
        try:
            return await self.discovery_service.list_models()
        except Exception as exc:
            raise ProviderError(f"Failed to fetch Ollama models: {exc}")
    
    async def validate_model(self, model_name: str) -> bool:
        """Validate that an Ollama model is available"""
        try:
            models = await self.get_available_models()
            return any(model.name == model_name for model in models)
        except Exception:
            return False
    
    async def execute_agent(
        self,
        stage: str,
        prompt: str,
        model_name: str,
        system_prompt: str = "",
        timeout_seconds: int = 300,
        **kwargs
    ) -> AgentResult:
        """Execute an agent request with Ollama"""
        try:
            # Import here to avoid circular dependencies
            from .services import OllamaAgentRunner
            runner = OllamaAgentRunner(base_url=self.base_url, model=model_name)
            
            # For now, we need the full context - this will be integrated with SDLC execution
            # We'll need to adapt this to work with existing OllamaAgentRunner
            raise NotImplementedError("Ollama agent execution needs integration with existing SDLC runner")
            
        except Exception as exc:
            raise ProviderError(f"Ollama execution failed: {exc}")
    
    def get_provider_id(self) -> str:
        return "ollama"
    
    def get_display_name(self) -> str:
        return "Ollama (Local LLM)"
    
    def get_agent_type(self) -> AgentType:
        return AgentType.ollama
    
    def get_runner_type(self) -> StageRunner:
        return StageRunner.ollama


class CodexProvider(ProviderInterface):
    """Codex CLI provider implementation"""
    
    def __init__(self):
        self.executable = "codex"
    
    async def check_availability(self) -> bool:
        """Check if Codex CLI is installed"""
        import shutil
        return shutil.which(self.executable) is not None
    
    async def get_available_models(self) -> List[ModelInfo]:
        """Get available Codex models from the App Server"""
        try:
            from .services import codex_account_status
            status = await codex_account_status(timeout=15)
            raw_models = status.get("models", [])
            
            if raw_models:
                models = []
                for m in raw_models:
                    model_id = m.get("model") or m.get("id") or ""
                    if not model_id:
                        continue
                    models.append(ModelInfo(
                        name=model_id,
                        family="OpenAI",
                        parameters="",
                        description=m.get("displayName") or model_id,
                        supports_tool_calls=True,
                    ))
                return models
        except Exception:
            pass
        
        # Fallback: return a minimal known list when the App Server is unavailable
        return [
            ModelInfo(name="codex", family="OpenAI", parameters="", description="Default Codex model"),
        ]
    
    async def validate_model(self, model_name: str) -> bool:
        """Validate a Codex model against the App Server catalog"""
        try:
            models = await self.get_available_models()
            return any(m.name == model_name for m in models)
        except Exception:
            return False
    
    async def execute_agent(
        self,
        stage: str,
        prompt: str,
        model_name: str,
        system_prompt: str = "",
        timeout_seconds: int = 3600,
        **kwargs
    ) -> AgentResult:
        """Codex execution is handled by the existing CLI runner in sdlc_runner.py"""
        raise NotImplementedError("Codex agent execution is handled by run_cli_stage in sdlc_runner.py")
    
    def get_provider_id(self) -> str:
        return "codex"
    
    def get_display_name(self) -> str:
        return "Codex CLI"
    
    def get_agent_type(self) -> AgentType:
        return AgentType.codex
    
    def get_runner_type(self) -> StageRunner:
        return StageRunner.codex


class ClaudeProvider(ProviderInterface):
    """Claude CLI provider implementation"""
    
    # Known Claude model aliases supported by the CLI `--model` flag.
    # Claude CLI does not provide a machine-readable catalog endpoint, so we
    # maintain a validated list of aliases that Claude Code accepts.
    # Source: https://docs.anthropic.com/en/docs/about-claude/models/overview
    KNOWN_MODELS = [
        ModelInfo(name="claude",          family="Anthropic", description="Claude (default, latest alias)"),
        ModelInfo(name="claude-opus-4-5",  family="Anthropic", description="Claude Opus 4.5"),
        ModelInfo(name="claude-sonnet-4-5",family="Anthropic", description="Claude Sonnet 4.5"),
        ModelInfo(name="claude-haiku-4-5", family="Anthropic", description="Claude Haiku 4.5"),
        ModelInfo(name="claude-opus-4",   family="Anthropic", description="Claude Opus 4"),
        ModelInfo(name="claude-sonnet-4", family="Anthropic", description="Claude Sonnet 4"),
        ModelInfo(name="claude-3-7-sonnet-latest", family="Anthropic", description="Claude 3.7 Sonnet (latest)"),
        ModelInfo(name="claude-3-5-haiku-latest",  family="Anthropic", description="Claude 3.5 Haiku (latest)"),
    ]
    
    def __init__(self):
        self.executable = "claude"
    
    async def check_availability(self) -> bool:
        """Check if Claude CLI is installed"""
        import shutil
        return shutil.which(self.executable) is not None
    
    async def get_available_models(self) -> List[ModelInfo]:
        """Return validated Claude model aliases.
        
        The Claude CLI does not expose a local model catalog, so we return the
        known list. Users may also type any model ID directly in the UI.
        """
        return list(self.KNOWN_MODELS)
    
    async def validate_model(self, model_name: str) -> bool:
        """Accept any non-empty string — the CLI will reject unknown models at runtime."""
        return bool(model_name and model_name.strip())
    
    async def execute_agent(
        self,
        stage: str,
        prompt: str,
        model_name: str,
        system_prompt: str = "",
        timeout_seconds: int = 3600,
        **kwargs
    ) -> AgentResult:
        """Claude execution is handled by the existing CLI runner in sdlc_runner.py"""
        raise NotImplementedError("Claude agent execution is handled by run_cli_stage in sdlc_runner.py")
    
    def get_provider_id(self) -> str:
        return "claude"
    
    def get_display_name(self) -> str:
        return "Claude CLI"
    
    def get_agent_type(self) -> AgentType:
        return AgentType.claude
    
    def get_runner_type(self) -> StageRunner:
        return StageRunner.claude


class ProviderRegistry:
    """Registry for managing available providers"""
    
    def __init__(self):
        self._providers: Dict[str, ProviderInterface] = {}
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize all available providers"""
        self._providers["ollama"] = OllamaProvider()
        self._providers["codex"] = CodexProvider()
        self._providers["claude"] = ClaudeProvider()
    
    def get_provider(self, provider_id: str) -> Optional[ProviderInterface]:
        """Get a provider by ID"""
        return self._providers.get(provider_id)
    
    def get_all_providers(self) -> List[ProviderInterface]:
        """Get all registered providers"""
        return list(self._providers.values())
    
    async def get_available_providers(self) -> List[Dict[str, Any]]:
        """Get list of all providers with their availability status"""
        providers_info = []
        
        for provider in self.get_all_providers():
            try:
                available = await provider.check_availability()
                providers_info.append({
                    "id": provider.get_provider_id(),
                    "name": provider.get_display_name(),
                    "available": available,
                    "agent_type": provider.get_agent_type().value,
                    "runner_type": provider.get_runner_type().value,
                })
            except Exception:
                providers_info.append({
                    "id": provider.get_provider_id(),
                    "name": provider.get_display_name(),
                    "available": False,
                    "agent_type": provider.get_agent_type().value,
                    "runner_type": provider.get_runner_type().value,
                    "error": "Failed to check availability",
                })
        
        return providers_info
    
    async def get_provider_models(self, provider_id: str) -> List[ModelInfo]:
        """Get available models for a specific provider"""
        provider = self.get_provider(provider_id)
        if not provider:
            raise ProviderError(f"Provider '{provider_id}' not found")
        
        if not await provider.check_availability():
            raise ProviderUnavailableError(f"Provider '{provider_id}' is unavailable")
        
        try:
            return await provider.get_available_models()
        except Exception as exc:
            raise ProviderError(f"Failed to get models for provider '{provider_id}': {exc}")


# Global provider registry instance
provider_registry = ProviderRegistry()