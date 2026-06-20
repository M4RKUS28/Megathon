import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.people import (
    VALID_ROLES,
    DepartmentCreate,
    DepartmentResponse,
    UserResponse,
    UserUpdate,
)
from src.core.exceptions import AppError, NotFoundError
from src.core.tenant import CompanyDep, require_app_role
from src.db.crud.department import (
    create_department,
    delete_department,
    get_department,
    list_departments,
)
from src.db.crud.user import get_user, list_company_users, update_user
from src.db.database import get_db
from src.db.models.org import ROLE_ADMIN, ROLE_COURSE_CREATOR, User

router = APIRouter(tags=["people"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
StaffDep = Annotated[User, Depends(require_app_role(ROLE_ADMIN, ROLE_COURSE_CREATOR))]
AdminDep = Annotated[User, Depends(require_app_role(ROLE_ADMIN))]


# ── Departments ──────────────────────────────────────────────────────────────
@router.get("/departments", response_model=list[DepartmentResponse])
async def get_departments(company: CompanyDep, db: DbDep) -> list[DepartmentResponse]:
    depts = await list_departments(db, company.id)
    return [DepartmentResponse(id=d.id, name=d.name, parent_id=d.parent_id) for d in depts]


@router.post("/departments", response_model=DepartmentResponse, status_code=201)
async def post_department(
    body: DepartmentCreate, company: CompanyDep, db: DbDep, _: StaffDep
) -> DepartmentResponse:
    dept = await create_department(db, company.id, body.name, body.parent_id)
    return DepartmentResponse(id=dept.id, name=dept.name, parent_id=dept.parent_id)


@router.delete("/departments/{department_id}", status_code=204)
async def remove_department(
    department_id: uuid.UUID, company: CompanyDep, db: DbDep, _: AdminDep
) -> None:
    dept = await get_department(db, company.id, department_id)
    if dept is None:
        raise NotFoundError("Department")
    await delete_department(db, dept)


# ── Users (people) ───────────────────────────────────────────────────────────
@router.get("/people", response_model=list[UserResponse])
async def get_people(company: CompanyDep, db: DbDep, _: StaffDep) -> list[UserResponse]:
    users = await list_company_users(db, company.id)
    return [
        UserResponse(
            id=u.id,
            email=u.email,
            display_name=u.display_name,
            role=u.role,
            department_id=u.department_id,
            manager_id=u.manager_id,
        )
        for u in users
    ]


@router.patch("/people/{user_id}", response_model=UserResponse)
async def patch_person(
    user_id: str,
    body: UserUpdate,
    company: CompanyDep,
    db: DbDep,
    _: AdminDep,
) -> UserResponse:
    user = await get_user(db, user_id)
    if user is None or user.company_id != company.id:
        raise NotFoundError("User")
    if body.role is not None and body.role not in VALID_ROLES:
        raise AppError(422, f"Invalid role '{body.role}'")
    updated = await update_user(
        db,
        user,
        role=body.role,
        manager_id=body.manager_id,
        department_id=body.department_id,
    )
    return UserResponse(
        id=updated.id,
        email=updated.email,
        display_name=updated.display_name,
        role=updated.role,
        department_id=updated.department_id,
        manager_id=updated.manager_id,
    )
