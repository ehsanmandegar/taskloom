from enum import Enum
from pathlib import Path
from datetime import datetime, timezone
import re

from pydantic import BaseModel, Field, field_validator, model_validator


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


class AgentType(str, Enum):
    codex = "codex"
    claude = "claude"


class TaskRole(str, Enum):
    analyst = "analyst"
    developer = "developer"
    tester = "tester"
    product_owner = "product_owner"


class RoleKnowledgeSettings(BaseModel):
    analyst: str = Field(default="", max_length=2000)
    developer: str = Field(default="", max_length=2000)
    tester: str = Field(default="", max_length=2000)
    product_owner: str = Field(default="", max_length=2000)

    @field_validator("analyst", "developer", "tester", "product_owner")
    @classmethod
    def clean_path(cls, value: str) -> str:
        return value.strip()


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
    confirm_dirty_worktree: bool = False
    auto_commit: bool = False
    auto_generate_commit_message: bool = False
    auto_push: bool = False
    auto_merge_request: bool = False
    mcp_server_name: str | None = Field(default=None, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    mcp_failure_mode: McpFailureMode = McpFailureMode.warning
    git_provider: GitProvider = GitProvider.auto
    agent_type: AgentType = AgentType.codex
    role: TaskRole = TaskRole.analyst

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
    agent_type: AgentType = AgentType.codex

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
    agent_type: AgentType = AgentType.codex


class CommitRequest(BaseModel):
    message: str = Field(min_length=3, max_length=200)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)


