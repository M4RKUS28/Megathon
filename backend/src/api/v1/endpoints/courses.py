import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.course import (
    AssignmentCreate,
    AssignmentResponse,
    CourseCreate,
    CourseDetail,
    CourseReportRow,
    CourseSummary,
    EditCreate,
    EditResponse,
    JobResponse,
    PlanApproval,
)
from src.core.exceptions import AppError, NotFoundError
from src.core.tenant import CompanyDep, require_app_role
from src.db.crud.assignment import (
    create_assignment,
    list_assignments_for_course,
)
from src.db.crud.company import get_branding
from src.db.crud.course import (
    create_course,
    create_job,
    get_course,
    list_courses,
    list_jobs_for_course,
)
from src.db.crud.department import get_department
from src.db.crud.enrollment import get_or_create_enrollment, list_enrollments_for_course
from src.db.crud.user import get_user, list_company_users
from src.db.database import get_db
from src.db.models.course import (
    COURSE_AUTHORING,
    COURSE_BUILDING,
    COURSE_PLAN_REVIEW,
    COURSE_PLANNING,
    JOB_PLAN,
    JOB_SPEC,
    Course,
    CourseAssignment,
    EditRequest,
    GenerationJob,
)
from src.db.models.org import ROLE_ADMIN, ROLE_COURSE_CREATOR, User
from src.services.generation.builder import index_url
from src.services.queue.pool import get_pool

