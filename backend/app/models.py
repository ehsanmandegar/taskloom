from enum import Enum
import re

from pydantic import BaseModel, Field, field_validator


class RunStatus(str, Enum):
    queued = "queued"
    running = "running"
    testing = "testing"
    stopped = "stopped"
    passed = "passed"
    failed = "failed"
    blocked = "blocked"


class McpFailureMode(str, Enum):
    blocked = "blocked"
    warning = "warning"


class McpStatus(str, Enum):
    not_configured = "not_configured"
    checking = "checking"
    ready = "ready"
    warning = "warning"
    blocked = "blocked"


class GitProvider(str, Enum):
    auto = "auto"
    gitlab = "gitlab"
    github = "github"


def valid_branch_name(value: str) -> str:
    value = value.strip()
    invalid_part = any(part in {"", ".", ".."} for part in value.split("/"))
    if (
        not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", value)
        or invalid_part
        or ".." in value
        or value.endswith((".", "/", ".lock"))
    ):
        raise ValueError("Branch name contains characters or sequences Git does not allow")
    return value


class TaskRequest(BaseModel):
    project_path: str = Field(min_length=1)
    guide_paths: list[str] = Field(default_factory=list)
    task_id: str = Field(min_length=2, max_length=80)
    request: str = Field(min_length=5, max_length=20_000)
    base_branch: str = Field(default="main", min_length=1, max_length=240)
    test_command: str | None = Field(default=None, max_length=500)
    mcp_server_name: str | None = Field(default=None, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    mcp_failure_mode: McpFailureMode = McpFailureMode.warning
    git_provider: GitProvider = GitProvider.auto

    @field_validator("task_id")
    @classmethod
    def valid_task_id(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", value):
            raise ValueError("Task ID may only contain letters, numbers, dot, dash and underscore")
        return value

    @field_validator("base_branch")
    @classmethod
    def clean_base_branch(cls, value: str) -> str:
        return valid_branch_name(value)


class ProjectProfile(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    project_path: str = Field(min_length=1)
    guide_paths: list[str] = Field(default_factory=list)
    base_branch: str = Field(default="main", min_length=1, max_length=240)
    test_command: str | None = Field(default=None, max_length=500)
    mcp_server_name: str | None = Field(default=None, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    mcp_failure_mode: McpFailureMode = McpFailureMode.warning
    git_provider: GitProvider = GitProvider.auto

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Profile name cannot be empty")
        return value

    @field_validator("base_branch")
    @classmethod
    def clean_base_branch(cls, value: str) -> str:
        return valid_branch_name(value)


class ProjectDefaults(BaseModel):
    project_path: str
    guide_paths: list[str] = Field(default_factory=list)
    base_branch: str = "main"
    test_command: str | None = None
    mcp_server_name: str | None = None
    mcp_failure_mode: McpFailureMode = McpFailureMode.warning
    git_provider: GitProvider = GitProvider.gitlab


class CommitRequest(BaseModel):
    message: str = Field(min_length=3, max_length=200)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)


class ChatMessage(BaseModel):
    role: str
    content: str


class TaskState(BaseModel):
    id: str
    task_id: str
    project_path: str
    branch: str
    base_branch: str = "main"
    test_command: str | None = None
    mcp_server_name: str | None = None
    mcp_failure_mode: McpFailureMode = McpFailureMode.warning
    mcp_status: McpStatus = McpStatus.not_configured
    mcp_message: str = ""
    git_provider: GitProvider = GitProvider.auto
    status: RunStatus
    step: str
    logs: list[str] = Field(default_factory=list)
    live_output: str = ""
    live_response: str = ""
    summary: str = ""
    diff: str = ""
    changed_files: list[str] = Field(default_factory=list)
    test_output: str = ""
    commit_message: str = ""
    error: str | None = None
    committed: bool = False
    pushed: bool = False
    merge_request_url: str = ""
    codex_thread_id: str = ""
    messages: list[ChatMessage] = Field(default_factory=list)
