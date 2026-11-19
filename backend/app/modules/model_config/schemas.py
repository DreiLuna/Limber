from typing import Any

from pydantic import BaseModel, Field


class VersionSummary(BaseModel):
    version: int
    is_active: bool
    note: str
    author: str | None
    parent_version: int | None
    created_at: str


class VersionOut(VersionSummary):
    thresholds: dict[str, Any]
    prompt_instructions: str


class ActiveOut(BaseModel):
    version: int | None  # None = no saved versions yet, YAML defaults in use
    thresholds: dict[str, Any]
    prompt_instructions: str
    locked_rules: str


class VersionCreate(BaseModel):
    thresholds: dict[str, Any]
    prompt_instructions: str = Field(max_length=8000)
    note: str = Field(max_length=500)
    activate: bool = True


class FieldChange(BaseModel):
    path: str
    before: Any
    after: Any


class DiffOut(BaseModel):
    base: int
    target: int
    threshold_changes: list[FieldChange]
    prompt_changed: bool
    base_prompt: str
    target_prompt: str


class PreviewRequest(BaseModel):
    prompt_instructions: str = Field(max_length=8000)
    thresholds: dict[str, Any] | None = None


class PreviewOut(BaseModel):
    prompt: str
    errors: list[str]
