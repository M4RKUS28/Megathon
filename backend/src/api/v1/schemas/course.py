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
    plan: dict | None = None
    spec: dict | None = None
    asset_manifest: dict | None = None
    asset_map: dict | None = None
    course_url: str | None = None
    iframe_url: str | None = None
    devin_session_id: str | None = None
    devin_session_url: str | None = None


class PlanApproval(BaseModel):
    """Approval-gate payload. An optionally edited plan replaces the generated
    one before the script writer (Phase 2) proceeds."""

    plan: dict | None = None


class JobResponse(BaseModel):
    id: uuid.UUID
    type: str
    status: str
    error: str | None = None
    devin_session_id: str | None = None
    devin_session_url: str | None = None
    result: dict | None = None
    created_at: datetime


class EditCreate(BaseModel):
    prompt: str = Field(min_length=3, max_length=2000)
    target_selector: str | None = None
    target_text: str | None = None


class EditDiff(BaseModel):
    blocks_changed: list[str] = Field(default_factory=list)
    blocks_added: list[str] = Field(default_factory=list)
    blocks_removed: list[str] = Field(default_factory=list)
    summary: str = ""


class EditResponse(BaseModel):
    id: uuid.UUID
    prompt: str
    target_selector: str | None
    status: str
    preview_url: str | None = None
    diff: EditDiff | None = None
    devin_session_id: str | None = None
    devin_session_url: str | None = None
    created_at: datetime


# ── Learning / enrollment ────────────────────────────────────────────────────
class EnrollmentResponse(BaseModel):
    status: str
    progress_pct: int
    current_chapter: int | None = None
    score: int | None = None
    completed_at: datetime | None = None


class EnrollmentResponseFull(EnrollmentResponse):
    current_page: int | None = None
    time_spent_seconds: int = 0
    quiz_attempts: int = 0
    engagement_score: int = 0
    certified: bool = False
    certificate_id: str | None = None


class ProgressUpdate(BaseModel):
    status: str | None = None
    progress_pct: int | None = None
    current_chapter: int | None = None
    current_page: int | None = None
    score: int | None = None
    time_spent_seconds: int | None = None
    quiz_attempts: int | None = None
    drop_off_point: str | None = None
    engagement_score: int | None = None


class LearningCourse(CourseSummary):
    enrollment: EnrollmentResponse | None = None


class LearningCourseDetail(LearningCourse):
    pass


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
    time_spent_seconds: int = 0
    quiz_attempts: int = 0
    engagement_score: int = 0
    certified: bool = False
    completed_at: datetime | None = None
