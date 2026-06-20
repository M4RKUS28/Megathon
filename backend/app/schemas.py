from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class CourseCreate(BaseModel):
    title: str = Field(min_length=2)
    description: str = Field(min_length=2)
    target_audience: str = Field(min_length=2)
    language: str = Field(default="English", min_length=2)
    difficulty: str = Field(default="Beginner")
    desired_duration_minutes: int = Field(default=45, ge=5, le=480)
    company_context: str = Field(min_length=2)
    compliance_requirements: str = Field(min_length=2)
    source_material: str | None = None


class ChapterEdit(BaseModel):
    id: str
    title: str
    duration_minutes: int = Field(ge=1)


class PlanApproval(BaseModel):
    chapters: list[ChapterEdit] | None = None


class LaunchDevinPhase(BaseModel):
    phase: Literal["implementation", "asset_integration", "qa"]


class ApiMessage(BaseModel):
    ok: bool
    message: str
    details: dict[str, Any] | None = None


class PreflightResult(BaseModel):
    ok: bool
    mode: Literal["real", "testing_fake"]
    checks: dict[str, Any]
    error: str | None = None


class CourseSummary(BaseModel):
    id: str
    title: str
    status: str
    target_audience: str
    desired_duration_minutes: int
    created_at: str
    updated_at: str
