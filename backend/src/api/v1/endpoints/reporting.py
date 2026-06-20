"""Phase 5 — reporting, manager dashboards and LMS standards export."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError
from src.core.tenant import AppUserDep, CompanyDep, require_app_role
from src.db.crud.course import get_course
from src.db.crud.user import list_company_users
from src.db.database import get_db
from src.db.models.course import Enrollment
from src.db.models.org import ROLE_ADMIN, ROLE_COURSE_CREATOR, User
from src.services.standards import (
    VERB_COMPLETED,
    VERB_PASSED,
    VERB_PROGRESSED,
    scorm_manifest,
    xapi_statement,
)

router = APIRouter(prefix="/reporting", tags=["reporting"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
StaffDep = Annotated[User, Depends(require_app_role(ROLE_ADMIN, ROLE_COURSE_CREATOR))]


# ── SCORM export ─────────────────────────────────────────────────────────────
@router.get("/courses/{course_id}/scorm")
async def export_scorm(
    course_id: uuid.UUID,
    company: CompanyDep,
    db: DbDep,
    _: StaffDep,
    version: str = Query("1.2", pattern="^(1.2|2004)$"),
) -> Response:
    """Return an IMS SCORM `imsmanifest.xml` for the hosted course entry point."""
    course = await get_course(db, company.id, course_id)
    if course is None:
        raise NotFoundError("Course")
    xml = scorm_manifest(str(course.id), course.title, version=version)
    return Response(
        content=xml,
        media_type="application/xml",
        headers={"Content-Disposition": "attachment; filename=imsmanifest.xml"},
    )


# ── xAPI export ──────────────────────────────────────────────────────────────
@router.get("/courses/{course_id}/xapi")
async def export_xapi(
    course_id: uuid.UUID, company: CompanyDep, db: DbDep, _: StaffDep
) -> list[dict]:
    """Return xAPI (Tin Can) statements derived from the course's enrollments."""
    course = await get_course(db, company.id, course_id)
    if course is None:
        raise NotFoundError("Course")
    users = {u.id: u for u in await list_company_users(db, company.id)}
    result = await db.execute(select(Enrollment).where(Enrollment.course_id == course.id))
    enrollments = result.scalars().all()

    object_id = course.course_url or f"urn:coursive:course:{course.id}"
    statements: list[dict] = []
    for e in enrollments:
        u = users.get(e.user_id)
        if u is None:
            continue
        completed = e.status == "completed"
        verb_id, verb_disp = (
            VERB_COMPLETED if completed else VERB_PROGRESSED
        )
        statements.append(
            xapi_statement(
                u.email,
                u.display_name,
                verb_id,
                verb_disp,
                object_id,
                course.title,
                score_pct=e.score,
                completed=completed,
            )
        )
        if completed and e.certified:
            statements.append(
                xapi_statement(
                    u.email,
                    u.display_name,
                    *VERB_PASSED,
                    object_id,
                    course.title,
                    score_pct=e.score,
                    success=True,
                )
            )
    return statements


# ── Manager dashboard ────────────────────────────────────────────────────────
class TeamMemberProgress(BaseModel):
    user_id: str
    display_name: str
    email: str
    assigned: int
    completed: int
    in_progress: int
    not_started: int
    avg_score: float | None = None
    compliance_pct: int = 0


class ManagerDashboard(BaseModel):
    team_size: int
    assigned_courses: int
    completed_courses: int
    open_courses: int
    avg_score: float | None
    compliance_pct: int
    members: list[TeamMemberProgress]


@router.get("/manager/dashboard", response_model=ManagerDashboard)
async def manager_dashboard(
    user: AppUserDep, company: CompanyDep, db: DbDep
) -> ManagerDashboard:
    """Aggregate progress for the current user's direct reports."""
    all_users = await list_company_users(db, company.id)
    team = [u for u in all_users if u.manager_id == user.id]
    team_ids = [u.id for u in team]

    enrollments: list[Enrollment] = []
    if team_ids:
        result = await db.execute(
            select(Enrollment).where(
                Enrollment.company_id == company.id, Enrollment.user_id.in_(team_ids)
            )
        )
        enrollments = list(result.scalars().all())

    by_user: dict[str, list[Enrollment]] = {uid: [] for uid in team_ids}
    for e in enrollments:
        by_user.setdefault(e.user_id, []).append(e)

    members: list[TeamMemberProgress] = []
    total_assigned = total_completed = total_open = 0
    all_scores: list[int] = []
    for u in team:
        es = by_user.get(u.id, [])
        completed = sum(1 for e in es if e.status == "completed")
        in_progress = sum(1 for e in es if e.status == "in_progress")
        not_started = sum(1 for e in es if e.status not in {"completed", "in_progress"})
        scores = [e.score for e in es if e.score is not None]
        all_scores.extend(scores)
        assigned = len(es)
        total_assigned += assigned
        total_completed += completed
        total_open += assigned - completed
        members.append(
            TeamMemberProgress(
                user_id=u.id,
                display_name=u.display_name,
                email=u.email,
                assigned=assigned,
                completed=completed,
                in_progress=in_progress,
                not_started=not_started,
                avg_score=(sum(scores) / len(scores)) if scores else None,
                compliance_pct=round(100 * completed / assigned) if assigned else 0,
            )
        )

    return ManagerDashboard(
        team_size=len(team),
        assigned_courses=total_assigned,
        completed_courses=total_completed,
        open_courses=total_open,
        avg_score=(sum(all_scores) / len(all_scores)) if all_scores else None,
        compliance_pct=round(100 * total_completed / total_assigned) if total_assigned else 0,
        members=members,
    )
