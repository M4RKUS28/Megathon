import uuid
from datetime import datetime

from pydantic import BaseModel


class CompanyResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    status: str
    created_at: datetime


class CompanyCreate(BaseModel):
    name: str
    slug: str
