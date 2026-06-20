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
    progress: dict | None = None
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


# ── Learning / enrollment ────────────────────────────────────────────────────
class EnrollmentResponse(BaseModel):
    status: str
    progress_pct: int
    current_chapter: int | None = None
    score: int | None = None
    completed_at: datetime | None = None


class ProgressUpdate(BaseModel):
    status: str | None = None
    progress_pct: int | None = None
    current_chapter: int | None = None
    score: int | None = None


class LearningCourse(CourseSummary):
    enrollment: EnrollmentResponse | None = None


class LearningCourseDetail(LearningCourse):
    concept: dict | None = None


# ── Assignments / reporting ──────────────────────────────────────────────────
class AssignmentCreate(BaseModel):
    user_id: str | None = None
    department_id: uuid.UUID | None = None
    mandatory: bool = False
    due_date: datetime | None = None


class AssignmentResponse(BaseModel):
    id: uuid.UUID
    assignee_user_id: str | None
    assignee_department_id: uuid.UUID | None
    mandatory: bool
    due_date: datetime | None
    created_at: datetime


class CourseReportRow(BaseModel):
    user_id: str
    display_name: str
    email: str
    status: str
    progress_pct: int
    score: int | None = None
    completed_at: datetime | None = None
