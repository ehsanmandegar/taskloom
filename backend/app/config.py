"""Runtime configuration for the Taskloom backend, read from environment variables."""

import os

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", os.getenv("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:0.8b")
