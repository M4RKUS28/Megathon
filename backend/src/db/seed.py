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
from src.db.models.org import ROLE_ADMIN, ROLE_COURSE_CREATOR, ROLE_USER, Department
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

TEST_USERS = [
    {
        "username": "admin@acme.test",
        "email": "admin@acme.test",
        "first_name": "Ada",
        "last_name": "Admin",
        "password": "admin2026",
        "realm_roles": [ROLE_USER, ROLE_ADMIN],
        "display_name": "Ada Admin",
        "app_role": ROLE_ADMIN,
    },
    {
        "username": "creator@acme.test",
        "email": "creator@acme.test",
        "first_name": "Carla",
        "last_name": "Creator",
        "password": "creator2026",
        "realm_roles": [ROLE_USER, ROLE_COURSE_CREATOR],
        "display_name": "Carla Creator",
        "app_role": ROLE_COURSE_CREATOR,
    },
    {
        "username": "employee@acme.test",
        "email": "employee@acme.test",
        "first_name": "Erik",
        "last_name": "Employee",
        "password": "employee2026",
        "realm_roles": [ROLE_USER],
        "display_name": "Erik Employee",
        "app_role": ROLE_USER,
    },
]


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
    user.email = spec["email"]
    user.display_name = spec["display_name"]
    user.department_id = department_id
    user.manager_id = manager_id
    await update_user(
        db,
        user,
        role=spec["app_role"],
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

        specs = [DEMO_LEAD, DEMO_MEMBER, *TEST_USERS]
        subs: dict[str, str] = {}
        for spec in specs:
            sub = await ensure_user(
                username=spec["username"],
                email=spec["email"],
                first_name=spec["first_name"],
                last_name=spec["last_name"],
                password=spec["password"],
                realm_roles=spec["realm_roles"],
                company_slug=settings.demo_company_slug,
            )
            if sub is not None:
                subs[spec["username"]] = sub
        if not subs:
            return  # admin provisioning unavailable

        for spec in specs:
            sub = subs.get(spec["username"])
            if sub is None:
                continue
            manager_id = None
            if spec["username"] == DEMO_MEMBER["username"]:
                manager_id = subs.get(DEMO_LEAD["username"])
            elif spec["username"] == "employee@acme.test":
                manager_id = subs.get("creator@acme.test")
            department_id = None if spec["app_role"] == ROLE_ADMIN else dept_id
            await _ensure_app_user(
                db,
                sub=sub,
                company=company,
                spec=spec,
                department_id=department_id,
                manager_id=manager_id,
            )
        await db.commit()
