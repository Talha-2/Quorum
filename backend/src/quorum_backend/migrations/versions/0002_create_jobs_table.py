"""create jobs table

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-22

The pipeline job queue: one row per unit of pipeline work the worker
should perform. ``payload`` carries stage-specific parameters (rounds,
agents_per_round, ...).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("job_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.String(length=64), nullable=True),
        sa.Column("completed_at", sa.String(length=64), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_index("ix_jobs_project_id", "jobs", ["project_id"])
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_created_at", "jobs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_jobs_created_at", table_name="jobs")
    op.drop_index("ix_jobs_status", table_name="jobs")
    op.drop_index("ix_jobs_project_id", table_name="jobs")
    op.drop_table("jobs")
