import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.course import Course, CourseAssignment


async def create_assignment(
    db: AsyncSession,
    course_id: uuid.UUID,
    company_id: uuid.UUID,
    assigned_by: str,
    *,
    user_id: str | None = None,
    department_id: uuid.UUID | None = None,
    mandatory: bool = False,
    due_date: datetime | None = None,
) -> CourseAssignment:
    assignment = CourseAssignment(
        course_id=course_id,
        company_id=company_id,
        assigned_by=assigned_by,
        assignee_user_id=user_id,
        assignee_department_id=department_id,
        mandatory=mandatory,
        due_date=due_date,
    )
    db.add(assignment)
    await db.flush()
    return assignment


async def list_assignments_for_course(
    db: AsyncSession, course_id: uuid.UUID
) -> Sequence[CourseAssignment]:
    result = await db.execute(
        select(CourseAssignment).where(CourseAssignment.course_id == course_id)
    )
    return result.scalars().all()


async def delete_assignment(db: AsyncSession, assignment: CourseAssignment) -> None:
    await db.delete(assignment)
    await db.flush()


async def list_assigned_courses(
    db: AsyncSession, company_id: uuid.UUID, user_id: str, department_id: uuid.UUID | None
) -> Sequence[Course]:
    """Courses assigned to a user directly or via their department."""
    conds = [CourseAssignment.assignee_user_id == user_id]
    if department_id is not None:
        conds.append(CourseAssignment.assignee_department_id == department_id)
    result = await db.execute(
        select(Course)
        .join(CourseAssignment, CourseAssignment.course_id == Course.id)
        .where(CourseAssignment.company_id == company_id, or_(*conds))
        .distinct()
        .order_by(Course.created_at.desc())
    )
    return result.scalars().all()
