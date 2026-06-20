import uuid

from pydantic import BaseModel


class CompanySummary(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    status: str


class MeResponse(BaseModel):
    id: str
    email: str
    display_name: str
    role: str
    company: CompanySummary
