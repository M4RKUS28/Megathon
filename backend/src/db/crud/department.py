import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.org import Department


async def list_departments(db: AsyncSession, company_id: uuid.UUID) -> Sequence[Department]:
    result = await db.execute(
        select(Department).where(Department.company_id == company_id).order_by(Department.name)
    )
    return result.scalars().all()


async def get_department(
    db: AsyncSession, company_id: uuid.UUID, department_id: uuid.UUID
) -> Department | None:
    result = await db.execute(
        select(Department).where(
            Department.id == department_id, Department.company_id == company_id
        )
    )
    return result.scalar_one_or_none()


async def create_department(
    db: AsyncSession, company_id: uuid.UUID, name: str, parent_id: uuid.UUID | None
) -> Department:
    dept = Department(company_id=company_id, name=name, parent_id=parent_id)
    db.add(dept)
    await db.flush()
    await db.refresh(dept)
    return dept


async def delete_department(db: AsyncSession, dept: Department) -> None:
    await db.delete(dept)
    await db.flush()
