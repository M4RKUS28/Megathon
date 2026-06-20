"""Platform-level tenant management.

In production these would be gated to a platform super-admin; for the demo the
tenant `admin` role can view/create companies so the white-label story is
visible end-to-end.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.company import CompanyCreate, CompanyResponse
from src.core.exceptions import AppError
from src.core.tenant import require_app_role
from src.db.crud.company import create_company, get_company_by_slug, list_companies
from src.db.database import get_db
from src.db.models.org import ROLE_ADMIN, User

router = APIRouter(prefix="/companies", tags=["companies"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
AdminDep = Annotated[User, Depends(require_app_role(ROLE_ADMIN))]


@router.get("", response_model=list[CompanyResponse])
async def get_companies(db: DbDep, _: AdminDep) -> list[CompanyResponse]:
    companies = await list_companies(db)
    return [
        CompanyResponse(
            id=c.id, name=c.name, slug=c.slug, status=c.status, created_at=c.created_at
        )
        for c in companies
    ]


@router.post("", response_model=CompanyResponse, status_code=201)
async def post_company(body: CompanyCreate, db: DbDep, _: AdminDep) -> CompanyResponse:
    slug = body.slug.strip().lower()
    if await get_company_by_slug(db, slug) is not None:
        raise AppError(409, f"Company slug '{slug}' already exists")
    company = await create_company(db, name=body.name, slug=slug)
    return CompanyResponse(
        id=company.id,
        name=company.name,
        slug=company.slug,
        status=company.status,
        created_at=company.created_at,
    )
