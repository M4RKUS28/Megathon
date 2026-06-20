"""Idempotent seed of the demo tenant (Acme) used to showcase white-labeling.

Runs on backend startup. Safe to run repeatedly: it only creates rows that do
not already exist.
"""

import logging

from sqlalchemy import select

from src.config.settings import settings
from src.db.crud.company import (
    create_company,
    get_branding,
    get_company_by_slug,
    upsert_branding,
)
from src.db.database import AsyncSessionLocal
from src.db.models.org import Department

logger = logging.getLogger(__name__)

# Acme brand: indigo/violet, stored as HSL triples the CSS variables expect.
ACME_STYLE_GUIDE = {
    "companyName": "Acme Inc.",
    "logoUrls": ["https://api.dicebear.com/9.x/initials/svg?seed=Acme&backgroundColor=6d28d9"],
    "brandColors": ["#6d28d9", "#0ea5e9", "#f59e0b"],
    "fonts": ["Inter", "Sora"],
    "imageUrls": [],
    "websiteUrl": "https://acme.example.com",
}
ACME_PRIMARY_HSL = "262 83% 58%"
ACME_DEPARTMENTS = ["Engineering", "People & Culture", "Sales", "Operations"]


async def seed_demo_data() -> None:
    async with AsyncSessionLocal() as db:
        company = await get_company_by_slug(db, settings.demo_company_slug)
        if company is None:
            company = await create_company(
                db, name="Acme Inc.", slug=settings.demo_company_slug
            )
            logger.info("Seeded demo company '%s'", settings.demo_company_slug)

        if await get_branding(db, company.id) is None:
            await upsert_branding(
                db,
                company.id,
                style_guide=ACME_STYLE_GUIDE,
                primary_color=ACME_PRIMARY_HSL,
                logo_url=ACME_STYLE_GUIDE["logoUrls"][0],
            )
            logger.info("Seeded demo branding for '%s'", settings.demo_company_slug)

        existing = (
            await db.execute(select(Department.name).where(Department.company_id == company.id))
        ).scalars().all()
        for name in ACME_DEPARTMENTS:
            if name not in existing:
                db.add(Department(company_id=company.id, name=name))
        await db.commit()
