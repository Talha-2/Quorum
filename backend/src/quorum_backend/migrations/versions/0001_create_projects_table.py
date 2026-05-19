"""create projects table

Revision ID: 0001
Revises:
Create Date: 2026-05-19

The project store: one row per project. ``data`` holds the full serialized
aggregate; the scalar columns are projections kept for indexing and listing.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "domain", sa.String(length=64), nullable=False, server_default="general"
        ),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("created_at", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.String(length=64), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.create_index("ix_projects_domain", "projects", ["domain"])
    op.create_index("ix_projects_updated_at", "projects", ["updated_at"])


def downgrade() -> None:
    op.drop_index("ix_projects_updated_at", table_name="projects")
    op.drop_index("ix_projects_domain", table_name="projects")
    op.drop_table("projects")
