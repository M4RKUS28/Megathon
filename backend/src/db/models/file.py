import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.db.database import Base


class File(Base):
    __tablename__ = "files"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    object_name: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    content_type: Mapped[str] = mapped_column(String(256), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
