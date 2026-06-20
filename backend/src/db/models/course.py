import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.db.database import Base

# Course lifecycle (5-phase pipeline)
COURSE_DRAFT = "draft"
COURSE_PLANNING = "planning"  # Phase 1: planner agent running (states 1-3)
COURSE_PLAN_REVIEW = "plan_review"  # Approval gate — paused for user
COURSE_AUTHORING = "authoring"  # Phase 2: script writer (states 4-5)
COURSE_SPEC_READY = "spec_ready"  # Lastenheft + asset manifest ready
COURSE_BUILDING = "building"  # Phase 2.5/3: assets + implementation
COURSE_READY = "ready"  # Phase 4: built dist published
COURSE_PUBLISHED = "published"
COURSE_FAILED = "failed"

# Generation job lifecycle
JOB_QUEUED = "queued"
JOB_RUNNING = "running"
JOB_SUCCEEDED = "succeeded"
JOB_FAILED = "failed"

# Job types
JOB_PLAN = "plan"  # Phase 1 planner agent (LangGraph states 1-3)
JOB_SPEC = "spec"  # Phase 2 script writer (LangGraph states 4-5)
JOB_ASSETS = "assets"  # Phase 2.5 process A — resource fetch
JOB_BUILD = "build"  # Phase 2.5/3 process B — implementation + hosting
JOB_EDIT = "edit"  # Devin-assisted edit loop


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid()
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=COURSE_DRAFT)
    # Phase 1 — Course Plan (planner agent output, shown at the approval gate).
    plan: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Phase 2 — Lastenheft (full interactive spec from the script writer).
    spec: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Phase 2 — isolated asset manifest (template_link + specs, no assets yet).
    asset_manifest: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Phase 2.5 process A — template_link -> final storage_url mapping.
    asset_map: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Style guide captured at generation time, for reproducibility.
    style_guide_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # MinIO prefix where the built dist/ for the current version lives.
    dist_object_prefix: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # Phase 4 — public hosting URLs.
    course_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    iframe_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    devin_session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class GenerationJob(Base):
    """Queue record for the async generation pipeline (plan | spec | build | edit)."""

    __tablename__ = "generation_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid()
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False)  # plan|spec|build|edit
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=JOB_QUEUED)
    devin_session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class CourseAssignment(Base):
    """Polymorphic assignment: to a user, a department, or a group."""

    __tablename__ = "course_assignments"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid()
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assignee_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    assignee_department_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE"), nullable=True
    )
    assignee_group_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), nullable=True
    )
    assigned_by: Mapped[str] = mapped_column(String(255), nullable=False)
    mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Enrollment(Base):
    """A user's progress through a course."""

    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("course_id", "user_id", name="uq_enrollment_course_user"),)

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid()
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_started")
    progress_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_chapter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Phase 5 — richer progress tracking.
    time_spent_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quiz_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    drop_off_point: Mapped[str | None] = mapped_column(String(255), nullable=True)
    engagement_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    certified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    certificate_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_activity_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class EditRequest(Base):
    """A Devin-assisted edit to a generated course (element select -> prompt)."""

    __tablename__ = "edit_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid()
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requested_by: Mapped[str] = mapped_column(String(255), nullable=False)
    target_selector: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    devin_session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    preview_object_prefix: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
