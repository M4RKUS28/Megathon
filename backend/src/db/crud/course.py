import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.course import Course, GenerationJob


async def create_course(
    db: AsyncSession,
    company_id: uuid.UUID,
    created_by: str,
    title: str,
    description: str,
    brief: dict,
    style_guide_snapshot: dict | None = None,
) -> Course:
    course = Course(
        company_id=company_id,
        created_by=created_by,
        title=title,
        description=description,
        style_guide_snapshot=style_guide_snapshot,
    )
    # Stash the raw brief so the worker can build the planner prompt.
    course.style_guide_snapshot = {
        "brief": brief,
        "style_guide": style_guide_snapshot or {},
    }
    db.add(course)
    await db.flush()
    await db.refresh(course)
    return course


async def get_course(
    db: AsyncSession, company_id: uuid.UUID, course_id: uuid.UUID
) -> Course | None:
    result = await db.execute(
        select(Course).where(Course.id == course_id, Course.company_id == company_id)
    )
    return result.scalar_one_or_none()


async def get_course_by_id(db: AsyncSession, course_id: uuid.UUID) -> Course | None:
    result = await db.execute(select(Course).where(Course.id == course_id))
    return result.scalar_one_or_none()


async def list_courses(db: AsyncSession, company_id: uuid.UUID) -> Sequence[Course]:
    result = await db.execute(
        select(Course).where(Course.company_id == company_id).order_by(Course.created_at.desc())
    )
    return result.scalars().all()


async def create_job(
    db: AsyncSession,
    course_id: uuid.UUID,
    company_id: uuid.UUID,
    job_type: str,
    payload: dict | None = None,
) -> GenerationJob:
    job = GenerationJob(
        course_id=course_id, company_id=company_id, type=job_type, payload=payload or {}
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)
    return job


async def get_job(db: AsyncSession, job_id: uuid.UUID) -> GenerationJob | None:
    result = await db.execute(select(GenerationJob).where(GenerationJob.id == job_id))
    return result.scalar_one_or_none()


async def list_jobs_for_course(
    db: AsyncSession, course_id: uuid.UUID
) -> Sequence[GenerationJob]:
    result = await db.execute(
        select(GenerationJob)
        .where(GenerationJob.course_id == course_id)
        .order_by(GenerationJob.created_at.desc())
    )
    return result.scalars().all()
