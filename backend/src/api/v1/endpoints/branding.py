from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.branding import BrandingResponse, BrandingUpdate, StyleGuide
from src.core.exceptions import NotFoundError
from src.core.tenant import CompanyDep, require_app_role
from src.db.crud.company import get_branding, get_company_by_slug, upsert_branding
from src.db.database import get_db
from src.db.models.org import ROLE_ADMIN, ROLE_COURSE_CREATOR, User

router = APIRouter(tags=["branding"])

DbDep = Annotated[AsyncSession, Depends(get_db)]


def _to_response(company_id, company_name, slug, branding) -> BrandingResponse:
    style = StyleGuide(**(branding.style_guide if branding else {}))
    return BrandingResponse(
        company_id=company_id,
        company_name=company_name,
        slug=slug,
        primary_color=branding.primary_color if branding else None,
        logo_url=branding.logo_url if branding else None,
        style_guide=style,
    )


@router.get("/public/branding/{slug}", response_model=BrandingResponse)
async def public_branding(slug: str, db: DbDep) -> BrandingResponse:
    """Unauthenticated branding lookup used to theme the shell before login."""
    company = await get_company_by_slug(db, slug)
    if company is None:
        raise NotFoundError("Company")
    branding = await get_branding(db, company.id)
    return _to_response(company.id, company.name, company.slug, branding)


@router.get("/branding", response_model=BrandingResponse)
async def my_branding(company: CompanyDep, db: DbDep) -> BrandingResponse:
    branding = await get_branding(db, company.id)
    return _to_response(company.id, company.name, company.slug, branding)


@router.put("/branding", response_model=BrandingResponse)
async def update_branding(
    body: BrandingUpdate,
    company: CompanyDep,
    db: DbDep,
    _: Annotated[User, Depends(require_app_role(ROLE_ADMIN, ROLE_COURSE_CREATOR))],
) -> BrandingResponse:
    branding = await upsert_branding(
        db,
        company.id,
        style_guide=body.style_guide.model_dump(),
        primary_color=body.primary_color,
        logo_url=body.logo_url,
    )
    return _to_response(company.id, company.name, company.slug, branding)
