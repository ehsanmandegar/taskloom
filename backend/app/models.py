from enum import Enum
import re

from pydantic import BaseModel, Field, field_validator


class RunStatus(str, Enum):
    queued = "queued"
    running = "running"
    testing = "testing"
    passed = "passed"
    failed = "failed"


class TaskRequest(BaseModel):
    project_path: str = Field(min_length=1)
    guide_paths: list[str] = Field(default_factory=list)
    task_id: str = Field(min_length=2, max_length=80)
    request: str = Field(min_length=5, max_length=20_000)
    test_command: str | None = Field(default=None, max_length=500)

    @field_validator("task_id")
    @classmethod
    def valid_task_id(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", value):
            raise ValueError("Task ID may only contain letters, numbers, dot, dash and underscore")
        return value


class ProjectProfile(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    project_path: str = Field(min_length=1)
    guide_paths: list[str] = Field(default_factory=list)
    test_command: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Profile name cannot be empty")
        return value


class CommitRequest(BaseModel):
    message: str = Field(min_length=3, max_length=200)


class TaskState(BaseModel):
    id: str
    task_id: str
    project_path: str
    branch: str
    status: RunStatus
    step: str
    logs: list[str] = Field(default_factory=list)
    summary: str = ""
    diff: str = ""
    changed_files: list[str] = Field(default_factory=list)
    test_output: str = ""
    commit_message: str = ""
    error: str | None = None
    committed: bool = False
    pushed: bool = False
    merge_request_url: str = ""
