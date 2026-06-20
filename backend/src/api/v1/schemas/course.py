import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CourseBrief(BaseModel):
    audience: str = "new employees"
    goals: str = ""
    tone: str = "friendly and professional"
    duration: str = "4-6 chapters"
    topics: list[str] = Field(default_factory=list)


class CourseCreate(BaseModel):
    title: str
    description: str = ""
    brief: CourseBrief = Field(default_factory=CourseBrief)


class CourseSummary(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    status: str
    version: int
    created_by: str
    created_at: datetime
    host_url: str | None = None


class CourseDetail(CourseSummary):
    concept: dict | None = None
    devin_session_id: str | None = None


class JobResponse(BaseModel):
    id: uuid.UUID
    type: str
    status: str
    error: str | None = None
    devin_session_id: str | None = None
    result: dict | None = None
    created_at: datetime


class EditCreate(BaseModel):
    prompt: str
    target_selector: str | None = None
    target_text: str | None = None


class EditResponse(BaseModel):
    id: uuid.UUID
    prompt: str
    target_selector: str | None
    status: str
    preview_url: str | None = None
    devin_session_id: str | None = None
    created_at: datetime
