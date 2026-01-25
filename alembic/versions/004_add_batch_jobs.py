"""Add batch job tracking table

Revision ID: 004
Revises: 003
Create Date: 2024-01-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "batch_jobs",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("job_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("vendor_ids", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("total_count", sa.Integer(), nullable=False),
        sa.Column("success_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("results", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_batch_jobs_status", "batch_jobs", ["status"])
    op.create_index("idx_batch_jobs_created_at", "batch_jobs", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_batch_jobs_created_at", table_name="batch_jobs")
    op.drop_index("idx_batch_jobs_status", table_name="batch_jobs")
    op.drop_table("batch_jobs")
