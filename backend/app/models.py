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
    session_name: str | None = Field(default=None, max_length=120)
    request: str = Field(min_length=5, max_length=20_000)
    base_branch: str = Field(default="main", min_length=1, max_length=240)
    test_command: str | None = Field(default=None, max_length=500)
    test_working_directory: str | None = Field(default=None, max_length=500)
    test_setup_enabled: bool = False
    auto_commit: bool = False
    auto_generate_commit_message: bool = False
    auto_push: bool = False
    auto_merge_request: bool = False
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

    @field_validator("session_name")
    @classmethod
    def clean_session_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("base_branch")
    @classmethod
    def clean_base_branch(cls, value: str) -> str:
        return valid_branch_name(value)

    @field_validator("test_working_directory")
    @classmethod
    def clean_test_working_directory(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ProjectProfile(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    project_path: str = Field(min_length=1)
    guide_paths: list[str] = Field(default_factory=list)
    base_branch: str = Field(default="main", min_length=1, max_length=240)
    test_command: str | None = Field(default=None, max_length=500)
    test_working_directory: str | None = Field(default=None, max_length=500)
    test_setup_enabled: bool = False
    auto_commit: bool = False
    auto_generate_commit_message: bool = False
    auto_push: bool = False
    auto_merge_request: bool = False
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

    @field_validator("test_working_directory")
    @classmethod
    def clean_test_working_directory(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ProjectDefaults(BaseModel):
    project_path: str
    guide_paths: list[str] = Field(default_factory=list)
    base_branch: str = "main"
    test_command: str | None = None
    test_working_directory: str | None = None
    test_setup_enabled: bool = False
    auto_commit: bool = False
    auto_generate_commit_message: bool = False
    auto_push: bool = False
    auto_merge_request: bool = False
    mcp_server_name: str | None = None
    mcp_failure_mode: McpFailureMode = McpFailureMode.warning
    git_provider: GitProvider = GitProvider.gitlab


class CommitRequest(BaseModel):
    message: str = Field(min_length=3, max_length=200)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)


class TodoRequest(BaseModel):
    content: str = Field(min_length=1, max_length=20_000)
    project_path: str = Field(default="", max_length=2_000)
    branch: str = Field(default="", max_length=240)
    session_id: str = Field(default="", max_length=120)

    @field_validator("content")
    @classmethod
    def clean_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Todo cannot be empty")
        return value

    @field_validator("project_path", "branch", "session_id")
    @classmethod
    def clean_target(cls, value: str) -> str:
        return value.strip()


class RenameTaskRequest(BaseModel):
    session_name: str = Field(min_length=1, max_length=120)

    @field_validator("session_name")
    @classmethod
    def clean_session_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Session name cannot be empty")
        return value


class TestSetupRequest(BaseModel):
    project_path: str = Field(min_length=1)
    confirm_test_database: bool = False


class BranchSwitchRequest(BaseModel):
    project_path: str = Field(min_length=1)
    branch: str = Field(min_length=1, max_length=240)

    @field_validator("branch")
    @classmethod
    def clean_branch(cls, value: str) -> str:
        return valid_branch_name(value)


class ChatMessage(BaseModel):
    role: str
    content: str


class TodoItem(BaseModel):
    id: str
    content: str
    project_path: str = ""
    branch: str = ""
    session_id: str = ""
    order: int = 0
    status: str = "pending"
    error: str = ""


class TaskState(BaseModel):
    id: str
    task_id: str
    session_name: str = ""
    project_path: str
    branch: str
    base_branch: str = "main"
    guide_paths: list[str] = Field(default_factory=list)
    test_command: str | None = None
    test_working_directory: str | None = None
    test_setup_enabled: bool = False
    auto_commit: bool = False
    auto_generate_commit_message: bool = False
    auto_push: bool = False
    auto_merge_request: bool = False
    test_setup_output: str = ""
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
    todos: list[TodoItem] = Field(default_factory=list)
