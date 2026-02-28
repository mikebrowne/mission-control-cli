from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict


T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    model_config = ConfigDict(extra="allow")
    ok: bool
    data: T | None = None
    reason: str | None = None


class Task(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    status: str
    priority: str | None = None
    attempt_count: int | None = None


class TaskRun(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    task_id: str
    agent_id: str | None = None
    attempt: int
    outcome: str | None = None


class ClaimData(BaseModel):
    model_config = ConfigDict(extra="allow")
    task: Task
    task_run: TaskRun


class ConcurrencyData(BaseModel):
    max: int
    running: int


class Project(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    name: str
    status: str | None = None


class ExpireLeasesData(BaseModel):
    model_config = ConfigDict(extra="allow")
    expired_count: int | None = None


class CommentaryItem(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str | None = None
    author: str | None = None
    body: str | None = None


class SettingsData(BaseModel):
    model_config = ConfigDict(extra="allow")


class ExpireLeasesData(BaseModel):
    model_config = ConfigDict(extra="allow")
    expired_count: int | None = None


class CommentaryItem(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str | None = None
    author: str | None = None
    body: str | None = None


class SettingsData(BaseModel):
    model_config = ConfigDict(extra="allow")
