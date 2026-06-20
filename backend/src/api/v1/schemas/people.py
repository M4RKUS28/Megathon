import uuid

from pydantic import BaseModel

from src.db.models.org import ROLE_ADMIN, ROLE_COURSE_CREATOR, ROLE_USER

VALID_ROLES = {ROLE_ADMIN, ROLE_COURSE_CREATOR, ROLE_USER}


class DepartmentResponse(BaseModel):
    id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None = None


class DepartmentCreate(BaseModel):
    name: str
    parent_id: uuid.UUID | None = None


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    role: str
    department_id: uuid.UUID | None = None
    manager_id: str | None = None


class UserUpdate(BaseModel):
    role: str | None = None
    department_id: uuid.UUID | None = None
    manager_id: str | None = None
