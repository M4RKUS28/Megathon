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
from src.db.crud.user import create_user, get_user, update_user
from src.db.database import AsyncSessionLocal
from src.db.models.company import Company
from src.db.models.org import ROLE_COURSE_CREATOR, ROLE_USER, Department
from src.services.keycloak_admin import ensure_user

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

# Department whose lead/member the demo users belong to.
DEMO_DEPARTMENT = "People & Culture"

# Demo department lead — can create and assign courses (Keycloak role
# `course_creator`). Acts as the manager of the demo mock user below.
DEMO_LEAD = {
    "username": "lead@acme.test",
    "email": "lead@acme.test",
    "first_name": "Demo",
    "last_name": "Abteilungsleiter",
    "password": "lead2026",
    "realm_roles": [ROLE_USER, ROLE_COURSE_CREATOR],
    "display_name": "Demo Abteilungsleiter",
    "app_role": ROLE_COURSE_CREATOR,
}

# Demo learner — only sees the courses assigned to them (Keycloak role `user`).
DEMO_MEMBER = {
    "username": "mockuser@acme.test",
    "email": "mockuser@acme.test",
    "first_name": "Demo",
    "last_name": "Mock User",
    "password": "mockuser2026",
    "realm_roles": [ROLE_USER],
    "display_name": "Demo Mock User",
    "app_role": ROLE_USER,
}


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

    # Demo org users (Keycloak login + roles + app-side manager relationship).
    # Isolated in its own session so a Keycloak hiccup never rolls back the
    # company/branding/department seed above.
    try:
        await _seed_demo_org_users()
    except Exception:  # noqa: BLE001 — best-effort, never block boot
        logger.exception("Demo org-user seeding failed")


async def _ensure_app_user(
    db,
    *,
    sub: str,
    company: Company,
    spec: dict,
    department_id,
    manager_id: str | None,
) -> None:
    """Upsert the app-side mirror of a provisioned Keycloak user."""
    user = await get_user(db, sub)
    if user is None:
        user = await create_user(
            db,
            user_id=sub,
            company_id=company.id,
            email=spec["email"],
            display_name=spec["display_name"],
            role=spec["app_role"],
        )
        logger.info("Seeded demo user '%s' (%s)", spec["email"], spec["app_role"])
    # Keep role/department/manager in sync on every boot (idempotent). The role
    # is re-derived from the token on login; we set it so the people list is
    # correct even before the user's first sign-in.
    await update_user(
        db,
        user,
        role=spec["app_role"],
        department_id=department_id,
        manager_id=manager_id,
    )


async def _seed_demo_org_users() -> None:
    """Provision a demo department lead (course_creator) and a demo learner who
    reports to them — in Keycloak (login + roles) and the app DB (manager link).

    Idempotent and best-effort: needs Keycloak admin credentials; without them
    ``ensure_user`` returns ``None`` and this is skipped.
    """
    async with AsyncSessionLocal() as db:
        company = await get_company_by_slug(db, settings.demo_company_slug)
        if company is None:
            return

        dept = (
            await db.execute(
                select(Department).where(
                    Department.company_id == company.id,
                    Department.name == DEMO_DEPARTMENT,
                )
            )
        ).scalar_one_or_none()
        dept_id = dept.id if dept else None

        lead_sub = await ensure_user(
            username=DEMO_LEAD["username"],
            email=DEMO_LEAD["email"],
            first_name=DEMO_LEAD["first_name"],
            last_name=DEMO_LEAD["last_name"],
            password=DEMO_LEAD["password"],
            realm_roles=DEMO_LEAD["realm_roles"],
        )
        member_sub = await ensure_user(
            username=DEMO_MEMBER["username"],
            email=DEMO_MEMBER["email"],
            first_name=DEMO_MEMBER["first_name"],
            last_name=DEMO_MEMBER["last_name"],
            password=DEMO_MEMBER["password"],
            realm_roles=DEMO_MEMBER["realm_roles"],
        )
        if lead_sub is None or member_sub is None:
            return  # admin provisioning unavailable

        await _ensure_app_user(
            db, sub=lead_sub, company=company, spec=DEMO_LEAD,
            department_id=dept_id, manager_id=None,
        )
        await _ensure_app_user(
            db, sub=member_sub, company=company, spec=DEMO_MEMBER,
            department_id=dept_id, manager_id=lead_sub,
        )
        await db.commit()
