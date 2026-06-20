import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import ForbiddenError, NotFoundError
from src.db.crud.file import (
    create_file,
    delete_file,
    get_file,
    get_user_files,
    update_file_size,
)
from src.db.models.file import File
from src.services.storage_service import (
    build_object_name,
    generate_download_url,
    generate_upload_url,
    remove_object,
)


@dataclass
class UploadIntent:
    file_id: uuid.UUID
    upload_url: str
    object_name: str


async def initiate_upload(
    db: AsyncSession,
    user_id: str,
    filename: str,
    content_type: str,
) -> UploadIntent:
    """Create DB record and return a presigned PUT URL for direct browser upload."""
    object_name = build_object_name(user_id, filename)
    upload_url = generate_upload_url(object_name)

    file = await create_file(
        db,
        user_id=user_id,
        filename=filename,
        object_name=object_name,
        content_type=content_type,
    )
    return UploadIntent(file_id=file.id, upload_url=upload_url, object_name=object_name)


async def confirm_upload(
    db: AsyncSession,
    file_id: uuid.UUID,
    user_id: str,
    size_bytes: int,
) -> File:
    """Called after the browser completes the PUT to update file size."""
    file = await get_file(db, file_id)
    if not file:
        raise NotFoundError("File")
    if file.user_id != user_id:
        raise ForbiddenError()
    await update_file_size(db, file_id, size_bytes)
    return file


async def list_user_files(db: AsyncSession, user_id: str, offset: int = 0, limit: int = 50):
    return await get_user_files(db, user_id, offset=offset, limit=limit)


async def get_download_url(
    db: AsyncSession, file_id: uuid.UUID, user_id: str
) -> tuple[File, str]:
    file = await get_file(db, file_id)
    if not file:
        raise NotFoundError("File")
    if file.user_id != user_id:
        raise ForbiddenError()
    url = generate_download_url(file.object_name)
    return file, url


async def remove_file(db: AsyncSession, file_id: uuid.UUID, user_id: str) -> None:
    file = await get_file(db, file_id)
    if not file:
        raise NotFoundError("File")
    if file.user_id != user_id:
        raise ForbiddenError()
    remove_object(file.object_name)
    await delete_file(db, file_id)
