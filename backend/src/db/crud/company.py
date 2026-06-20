import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.company import Company, CompanyBranding


async def get_company(db: AsyncSession, company_id: uuid.UUID) -> Company | None:
    result = await db.execute(select(Company).where(Company.id == company_id))
    return result.scalar_one_or_none()


async def get_company_by_slug(db: AsyncSession, slug: str) -> Company | None:
    result = await db.execute(select(Company).where(Company.slug == slug))
    return result.scalar_one_or_none()


async def list_companies(db: AsyncSession) -> Sequence[Company]:
    result = await db.execute(select(Company).order_by(Company.created_at.desc()))
    return result.scalars().all()


async def create_company(db: AsyncSession, name: str, slug: str) -> Company:
    company = Company(name=name, slug=slug)
    db.add(company)
    await db.flush()
    await db.refresh(company)
    return company


async def get_branding(db: AsyncSession, company_id: uuid.UUID) -> CompanyBranding | None:
    result = await db.execute(
        select(CompanyBranding).where(CompanyBranding.company_id == company_id)
    )
    return result.scalar_one_or_none()


async def upsert_branding(
    db: AsyncSession,
    company_id: uuid.UUID,
    style_guide: dict,
    primary_color: str | None,
    logo_url: str | None,
) -> CompanyBranding:
    branding = await get_branding(db, company_id)
    if branding is None:
        branding = CompanyBranding(company_id=company_id)
        db.add(branding)
    branding.style_guide = style_guide
    branding.primary_color = primary_color
    branding.logo_url = logo_url
    await db.flush()
    await db.refresh(branding)
    return branding
