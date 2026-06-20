import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.course import (
    EnrollmentResponse,
    LearningCourse,
    LearningCourseDetail,
    ProgressUpdate,
)
from src.core.exceptions import NotFoundError
from src.core.tenant import AppUserDep, CompanyDep
from src.db.crud.assignment import list_assigned_courses
from src.db.crud.course import get_course
from src.db.crud.enrollment import (
    get_enrollment,
    get_or_create_enrollment,
    update_progress,
)
from src.db.database import get_db
from src.db.models.course import COURSE_PUBLISHED, COURSE_READY, Course, Enrollment

router = APIRouter(prefix="/learning", tags=["learning"])

DbDep = Annotated[AsyncSession, Depends(get_db)]

_VISIBLE = {COURSE_READY, COURSE_PUBLISHED}


def _enrollment_response(e: Enrollment | None) -> EnrollmentResponse | None:
    if e is None:
        return None
    return EnrollmentResponse(
        status=e.status,
        progress_pct=e.progress_pct,
        current_chapter=e.current_chapter,
        score=e.score,
        completed_at=e.completed_at,
    )


def _host_url(course: Course) -> str | None:
    from src.services.generation.builder import index_url

    return index_url(course.dist_object_prefix) if course.dist_object_prefix else None


def _learning_course(course: Course, enrollment: Enrollment | None) -> LearningCourse:
    return LearningCourse(
        id=course.id,
        title=course.title,
        description=course.description,
        status=course.status,
        version=course.version,
        created_by=course.created_by,
        created_at=course.created_at,
        host_url=_host_url(course),
        enrollment=_enrollment_response(enrollment),
    )


@router.get("/courses", response_model=list[LearningCourse])
async def my_courses(user: AppUserDep, company: CompanyDep, db: DbDep) -> list[LearningCourse]:
    courses = await list_assigned_courses(db, company.id, user.id, user.department_id)
    visible = [c for c in courses if c.status in _VISIBLE]
    out: list[LearningCourse] = []
    for c in visible:
        enrollment = await get_enrollment(db, c.id, user.id)
        out.append(_learning_course(c, enrollment))
    return out


@router.get("/courses/{course_id}", response_model=LearningCourseDetail)
async def my_course_detail(
    course_id: uuid.UUID, user: AppUserDep, company: CompanyDep, db: DbDep
) -> LearningCourseDetail:
    course = await get_course(db, company.id, course_id)
    if course is None or course.status not in _VISIBLE:
        raise NotFoundError("Course")
    enrollment = await get_enrollment(db, course.id, user.id)
    base = _learning_course(course, enrollment)
    return LearningCourseDetail(**base.model_dump(), concept=course.concept)


@router.post("/courses/{course_id}/progress", response_model=EnrollmentResponse)
async def report_progress(
    course_id: uuid.UUID,
    body: ProgressUpdate,
    user: AppUserDep,
    company: CompanyDep,
    db: DbDep,
) -> EnrollmentResponse:
    course = await get_course(db, company.id, course_id)
    if course is None or course.status not in _VISIBLE:
        raise NotFoundError("Course")
    enrollment = await get_or_create_enrollment(db, course.id, company.id, user.id)
    enrollment = await update_progress(
        db,
        enrollment,
        status=body.status,
        progress_pct=body.progress_pct,
        current_chapter=body.current_chapter,
        current_page=body.current_page,
        score=body.score,
        time_spent_seconds=body.time_spent_seconds,
        quiz_attempts=body.quiz_attempts,
        drop_off_point=body.drop_off_point,
        engagement_score=body.engagement_score,
    )
    return _enrollment_response(enrollment)  # type: ignore[return-value]
