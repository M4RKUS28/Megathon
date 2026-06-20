import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.org import User


async def get_user(db: AsyncSession, user_id: str) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def list_company_users(db: AsyncSession, company_id: uuid.UUID) -> Sequence[User]:
    result = await db.execute(
        select(User).where(User.company_id == company_id).order_by(User.created_at.desc())
    )
    return result.scalars().all()


async def create_user(
    db: AsyncSession,
    user_id: str,
    company_id: uuid.UUID,
    email: str,
    display_name: str,
    role: str,
) -> User:
    user = User(
        id=user_id,
        company_id=company_id,
        email=email,
        display_name=display_name,
        role=role,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def update_user(
    db: AsyncSession,
    user: User,
    *,
    role: str | None = None,
    manager_id: str | None = None,
    department_id: uuid.UUID | None = None,
) -> User:
    if role is not None:
        user.role = role
    if manager_id is not None:
        user.manager_id = manager_id
    if department_id is not None:
        user.department_id = department_id
    await db.flush()
    await db.refresh(user)
    return user
