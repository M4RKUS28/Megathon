"""five_phase_pipeline: plan/spec/asset columns + richer enrollment tracking

Revision ID: a1b2c3d4e5f6
Revises: 458d3a95203f
Create Date: 2026-06-20 09:55:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "458d3a95203f"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _jsonb() -> postgresql.JSONB:
    return postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    # Phase 1-4 course artifacts and hosting URLs.
    op.add_column("courses", sa.Column("plan", _jsonb(), nullable=True))
    op.add_column("courses", sa.Column("spec", _jsonb(), nullable=True))
    op.add_column("courses", sa.Column("asset_manifest", _jsonb(), nullable=True))
    op.add_column("courses", sa.Column("asset_map", _jsonb(), nullable=True))
    op.add_column("courses", sa.Column("course_url", sa.String(length=1024), nullable=True))
    op.add_column("courses", sa.Column("iframe_url", sa.String(length=1024), nullable=True))

    # Phase 5 richer progress tracking.
    op.add_column("enrollments", sa.Column("current_page", sa.Integer(), nullable=True))
    op.add_column(
        "enrollments",
        sa.Column("time_spent_seconds", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "enrollments",
        sa.Column("quiz_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("enrollments", sa.Column("drop_off_point", sa.String(length=255), nullable=True))
    op.add_column(
        "enrollments",
        sa.Column("engagement_score", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "enrollments",
        sa.Column("certified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("enrollments", sa.Column("certificate_id", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("enrollments", "certificate_id")
    op.drop_column("enrollments", "certified")
    op.drop_column("enrollments", "engagement_score")
    op.drop_column("enrollments", "drop_off_point")
    op.drop_column("enrollments", "quiz_attempts")
    op.drop_column("enrollments", "time_spent_seconds")
    op.drop_column("enrollments", "current_page")

    op.drop_column("courses", "iframe_url")
    op.drop_column("courses", "course_url")
    op.drop_column("courses", "asset_map")
    op.drop_column("courses", "asset_manifest")
    op.drop_column("courses", "spec")
    op.drop_column("courses", "plan")
