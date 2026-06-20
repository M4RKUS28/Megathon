import uuid
from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.file import File


async def create_file(db: AsyncSession, **kwargs) -> File:
    file = File(**kwargs)
    db.add(file)
    await db.flush()
    await db.refresh(file)
    return file


async def get_file(db: AsyncSession, file_id: uuid.UUID) -> File | None:
    result = await db.execute(select(File).where(File.id == file_id))
    return result.scalar_one_or_none()


async def get_user_files(
    db: AsyncSession,
    user_id: str,
    offset: int = 0,
    limit: int = 50,
) -> Sequence[File]:
    result = await db.execute(
        select(File)
        .where(File.user_id == user_id)
        .order_by(File.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return result.scalars().all()


async def get_file_by_object_name(db: AsyncSession, object_name: str) -> File | None:
    result = await db.execute(select(File).where(File.object_name == object_name))
    return result.scalar_one_or_none()


async def delete_file(db: AsyncSession, file_id: uuid.UUID) -> bool:
    result = await db.execute(delete(File).where(File.id == file_id))
    return result.rowcount > 0


async def update_file_size(db: AsyncSession, file_id: uuid.UUID, size_bytes: int) -> File | None:
    file = await get_file(db, file_id)
    if file:
        file.size_bytes = size_bytes
        await db.flush()
        # Reload server-side onupdate columns (updated_at) within the async
        # context, so later attribute access doesn't trigger a lazy load.
        await db.refresh(file)
    return file
