import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.course import Enrollment


async def get_enrollment(
    db: AsyncSession, course_id: uuid.UUID, user_id: str
) -> Enrollment | None:
    result = await db.execute(
        select(Enrollment).where(
            Enrollment.course_id == course_id, Enrollment.user_id == user_id
        )
    )
    return result.scalar_one_or_none()


async def get_or_create_enrollment(
    db: AsyncSession, course_id: uuid.UUID, company_id: uuid.UUID, user_id: str
) -> Enrollment:
    enrollment = await get_enrollment(db, course_id, user_id)
    if enrollment is None:
        enrollment = Enrollment(
            course_id=course_id, company_id=company_id, user_id=user_id, status="not_started"
        )
        db.add(enrollment)
        await db.flush()
    return enrollment


async def update_progress(
    db: AsyncSession,
    enrollment: Enrollment,
    *,
    status: str | None = None,
    progress_pct: int | None = None,
    current_chapter: int | None = None,
    score: int | None = None,
) -> Enrollment:
    if status is not None:
        enrollment.status = status
    if progress_pct is not None:
        enrollment.progress_pct = max(0, min(100, progress_pct))
    if current_chapter is not None:
        enrollment.current_chapter = current_chapter
    if score is not None:
        enrollment.score = score
    enrollment.last_activity_at = datetime.now(UTC)
    if enrollment.status == "completed" and enrollment.completed_at is None:
        enrollment.completed_at = datetime.now(UTC)
    await db.flush()
    return enrollment


async def list_enrollments_for_course(
    db: AsyncSession, course_id: uuid.UUID
) -> Sequence[Enrollment]:
    result = await db.execute(select(Enrollment).where(Enrollment.course_id == course_id))
    return result.scalars().all()