class TodoRequest(BaseModel):
    content: str = Field(min_length=1, max_length=20_000)
    project_path: str = Field(default="", max_length=2_000)
    branch: str = Field(default="", max_length=240)
    session_id: str = Field(default="", max_length=120)
    scheduled_for: datetime | None = None

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

    @field_validator("scheduled_for")
    @classmethod
    def normalize_scheduled_for(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Scheduled time must include a timezone")
        return value.astimezone(timezone.utc)


class RenameTaskRequest(BaseModel):
    session_name: str = Field(min_length=1, max_length=120)

    @field_validator("session_name")
    @classmethod
    def clean_session_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Session name cannot be empty")
        return value


class TaskRoleRequest(BaseModel):
    role: TaskRole


class TestSetupRequest(BaseModel):
    project_path: str = Field(min_length=1)
    confirm_test_database: bool = False


class BranchSwitchRequest(BaseModel):
    project_path: str = Field(min_length=1)
    branch: str = Field(min_length=1, max_length=240)
    base_branch: str = Field(default="main", min_length=1, max_length=240)

    @field_validator("branch", "base_branch")
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
    scheduled_for: datetime | None = None

    @field_validator("scheduled_for")
    @classmethod
    def normalize_scheduled_for(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Scheduled time must include a timezone")
        return value.astimezone(timezone.utc)


class TaskState(BaseModel):
    id: str
    task_id: str
    session_name: str = ""
    project_path: str
    branch: str
    base_branch: str = "main"
    guide_paths: list[str] = Field(default_factory=list)
    role: TaskRole = TaskRole.analyst
    role_knowledge_path: str = ""
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
    agent_type: AgentType = AgentType.codex
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


# ===== SDLC PLATFORM MODELS =====

class SDLCStatus(str, Enum):
    """Extended statuses for SDLC workflow"""
    created = "created"
    analyzing = "analyzing"
    human_review = "human_review"
    analysis_approved = "analysis_approved"
    backend_running = "backend_running"
    n8n_running = "n8n_running"
    frontend_running = "frontend_running"
    testing = "testing"  # Reusing existing
    human_qa = "human_qa"
    pending_approval = "pending_approval"
    revision = "revision"
    blocked = "blocked"  # Reusing existing
    failed = "failed"    # Reusing existing
    done = "done"


class StageRunner(str, Enum):
    """Who executes an SDLC stage.

    auto: a CLI coding agent (Claude Code, else Codex) when the stage has a project_path
    and a CLI is installed; otherwise a text-only Ollama report.
    """
    auto = "auto"
    ollama = "ollama"
    claude = "claude"
    codex = "codex"


class RepositoryMode(str, Enum):
    none = "none"          # the stage uses its own project_path; nothing is created or cloned
    create = "create"      # from scratch: Taskloom creates a private GitHub repo on the first push
    existing = "existing"  # Taskloom clones `url` once and fetches it before every task


class RepositoryConfig(BaseModel):
    """The Git/GitHub repository one SDLC stage (agent) works in."""
    mode: RepositoryMode = RepositoryMode.none
    url: str = ""                 # https://github.com/<owner>/<name>; filled in after creation in `create` mode
    name: str = ""                # repo name to create; defaults to <project-id>-<stage>
    local_path: str = ""          # local clone; defaults to project_path, else ~/taskloom-workspaces/<project>/<stage>
    default_branch: str = "main"
    private: bool = True
    github_token: str = ""        # write-only: moved into the encrypted secret store on save
    token_saved: bool = False
    clear_token: bool = False


ProjectRepository = RepositoryConfig  # name used by the first (project-level) version


class AgentConfig(BaseModel):
    """Configuration for a specific agent type within a project"""
    enabled: bool = True
    runner: StageRunner = StageRunner.auto
    knowledge_path: str = ""
    project_path: str = ""
    system_prompt: str = ""
    test_instructions: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: int = 300  # Ollama request timeout
    cli_timeout_seconds: int = 3600  # Claude Code / Codex run timeout
    max_retries: int = 2
    setup_command: str = ""  # e.g. "npm install" / "pip install -r requirements.txt"; the dialog's Install button
    run_command: str = ""  # e.g. "npm run dev"; started by the ▶ button, runs in the stage's folder
    repository: RepositoryConfig = Field(default_factory=RepositoryConfig)
    github_config: dict[str, str | bool] = Field(default_factory=lambda: {
        "repository_url": "",
        "github_token": "",
        "branch": "main",
        "auto_commit": False,
        "auto_push": False,
        "auto_pr": False
    })


class ProjectWorkflowConfig(BaseModel):
    """Workflow configuration for a project"""
    stages: list[str] = Field(default_factory=lambda: ["analysis", "backend", "n8n", "frontend", "qa"])
    sequential: bool = True
    allow_parallel: bool = False
    max_revision_attempts: int = 3
    require_analysis_approval: bool = False
    require_final_human_approval: bool = False
    auto_resume_interrupted: bool = False  # re-run a stage cut off by a server restart without asking


class SDLCProjectConfig(BaseModel):
    """SDLC-specific project configuration"""
    id: str
    name: str
    description: str = ""
    enabled: bool = True
    sdlc_enabled: bool = True
    workflow: ProjectWorkflowConfig = Field(default_factory=ProjectWorkflowConfig)
    agents: dict[str, AgentConfig] = Field(default_factory=dict)
    # Legacy project-level repository (one repo for all stages). On load it is moved into the
    # agents that have neither their own folder nor their own repository; kept only for parsing.
    repository: RepositoryConfig = Field(default_factory=RepositoryConfig)

    @model_validator(mode="after")
    def move_project_repository_to_agents(self) -> "SDLCProjectConfig":
        legacy = self.repository
        if legacy.mode != RepositoryMode.none:
            for config in self.agents.values():
                if not config.project_path and config.repository.mode == RepositoryMode.none:
                    config.repository = legacy.model_copy(update={"github_token": "", "clear_token": False})
            self.repository = RepositoryConfig()
        return self

    def stage_repository(self, stage: str) -> RepositoryConfig:
        config = self.agents.get(stage)
        return config.repository if config else RepositoryConfig()

    def stage_path(self, stage: str) -> str:
        """Where a stage works: its repository's folder, else its own project_path ("" if neither)."""
        config = self.agents.get(stage)
        if not config:
            return ""
        if config.repository.mode != RepositoryMode.none:
            return (config.repository.local_path or config.project_path
                    or str(Path.home() / "taskloom-workspaces" / self.id / stage))
        return config.project_path

    def stage_repo_name(self, stage: str) -> str:
        return (self.stage_repository(stage).name or f"{self.id}-{stage}").strip()

    @field_validator("id")
    @classmethod
    def valid_id(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", value):
            raise ValueError("Project ID may only contain letters, numbers, dot, dash and underscore")
        return value


class Change(BaseModel):
    """File change information"""
    file: str
    description: str
    kind: str = "modified"  # modified, created, deleted


class TestResults(BaseModel):
    """Structured test results"""
    executed: bool = False
    passed: bool = False
    results: list[dict] = Field(default_factory=list)


class RevisionRequest(BaseModel):
    """Request for revision from one agent to another"""
    requesting_agent: str
    target_agent: str
    reason: str
    description: str
    affected_files: list[str] = Field(default_factory=list)
    expected_result: str = ""
    priority: str = "normal"  # low, normal, high, critical


class HumanIntervention(BaseModel):
    """Request for human intervention"""
    id: str
    task_id: str
    requesting_agent: str
    reason: str
    description: str
    context: dict = Field(default_factory=dict)
    expected_action: str = ""
    response_options: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    responded_at: datetime | None = None
    response: str = ""
    status: str = "pending"  # pending, responded, expired


class AgentResult(BaseModel):
    """Structured output from SDLC agents"""
    agent: str
    status: str  # "completed", "needs_human", "needs_revision", "blocked", "failed"
    summary: str = ""
    changes: list[Change] = Field(default_factory=list)
    tests: TestResults = Field(default_factory=TestResults)
    recommendations: dict[str, list[str]] = Field(default_factory=dict)
    issues: list[str] = Field(default_factory=list)
    revision_request: RevisionRequest | None = None
    human_intervention: HumanIntervention | None = None
    raw_output: str = ""
    
    @field_validator("status")
    @classmethod
    def valid_status(cls, value: str) -> str:
        valid_statuses = {"completed", "needs_human", "needs_revision", "blocked", "failed"}
        if value not in valid_statuses:
            raise ValueError(f"Status must be one of: {valid_statuses}")
        return value


class TaskRepo(BaseModel):
    """A Git repository an SDLC task worked in, and what has been published from it."""
    path: str
    branch: str
    base_branch: str
    commit_sha: str = ""
    pushed: bool = False
    pr_url: str = ""
    pr_number: int | None = None


class SDLCTaskContext(BaseModel):
    """Complete context for SDLC agent execution"""
    task_id: str
    project_config: SDLCProjectConfig
    task_request: str
    previous_results: dict[str, AgentResult] = Field(default_factory=dict)
    agent_specific_knowledge: dict = Field(default_factory=dict)
    test_instructions: dict = Field(default_factory=dict)
    system_prompt: str = ""


class StageQuestion(BaseModel):
    """A question a development/QA stage could not resolve alone. The analyst answers it; what the
    analyst cannot answer goes to a human operator, and the answer comes back through the analyst."""
    id: str
    asking_stage: str
    question: str
    answer: str = ""
    answered_by: str = ""  # "analysis" or "human" (the analyst needed an operator's answer)
    status: str = "open"  # open, answered
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SDLCTask(BaseModel):
    """SDLC-specific task model extending TaskState"""
    # Inherit all TaskState fields
    base_task: TaskState
    
    # Task metadata
    title: str = ""
    description: str = ""
    priority: str = "medium"
    tags: list[str] = Field(default_factory=list)
    
    # SDLC-specific fields
    sdlc_status: SDLCStatus = SDLCStatus.created
    current_stage: str = ""
    current_agent: str = ""
    execution_attempt: int = 0
    revision_count: int = 0
    previous_status: SDLCStatus | None = None
    transition_reason: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # SDLC execution data
    project_config_id: str = ""
    agent_results: dict[str, AgentResult] = Field(default_factory=dict)
    human_interventions: list[HumanIntervention] = Field(default_factory=list)
    revisions: list[RevisionRequest] = Field(default_factory=list)
    stage_questions: list[StageQuestion] = Field(default_factory=list)
    consult_question_id: str = ""  # while set, the analysis stage is answering that StageQuestion
    test_results: dict[str, TestResults] = Field(default_factory=dict)
    repos: dict[str, TaskRepo] = Field(default_factory=dict)  # keyed by repository root path
    version: int = 0  # optimistic-concurrency counter, bumped on every save
    
    # Checkpoint and recovery
    checkpoint_path: str = ""
    last_checkpoint: datetime | None = None


class SDLCTaskRequest(BaseModel):
    """Request to create a new SDLC task"""
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=10000)
    project_id: str = Field(min_length=1)
    priority: str = Field(default="medium")
    tags: list[str] = Field(default_factory=list)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Task title cannot be empty")
        return value

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str) -> str:
        return value.strip()

    @field_validator("priority")
    @classmethod
    def valid_priority(cls, value: str) -> str:
        if value not in {"low", "medium", "high", "critical"}:
            return "medium"
        return value


class HumanInterventionResponse(BaseModel):
    """Response to a human intervention request"""
    intervention_id: str
    response: str
    
    @field_validator("response")
    @classmethod
    def clean_response(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Response cannot be empty")
        return value


class StageTransitionRequest(BaseModel):
    """Request to transition task to next stage"""
    task_id: str
    stage: str
    force: bool = False
    
    @field_validator("stage")
    @classmethod
    def valid_stage(cls, value: str) -> str:
        valid_stages = {"analysis", "backend", "n8n", "frontend", "qa"}
        if value not in valid_stages:
            raise ValueError(f"Stage must be one of: {valid_stages}")
        return value
