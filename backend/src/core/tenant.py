"""Multi-tenant request context.

Keycloak owns authentication; the application database owns tenant membership
and org structure. On every authenticated request we upsert an app-side `User`
row (keyed by the Keycloak subject) and resolve the active `Company`.

Tenant resolution (hackathon-pragmatic, shared DB + company_id):
  1. If the user already has an app row, use its company.
  2. Otherwise place the user in the company named by the token's optional
     `company_slug` claim, falling back to the demo company.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import settings
from src.core.auth import TokenData, get_current_user
from src.core.exceptions import AppError
from src.db.crud.company import create_company, get_company, get_company_by_slug
from src.db.crud.user import create_user, get_user
from src.db.database import get_db
from src.db.models.company import Company
from src.db.models.org import ROLE_ADMIN, ROLE_COURSE_CREATOR, ROLE_USER, User

DbDep = Annotated[AsyncSession, Depends(get_db)]

# Highest-privilege realm role wins when mapping Keycloak roles to an app role.
_ROLE_PRIORITY = [ROLE_ADMIN, ROLE_COURSE_CREATOR, ROLE_USER]


def role_from_token(token: TokenData) -> str:
    for role in _ROLE_PRIORITY:
        if token.has_role(role):
            return role
    return ROLE_USER


async def _get_or_create_demo_company(db: AsyncSession) -> Company:
    company = await get_company_by_slug(db, settings.demo_company_slug)
    if company is None:
        company = await create_company(db, name="Acme Inc.", slug=settings.demo_company_slug)
    return company


async def get_current_app_user(
    token: Annotated[TokenData, Depends(get_current_user)],
    db: DbDep,
) -> User:
    user = await get_user(db, token.user_id)
    derived_role = role_from_token(token)

    if user is None:
        slug = token.raw.get("company_slug") or settings.demo_company_slug
        company = await get_company_by_slug(db, slug)
        if company is None:
            company = await _get_or_create_demo_company(db)
        user = await create_user(
            db,
            user_id=token.user_id,
            company_id=company.id,
            email=token.email,
            display_name=token.username or token.email,
            role=derived_role,
        )
        return user

    # Keep the app role and contact details in sync with Keycloak each request.
    changed = False
    if user.role != derived_role:
        user.role = derived_role
        changed = True
    if token.email and user.email != token.email:
        user.email = token.email
        changed = True
    if changed:
        await db.flush()
    return user


AppUserDep = Annotated[User, Depends(get_current_app_user)]


async def get_current_company(user: AppUserDep, db: DbDep) -> Company:
    company = await get_company(db, user.company_id)
    if company is None:
        raise AppError(404, "Company not found")
    return company


CompanyDep = Annotated[Company, Depends(get_current_company)]


def require_app_role(*roles: str):
    """Dependency factory enforcing one of the given app roles."""

    async def _check(user: AppUserDep) -> User:
        if user.role not in roles:
            raise AppError(403, "Insufficient role")
        return user

    return _check
