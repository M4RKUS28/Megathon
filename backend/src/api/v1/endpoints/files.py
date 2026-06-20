import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import TokenData, get_current_user
from src.db.database import get_db
from src.services.file_service import (
    confirm_upload,
    get_download_url,
    initiate_upload,
    list_user_files,
    remove_file,
)
from src.api.v1.schemas.file import (
    ConfirmUploadRequest,
    FileListResponse,
    FileResponse,
    InitiateUploadRequest,
    UploadIntentResponse,
)

router = APIRouter(prefix="/files", tags=["files"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
UserDep = Annotated[TokenData, Depends(get_current_user)]


@router.post("/upload/initiate", response_model=UploadIntentResponse)
async def initiate(body: InitiateUploadRequest, db: DbDep, user: UserDep):
    intent = await initiate_upload(db, user.user_id, body.filename, body.content_type)
    return UploadIntentResponse(
        file_id=intent.file_id,
        upload_url=intent.upload_url,
        object_name=intent.object_name,
    )


@router.post("/upload/{file_id}/confirm", response_model=FileResponse)
async def confirm(file_id: uuid.UUID, body: ConfirmUploadRequest, db: DbDep, user: UserDep):
    file = await confirm_upload(db, file_id, user.user_id, body.size_bytes)
    return FileResponse.model_validate(file)


@router.get("", response_model=FileListResponse)
async def list_files(
    db: DbDep,
    user: UserDep,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    files = await list_user_files(db, user.user_id, offset=offset, limit=limit)
    return FileListResponse(items=[FileResponse.model_validate(f) for f in files])


@router.get("/{file_id}/download-url")
async def download_url(file_id: uuid.UUID, db: DbDep, user: UserDep):
    _, url = await get_download_url(db, file_id, user.user_id)
    return {"download_url": url}


@router.delete("/{file_id}", status_code=204)
async def delete(file_id: uuid.UUID, db: DbDep, user: UserDep):
    await remove_file(db, file_id, user.user_id)
