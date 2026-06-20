import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class InitiateUploadRequest(BaseModel):
    filename: str
    content_type: str


class ConfirmUploadRequest(BaseModel):
    size_bytes: int


class UploadIntentResponse(BaseModel):
    file_id: uuid.UUID
    upload_url: str
    object_name: str


class FileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: str
    filename: str
    object_name: str
    content_type: str
    size_bytes: int
    created_at: datetime
    updated_at: datetime


class FileListResponse(BaseModel):
    items: list[FileResponse]