router = APIRouter(prefix="/courses", tags=["courses"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
StaffDep = Annotated[User, Depends(require_app_role(ROLE_ADMIN, ROLE_COURSE_CREATOR))]


async def _assignment_users(
    db: AsyncSession,
    company_id: uuid.UUID,
    assignment: CourseAssignment,
    users: list[User] | None = None,
) -> list[User]:
    if users is None:
        users = list(await list_company_users(db, company_id))
    by_id = {u.id: u for u in users}
    assigned: dict[str, User] = {}
    if assignment.assignee_user_id:
        user = by_id.get(assignment.assignee_user_id)
        if user is None:
            user = await get_user(db, assignment.assignee_user_id)
        if user is not None and user.company_id == company_id:
            assigned[user.id] = user
    if assignment.assignee_department_id:
        for user in users:
            if user.department_id == assignment.assignee_department_id:
                assigned[user.id] = user
    return list(assigned.values())


def _host_url(course: Course) -> str | None:
    if course.course_url:
        return course.course_url
    return index_url(course.dist_object_prefix) if course.dist_object_prefix else None


def _detail(course: Course) -> CourseDetail:
    return CourseDetail(
        **_summary(course).model_dump(),
        concept=course.concept,
        plan=course.plan,
        spec=course.spec,
        asset_manifest=course.asset_manifest,
        asset_map=course.asset_map,
        course_url=course.course_url,
        iframe_url=course.iframe_url,
        devin_session_id=course.devin_session_id,
    )


def _summary(course: Course) -> CourseSummary:
    return CourseSummary(
        id=course.id,
        title=course.title,
        description=course.description,
        status=course.status,
        version=course.version,
        created_by=course.created_by,
        created_at=course.created_at,
        host_url=_host_url(course),
    )


@router.get("", response_model=list[CourseSummary])
async def get_courses(company: CompanyDep, db: DbDep, _: StaffDep) -> list[CourseSummary]:
    courses = await list_courses(db, company.id)
    return [_summary(c) for c in courses]


@router.post("", response_model=CourseDetail, status_code=201)
async def post_course(
    body: CourseCreate, company: CompanyDep, user: StaffDep, db: DbDep
) -> CourseDetail:
    branding = await get_branding(db, company.id)
    style_guide = branding.style_guide if branding else {}
    course = await create_course(
        db,
        company_id=company.id,
        created_by=user.id,
        title=body.title,
        description=body.description,
        brief={"title": body.title, **body.brief.model_dump()},
        style_guide_snapshot=style_guide,
    )
    # Phase 1 — planner agent (pauses at the approval gate).
    course.status = COURSE_PLANNING
    job = await create_job(db, course.id, company.id, JOB_PLAN)
    await db.commit()
    await db.refresh(course)

    pool = await get_pool()
    await pool.enqueue_job("run_plan_job", str(job.id))

    return _detail(course)


@router.get("/{course_id}", response_model=CourseDetail)
async def get_course_detail(
    course_id: uuid.UUID, company: CompanyDep, db: DbDep, _: StaffDep
) -> CourseDetail:
    course = await get_course(db, company.id, course_id)
    if course is None:
        raise NotFoundError("Course")
    return _detail(course)


@router.post("/{course_id}/plan/approve", response_model=JobResponse, status_code=202)
async def approve_plan(
    course_id: uuid.UUID,
    body: PlanApproval,
    company: CompanyDep,
    db: DbDep,
    _: StaffDep,
) -> JobResponse:
    """Approval gate: accept (optionally edited) plan and start the script writer."""
    course = await get_course(db, company.id, course_id)
    if course is None:
        raise NotFoundError("Course")
    if course.status != COURSE_PLAN_REVIEW:
        raise AppError(409, "Course is not awaiting plan approval")
    if body.plan is not None:
        course.plan = body.plan
    if not course.plan:
        raise AppError(409, "No plan to approve")

    course.status = COURSE_AUTHORING
    job = await create_job(db, course.id, company.id, JOB_SPEC)
    await db.commit()
    await db.refresh(job)

    pool = await get_pool()
    await pool.enqueue_job("run_spec_job", str(job.id))
    return JobResponse(
        id=job.id,
        type=job.type,
        status=job.status,
        error=job.error,
        devin_session_id=job.devin_session_id,
        result=job.result,
        created_at=job.created_at,
    )


@router.post("/{course_id}/generate", response_model=JobResponse, status_code=202)
async def generate_course(
    course_id: uuid.UUID, company: CompanyDep, db: DbDep, _: StaffDep
) -> JobResponse:
    course = await get_course(db, company.id, course_id)
    if course is None:
        raise NotFoundError("Course")
    if course.concept is None:
        raise AppError(409, "Concept not ready yet")
    job = await create_job(db, course.id, company.id, "generate")
    await db.commit()
    await db.refresh(job)

    pool = await get_pool()
    await pool.enqueue_job("run_generate_job", str(job.id))
    return JobResponse(
        id=job.id,
        type=job.type,
        status=job.status,
        error=job.error,
        devin_session_id=job.devin_session_id,
        result=job.result,
        created_at=job.created_at,
    )


@router.get("/{course_id}/jobs", response_model=list[JobResponse])
async def get_course_jobs(
    course_id: uuid.UUID, company: CompanyDep, db: DbDep, _: StaffDep
) -> list[JobResponse]:
    course = await get_course(db, company.id, course_id)
    if course is None:
        raise NotFoundError("Course")
    jobs = await list_jobs_for_course(db, course.id)
    return [
        JobResponse(
            id=j.id,
            type=j.type,
            status=j.status,
            error=j.error,
            devin_session_id=j.devin_session_id,
            result=j.result,
            created_at=j.created_at,
        )
        for j in jobs
    ]


# ── Devin edit-loop ──────────────────────────────────────────────────────────
def _edit_response(edit: EditRequest) -> EditResponse:
    return EditResponse(
        id=edit.id,
        prompt=edit.prompt,
        target_selector=edit.target_selector,
        status=edit.status,
        preview_url=index_url(edit.preview_object_prefix)
        if edit.preview_object_prefix
        else None,
        devin_session_id=edit.devin_session_id,
        created_at=edit.created_at,
    )


@router.post("/{course_id}/edits", response_model=EditResponse, status_code=202)
async def create_edit(
    course_id: uuid.UUID, body: EditCreate, company: CompanyDep, user: StaffDep, db: DbDep
) -> EditResponse:
    course = await get_course(db, company.id, course_id)
    if course is None:
        raise NotFoundError("Course")
    if course.spec is None and course.concept is None:
        raise AppError(409, "Course has nothing to edit yet")

    edit = EditRequest(
        course_id=course.id,
        company_id=company.id,
        requested_by=user.id,
        target_selector=body.target_selector,
        prompt=body.prompt,
        status="queued",
    )
    db.add(edit)
    await db.flush()
    job = await create_job(
        db,
        course.id,
        company.id,
        "edit",
        payload={"edit_request_id": str(edit.id), "target_text": body.target_text},
    )
    await db.commit()
    await db.refresh(edit)

    pool = await get_pool()
    await pool.enqueue_job("run_edit_job", str(job.id))
    return _edit_response(edit)


@router.get("/{course_id}/edits", response_model=list[EditResponse])
async def list_edits(
    course_id: uuid.UUID, company: CompanyDep, db: DbDep, _: StaffDep
) -> list[EditResponse]:
    course = await get_course(db, company.id, course_id)
    if course is None:
        raise NotFoundError("Course")
    result = await db.execute(
        select(EditRequest)
        .where(EditRequest.course_id == course.id)
        .order_by(EditRequest.created_at.desc())
    )
    return [_edit_response(e) for e in result.scalars().all()]


async def _get_edit(db: AsyncSession, course_id: uuid.UUID, edit_id: uuid.UUID) -> EditRequest:
    result = await db.execute(
        select(EditRequest).where(
            EditRequest.id == edit_id, EditRequest.course_id == course_id
        )
    )
    edit = result.scalar_one_or_none()
    if edit is None:
        raise NotFoundError("Edit request")
    return edit


@router.post("/{course_id}/edits/{edit_id}/accept", response_model=JobResponse)
async def accept_edit(
    course_id: uuid.UUID, edit_id: uuid.UUID, company: CompanyDep, db: DbDep, _: StaffDep
) -> JobResponse:
    course = await get_course(db, company.id, course_id)
    if course is None:
        raise NotFoundError("Course")
    edit = await _get_edit(db, course.id, edit_id)

    # The proposed concept was stored on the edit's generation job result.
    result = await db.execute(
        select(GenerationJob)
        .where(
            GenerationJob.course_id == course.id,
            GenerationJob.type == "edit",
            GenerationJob.payload["edit_request_id"].astext == str(edit.id),
        )
        .order_by(GenerationJob.created_at.desc())
    )
    edit_job = result.scalars().first()
    if edit_job is None or not edit_job.result:
        raise AppError(409, "No previewed version to accept")

    edit.status = "accepted"
    course.version += 1

    if "spec" in edit_job.result:
        # Phase-2 course: promote the edited spec and rebuild, reusing the
        # already-fetched assets (no re-generation), then re-host the new version.
        course.spec = edit_job.result["spec"]
        course.status = COURSE_BUILDING
        job = await create_job(
            db, course.id, company.id, "build", payload={"reuse_assets": True}
        )
        await db.commit()
        await db.refresh(job)
        pool = await get_pool()
        await pool.enqueue_job("run_build_job", str(job.id))
    elif "concept" in edit_job.result:
        # Legacy concept course.
        course.concept = edit_job.result["concept"]
        job = await create_job(db, course.id, company.id, "generate")
        await db.commit()
        await db.refresh(job)
        pool = await get_pool()
        await pool.enqueue_job("run_generate_job", str(job.id))
    else:
        raise AppError(409, "No previewed version to accept")

    return JobResponse(
        id=job.id,
        type=job.type,
        status=job.status,
        error=job.error,
        devin_session_id=job.devin_session_id,
        result=job.result,
        created_at=job.created_at,
    )


@router.post("/{course_id}/edits/{edit_id}/reject", response_model=EditResponse)
async def reject_edit(
    course_id: uuid.UUID, edit_id: uuid.UUID, company: CompanyDep, db: DbDep, _: StaffDep
) -> EditResponse:
    course = await get_course(db, company.id, course_id)
    if course is None:
        raise NotFoundError("Course")
    edit = await _get_edit(db, course.id, edit_id)
    edit.status = "rejected"
    await db.commit()
    await db.refresh(edit)
    return _edit_response(edit)


# ── Assignments & reporting ──────────────────────────────────────────────────
@router.get("/{course_id}/assignments", response_model=list[AssignmentResponse])
async def get_assignments(
    course_id: uuid.UUID, company: CompanyDep, db: DbDep, _: StaffDep
) -> list[AssignmentResponse]:
    course = await get_course(db, company.id, course_id)
    if course is None:
        raise NotFoundError("Course")
    rows = await list_assignments_for_course(db, course.id)
    return [
        AssignmentResponse(
            id=a.id,
            assignee_user_id=a.assignee_user_id,
            assignee_department_id=a.assignee_department_id,
            mandatory=a.mandatory,
            due_date=a.due_date,
            created_at=a.created_at,
        )
        for a in rows
    ]


@router.post("/{course_id}/assignments", response_model=AssignmentResponse, status_code=201)
async def post_assignment(
    course_id: uuid.UUID,
    body: AssignmentCreate,
    company: CompanyDep,
    user: StaffDep,
    db: DbDep,
) -> AssignmentResponse:
    course = await get_course(db, company.id, course_id)
    if course is None:
        raise NotFoundError("Course")
    if body.user_id is None and body.department_id is None:
        raise AppError(422, "Provide a user_id or department_id")
    if body.user_id is not None and body.department_id is not None:
        raise AppError(422, "Provide either user_id or department_id, not both")

    target_users: list[User] = []
    if body.user_id is not None:
        target = await get_user(db, body.user_id)
        if target is None or target.company_id != company.id:
            raise NotFoundError("User")
        target_users.append(target)
    if body.department_id is not None:
        dept = await get_department(db, company.id, body.department_id)
        if dept is None:
            raise NotFoundError("Department")
        company_users = await list_company_users(db, company.id)
        target_users = [u for u in company_users if u.department_id == body.department_id]

    assignment = await create_assignment(
        db,
        course.id,
        company.id,
        assigned_by=user.id,
        user_id=body.user_id,
        department_id=body.department_id,
        mandatory=body.mandatory,
        due_date=body.due_date,
    )
    for target in target_users:
        await get_or_create_enrollment(db, course.id, company.id, target.id)
    await db.commit()
    await db.refresh(assignment)
    return AssignmentResponse(
        id=assignment.id,
        assignee_user_id=assignment.assignee_user_id,
        assignee_department_id=assignment.assignee_department_id,
        mandatory=assignment.mandatory,
        due_date=assignment.due_date,
        created_at=assignment.created_at,
    )


@router.delete("/{course_id}/assignments/{assignment_id}", status_code=204)
async def remove_assignment(
    course_id: uuid.UUID,
    assignment_id: uuid.UUID,
    company: CompanyDep,
    db: DbDep,
    _: StaffDep,
) -> None:
    result = await db.execute(
        select(CourseAssignment).where(
            CourseAssignment.id == assignment_id,
            CourseAssignment.course_id == course_id,
            CourseAssignment.company_id == company.id,
        )
    )
    assignment = result.scalar_one_or_none()
    if assignment is None:
        raise NotFoundError("Assignment")
    await db.delete(assignment)
    await db.commit()


@router.get("/{course_id}/report", response_model=list[CourseReportRow])
async def course_report(
    course_id: uuid.UUID, company: CompanyDep, db: DbDep, _: StaffDep
) -> list[CourseReportRow]:
    course = await get_course(db, company.id, course_id)
    if course is None:
        raise NotFoundError("Course")
    enrollments = {
        e.user_id: e for e in await list_enrollments_for_course(db, course.id)
    }
    users = list(await list_company_users(db, company.id))
    assignments = await list_assignments_for_course(db, course.id)
    assigned_users: dict[str, User] = {}
    for assignment in assignments:
        for assigned in await _assignment_users(db, company.id, assignment, users):
            assigned_users[assigned.id] = assigned
    rows: list[CourseReportRow] = []
    for u in assigned_users.values():
        e = enrollments.get(u.id)
        rows.append(
            CourseReportRow(
                user_id=u.id,
                display_name=u.display_name,
                email=u.email,
                status=e.status if e else "not_started",
                progress_pct=e.progress_pct if e else 0,
                score=e.score if e else None,
                time_spent_seconds=e.time_spent_seconds if e else 0,
                quiz_attempts=e.quiz_attempts if e else 0,
                engagement_score=e.engagement_score if e else 0,
                certified=e.certified if e else False,
                completed_at=e.completed_at if e else None,
            )
        )
    return rows
