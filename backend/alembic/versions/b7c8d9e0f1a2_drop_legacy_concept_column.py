"""drop_legacy_concept_column: remove the unused single-shot concept column

The legacy single-shot "concept" pipeline was replaced by the 5-phase
plan/spec/build pipeline; the ``courses.concept`` column is no longer written or
read by the application. Drop it.

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-06-20 22:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7c8d9e0f1a2"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("courses", "concept")


def downgrade() -> None:
    op.add_column(
        "courses",
        sa.Column("concept", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
